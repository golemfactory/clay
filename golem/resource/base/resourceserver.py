import copy
import logging
from threading import Lock

from enum import Enum

logger = logging.getLogger(__name__)


class TransferStatus(Enum):
    idle = 0
    transferring = 1
    complete = 2
    cancelled = 3
    failed = 4


class BaseResourceServer(object):

    lock = Lock()

    def __init__(self, resource_manager, dir_manager, keys_auth, client):

        self.client = client
        self.keys_auth = keys_auth

        self.dir_manager = dir_manager
        self.resource_manager = resource_manager

        self.resource_dir = self.dir_manager.res

        self.resources_to_get = []
        self.waiting_resources = {}
        self.waiting_tasks_to_compute = {}

    def change_resource_dir(self, config_desc):
        if self.dir_manager.root_path == config_desc.root_path:
            return

        old_resource_dir = self.get_distributed_resource_root()

        self.dir_manager.root_path = config_desc.root_path
        self.dir_manager.node_name = config_desc.node_name

        self.resource_manager.storage.copy_dir(old_resource_dir)

    def get_distributed_resource_root(self):
        return self.resource_manager.storage.get_root()

    def get_peers(self):
        self.client.get_resource_peers()

    def sync_network(self):
        self.get_resources()

    def add_task(self, files, task_id, client_options=None):
        self.resource_manager.add_task(files, task_id, client_options=client_options)
        res = self.resource_manager.storage.get_resources(task_id)
        res = self.resource_manager.storage.split_resources(res)
        if res:
            logger.debug("Resource server: resource list: {} (client options: {})"
                         .format(res, client_options))
        else:
            logger.warn("Resource server: empty resource list: {}".format(res))

    def remove_task(self, task_id, client_options=None):
        self.resource_manager.remove_task(task_id, client_options=client_options)

    def add_files_to_get(self, files, task_id, client_options=None):
        num = 0
        collected = False

        with self.lock:
            for filename, multihash in files:
                exists = self.resource_manager.storage.get_path_and_hash(filename, task_id,
                                                                         multihash=multihash)
                if not exists:
                    self._add_resource_to_get(filename, multihash, task_id, client_options)
                    num += 1

            if num > 0:
                self.waiting_tasks_to_compute[task_id] = num
            else:
                collected = True

        if collected:
            self.client.task_resource_collected(task_id, unpack_delta=False)

    def _add_resource_to_get(self, filename, multihash, task_id, client_options):
        resource = [filename, multihash, task_id, client_options, TransferStatus.idle]

        if filename not in self.waiting_resources:
            self.waiting_resources[filename] = []

        if task_id not in self.waiting_resources[filename]:
            self.waiting_resources[filename].append(task_id)

        self.resources_to_get.append(resource)

    def get_resources(self, async=True):
        resources = copy.copy(self.resources_to_get)

        for resource in resources:
            if resource[-1] in [TransferStatus.idle, TransferStatus.failed]:
                resource[-1] = TransferStatus.transferring
                self.pull_resource(resource, async=async)

    def pull_resource(self, resource, async=True):

        filename = resource[0]
        multihash = resource[1]
        task_id = resource[2]
        client_options = resource[3]

        logger.debug("Resource server: pull resource: {} ({})"
                     .format(filename, multihash))

        self.resource_manager.pull_resource(filename,
                                            multihash,
                                            task_id,
                                            self.resource_downloaded,
                                            self.resource_download_error,
                                            async=async,
                                            client_options=client_options)

    def resource_downloaded(self, filename, multihash, task_id, *args):
        if not filename or not multihash:
            self.resource_download_error(Exception("Invalid resource: {} ({})"
                                                   .format(filename, multihash)),
                                         filename, multihash, task_id)
            return

        collected = self.remove_resource_to_get(filename, task_id)
        if collected:
            self.client.task_resource_collected(collected,
                                                unpack_delta=False)

    def resource_download_error(self, exc, filename, multihash, task_id, *args):
        for entry in self.resources_to_get:
            if task_id == entry[2]:
                self.remove_resource_to_get(filename, task_id)
        self.client.task_resource_failure(task_id, exc)

    def remove_resource_to_get(self, filename, task_id):
        collected = None

        with self.lock:
            for waiting_task_id in self.waiting_resources.get(filename, []):
                self.waiting_tasks_to_compute[waiting_task_id] -= 1

                if self.waiting_tasks_to_compute[waiting_task_id] <= 0:
                    collected = waiting_task_id
                    del self.waiting_tasks_to_compute[waiting_task_id]

            self.waiting_resources.pop(filename, None)

            for i, entry in enumerate(self.resources_to_get):
                if task_id == entry[2] and filename == entry[0]:
                    del self.resources_to_get[i]
                    break

        return collected

    def get_key_id(self):
        return self.keys_auth.get_key_id()

    def encrypt(self, message, public_key):
        if public_key == 0:
            return message
        return self.keys_auth.encrypt(message, public_key)

    def decrypt(self, message):
        return self.keys_auth.decrypt(message)

    def sign(self, data):
        return self.keys_auth.sign(data)

    def verify_sig(self, sig, data, public_key):
        return self.keys_auth.verify(sig, data, public_key)

    def start_accepting(self):
        pass

    def set_resource_peers(self, *args, **kwargs):
        pass

    def add_files_to_send(self, *args):
        pass

    def change_config(self, config_desc):
        pass
