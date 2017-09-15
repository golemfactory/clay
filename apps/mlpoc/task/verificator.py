import logging
import os

from apps.core.task.verificator import CoreVerificator, SubtaskVerificationState
from apps.mlpoc.mlpocenvironment import MLPOCTorchEnvironment
from golem.core.common import get_golem_path
from golem.docker.image import DockerImage
from golem.resource.dirmanager import find_task_script
from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import ComputeTaskDef

logger = logging.getLogger("apps.mlpoc")


class MLPOCTaskVerificator(CoreVerificator):
    SCRIPT_NAME = "requestor_verification.py"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.verification_options = {}
        self.verification_error = False
        self.script_name = find_task_script(MLPOCTorchEnvironment.APP_DIR,
                                            self.SCRIPT_NAME)
        assert os.path.isfile(self.script_name)

        self.docker_image = DockerImage(MLPOCTorchEnvironment.DOCKER_IMAGE,
                                        tag=MLPOCTorchEnvironment.DOCKER_TAG)

    def __verification_success(self, results, time_spent):
        logger.info("Advance verification finished")
        self.verification_error = False

    def __verification_failure(self, error):
        logger.info("Advance verification failure {}".format(error))
        self.verification_error = True

    def _load_src(self):
        with open(self.script_name, "r") as f:
            src = f.read()
        return src

    def __query_extra_data(self, steps):
        ctd = ComputeTaskDef()
        ctd.extra_data["STEPS_PER_EPOCH"] = steps
        ctd.extra_data["data_file"] = os.path.join(get_golem_path(),
                                                   "apps",
                                                   "mlpoc",
                                                   "test_data",
                                                   "IRIS.csv")
        ctd.src_code = self._load_src()
        ctd.docker_images = [self.docker_image]
        return ctd

    def _check_files(self, subtask_id, subtask_info, tr_files, task):

        if self.verification_options["no_verification"]:
            # FIXME quite tricky to know that I should save that
            # it would be a lot better if _check_files would juts return True/False
            self.ver_states[subtask_id] = SubtaskVerificationState.VERIFIED
            return

        qed = lambda: self.__query_extra_data(subtask_info["STEPS_PER_EPOCH"])
        computer = LocalComputer(None,  # we don't use task at all
                                 "",
                                 self.__verification_success,
                                 self.__verification_failure,
                                 qed,
                                 additional_resources=tr_files,
                                 use_task_resources=False)
        computer.run()
        if computer.tt is not None:
            computer.tt.join()
        else:
            self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER
        if self.verification_error:
            self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER
        # TODO only for debugging
        stderr = [x for x in computer.tt.result['data']
                  if os.path.basename(x) == "stderr.log"]

        self.ver_states[subtask_id] = SubtaskVerificationState.VERIFIED
