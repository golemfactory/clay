import os
from golem.resource.resourcesmanager import ResourcesManager
from golem.resource.dirmanager import DirManager
from test_dirmanager import TestDirFixture


class TestResourcesManager(TestDirFixture):
    def setUp(self):
        TestDirFixture.setUp(self)

        self.dir_manager = DirManager(self.path)
        res_path = self.dir_manager.get_task_resource_dir('task2')

        file1 = os.path.join(res_path, 'file1')
        file2 = os.path.join(res_path, 'file2')
        dir1 = os.path.join(res_path, 'dir1')
        file3 = os.path.join(dir1, 'file3')
        open(file1, 'w').close()
        open(file2, 'w').close()
        if not os.path.isdir(dir1):
            os.mkdir(dir1)
        open(file3, 'w').close()

    def testInit(self):
        self.assertIsNotNone(ResourcesManager(self.dir_manager, 'owner'))

    def testGetResourceHeader(self):
        rm = ResourcesManager(self.dir_manager, 'owner')
        header = rm.get_resource_header('task2')
        self.assertEquals(len(header.files_data), 2)
        self.assertEquals(len(header.sub_dir_headers[0].files_data), 1)
        header2 = rm.get_resource_header('task3')
        self.assertEquals(len(header2.files_data), 0)
        self.assertEquals(len(header2.sub_dir_headers), 0)

    def testGetResourceDelta(self):
        rm = ResourcesManager(self.dir_manager, 'owner')
        header = rm.get_resource_header('task2')
        delta = rm.get_resource_delta('task2', header)
        self.assertEquals(len(delta.files_data), 0)
        self.assertEquals(len(delta.sub_dir_resources[0].files_data), 0)
        header2 = rm.get_resource_header('task3')
        delta2 = rm.get_resource_delta('task2', header2)
        self.assertEquals(len(delta2.files_data), 2)
        self.assertEquals(len(delta2.sub_dir_resources[0].files_data), 1)
        res_path = self.dir_manager.get_task_resource_dir('task2')
        file5 = os.path.join(res_path, 'file5')
        open(file5, 'w').close()
        dir1 = os.path.join(res_path, 'dir1')
        file4 = os.path.join(dir1, 'file4')
        open(file4, 'w').close()
        delta3 = rm.get_resource_delta('task2', header)
        self.assertEquals(len(delta3.files_data), 1)
        self.assertEquals(len(delta3.sub_dir_resources[0].files_data), 1)
        os.remove(file4)
        os.remove(file5)

    #
    # def testPrepareResourceDelta(self):
    #     assert False
    #
    # def testUpdateResource(self):
    #     assert False
    #
    def testGetResourceDir(self):
        rm = ResourcesManager(self.dir_manager, 'owner')
        resDir = rm.get_resource_dir('task2')
        self.assertTrue(os.path.isdir(resDir))
        self.assertEqual(resDir, self.dir_manager.get_task_resource_dir('task2'))

    def testGetTemporaryDir(self):
        rm = ResourcesManager(self.dir_manager, 'owner')
        tmp_dir = rm.get_temporary_dir('task2')
        self.assertTrue(os.path.isdir(tmp_dir))
        self.assertEqual(tmp_dir, self.dir_manager.get_task_temporary_dir('task2'))

    def testGetOutputDir(self):
        rm = ResourcesManager(self.dir_manager, 'owner')
        outDir = rm.get_output_dir('task2')
        self.assertTrue(os.path.isdir(outDir))
        self.assertEqual(outDir, self.dir_manager.get_task_output_dir('task2'))

    # def test_fileDataReceived(self):
    #     assert False
