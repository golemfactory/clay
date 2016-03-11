import logging
from threading import Lock

import time

from golem.resource.dirmanager import DirManager
from golem.resource.ipfs.resourcesmanager import IPFSResourceManager

logger = logging.getLogger(__name__)


class IPFSTransferStatus(object):
    idle = 0
    transferring = 1
    complete = 2
    cancelled = 3
    failed = 4


class IPFSResourceServer:

    lock = Lock()

    def __init__(self, dir_manager, config_desc, keys_auth, client):
        self.client = client
        self.keys_auth = keys_auth
        self.dir_manager = dir_manager

        self.resource_dir = self.dir_manager.res
        self.resource_manager = IPFSResourceManager(self.dir_manager, config_desc.node_name)

        self.resources_to_get = []
        self.waiting_resources = {}
        self.waiting_tasks_to_compute = {}

    def change_resource_dir(self, config_desc):
        if self.dir_manager.root_path == config_desc.root_path:
            return
        self.dir_manager.root_path = config_desc.root_path
        self.dir_manager.node_name = config_desc.node_name
        self.resource_manager.change_resource_dir(self.dir_manager.get_resource_dir())

    def start_accepting(self):
        try:
            self.resource_manager.id()
        except:
            raise EnvironmentError("IPFS daemon is not running or is not properly configured")

    def set_resource_peers(self, *args, **kwargs):
        pass

    def add_files_to_send(self, *args):
        pass

    def get_distributed_resource_root(self):
        return self.dir_manager.get_resource_dir()

    def get_peers(self):
        self.client.get_resource_peers()

    def sync_network(self):
        self.get_resources()

    def add_files_to_get(self, files, task_id):
        num = 0

        with IPFSResourceServer.lock:
            for filename, multihash in files:
                if not self.resource_manager.check_resource(filename, task_id):
                    num += 1
                    self.add_resource_to_get(filename, multihash, task_id)

            if num > 0:
                self.waiting_tasks_to_compute[task_id] = num
            else:
                self.client.task_resource_collected(task_id, unpack_delta=False)

    def add_resource_to_get(self, filename, multihash, task_id):
        resource = [filename, multihash, task_id, IPFSTransferStatus.idle]

        if filename not in self.waiting_resources:
            self.waiting_resources[multihash] = []

        if task_id in self.waiting_resources[multihash]:
            return

        self.waiting_resources[multihash].append(task_id)
        self.resources_to_get.append(resource)

    def get_resources(self):
        if self.resources_to_get:
            for resource in self.resources_to_get:
                if resource[-1] in [IPFSTransferStatus.idle, IPFSTransferStatus.failed]:
                    resource[-1] = IPFSTransferStatus.transferring
                    self.pull_resource(resource)

    def pull_resource(self, resource):

        filename = resource[0]
        multihash = resource[1]
        task_id = resource[2]

        logger.debug("IPFS: Resource %s (%s) requested [%r]" % (filename, multihash, time.time() * 1000))

        self.resource_manager.pull_resource(filename,
                                            multihash,
                                            task_id,
                                            self.resource_downloaded,
                                            self.resource_download_error)

    def has_resource(self, resource, *args):
        return self.check_resource(resource)

    def check_resource(self, resource):
        return self.resource_manager.check_resource(resource)

    def prepare_resource(self, file_name):
        return self.resource_manager.get_resource_path(file_name)

    def resource_downloaded(self, filename, multihash):

        if not multihash:
            self.resource_download_error(multihash)
            return

        with IPFSResourceServer.lock:

            for task_id in self.waiting_resources[multihash]:
                self.waiting_tasks_to_compute[task_id] -= 1
                if self.waiting_tasks_to_compute[task_id] <= 0:
                    self.client.task_resource_collected(task_id, unpack_delta=False)
                    del self.waiting_tasks_to_compute[task_id]
            del self.waiting_resources[multihash]

            for entry, i in enumerate(self.resources_to_get):
                if multihash == entry[1]:
                    del self.resources_to_get[i]
                    break

        logger.debug("IPFS: Resource %s (%s) downloaded [%r]" % (filename, multihash, time.time() * 1000))

    def resource_download_error(self, resource):

        (filename, multihash) = resource if isinstance(resource, tuple) else (None, resource)

        with IPFSResourceServer.lock:

            for entry in self.resources_to_get:
                if multihash == entry[1]:
                    entry[2] = IPFSTransferStatus.failed
                    break

        logger.error("IPFS: Resource %s failed to download [%r]" % (resource, time.time() * 1000))

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

    def change_config(self, config_desc):
        self.last_message_time_threshold = config_desc.resource_session_timeout
