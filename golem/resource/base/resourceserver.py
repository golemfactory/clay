import logging
from enum import Enum
from threading import Lock

import os
from twisted.internet.defer import Deferred

from golem.core import golem_async
from golem.task.result.resultpackage import ZipPackager

logger = logging.getLogger(__name__)


class TransferStatus(Enum):
    idle = 0
    transferring = 1
    complete = 2
    cancelled = 3
    failed = 4


class PendingResource(object):

    def __init__(self, resource, res_id, client_options, status):
        self.resource = resource
        self.res_id = res_id
        self.client_options = client_options
        self.status = status


class BaseResourceServer:

    def __init__(self, resource_manager, client):
        self._lock = Lock()

        self.client = client

        self.resource_manager = resource_manager

        self.packager = ZipPackager()
        self.pending_resources = {}

    def get_distributed_resource_root(self):
        return self.resource_manager.storage.get_root()

    def sync_network(self):
        self._download_resources()

    def add_resources(self, pkg_path, res_id, client_options=None) -> Deferred:
        _result = Deferred()
        _result.addErrback(self._add_res_error)

        def callback(r):
            value = r, pkg_path
            _result.callback(value)

        _deferred = self.resource_manager.add_resources(
            [pkg_path], res_id, client_options=client_options)
        _deferred.addCallback(callback)
        _deferred.addErrback(_result.errback)

        return _result

    def create_resource_package(self, files, res_id) -> Deferred:
        resource_dir = self.resource_manager.storage.get_dir(res_id)
        package_path = os.path.join(resource_dir, res_id)
        request = golem_async.AsyncRequest(
            self.packager.create,
            package_path, files,
        )
        return golem_async.async_run(request)

    @staticmethod
    def _add_res_error(error):
        logger.error("Resource server: add_resources error: %r", error)
        return error  # continue with the errback chain

    def remove_resources(self, res_id):
        self.resource_manager.remove_resources(res_id)

    def download_resources(self, resources, res_id, client_options=None):
        with self._lock:
            for resource in resources:
                self._add_pending_resource(resource, res_id, client_options)

            collected = not self.pending_resources.get(res_id)

        if collected:
            self.client.resource_collected(res_id)

    def _add_pending_resource(self, resource, res_id, client_options):
        if res_id not in self.pending_resources:
            self.pending_resources[res_id] = []

        self.pending_resources[res_id].append(PendingResource(
            resource, res_id, client_options, TransferStatus.idle
        ))

    def _remove_pending_resource(self, resource, res_id):
        with self._lock:
            pending_resources = self.pending_resources.get(res_id, [])

            for i, pending_resource in enumerate(pending_resources):
                if pending_resource.resource == resource:
                    pending_resources.pop(i)
                    break

        if not pending_resources:
            self.pending_resources.pop(res_id, None)
            return res_id

    def _download_resources(self, async_=True):
        download_statuses = [TransferStatus.idle, TransferStatus.failed]
        pending = dict(self.pending_resources)

        for _, entries in pending.items():
            for entry in entries:

                if entry.status not in download_statuses:
                    continue
                entry.status = TransferStatus.transferring

                self.resource_manager.pull_resource(
                    entry.resource, entry.res_id,
                    client_options=entry.client_options,
                    success=self._download_success,
                    error=self._download_error,
                    async_=async_
                )

    def _download_success(self, resource, _, res_id):
        if not resource:
            self._download_error("Downloaded an empty resource package",
                                 resource, res_id)
            return

        if not self._remove_pending_resource(resource, res_id):
            logger.warning("Resources for id %r were re-downloaded", res_id)
            return

        self._extract_resources(resource, res_id)

    def _download_error(self, error, resource, res_id):
        self._remove_pending_resource(resource, res_id)
        self.client.resource_failure(res_id, error)

    def _extract_resources(self, resource, res_id):
        resource_dir = self.resource_manager.storage.get_dir(res_id)
        ctk = self.client.task_server.task_manager.comp_task_keeper

        def extract_packages(package_files):
            package_paths = []
            for package_file in package_files:
                package_path = os.path.join(resource_dir, package_file)
                package_paths.append(package_path)
                logger.info('Extracting task resource: %r', package_path)
                self.packager.extract(package_path, resource_dir)

            ctk.add_package_paths(res_id, package_paths)

        async_req = golem_async.AsyncRequest(extract_packages, resource[1])
        golem_async.async_run(async_req).addCallbacks(
            lambda _: self.client.resource_collected(res_id),
            lambda e: self._download_error(e, resource, res_id)
        )
