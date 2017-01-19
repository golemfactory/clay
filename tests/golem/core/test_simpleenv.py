import os
import shutil
import unittest

from golem.core.simpleenv import SimpleEnv


class TestSimpleEnv(unittest.TestCase):

    def testEnvFileName(self):
        fname = SimpleEnv.env_file_name('testFile.txt')
        shutil.rmtree(os.path.dirname(fname))
