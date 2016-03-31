import logging
import os
import socket
import time
import urllib2
from collections import deque
from threading import Lock

import requests
import twisted

from golem.core.fileshelper import copy_file_tree
from golem.resource.ipfs.client import IPFSClient, IPFSAsyncCall, IPFSAsyncExecutor, IPFSCommands

__all__ = ['IPFSResourceManager']

logger = logging.getLogger(__name__)


def to_unicode(source):
    if not isinstance(source, unicode):
        return unicode(source)
    return source

try:
    from requests.packages.urllib3.exceptions import *
    urllib_exceptions = [MaxRetryError, TimeoutError, ReadTimeoutError,
                         ConnectTimeoutError, ConnectionError]
except ImportError:
    urllib_exceptions = [urllib2.URLError]


class IPFSResourceManager:

    root_path = os.path.abspath(os.sep)
    timeout_exceptions = urllib_exceptions + [socket.timeout,
                                              requests.exceptions.Timeout,
                                              twisted.internet.defer.TimeoutError]

    def __init__(self, dir_manager, node_name,
                 ipfs_client_config=None,
                 resource_dir_method=None,
                 max_concurrent_downloads=8,
                 max_retries=5):

        self.lock = Lock()

        self.node_name = node_name
        self.dir_manager = dir_manager
        self.ipfs_client_config = ipfs_client_config

        self.current_downloads = 0
        self.max_retries = max_retries
        self.max_concurrent_downloads = max_concurrent_downloads

        self.client_config = {
            'timeout': (5000, 5000)
        }

        if ipfs_client_config:
            self.client_config.update(ipfs_client_config)

        self.hash_to_file = dict()
        self.file_to_hash = dict()
        self.task_id_to_files = dict()
        self.task_common_prefixes = dict()
        self.download_queue = deque()
        self.command_retries = dict()
        self.commands = dict()

        for name, val in IPFSCommands.__dict__.iteritems():
            if not name.startswith('_'):
                self.command_retries[val] = {}
                self.commands[val] = name

        if not resource_dir_method:
            self.resource_dir_method = dir_manager.get_task_resource_dir
        else:
            self.resource_dir_method = resource_dir_method

        self.add_resource_dir(self.get_resource_root_dir())

    def make_relative_path(self, path, task_id):
        common_prefix = self.task_common_prefixes.get(task_id, '')
        return path.replace(common_prefix, '', 1)

    def copy_resources(self, from_dir):
        resource_dir = self.get_resource_root_dir()
        copy_file_tree(from_dir, resource_dir)
        file_names = next(os.walk(from_dir))[2]
        for f in file_names:
            os.remove(os.path.join(from_dir, f))

    def update_resource_dir(self):
        self.__init__(self.dir_manager,
                      self.node_name,
                      self.ipfs_client_config,
                      self.resource_dir_method,
                      self.max_concurrent_downloads)

    def get_resource_root_dir(self):
        return self.get_resource_dir('')

    def get_resource_dir(self, task_id):
        return self.resource_dir_method(task_id)

    def get_resource_path(self, resource, task_id):
        resource_dir = self.get_resource_dir(task_id)
        return os.path.join(resource_dir, resource)

    def get_temporary_dir(self, task_id):
        return self.dir_manager.get_task_temporary_dir(task_id)

    def get_temporary_path(self, resource, task_id):
        temp_dir = self.get_temporary_dir(task_id)
        return os.path.join(temp_dir, resource)

    def new_ipfs_client(self):
        return IPFSClient(**self.client_config)

    def check_resource(self, fs_object, task_id, absolute_path=False):
        if absolute_path:
            res_path = fs_object
        else:
            res_path = self.get_resource_path(fs_object, task_id)

        return to_unicode(res_path) in self.file_to_hash and os.path.exists(res_path)

    def list_resources(self, task_id):
        return self.task_id_to_files.get(task_id, [])

    def list_split_resources(self, task_id):
        if task_id in self.task_id_to_files:
            files = self.task_id_to_files[task_id]
            if files:
                return [[f[0].split(os.path.sep)] + f[1:] for f in files]
        return []

    def join_split_resources(self, resources):
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

        task_ids = self.dir_manager.list_task_ids_in_dir(dir_name)

        for task_id in task_ids:
            self.add_resource(task_id,
                              task_id=task_id,
                              client=client)

    def add_task(self, resource_coll, task_id, client=None):
        if task_id in self.task_common_prefixes:
            return

        self.task_common_prefixes[task_id] = os.path.commonprefix(resource_coll)
        self.add_resources(resource_coll, task_id,
                           absolute_path=True,
                           client=client)

    def remove_task(self, task_id):
        if task_id in self.task_id_to_files:
            files = self.task_id_to_files[task_id]

            if files:
                for file_name in files:
                    self.file_to_hash.pop(file_name, None)

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

    def add_resource(self, fs_object, task_id, absolute_path=False, client=None):

        if not client:
            client = self.new_ipfs_client()

        if absolute_path:
            resource_path = fs_object
        else:
            resource_path = self.get_resource_path(fs_object, task_id)

        if not os.path.exists(resource_path):
            logger.error("IPFS: resource '%s' does not exist" % resource_path)
            return
        elif self.check_resource(fs_object, task_id):
            return

        is_dir = os.path.isdir(resource_path)
        response = self.__handle_retries(client.add,
                                         IPFSCommands.add,
                                         resource_path,
                                         recursive=is_dir)

        self._register_resource(response, task_id, absolute_path=absolute_path)

    def _register_resource(self, add_response, task_id, absolute_path=False):
        # response consists of multihashes and absolute paths

        if isinstance(add_response, list):
            for entry in add_response:
                self._register_resource(entry, task_id, absolute_path=absolute_path)
            return

        if add_response and 'Hash' in add_response and 'Name' in add_response:

            name = self.make_relative_path(add_response.get('Name'), task_id)
            multihash = add_response.get('Hash')

            name = to_unicode(name)
            multihash = to_unicode(multihash)

            if task_id not in self.task_id_to_files:
                self.task_id_to_files[task_id] = []

            self.hash_to_file[multihash] = name
            self.file_to_hash[name] = multihash
            self.task_id_to_files[task_id].append([name, multihash])

            logging.debug("IPFS: Adding resource %s (%s)" % (name, multihash))
        else:
            logging.error("IPFS: Invalid resource %r" % add_response)

    def pin_resource(self, multihash, client=None):
        if not client:
            client = self.new_ipfs_client()
        return self.__handle_retries(client.pin_add,
                                     IPFSCommands.pin,
                                     multihash)

    def unpin_resource(self, multihash, client=None):
        if not client:
            client = self.new_ipfs_client()
        return self.__handle_retries(client.pin_rm,
                                     IPFSCommands.unpin,
                                     multihash)

    def pull_resource(self, filename, multihash, task_id,
                      success, error, client=None, async=True):

        if multihash in self.hash_to_file:
            success(filename, multihash, task_id)
            return

        def success_wrapper(*args, **kwargs):
            with self.lock:
                self.current_downloads -= 1

            result = args[0][0]
            filename = result[0]
            multihash = result[1]

            logger.error("[IPFS]:success:{}:{}".format(multihash, time.time()))
            logger.debug("IPFS: %r (%r) downloaded" % (filename, multihash))

            self.__clear_retry(IPFSCommands.pull, multihash)
            self.pin_resource(multihash)

            success(filename, multihash, task_id)
            self.__process_queue()

        def error_wrapper(exc, *args, **kwargs):
            with self.lock:
                self.current_downloads -= 1

            if self.__can_retry(exc, IPFSCommands.pull, multihash):
                self.pull_resource(filename,
                                   multihash,
                                   task_id,
                                   success=success,
                                   error=error,
                                   async=async)
            else:
                logger.error("[IPFS]:error:{}:{}".format(multihash, time.time()))
                logger.error("IPFS: error downloading %r (%r)" % (filename, multihash))
                error(*args, **kwargs)
                self.__process_queue()

        out_path = self.get_resource_path(filename, task_id)
        out_dir = out_path.rsplit(os.sep, 1)

        if out_dir and len(out_dir) > 1:
            if not os.path.exists(out_dir[0]):
                os.makedirs(out_dir[0])

        self.__pull(filename, multihash, task_id,
                    success=success_wrapper,
                    error=error_wrapper,
                    async=async,
                    client=client)

    def id(self, client=None):
        if not client:
            client = self.new_ipfs_client()
        return self.__handle_retries(client.id, IPFSCommands.id, 'id')

    def __can_download(self):
        with self.lock:
            return self.max_concurrent_downloads < 1 or \
                   self.current_downloads < self.max_concurrent_downloads

    def __pull(self, filename, multihash, task_id,
               success, error, async, client=None):

        if not client:
            client = self.new_ipfs_client()

        res_dir = self.get_resource_dir(task_id)

        if self.__can_download():
            with self.lock:
                self.current_downloads += 1

            if async:
                self.__ipfs_async_call(client.get_file,
                                       success,
                                       error,
                                       multihash=multihash,
                                       filename=filename,
                                       filepath=res_dir)
            else:
                try:
                    data = client.get_file(multihash,
                                           filename=filename,
                                           filepath=res_dir)
                    success(data)
                except Exception as e:
                    error(e)
        else:
            self.__push_to_queue(filename, multihash,
                                 task_id,
                                 success, error)

    def __can_retry(self, exc, cmd, obj_id):
        if type(exc) in self.timeout_exceptions:
            this_cmd = self.command_retries[cmd]

            if obj_id not in this_cmd:
                this_cmd[obj_id] = 0

            if this_cmd[obj_id] < self.max_retries:
                this_cmd[obj_id] += 1
                return True

            this_cmd.pop(obj_id, None)

        return False

    def __clear_retry(self, cmd, obj_id):
        self.command_retries[cmd].pop(obj_id, None)

    def __handle_retries(self, method, cmd, *args, **kwargs):
        working = True
        obj_id = args[0]
        result = None

        while working:
            try:
                result = method(*args, **kwargs)
                working = False
            except Exception as e:
                if not self.__can_retry(e, cmd, obj_id):
                    self.__clear_retry(cmd, obj_id)
                    raise

        self.__clear_retry(cmd, obj_id)
        return result

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

    def __ipfs_async_call(self, method, success, error, *args, **kwargs):
        call = IPFSAsyncCall(method, *args, **kwargs)
        IPFSAsyncExecutor.run(call, success, error)
