import logging
from enum import Enum
from threading import Lock

import os
from twisted.internet.defer import Deferred

from golem.core.async import AsyncRequest, async_run
from golem.task.result.resultpackage import ZipPackager

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

        self.packager = ZipPackager()
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

    def sync_network(self):
        self._download_resources()

    def add_task(self, pkg_path, pkg_sha1, task_id) -> Deferred:
        _result = Deferred()
        _result.addErrback(self._add_task_error)

        _deferred = self.resource_manager.add_task([pkg_path], task_id)
        _deferred.addCallback(lambda r: _result.callback((r, pkg_sha1)))
        _deferred.addErrback(_result.errback)

        return _result

    def create_resource_package(self, files, task_id) -> Deferred:
        resource_dir = self.resource_manager.storage.get_dir(task_id)
        package_path = os.path.join(resource_dir, task_id)
        request = AsyncRequest(self.packager.create, package_path, files)
        return async_run(request)

    @staticmethod
    def _add_task_error(error):
        logger.error("Resource server: add_task error: %r", error)
        return error  # continue with the errback chain

    def remove_task(self, task_id):
        self.resource_manager.remove_task(task_id)

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

    def _download_resources(self, async_=True):
        download_statuses = [TransferStatus.idle, TransferStatus.failed]
        pending = dict(self.pending_resources)

        for _, entries in pending.items():
            for entry in entries:

                if entry.status not in download_statuses:
                    continue
                entry.status = TransferStatus.transferring

                self.resource_manager.pull_resource(
                    entry.resource, entry.task_id,
                    client_options=entry.client_options,
                    success=self._download_success,
                    error=self._download_error,
                    async_=async_
                )

    def _download_success(self, resource, _, task_id):
        if not resource:
            self._download_error("Downloaded an empty resource package",
                                 resource, task_id)
            return

        if not self._remove_pending_resource(resource, task_id):
            logger.warning("Resources for task %r were re-downloaded", task_id)
            return

        self._extract_task_resources(resource, task_id)

    def _download_error(self, error, resource, task_id):
        self._remove_pending_resource(resource, task_id)
        self.client.task_resource_failure(task_id, error)

    def _extract_task_resources(self, resource, task_id):
        resource_dir = self.resource_manager.storage.get_dir(task_id)

        def extract_packages(package_files):
            for package_file in package_files:
                package_path = os.path.join(resource_dir, package_file)
                logger.debug('Extracting task resource: %r', package_path)
                self.packager.extract(package_path, resource_dir)

        async_req = AsyncRequest(extract_packages, resource[1])
        async_run(async_req).addCallbacks(
            lambda _: self.client.task_resource_collected(task_id,
                                                          unpack_delta=False),
            lambda e: self._download_error(e, resource, task_id)
        )

    def get_key_id(self):
        return self.keys_auth.key_id

    def sign(self, data):
        return self.keys_auth.sign(data)

    def verify_sig(self, sig, data, public_key):
        return self.keys_auth.verify(sig, data, public_key)

    def start_accepting(self):
        pass

    def add_files_to_send(self, *args):
        pass

    def change_config(self, config_desc):
        pass
