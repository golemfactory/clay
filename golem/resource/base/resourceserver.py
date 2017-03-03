import copy
import logging
from collections import namedtuple
from threading import Lock

from enum import Enum
from twisted.internet.defer import Deferred

logger = logging.getLogger(__name__)


class TransferStatus(Enum):
    idle = 0
    transferring = 1
    complete = 2
    cancelled = 3
    failed = 4


class PendingResource(object):

    def __init__(self, resource, task_id, client_options, status):
        self.resource = resource
        self.task_id = task_id
        self.client_options = client_options
        self.status = status


class BaseResourceServer(object):

    def __init__(self, resource_manager, dir_manager, keys_auth, client):
        self._lock = Lock()

        self.client = client
        self.keys_auth = keys_auth

        self.dir_manager = dir_manager
        self.resource_manager = resource_manager

        self.resource_dir = self.dir_manager.res
        self.pending_resources = {}

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
        self._download_resources()

    def add_task(self, files, task_id, client_options=None):
        result = self.resource_manager.add_task(files, task_id,
                                                client_options=client_options)
        result.addErrback(self._add_task_error)
        return result

    @staticmethod
    def _add_task_error(error):
        logger.error("Resource server: add_task error: {}".format(error))

    def remove_task(self, task_id, client_options=None):
        self.resource_manager.remove_task(task_id, client_options=client_options)

    def download_resources(self, resources, task_id, client_options=None):
        with self._lock:
            for resource in resources:
                self._add_pending_resource(resource, task_id, client_options)

            collected = not self.pending_resources.get(task_id)

        if collected:
            self.client.task_resource_collected(task_id, unpack_delta=False)

    def _add_pending_resource(self, resource, task_id, client_options):
        if task_id not in self.pending_resources:
            self.pending_resources[task_id] = []

        self.pending_resources[task_id].append(PendingResource(
            resource, task_id, client_options, TransferStatus.idle
        ))

    def _remove_pending_resource(self, resource, task_id):
        with self._lock:
            pending_resources = self.pending_resources.get(task_id, [])

            for i, pending_resource in enumerate(pending_resources):
                if pending_resource.resource == resource:
                    pending_resources.pop(i)
                    break

        if not pending_resources:
            self.pending_resources.pop(task_id, None)
            return task_id

    def _download_resources(self, async=True):
        pending = dict(self.pending_resources)

        for task_id, entries in pending.iteritems():
            for entry in list(entries):
                if entry.status in [TransferStatus.idle, TransferStatus.failed]:
                    entry.status = TransferStatus.transferring
                    self.resource_manager.pull_resource(entry.resource, entry.task_id,
                                                        client_options=entry.client_options,
                                                        success=self._download_success,
                                                        error=self._download_error,
                                                        async=async)

    def _download_success(self, resource, task_id):
        if resource:

            collected = self._remove_pending_resource(resource, task_id)
            if collected:
                self.client.task_resource_collected(collected,
                                                    unpack_delta=False)
        else:
            logger.error("Empty resource downloaded for task {}"
                         .format(task_id))

    def _download_error(self, error, resource, task_id):
        self._remove_pending_resource(resource, task_id)
        self.client.task_resource_failure(task_id, error)

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
