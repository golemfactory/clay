import os
import shutil

from golem.resource.dirmanager import DirManager, find_task_script, logger
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture



class TestDirManager(TestDirFixture):

    node1 = 'node1'

    def testInit(self):
        self.assertIsNotNone(DirManager(self.path))

    def testClearDir(self):
        file1 = os.path.join(self.path, 'file1')
        file2 = os.path.join(self.path, 'file2')
        dir1 = os.path.join(self.path, 'dir1')
        dir2 = os.path.join(self.path, 'dir2')
        file3 = os.path.join(dir1, 'file3')
        file4 = os.path.join(dir2, 'file4')
        open(file1, 'w').close()
        open(file2, 'w').close()
        if not os.path.isdir(dir1):
            os.mkdir(dir1)
        if not os.path.isdir(dir2):
            os.mkdir(dir2)
        open(file3, 'w').close()
        open(file4, 'w').close()
        undeletable = []
        undeletable.append(file1)
        undeletable.append(file3)
        self.assertTrue(os.path.isfile(file1))
        self.assertTrue(os.path.isfile(file2))
        self.assertTrue(os.path.isfile(file3))
        self.assertTrue(os.path.isfile(file4))
        self.assertTrue(os.path.isdir(dir1))
        self.assertTrue(os.path.isdir(dir2))
        dm = DirManager(self.path)
        dm.clear_dir(dm.root_path, undeletable)
        self.assertTrue(os.path.isfile(file1))
        self.assertTrue(os.path.isfile(file3))
        self.assertTrue(os.path.isdir(dir1))
        self.assertFalse(os.path.isfile(file2))
        self.assertFalse(os.path.isfile(file4))
        self.assertFalse(os.path.isdir(dir2))
        dm.clear_dir(dm.root_path)
        self.assertFalse(os.path.isfile(file1))
        self.assertFalse(os.path.isfile(file3))
        self.assertFalse(os.path.isdir(dir1))

    def testGetTaskTemporaryDir(self):
        dm = DirManager(self.path)
        task_id = '12345'
        tmp_dir = dm.get_task_temporary_dir(task_id)
        expected_tmp_dir = os.path.join(self.path, task_id, 'tmp')
        self.assertEquals(os.path.normpath(tmp_dir), expected_tmp_dir)
        self.assertTrue(os.path.isdir(tmp_dir))
        tmp_dir = dm.get_task_temporary_dir(task_id)
        self.assertTrue(os.path.isdir(tmp_dir))
        tmp_dir = dm.get_task_temporary_dir(task_id, create=False)
        self.assertTrue(os.path.isdir(tmp_dir))
        self.assertEquals(os.path.normpath(tmp_dir), expected_tmp_dir)
        shutil.rmtree(tmp_dir)
        tmp_dir = dm.get_task_temporary_dir(task_id, create=False)
        self.assertFalse(os.path.isdir(tmp_dir))
        tmp_dir = dm.get_task_temporary_dir(task_id, create=True)
        self.assertTrue(os.path.isdir(tmp_dir))

    def testGetTaskResourceDir(self):
        dm = DirManager(self.path)
        task_id = '12345'
        resDir = dm.get_task_resource_dir(task_id)
        expectedResDir = os.path.join(self.path, task_id, 'resources')
        self.assertEquals(os.path.normpath(resDir), expectedResDir)
        self.assertTrue(os.path.isdir(resDir))
        resDir = dm.get_task_resource_dir(task_id)
        self.assertTrue(os.path.isdir(resDir))
        resDir = dm.get_task_resource_dir(task_id, create=False)
        self.assertTrue(os.path.isdir(resDir))
        self.assertEquals(os.path.normpath(resDir), expectedResDir)
        shutil.rmtree(resDir)
        resDir = dm.get_task_resource_dir(task_id, create=False)
        self.assertFalse(os.path.isdir(resDir))
        resDir = dm.get_task_resource_dir(task_id, create=True)
        self.assertTrue(os.path.isdir(resDir))

    def testGetTaskOutputDir(self):
        dm = DirManager(self.path)
        task_id = '12345'
        outDir = dm.get_task_output_dir(task_id)
        expectedResDir = os.path.join(self.path, task_id, 'output')
        self.assertEquals(os.path.normpath(outDir), expectedResDir)
        self.assertTrue(os.path.isdir(outDir))
        outDir = dm.get_task_output_dir(task_id)
        self.assertTrue(os.path.isdir(outDir))
        outDir = dm.get_task_output_dir(task_id, create=False)
        self.assertTrue(os.path.isdir(outDir))
        self.assertEquals(os.path.normpath(outDir), expectedResDir)
        shutil.rmtree(outDir)
        outDir = dm.get_task_output_dir(task_id, create=False)
        self.assertFalse(os.path.isdir(outDir))
        outDir = dm.get_task_output_dir(task_id, create=True)
        self.assertTrue(os.path.isdir(outDir))

    def testClearTemporary(self):
        dm = DirManager(self.path)
        task_id = '12345'
        tmp_dir = dm.get_task_temporary_dir(task_id)
        self.assertTrue(os.path.isdir(tmp_dir))
        file1 = os.path.join(tmp_dir, 'file1')
        file2 = os.path.join(tmp_dir, 'file2')
        dir1 = os.path.join(tmp_dir, 'dir1')
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
        self.assertTrue(os.path.isdir(tmp_dir))
        self.assertFalse(os.path.isfile(file1))
        self.assertFalse(os.path.isfile(file2))
        self.assertFalse(os.path.isfile(file3))
        self.assertFalse(os.path.isdir(dir1))

    def testClearResource(self):
        dm = DirManager(self.path)
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
        self.assertFalse(os.path.isfile(file3))
        self.assertFalse(os.path.isdir(dir1))

    def testClearOutput(self):
        dm = DirManager(self.path)
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
        self.assertFalse(os.path.isfile(file3))
        self.assertFalse(os.path.isdir(dir1))


class TestFindTaskScript(TestDirFixture, LogTestCase):
    def test_find_task_script(self):
        script_path = os.path.join(self.path, "resources", "scripts")
        os.makedirs(script_path)
        script = os.path.join(script_path, "bla")
        open(script, "w").close()
        task_file = os.path.join(self.path, "task", "testtask.py")
        path = find_task_script(self.path, "bla")
        self.assertTrue(os.path.isdir(os.path.dirname(path)))
        self.assertEqual(os.path.basename(path), "bla")
        with self.assertLogs(logger, level="ERROR"):
            find_task_script(self.path, "notexisting")
