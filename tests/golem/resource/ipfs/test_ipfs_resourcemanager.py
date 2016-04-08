import os
import uuid

from golem.resource.dirmanager import DirManager
from golem.resource.ipfs.resourcesmanager import IPFSResourceManager
from golem.tools.testdirfixture import TestDirFixture


class TestResourcesManager(TestDirFixture):

    node_name = 'test_suite'

    def setUp(self):
        TestDirFixture.setUp(self)

        self.dir_manager = DirManager(self.path, self.node_name)
        self.task_id = str(uuid.uuid4())

        self.split_resources = [
            ['test_file'],
            ['test_dir', 'dir_file']
        ]

        self.target_resources = [
            os.path.join(*self.split_resources[0]),
            os.path.join(*self.split_resources[1])
        ]

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        test_file = os.path.join(res_path, 'test_file')
        test_dir = os.path.join(res_path, 'test_dir')
        test_dir_file = os.path.join(test_dir, 'dir_file')

        open(test_file, 'w').close()

        if not os.path.isdir(test_dir):
            os.mkdir(test_dir)

        with open(test_dir_file, 'w') as f:
            f.write("test content")

    def testCopyResources(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        old_resource_dir = rm.get_resource_root_dir()

        prev_list = os.listdir(old_resource_dir)

        self.dir_manager.node_name = "another" + self.node_name
        rm.copy_resources(old_resource_dir)

        cur_list = os.listdir(rm.get_resource_root_dir())

        self.assertTrue(cur_list == prev_list)

    def testCopyResource(self):
        dir_manager = DirManager(self.path, 'test_suite_copy')
        rm = IPFSResourceManager(dir_manager, self.node_name)
        rm.add_resources(self.target_resources, self.task_id)
        resources = rm.list_resources(self.task_id)

        new_task_id = self.task_id + "-new"

        for filename, multihash in resources:
            dst_path = rm.get_resource_path(filename, new_task_id)
            src_path = rm.get_resource_path(filename, self.task_id)

            copied_name = rm._copy_resource(src_path,
                                            filename,
                                            multihash,
                                            new_task_id)

            assert filename == copied_name
            assert os.path.exists(dst_path)

    def testNewIpfsClient(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        from golem.resource.ipfs.client import IPFSClient
        self.assertIsInstance(rm.new_ipfs_client(), IPFSClient)

    def testInit(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        self.assertIsNotNone(rm)

    def testGetResourceRootDir(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        dm_dir = self.dir_manager.get_task_resource_dir('').rstrip(os.path.sep)
        rm_dir = rm.get_resource_root_dir().rstrip(os.path.sep)

        self.assertEqual(dm_dir, rm_dir)
        self.assertEqual(dm_dir, rm.get_resource_dir('').rstrip(os.path.sep))

    def testGetResourceDir(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        res_dir = rm.get_resource_dir(self.task_id)
        self.assertTrue(os.path.isdir(res_dir))
        self.assertEqual(res_dir, self.dir_manager.get_task_resource_dir(self.task_id))
        self.assertNotEqual(res_dir, rm.get_resource_dir(self.task_id + "-other"))

    def testGetTemporaryDir(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        tmp_dir = rm.get_temporary_dir(self.task_id)
        self.assertTrue(os.path.isdir(tmp_dir))
        self.assertEqual(tmp_dir, self.dir_manager.get_task_temporary_dir(self.task_id))

    def testCheckResource(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        rm.add_resources(self.target_resources, self.task_id)
        self.assertTrue(rm.check_resource(self.target_resources[1], self.task_id))
        self.assertFalse(rm.check_resource(str(uuid.uuid4()), self.task_id))

    def testAddTask(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        resource_paths = [rm.get_resource_path(f, self.task_id) for f in self.target_resources]
        rm.add_task(resource_paths, self.task_id)
        resources = rm.list_resources(self.task_id)

        self.assertTrue(self.task_id in rm.task_common_prefixes)
        self.assertEqual(len(resources), len(self.target_resources))

    def testRemoveTask(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        rm.add_task(self.target_resources, self.task_id)
        rm.remove_task(self.task_id)

        self.assertFalse(self.task_id in rm.task_common_prefixes)
        self.assertEqual(rm.list_resources(self.task_id), [])

    def testListResources(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        rm.add_resources(self.target_resources, self.task_id)
        rl = rm.list_resources(self.task_id)

        self.assertEqual(len(rl), len(self.target_resources))

    def testListSplitResources(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        rm.add_resources(self.target_resources, self.task_id)
        rsl = rm.list_split_resources(self.task_id)

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        split_res_path = res_path.split(os.path.sep)
        split_res = [split_res_path + x for x in self.split_resources]

        self.assertTrue(len(rsl) == len(self.split_resources))

        for elem in rsl:
            assert elem[0] in split_res

    def testJoinSplitResources(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        rm.add_resources(self.target_resources, self.task_id)

        rsl = rm.list_split_resources(self.task_id)
        rl = rm.join_split_resources(rsl)

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        res_list = [os.path.join(res_path, x) for x in self.target_resources]

        self.assertTrue(len(rsl) == len(self.target_resources))

        for elem in rl:
            self.assertTrue(os.path.join(os.path.sep, elem[0]) in res_list)

    def testId(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        ipfs_id = rm.id()

        self.assertIsInstance(ipfs_id, list)
        self.assertTrue('PublicKey' in ipfs_id[0])

    def testAddResource(self):
        dir_manager = DirManager(self.path, 'test_suite')

        rm = IPFSResourceManager(dir_manager, self.node_name,
                                 resource_dir_method=dir_manager.get_task_temporary_dir)

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        test_dir = os.path.join(res_path, 'test_dir')
        test_dir_file = os.path.join(test_dir, 'dir_file')

        rm.add_resource(test_dir_file, self.task_id)

        self.assertEqual(len(rm.list_resources(self.task_id)), 1)

    def testAddResources(self):
        dir_manager = DirManager(self.path, 'test_suite')

        rm = IPFSResourceManager(dir_manager, self.node_name,
                                 resource_dir_method=dir_manager.get_task_temporary_dir)

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        test_dir = os.path.join(res_path, 'test_dir')
        test_dir_file = os.path.join(test_dir, 'dir_file')

        rm.add_resources([test_dir_file], self.task_id)

        self.assertEqual(len(rm.list_resources(self.task_id)), 1)

    def testGetCached(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        rm.add_resources(self.target_resources, self.task_id)
        resources = rm.list_resources(self.task_id)

        for filename, multihash in resources:
            assert rm.get_cached(multihash) == filename

    def testPinResource(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        rm.add_resources(self.target_resources, self.task_id)
        resources = rm.list_resources(self.task_id)

        result = rm.pin_resource(resources[0][1])
        self.assertTrue(result)

    def testUnpinResource(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        rm.add_resources(self.target_resources, self.task_id)
        resources = rm.list_resources(self.task_id)

        rm.pin_resource(resources[0][1])
        rm.unpin_resource(resources[0][1])

    def testPullResource(self):

        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        rm.add_resources(self.target_resources, self.task_id)
        rls = rm.list_resources(self.task_id)
        rl = rls[0]
        multihash = rl[1]

        # working, downloaded
        status = [True, False]

        def success(*args, **kwargs):
            status[0] = False
            status[1] = True

        def error(*args, **kwargs):
            status[0] = False
            raise ValueError("Invalid value downloaded %r" % args)

        rm.pull_resource('other_resource',
                         multihash,
                         self.task_id,
                         success, error,
                         async=False)

        self.assertTrue(status[1])

        rm.pull_resource('other_resource',
                         multihash,
                         self.task_id,
                         success, error,
                         async=False)

        self.assertTrue(status[1])
