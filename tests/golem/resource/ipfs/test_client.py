import os

from golem.resource.dirmanager import DirManager
from golem.resource.ipfs.client import IPFSClient
from golem.tools.testdirfixture import TestDirFixture


class TestIpfsClient(TestDirFixture):

    node_name = 'test_suite'
    task_id = 'deadbeef-deadbeef'

    def setUp(self):
        TestDirFixture.setUp(self)

        self.dir_manager = DirManager(self.path, self.node_name)

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        self.test_dir = os.path.join(res_path, 'test_dir')
        self.test_dir_file = os.path.join(self.test_dir, 'dir_file')

        if not os.path.isdir(self.test_dir):
            os.mkdir(self.test_dir)

        with open(self.test_dir_file, 'w') as f:
            f.write("test content")

    def testAdd(self):
        client = IPFSClient()
        client.add([self.test_dir_file])

    def testGetFile(self):
        client = IPFSClient()
        response = client.add([self.test_dir_file])

        self.assertIsNotNone(response)

        tmp_filename = 'tmp_file'
        dest_path = os.path.join(self.test_dir, tmp_filename)

        client.get_file(response[0]['Hash'],
                        filepath=dest_path,
                        filename=tmp_filename)

    def testPinAdd(self):
        client = IPFSClient()
        response = client.add([self.test_dir_file])

        self.assertIsNotNone(response)

        client.pin_add(response[0]['Hash'])
