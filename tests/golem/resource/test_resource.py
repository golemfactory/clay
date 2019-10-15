import os
import unittest.mock as mock
import zipfile

from apps.core.task.coretask import CoreTask
from apps.core.task.coretaskstate import TaskDefinition

from golem.resource.dirmanager import DirManager
from golem.resource.resource import get_resources_for_task

from golem.testutils import TempDirFixture



class TestGetTaskResources(TempDirFixture):

    @staticmethod
    def _get_core_task_definition():
        task_definition = TaskDefinition()
        task_definition.max_price = 100
        task_definition.task_id = "xyz"
        task_definition.estimated_memory = 1024
        task_definition.timeout = 3000
        task_definition.subtask_timeout = 30
        task_definition.subtasks_count = 1
        return task_definition

    def _get_core_task(self):
        from golem_messages.datastructures.p2p import Node
        task_def = self._get_core_task_definition()

        class CoreTaskDeabstacted(CoreTask):
            ENVIRONMENT_CLASS = lambda _self: mock.MagicMock(  # noqa
                get_id=lambda: 'test',
            )

            def query_extra_data(self, perf_index, node_id=None,
                                 node_name=None):
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

        files = self.additional_dir_content([[1], [[1], [2, [3]]]])
        c.task_resources = files[1:]

        assert get_resources_for_task(c.get_resources()) == files[1:]
