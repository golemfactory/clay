import logging
import os
import random
from typing import Dict

import enforce

from apps.core.task import coretask
from apps.core.task.coretask import (CoreTask,
                                     CoreTaskBuilder,
                                     CoreTaskTypeInfo)
from apps.dummy.dummyenvironment import DummyTaskEnvironment
from apps.dummy.task.dummytaskstate import DummyTaskDefaults, DummyTaskOptions
from apps.dummy.task.dummytaskstate import DummyTaskDefinition
from apps.dummy.task.verificator import DummyTaskVerificator
from golem.task.taskbase import ComputeTaskDef, Task
from golem.task.taskstate import SubtaskStatus

logger = logging.getLogger("apps.dummy")


@enforce.runtime_validation(group="dummy")
class DummyTaskTypeInfo(CoreTaskTypeInfo):
    def __init__(self, dialog, customizer):
        super().__init__(
            "Dummy",
            DummyTaskDefinition,
            DummyTaskDefaults(),
            DummyTaskOptions,
            DummyTaskBuilder,
            dialog,
            customizer
        )


@enforce.runtime_validation(group="dummy")
class DummyTask(CoreTask):
    ENVIRONMENT_CLASS = DummyTaskEnvironment
    VERIFICATOR_CLASS = DummyTaskVerificator

    RESULT_EXT = ".result"

    def __init__(self,
                 total_tasks: int,
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
            root_path=root_path,
            total_tasks=total_tasks
        )

        ver_opts = self.verificator.verification_options
        ver_opts["difficulty"] = self.task_definition.options.difficulty
        ver_opts["shared_data_files"] = self.task_definition.shared_data_files
        ver_opts["result_size"] = self.task_definition.result_size
        ver_opts["result_extension"] = self.RESULT_EXT

    def short_extra_data_repr(self, extra_data):
        return "Dummytask extra_data: {}".format(extra_data)

    def __extra_data(self, perf_index=0.0) -> ComputeTaskDef:
        subtask_id = self.__get_new_subtask_id()

        sbs = self.task_definition.options.subtask_data_size
        # create subtask-specific data, 4 bits go for one hex digit
        data = "{:128x}".format(random.getrandbits(sbs * 4))

        shared_data_files_base = [os.path.basename(x) for x in
                                  self.task_definition.shared_data_files]

        extra_data = {
            "data_files": shared_data_files_base,
            "subtask_data": data,
            "difficulty": self.task_definition.options.difficulty,
            "result_size": self.task_definition.result_size,
            "result_file": self.__get_result_file_name(subtask_id),
            "subtask_data_size": sbs,
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
        ctd = self.__extra_data(perf_index)
        sid = ctd.subtask_id

        self.subtasks_given[sid] = ctd.extra_data
        self.subtasks_given[sid]["status"] = SubtaskStatus.starting
        self.subtasks_given[sid]["perf"] = perf_index
        self.subtasks_given[sid]["node_id"] = node_id

        return self.ExtraData(ctd=ctd)

    # FIXME quite tricky to know that this method should be overwritten
    def accept_results(self, subtask_id, result_files):
        # TODO maybe move it to the base method
        if self.subtasks_given[subtask_id]["status"] == SubtaskStatus.finished:
            raise Exception("Subtask {} already accepted".format(subtask_id))

        super().accept_results(subtask_id, result_files)
        self.counting_nodes[
            self.subtasks_given[subtask_id]['node_id']
        ].accept()
        self.num_tasks_received += 1

    def __get_new_subtask_id(self) -> str:
        return "{:32x}".format(random.getrandbits(128))

    def __get_result_file_name(self, subtask_id: str) -> str:
        return "{}{}{}".format(self.task_definition.out_file_basename,
                               subtask_id[0:6],
                               self.RESULT_EXT)

    def query_extra_data_for_test_task(self) -> ComputeTaskDef:
        exd = self.__extra_data()
        size = self.task_definition.options.subtask_data_size
        char = self.__get_testing_char()
        exd.extra_data["subtask_data"] = char * size
        return exd

    def __get_testing_char(self):
        return "a"

    # Temporary testing for communications
    # def react_to_message(self, subtask_id: str, data: Dict):
    #     if "content" in data:
    #         return {"content": {"got_messages": "a" + data["got_messages"]}}
    #     else:
    #         return {"content": {"got_messages": "bbbb"}}


class DummyTaskBuilder(CoreTaskBuilder):
    TASK_CLASS = DummyTask

    @classmethod
    def build_dictionary(cls, definition: DummyTaskDefinition):
        dictionary = super().build_dictionary(definition)
        opts = dictionary['options']

        opts["subtask_data_size"] = int(definition.options.subtask_data_size)
        opts["difficulty"] = int(definition.options.difficulty)

        return dictionary

    @classmethod
    def build_full_definition(cls, task_type: DummyTaskTypeInfo, dictionary):
        # dictionary comes from GUI
        opts = dictionary["options"]

        definition = super().build_full_definition(task_type, dictionary)

        sbs = opts.get("subtask_data_size",
                       definition.options.subtask_data_size)
        difficulty = opts.get("difficulty",
                              definition.options.difficulty)

        # TODO uncomment that when GUI will be fixed
        # if not isinstance(sbs, int):
        #     raise TypeError("Subtask data size should be int")
        # if not isinstance(difficulty, int):
        #     raise TypeError("Difficulty should be int")
        sbs = int(sbs)
        difficulty = int(difficulty)

        if sbs <= 0:
            raise Exception("Subtask data size should be greater than 0")
        if difficulty < 0:
            raise Exception("Difficulty should be greater than 0")
        if difficulty >= 16 ** 8:
            raise Exception("Difficulty should be < {}".format(16 ** 8))

        definition.options.difficulty = difficulty
        definition.options.subtask_data_size = sbs

        return definition


# comment that line to enable type checking
enforce.config({'groups': {'set': {'dummy': False}}})
