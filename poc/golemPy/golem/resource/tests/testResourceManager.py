import sys
import os
import unittest
import logging
import shutil

sys.path.append(os.environ.get('GOLEM'))

from golem.resource.ResourcesManager import ResourcesManager
from golem.resource.DirManager import DirManager

path = 'C:\golem_test\\test2'

class TestResourcesManager(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)

        if not os.path.isdir(path):
            os.mkdir(path)

        self.dirManager = DirManager(path, 'node2')
        resPath = self.dirManager.getTaskResourceDir('task2')

        file1 = os.path.join(resPath, 'file1')
        file2 = os.path.join(resPath, 'file2')
        dir1 = os.path.join(resPath, 'dir1')
        file3 = os.path.join(dir1, 'file3')
        open(file1, 'w').close()
        open(file2, 'w').close()
        if not os.path.isdir(dir1):
            os.mkdir(dir1)
        open(file3, 'w').close()

    def tearDown(self):
       path = 'C:\golem_test\\test2'
       if os.path.isdir(path):
           shutil.rmtree(path)

    def testInit(self):
         self.assertIsNotNone(ResourcesManager(self.dirManager, 'owner'))

    def testGetResourceHeader(self):
        rm = ResourcesManager(self.dirManager, 'owner')
        header = rm.getResourceHeader('task2')
        self.assertEquals(len(header.filesData), 2)
        self.assertEquals(len(header.subDirHeaders[0].filesData), 1)
        header2 = rm.getResourceHeader('task3')
        self.assertEquals(len(header2.filesData), 0)
        self.assertEquals(len(header2.subDirHeaders), 0)

    def testGetResourceDelta(self):
        rm = ResourcesManager(self.dirManager, 'owner')
        header = rm.getResourceHeader('task2')
        delta = rm.getResourceDelta('task2', header)
        self.assertEquals(len(delta.filesData), 0)
        self.assertEquals(len (delta.subDirResources[0].filesData), 0)
        header2 = rm.getResourceHeader('task3')
        delta2 = rm.getResourceDelta('task2', header2)
        self.assertEquals(len(delta2.filesData), 2)
        self.assertEquals(len (delta2.subDirResources[0].filesData), 1)
        resPath = self.dirManager.getTaskResourceDir('task2')
        file5 = os.path.join(resPath, 'file5')
        open(file5, 'w').close()
        dir1 = os.path.join(resPath, 'dir1')
        file4 = os.path.join(dir1, 'file4')
        open(file4, 'w').close()
        delta3 = rm.getResourceDelta('task2', header)
        self.assertEquals(len(delta3.filesData), 1)
        self.assertEquals(len(delta3.subDirResources[0].filesData), 1)
        os.remove(file4)
        os.remove(file5)

    #
    # def testPrepareResourceDelta(self):
    #     assert False
    #
    # def testUpdateResource(self):
    #     assert False
    #
    def testGetResourceDir(self):
        rm = ResourcesManager(self.dirManager, 'owner')
        resDir = rm.getResourceDir('task2')
        self.assertTrue(os.path.isdir(resDir))
        self.assertEqual(resDir, self.dirManager.getTaskResourceDir('task2'))

    def testGetTemporaryDir(self):
        rm = ResourcesManager(self.dirManager, 'owner')
        tmpDir = rm.getTemporaryDir('task2')
        self.assertTrue(os.path.isdir(tmpDir))
        self.assertEqual(tmpDir, self.dirManager.getTaskTemporaryDir('task2'))

    def testGetOutputDir(self):
        rm = ResourcesManager(self.dirManager, 'owner')
        outDir = rm.getOutputDir('task2')
        self.assertTrue(os.path.isdir(outDir))
        self.assertEqual(outDir, self.dirManager.getTaskOutputDir('task2'))


    # def testFileDataReceived(self):
    #     assert False

if __name__ == '__main__':
    unittest.main()