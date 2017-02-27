import abc
import logging
import os
import re
import shutil
from collections import deque
from threading import Lock

from golem.core.fileshelper import copy_file_tree, common_dir
from golem.resource.client import IClientHandler, ClientCommands, ClientHandler, ClientConfig, TestClient

logger = logging.getLogger(__name__)


def to_unicode(string):
    if not isinstance(string, unicode):
        return unicode(string)
    return string


def split_path(path):
    return re.split('/|\\\\', path) if path else path


def make_path_dirs(path):
    out_dir = path.rsplit(os.sep, 1)
    path = out_dir[0] if out_dir else None
    if path and not os.path.exists(path):
        os.makedirs(path)


def norm_path(path):
    normpath = os.path.normpath(path)
    split = os.path.split(normpath)
    while split and split[0] in ['.', '..']:
        split = split[1:]
    return os.path.join(*split) if split else ''


def dir_files(directory):
    result = []
    for src_dir, dirs, files in os.walk(directory):
        for f in files:
            result.append(os.path.join(src_dir, f))
    return result


class ResourceCache(object):

    def __init__(self):
        self._lock = Lock()
        # hash to file/dir path
        self._hash_to_path = dict()
        # file/dir path to hash
        self._path_to_hash = dict()
        # category to relative file path
        self._cat_to_res = dict()
        # category to common path for resources
        self._cat_to_prefix = dict()

    def set_path(self, resource_hash, path):
        self._hash_to_path[resource_hash] = path
        self._path_to_hash[path] = resource_hash

    def get_path(self, resource_hash, default=None):
        return self._hash_to_path.get(resource_hash, default)

    def get_hash(self, path, default=None):
        return self._path_to_hash.get(path, default)

    def remove_path(self, resource_hash):
        path = self._hash_to_path.pop(resource_hash, None)
        self._path_to_hash.pop(path, None)
        return path

    def add_resource(self, category, resource):
        with self._lock:
            resource_list = self._cat_to_res.get(category)
            if not resource_list:
                self._cat_to_res[category] = resource_list = list()
            resource_list.append(resource)

    def has_resource(self, category, resource):
        return resource in self.get_resources(category)

    def has_file(self, entry, category):
        return entry in self._cat_to_res.get(category, [])

    def set_resources(self, category, resources):
        with self._lock:
            self._cat_to_res[category] = resources

    def get_resources(self, category, default=None):
        return self._cat_to_res.get(category, default or [])

    def remove_resources(self, category):
        with self._lock:
            return self._cat_to_res.pop(category, [])

    def set_prefix(self, category, prefix):
        self._cat_to_prefix[category] = prefix

    def get_prefix(self, category, default=''):
        return self._cat_to_prefix.get(category, default)

    def remove_prefix(self, category):
        return self._cat_to_prefix.pop(category, None)

    def remove(self, category):
        resources = self.remove_resources(category)
        for r in resources:
            self.remove_path(r[1])
        self.remove_prefix(category)

    def clear(self):
        self._hash_to_path = dict()
        self._path_to_hash = dict()
        self._cat_to_res = dict()
        self._cat_to_prefix = dict()


class ResourceStorage(object):

    def __init__(self, dir_manager, resource_dir_method):
        self.dir_manager = dir_manager
        self.resource_dir_method = resource_dir_method
        self.cache = ResourceCache()

    def list_dir(self, dir_name):
        return self.dir_manager.list_dir_names(dir_name)

    def get_dir(self, category):
        return norm_path(self.resource_dir_method(category))

    def get_path(self, relative_file_path, category):
        resource_dir = self.get_dir(category)
        return os.path.join(resource_dir, norm_path(relative_file_path))

    def get_path_and_hash(self, path, category,
                          multihash=None, absolute_path=False):

        if absolute_path:
            res_path = norm_path(path)
        else:
            res_path = self.get_path(path, category)

        res_path = to_unicode(res_path)

        if multihash:
            if self.cache.get_path(multihash) == res_path:
                return res_path, multihash
        else:
            multihash = self.cache.get_hash(res_path)
            if multihash:
                return res_path, multihash

    def get_root(self):
        return self.dir_manager.get_node_dir()

    def get_resources(self, task_id):
        return self.cache.get_resources(task_id)

    @staticmethod
    def split_resources(resources):
        return [[split_path(r[0])] + r[1:] for r in resources]

    @staticmethod
    def join_resources(resources):
        results = []

        for r in resources:
            if not r:
                continue
            elif isinstance(r[0], basestring):
                results.append(r)
            elif r[0]:
                results.append([os.path.join(*r[0])] + r[1:])

        return results

    def relative_path(self, path, category):
        path = norm_path(path)
        common_prefix = self.cache.get_prefix(category)
        return_path = path.replace(common_prefix, '', 1)

        if common_prefix:
            while return_path and return_path.startswith(os.path.sep):
                return_path = return_path[1:]
        return return_path

    def copy_dir(self, src_dir):

        root_dir = self.get_root()
        src_dir = norm_path(src_dir)

        if root_dir != src_dir:
            copy_file_tree(src_dir, root_dir)
            return True

    def copy_file(self, src_path, dst_relative_path, category):

        dst_path = self.get_path(dst_relative_path, category)
        src_path = norm_path(src_path)
        dst_relative_path = norm_path(dst_relative_path)

        make_path_dirs(dst_path)
        if os.path.exists(dst_path):
            os.remove(dst_path)

        try:
            shutil.copyfile(src_path, dst_path)
        except OSError as e:
            logger.error("Resource storage: Error copying {} (as {}): {}"
                         .format(src_path, dst_relative_path, e))
        else:
            return True

    def copy_cached(self, dst_relative_path, res_hash, category):

        cached_path = self.cache.get_path(res_hash)
        if cached_path and os.path.exists(cached_path):

            if self.copy_file(cached_path, dst_relative_path, category):
                logger.debug("Resource storage: Resource copied {} ({})"
                             .format(dst_relative_path, res_hash))
                return True

    def clear_cache(self):
        self.cache.clear()


class AbstractResourceManager(IClientHandler):
    __metaclass__ = abc.ABCMeta

    lock = Lock()
    queue_lock = Lock()

    def __init__(self, dir_manager, resource_dir_method=None):

        self.download_queue = deque()
        self.current_downloads = 0
        self.storage = ResourceStorage(dir_manager, resource_dir_method or dir_manager.get_task_resource_dir)
        self.index_resources(self.storage.get_root())

        if not hasattr(self, 'commands'):
            self.commands = ClientCommands

    @abc.abstractmethod
    def build_client_options(self, node_id, **kwargs):
        pass

    def index_resources(self, dir_name, client=None, client_options=None):
        pass

    def pin_resource(self, multihash, client=None, client_options=None):
        pass

    def unpin_resource(self, multihash, client=None, client_options=None):
        pass

    def add_task(self, resources, task_id,
                 client=None, client_options=None):

        if self.storage.cache.get_prefix(task_id):
            logger.warn("Resource manager: Not re-adding task {}"
                        .format(task_id))
            return

        if resources and len(resources) == 1:
            prefix = os.path.dirname(next(iter(resources)))
        else:
            prefix = common_dir(resources)

        prefix = norm_path(prefix)
        self.storage.cache.set_prefix(task_id, prefix)
        self.add_resources(resources, task_id,
                           absolute_path=True,
                           client=client,
                           client_options=client_options)

    def remove_task(self, task_id, **kwargs):
        self.storage.cache.remove(task_id)

    def add_resources(self, resources, task_id,
                      absolute_path=False, client=None, client_options=None):
        client = client or self.new_client()

        if resources:
            for resource in resources:
                self.add_resource(resource, task_id,
                                  absolute_path=absolute_path,
                                  client=client,
                                  client_options=client_options)

    def add_resource(self, resource, task_id,
                     absolute_path=False, client=None, client_options=None):

        client = client or self.new_client()
        resource = norm_path(resource)

        if absolute_path:
            resource_path = resource
        else:
            resource_path = self.storage.get_path(resource, task_id)

        if not os.path.exists(resource_path):
            logger.error("Resource manager: resource '{}' does not exist"
                         .format(resource_path))
            return

        disk_resource = self.storage.get_path_and_hash(resource, task_id)

        if disk_resource:
            if self.storage.cache.has_file(disk_resource, task_id):
                logger.debug("Resource manager: resource '{}' already exists in task {}"
                             .format(resource, task_id))
            else:
                file_path, multihash = disk_resource
                self._cache_resource(resource, file_path, multihash, task_id)
        else:
            is_dir = os.path.isdir(resource_path)
            response = self._handle_retries(client.add,
                                            self.commands.add,
                                            resource_path,
                                            recursive=is_dir,
                                            client_options=client_options)
            self._cache_response(resource, response, task_id)

    def copy_resources(self, from_dir):
        self.storage.copy_dir(from_dir)
        AbstractResourceManager.__init__(self, self.storage.dir_manager,
                                         self.storage.resource_dir_method)

    def pull_resource(self, filename, multihash, task_id,
                      success, error,
                      client=None, client_options=None, async=True, pin=True):

        filename = norm_path(filename)

        if self.storage.get_path_and_hash(filename, task_id, multihash=multihash):
            success(filename, multihash, task_id)
            return

        def success_wrapper(result, *args, **kwargs):
            self.__dec_downloads()

            result_filename = result['Name']
            result_multihash = result['Hash']
            result_path = self.storage.get_path(result_filename, task_id)

            self._clear_retry(self.commands.get, result_multihash)

            if pin:
                self._cache_resource(result_filename,
                                     result_path,
                                     result_multihash,
                                     task_id)
                self.pin_resource(result_multihash)

            logger.debug("Resource manager: {} ({}) downloaded"
                         .format(result_filename, result_multihash))

            success(filename, result_multihash, task_id)
            self.__process_queue()

        def error_wrapper(exc, *args, **kwargs):
            self.__dec_downloads()

            if self._can_retry(exc, self.commands.get, multihash):
                self.pull_resource(filename,
                                   multihash,
                                   task_id,
                                   client_options=client_options,
                                   success=success,
                                   error=error,
                                   async=async,
                                   pin=pin)
            else:
                logger.error("Resource manager: error downloading {} ({}): {}"
                             .format(filename, multihash, exc))

                error(exc, filename, multihash, task_id)
                self.__process_queue()

        cached_path = self.storage.cache.get_path(multihash)
        make_path_dirs(self.storage.get_path(filename, task_id))

        if cached_path and os.path.exists(cached_path):

            self.__inc_downloads()
            try:
                self.storage.copy_cached(filename, multihash, task_id)
            except Exception as exc:
                error_wrapper(exc)
            else:
                success_wrapper(dict(Name=filename, Hash=multihash))

        else:

            if self.__can_download():
                self.__inc_downloads()
                self.__pull(filename, multihash, task_id,
                            success=success_wrapper,
                            error=error_wrapper,
                            client=client,
                            client_options=client_options,
                            async=async)
            else:
                self.__push_to_queue(filename, multihash, task_id,
                                     success, error,
                                     client, client_options, async, pin)

    def command_failed(self, exc, cmd, obj_id, **kwargs):
        logger.error("Resource manager: Error executing command '{}': {}"
                     .format(cmd.name, exc))

    def _cache_response(self, resource, response, task_id):
        if isinstance(response, list):
            for entry in response:
                self._cache_response(resource, entry, task_id)
        elif response and 'Hash' in response and 'Name' in response:
            if os.path.basename(response.get('Name')) != os.path.basename(resource):
                raise Exception("Resource manager: Invalid response {}".format(response))

            res_path = to_unicode(resource)
            res_hash = to_unicode(response.get('Hash'))

            self._cache_resource(resource, res_path, res_hash, task_id)

    def _cache_resource(self, resource, res_path, res_hash, task_id):
        """
        Caches information on a new resource.
        :param resource: original resource name
        :param res_path: resource path
        :param res_hash: resource hash
        :param task_id:   current task identifier
        :return: file's path relative to task resource path
        """
        if not os.path.exists(res_path):
            if os.path.isabs(res_path):
                raise Exception("Resource manager: File not found {} ({})"
                                .format(res_path, res_hash))
            return

        norm_file_path = norm_path(res_path)
        norm_resource = norm_path(resource)

        if not norm_file_path.endswith(norm_resource):
            raise Exception("Resource manager: Invalid resource path {} ({})"
                            .format(res_path, res_hash))

        name = self.storage.relative_path(res_path, task_id)
        self.storage.cache.add_resource(task_id, [name, res_hash])

        if res_hash:
            self.storage.cache.set_path(res_hash, res_path)
        else:
            logger.warn("Resource manager: No hash provided for {}".format(res_path))

        logger.debug("Resource manager: Resource registered {} ({})".format(res_path, res_hash))
        return name

    def __pull(self, filename, multihash, task_id,
               success, error,
               client=None, client_options=None, async=True):

        client = client or self.new_client()
        directory = self.storage.get_dir(task_id)

        kwargs = dict(
            multihash=multihash,
            filename=filename,
            filepath=directory,
            client_options=client_options
        )

        if async:
            self._async_call(client.get_file,
                             success, error,
                             **kwargs)
        else:
            try:
                data = client.get_file(**kwargs)
                success(data)
            except Exception as e:
                error(e)

    def __can_download(self):
        max_dl = self.config.max_concurrent_downloads
        with self.lock:
            return max_dl < 1 or self.current_downloads < max_dl

    def __inc_downloads(self):
        with self.lock:
            self.current_downloads += 1

    def __dec_downloads(self):
        with self.lock:
            self.current_downloads -= 1

    def __push_to_queue(self, *params):
        with self.queue_lock:
            self.download_queue.append(params)

    def __process_queue(self):
        params = None

        with self.queue_lock:
            if self.download_queue:
                params = self.download_queue.popleft()

        if params:
            self.pull_resource(*params)


class TestResourceManager(AbstractResourceManager, ClientHandler):

    def __init__(self, dir_manager, resource_dir_method=None):
        AbstractResourceManager.__init__(self, dir_manager, resource_dir_method)
        ClientHandler.__init__(self, ClientCommands, ClientConfig())

    def build_client_options(self, node_id, **kwargs):
        return TestClient.build_options(node_id, **kwargs)

    def new_client(self):
        return TestClient()
