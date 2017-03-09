import os
import time
import uuid
from unittest.case import skipIf

from golem.network.ipfs.client import ipfs_running
from golem.resource.base.resourcetest import AddGetResources
from golem.resource.dirmanager import DirManager
from golem.resource.ipfs.resourcesmanager import IPFSResourceManager
from golem.tools.testdirfixture import TestDirFixture


@skipIf(not ipfs_running(), "IPFS daemon isn't running")
class TestIPFSResourceManager(TestDirFixture):

    def setUp(self):
        TestDirFixture.setUp(self)

        self.node_name = str(uuid.uuid4())
        self.task_id = str(uuid.uuid4())
        self.dir_manager = DirManager(self.path)

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        test_file = os.path.join(res_path, 'test_file.one.two')
        test_dir = os.path.join(res_path, 'test_dir.one.two')
        test_dir_file = os.path.join(test_dir, 'dir_file.one.two')

        self.split_resources = [
            ['test_file.one.two'],
            ['test_dir.one.two', 'dir_file.one.two']
        ]
        self.target_resources = [
            os.path.join(res_path, *self.split_resources[0]),
            os.path.join(res_path, *self.split_resources[1])
        ]

        if not os.path.isdir(test_dir):
            os.mkdir(test_dir)

        open(test_file, 'w').close()
        with open(test_dir_file, 'w') as f:
            f.write("test content")

    def test_new_client(self):
        rm = IPFSResourceManager(self.dir_manager)
        rm.storage.clear_cache()

        from golem.network.ipfs.client import IPFSClient
        self.assertIsInstance(rm.new_client(), IPFSClient)

    def test_pin(self):
        rm = IPFSResourceManager(self.dir_manager)
        rm.storage.clear_cache()

        rm.add_files(self.target_resources, self.task_id)
        resources = rm.storage.get_resources(self.task_id)
        assert resources

        result = rm.pin_resource(resources[0].hash)
        assert result

    def test_unpin(self):
        rm = IPFSResourceManager(self.dir_manager)
        rm.storage.clear_cache()

        rm.add_files(self.target_resources, self.task_id)
        resources = rm.storage.get_resources(self.task_id)
        assert resources

        rm.pin_resource(resources[0].hash)
        rm.unpin_resource(resources[0].hash)

    def test_pull(self):
        rm = IPFSResourceManager(self.dir_manager)
        rm.storage.clear_cache()

        rm.add_files(self.target_resources, self.task_id)
        rls = rm.storage.get_resources(self.task_id)
        assert rls

        rl = rls[0]
        multihash = rl.hash

        # working, downloaded
        status = [True, False]
        async = False

        def success(*args, **kwargs):
            status[0] = False
            status[1] = True

        def error(*args, **kwargs):
            status[0] = False
            status[1] = False
            raise ValueError("Invalid value downloaded %r" % args)

        def wait():
            while status[0]:
                time.sleep(0.25)
            self.assertTrue(status[1])

        rm.pull_resource(('other_resource', multihash),
                         self.task_id,
                         success, error,
                         async=async)
        wait()

        status[0] = True
        status[1] = False

        rm.pull_resource(('other_resource', multihash),
                         self.task_id,
                         success, error,
                         async=async)
        wait()


@skipIf(not ipfs_running(), "IPFS daemon isn't running")
class TestIPFSResources(AddGetResources):
    __test__ = True
    _resource_manager_class = IPFSResourceManager
