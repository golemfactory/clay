import os

from golem.resource.ipfs.client import IPFSClient, IPFSAsyncCall, IPFSAsyncExecutor

import logging
logger = logging.getLogger(__name__)


class IPFSResourceManager:

    root_path = os.path.abspath(os.sep)

    def __init__(self, dir_manager, node_name, resource_dir_method=None):

        self.node_name = node_name
        self.dir_manager = dir_manager

        self.hash_to_file = dict()
        self.file_to_hash = dict()
        self.task_id_to_files = dict()
        self.task_common_prefixes = dict()

        if not resource_dir_method:
            self.resource_dir_method = dir_manager.get_task_resource_dir
        else:
            self.resource_dir_method = resource_dir_method

        # self.resource_dir = dir_manager.get_task_resource_dir('')
        # self.add_resource_dir(self.resource_dir)

    def make_relative_path(self, path, task_id):
        common_prefix = self.task_common_prefixes.get(task_id, '')
        return path.replace(common_prefix, '', 1)

    # def copy_resources(self, new_resource_dir):
    #     copy_file_tree(self.resource_dir, new_resource_dir)
    #     file_names = next(os.walk(self.resource_dir))[2]
    #     for f in file_names:
    #         os.remove(os.path.join(self.resource_dir, f))
    #
    # def change_resource_dir(self, resource_dir):
    #     self.copy_resources(resource_dir)
    #     self.resource_dir = resource_dir
    #     self.__init__(self.dir_manager, resource_dir)

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

    def add_resource_dir(self, dir_name, client=None):
        if not client:
            client = self.__new_ipfs_client()

        task_ids = next(os.walk(dir_name))[1]
        if task_ids:
            for task_id in task_ids:
                self.add_resource(task_id,
                                  task_id=task_id,
                                  client=client)

    def add_task(self, resource_coll, task_id):
        if task_id in self.task_common_prefixes:
            return

        self.task_common_prefixes[task_id] = os.path.commonprefix(resource_coll)
        self.add_resources(resource_coll, task_id, absolute_path=True)

    def add_resources(self, resource_coll, task_id, absolute_path=False, client=None):
        if not client:
            client = self.__new_ipfs_client()

        if resource_coll:
            for resource in resource_coll:
                self.add_resource(resource, task_id,
                                  absolute_path=absolute_path,
                                  client=client)

    def add_resource(self, fs_object, task_id, absolute_path=False, client=None):

        if not client:
            client = self.__new_ipfs_client()

        if absolute_path:
            resource_path = fs_object
        else:
            resource_path = self.get_resource_path(fs_object, task_id)

        if not os.path.exists(resource_path):
            logger.error("IPFS: resource '%s' does not exist" % resource_path)
            return
        elif fs_object in self.file_to_hash:
            return

        is_dir = os.path.isdir(resource_path)
        response = client.add(resource_path, recursive=is_dir)

        self._register_resource(response, task_id, absolute_path=absolute_path)

    def _register_resource(self, add_response, task_id, absolute_path=False):
        # response consists of multihashes and absolute paths

        if isinstance(add_response, list):
            for entry in add_response:
                self._register_resource(entry, task_id, absolute_path=absolute_path)
        else:
            if add_response and 'Hash' in add_response and 'Name' in add_response:

                name = self.make_relative_path(add_response.get('Name'), task_id)
                multihash = add_response.get('Hash')

                if multihash in self.hash_to_file:
                    return

                if task_id not in self.task_id_to_files:
                    self.task_id_to_files[task_id] = []

                self.hash_to_file[multihash] = name
                self.file_to_hash[name] = multihash
                self.task_id_to_files[task_id].append([name, multihash])

                logging.debug("IPFS: Adding resource %s (%s)" % (name, multihash))
            else:
                logging.error("IPFS: Invalid resource %r" % add_response)

    def check_resource(self, fs_object, task_id, absolute_path=False):
        if absolute_path:
            res_path = fs_object
        else:
            res_path = self.get_resource_path(fs_object, task_id)

        return fs_object in self.file_to_hash and os.path.exists(res_path)

    def list_resources(self, task_id):
        if task_id in self.task_id_to_files:
            return self.task_id_to_files[task_id]
        return []

    def pin_resource(self, multihash, client=None):
        if not client:
            client = self.__new_ipfs_client()
        return client.pin_add(multihash)

    def unpin_resource(self, multihash, client=None):
        if not client:
            client = self.__new_ipfs_client()
        return client.pin_rm(multihash)

    def pull_resource(self, filename, multihash, task_id,
                      success, error,
                      temporary=False):

        client = self.__new_ipfs_client()

        def success_wrapper(*args, **kwargs):
            result = args[0][0]
            filename = result[0]
            multihash = result[1]

            self.pin_resource(multihash, client=client)
            success(filename, multihash, task_id)

        def error_wrapper(*args, **kwargs):
            error(*args, **kwargs)

        if temporary:
            res_dir = self.get_temporary_dir(task_id)
            out_path = self.get_temporary_path(filename, task_id)
        else:
            res_dir = self.get_resource_dir(task_id)
            out_path = self.get_resource_path(filename, task_id)

        out_dir = out_path.rsplit(os.sep, 1)

        if out_dir and len(out_dir) > 1:
            if not os.path.exists(out_dir[0]):
                os.makedirs(out_dir[0])

        self.__ipfs_async_call(client.get_file,
                               success_wrapper,
                               error_wrapper,
                               multihash=multihash,
                               filename=filename,
                               filepath=res_dir)

    def id(self, client=None):
        if not client:
            client = self.__new_ipfs_client()
        return client.id()

    def __new_ipfs_client(self):
        # todo: pass (optional) server config to the client
        return IPFSClient()

    def __ipfs_async_call(self, method, success, error, *args, **kwargs):
        call = IPFSAsyncCall(method, *args, **kwargs)
        IPFSAsyncExecutor.run(call, success, error)
