from copy import copy
import logging
import os
import random

import enforce

from golem_messages.message import ComputeTaskDef

from apps.core.task import coretask
from apps.core.task.coretask import (CoreTask,
                                     CoreTaskBuilder,
                                     CoreTaskTypeInfo)
from apps.dummy.dummyenvironment import DummyTaskEnvironment
from apps.dummy.task.dummytaskstate import DummyTaskDefaults, DummyTaskOptions
from apps.dummy.task.dummytaskstate import DummyTaskDefinition
from apps.dummy.task.verifier import DummyTaskVerifier
from golem.task.taskbase import Task
from golem.task.taskstate import SubtaskStatus

logger = logging.getLogger("apps.dummy")


class DummyTaskTypeInfo(CoreTaskTypeInfo):
    def __init__(self):
        super().__init__(
            "Dummy",
            DummyTaskDefinition,
            DummyTaskDefaults(),
            DummyTaskOptions,
            DummyTaskBuilder
        )


@enforce.runtime_validation(group="dummy")
class DummyTask(CoreTask):
    ENVIRONMENT_CLASS = DummyTaskEnvironment
    VERIFIER_CLASS = DummyTaskVerifier

    RESULT_EXT = ".result"
    TESTING_CHAR = "a"

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

    def short_extra_data_repr(self, extra_data):
        return "Dummytask extra_data: {}".format(extra_data)

    def _extra_data(self, perf_index=0.0) -> ComputeTaskDef:
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
        logger.debug("Query extra data on dummytask")

        ctd = self._extra_data(perf_index)
        sid = ctd['subtask_id']

        self.subtasks_given[sid] = copy(ctd['extra_data'])
        self.subtasks_given[sid]["status"] = SubtaskStatus.starting
        self.subtasks_given[sid]["perf"] = perf_index
        self.subtasks_given[sid]["node_id"] = node_id
        self.subtasks_given[sid]["result_extension"] = self.RESULT_EXT
        self.subtasks_given[sid]["shared_data_files"] = \
            self.task_definition.shared_data_files
        self.subtasks_given[sid]["subtask_id"] = sid

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
        exd = self._extra_data()
        size = self.task_definition.options.subtask_data_size
        char = self.TESTING_CHAR
        exd['extra_data']["subtask_data"] = char * size
        return exd


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
        sbs = int(sbs)
        # difficulty comes in hex string from GUI
        if isinstance(difficulty, str):
            difficulty = int(difficulty, 16)

        if sbs <= 0:
            raise Exception("Subtask data size should be greater than 0")
        if difficulty < 0:
            raise Exception("Difficulty should be greater than 0")

        definition.options.difficulty = difficulty
        definition.options.subtask_data_size = sbs

        return definition


class DummyTaskMod(DummyTask):
    def query_extra_data(self, *args, **kwargs):
        ctd = self.query_extra_data_for_test_task()
        return self.ExtraData(ctd=ctd)


class DummyTaskBuilderMod(DummyTaskBuilder):
    TASK_CLASS = DummyTaskMod


# comment that line to enable type checking
enforce.config({'groups': {'set': {'dummy': False}}})
