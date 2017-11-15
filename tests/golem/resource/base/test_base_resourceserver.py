import os
import shutil
import time
import uuid

from golem.core.fileshelper import common_dir
from golem.core.keysauth import EllipticalKeysAuth
from golem.resource.base import resourcesmanager
from golem.resource.base.resourceserver import BaseResourceServer
from golem.resource.dirmanager import DirManager
from golem.tools import testwithreactor

node_name = 'test_suite'


class MockClient:

    def __init__(self):
        self.downloaded = None
        self.failed = None
        self.resource_peers = []

    def get_resource_peers(self, *args, **kwargs):
        return self.resource_peers

    def task_resource_collected(self, *args, **kwargs):
        self.downloaded = True

    def task_resource_failure(self, *args, **kwrags):
        self.failed = True


class MockConfig:
    def __init__(self, root_path=None, new_node_name=node_name):
        self.node_name = new_node_name
        self.root_path = root_path


class TestResourceServer(testwithreactor.TestDirFixtureWithReactor):

    def setUp(self):
        super(TestResourceServer, self).setUp()

        self.task_id = str(uuid.uuid4())

        self.dir_manager = DirManager(self.path)
        self.dir_manager_aux = DirManager(self.path)
        self.config_desc = MockConfig()
        self.target_resources = [
            'test_file',
            os.path.join('test_dir', 'dir_file'),
            os.path.join('test_dir', 'dir_file_copy')
        ]

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        test_file = os.path.join(res_path, 'test_file')
        test_dir = os.path.join(res_path, 'test_dir')
        test_dir_file = os.path.join(test_dir, 'dir_file')
        test_dir_file_copy = os.path.join(test_dir, 'dir_file_copy')

        open(test_file, 'w').close()

        if not os.path.isdir(test_dir):
            os.mkdir(test_dir)

        with open(test_dir_file, 'w') as f:
            f.write("test content")

        if os.path.exists(test_dir_file_copy):
            os.remove(test_dir_file_copy)

        shutil.copy(test_dir_file, test_dir_file_copy)
        self.resource_manager = resourcesmanager.TestResourceManager(self.dir_manager)
        self.keys_auth = EllipticalKeysAuth(self.path)
        self.client = MockClient()
        self.resource_server = BaseResourceServer(
            self.resource_manager,
            self.dir_manager,
            self.keys_auth,
            self.client
        )

    def testStartAccepting(self):
        self.resource_server.start_accepting()

    def testGetDistributedResourceRoot(self):
        resource_dir = self.dir_manager.get_node_dir()

        self.assertEqual(
            self.resource_server.get_distributed_resource_root(),
            resource_dir
        )

    def testDecrypt(self):

        to_encrypt = "test string to enc"
        encrypted = self.resource_server.encrypt(
            to_encrypt,
            self.keys_auth.public_key
        )
        decrypted = self.resource_server.decrypt(encrypted)

        self.assertEqual(decrypted, to_encrypt.encode())

    def _resources(self):
        existing_dir = self.dir_manager.get_task_resource_dir(self.task_id)
        existing_paths = []

        for resource in self.target_resources:
            resource_path = os.path.join(existing_dir, resource)
            existing_paths.append(resource_path)

        return existing_paths

    def _add_task(self):
        new_config_desc = MockConfig(self.path, node_name)

        rs = self.resource_server
        rm = self.resource_server.resource_manager
        rm.storage.clear_cache()

        existing_paths = self._resources()
        return rm, rs.add_task(existing_paths, self.task_id)

    def testAddTask(self):
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

    def testChangeResourceDir(self):

        self.resource_manager.add_files(
            self._resources(),
            self.task_id,
            absolute_path=True
        )

        resources = self.resource_manager.storage.get_resources(self.task_id)

        assert resources

        new_path = self.path + '_' + str(uuid.uuid4())

        new_config_desc = MockConfig(new_path, node_name + "-new")
        self.resource_server.change_resource_dir(new_config_desc)
        new_resources = self.resource_manager.storage.get_resources(self.task_id)

        assert len(resources) == len(new_resources)

        for resource in resources:
            assert resource in new_resources

        if os.path.exists(new_path):
            shutil.rmtree(new_path)

    def testRemoveTask(self):

        self.resource_manager.add_files(
            self._resources(),
            self.task_id,
            absolute_path=True
        )

        assert self.resource_manager.storage.get_resources(self.task_id)

        self.resource_server.remove_task(self.task_id)
        resources = self.resource_manager.storage.get_resources(self.task_id)

        assert not resources

    def testGetResources(self):

        self.resource_manager.storage.clear_cache()
        self.resource_manager.add_files(self.target_resources, self.task_id)

        common_path = common_dir(self.target_resources)
        resources = self.resource_manager.storage.get_resources(self.task_id)
        assert len(resources) == len(self.target_resources)

        assert len(self.resource_server.pending_resources) == 0
        self.resource_server.download_resources(resources, self.task_id)
        assert len(self.resource_server.pending_resources[self.task_id]) == len(resources)  # noqa

        rs_aux = BaseResourceServer(
            resourcesmanager.TestResourceManager(self.dir_manager),
            self.dir_manager_aux,
            self.keys_auth,
            self.client
        )

        relative_resources = []
        for resource in resources:
            relative_resources.append((resource.path.replace(common_path, '', 1),
                                       resource.hash))

        task_id_2 = str(uuid.uuid4())

        assert len(rs_aux.pending_resources) == 0
        rs_aux.download_resources(relative_resources, task_id_2)
        assert len(rs_aux.pending_resources[task_id_2]) == len(resources)

        rs_aux._download_resources(async=False)

        for entry in relative_resources:
            assert os.path.exists(entry[0])

        assert self.client.downloaded

    def testVerifySig(self):
        test_str = "A test string to sign"
        sig = self.resource_server.sign(test_str)
        self.assertTrue(self.resource_server.verify_sig(sig, test_str, self.keys_auth.public_key))

    def testAddFilesToGet(self):
        test_files = [
            ['file1.txt', '1'],
            [os.path.join('tmp', 'file2.bin'), '2']
        ]

        assert not self.resource_server.pending_resources
        self.resource_server.download_resources(test_files, self.task_id)
        assert len(self.resource_server.pending_resources[self.task_id]) == len(test_files)

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
