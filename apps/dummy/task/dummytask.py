import logging
import os
import random
from typing import Union

from apps.core.task.coretask import (CoreTask,
                                     CoreTaskBuilder,
                                     TaskTypeInfo)
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
    # TODO but many of them had to be copied from
    # TODO renderingtask, do something about it
    def __init__(self,
                 node_name: str,
                 task_definition: DummyTaskDefinition,
                 # TODO change that when TaskHeader will be updated
                 owner_address="",
                 owner_port=0,
                 owner_key_id="",
                 **kwargs
                 ):

        # TODO check what's going on here? why the test is putting environment in here? (docker-dummy-tst-task.json)
        if "environment" in kwargs and kwargs["environment"]:
            environment = kwargs["environment"]
        else:
            environment = self.ENVIRONMENT_CLASS()

        self.main_program_file = environment.main_program_file
        try:
            with open(self.main_program_file, "r") as src_file:
                src_code = src_file.read()
        except IOError as err:
            logger.warning("Wrong main program file: {}".format(err))
            src_code = ""

        super(DummyTask, self).__init__(
            src_code=src_code,
            task_definition=task_definition,
            node_name=node_name,
            owner_address=owner_address,
            owner_port=owner_port,
            owner_key_id=owner_key_id,
            environment=environment.get_id(),
            resource_size=task_definition.shared_data_size
        )

        # TODO implemented at renderingtask lvl, but used
        # TODO on at coretask lvl
        # It is also needed for test, where I have to manually copy files
        # but idk if will be needed in real setting
        # INFO it is needed for query_new_data, used in function get_resources
        # IMPORTANT it has to be AFTER the super()
        self.task_resources = set(filter(os.path.isfile, task_definition.resources))

        # TODO very ugly, refactor
        # IMPORTANT it has to be AFTER the super()
        self.root_path = kwargs["root_path"]

        # TODO abstract away
        self.verificator.result_size = self.task_definition.result_size
        self.verificator.difficulty = self.task_definition.difficulty
        self.verificator.shared_data_file = \
            self.task_definition.shared_data_file
        self.verificator.result_size = self.task_definition.result_size
        self.dir_manager = DirManager(self.root_path)

    def short_extra_data_repr(self, perf_index=None):
        return "dummy task " + self.header.task_id

    def query_extra_data(self,
                         perf_index: float,
                         num_cores: int = 1,
                         node_id: str = None,
                         node_name: str = None
                         ) -> Task.ExtraData:
        """Returns data for the next subtask.
        :param int perf_index:
        :param int num_cores:
        :param str | None node_id:
        :param str | None node_name:
        :rtype: ComputeTaskDef"""

        # create new subtask_id
        subtask_id = self._get_new_subtask_id()

        # TODO copied from luxrender, do sth about that
        # TODO it's generic, should be in the coretask
        # verdict = self._accept_client(node_id)
        # if verdict != AcceptClientVerdict.ACCEPTED:
        #
        #     should_wait = verdict == AcceptClientVerdict.SHOULD_WAIT
        #     if should_wait:
        #         logger.warning("Waiting for results from {}"
        #                        .format(node_name))
        #     else:
        #         logger.warning("Client {} banned from this task"
        #                        .format(node_name))
        #
        #     return self.ExtraData(should_wait=should_wait)
        #
        # if self.get_progress == 1.0:
        #     logger.error("Task already computed")
        #     return self.ExtraData()

        # create subtask-specific data, 4 bits go for one char (hex digit)
        data = str(random.getrandbits(self.task_definition.subtask_data_size * 4))
        shared_data_file_base = os.path.basename(self.task_definition.shared_data_file)

        extra_data = {
            'data_file': shared_data_file_base,
            'subtask_data': data,
            'difficulty': self.task_definition.difficulty,
            'result_size': self.task_definition.result_size,
            'result_file': self._get_result_file_name(subtask_id)
        }

        ctd = self._new_compute_task_def(subtask_id, extra_data, perf_index)

        self.subtasks_given[subtask_id] = extra_data
        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.starting
        self.subtasks_given[subtask_id]['perf'] = perf_index
        self.subtasks_given[subtask_id]['node_id'] = node_id

        return self.ExtraData(ctd=ctd)

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

        # create subtask-specific data, 4 bits go for one char (hex digit)
        data = random.getrandbits(self.task_definition.subtask_data_size * 4)

        extra_data = {
            'data_file': os.path.basename(self.task_definition.shared_data_file),
            'subtask_data': data,
            'difficulty': self.task_definition.difficulty,
            'result_size': self.task_definition.result_size,
            'result_file': self._get_result_file_name(subtask_id)
        }

        # perf_index for test_task was set to 0 in luxrendertask
        perf_index = 0.0  # TODO how to calculate perf_index for local computer?

        return self._new_compute_task_def(subtask_id, extra_data, perf_index)

    # TODO copied from renderingtask, do something about it
    def _new_compute_task_def(self,
                              subtask_id: str,
                              extra_data,
                              perf_index: float
                              ):
        ctd = ComputeTaskDef()
        ctd.task_id = self.header.task_id
        ctd.subtask_id = subtask_id
        ctd.extra_data = extra_data
        ctd.task_owner = self.header.task_owner
        ctd.short_description = self.short_extra_data_repr(perf_index)
        ctd.src_code = self.src_code
        ctd.performance = perf_index
        ctd.docker_images = self.header.docker_images
        ctd.environment = self.header.environment
        ctd.deadline = timeout_to_deadline(self.header.subtask_timeout)

        return ctd

    def _get_test_answer(self):
        return os.path.join(self.tmp_dir, "in" + self.RESULT_EXTENSION)


class DummyTaskBuilder(CoreTaskBuilder):
    TASK_CLASS = DummyTask
    DEFAULTS = DummyTaskDefaults  # TODO may be useful at some point...

    def build(self):
        task = super(DummyTaskBuilder, self).build()
        task.initialize(self.dir_manager)
        return task

    def get_task_kwargs(self, **kwargs):
        kwargs = super(DummyTaskBuilder, self).get_task_kwargs(**kwargs)
        kwargs["root_path"] = self.root_path
        return kwargs
