import copy
import json
import logging
import os
import random
from collections import OrderedDict
from typing import Dict, Tuple, Type
from unittest.mock import Mock

import enforce

from apps.core.task import coretask
from apps.core.task.coretask import (CoreTask,
                                     CoreTaskBuilder,
                                     CoreTaskTypeInfo)
from apps.mlpoc.mlpocenvironment import MLPOCTorchEnvironment, \
    MLPOCSpearmintEnvironment
# from apps.mlpoc.resources.code_pytorch.impl.batchmanager import IrisBatchManager
from apps.mlpoc.resources.code_pytorch.impl.box import CountingBlackBox, BlackBox
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


# TODO remove that when really batch_manager will be available to be imported
class MockIrisBatchManager():
    def __init__(self, data_files):
        pass

    def get_order_of_batches(self, *args, **kwargs):
        return list(range(100))


# TODO refactor it to inherit from DummyTask
# @enforce.runtime_validation(group="mlpoc")
class MLPOCTask(CoreTask):
    ENVIRONMENT_CLASS = MLPOCTorchEnvironment
    VERIFICATOR_CLASS = MLPOCTaskVerificator

    SPEARMINT_ENV = MLPOCSpearmintEnvironment
    SPEARMINT_EXP_DIR = "work/experiment"
    SPEARMINT_SIGNAL_FILE = "x.signal"
    RESULT_EXT = ".score"
    BLACK_BOX = CountingBlackBox  #  type: Type[BlackBox]
    BATCH_MANAGER = MockIrisBatchManager  # type: Type[BatchManager]
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
        ver_opts["no_verification"] = False
        ver_opts["data_place"] = task_definition.data_place
        ver_opts["code_place"] = task_definition.code_place
        ver_opts["result_extension"] = self.RESULT_EXT

    def initialize(self, dir_manager):
        super().initialize(dir_manager)
        self.spearmint_path = dir_manager.get_task_temporary_dir(self.task_definition.task_id)
        self.local_spearmint = self.run_spearmint_in_background(self.spearmint_path)

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
        ctd.extra_data["EXPERIMENT_DIR"] = "/golem/" + self.SPEARMINT_EXP_DIR  # TODO change that, take "/golem/work" from DockerTaskThread
        ctd.extra_data["SIGNAL_FILE"] = "/golem/work/" + self.SPEARMINT_SIGNAL_FILE  # TODO change that, as ^
        ctd.extra_data["SIMULTANEOUS_UPDATES_NUM"] = 1
        ctd.extra_data["EVENT_LOOP_SLEEP"] = 0.5
        return ctd

    def __send_signal_to_spearmint(self):
        spearmint_utils.generate_new_suggestions(
            os.path.join(self.spearmint_path,
                         "work",
                         self.SPEARMINT_SIGNAL_FILE))

    def run_spearmint_in_background(self, tmp_path):
        local_spearmint = LocalComputer(None,  # we don't use task at all
                                        os.path.join(self.spearmint_path),  # Root path is used to store resourecs (DirManager is constructed from root_path)
                                        lambda *_: self.__restart_spearmint_pos(),
                                        lambda *_: self.__restart_spearmint_neg(),
                                        lambda: self.__spearmint_ctd(),
                                        use_task_resources=False,
                                        additional_resources=None,
                                        tmp_dir=self.spearmint_path)
        self.experiment_dir = os.path.join(tmp_path, self.SPEARMINT_EXP_DIR)
        os.makedirs(self.experiment_dir)  # experiment dir has to be AFTER local_spearmint, since it destroys LocalComputer.tmp_dir
        spearmint_utils.create_conf(self.experiment_dir)
        local_spearmint.run()
        self.__send_signal_to_spearmint()
        return local_spearmint

    def __restart_spearmint_pos(self):
        raise Exception("Spearmint docker was restarted positively. WRONG!")

    def __restart_spearmint_neg(self):
        raise Exception("Spearmint docker was restarted negatively. WRONG!")

    def short_extra_data_repr(self, extra_data):
        return "MLPOC extra_data: {}".format(extra_data)

    def __get_next_network_config(self):
        # here happens magic with spearmint in localcomputer
        # using spearmint_utils methods

        hidden_size = int(spearmint_utils.get_next_configuration(self.experiment_dir)[0])

        # order of these is important! that's why there's no dict here
        # (no OrderedDict, because these params will be saved to json)
        return [("HIDDEN_SIZE", hidden_size),
                ("NUM_EPOCHS", self.task_definition.options.number_of_epochs),
                ("STEPS_PER_EPOCH", self.task_definition.options.steps_per_epoch)]

    def _extra_data(self, perf_index=0.0) -> Tuple[BLACK_BOX, BATCH_MANAGER, ComputeTaskDef]:
        subtask_id = self.__get_new_subtask_id()
        black_box = self.BLACK_BOX(
            self.task_definition.options.probability_of_save,
            self.task_definition.options.number_of_epochs
        )
        batch_manager = self.BATCH_MANAGER(self.task_definition.shared_data_files)

        network_configuration = self.__get_next_network_config()

        shared_data_files_base = [os.path.basename(x) for x in
                                  self.task_definition.shared_data_files]

        extra_data = {
            "data_files": shared_data_files_base,
            "network_configuration": network_configuration,
            "order_of_batches": batch_manager.get_order_of_batches(),
            "RESULT_EXT": self.RESULT_EXT
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

        logger.warning("New task is being deployed")

        black_box, batch_manager, ctd = self._extra_data(perf_index)
        sid = ctd.subtask_id

        # TODO maybe save batch_manager and black_box somewhere else?
        # as the ctd.extra_data is modified in-place, and then saved/stored/send
        # somewhere, black_box and batch_manager don't survive serialization
        # (at least now, when they are Mocks)
        # they are available to verificator, since it has access to subtasks_given
        # array
        self.subtasks_given[sid] = copy.deepcopy(ctd.extra_data)
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

        score_file = [f for f in result_files if ".score" in f][0]
        self.__update_spearmint_state(score_file)
        self.__send_signal_to_spearmint()
        logger.warning("Subtask finished")

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
            res = json.load(f)  # TODO check if it doesn't pose any security threat

        # structure of the score file: {score: list_of_hyperparams}
        # where list_of_hyperparams = [(name_of_param, param_value)]
        score, hyperparameters = list(res.items())[0]

        # TODO temporary hack, because for now only one param is used
        hyperparameters = [str(v) for k, v in hyperparameters if k == "HIDDEN_SIZE"]

        assert isinstance(hyperparameters, list)
        assert isinstance(float(score), float)  # not so dumb as it seems - just checking if score can be mapped to float

        spearmint_utils.run_one_evaluation(
            self.experiment_dir,
            params={score: hyperparameters}
        )


    # TODO set the structure of message_data, as in TaskThread.check_for_new_messages TODO
    def react_to_message(self, subtask_id: str, data: Dict):
        # save answer to blackbox and get a response
        assert data["content"]["message_type"] == "MLPOCBlackBoxAskMessage"
        box = self.subtasks_given[subtask_id]["black_box"]  # type: BlackBox

        answer = box.decide(hash=data["content"]["params_hash"],
                            epoch_num=data["content"]["number_of_epoch"])
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
        probability_of_save = opts.get("probability_of_save",
                                    definition.options.probability_of_save)
        # TODO uncomment that when GUI will be fixed
        # if not isinstance(steps_per_epoch, int):
        #     raise TypeError("Num of steps per epoch should be int")
        # if not isinstance(number_of_epochs, int):
        #     raise TypeError("Num of epochs should be int")
        steps_per_epoch = int(steps_per_epoch)
        number_of_epochs = int(number_of_epochs)
        probability_of_save = float(probability_of_save)
        if steps_per_epoch <= 0:
            raise Exception("Num of steps per epoch should be greater than 0")
        if number_of_epochs < 0:
            raise Exception("Num of epochs should be greater than 0")

        definition.options.number_of_epochs = number_of_epochs
        definition.options.steps_per_epoch = steps_per_epoch
        definition.options.probability_of_save = probability_of_save

        return definition
        # also, a second file, which will be a configuration file for spearmint


# comment that line to enable type checking
enforce.config({'groups': {'set': {'mlpoc': True}}})
