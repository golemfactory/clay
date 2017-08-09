import logging
import os
import random
import uuid
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

        ver_opts = self.verificator.verification_options
        ver_opts["result_size"] = self.task_definition.options.result_size
        ver_opts["difficulty"] = self.task_definition.options.difficulty
        ver_opts["shared_data_files"] = self.task_definition.shared_data_files
        ver_opts["result_size"] = self.task_definition.options.result_size

        # self.dir_manager = DirManager(self.root_path) # is it needed?

    def short_extra_data_repr(self, extra_data):
        return "Dummytask extra_data: {}".format(extra_data)

    def _extra_data(self, perf_index=0.0):
        subtask_id = self.__get_new_subtask_id()

        # create subtask-specific data, 4 bits go for one char (hex digit)
        sbs = self.task_definition.options.subtask_data_size
        data = format((random.getrandbits(sbs)), '0{}b'.format(sbs))
        # now data is in the format "010010111010011...001"

        shared_data_files_base = [os.path.basename(x) for x in
                                  self.task_definition.shared_data_files]

        extra_data = {
            'data_files': shared_data_files_base,
            'subtask_data': data,
            'difficulty': self.task_definition.options.difficulty,
            'result_size': self.task_definition.options.result_size,
            'result_file': self.__get_result_file_name(subtask_id),
            'subtask_data_size': sbs,
            'code_dir': self.task_definition.code_dir
        }

        return self._new_compute_task_def(subtask_id,
                                          extra_data,
                                          perf_index=perf_index)

    @coretask.accepting
    def query_extra_data(self,
                         perf_index: float,
                         num_cores=1,
                         node_id: str = None,
                         node_name: str = None) -> Task.ExtraData:
        ctd = self._extra_data(perf_index)
        sid = ctd.subtask_id

        self.subtasks_given[sid] = ctd.extra_data
        self.subtasks_given[sid]['status'] = SubtaskStatus.starting
        self.subtasks_given[sid]['perf'] = perf_index
        self.subtasks_given[sid]['node_id'] = node_id

        return self.ExtraData(ctd=ctd)

    # FIXME quite tricky to know that I should override this method
    # it isn't really needed, i think
    # but it is useful from educational point of view
    def accept_results(self, subtask_id, result_files):
        super().accept_results(subtask_id, result_files)
        self.num_tasks_received += 1

    def __get_new_subtask_id(self) -> str:
        return "{}".format(random.getrandbits(128))

    def __get_result_file_name(self, subtask_id: str) -> str:
        return "{}{}{}".format(self.task_definition.out_file_basename,
                               subtask_id[0:6],
                               self.RESULT_EXTENSION)

    def query_extra_data_for_test_task(self):
        return self._extra_data()

    # TODO why do I need that? (except for test)
    def _get_test_answer(self):
        return os.path.join(self.tmp_dir, "in" + self.RESULT_EXTENSION)


class DummyTaskBuilder(CoreTaskBuilder):
    TASK_CLASS = DummyTask
    DEFAULTS = DummyTaskDefaults  # TODO may be useful at some point...

    def get_task_kwargs(self, **kwargs):
        kwargs = super().get_task_kwargs(**kwargs)
        kwargs['subtask_data_size'] = self.task_definition.options.subtask_data_size
        kwargs['result_size'] = self.task_definition.options.result_size
        kwargs['difficulty'] = self.task_definition.options.difficulty
        return kwargs

    @classmethod
    def build_dictionary(cls, definition):
        dictionary = super().build_dictionary(definition)
        dictionary['options']['subtask_data_size'] = definition.options.subtask_data_size
        dictionary['options']['result_size'] = definition.options.result_size
        dictionary['options']['difficulty'] = definition.options.difficulty

        return dictionary

    @classmethod
    def build_full_definition(cls, task_type, dictionary):
        options = dictionary['options']

        definition = super().build_full_definition(task_type, dictionary)
        definition.options.subtask_data_size = options.get('subtask_data_size',
                                                 definition.options.subtask_data_size)
        definition.options.result_size = options.get('result_size',
                                                 definition.options.result_size)
        definition.options.difficulty = options.get('difficulty',
                                                 definition.options.difficulty)
        return definition
