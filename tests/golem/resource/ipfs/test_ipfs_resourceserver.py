import os
import unittest
import shutil
import uuid

from golem.core.keysauth import EllipticalKeysAuth
from golem.resource.dirmanager import DirManager
from golem.resource.ipfs.resourceserver import IPFSResourceServer, DummyContext
from golem.tools.testdirfixture import TestDirFixture

node_name = 'test_suite'


class MockClient:

    def __init__(self):
        self.downloaded = None
        self.resource_peers = []

    def get_resource_peers(self, *args, **kwargs):
        return self.resource_peers

    def task_resource_collected(self, *args, **kwargs):
        self.downloaded = True


class MockConfig:
    def __init__(self):
        self.node_name = node_name


class TestResourceServer(TestDirFixture):

    def setUp(self):

        TestDirFixture.setUp(self)

        self.task_id = str(uuid.uuid4())

        self.dir_manager = DirManager(self.path, node_name)
        self.dir_manager_aux = DirManager(self.path, node_name + "-aux")
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
        keys_auth = EllipticalKeysAuth()
        client = MockClient()
        rs = IPFSResourceServer(self.dir_manager, self.config_desc,
                                keys_auth, client)
        rs.start_accepting()

    def testDecrypt(self):
        keys_auth = EllipticalKeysAuth()
        client = MockClient()
        rs = IPFSResourceServer(self.dir_manager, self.config_desc,
                                keys_auth, client)

        to_encrypt = "test string to enc"
        encrypted = rs.encrypt(to_encrypt, keys_auth.get_public_key())
        decrypted = rs.decrypt(encrypted)

        self.assertEqual(decrypted, to_encrypt)

    def testGetResources(self):
        keys_auth = EllipticalKeysAuth()
        client = MockClient()
        rs = IPFSResourceServer(self.dir_manager, self.config_desc,
                                keys_auth, client)

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

        rs_aux = IPFSResourceServer(self.dir_manager_aux, self.config_desc,
                                    keys_auth, client)

        rs_aux.add_files_to_get(relative_resources, self.task_id)
        assert len(rs_aux.waiting_resources) == resources_len

        rs_aux.get_resources(async=False)
        rm_aux = rs_aux.resource_manager

        for entry in relative_resources:
            new_path = rm_aux.get_resource_path(entry[0], self.task_id)
            assert os.path.exists(new_path)

        assert client.downloaded

    def testVerifySig(self):
        keys_auth = EllipticalKeysAuth()
        client = MockClient()
        rs = IPFSResourceServer(self.dir_manager, self.config_desc,
                                keys_auth, client)

        test_str = "A test string to sign"
        sig = rs.sign(test_str)
        self.assertTrue(rs.verify_sig(sig, test_str, keys_auth.get_public_key()))

    def testGetDistributedResourceRoot(self):
        keys_auth = EllipticalKeysAuth()
        client = MockClient()
        rs = IPFSResourceServer(self.dir_manager, self.config_desc,
                                keys_auth, client)
        expected = self.dir_manager.get_task_resource_dir('')

        self.assertEqual(rs.get_distributed_resource_root(), expected)


class TestDummyContext(unittest.TestCase):
    def test(self):
        with DummyContext():
            pass
