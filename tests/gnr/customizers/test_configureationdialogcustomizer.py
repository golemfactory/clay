import unittest
import os
import re

from gnr.customizers.configurationdialogcustomizer import ConfigurationDialogCustomizer


class TestConfigurationDialogCustomizer(unittest.TestCase):
    testdir = "testdir"
    testdir2 = os.path.join(testdir, "testdir2")
    testfile1 = "testfile1"
    testfile2 = "testfile2"

    def setUp(self):
        if not os.path.exists(self.testdir):
            os.makedirs(self.testdir)

    def test_du(self):
        res = ConfigurationDialogCustomizer.du("notexisting")
        self.assertEqual(res, "-1")
        res = ConfigurationDialogCustomizer.du(self.testdir)
        try:
            size = float(res)
        except ValueError:
            size, sym = re.split("[ kKmMgGbB]", res)[:2]
        self.assertGreaterEqual(float(size), 0.0)
        with open(os.path.join(self.testdir, self.testfile1), 'w') as f:
            f.write("a" * 10000)
        res = ConfigurationDialogCustomizer.du(self.testdir)
        size1, sym = re.split("[ kKmMgGbB]", res)[:2]
        self.assertGreater(float(size1), float(size))
        if not os.path.exists(self.testdir2):
            os.makedirs(self.testdir2)
        with open(os.path.join(self.testdir2, self.testfile2), 'w') as f:
            f.write("123" * 10000)
        res = ConfigurationDialogCustomizer.du(self.testdir)
        size2, sym = re.split("[ kKmMgGbB]", res)[:2]
        self.assertGreater(float(size2), float(size1))
        res = ConfigurationDialogCustomizer.du(".")
        try:
            size = float(res)
        except ValueError:
            size, sym = re.split("[ kKmMgGbB]", res)[:2]
        self.assertGreater(size, 0)

    def tearDown(self):
        if os.path.exists(os.path.join(self.testdir2, self.testfile2)):
            os.remove(os.path.join(self.testdir2, self.testfile2))
        if os.path.exists(self.testdir2):
            os.removedirs(self.testdir2)
        if os.path.exists(os.path.join(self.testdir, self.testfile1)):
            os.remove(os.path.join(self.testdir, self.testfile1))
        if os.path.exists(self.testdir):
            os.removedirs(self.testdir)


