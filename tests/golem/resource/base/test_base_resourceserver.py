from pathlib import Path
from unittest import mock

import os
import shutil
import time
import uuid

from twisted.internet.defer import succeed

from golem.core.deferred import sync_wait
from golem.resource.base.resourceserver import BaseResourceServer
from golem.resource.dirmanager import DirManager
from golem.resource.hyperdrive.resourcesmanager import DummyResourceManager
from golem.tools import testwithreactor

from tests.factories.hyperdrive import hyperdrive_client_kwargs

node_name = 'test_suite'


class MockClient:

    def __init__(self):
        self.downloaded = None
        self.failed = None
        self.task_server = mock.Mock()

    def resource_collected(self, *args, **kwargs):
        self.downloaded = True

    def resource_failure(self, *args, **kwrags):
        self.failed = True


class MockConfig:
    def __init__(self, root_path=None, new_node_name=node_name):
        self.node_name = new_node_name
        self.root_path = root_path


class TestResourceServer(testwithreactor.TestDirFixtureWithReactor):

    def setUp(self):
        super().setUp()

        src_dir = os.path.join(self.path, 'sources')

        self.task_id = str(uuid.uuid4())
        self.dir_manager = DirManager(self.path)
        self.config_desc = MockConfig()
        self.target_resources = [
            os.path.join(src_dir, 'test_file'),
            os.path.join(src_dir, 'test_dir', 'dir_file'),
            os.path.join(src_dir, 'test_dir', 'dir_file_copy')
        ]

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        test_file = os.path.join(res_path, 'test_file')
        test_dir = os.path.join(res_path, 'test_dir')
        test_dir_file = os.path.join(test_dir, 'dir_file')
        test_dir_file_copy = os.path.join(test_dir, 'dir_file_copy')

        for path in self.target_resources + [test_file, test_dir_file]:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                f.write("test content")

        shutil.copy(test_dir_file, test_dir_file_copy)

        self.resource_manager = DummyResourceManager(
            self.dir_manager, **hyperdrive_client_kwargs())
        self.client = MockClient()
        self.resource_server = BaseResourceServer(
            self.resource_manager,
            self.client
        )

    def testGetDistributedResourceRoot(self):
        resource_dir = self.dir_manager.get_node_dir()

        self.assertEqual(
            self.resource_server.get_distributed_resource_root(),
            resource_dir
        )

    def _resources(self):
        existing_dir = self.dir_manager.get_task_resource_dir(self.task_id)
        existing_paths = []

        for resource in self.target_resources:
            resource_path = os.path.join(existing_dir, resource)
            existing_paths.append(resource_path)

        return existing_paths

    def _add_task(self):
        rs = self.resource_server
        rm = self.resource_server.resource_manager
        rm.storage.cache.clear()

        existing_paths = self._resources()

        _deferred = rs.create_resource_package(existing_paths, self.task_id)
        pkg_path, pkg_sha1 = sync_wait(_deferred)
        return rm, rs.add_resources(pkg_path, self.task_id)

    def testAddResources(self):
        rm, deferred = self._add_task()

        def test(*_):
            resources = rm.storage.get_resources(self.task_id)
            assert resources
            assert len(resources) == len(self.target_resources)

        deferred.addCallbacks(
            test,
            lambda e: self.fail(e)
        )

        started = time.time()

        while not deferred.called:
            if time.time() - started > 10:
                self.fail("Test timed out")
            time.sleep(0.1)

    def testRemoveResources(self):
        self.resource_manager.add_files(self._resources(), self.task_id)
        assert self.resource_manager.storage.get_resources(self.task_id)
        self.resource_server.remove_resources(self.task_id)
        assert not self.resource_manager.storage.get_resources(self.task_id)

    def testPendingResources(self):
        self.resource_manager.add_resources(self.target_resources, self.task_id,
                                            async_=False)

        resources = self.resource_manager.storage.get_resources(self.task_id)
        assert len(self.resource_server.pending_resources) == 0

        self.resource_server.download_resources(resources, self.task_id)
        pending = self.resource_server.pending_resources[self.task_id]
        assert len(pending) == len(resources)

    def testGetResources(self):
        self.resource_manager.add_resources(
            self.target_resources,
            self.task_id,
            async_=False)

        resources = self.resource_manager.storage.get_resources(self.task_id)
        resources = [[r.hash, r.files] for r in resources]

        client_kwargs = hyperdrive_client_kwargs()
        # DummyClient resolves hashes via an in-memory store;
        # assign the currently used one with proper entries
        manager = DummyResourceManager(self.dir_manager, **client_kwargs)
        manager.client = self.resource_manager.client

        task_id = str(uuid.uuid4())
        task_path = manager.storage.get_dir(task_id)

        server = BaseResourceServer(manager, self.client)
        server.download_resources(resources, task_id)

        def run(*args, **kwargs):
            del args, kwargs
            return succeed(True)

        with mock.patch('golem.core.golem_async.async_run', run):
            server._download_resources(async_=False)
            assert self.client.downloaded

        for entry in resources:
            for f in entry[1]:
                assert (Path(task_path) / f).exists()

    def testAddFilesToGet(self):
        test_files = [
            ['file1.txt', '1'],
            [os.path.join('tmp', 'file2.bin'), '2']
        ]

        assert not self.resource_server.pending_resources
        self.resource_server.download_resources(test_files, self.task_id)
        assert len(self.resource_server.pending_resources[self.task_id]) == len(
            test_files)

        return self.resource_server, test_files

    def testDownloadSuccess(self):
        rs, file_names = self.testAddFilesToGet()
        resources = list(rs.pending_resources[self.task_id])
        for entry in resources:
            rs._download_success(entry.resource, None, self.task_id)
        assert not rs.pending_resources

    def testDownloadError(self):
        rs, file_names = self.testAddFilesToGet()
        resources = list(rs.pending_resources[self.task_id])
        for entry in resources:
            rs._download_error(Exception(), entry.resource, self.task_id)
        assert not rs.pending_resources
