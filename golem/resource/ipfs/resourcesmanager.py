import logging
import os
import re
import shutil
import time
from collections import deque
from threading import Lock

from golem.core.fileshelper import copy_file_tree, common_dir
from golem.network.ipfs.client import IPFSCommands, IPFSClientHandler

__all__ = ['IPFSResourceManager']
logger = logging.getLogger(__name__)


def to_unicode(source):
    if not isinstance(source, unicode):
        return unicode(source)
    return source


class IPFSResourceManager(IPFSClientHandler):

    root_path = os.path.abspath(os.sep)
    lock = Lock()

    def __init__(self, dir_manager,
                 config=None,
                 resource_dir_method=None):

        super(IPFSResourceManager, self).__init__(config)

        self.file_to_hash = dict()
        self.hash_to_path = dict()
        self.task_id_to_files = dict()
        self.task_common_prefixes = dict()
        self.download_queue = deque()

        self.current_downloads = 0
        self.dir_manager = dir_manager
        self.node_name = dir_manager.node_name

        if not resource_dir_method:
            self.resource_dir_method = dir_manager.get_task_resource_dir
        else:
            self.resource_dir_method = resource_dir_method

        self.add_resource_dir(self.get_resource_root_dir())

    def make_relative_path(self, path, task_id):
        norm_path = os.path.normpath(path)
        common_prefix = self.task_common_prefixes.get(task_id, '')
        return norm_path.replace(common_prefix, '', 1)

    @staticmethod
    def split_path(path):
        return re.split('/|\\\\', path) if path else path

    def copy_resources(self, from_dir):
        resource_dir = self.get_resource_root_dir()
        from_dir = os.path.normpath(from_dir)
        if resource_dir == from_dir:
            return

        copy_file_tree(from_dir, resource_dir)
        file_names = next(os.walk(from_dir))[2]

        for f in file_names:
            os.remove(os.path.join(from_dir, f))

        self.update_resource_dir()

    def _copy_resource(self, src_path, filename, multihash, task_id):
        src_path = os.path.normpath(src_path)
        dst_path = self.get_resource_path(filename, task_id)
        filename = os.path.normpath(filename)

        if not os.path.exists(src_path):
            logger.error("IPFS: cached file does not exist: {}"
                         .format(src_path))
            self.hash_to_path.pop(multihash, None)
            return None

        if src_path == dst_path:
            logger.error("IPFS: cannot copy file over itself: {}"
                         .format(src_path, dst_path))
            return None

        dst_dir = os.path.dirname(dst_path)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        if os.path.exists(dst_path):
            os.remove(dst_path)

        # we might perform linking instead, but it may eventually
        # result in a broken link chain
        shutil.copyfile(src_path, dst_path)
        return filename

    def update_resource_dir(self):
        self.__init__(self.dir_manager,
                      self.config,
                      self.resource_dir_method)

    def get_resource_root_dir(self):
        return self.get_resource_dir('')

    def get_resource_dir(self, task_id):
        return os.path.normpath(self.resource_dir_method(task_id))

    def get_resource_path(self, resource, task_id):
        resource_dir = self.get_resource_dir(task_id)
        return os.path.join(resource_dir, os.path.normpath(resource))

    def check_resource(self, resource, task_id,
                       absolute_path=False, multihash=None):

        if absolute_path:
            res_path = os.path.normpath(resource)
        else:
            res_path = self.get_resource_path(resource, task_id)

        uni_path = to_unicode(res_path)
        if uni_path in self.file_to_hash:
            local_hash = self.file_to_hash[uni_path]
            if multihash and local_hash != unicode(multihash):
                return False
            return os.path.exists(res_path)
        return False

    def get_cached(self, multihash):
        return self.hash_to_path.get(multihash, None)

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
                if not isinstance(resource[0], basestring):
                    results.append([os.path.join(*resource[0])] + resource[1:])
                else:
                    results.append(resource)
        return results

    def add_resource_dir(self, dir_name, client=None):
        if not client:
            client = self.new_ipfs_client()

        dir_name = os.path.normpath(dir_name)
        task_ids = self.dir_manager.list_task_ids_in_dir(dir_name)

        for task_id in task_ids:
            self.add_resource(task_id,
                              task_id=task_id,
                              client=client)

    def add_task(self, resource_coll, task_id, client=None):
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
                           client=client)

    def remove_task(self, task_id):
        if task_id in self.task_id_to_files:
            files = self.task_id_to_files.get(task_id, [])
            for entry in files:
                self.file_to_hash.pop(entry[0], None)
            del self.task_id_to_files[task_id]

        self.task_common_prefixes.pop(task_id, None)

    def add_resources(self, resource_coll, task_id, absolute_path=False, client=None):
        if not client:
            client = self.new_ipfs_client()

        if resource_coll:
            for resource in resource_coll:
                self.add_resource(resource, task_id,
                                  absolute_path=absolute_path,
                                  client=client)

    def add_resource(self, resource, task_id, absolute_path=False, client=None):
        if not client:
            client = self.new_ipfs_client()

        resource = os.path.normpath(resource)

        if absolute_path:
            resource_path = resource
        else:
            resource_path = self.get_resource_path(resource, task_id)

        if not os.path.exists(resource_path):
            logger.error("IPFS: resource '%s' does not exist" % resource_path)
            return
        elif self.check_resource(resource, task_id):
            return

        is_dir = os.path.isdir(resource_path)
        response = self._handle_retries(client.add,
                                        IPFSCommands.add,
                                        resource_path,
                                        recursive=is_dir)

        self._register_response(resource, response, task_id)

    def _register_response(self, resource, response, task_id):
        if isinstance(response, list):
            for entry in response:
                self._register_response(resource, entry, task_id)
        elif response and 'Hash' in response and 'Name' in response:
            path = to_unicode(response.get('Name'))
            multihash = to_unicode(response.get('Hash'))
            self._register_resource(resource, path, multihash, task_id)
        else:
            logger.error("IPFS: Invalid response {}".format(response))

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
            return

        norm_file_path = os.path.normpath(file_path)
        norm_resource = os.path.normpath(resource)

        if not norm_file_path.endswith(norm_resource):
            return

        name = self.make_relative_path(file_path, task_id)

        if task_id not in self.task_id_to_files:
            self.task_id_to_files[task_id] = []

        self.file_to_hash[name] = multihash
        self.hash_to_path[multihash] = file_path
        self.task_id_to_files[task_id].append([name, multihash])

        logger.debug("IPFS: Resource registered {} ({})".format(file_path, multihash))
        return name

    def pin_resource(self, multihash, client=None):
        if not client:
            client = self.new_ipfs_client()
        return self._handle_retries(client.pin_add,
                                    IPFSCommands.pin,
                                    multihash)

    def unpin_resource(self, multihash, client=None):
        if not client:
            client = self.new_ipfs_client()
        return self._handle_retries(client.pin_rm,
                                    IPFSCommands.unpin,
                                    multihash)

    def pull_resource(self, filename, multihash, task_id,
                      success, error, client=None, async=True):

        filename = os.path.normpath(filename)

        if self.check_resource(filename, task_id, multihash=multihash):
            success(filename, multihash, task_id)
            return

        def success_wrapper(*args, **kwargs):
            with self.lock:
                self.current_downloads -= 1

            result = args[0][0]
            result_filename = result[0]
            result_multihash = result[1]
            result_path = self.get_resource_path(result_filename, task_id)

            logger.debug("[IPFS]:success:%s:%r" %
                         (result_multihash, time.time()))
            logger.debug("IPFS: %r (%r) downloaded" %
                         (result_filename, result_multihash))

            self._clear_retry(IPFSCommands.pull, result_multihash)
            self._register_resource(result_filename,
                                    result_path,
                                    result_multihash,
                                    task_id)
            self.pin_resource(result_multihash)

            success(filename, result_multihash, task_id)
            self.__process_queue()

        def error_wrapper(exc, *args, **kwargs):
            with self.lock:
                self.current_downloads -= 1

            if self._can_retry(exc, IPFSCommands.pull, multihash):
                self.pull_resource(filename,
                                   multihash,
                                   task_id,
                                   success=success,
                                   error=error,
                                   async=async)
            else:
                logger.error("[IPFS]:error:%s:%r" %
                             (multihash, time.time()))
                logger.error("IPFS: error downloading %r (%r)" %
                             (filename, multihash))

                error(filename, task_id)
                self.__process_queue()

        copied = self.__copy_cached(filename, multihash, task_id)
        if copied:
            self.current_downloads += 1
            success_wrapper([[filename, multihash]])
            return

        out_path = self.get_resource_path(filename, task_id)
        out_dir = out_path.rsplit(os.sep, 1)

        if out_dir and len(out_dir) > 1:
            if not os.path.exists(out_dir[0]):
                os.makedirs(out_dir[0])

        self.__pull(filename, multihash, task_id,
                    success_wrapper=success_wrapper,
                    error_wrapper=error_wrapper,
                    success=success,
                    error=error,
                    async=async,
                    client=client)

    def __copy_cached(self, filename, multihash, task_id):
        cached_path = self.get_cached(multihash)
        if cached_path and os.path.exists(cached_path):
            copied_filename = self._copy_resource(cached_path,
                                                  filename,
                                                  multihash,
                                                  task_id)

            if copied_filename:
                logger.debug("IPFS: Resource copied {} ({})"
                             .format(copied_filename, multihash))
                return True
        return None

    def __can_download(self):
        with self.lock:
            max_dl = self.config.max_concurrent_downloads
            return max_dl < 1 or self.current_downloads < max_dl

    def __pull(self, filename, multihash, task_id,
               success_wrapper, error_wrapper,
               success, error,
               async=True, client=None):

        if not self.__can_download():
            self.__push_to_queue(filename, multihash, task_id,
                                 success, error)
            return

        if not client:
            client = self.new_ipfs_client()

        res_dir = self.get_resource_dir(task_id)

        with self.lock:
            self.current_downloads += 1

        if async:
            self._ipfs_async_call(client.get_file,
                                  success_wrapper,
                                  error_wrapper,
                                  multihash=multihash,
                                  filename=filename,
                                  filepath=res_dir)
        else:
            try:
                data = client.get_file(multihash,
                                       filename=filename,
                                       filepath=res_dir)
                success_wrapper(data)
            except Exception as e:
                error_wrapper(e)

    def __push_to_queue(self, *args):
        with self.lock:
            self.download_queue.append(args)

    def __process_queue(self):
        params = None

        with self.lock:
            if self.download_queue:
                params = self.download_queue.popleft()

        if params:
            self.pull_resource(*params)
