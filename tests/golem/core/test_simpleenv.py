import unittest
import os
import shutil
from golem.core.simpleenv import SimpleEnv


class TestSimpleEnv(unittest.TestCase):

    def setUp(self):
        self.saved_data_directory = SimpleEnv.DATA_DIRECTORY
        SimpleEnv.DATA_DIRECTORY = os.path.abspath("tmpdir")

    def testEnvFileName(self):
        if os.path.isdir(SimpleEnv.DATA_DIRECTORY):
            shutil.rmtree(SimpleEnv.DATA_DIRECTORY)
        self.assertFalse(os.path.isdir(SimpleEnv.DATA_DIRECTORY))
        fname = SimpleEnv.env_file_name('testFile.txt')
        self.assertTrue(os.path.isdir(SimpleEnv.DATA_DIRECTORY))
        self.assertTrue(SimpleEnv.DATA_DIRECTORY in fname)
        fname2 = SimpleEnv.env_file_name(os.path.join(SimpleEnv.DATA_DIRECTORY, 'testFile.txt'))
        self.assertTrue(os.path.isdir(SimpleEnv.DATA_DIRECTORY))
        self.assertTrue(SimpleEnv.DATA_DIRECTORY in fname2)
        shutil.rmtree(SimpleEnv.DATA_DIRECTORY)

    def testOpenEnvFile(self):
        f = SimpleEnv.open_env_file('testFile.txt')
        self.assertTrue(os.path.isdir(SimpleEnv.DATA_DIRECTORY))
        self.assertFalse(f.closed)
        self.assertTrue(os.path.isfile(os.path.join(SimpleEnv.DATA_DIRECTORY, 'testFile.txt')))
        f.close()
        self.assertTrue(f.closed)

    def tearDown(self):
        if os.path.isdir(SimpleEnv.DATA_DIRECTORY):
            shutil.rmtree(SimpleEnv.DATA_DIRECTORY)
        SimpleEnv.DATA_DIRECTORY = self.saved_data_directory
