import logging
import os
import random
from typing import Dict, Tuple

import enforce

from apps.core.task import coretask
from apps.core.task.coretask import (CoreTask,
                                     CoreTaskBuilder,
                                     CoreTaskTypeInfo)
from apps.mlpoc.mlpocenvironment import MLPOCTaskEnvironment
from apps.mlpoc.resources.code_dir.impl.batchmanager import IrisBatchManager
from apps.mlpoc.resources.code_dir.impl.box import CountingBlackBox
from apps.mlpoc.resources.code_dir.messages import MLPOCBlackBoxAnswerMessage
from apps.mlpoc.task.mlpoctaskstate import MLPOCTaskDefaults, MLPOCTaskOptions
from apps.mlpoc.task.mlpoctaskstate import MLPOCTaskDefinition
from apps.mlpoc.task.verificator import MLPOCTaskVerificator
from golem.task.taskbase import ComputeTaskDef, Task
from golem.task.taskstate import SubtaskStatus

logger = logging.getLogger("apps.mlpoc")


@enforce.runtime_validation(group="mlpoc")
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
@enforce.runtime_validation(group="mlpoc")
class MLPOCTask(CoreTask):
    ENVIRONMENT_CLASS = MLPOCTaskEnvironment
    VERIFICATOR_CLASS = MLPOCTaskVerificator

    RESULT_EXT = ".result"
    BLACK_BOX = CountingBlackBox  # black box class, not instance
    BATCH_MANAGER = IrisBatchManager  # batch manager class, not instace

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
        ver_opts["no_verification"] = True
        # ver_opts["shared_data_files"] = self.task_definition.shared_data_files
        # ver_opts["result_extension"] = self.RESULT_EXT

    def short_extra_data_repr(self, extra_data):
        return "MLPOC extra_data: {}".format(extra_data)

    def __get_next_network_config(self):
        return {"HIDDEN_SIZE": 10,
                "INPUT_SIZE": 10,
                "NUM_CLASSES": 3,
                "NUM_EPOCHS": self.task_definition.options.number_of_epochs,
                "STEPS_PER_EPOCH": self.task_definition.options.steps_per_epoch
                }

    def _extra_data(self, perf_index=0.0) -> Tuple[
        BLACK_BOX, BATCH_MANAGER, ComputeTaskDef]:
        subtask_id = self.__get_new_subtask_id()

        black_box = self.BLACK_BOX(
            self.task_definition.options.probability_of_save,
            self.task_definition.options.number_of_epochs
        )
        batch_manager = self.BATCH_MANAGER(self.shared_data_files)

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
        self.__update_spearmint_state(result_files)

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

    def __update_spearmint_state(self, result_files):
        # TODO here happens magic with local spearmint dockerthread
        # adding new params to spearmint file and running it
        pass

    def react_to_message(self, subtask_id: str, data: Dict):
        # save answer to blackbox and get a response
        assert data["message_type"] == "MLPOCBlackBoxAskMessage"
        answer = self.black_box[subtask_id].save(
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
