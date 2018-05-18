import os
import unittest.mock as mock
import zipfile

from apps.core.task.coretask import CoreTask
from apps.core.task.coretaskstate import TaskDefinition

from golem.resource.dirmanager import DirManager
from golem.resource.resource import (get_resources_for_task, ResourceType,
                                     TaskResource, TaskResourceHeader)
from golem.resource.resourcesmanager import DistributedResourceManager

from golem.testutils import TempDirFixture


class TestTaskResourceHeader(TempDirFixture):
    def setUp(self):
        TempDirFixture.setUp(self)

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
        self.assertEqual(len(header.files_data), 2)
        self.assertEqual(len(header.sub_dir_headers[0].files_data), 1)

    def testBuildFromChosen(self):
        dir_name = self.dir_manager.get_task_resource_dir('task2')
        header = TaskResourceHeader.build_from_chosen("resource", dir_name, [self.file1, self.file3])
        header2 = TaskResourceHeader.build_header_delta_from_header(TaskResourceHeader("resource"), dir_name,
                                                                    [self.file1, self.file3])
        self.assertTrue(header == header2)
        self.assertEqual(header.dir_name, header2.dir_name)
        self.assertEqual(header.files_data, header2.files_data)

        with self.assertRaises(TypeError):
            TaskResourceHeader.build_header_delta_from_chosen(None, None)

        self.assertEqual(TaskResourceHeader.build_header_delta_from_chosen(header, self.path),
                         TaskResourceHeader(header.dir_name))

        with self.assertRaises(TypeError):
            TaskResourceHeader.build_parts_header_delta_from_chosen(None, None, None)
        with self.assertRaises(TypeError):
            TaskResourceHeader.build_header_delta_from_header(None, None, None)


class TestTaskResource(TempDirFixture):

    def testInit(self):
        self.assertIsNotNone(TaskResource(self.path))


class TestGetTaskResources(TempDirFixture):

    @staticmethod
    def _get_core_task_definition():
        task_definition = TaskDefinition()
        task_definition.max_price = 100
        task_definition.task_id = "xyz"
        task_definition.estimated_memory = 1024
        task_definition.full_task_timeout = 3000
        task_definition.subtask_timeout = 30
        return task_definition

    def _get_core_task(self):
        from golem.network.p2p.node import Node
        task_def = self._get_core_task_definition()

        class CoreTaskDeabstacted(CoreTask):
            ENVIRONMENT_CLASS = mock.MagicMock()

            def query_extra_data(self, perf_index, num_cores=0, node_id=None,
                                 node_name=None):
                pass

            def short_extra_data_repr(self, extra_data):
                pass

            def query_extra_data_for_test_task(self):
                pass

        task = CoreTaskDeabstacted(
            owner=Node(
                node_name="ABC",
                pub_addr="10.10.10.10",
                pub_port=123,
                key="key",
            ),
            task_definition=task_def,
            resource_size=1024
        )
        dm = DirManager(self.path)
        task.initialize(dm)
        return task

    def test_get_task_resources(self):
        c = self._get_core_task()
        th = TaskResourceHeader(self.path)
        assert get_resources_for_task(th, c.get_resources(), c.tmp_dir) is None

        files = self.additional_dir_content([[1], [[1], [2, [3]]]])
        c.task_resources = files[1:]
        resource = get_resources_for_task(th, c.get_resources(), c.tmp_dir)
        assert os.path.isfile(resource)
        assert zipfile.is_zipfile(resource)
        z = zipfile.ZipFile(resource)
        in_z = z.namelist()
        assert len(in_z) == 6

        assert get_resources_for_task(th, c.get_resources(), c.tmp_dir,
                                      ResourceType.HASHES) == files[1:]

        with open(files[0], 'w') as f:
            f.write("ABCD")

        drm = DistributedResourceManager(os.path.dirname(files[0]))
        res_files = drm.split_file(files[0])
        c.add_resources({files[0]: res_files})

        assert get_resources_for_task(th, c.get_resources(), c.tmp_dir,
                                      resource_type=3) is None
        assert get_resources_for_task(th, c.get_resources(), c.tmp_dir,
                                      resource_type="aaa") is None
        assert get_resources_for_task(th, c.get_resources(), c.tmp_dir,
                                      resource_type=None) is None
