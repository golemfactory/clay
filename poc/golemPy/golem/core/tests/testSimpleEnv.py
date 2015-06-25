import unittest
import sys
import os
import shutil

sys.path.append(os.environ.get('GOLEM'))

from golem.core.simpleenv import SimpleEnv, DATA_DIRECTORY

class TestSimpleEnv(unittest.TestCase):
    def testEnvFileName(self):
        shutil.rmtree(DATA_DIRECTORY)
        self.assertFalse(os.path.isdir(DATA_DIRECTORY))
        fname = SimpleEnv.envFileName('testFile.txt')
        self.assertTrue(os.path.isdir(DATA_DIRECTORY))
        self.assertTrue(DATA_DIRECTORY in fname)
        fname2 = SimpleEnv.envFileName(os.path.join(DATA_DIRECTORY, 'testFile.txt'))
        self.assertTrue(os.path.isdir(DATA_DIRECTORY))
        self.assertTrue(DATA_DIRECTORY in fname2)
        shutil.rmtree(DATA_DIRECTORY)

    def testOpenEnvFile(self):
        f = SimpleEnv.openEnvFile('testFile.txt')
        self.assertTrue(os.path.isdir(DATA_DIRECTORY))
        self.assertFalse(f.closed)
        self.assertTrue(os.path.isfile(os.path.join(DATA_DIRECTORY, 'testFile.txt')))
        f.close()
        self.assertTrue(f.closed)


if __name__ == '__main__':
    unittest.main()