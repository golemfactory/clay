import os

from golem.resource.ipfs.resourcesmanager import IPFSResourceManager
from golem.resource.dirmanager import DirManager
from golem.tools.testdirfixture import TestDirFixture


class TestResourcesManager(TestDirFixture):

    node_name = 'test_suite'
    task_id = 'deadbeef-deadbeef'

    def setUp(self):
        TestDirFixture.setUp(self)

        self.dir_manager = DirManager(self.path, self.node_name)
        self.target_resources = [
            'test_file',
            'test_dir/dir_file'
        ]
        self.split_resources = [
            ['test_file'],
            ['test_dir', 'dir_file']
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

    def testNewIpfsClient(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        from golem.resource.ipfs.client import IPFSClient
        self.assertIsInstance(rm.new_ipfs_client(), IPFSClient)

    def testInit(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        self.assertIsNotNone(rm)

    def testGetResourceDir(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        res_dir = rm.get_resource_dir(self.task_id)
        self.assertTrue(os.path.isdir(res_dir))
        self.assertEqual(res_dir, self.dir_manager.get_task_resource_dir(self.task_id))

    def testGetTemporaryDir(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        tmp_dir = rm.get_temporary_dir(self.task_id)
        self.assertTrue(os.path.isdir(tmp_dir))
        self.assertEqual(tmp_dir, self.dir_manager.get_task_temporary_dir(self.task_id))

    def testListResources(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        rm.add_resources(self.target_resources, self.task_id)
        rl = rm.list_resources(self.task_id)

        self.assertTrue(len(rl) == len(self.target_resources))

    def testListSplitResources(self):
        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        rm.add_resources(self.target_resources, self.task_id)
        rsl = rm.list_split_resources(self.task_id)

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        split_res_path = res_path.split(os.path.sep)
        split_res = [split_res_path + x for x in self.split_resources]

        self.assertTrue(len(rsl) == len(self.split_resources))

        for elem in rsl:
            self.assertTrue(elem[0] in split_res)

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
        id = rm.id()

        self.assertIsInstance(id, list)
        self.assertTrue('PublicKey' in id[0])

    def testAddResource(self):
        dir_manager = DirManager(self.path, 'test_suite')

        rm = IPFSResourceManager(dir_manager, self.node_name,
                                 resource_dir_method=dir_manager.get_task_temporary_dir)

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        test_dir = os.path.join(res_path, 'test_dir')
        test_dir_file = os.path.join(test_dir, 'dir_file')

        rm.add_resource(test_dir_file, self.task_id)

        self.assertTrue(len(rm.list_resources(self.task_id)) == 1)

    def testAddResources(self):
        dir_manager = DirManager(self.path, 'test_suite')

        rm = IPFSResourceManager(dir_manager, self.node_name,
                                 resource_dir_method=dir_manager.get_task_temporary_dir)

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        test_dir = os.path.join(res_path, 'test_dir')
        test_dir_file = os.path.join(test_dir, 'dir_file')

        rm.add_resources([test_dir_file], self.task_id)

        self.assertTrue(len(rm.list_resources(self.task_id)) == 1)

    def testPullResource(self):

        # working, downloaded
        status = [True, False]

        from twisted.internet import reactor
        if not reactor:
            from twisted.internet import selectreactor
            selectreactor.install()

        manage_reactor = [reactor.running]

        def success(*args, **kwargs):
            status[0] = False
            status[1] = True
            stop()

        def error(*args, **kwargs):
            status[0] = False
            stop()
            raise ValueError("Invalid value downloaded %r" % args)

        def stop(*args, **kwargs):
            if not manage_reactor[0]:
                manage_reactor[0] = True
                reactor.stop()

        rm = IPFSResourceManager(self.dir_manager, self.node_name)
        rm.add_resources(self.target_resources, self.task_id)
        rls = rm.list_resources(self.task_id)
        rl = rls[0]
        multihash = rl[1]

        def pull(*args, **kwargs):
            rm.pull_resource('other_resource',
                             multihash,
                             self.task_id,
                             success, error)

        reactor.callLater(0, pull)
        # timeout
        reactor.callLater(30, stop)
        if not manage_reactor[0]:
            reactor.run()

        self.assertTrue(status[1])
