import abc
import logging
import os
import re
import shutil
from collections import deque
from threading import Lock

from golem.core.fileshelper import copy_file_tree, common_dir
from golem.resource.client import IClientHandler, ClientCommands

logger = logging.getLogger(__name__)


def to_unicode(source):
    if not isinstance(source, unicode):
        return unicode(source)
    return source


class BaseAbstractResourceManager(IClientHandler):
    __metaclass__ = abc.ABCMeta

    root_path = os.path.abspath(os.sep)

    lock = Lock()
    queue_lock = Lock()

    def __init__(self, dir_manager, resource_dir_method=None):

        self.file_to_hash = dict()
        self.hash_to_path = dict()
        self.task_id_to_files = dict()
        self.task_common_prefixes = dict()
        self.download_queue = deque()

        self.current_downloads = 0
        self.dir_manager = dir_manager
        self.node_name = dir_manager.node_name

        if resource_dir_method:
            self.resource_dir_method = resource_dir_method
        else:
            self.resource_dir_method = dir_manager.get_task_resource_dir

        self.add_resource_dir(self.get_root_dir())

        if not hasattr(self, 'commands'):
            self.commands = ClientCommands

    def make_relative_path(self, path, task_id):
        norm_path = os.path.normpath(path)
        common_prefix = self.task_common_prefixes.get(task_id, '')
        return norm_path.replace(common_prefix, '', 1)

    @abc.abstractmethod
    def build_client_options(self, node_id, **kwargs):
        pass

    @staticmethod
    def split_path(path):
        return re.split('/|\\\\', path) if path else path

    def command_failed(self, exc, cmd, obj_id, **kwargs):
        logger.error("Resource manager: Error executing command '{}': {}"
                     .format(self.commands.names[cmd], exc.message))

    def copy_resources(self, from_dir):
        resource_dir = self.get_root_dir()
        from_dir = os.path.normpath(from_dir)
        if resource_dir == from_dir:
            return

        copy_file_tree(from_dir, resource_dir)

        self.update_resource_dir()

    def _copy_resource(self, src_path, filename, multihash, task_id):
        src_path = os.path.normpath(src_path)
        dst_path = self.get_resource_path(filename, task_id)
        filename = os.path.normpath(filename)

        if not os.path.exists(src_path):
            logger.error("Resource manager: cached file does not exist: {}"
                         .format(src_path))
            self.hash_to_path.pop(multihash, None)
            return None

        if src_path == dst_path:
            logger.error("Resource manager: cannot copy file over itself: {}"
                         .format(src_path, dst_path))
            return None

        dst_dir = os.path.dirname(dst_path)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)

        # we might perform linking instead, but it may eventually
        # result in a broken link chain
        if not os.path.exists(dst_path):
            shutil.copyfile(src_path, dst_path)

        return filename

    def update_resource_dir(self):
        self.__init__(self.dir_manager,
                      resource_dir_method=self.resource_dir_method)

    def get_root_dir(self):
        return self.dir_manager.get_node_dir()

    def get_resource_dir(self, task_id):
        return os.path.normpath(self.resource_dir_method(task_id))

    def get_resource_path(self, resource, task_id):
        resource_dir = self.get_resource_dir(task_id)
        return os.path.join(resource_dir, os.path.normpath(resource))

    def get_resource_entry(self, resource, task_id,
                           absolute_path=False, multihash=None):

        if absolute_path:
            res_path = os.path.normpath(resource)
        else:
            res_path = self.get_resource_path(resource, task_id)

        uni_path = to_unicode(res_path)
        if uni_path in self.file_to_hash:
            uni_multihash = self.file_to_hash[uni_path]
            if multihash and uni_multihash != unicode(multihash):
                return None
            if os.path.exists(res_path):
                return uni_path, uni_multihash
        return None

    @staticmethod
    def list_files(directory):
        result = []
        for src_dir, dirs, files in os.walk(directory):
            for f in files:
                result.append(os.path.join(src_dir, f))
        return result

    def get_cached(self, multihash):
        return self.hash_to_path.get(multihash, None)

    def task_entry_exists(self, entry, task_id):
        return task_id in self.task_id_to_files and \
            entry in self.task_id_to_files[task_id]

    def list_resources(self, task_id):
        return self.task_id_to_files.get(task_id, [])

    def list_split_resources(self, task_id):
        if task_id in self.task_id_to_files:
            files = self.task_id_to_files[task_id]
            if files:
                return [[self.split_path(f[0])] + f[1:] for f in files]
        return []

    @staticmethod
    def join_split_resources(resources):
        results = []
        for resource in resources:
            if resource:
                if isinstance(resource[0], basestring):
                    results.append(resource)
                else:
                    results.append([os.path.join(*resource[0])] + resource[1:])
        return results

    def add_resource_dir(self, dir_name,
                         client=None, client_options=None):
        pass

    def add_task(self, resource_coll, task_id,
                 client=None, client_options=None):

        if task_id in self.task_common_prefixes:
            return

        if resource_coll and len(resource_coll) == 1:
            common_prefix = os.path.dirname(next(iter(resource_coll)))
        else:
            common_prefix = common_dir(resource_coll)

        normpath = os.path.normpath(common_prefix)
        if normpath in ['.', '..']:
            normpath = ''

        self.task_common_prefixes[task_id] = normpath
        self.add_resources(resource_coll, task_id,
                           absolute_path=True,
                           client=client,
                           client_options=client_options)

    def remove_task(self, task_id, **kwargs):
        if task_id in self.task_id_to_files:
            files = self.task_id_to_files.get(task_id, [])
            for entry in files:
                self.file_to_hash.pop(entry[0], None)
            del self.task_id_to_files[task_id]

        self.task_common_prefixes.pop(task_id, None)

    def clear_resources(self):
        self.file_to_hash = dict()
        self.hash_to_path = dict()
        self.task_id_to_files = dict()
        self.task_common_prefixes = dict()

    def add_resources(self, resource_coll, task_id,
                      absolute_path=False, client=None, client_options=None):
        if not client:
            client = self.new_client()

        if resource_coll:
            for resource in resource_coll:
                self.add_resource(resource, task_id,
                                  absolute_path=absolute_path,
                                  client=client,
                                  client_options=client_options)

    def add_resource(self, resource, task_id,
                     absolute_path=False, client=None, client_options=None):

        if not client:
            client = self.new_client()

        resource = os.path.normpath(resource)

        if absolute_path:
            resource_path = resource
        else:
            resource_path = self.get_resource_path(resource, task_id)

        if not os.path.exists(resource_path):
            logger.error("Resource manager: resource '{}' does not exist"
                         .format(resource_path))
            return

        existing_entry = self.get_resource_entry(resource, task_id)
        if existing_entry:
            if not self.task_entry_exists(existing_entry, task_id):
                file_path, multihash = existing_entry
                self._register_resource(resource, file_path, multihash, task_id)
            else:
                logger.debug("Resource manager: resource '{}' already exists in task {}"
                             .format(resource, task_id))
            return

        is_dir = os.path.isdir(resource_path)
        response = self._handle_retries(client.add,
                                        self.commands.add,
                                        resource_path,
                                        recursive=is_dir,
                                        client_options=client_options)
        self._register_response(resource, response, task_id)

    def _register_response(self, resource, response, task_id):
        if isinstance(response, list):
            for entry in response:
                self._register_response(resource, entry, task_id)
        elif response and 'Hash' in response and 'Name' in response:
            if os.path.basename(response.get('Name')) != os.path.basename(resource):
                raise Exception("Invalid response {}".format(response))

            path = to_unicode(resource)
            multihash = to_unicode(response.get('Hash'))

            self._register_resource(resource, path, multihash, task_id)

    def _register_resource(self, resource, file_path, multihash, task_id):
        """
        Caches information on new file. Fails silently if a file does not exist.
        :param resource: original resource name
        :param file_path: file's path
        :param multihash: file's multihash
        :param task_id:   current task identifier
        :return: file's path relative to current resource path
        """
        if not os.path.exists(file_path):
            if os.path.isabs(file_path):
                raise Exception("Resource manager: File not found {} ({})"
                                .format(file_path, multihash))
            return

        norm_file_path = os.path.normpath(file_path)
        norm_resource = os.path.normpath(resource)

        if not norm_file_path.endswith(norm_resource):
            raise Exception("Resource manager: Invalid resource path {} ({})"
                            .format(file_path, multihash))

        name = self.make_relative_path(file_path, task_id)

        if task_id not in self.task_id_to_files:
            self.task_id_to_files[task_id] = []

        self.file_to_hash[name] = multihash
        self.hash_to_path[multihash] = file_path
        self.task_id_to_files[task_id].append([name, multihash])

        logger.debug("Resource manager: Resource registered {} ({})".format(file_path, multihash))
        return name

    def pin_resource(self, multihash, client=None, client_options=None):
        pass

    def unpin_resource(self, multihash, client=None, client_options=None):
        pass

    def pull_resource(self, filename, multihash, task_id,
                      success, error,
                      client=None, client_options=None, async=True, pin=True):

        filename = os.path.normpath(filename)

        if self.get_resource_entry(filename, task_id, multihash=multihash):
            success(filename, multihash, task_id)
            return

        def success_wrapper(*args, **kwargs):
            with self.lock:
                self.current_downloads -= 1

            result = args[0][0]
            result_filename = result[0]
            result_multihash = result[1]
            result_path = self.get_resource_path(result_filename, task_id)

            self._clear_retry(self.commands.get, result_multihash)

            if pin:
                self._register_resource(result_filename,
                                        result_path,
                                        result_multihash,
                                        task_id)
                self.pin_resource(result_multihash)

            logger.debug("Resource manager: {} ({}) downloaded"
                         .format(result_filename, result_multihash))

            success(filename, result_multihash, task_id)
            self.__process_queue()

        def error_wrapper(exc, *args, **kwargs):
            with self.lock:
                self.current_downloads -= 1

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

        copied = self.__copy_cached(filename, multihash, task_id)
        if copied:
            with self.lock:
                self.current_downloads += 1
            success_wrapper([[filename, multihash]])
            return

        out_path = self.get_resource_path(filename, task_id)
        out_dir = out_path.rsplit(os.sep, 1)

        if out_dir and len(out_dir) > 1:
            if not os.path.exists(out_dir[0]):
                os.makedirs(out_dir[0])

        if self.__can_download():
            with self.lock:
                self.current_downloads += 1
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

    def __copy_cached(self, filename, multihash, task_id):
        cached_path = self.get_cached(multihash)

        if cached_path and os.path.exists(cached_path):
            copied_filename = self._copy_resource(cached_path,
                                                  filename,
                                                  multihash,
                                                  task_id)
            if copied_filename:
                logger.debug("Resource manager: Resource copied {} ({})"
                             .format(copied_filename, multihash))
                return True

        return None

    def __pull(self, filename, multihash, task_id,
               success, error,
               client=None, client_options=None, async=True):

        if not client:
            client = self.new_client()
        res_dir = self.get_resource_dir(task_id)

        if async:
            self._async_call(client.get_file,
                             success,
                             error,
                             multihash=multihash,
                             filename=filename,
                             filepath=res_dir,
                             client_options=client_options)
        else:
            try:
                data = client.get_file(multihash,
                                       filename=filename,
                                       filepath=res_dir,
                                       client_options=client_options)
                success(data)
            except Exception as e:
                error(e)

    def __can_download(self):
        with self.lock:
            max_dl = self.config.max_concurrent_downloads
            return max_dl < 1 or self.current_downloads < max_dl

    def __push_to_queue(self, *args):
        with self.queue_lock:
            self.download_queue.append(args)

    def __process_queue(self):
        params = None

        with self.queue_lock:
            if self.download_queue:
                params = self.download_queue.popleft()

        if params:
            self.pull_resource(*params)
