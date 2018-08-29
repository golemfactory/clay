from unittest.mock import patch
import os
import shutil
import time

from golem.core.common import is_linux, is_osx
from golem.resource.dirmanager import symlink_or_copy, DirManager, \
    find_task_script, logger, list_dir_recursive
from golem.tools.assertlogs import LogTestCase
from golem.testutils import TempDirFixture


class TestSymlinkOrCopy(TempDirFixture):
    def test_OSError_file(self):
        # given
        source_path = os.path.join(self.path, 'source')
        target_path = os.path.join(self.path, 'target')

        with open(source_path, 'w') as f:
            f.write('source')
        with open(target_path, 'w') as f:
            f.write('target')

        # when
        with patch('os.symlink', side_effect=OSError):
            symlink_or_copy(source_path, target_path)

        # then
        with open(target_path, 'r') as f:
            target_contents = f.read()
        assert target_contents == 'source'

    def test_OSError_dir(self):
        # given
        source_dir_path = os.path.join(self.path, 'source')
        source_file_path = os.path.join(source_dir_path, 'file')
        target_path = os.path.join(self.path, 'target')

        os.mkdir(source_dir_path)
        with open(source_file_path, 'w') as f:
            f.write('source')

        # when
        with patch('os.symlink', side_effect=OSError):
            symlink_or_copy(source_dir_path, target_path)

        # then
        with open(os.path.join(target_path, 'file')) as f:
            target_file_contents = f.read()

        assert target_file_contents == 'source'


class TestDirManager(TempDirFixture):

    node1 = 'node1'

    def testInit(self):
        self.assertIsNotNone(DirManager(self.path))


    def test_getFileExtension(self):
        dm = DirManager(self.path)
        path = 'some/long/path/to/somefile.abc'
        ext = dm.get_file_extension(path)

        assert ext == '.abc'

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
        self.assertTrue(os.path.isfile(file1))
        self.assertTrue(os.path.isfile(file2))
        self.assertTrue(os.path.isfile(file3))
        self.assertTrue(os.path.isfile(file4))
        self.assertTrue(os.path.isdir(dir1))
        self.assertTrue(os.path.isdir(dir2))
        dm = DirManager(self.path)
        dm.clear_dir(dm.root_path)
        self.assertFalse(os.path.isfile(file1))
        self.assertFalse(os.path.isfile(file3))
        self.assertFalse(os.path.isdir(dir1))
        self.assertFalse(os.path.isfile(file2))
        self.assertFalse(os.path.isfile(file4))
        self.assertFalse(os.path.isdir(dir2))

    def testClearDirOlderThan(self):
        # given
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

        two_hours_ago = time.time() - 2*60*60

        os.utime(file1, times=(two_hours_ago, two_hours_ago))
        os.utime(dir1, times=(two_hours_ago, two_hours_ago))

        assert os.path.isfile(file1)
        assert os.path.isfile(file2)
        assert os.path.isfile(file3)
        assert os.path.isfile(file4)
        assert os.path.isdir(dir1)
        assert os.path.isdir(dir2)

        # when
        dm = DirManager(self.path)
        dm.clear_dir(dm.root_path, older_than_seconds=60*60)

        # then
        assert not os.path.isfile(file1)
        assert os.path.isfile(file2)
        assert not os.path.isdir(dir1)
        assert not os.path.isfile(file3)
        assert os.path.isdir(dir2)
        assert os.path.isfile(file4)

    def testGetTaskTemporaryDir(self):
        dm = DirManager(self.path)
        task_id = '12345'
        tmp_dir = dm.get_task_temporary_dir(task_id)
        expected_tmp_dir = os.path.join(self.path, task_id, 'tmp')
        self.assertEqual(os.path.normpath(tmp_dir), expected_tmp_dir)
        self.assertTrue(os.path.isdir(tmp_dir))
        tmp_dir = dm.get_task_temporary_dir(task_id)
        self.assertTrue(os.path.isdir(tmp_dir))
        tmp_dir = dm.get_task_temporary_dir(task_id, create=False)
        self.assertTrue(os.path.isdir(tmp_dir))
        self.assertEqual(os.path.normpath(tmp_dir), expected_tmp_dir)
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
        self.assertEqual(os.path.normpath(resDir), expectedResDir)
        self.assertTrue(os.path.isdir(resDir))
        resDir = dm.get_task_resource_dir(task_id)
        self.assertTrue(os.path.isdir(resDir))
        resDir = dm.get_task_resource_dir(task_id, create=False)
        self.assertTrue(os.path.isdir(resDir))
        self.assertEqual(os.path.normpath(resDir), expectedResDir)
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
        self.assertEqual(os.path.normpath(outDir), expectedResDir)
        self.assertTrue(os.path.isdir(outDir))
        outDir = dm.get_task_output_dir(task_id)
        self.assertTrue(os.path.isdir(outDir))
        outDir = dm.get_task_output_dir(task_id, create=False)
        self.assertTrue(os.path.isdir(outDir))
        self.assertEqual(os.path.normpath(outDir), expectedResDir)
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


class TestFindTaskScript(TempDirFixture, LogTestCase):
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


class TestUtilityFunction(TempDirFixture):
    def test_ls_r(self):
        os.makedirs(os.path.join(self.tempdir, "aa", "bb", "cc"))
        os.makedirs(os.path.join(self.tempdir, "ddd", "bb", "cc"))
        os.makedirs(os.path.join(self.tempdir, "ee", "ff"))

        with open(os.path.join(self.tempdir, "ee", "f1"), "w") as f:
            f.write("content")
        with open(os.path.join(self.tempdir, "f2"), "w") as f:
            f.write("content")
        with open(os.path.join(self.tempdir, "aa", "bb", "f3"), "w") as f:
            f.write("content")

        # Depending on os, we are testing symlinks or not
        if is_osx() or is_linux():
            os.symlink(os.path.join(self.tempdir, "f2"),
                       os.path.join(self.tempdir, "ee", "ff", "f4"))
            dirs = list(list_dir_recursive(self.tempdir))
            true_dirs = {os.path.join(*[self.tempdir, *x])
                         for x in [["ee", "f1"],
                                   ["f2"],
                                   ["aa", "bb", "f3"],
                                   ["ee", "ff", "f4"]]}
            self.assertEqual(set(dirs), true_dirs)
        else:
            dirs = list(list_dir_recursive(self.tempdir))
            true_dirs = {os.path.join(*[self.tempdir, *x])
                         for x in [["ee", "f1"], ["f2"], ["aa", "bb", "f3"]]}
            self.assertEqual(set(dirs), true_dirs)
