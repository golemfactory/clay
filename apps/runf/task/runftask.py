import logging
import os
import random
import shutil
from copy import copy
from typing import Optional, Dict

import enforce
from golem_messages.message import ComputeTaskDef

from apps.core.task import coretask
from apps.core.task.coretask import (CoreTask,
                                     CoreTaskBuilder,
                                     CoreTaskTypeInfo)
from apps.runf.runfenvironment import RunFEnvironment
from apps.runf.task import queue_utils
from apps.runf.task.runftaskstate import RunFDefaults, RunFOptions
from apps.runf.task.runftaskstate import RunFDefinition
from apps.runf.task.verifier import RunFVerifier
from golem.core.common import timeout_to_deadline
from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import Task
from golem.task.taskstate import SubtaskStatus

logger = logging.getLogger("apps.runf")


class RunFTypeInfo(CoreTaskTypeInfo):
    def __init__(self):
        super().__init__(
            "Dummy",
            RunFDefinition,
            RunFDefaults(),
            RunFOptions,
            RunFBuilder
        )


@enforce.runtime_validation(group="runf")
class RunF(CoreTask):
    ENVIRONMENT_CLASS = RunFEnvironment
    VERIFIER_CLASS = RunFVerifier
    LOCALCOMPUTER_ENV = RunFEnvironment

    RESULT_EXT = ".result"

    def __init__(self,
                 total_tasks: int,
                 task_definition: RunFDefinition,
                 root_path=None,
                 owner=None):
        super().__init__(
            owner=owner,
            task_definition=task_definition,
            root_path=root_path,
            total_tasks=total_tasks
        )

    def initialize(self, dir_manager):
        super().initialize(dir_manager)
        # FIXME super ugly, the line length limit should be increased
        self.local_comp_path = \
            dir_manager.get_task_temporary_dir(self.task_definition.task_id)
        self.local_computer = \
            self.prepare_localcomputer(self.local_comp_path)
        self.local_computer.run()

    def __local_ctd(self) -> ComputeTaskDef:
        """
        Returns parameters for spearmint task run.
        In particular, extra_data structure containing:
        - EXPERIMENT_DIR - dir with config.json (and then results.dat)
        - SIGNAL_DIR - dir in which we add signal files
                       when requesting an update of results.dat
        - EVENT_LOOP_SLEEP - that's how long time.sleep()
                             waits in each repetition of event loop
        :return: ComputeTaskDef with extra_data specified above
        """
        env = self.LOCALCOMPUTER_ENV()
        ctd = ComputeTaskDef()
        ctd.environment = env.ENV_ID
        ctd.docker_images = env.docker_images
        ctd.src_code = env.get_source_code()

        # we should set not working directory, but LocalComputer.temp_dir
        ctd.working_directory = ""

        # LocalComputer has to run indefinitely
        ctd.deadline = timeout_to_deadline(self.INFTY)

        # TODO change that, take "/golem" from DockerTaskThread
        ctd["extra_data"]["SIGNAL_DIR"] = "/golem/" + self.SPEARMINT_SIGNAL_DIR
        ctd["extra_data"]["SIGNAL_DIR"] = "/golem/" + self.SPEARMINT_SIGNAL_DIR

        ctd["extra_data"]["EVENT_LOOP_SLEEP"] = 0.5
        return ctd

    def prepare_localcomputer(self, local_comp_path):
        local_computer = LocalComputer(
            root_path=local_comp_path,  # root_path/temp is used to store resources
            # inside LocalComputer, because DirManager
            # is constructed from root_path
            success_callback=lambda *_: self.__spearmint_exit("=0"),
            error_callback=lambda *_: self.__spearmint_exit("!=0"),
            get_compute_task_def=self.__local_ctd,
            additional_resources=None,
        )
        self.experiment_dir = os.path.join(local_comp_path,
                                           self.SPEARMINT_EXP_DIR)
        self.signal_dir = os.path.join(local_comp_path,
                                       self.SPEARMINT_SIGNAL_DIR)

        # experiment dir has to be created AFTER local_computer
        # LocalComputer.tmp_dir destroys it
        os.makedirs(self.experiment_dir)

        # signal dir has to be created AFTER local_computer
        # LocalComputer.tmp_dir destroys it
        os.makedirs(self.signal_dir)

        queue_utils.create_conf(self.experiment_dir)
        return local_computer

    def __update_queue_state(self, subtask_id):
        """
        Inform the queue running in localcomputer that the subtask was finished
        and it can be removed from queue
        :param subtask_id
        :return:
        """
        queue_utils.subtask_finished(
            self.experiment_dir,
            subtask_id
        )

    def __spearmint_exit(self, label):
        # There was some problem with spearmint LocalComputer and it exited
        # so we lost all progress on the task - so let's panic!
        raise Exception("Spearmint docker was restarted "
                        "with exit code {}. WRONG!".format(label))

    def short_extra_data_repr(self, extra_data):
        return "Runf extra_data: {}".format(extra_data)

    def __trigger_queue_update(self):
        some_random_name = "{:32x}".format(random.getrandbits(128))
        queue_utils.wait_for_new_suggestions(
            os.path.join(self.signal_dir, some_random_name)
        )

    def __get_next_func_args(self):
        # here happens magic with queue in localcomputer
        self.__trigger_queue_update()
        args, kwargs = queue_utils.get_next_configuration(self.queue_dir)
        return args, kwargs

    def _extra_data(self, perf_index=0.0) -> ComputeTaskDef:
        subtask_id = self.__get_new_subtask_id()
        args, kwargs = self.__get_next_func_args()

        extra_data = {
            "args": args,
            "kwargs": kwargs,
            "main_file": self.task_definition.options.main_file,
            "RESULT_EXT": self.RESULT_EXT
        }

        return self._new_compute_task_def(subtask_id,
                                          extra_data,
                                          perf_index=perf_index)

    @coretask.accepting
    def query_extra_data(self,
                         perf_index: float,
                         num_cores: int = 1,
                         node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        logger.debug("Query extra data on runftask")

        ctd = self._extra_data(perf_index)
        sid = ctd['subtask_id']

        # TODO these should all be in CoreTask
        self.subtasks_given[sid] = copy(ctd['extra_data'])
        self.subtasks_given[sid]["status"] = SubtaskStatus.starting
        self.subtasks_given[sid]["perf"] = perf_index
        self.subtasks_given[sid]["node_id"] = node_id
        self.subtasks_given[sid]["result_extension"] = self.RESULT_EXT
        self.subtasks_given[sid]["shared_data_files"] = \
            self.task_definition.shared_data_files
        self.subtasks_given[sid]["subtask_id"] = sid

        return self.ExtraData(ctd=ctd)

    def __get_result_file_name(self, subtask_id: str) -> str:
        return "{}{}".format(subtask_id[0:6],
                             self.RESULT_EXT)

    def accept_results(self, subtask_id, result_files):
        super().accept_results(subtask_id, result_files)
        self.counting_nodes[
            self.subtasks_given[subtask_id]['node_id']
        ].accept()
        self.num_tasks_received += 1

        queue_id = self.sid_to_qid[subtask_id]
        self.__update_queue_state(queue_id)
        logger.info("Subtask finished")
        if self._is_final(queue_id):
            self._end_computation()

    def _end_computation(self):
        out_file = self.task_definition.options.output_dir
        logger.info("Copying final answer in to %s", out_file)
        results_dir = self.local_comp_path
        shutil.copy(results_dir, out_file)
        self.local_computer.end_comp()

    def query_extra_data_for_test_task(self) -> ComputeTaskDef:
        pass
        # exd = self._extra_data()
        # size = self.task_definition.options.subtask_data_size
        # char = self.TESTING_CHAR
        # exd['extra_data']["subtask_data"] = char * size
        # return exd

    def react_to_message(self, subtask_id: str, data: Dict):
        pass

class RunFBuilder(CoreTaskBuilder):
    TASK_CLASS = RunF

    @classmethod
    def build_dictionary(cls, definition: RunFDefinition):
        dictionary = super().build_dictionary(definition)
        opts = dictionary['options']

        opts["subtask_data_size"] = int(definition.options.subtask_data_size)
        opts["difficulty"] = int(definition.options.difficulty)

        return dictionary

    @classmethod
    def build_full_definition(cls, task_type: RunFTypeInfo, dictionary):
        # dictionary comes from GUI
        opts = dictionary["options"]

        definition = super().build_full_definition(task_type, dictionary)

        sbs = opts.get("subtask_data_size",
                       definition.options.subtask_data_size)
        difficulty = opts.get("difficulty",
                              definition.options.difficulty)

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


class RunFMod(RunF):
    def query_extra_data(self, *args, **kwargs):
        ctd = self.query_extra_data_for_test_task()
        return self.ExtraData(ctd=ctd)


class RunFBuilderMod(RunFBuilder):
    TASK_CLASS = RunFMod


# comment that line to enable type checking
enforce.config({'groups': {'set': {'runf': False}}})
