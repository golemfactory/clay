import sys
import os
import unittest
import logging
import shutil

sys.path.append(os.environ.get('GOLEM'))

from golem.resource.dir_manager import DirManager

path = 'C:\golem_test\\test1'
node1 = 'node1'

class TestDirManager(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)
        if not os.path.isdir(path):
            os.mkdir(path)

    def tearDown(self):
        path = 'C:\golem_test\\test1'
        if os.path.isdir(path):
            shutil.rmtree(path)

    def testInit(self):
        self.assertIsNotNone(DirManager(path, node1))

    def testClearDir(self):
        file1 = os.path.join(path, 'file1')
        file2 = os.path.join(path, 'file2')
        dir1 = os.path.join(path, 'dir1')
        file3 = os.path.join(dir1, 'file3')
        open(file1, 'w').close()
        open(file2, 'w').close()
        if not os.path.isdir(dir1):
            os.mkdir(dir1)
        open(file3, 'w').close()
        self.assertTrue(os.path.isfile(file1))
        self.assertTrue(os.path.isfile(file2))
        self.assertTrue(os.path.isfile(file3))
        self.assertTrue(os.path.isdir(dir1))
        dm = DirManager(path, node1)
        dm.clear_dir(dm.root_path)
        self.assertFalse(os.path.isfile(file1))
        self.assertFalse(os.path.isfile(file2))
        self.assertFalse(os.path.isfile (file3))
        self.assertFalse(os.path.isdir (dir1))

    def testGetTaskTemporaryDir(self):
        dm = DirManager(path, node1)
        task_id = '12345'
        tmpDir = dm.get_task_temporary_dir(task_id)
        expectedTmpDir = os.path.join(path, node1, task_id, 'tmp')
        self.assertEquals(tmpDir, expectedTmpDir)
        self.assertTrue(os.path.isdir(tmpDir))
        tmpDir = dm.get_task_temporary_dir(task_id)
        self.assertTrue(os.path.isdir(tmpDir))
        tmpDir = dm.get_task_temporary_dir(task_id, create = False)
        self.assertTrue(os.path.isdir(tmpDir))
        self.assertEquals(tmpDir, expectedTmpDir)
        shutil.rmtree(tmpDir)
        tmpDir = dm.get_task_temporary_dir(task_id, create = False)
        self.assertFalse(os.path.isdir(tmpDir))
        tmpDir = dm.get_task_temporary_dir(task_id, create = True)
        self.assertTrue(os.path.isdir(tmpDir))

    def testGetTaskResourceDir(self):
        dm = DirManager(path, node1)
        task_id = '12345'
        resDir = dm.get_task_resource_dir(task_id)
        expectedResDir = os.path.join(path, node1, task_id, 'resources')
        self.assertEquals(resDir, expectedResDir)
        self.assertTrue(os.path.isdir(resDir))
        resDir = dm.get_task_resource_dir(task_id)
        self.assertTrue(os.path.isdir(resDir))
        resDir = dm.get_task_resource_dir(task_id, create = False)
        self.assertTrue(os.path.isdir(resDir))
        self.assertEquals(resDir, expectedResDir)
        shutil.rmtree(resDir)
        resDir = dm.get_task_resource_dir(task_id, create = False)
        self.assertFalse(os.path.isdir(resDir))
        resDir = dm.get_task_resource_dir(task_id, create = True)
        self.assertTrue(os.path.isdir(resDir))

    def testGetTaskOutputDir(self):
        dm = DirManager(path, node1)
        task_id = '12345'
        outDir = dm.get_task_output_dir(task_id)
        expectedResDir = os.path.join(path, node1, task_id, 'output')
        self.assertEquals(outDir, expectedResDir)
        self.assertTrue(os.path.isdir(outDir))
        outDir = dm.get_task_output_dir(task_id)
        self.assertTrue(os.path.isdir(outDir))
        outDir = dm.get_task_output_dir(task_id, create = False)
        self.assertTrue(os.path.isdir(outDir))
        self.assertEquals(outDir, expectedResDir)
        shutil.rmtree(outDir)
        outDir = dm.get_task_output_dir(task_id, create = False)
        self.assertFalse(os.path.isdir(outDir))
        outDir = dm.get_task_output_dir(task_id, create = True)
        self.assertTrue(os.path.isdir(outDir))

    def testClearTemporary(self):
        dm = DirManager(path, node1)
        task_id = '12345'
        tmpDir = dm.get_task_temporary_dir(task_id)
        self.assertTrue(os.path.isdir(tmpDir))
        file1 = os.path.join(tmpDir, 'file1')
        file2 = os.path.join(tmpDir, 'file2')
        dir1 = os.path.join(tmpDir, 'dir1')
        file3 = os.path.join(dir1, 'file3')
        open(file1, 'w').close()
        open(file2, 'w').close()
        if not os.path.isdir(dir1):
            os.mkdir(dir1)
        open(file3, 'w').close()
        self.assertTrue(os.path.isfile(file1))
        self.assertTrue(os.path.isfile(file2))
        self.assertTrue(os.path.isfile(file3))
        self.assertTrue(os.path.isdir(dir1))
        dm.clear_temporary(task_id)
        self.assertTrue(os.path.isdir(tmpDir))
        self.assertFalse(os.path.isfile(file1))
        self.assertFalse(os.path.isfile(file2))
        self.assertFalse(os.path.isfile (file3))
        self.assertFalse(os.path.isdir (dir1))

    def testClearResource(self):
        dm = DirManager(path, node1)
        task_id = '67891'
        resDir = dm.get_task_resource_dir(task_id)
        self.assertTrue(os.path.isdir(resDir))
        file1 = os.path.join(resDir, 'file1')
        file2 = os.path.join(resDir, 'file2')
        dir1 = os.path.join(resDir, 'dir1')
        file3 = os.path.join(dir1, 'file3')
        open(file1, 'w').close()
        open(file2, 'w').close()
        if not os.path.isdir(dir1):
            os.mkdir(dir1)
        open(file3, 'w').close()
        self.assertTrue(os.path.isfile(file1))
        self.assertTrue(os.path.isfile(file2))
        self.assertTrue(os.path.isfile(file3))
        self.assertTrue(os.path.isdir(dir1))
        dm.clear_resource(task_id)
        self.assertTrue(os.path.isdir(resDir))
        self.assertFalse(os.path.isfile(file1))
        self.assertFalse(os.path.isfile(file2))
        self.assertFalse(os.path.isfile (file3))
        self.assertFalse(os.path.isdir (dir1))

    def testClearOutput(self):
        dm = DirManager(path, node1)
        task_id = '01112'
        outDir = dm.get_task_output_dir(task_id)
        self.assertTrue(os.path.isdir(outDir))
        self.assertTrue(os.path.isdir(outDir))
        file1 = os.path.join(outDir, 'file1')
        file2 = os.path.join(outDir, 'file2')
        dir1 = os.path.join(outDir, 'dir1')
        file3 = os.path.join(dir1, 'file3')
        open(file1, 'w').close()
        open(file2, 'w').close()
        if not os.path.isdir(dir1):
            os.mkdir(dir1)
        open(file3, 'w').close()
        dm.clear_output(task_id)
        self.assertTrue(os.path.isdir(outDir))
        self.assertFalse(os.path.isfile(file1))
        self.assertFalse(os.path.isfile(file2))
        self.assertFalse(os.path.isfile (file3))
        self.assertFalse(os.path.isdir (dir1))

if __name__ == '__main__':
    unittest.main()