import os
import time
import uuid

from golem.resource.dirmanager import DirManager
from golem.resource.ipfs.resourcesmanager import IPFSResourceManager
from golem.tools.testdirfixture import TestDirFixture


class TestResourcesManager(TestDirFixture):

    def setUp(self):
        TestDirFixture.setUp(self)

        self.node_name = str(uuid.uuid4())
        self.task_id = str(uuid.uuid4())
        self.dir_manager = DirManager(self.path, self.node_name)

        self.split_resources = [
            ['test_file.one.two'],
            ['test_dir.one.two', 'dir_file.one.two']
        ]

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        test_file = os.path.join(res_path, 'test_file.one.two')
        test_dir = os.path.join(res_path, 'test_dir.one.two')
        test_dir_file = os.path.join(test_dir, 'dir_file.one.two')

        self.target_resources = [
            os.path.join(res_path, *self.split_resources[0]),
            os.path.join(res_path, *self.split_resources[1])
        ]

        open(test_file, 'w').close()

        if not os.path.isdir(test_dir):
            os.mkdir(test_dir)

        with open(test_dir_file, 'w') as f:
            f.write("test content")

    def testCopyResources(self):
        rm = IPFSResourceManager(self.dir_manager)
        old_resource_dir = rm.get_resource_root_dir()

        prev_list = os.listdir(old_resource_dir)

        self.dir_manager.node_name = "another" + self.node_name
        rm.copy_resources(old_resource_dir)

        cur_list = os.listdir(rm.get_resource_root_dir())

        assert cur_list == prev_list

    def testCopyResource(self):
        rm = IPFSResourceManager(self.dir_manager)
        resource_paths = [rm.get_resource_path(f, self.task_id) for f in self.target_resources]
        rm.add_task(resource_paths, self.task_id)
        new_task_id = str(uuid.uuid4())

        assert rm.hash_to_path

        for multihash, file_path in rm.hash_to_path.iteritems():
            file_name = rm.make_relative_path(file_path, self.task_id)
            file_name = file_name[1:] if file_name.startswith(os.path.sep) else file_name
            dst_path = rm.get_resource_path(file_name, new_task_id)

            assert file_path != dst_path

            rm._copy_resource(file_path, file_name, multihash, new_task_id)

            assert os.path.exists(dst_path)

    def testNewIpfsClient(self):
        rm = IPFSResourceManager(self.dir_manager)
        from golem.network.ipfs.client import IPFSClient
        self.assertIsInstance(rm.new_client(), IPFSClient)

    def testGetResourceRootDir(self):
        rm = IPFSResourceManager(self.dir_manager)
        dm_dir = self.dir_manager.get_task_resource_dir('').rstrip(os.path.sep)
        rm_dir = rm.get_resource_root_dir().rstrip(os.path.sep)

        self.assertEqual(dm_dir, rm_dir)
        self.assertEqual(dm_dir, rm.get_resource_dir('').rstrip(os.path.sep))

    def testGetResourceDir(self):
        rm = IPFSResourceManager(self.dir_manager)
        res_dir = rm.get_resource_dir(self.task_id)
        self.assertTrue(os.path.isdir(res_dir))
        self.assertEqual(res_dir, self.dir_manager.get_task_resource_dir(self.task_id))
        self.assertNotEqual(res_dir, rm.get_resource_dir(self.task_id + "-other"))

    def testCheckResource(self):
        rm = IPFSResourceManager(self.dir_manager)
        rm.add_resources(self.target_resources, self.task_id)
        assert rm.get_resource_entry(self.target_resources[1], self.task_id) is not None
        assert rm.get_resource_entry(str(uuid.uuid4()), self.task_id) is None

    def testAddTask(self):
        rm = IPFSResourceManager(self.dir_manager)
        resource_paths = [rm.get_resource_path(f, self.task_id) for f in self.target_resources]

        rm.add_task(resource_paths, self.task_id)
        resources = rm.list_resources(self.task_id)

        assert self.task_id in rm.task_common_prefixes
        assert len(resources) == len(self.target_resources)

        task_files = rm.task_id_to_files[self.task_id]
        assert task_files

        new_task = str(uuid.uuid4())
        rm.add_task(resource_paths, new_task)
        assert len(resources) == len(rm.list_resources(new_task))

        rm.add_task(resource_paths, new_task)
        assert len(rm.list_resources(new_task)) == len(resources)

        assert rm.task_entry_exists(task_files[0], self.task_id)
        assert not rm.task_entry_exists((u'File path', u'Multihash'), self.task_id)
        assert not rm.task_entry_exists(task_files[0], str(uuid.uuid4()))

    def testRemoveTask(self):
        rm = IPFSResourceManager(self.dir_manager)
        resource_paths = [rm.get_resource_path(f, self.task_id) for f in self.target_resources]
        rm.add_task(resource_paths, self.task_id)
        rm.remove_task(self.task_id)

        self.assertFalse(self.task_id in rm.task_common_prefixes)
        self.assertEqual(rm.list_resources(self.task_id), [])

    def testListResources(self):
        rm = IPFSResourceManager(self.dir_manager)
        rm.add_resources(self.target_resources, self.task_id)
        rl = rm.list_resources(self.task_id)

        self.assertEqual(len(rl), len(self.target_resources))

    def testListSplitResources(self):
        rm = IPFSResourceManager(self.dir_manager)
        rm.add_resources(self.target_resources, self.task_id)
        rsl = rm.list_split_resources(self.task_id)

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        split_res_path = rm.split_path(res_path)
        split_res = [split_res_path + x for x in self.split_resources]

        self.assertTrue(len(rsl) == len(self.split_resources))

        for elem in rsl:
            assert elem[0] in split_res

    def testJoinSplitResources(self):
        rm = IPFSResourceManager(self.dir_manager)
        resource_paths = [rm.get_resource_path(f, self.task_id) for f in self.target_resources]
        rm.add_task(resource_paths, self.task_id)

        rsl = rm.list_split_resources(self.task_id)
        rl = rm.join_split_resources(rsl)

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        res_list = [os.path.join(res_path, x) for x in self.target_resources]

        assert len(rsl) == len(self.target_resources)

        for elem in rl:
            assert rm.get_resource_path(elem[0], self.task_id) in res_list

    def testAddResource(self):
        rm = IPFSResourceManager(self.dir_manager)

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        test_dir = os.path.join(res_path, 'test_dir.one.two')
        test_dir_file = os.path.join(test_dir, 'dir_file.one.two')

        rm.add_resource(test_dir_file, self.task_id)
        assert len(rm.list_resources(self.task_id)) == 1

        rm.add_resource('/.!&^%', self.task_id)
        assert len(rm.list_resources(self.task_id)) == 1

    def testAddResources(self):
        rm = IPFSResourceManager(self.dir_manager)

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        test_dir = os.path.join(res_path, 'test_dir.one.two')
        test_dir_file = os.path.join(test_dir, 'dir_file.one.two')

        rm.add_resources([test_dir_file], self.task_id)
        assert len(rm.list_resources(self.task_id)) == 1

        rm.add_resources(['/.!&^%'], self.task_id)
        assert len(rm.list_resources(self.task_id)) == 1

    def testGetCached(self):
        rm = IPFSResourceManager(self.dir_manager)
        rm.add_resources(self.target_resources, self.task_id)
        resources = rm.list_resources(self.task_id)

        for filename, multihash in resources:
            assert rm.get_cached(multihash) == filename

    def testPinResource(self):
        rm = IPFSResourceManager(self.dir_manager)
        rm.add_resources(self.target_resources, self.task_id)
        resources = rm.list_resources(self.task_id)

        result = rm.pin_resource(resources[0][1])
        self.assertTrue(result)

    def testUnpinResource(self):
        rm = IPFSResourceManager(self.dir_manager)
        rm.add_resources(self.target_resources, self.task_id)
        resources = rm.list_resources(self.task_id)

        rm.pin_resource(resources[0][1])
        rm.unpin_resource(resources[0][1])

    def testPullResource(self):

        rm = IPFSResourceManager(self.dir_manager)
        rm.add_resources(self.target_resources, self.task_id)
        rls = rm.list_resources(self.task_id)
        rl = rls[0]
        multihash = rl[1]

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

        rm.pull_resource('other_resource',
                         multihash,
                         self.task_id,
                         success, error,
                         async=async)
        wait()

        status[0] = True
        status[1] = False

        rm.pull_resource('other_resource',
                         multihash,
                         self.task_id,
                         success, error,
                         async=async)
        wait()
