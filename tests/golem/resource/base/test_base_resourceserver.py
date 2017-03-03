import os
import shutil
import time
import uuid

from golem.core.fileshelper import common_dir
from golem.core.keysauth import EllipticalKeysAuth
from golem.resource.base.resourceserver import BaseResourceServer
from golem.resource.base.resourcesmanager import TestResourceManager
from golem.resource.dirmanager import DirManager
from golem.tools.testwithreactor import TestDirFixtureWithReactor

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


class TestResourceServer(TestDirFixtureWithReactor):

    def setUp(self):

        TestDirFixtureWithReactor.setUp(self)

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

    def testStartAccepting(self):
        keys_auth = EllipticalKeysAuth(self.path)
        client = MockClient()
        rs = BaseResourceServer(TestResourceManager(self.dir_manager),
                                self.dir_manager, keys_auth, client)
        rs.start_accepting()

    def testGetDistributedResourceRoot(self):
        keys_auth = EllipticalKeysAuth(self.path)
        client = MockClient()
        rs = BaseResourceServer(TestResourceManager(self.dir_manager),
                                self.dir_manager, keys_auth, client)
        resource_dir = self.dir_manager.get_node_dir()

        assert rs.get_distributed_resource_root() == resource_dir

    def testDecrypt(self):
        keys_auth = EllipticalKeysAuth(self.path)
        client = MockClient()
        rs = BaseResourceServer(TestResourceManager(self.dir_manager),
                                self.dir_manager, keys_auth, client)

        to_encrypt = "test string to enc"
        encrypted = rs.encrypt(to_encrypt, keys_auth.get_public_key())
        decrypted = rs.decrypt(encrypted)

        self.assertEqual(decrypted, to_encrypt)

    def _resources(self):
        existing_dir = self.dir_manager.get_task_resource_dir(self.task_id)
        existing_paths = []

        for resource in self.target_resources:
            resource_path = os.path.join(existing_dir, resource)
            existing_paths.append(resource_path)

        return existing_paths

    def _add_task(self):

        keys_auth = EllipticalKeysAuth(self.path)
        client = MockClient()
        new_config_desc = MockConfig(self.path, node_name)
        dir_manager = DirManager(new_config_desc.root_path)

        rs = BaseResourceServer(TestResourceManager(self.dir_manager),
                                dir_manager, keys_auth, client)
        rm = rs.resource_manager
        rm.storage.clear_cache()

        existing_paths = self._resources()
        return rm, rs, rs.add_task(existing_paths, self.task_id)

    def testAddTask(self):
        rm, rs, deferred = self._add_task()

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
        keys_auth = EllipticalKeysAuth(self.path)
        client = MockClient()

        rm = TestResourceManager(self.dir_manager)
        rs = BaseResourceServer(TestResourceManager(self.dir_manager),
                                self.dir_manager, keys_auth, client)

        rm.add_files(self._resources(), self.task_id,
                     absolute_path=True)

        resources = rm.storage.get_resources(self.task_id)

        assert resources

        new_path = self.path + '_' + str(uuid.uuid4())

        new_config_desc = MockConfig(new_path, node_name + "-new")
        rs.change_resource_dir(new_config_desc)
        new_resources = rm.storage.get_resources(self.task_id)

        assert len(resources) == len(new_resources)

        for resource in resources:
            assert resource in new_resources

        if os.path.exists(new_path):
            shutil.rmtree(new_path)

    def testRemoveTask(self):
        keys_auth = EllipticalKeysAuth(self.path)
        client = MockClient()

        rs = BaseResourceServer(TestResourceManager(self.dir_manager),
                                self.dir_manager, keys_auth, client)
        rm = rs.resource_manager

        rm.add_files(self._resources(), self.task_id,
                     absolute_path=True)

        assert rm.storage.get_resources(self.task_id)

        rs.remove_task(self.task_id)
        resources = rm.storage.get_resources(self.task_id)

        assert not resources

    def testGetResources(self):
        keys_auth = EllipticalKeysAuth(self.path)
        client = MockClient()

        rs = BaseResourceServer(TestResourceManager(self.dir_manager),
                                self.dir_manager, keys_auth, client)

        rm = rs.resource_manager
        rm.storage.clear_cache()
        rm.add_files(self.target_resources, self.task_id)

        common_path = common_dir(self.target_resources)
        resources = rm.storage.get_resources(self.task_id)
        assert len(resources) == len(self.target_resources)

        assert len(rs.pending_resources) == 0
        rs.download_resources(resources, self.task_id)
        assert len(rs.pending_resources[self.task_id]) == len(resources)

        rs_aux = BaseResourceServer(TestResourceManager(self.dir_manager),
                                    self.dir_manager_aux, keys_auth, client)

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

        assert client.downloaded

    def testVerifySig(self):
        keys_auth = EllipticalKeysAuth(self.path)
        rs = BaseResourceServer(TestResourceManager(self.dir_manager),
                                self.dir_manager, keys_auth, MockClient())

        test_str = "A test string to sign"
        sig = rs.sign(test_str)
        self.assertTrue(rs.verify_sig(sig, test_str, keys_auth.get_public_key()))

    def testAddFilesToGet(self):
        keys_auth = EllipticalKeysAuth(self.path)
        rs = BaseResourceServer(TestResourceManager(self.dir_manager),
                                self.dir_manager, keys_auth, MockClient())

        test_files = [
            ['file1.txt', '1'],
            [os.path.join('tmp', 'file2.bin'), '2']
        ]

        assert not rs.pending_resources
        rs.download_resources(test_files, self.task_id)
        assert len(rs.pending_resources[self.task_id]) == len(test_files)

        return rs, test_files

    def testDownloadSuccess(self):
        rs, file_names = self.testAddFilesToGet()
        resources = list(rs.pending_resources[self.task_id])
        for entry in resources:
            rs._download_success(entry.resource, self.task_id)
        assert not rs.pending_resources

    def testDownloadError(self):
        rs, file_names = self.testAddFilesToGet()
        resources = list(rs.pending_resources[self.task_id])
        for entry in resources:
            rs._download_error(Exception(), entry.resource, self.task_id)
        assert not rs.pending_resources
