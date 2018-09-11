import logging
import os
import random
from copy import copy
from typing import Optional

import enforce
from golem_messages.message import ComputeTaskDef

from apps.core.task.coretask import (CoreTask,
                                     CoreTaskBuilder,
                                     CoreTaskTypeInfo)
from apps.upack.upackenvironment import UpackTaskEnvironment
from apps.upack.task.upacktaskstate import UpackTaskDefaults, UpackTaskOptions
from apps.upack.task.upacktaskstate import UpackTaskDefinition
from apps.upack.task.verifier import UpackTaskVerifier
from golem.task.taskbase import Task
from golem.task.taskclient import TaskClient
from golem.task.taskstate import SubtaskStatus

logger = logging.getLogger("apps.upack")


class UpackTaskTypeInfo(CoreTaskTypeInfo):
    def __init__(self):
        super().__init__(
            "Upack",
            UpackTaskDefinition,
            UpackTaskDefaults(),
            UpackTaskOptions,
            UpackTaskBuilder
        )


@enforce.runtime_validation(group="upack")
class UpackTask(CoreTask):
    ENVIRONMENT_CLASS = UpackTaskEnvironment
    VERIFIER_CLASS = UpackTaskVerifier

    def __init__(self,
                 total_tasks: int,
                 task_definition: UpackTaskDefinition,
                 root_path=None,
                 owner=None):
        super().__init__(
            owner=owner,
            task_definition=task_definition,
            root_path=root_path,
            total_tasks=total_tasks
        )

    def short_extra_data_repr(self, extra_data):
        return "Upacktask extra_data: {}".format(extra_data)

    def _extra_data(self, perf_index=0.0) -> ComputeTaskDef:
        subtask_id = self.create_subtask_id()
        extra_data = {
            "echo": "Hello Upack task"
        }

        return self._new_compute_task_def(subtask_id,
                                          extra_data,
                                          perf_index=perf_index)

    def query_extra_data(self,
                         perf_index: float,
                         num_cores: int = 1,
                         node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        logger.debug("Query extra data on upacktask")

        ctd = self._extra_data(perf_index)
        sid = ctd['subtask_id']

        #FIXME Is this necessary?
        self.subtasks_given[sid] = copy(ctd['extra_data'])
        self.subtasks_given[sid]["status"] = SubtaskStatus.starting
        self.subtasks_given[sid]["perf"] = perf_index
        self.subtasks_given[sid]["node_id"] = node_id
        self.subtasks_given[sid]["node_id"] = node_id
        self.subtasks_given[sid]["shared_data_files"] = \
            self.task_definition.shared_data_files
        self.subtasks_given[sid]["subtask_id"] = sid

        return self.ExtraData(ctd=ctd)

    def accept_results(self, subtask_id, result_files):
        super().accept_results(subtask_id, result_files)
        node_id = self.subtasks_given[subtask_id]['node_id']
        TaskClient.assert_exists(node_id, self.counting_nodes).accept()
        self.num_tasks_received += 1

    def query_extra_data_for_test_task(self) -> ComputeTaskDef:
        exd = self._extra_data()
        return exd


class UpackTaskBuilder(CoreTaskBuilder):
    TASK_CLASS = UpackTask

    @classmethod
    def build_dictionary(cls, definition: UpackTaskDefinition):
        return super().build_dictionary(definition)

    @classmethod
    def build_full_definition(cls, task_type: UpackTaskTypeInfo, dictionary):
        return super().build_full_definition(task_type, dictionary)

# comment that line to enable type checking
enforce.config({'groups': {'set': {'upack': False}}})
