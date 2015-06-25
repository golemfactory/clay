import sys
import os
import unittest
import logging
import shutil

sys.path.append(os.environ.get('GOLEM'))

path = 'C:\golem_test\\test3'
from golem.resource.Resource import TaskResourceHeader, removeDisallowedFilenameChars, TaskResource
from golem.resource.DirManager import DirManager

class TestTaskResourceHeader(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)

        if not os.path.isdir(path):
            os.mkdir(path)

        self.dirManager = DirManager(path, 'node3')
        resPath = self.dirManager.getTaskResourceDir('task2')

        self.file1 = os.path.join(resPath, 'file1')
        self.file2 = os.path.join(resPath, 'file2')
        self.dir1 = os.path.join(resPath, 'dir1')
        self.file3 = os.path.join(self.dir1, 'file3')
        open(self.file1, 'w').close()
        open(self.file2, 'w').close()
        if not os.path.isdir(self.dir1):
            os.mkdir(self.dir1)
        open(self.file3, 'w').close()

    def tearDown(self):
       path = 'C:\golem_test\\test3'
       if os.path.isdir(path):
           shutil.rmtree(path)

    def testBuild(self):
        dirName = self.dirManager.getTaskResourceDir("task2")
        header = TaskResourceHeader.build("resource", dirName)
        self.assertEquals(len(header.filesData), 2)
        self.assertEquals(len(header.subDirHeaders[0].filesData), 1)

    def testBuildFromChosen(self):
        dirName = self.dirManager.getTaskResourceDir('task2')
        header = TaskResourceHeader.buildFromChosen("resource", dirName, [self.file1, self.file3])
        header2 = TaskResourceHeader.buildHeaderDeltaFromHeader(TaskResourceHeader("resource"), dirName, [self.file1, self.file3])
        self.assertTrue(header == header2)
        self.assertEquals(header.dirName, header2.dirName)
        self.assertEquals(header.filesData, header2.filesData)

class TestTaskResource(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level = logging.DEBUG)
        if not os.path.isdir(path):
            os.mkdir(path)

    def testInit(self):
        self.assertIsNotNone(TaskResource(path))


if __name__ == '__main__':
    unittest.main()