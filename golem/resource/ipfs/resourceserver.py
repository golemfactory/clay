import logging
import time
import copy
from threading import Lock

from golem.resource.ipfs.resourcesmanager import IPFSResourceManager

logger = logging.getLogger(__name__)


class IPFSTransferStatus(object):
    idle = 0
    transferring = 1
    complete = 2
    cancelled = 3
    failed = 4


class DummyContext(object):
    def __enter__(self):
        return None

    def __exit__(self, *args):
        return False


class IPFSResourceServer:

    lock = Lock()
    dummy_lock = DummyContext()

    def __init__(self, dir_manager, config_desc, keys_auth, client):
        self.client = client
        self.keys_auth = keys_auth
        self.dir_manager = dir_manager

        self.resource_dir = self.dir_manager.res
        self.resource_manager = IPFSResourceManager(self.dir_manager,
                                                    config_desc.node_name)

        self.resources_to_get = []
        self.waiting_resources = {}
        self.waiting_tasks_to_compute = {}

    def change_resource_dir(self, config_desc):
        if self.dir_manager.root_path == config_desc.root_path:
            return

        old_resource_dir = self.resource_manager.get_resource_root_dir()

        self.dir_manager.root_path = config_desc.root_path
        self.dir_manager.node_name = config_desc.node_name

        self.resource_manager.copy_resources(old_resource_dir)

    def start_accepting(self):
        try:
            ipfs_id = self.resource_manager.id()
            logger.debug("IPFS: id %r" % ipfs_id)
        except Exception as e:
            logger.error("IPFS: daemon is not running "
                         "or is not properly configured: %s" % e.message)

    def set_resource_peers(self, *args, **kwargs):
        pass

    def add_files_to_send(self, *args):
        pass

    def get_distributed_resource_root(self):
        return self.resource_manager.get_resource_root_dir()

    def get_peers(self):
        self.client.get_resource_peers()

    def sync_network(self):
        self.get_resources()

    def add_task(self, files, task_id):
        self.resource_manager.add_task(files, task_id)
        res = self.resource_manager.list_split_resources(task_id)
        logger.debug("IPFS: resource list: %r" % res)

    def add_files_to_get(self, files, task_id):
        num = 0
        collected = False

        with self.lock:
            for filename, multihash in files:
                exists = self.resource_manager.check_resource(filename, task_id,
                                                              multihash=multihash)
                if not exists:
                    self._add_resource_to_get(filename, multihash, task_id)
                    num += 1

            if num > 0:
                self.waiting_tasks_to_compute[task_id] = num
            else:
                collected = True

        if collected:
            self.client.task_resource_collected(task_id, unpack_delta=False)

    def _add_resource_to_get(self, filename, multihash, task_id):
        resource = [filename, multihash, task_id, IPFSTransferStatus.idle]

        if filename not in self.waiting_resources:
            self.waiting_resources[filename] = []

        if task_id not in self.waiting_resources[filename]:
            self.waiting_resources[filename].append(task_id)

        self.resources_to_get.append(resource)

    def get_resources(self, async=True):
        with self.lock if async else self.dummy_lock:
            resources = copy.copy(self.resources_to_get)

        for resource in resources:
            if resource[-1] in [IPFSTransferStatus.idle, IPFSTransferStatus.failed]:
                resource[-1] = IPFSTransferStatus.transferring
                self.pull_resource(resource, async=async)

    def pull_resource(self, resource, async=True):

        filename = resource[0]
        multihash = resource[1]
        task_id = resource[2]

        logger.debug("[IPFS]:pull:%s:%r:%s" % (multihash, time.time() * 1000, filename))

        self.resource_manager.pull_resource(filename,
                                            multihash,
                                            task_id,
                                            self.resource_downloaded,
                                            self.resource_download_error,
                                            async=async)

    def resource_downloaded(self, filename, multihash, task_id, *args):
        if not filename or not multihash:
            self.resource_download_error(filename, task_id)
            return

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

        if collected:
            self.client.task_resource_collected(collected,
                                                unpack_delta=False)

    def resource_download_error(self, filename, task_id, *args):
        with self.lock:
            for entry in self.resources_to_get:
                if task_id == entry[2] and filename == entry[0]:
                    entry[-1] = IPFSTransferStatus.failed
                    break

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
