import copy
import json
import logging
import os
import random
import shutil
from typing import Dict, Tuple, Type

import enforce

from apps.core.task import coretask
from apps.core.task.coretask import (CoreTask,
                                     CoreTaskBuilder,
                                     CoreTaskTypeInfo)
from apps.mlpoc.mlpocenvironment import (MLPOCTorchEnvironment,
                                         MLPOCSpearmintEnvironment)
from apps.mlpoc.resources.code_pytorch.impl.box import (CountingBlackBox,
                                                        BlackBox)
from apps.mlpoc.resources.code_pytorch.messages import \
    MLPOCBlackBoxAnswerMessage
from apps.mlpoc.task import spearmint_utils
from apps.mlpoc.task.mlpoctaskstate import MLPOCTaskDefaults, MLPOCTaskOptions
from apps.mlpoc.task.mlpoctaskstate import MLPOCTaskDefinition
from apps.mlpoc.task.verificator import MLPOCTaskVerificator
from golem.core.common import timeout_to_deadline
from golem.core.fileshelper import find_file_with_ext
from golem.task.localcomputer import LocalComputer
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
    ENVIRONMENT_CLASS = MLPOCTorchEnvironment
    VERIFICATOR_CLASS = MLPOCTaskVerificator

    SPEARMINT_ENV = MLPOCSpearmintEnvironment
    SPEARMINT_EXP_DIR = "work/experiment"
    SPEARMINT_SIGNAL_DIR = "work/signal"
    RESULT_EXT = ".score"
    BLACK_BOX = CountingBlackBox  # type: Type[BlackBox]
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
        ver_opts["input_data_file"] = task_definition.input_data_file

    def initialize(self, dir_manager):
        super().initialize(dir_manager)
        self.spearmint_path = dir_manager.get_task_temporary_dir(self.task_definition.task_id)
        self.local_spearmint = self.prepare_spearmint_localcomputer(self.spearmint_path)
        self.local_spearmint.run()

    def __spearmint_ctd(self) -> ComputeTaskDef:
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
        env = self.SPEARMINT_ENV()
        src_code = env.get_source_code()
        ctd = ComputeTaskDef()
        ctd.environment = env.ENV_ID
        ctd.docker_images = env.docker_images
        ctd.src_code = src_code

        # we should set not working directory, but LocalComputer.temp_dir
        ctd.working_directory = ""

        # spearmint LocalComputer has to run indefinitely
        ctd.deadline = timeout_to_deadline(self.INFTY)

        # TODO change that, take "/golem" from DockerTaskThread
        ctd.extra_data["EXPERIMENT_DIR"] = "/golem/" + self.SPEARMINT_EXP_DIR
        # TODO change that, same as above
        ctd.extra_data["SIGNAL_DIR"] = "/golem/" + self.SPEARMINT_SIGNAL_DIR
        ctd.extra_data["EVENT_LOOP_SLEEP"] = 0.5
        return ctd

    def __trigger_spearmint_update(self):
        some_random_name = "{:32x}".format(random.getrandbits(128))
        spearmint_utils.generate_new_suggestions(
            os.path.join(self.signal_dir, some_random_name))

    def prepare_spearmint_localcomputer(self, tmp_path):
        local_spearmint = LocalComputer(
            task=None,  # we don't use task at all
            root_path=tmp_path,  # root_path/temp is used to store resources
            # inside LocalComputer, because DirManager
            # is constructed from root_path
            success_callback=lambda *_: self.__spearmint_exit("=0"),
            error_callback=lambda *_: self.__spearmint_exit("!=0"),
            get_compute_task_def=lambda: self.__spearmint_ctd(),
            use_task_resources=False,
            additional_resources=None,
            tmp_dir=tmp_path
        )
        self.experiment_dir = os.path.join(tmp_path, self.SPEARMINT_EXP_DIR)
        self.signal_dir = os.path.join(tmp_path, self.SPEARMINT_SIGNAL_DIR)

        # experiment dir has to be created AFTER local_spearmint
        # since it destroys LocalComputer.tmp_dir
        os.makedirs(self.experiment_dir)

        # signal dir has to be created AFTER local_spearmint
        # since it destroys LocalComputer.tmp_dir
        os.makedirs(self.signal_dir)

        spearmint_utils.create_conf(self.experiment_dir)
        return local_spearmint

    def __spearmint_exit(self, label):
        # There was some problem with spearmint LocalComputer and it exited
        # so we lost all progress on the task - so let's panic!
        raise Exception("Spearmint docker was restarted "
                        "with exit code {}. WRONG!".format(label))

    def short_extra_data_repr(self, extra_data):
        return "MLPOC extra_data: {}".format(extra_data)

    def __get_next_network_config(self):
        # here happens magic with spearmint in localcomputer
        self.__trigger_spearmint_update()

        # TODO hidden_size shouldn't be hardcoded here
        hidden_size = int(spearmint_utils.get_next_configuration(
            self.experiment_dir)[0]
        )

        # order of these is important! that's why there's no dict here
        # (no OrderedDict, because these params will be saved to json)
        return [("HIDDEN_SIZE", hidden_size),
                ("NUM_EPOCHS", self.task_definition.options.number_of_epochs),
                ("STEPS_PER_EPOCH", self.task_definition.options.steps_per_epoch)]  # noqa

    def _extra_data(self, perf_index=0.0) -> Tuple[BLACK_BOX, ComputeTaskDef]:
        subtask_id = self.__get_new_subtask_id()
        black_box = self.BLACK_BOX(
            self.task_definition.options.probability_of_save,
            self.task_definition.options.number_of_epochs
        )
        network_configuration = self.__get_next_network_config()

        input_data_file_base = os.path.basename(self.task_definition.input_data_file)  # noqa

        extra_data = {
            "data_file": input_data_file_base,
            "network_configuration": network_configuration,
            "order_of_batches": list(range(100)),
            "RESULT_EXT": self.RESULT_EXT
        }

        ctd = self._new_compute_task_def(subtask_id,
                                         extra_data,
                                         perf_index=perf_index)
        return (black_box, ctd)

    @coretask.accepting
    def query_extra_data(self,
                         perf_index: float,
                         num_cores=1,
                         node_id: str = None,
                         node_name: str = None) -> Task.ExtraData:
        logger.info("New task is being deployed")

        black_box, ctd = self._extra_data(perf_index)
        sid = ctd.subtask_id

        # Deepcopying extra_data is ugly, but it is probably the only option
        # as the ctd.extra_data is modified in-place,
        # and then saved/stored/send somewhere, black_box doesn't survive
        # serialization, so then have to be ereased
        # (in verificator.py/__query_extra_data) - but, only in this form
        # it is are available  to verificator - since it has access
        # only to subtasks_given array and not some MLPOCTask.black_boxes_array
        self.subtasks_given[sid] = copy.deepcopy(ctd.extra_data)
        self.subtasks_given[sid]["status"] = SubtaskStatus.starting
        self.subtasks_given[sid]["perf"] = perf_index
        self.subtasks_given[sid]["node_id"] = node_id
        self.subtasks_given[sid]["black_box"] = black_box

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
        logger.info("Subtask finished")

        if self.num_tasks_received == self.total_tasks:
            self.__generate_final_answer()

    def __generate_final_answer(self) -> None:
        """
        For now, it just returns the result.dat file from spearmint
        but maybe in the future we would want to return trained network model
        :return: None
        """
        out_file = self.task_definition.output_file
        logger.info("Genereting final answer in {}".format(out_file))
        result_file = find_file_with_ext(self.spearmint_path, [".dat"])
        shutil.copy(result_file, out_file)

    def __get_new_subtask_id(self) -> str:
        """
        :return: A random string of length 32
        """
        return "{:32x}".format(random.getrandbits(128))

    def __get_result_file_name(self, subtask_id: str) -> str:
        return "{}{}".format(subtask_id[0:6],
                             self.RESULT_EXT)

    def query_extra_data_for_test_task(self) -> ComputeTaskDef:
        black_box, exd = self._extra_data()
        self.test_black_box = black_box
        return exd

    def __update_spearmint_state(self, score_file):
        with open(score_file, "r") as f:
            res = json.load(f)

        # structure of the score file: {score: list_of_hyperparams}
        # where list_of_hyperparams = [(name_of_param, param_value)]
        score, hyperparameters = list(res.items())[0]

        # TODO HIDDEN_SIZE shouldn't be harcoded here like that
        hyperparameters = [str(v) for k, v in hyperparameters
                           if k == "HIDDEN_SIZE"]

        assert isinstance(hyperparameters, list)
        # not so dumb as it seems - it's checking if score can be casted to float
        assert isinstance(float(score), float)

        spearmint_utils.run_one_evaluation(
            self.experiment_dir,
            params={score: hyperparameters}
        )

    # TODO set the structure of message_data
    # as in TaskThread.check_for_new_messages
    def react_to_message(self, subtask_id: str, data: Dict):
        """
        Saves answer to blackbox and gets a response
        :param subtask_id:
        :param data: message_data containing hash of state
        :return: Message containing answer - if the state should be saved
        """
        assert data["content"]["message_type"] == "MLPOCBlackBoxAskMessage"
        box = self.subtasks_given[subtask_id]["black_box"]  # type: BlackBox

        answer = box.decide(hash=data["content"]["params_hash"],
                            epoch_num=data["content"]["number_of_epoch"])
        return MLPOCBlackBoxAnswerMessage.new_message(answer)


class MLPOCTaskBuilder(CoreTaskBuilder):
    TASK_CLASS = MLPOCTask

    @classmethod
    def build_dictionary(cls, definition: MLPOCTaskDefinition):
        dictionary = super().build_dictionary(definition)
        opts = dictionary['options']

        opts["number_of_epochs"] = int(definition.options.number_of_epochs)
        opts["steps_per_epoch"] = int(definition.options.steps_per_epoch)

        return dictionary

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


# comment that line to enable type checking
enforce.config({'groups': {'set': {'mlpoc': False}}})
