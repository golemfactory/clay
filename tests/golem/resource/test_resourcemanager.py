import os
from golem.resource.resourcesmanager import ResourcesManager
from golem.resource.dirmanager import DirManager
from golem.testutils import TempDirFixture


class TestResourcesManager(TempDirFixture):
    def setUp(self):
        TempDirFixture.setUp(self)

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
        self.assertIsNotNone(ResourcesManager(self.dir_manager))

    def testGetResourceDir(self):
        rm = ResourcesManager(self.dir_manager)
        resDir = rm.get_resource_dir('task2')
        self.assertTrue(os.path.isdir(resDir))
        self.assertEqual(resDir, self.dir_manager.get_task_resource_dir('task2'))

    def testGetTemporaryDir(self):
        rm = ResourcesManager(self.dir_manager)
        tmp_dir = rm.get_temporary_dir('task2')
        self.assertTrue(os.path.isdir(tmp_dir))
        self.assertEqual(tmp_dir, self.dir_manager.get_task_temporary_dir('task2'))

    def testGetOutputDir(self):
        rm = ResourcesManager(self.dir_manager)
        outDir = rm.get_output_dir('task2')
        self.assertTrue(os.path.isdir(outDir))
        self.assertEqual(outDir, self.dir_manager.get_task_output_dir('task2'))
