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


class Resource(object):

    def __init__(self, resource_hash, task_id=None, path=None):
        self._path_split = None
        self._path = None

        self.hash = resource_hash
        self.task_id = task_id
        self.path = path

    def __eq__(self, other):
        return self.task_id == other.task_id and \
            self.hash == other.hash and \
            self.path == other.path

    def __str__(self):
        return '({}, task: {})'.format(
            self.hash, self.task_id)

    def __unicode__(self):
        return unicode(self.__str__())

    def __repr__(self):
        return str(self)

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, value):
        if value is None:
            self._path_split = None
        else:
            self._path_split = split_path(value)
        self._path = value

    @property
    def path_split(self):
        return self._path_split

    @property
    def exists(self):
        return self.path and os.path.exists(self.path)

    def contains_file(self, name):
        raise NotImplementedError()


class FileResource(Resource):

    def __init__(self, file_name, resource_hash, task_id=None, path=None):
        super(FileResource, self).__init__(resource_hash, task_id=task_id, path=path)
        self.file_name = norm_path(file_name)

    def __eq__(self, other):
        return super(FileResource, self).__eq__(other) and \
            self.file_name == other.file_name

    def __str__(self):
        return '{} ({}, task: {})'.format(
            self.file_name, self.hash, self.task_id)

    def contains_file(self, name):
        return os.path.basename(self.file_name) == name


class ResourceBundle(Resource):

    def __init__(self, files, bundle_hash, task_id=None, path=None):
        super(ResourceBundle, self).__init__(bundle_hash, task_id=task_id, path=path)
        self._files = None
        self._files_split = None
        self.files = files

    def __eq__(self, other):
        return super(ResourceBundle, self).__eq__(other) and \
            self.files == other.list_files

    def __str__(self):
        return '{} (bundle: {}, task: {})'.format(
            self.files, self.hash, self.task_id)

    @property
    def files(self):
        return self._files

    @files.setter
    def files(self, value):
        self._files = value
        if value:
            self._files_split = []
            for v in value:
                self._files_split.append(split_path(v))

    @property
    def files_split(self):
        return self._files_split

    def contains_file(self, name):
        if self._files:
            return any([os.path.basename(f) == name
                        for f in self._files])
        return False


class ResourceCache(object):

    def __init__(self):
        self._lock = Lock()
        # hash to resource
        self._hash_to_res = dict()
        # path to resource
        self._path_to_res = dict()
        # category to relative file path
        self._cat_to_res = dict()
        # category to common path for resources
        self._cat_to_prefix = dict()

    def add_resource(self, resource):
        category = resource.task_id

        with self._lock:
            resource_list = self._cat_to_res.get(category)
            if not resource_list:
                self._cat_to_res[category] = resource_list = list()
            resource_list.append(resource)

            self._hash_to_res[resource.hash] = resource
            self._path_to_res[resource.path] = resource

    def get_by_hash(self, resource_hash, default=None):
        return self._hash_to_res.get(resource_hash, default)

    def get_by_path(self, resource_path, default=None):
        return self._path_to_res.get(resource_path, default)

    def has_resource(self, resource):
        if resource.task_id and resource.task_id not in self._cat_to_res:
            return False
        if resource.hash and resource.hash not in self._hash_to_res:
            return False
        return resource.path in self._path_to_res

    def get_resources(self, category, default=None):
        return self._cat_to_res.get(category, default or [])

    def remove_resources(self, category):
        with self._lock:
            return self._cat_to_res.pop(category, [])

    def set_prefix(self, category, prefix):
        self._cat_to_prefix[category] = norm_path(prefix)

    def get_prefix(self, category, default=''):
        return self._cat_to_prefix.get(category, default)

    def remove(self, category):
        resources = self.remove_resources(category)
        for r in resources:
            self._hash_to_res.pop(r.hash, None)
            self._path_to_res.pop(r.path, None)
        self._cat_to_prefix.pop(category, None)

    def clear(self):
        self._hash_to_res = dict()
        self._path_to_res = dict()
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

    def get_root(self):
        return self.dir_manager.get_node_dir()

    def get_resources(self, task_id):
        return self.cache.get_resources(task_id)

    def has_resource(self, resource):
        return self.cache.has_resource(resource) and resource.exists

    @staticmethod
    def split_resources(resources):
        return [[r.path_split, r.hash] for r in resources]

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

    def copy(self, src_path, dst_relative_path, category):

        dst_relative_path = norm_path(dst_relative_path)
        dst_path = self.get_path(dst_relative_path, category)
        src_path = norm_path(src_path)

        make_path_dirs(dst_path)

        if os.path.isfile(dst_path):
            os.remove(dst_path)
        elif os.path.isdir(dst_path):
            shutil.rmtree(dst_path)

        if os.path.isfile(src_path):
            shutil.copyfile(src_path, dst_path)
        elif os.path.isdir(src_path):
            copy_file_tree(src_path, dst_path)
        else:
            raise ValueError("Error reading source path: '{}'"
                             .format(src_path))

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

    def get_resources(self, task_id):
        return self.storage.get_resources(task_id)

    def to_wire(self, resources):
        return self.storage.split_resources(resources)

    def from_wire(self, resources):
        return self.storage.join_resources(resources)

    def remove_task(self, task_id, client_options=None):
        self.storage.cache.remove(task_id)

    def add_task(self, files, task_id,
                 client=None, client_options=None):

        if self.storage.cache.get_prefix(task_id):
            logger.warn("Resource manager: Task {} already exists"
                        .format(task_id))
            return

        if len(files) == 1:
            prefix = os.path.dirname(next(iter(files)))
        else:
            prefix = common_dir(files)

        self.storage.cache.set_prefix(task_id, prefix)
        self.add_files(files, task_id,
                       absolute_path=True,
                       client=client,
                       client_options=client_options)

    def add_files(self, files, task_id,
                  absolute_path=False, client=None, client_options=None):

        if files:
            client = client or self.new_client()

            for path in files:
                self.add_file(path, task_id,
                              absolute_path=absolute_path,
                              client=client,
                              client_options=client_options)

    def add_file(self, path, task_id,
                 absolute_path=False, client=None, client_options=None):

        client = client or self.new_client()
        path = norm_path(path)

        if absolute_path:
            file_path = path
        else:
            file_path = self.storage.get_path(path, task_id)

        if not os.path.exists(file_path):
            logger.error("Resource manager: file '{}' does not exist"
                         .format(file_path))
            return

        local = self.storage.cache.get_by_path(path)
        if local and local.exists and local.task_id == task_id:
            logger.debug("Resource manager: file '{}' already exists in task {}"
                         .format(path, task_id))
        else:
            response = self._handle_retries(client.add,
                                            self.commands.add,
                                            file_path,
                                            client_options=client_options)
            self._cache_response(path, response, task_id)

    def copy_files(self, from_dir):
        self.storage.copy_dir(from_dir)
        AbstractResourceManager.__init__(self, self.storage.dir_manager,
                                         self.storage.resource_dir_method)

    def pull_resource(self, entry, task_id,
                      success, error,
                      client=None, client_options=None, async=True, pin=True):

        resource = self._wrap_resource(entry, task_id)

        if self.storage.has_resource(resource):
            success(entry, task_id)
            return

        def success_wrapper(*_, **kwargs):
            self.__dec_downloads()
            self._clear_retry(self.commands.get, resource.hash)

            if pin:
                self._cache_resource(resource)
                self.pin_resource(resource.hash)

            logger.debug("Resource manager: {} ({}) downloaded"
                         .format(resource.path, resource.hash))

            success(entry, task_id)
            self.__process_queue()

        def error_wrapper(exception, *_, **kwargs):
            self.__dec_downloads()

            if self._can_retry(exception, self.commands.get, resource.hash):
                self.pull_resource(resource, task_id,
                                   client_options=client_options,
                                   success=success,
                                   error=error,
                                   async=async,
                                   pin=pin)
            else:
                logger.error("Resource manager: error downloading {} ({}): {}"
                             .format(resource.path, resource.hash, exception))

                error(exception, entry, task_id)
                self.__process_queue()

        make_path_dirs(self.storage.get_path(resource.path, task_id))
        existing = self.storage.cache.get_by_hash(resource.hash)

        if existing:

            self.__inc_downloads()
            try:
                self.storage.copy(existing.path, resource.path, task_id)
            except Exception as exc:
                error_wrapper(exc)
            else:
                success_wrapper(entry)

        else:

            if self.__can_download():
                self.__inc_downloads()
                self.__pull(resource, task_id,
                            success=success_wrapper,
                            error=error_wrapper,
                            client=client,
                            client_options=client_options,
                            async=async)
            else:
                self.__push_to_queue(resource, task_id,
                                     success, error,
                                     client, client_options, async, pin)

    def command_failed(self, exc, cmd, obj_id, **kwargs):
        logger.error("Resource manager: Error executing command '{}': {}"
                     .format(cmd.name, exc))

    def _cache_response(self, resource_name, response, task_id):
        if isinstance(response, list):
            for entry in response:
                self._cache_response(resource_name, entry, task_id)

        elif response and 'Hash' in response and 'Name' in response:
            if os.path.basename(response.get('Name')) != os.path.basename(resource_name):
                raise Exception("Resource manager: Invalid response {}".format(response))

            res_path = to_unicode(resource_name)
            res_hash = to_unicode(response.get('Hash'))
            resource = self._wrap_resource((res_path, res_hash), task_id)
            self._cache_resource(resource)

    def _cache_resource(self, resource):
        """
        Caches information on a new resource.
        :param resource: resource object
        :return: file's path relative to task resource path
        """
        if not os.path.exists(resource.path):
            if os.path.isabs(resource.path):
                raise Exception("Resource manager: File not found {} ({})"
                                .format(resource.path, resource.hash))
            logger.warn("Resource does not exist: {}"
                        .format(resource.path))
            return

        name = self.storage.relative_path(resource.path, resource.task_id)
        self.storage.cache.add_resource(resource)

        logger.debug("Resource manager: Resource cached: {}".format(resource))
        return name

    def _wrap_resource(self, resource, task_id=None):
        resource_path, resource_hash = resource
        path = self.storage.get_path(resource_path, task_id)
        return FileResource(resource_path, resource_hash,
                            task_id=task_id, path=path)

    def __pull(self, resource, task_id,
               success, error,
               client=None, client_options=None, async=True):

        client = client or self.new_client()
        directory = self.storage.get_dir(task_id)
        file_name = self.storage.relative_path(task_id, resource.path)

        kwargs = dict(
            multihash=resource.hash,
            filename=file_name,
            filepath=directory,
            client_options=client_options
        )

        print "GET", kwargs

        if async:
            self._async_call(client.get,
                             success, error,
                             **kwargs)
        else:
            try:
                data = client.get(**kwargs)
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
