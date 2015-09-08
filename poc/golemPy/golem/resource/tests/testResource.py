import sys
import os
import unittest
import logging
import shutil

sys.path.append(os.environ.get('GOLEM'))

path = 'C:\golem_test\\test3'
from golem.resource.Resource import TaskResourceHeader, remove_disallowed_filename_chars, TaskResource
from golem.resource.dir_manager import DirManager

class TestTaskResourceHeader(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)

        if not os.path.isdir(path):
            os.mkdir(path)

        self.dir_manager = DirManager(path, 'node3')
        res_path = self.dir_manager.get_task_resource_dir('task2')

        self.file1 = os.path.join(res_path, 'file1')
        self.file2 = os.path.join(res_path, 'file2')
        self.dir1 = os.path.join(res_path, 'dir1')
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
        dir_name = self.dir_manager.get_task_resource_dir("task2")
        header = TaskResourceHeader.build("resource", dir_name)
        self.assertEquals(len(header.files_data), 2)
        self.assertEquals(len(header.sub_dir_headers[0].files_data), 1)

    def testBuildFromChosen(self):
        dir_name = self.dir_manager.get_task_resource_dir('task2')
        header = TaskResourceHeader.build_from_chosen("resource", dir_name, [self.file1, self.file3])
        header2 = TaskResourceHeader.build_header_delta_from_header(TaskResourceHeader("resource"), dir_name, [self.file1, self.file3])
        self.assertTrue(header == header2)
        self.assertEquals(header.dir_name, header2.dir_name)
        self.assertEquals(header.files_data, header2.files_data)

class TestTaskResource(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level = logging.DEBUG)
        if not os.path.isdir(path):
            os.mkdir(path)

    def testInit(self):
        self.assertIsNotNone(TaskResource(path))


if __name__ == '__main__':
    unittest.main()