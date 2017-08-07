import logging
import os
import random
from typing import Union

from apps.core.task import coretask
from apps.core.task.coretask import (CoreTask,
                                     CoreTaskBuilder,
                                     TaskTypeInfo, AcceptClientVerdict)
from apps.dummy.dummyenvironment import DummyTaskEnvironment
from apps.dummy.task.dummytaskstate import DummyTaskDefaults, DummyTaskOptions
from apps.dummy.task.dummytaskstate import DummyTaskDefinition
from apps.dummy.task.verificator import DummyTaskVerificator
from golem.core.common import timeout_to_deadline
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import ComputeTaskDef, Task
from golem.task.taskstate import SubtaskStatus

logger = logging.getLogger("apps.dummy")


class DummyTaskTypeInfo(TaskTypeInfo):
    def __init__(self, dialog, customizer):
        super(DummyTaskTypeInfo, self).__init__(
            "Dummy",
            DummyTaskDefinition,
            DummyTaskDefaults(),
            DummyTaskOptions,
            DummyTaskBuilder,
            dialog,
            customizer
        )


class DummyTask(CoreTask):
    ENVIRONMENT_CLASS = DummyTaskEnvironment
    VERIFICATOR_CLASS = DummyTaskVerificator

    RESULT_EXTENSION = ".result"

    # TODO many things should be used at coretask lvl,
    #  but many of them had to be copied from
    #  renderingtask, do something about it
    def __init__(self,
                 node_name: str,
                 task_definition: DummyTaskDefinition,
                 root_path=None,
                 # TODO change that when TaskHeader will be updated
                 owner_address="",
                 owner_port=0,
                 owner_key_id=""
                 ):
        super().__init__(
            task_definition=task_definition,
            node_name=node_name,
            owner_address=owner_address,
            owner_port=owner_port,
            owner_key_id=owner_key_id,
            resource_size=task_definition.shared_data_size,
            root_path=root_path
        )

        # TODO abstract away
        self.verificator.verification_options["result_size"] = self.task_definition.result_size
        self.verificator.verification_options["difficulty"] = self.task_definition.difficulty
        self.verificator.verification_options["shared_data_file"] = \
            self.task_definition.shared_data_file
        self.verificator.verification_options["result_size"] = self.task_definition.result_size
        self.dir_manager = DirManager(self.root_path)

    def short_extra_data_repr(self, extra_data):
        return "Dummytask extra_data: {}".format(extra_data)

    @coretask.accepting
    def query_extra_data(self, perf_index: float, num_cores=1, node_id: str = None,
                         node_name: str = None) -> Task.ExtraData:
        subtask_id = self._get_new_subtask_id()

        # create subtask-specific data, 4 bits go for one char (hex digit)
        sbs = self.task_definition.subtask_data_size
        data = format((random.getrandbits(sbs)), '0{}b'.format(sbs))

        shared_data_file_base = os.path.basename(self.task_definition.shared_data_file)

        extra_data = {
            'data_file': shared_data_file_base,
            'subtask_data': data,
            'difficulty': self.task_definition.difficulty,
            'result_size': self.task_definition.result_size,
            'result_file': self._get_result_file_name(subtask_id),
            'subtask_data_size': sbs
        }

        ctd = self._new_compute_task_def(subtask_id, extra_data, perf_index)

        self.subtasks_given[subtask_id] = extra_data
        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.starting
        self.subtasks_given[subtask_id]['perf'] = perf_index
        self.subtasks_given[subtask_id]['node_id'] = node_id

        return self.ExtraData(ctd=ctd)

    # TODO luxrender also increases num_tasks_received, possible refactor
    def accept_results(self, subtask_id, result_files):
        super().accept_results(subtask_id, result_files)
        self.num_tasks_received += 1

    def _get_new_subtask_id(self) -> str:
        return "{}".format(random.getrandbits(128))

    def _get_result_file_name(self, subtask_id: str) -> str:
        return self.task_definition.out_file_basename + subtask_id[0:6] + self.RESULT_EXTENSION

    def query_extra_data_for_test_task(self):
        # TODO refactor this method, should use query_next_data

        # TODO copied from luxrender task, do sth about it
        self.test_task_res_path = self.dir_manager.get_task_test_dir(self.header.task_id)
        if not os.path.exists(self.test_task_res_path):
            os.makedirs(self.test_task_res_path)

        subtask_id = self._get_new_subtask_id()

        # create subtask-specific data
        sbs = self.task_definition.subtask_data_size
        data = format((random.getrandbits(sbs)), '0{}b'.format(sbs))

        extra_data = {
            'data_file': os.path.basename(self.task_definition.shared_data_file),
            'subtask_data': data,
            'difficulty': self.task_definition.difficulty,
            'result_size': self.task_definition.result_size,
            'result_file': self._get_result_file_name(subtask_id),
            'subtask_data_size': sbs
        }

        return self._new_compute_task_def(subtask_id, extra_data)

    def _get_test_answer(self):
        return os.path.join(self.tmp_dir, "in" + self.RESULT_EXTENSION)


class DummyTaskBuilder(CoreTaskBuilder):
    TASK_CLASS = DummyTask
    DEFAULTS = DummyTaskDefaults  # TODO may be useful at some point...

    def build(self):
        task = super(DummyTaskBuilder, self).build()
        task.initialize(self.dir_manager)
        return task
