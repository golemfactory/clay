import json
import logging
import os
import random
from typing import Dict, Tuple
from unittest.mock import Mock

import enforce

from apps.core.task import coretask
from apps.core.task.coretask import (CoreTask,
                                     CoreTaskBuilder,
                                     CoreTaskTypeInfo)
from apps.mlpoc.mlpocenvironment import MLPOCTorchEnvironment, \
    MLPOCSpearmintEnvironment
# from apps.mlpoc.resources.code_pytorch.impl.batchmanager import IrisBatchManager
# from apps.mlpoc.resources.code_pytorch.impl.box import CountingBlackBox
from apps.mlpoc.resources.code_pytorch.messages import \
    MLPOCBlackBoxAnswerMessage
from apps.mlpoc.task import spearmint_utils
from apps.mlpoc.task.mlpoctaskstate import MLPOCTaskDefaults, MLPOCTaskOptions
from apps.mlpoc.task.mlpoctaskstate import MLPOCTaskDefinition
from apps.mlpoc.task.verificator import MLPOCTaskVerificator
from golem.core.common import timeout_to_deadline
from golem.resource.dirmanager import DirManager
from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import ComputeTaskDef, Task
from golem.task.taskstate import SubtaskStatus

logger = logging.getLogger("apps.mlpoc")


# @enforce.runtime_validation(group="mlpoc")
class MLPOCTaskTypeInfo(CoreTaskTypeInfo):
    def __init__(self, dialog, customizer):
        super().__init__(
            "MLPOC",
            MLPOCTaskDefinition,
            MLPOCTaskDefaults(),
            MLPOCTaskOptions,
            MLPOCTaskBuilder,
            dialog,
            customizer
        )


# TODO refactor it to inherit from DummyTask
# @enforce.runtime_validation(group="mlpoc")
class MLPOCTask(CoreTask):
    ENVIRONMENT_CLASS = MLPOCTorchEnvironment
    VERIFICATOR_CLASS = MLPOCTaskVerificator

    SPEARMINT_ENV = MLPOCSpearmintEnvironment
    SPEARMINT_EXP_DIR = "work/experiment"
    SPEARMINT_SIGNAL_FILE = "work/x.signal"
    RESULT_EXT = ".result"
    BLACK_BOX = Mock # CountingBlackBox  # black box class, not instance
    BATCH_MANAGER = Mock # IrisBatchManager  # batch manager class, not instace
    INFTY = 10000000

    def __init__(self,
                 total_tasks: int,
                 node_name: str,
                 task_definition: MLPOCTaskDefinition,
                 root_path=None,
                 # TODO change that when TaskHeader will be updated
                 owner_address="",
                 owner_port=0,
                 owner_key_id=""
                 ):

        self.BATCH_MANAGER.get_order_of_batches = lambda *_: list(range(100)) # remove that when batchmanager will be real
        super().__init__(
            task_definition=task_definition,
            node_name=node_name,
            owner_address=owner_address,
            owner_port=owner_port,
            owner_key_id=owner_key_id,
            root_path=root_path,
            total_tasks=total_tasks
        )

        dm = DirManager(root_path)
        self.spearmint_path = dm.get_task_temporary_dir(task_definition.task_id)
        self.local_spearmint = self.run_spearmint_in_background(self.spearmint_path)

        ver_opts = self.verificator.verification_options
        ver_opts["no_verification"] = True
        # ver_opts["shared_data_files"] = self.task_definition.shared_data_files
        # ver_opts["result_extension"] = self.RESULT_EXT

    def __spearmint_ctd(self):
        env = self.SPEARMINT_ENV()
        src_code = env.get_source_code()
        ctd = ComputeTaskDef()
        ctd.environment = env.ENV_ID
        ctd.docker_images = env.docker_images
        ctd.src_code = src_code
        ctd.working_directory = ""  # we should set not working directory, but LocalComputer.temp_dir
        ctd.deadline = timeout_to_deadline(self.INFTY)

        # EXPERIMENT_DIR - dir with config.json
        # SIGNAL_FILE - file which signalizes the change in results.dat
        # SIMULTANEOUS_UPDATES_NUM - how many new suggestions should spearmint add every time?
        # EVENT_LOOP_SLEEP - that's how long time.sleep() waits in each repetition of event loop
        ctd.extra_data["EXPERIMENT_DIR"] = "/golem/work/" + self.SPEARMINT_EXP_DIR  # TODO change that, take "/golem/work" from DockerTaskThread
        ctd.extra_data["SIGNAL_FILE"] = "/golem/work/" + self.SPEARMINT_SIGNAL_FILE  # TODO change that, as ^
        ctd.extra_data["SIMULTANEOUS_UPDATES_NUM"] = 1
        ctd.extra_data["EVENT_LOOP_SLEEP"] = 0.5
        return ctd

    def run_spearmint_in_background(self, tmp_path):
        local_spearmint = LocalComputer(None,  # we don't use task at all
                                             "",  # os.path.join(self.spearmint_path),  # TODO i think it is not really needed
                                             lambda *_: self.__restart_spearmint_pos(),
                                             lambda *_: self.__restart_spearmint_neg(),
                                             lambda: self.__spearmint_ctd(),
                                             use_task_resources=False,
                                             additional_resources=None,
                                             tmp_dir=self.spearmint_path)
        experiment_dir = os.path.join(tmp_path, self.SPEARMINT_EXP_DIR)
        os.makedirs(experiment_dir) # experiment dir has to be AFTER local_spearmint, since it destroys LocalComputer.tmp_dir
        spearmint_utils.create_conf(experiment_dir)
        # local_spearmint.run()
        return local_spearmint

    def __restart_spearmint_pos(self):
        logger.warning("Spearmint docker was restarted positively. WRONG!")
        raise Exception("Spearmint docker was restarted positively. WRONG!")

    def __restart_spearmint_neg(self):
        logger.warning("Spearmint docker was restarted negatively. WRONG!")
        raise Exception("Spearmint docker was restarted negatively. WRONG!")

    def short_extra_data_repr(self, extra_data):
        return "MLPOC extra_data: {}".format(extra_data)

    def __get_next_network_config(self):
        # TODO here happens magic with spearmint in localcomputer
        # using spearmint_utils methods
        return {"HIDDEN_SIZE": 10,
                "NUM_EPOCHS": self.task_definition.options.number_of_epochs,
                "STEPS_PER_EPOCH": self.task_definition.options.steps_per_epoch
                }

    def _extra_data(self, perf_index=0.0) -> Tuple[BLACK_BOX, BATCH_MANAGER, ComputeTaskDef]:
        subtask_id = self.__get_new_subtask_id()

        black_box = self.BLACK_BOX(
            self.task_definition.options.probability_of_save,
            self.task_definition.options.number_of_epochs
        )
        batch_manager = self.BATCH_MANAGER(self.task_definition.shared_data_files)

        network_conf = self.__get_next_network_config()

        shared_data_files_base = [os.path.basename(x) for x in
                                  self.task_definition.shared_data_files]

        extra_data = {
            "data_files": shared_data_files_base,
            "network_configuration": network_conf,
            "order_of_batches": batch_manager.get_order_of_batches()
        }

        return (black_box,
                batch_manager,
                self._new_compute_task_def(subtask_id,
                                           extra_data,
                                           perf_index=perf_index))

    @coretask.accepting
    def query_extra_data(self,
                         perf_index: float,
                         num_cores=1,
                         node_id: str = None,
                         node_name: str = None) -> Task.ExtraData:
        black_box, batch_manager, ctd = self._extra_data(perf_index)
        sid = ctd.subtask_id

        self.subtasks_given[sid] = ctd.extra_data
        self.subtasks_given[sid]["status"] = SubtaskStatus.starting
        self.subtasks_given[sid]["perf"] = perf_index
        self.subtasks_given[sid]["node_id"] = node_id
        self.subtasks_given[sid]["black_box"] = black_box
        self.subtasks_given[sid]["batch_manager"] = batch_manager

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

        score_file = [f for f in result_files if ".score" in f]
        self.__update_spearmint_state(score_file)

    def __get_new_subtask_id(self) -> str:
        return "{:32x}".format(random.getrandbits(128))

    def __get_result_file_name(self, subtask_id: str) -> str:
        return "{}{}".format(subtask_id[0:6],
                             self.RESULT_EXT)

    def query_extra_data_for_test_task(self) -> ComputeTaskDef:
        black_box, batch_manager, exd = self._extra_data()
        self.test_black_box = black_box
        self.test_batch_manager = batch_manager
        return exd

    def __update_spearmint_state(self, score_file):
        with open(score_file, "r") as f:
            res = json.load(f)["score"]  # TODO check if it doesn't pose any security threat
        score = res["score"]  # overall score of the network with
        params = res["params"]  # the given parameters

    def react_to_message(self, subtask_id: str, data: Dict):
        # save answer to blackbox and get a response
        assert data["message_type"] == "MLPOCBlackBoxAskMessage"
        answer = self.subtasks_given[subtask_id]["black_box"].save(
            params_hash=data["params_hash"],
            number_of_epoch=data["number_of_epoch"])
        return MLPOCBlackBoxAnswerMessage.new_message(answer)


class MLPOCTaskBuilder(CoreTaskBuilder):
    TASK_CLASS = MLPOCTask

    # TODO build dictionary will specify the name of output variable column
    # and the indicator whenever variable is categorical or continous
    # or maybe I should do that by creating config file
    # with metadata about dataset and network configuration

    @classmethod
    def build_dictionary(cls, definition: MLPOCTaskDefinition):
        dictionary = super().build_dictionary(definition)
        opts = dictionary['options']

        opts["number_of_epochs"] = int(definition.options.number_of_epochs)
        opts["steps_per_epoch"] = int(definition.options.steps_per_epoch)

        return dictionary

    # TODO do the checking in some @enforce
    @classmethod
    def build_full_definition(cls, task_type: MLPOCTaskTypeInfo, dictionary):
        # dictionary comes from GUI
        opts = dictionary["options"]

        definition = super().build_full_definition(task_type, dictionary)

        steps_per_epoch = opts.get("steps_per_epoch",
                                   definition.options.steps_per_epoch)
        number_of_epochs = opts.get("number_of_epochs",
                                    definition.options.number_of_epochs)

        # TODO uncomment that when GUI will be fixed
        # if not isinstance(steps_per_epoch, int):
        #     raise TypeError("Num of steps per epoch should be int")
        # if not isinstance(number_of_epochs, int):
        #     raise TypeError("Num of epochs should be int")
        steps_per_epoch = int(steps_per_epoch)
        number_of_epochs = int(number_of_epochs)

        if steps_per_epoch <= 0:
            raise Exception("Num of steps per epoch should be greater than 0")
        if number_of_epochs < 0:
            raise Exception("Num of epochs should be greater than 0")

        definition.options.number_of_epochs = number_of_epochs
        definition.options.steps_per_epoch = steps_per_epoch

        return definition
        # also, a second file, which will be a configuration file for spearmint


# comment that line to enable type checking
enforce.config({'groups': {'set': {'mlpoc': False}}})
