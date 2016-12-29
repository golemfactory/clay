import os
from golem.resource.resource import TaskResourceHeader, TaskResource
from golem.resource.dirmanager import DirManager
from test_dirmanager import TestDirFixture


class TestTaskResourceHeader(TestDirFixture):
    def setUp(self):
        TestDirFixture.setUp(self)

        self.dir_manager = DirManager(self.path)
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

    def testBuild(self):
        dir_name = self.dir_manager.get_task_resource_dir("task2")
        header = TaskResourceHeader.build("resource", dir_name)
        self.assertEquals(len(header.files_data), 2)
        self.assertEquals(len(header.sub_dir_headers[0].files_data), 1)

    def testBuildFromChosen(self):
        dir_name = self.dir_manager.get_task_resource_dir('task2')
        header = TaskResourceHeader.build_from_chosen("resource", dir_name, [self.file1, self.file3])
        header2 = TaskResourceHeader.build_header_delta_from_header(TaskResourceHeader("resource"), dir_name,
                                                                    [self.file1, self.file3])
        self.assertTrue(header == header2)
        self.assertEquals(header.dir_name, header2.dir_name)
        self.assertEquals(header.files_data, header2.files_data)

        with self.assertRaises(TypeError):
            TaskResourceHeader.build_header_delta_from_chosen(None, None)

        self.assertEqual(TaskResourceHeader.build_header_delta_from_chosen(header, self.path),
                         TaskResourceHeader(header.dir_name))

        with self.assertRaises(TypeError):
            TaskResourceHeader.build_parts_header_delta_from_chosen(None, None, None)
        with self.assertRaises(TypeError):
            TaskResourceHeader.build_header_delta_from_header(None, None, None)


class TestTaskResource(TestDirFixture):

    def testInit(self):
        self.assertIsNotNone(TaskResource(self.path))
