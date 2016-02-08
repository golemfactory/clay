import unittest
import os
import shutil
import stat

from golem.core.fileshelper import get_dir_size
from golem.core.common import get_golem_path, is_windows


class TestDirSize(unittest.TestCase):
    testdir = "testdir"
    testfile1 = os.path.join(testdir, "testfile1")
    testdir2 = os.path.join(testdir, "testdir2")
    testfile2 = os.path.join(testdir2, "testfile2")
    testdir3 = os.path.join(testdir, "testdir3")
    testfile3 = os.path.join(testdir3, "testfile3")

    def setUp(self):
        if os.path.isdir(self.testdir):
            shutil.rmtree(self.testdir)
        os.makedirs(self.testdir)

    def test_dir_size(self):
        with self.assertRaises(OSError):
            get_dir_size("notexisting")

        self.assertLess(get_dir_size(self.testdir), 10000)
        with open(self.testfile1, 'w') as f:
            f.write("a" * 20000)
        os.makedirs(self.testdir2)
        with open(self.testfile2, 'w') as f:
            f.write("b" * 30000)
        size = get_dir_size(self.testdir)
        self.assertGreaterEqual(size, 50000)

        self.assertGreater(get_dir_size(get_golem_path()), 3 * 1024 * 1024)

        if not is_windows():
            os.makedirs(self.testdir3)
            with open(self.testfile3, 'w') as f:
                f.write("c" * 30000)
            os.chmod(self.testdir3, 0o200)
            new_size = get_dir_size(self.testdir)
            self.assertLess(new_size - size, 10000)

    def tearDown(self):
        if not is_windows():
            if os.path.isdir(self.testdir3):
                os.chmod(self.testdir3, 0o700)
            if os.path.isfile(self.testfile3):
                os.chmod(self.testfile3, 0o600)

        if os.path.isdir(self.testdir):
            shutil.rmtree(self.testdir)