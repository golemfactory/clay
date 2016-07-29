import os
import unittest
import shutil
import uuid
from mock import patch

from golem.core.keysauth import EllipticalKeysAuth
from golem.resource.base.resourceserver import TransferStatus
from golem.resource.dirmanager import DirManager
from golem.resource.ipfs.resourceserver import IPFSResourceServer
from golem.tools.testdirfixture import TestDirFixture

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


class TestResourceServer(TestDirFixture):

    def setUp(self):

        TestDirFixture.setUp(self)

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
        rs = IPFSResourceServer(self.dir_manager, keys_auth, client)
        rs.start_accepting()

    @patch('golem.network.ipfs.client.IPFSClient', autospec=True)
    def testGetResources(self):
        rs = self.testAddTask()
        rm = rs.resource_manager

        rm.add_files_to_get([
            (u'filename', u'multihash'),
            (u'filename_2', u'multihash_2'),
            (u'filename_2', u'')
        ], 'xyz')

        rs.sync_network()

    def testGetDistributedResourceRoot(self):
        keys_auth = EllipticalKeysAuth(self.path)
        client = MockClient()
        rs = IPFSResourceServer(self.dir_manager, keys_auth, client)
        resource_dir = self.dir_manager.get_node_dir()

        assert rs.get_distributed_resource_root() == resource_dir

    def testDecrypt(self):
        keys_auth = EllipticalKeysAuth(self.path)
        client = MockClient()
        rs = IPFSResourceServer(self.dir_manager, keys_auth, client)

        to_encrypt = "test string to enc"
        encrypted = rs.encrypt(to_encrypt, keys_auth.get_public_key())
        decrypted = rs.decrypt(encrypted)

        self.assertEqual(decrypted, to_encrypt)

    def testAddTask(self):
        keys_auth = EllipticalKeysAuth(self.path)
        client = MockClient()
        new_config_desc = MockConfig(self.path, node_name)
        dir_manager = DirManager(new_config_desc.root_path)

        rs = IPFSResourceServer(dir_manager, keys_auth, client)
        rm = rs.resource_manager
        rm.clear_resources()

        assert not rm.list_resources(self.task_id)

        existing_dir = self.dir_manager.get_task_resource_dir(self.task_id)
        existing_paths = []

        for resource in self.target_resources:
            resource_path = os.path.join(existing_dir, resource)
            existing_paths.append(resource_path)

        rs.add_task(existing_paths, self.task_id)
        resources = rm.list_resources(self.task_id)

        assert resources
        assert len(resources) == len(self.target_resources)

        return rs

    def testChangeResourceDir(self):
        rs = self.testAddTask()
        rm = rs.resource_manager
        resources = rm.list_resources(self.task_id)

        assert resources

        new_path = self.path + '_' + str(uuid.uuid4())

        new_config_desc = MockConfig(new_path, node_name + "-new")
        rs.change_resource_dir(new_config_desc)
        new_resources = rm.list_resources(self.task_id)

        assert len(resources) == len(new_resources)

        for resource in resources:
            assert resource in new_resources

        if os.path.exists(new_path):
            shutil.rmtree(new_path)

    def testRemoveTask(self):
        rs = self.testAddTask()
        rm = rs.resource_manager

        assert rm.list_resources(self.task_id)

        rs.remove_task(self.task_id)
        resources = rm.list_resources(self.task_id)

        assert not resources

    def testGetResources(self):
        keys_auth = EllipticalKeysAuth(self.path)
        client = MockClient()
        rs = IPFSResourceServer(self.dir_manager, keys_auth, client)
        rs.resource_manager.clear_resources()
        rs.resource_manager.add_resources(self.target_resources, self.task_id)
        resources = rs.resource_manager.list_resources(self.task_id)
        resources_len = len(resources)

        filenames = []
        for entry in resources:
            filenames.append(entry[0])
        common_path = os.path.commonprefix(filenames)

        relative_resources = []
        for resource in resources:
            relative_resources.append((resource[0].replace(common_path, '', 1),
                                       resource[1]))

        rs.add_files_to_get(resources, self.task_id)
        assert len(rs.waiting_resources) == 0

        rs_aux = IPFSResourceServer(self.dir_manager_aux, keys_auth, client)

        rs_aux.add_files_to_get(relative_resources, self.task_id)
        assert len(rs_aux.waiting_resources) == resources_len

        rs_aux.get_resources(async=False)
        rm_aux = rs_aux.resource_manager

        for entry in relative_resources:
            new_path = rm_aux.get_resource_path(entry[0], self.task_id)
            assert os.path.exists(new_path)

        assert client.downloaded

    def testVerifySig(self):
        keys_auth = EllipticalKeysAuth(self.path)
        client = MockClient()
        rs = IPFSResourceServer(self.dir_manager, keys_auth, client)

        test_str = "A test string to sign"
        sig = rs.sign(test_str)
        self.assertTrue(rs.verify_sig(sig, test_str, keys_auth.get_public_key()))

    def testAddFilesToGet(self):
        keys_auth = EllipticalKeysAuth(self.path)
        client = MockClient()
        rs = IPFSResourceServer(self.dir_manager, keys_auth, client)

        test_files = [
            ['file1.txt', '1'],
            [os.path.join('tmp', 'file2.bin'), '2']
        ]

        assert not rs.resources_to_get

        rs.add_files_to_get(test_files, self.task_id)

        assert len(rs.resources_to_get) == len(test_files)

        return rs, test_files

    def testResourceDownloaded(self):
        rs, file_names = self.testAddFilesToGet()

        for i, entry in enumerate(file_names):
            rs.resource_downloaded(entry[0], str(i), self.task_id)

        assert not rs.resources_to_get

    def testResourceDownloadError(self):
        rs, file_names = self.testAddFilesToGet()

        for entry in file_names:
            rs.resource_download_error(Exception("Error " + entry[0]),
                                       entry[0], entry[1], self.task_id)

        assert len(rs.resources_to_get) == 0
