import logging
import os
import tempfile
from typing import Any, Dict

from apps.core.task.verificator import CoreVerificator, SubtaskVerificationState
from apps.mlpoc.mlpocenvironment import MLPOCTorchEnvironment
from apps.mlpoc.resources.code_pytorch.impl.common_utils import \
    details_from_dump_name
from golem.docker.image import DockerImage
from golem.resource.dirmanager import find_task_script, symlink_or_copy
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

    def __verification_succ(self, results, time_spent):
        logger.info("Advance verification finished")
        self.verification_error = False

    def __verification_fail(self, error):
        logger.info("Advance verification failure {}".format(error))
        self.verification_error = True

    def _load_src(self):
        with open(self.script_name, "r") as f:
            src = f.read()
        return src

    def __query_extra_data(self,
                           steps: int,
                           subtask_data: Dict[str, Any],
                           black_box: 'MLPOCTask.BLACK_BOX'):
        ctd = ComputeTaskDef()

        ctd.src_code = self._load_src()
        ctd.docker_images = [self.docker_image]
        ctd.extra_data.update(subtask_data)

        data_file = self.verification_options["input_data_file"]
        ctd.extra_data["data_file"] = os.path.basename(data_file)

        ctd.extra_data["black_box_history"] = black_box.history
        ctd.extra_data["STEPS_PER_EPOCH"] = steps

        # delete non-serializable black box class
        ctd.extra_data["black_box"] = None

        return ctd

    # FIXME quite tricky to know that I should run
    # self.ver_states[subtask_id] = SubtaskVerificationState.VERIFIED
    # Maybe it be better if _check_files would return True/False
    def _check_files(self, subtask_id, subtask_info, tr_files, task):
        black_box = subtask_info["black_box"]

        with tempfile.TemporaryDirectory() as tempdir:

            logger.info("Verification is done in {} tempdir".format(tempdir))

            # TODO remove "checkpoints" magic constant
            checkpoints_dir = os.path.join(tempdir, "checkpoints")
            os.mkdir(checkpoints_dir)

            epoch_num = lambda x: details_from_dump_name(x).epoch

            # TODO remove "begin" and "end" magic constants
            checkpoints = [f for f in tr_files
                           if any(x in f for x in ["begin", "end"])]
            checkpoint_dirs = set(epoch_num(f) for f in checkpoints)

            for c in checkpoint_dirs:
                os.mkdir(os.path.join(checkpoints_dir, c))
                for f in checkpoints:
                    if epoch_num(f) == c:
                        symlink_or_copy(f, os.path.join(checkpoints_dir,
                                                        c,
                                                        os.path.basename(f)))

            resources = {self.verification_options["code_place"],
                         self.verification_options["data_place"],
                         checkpoints_dir}

            steps = dict(subtask_info["network_configuration"])["STEPS_PER_EPOCH"]  # noqa

            qed = lambda: self.__query_extra_data(steps,
                                                  subtask_info,
                                                  black_box)

            assert set(os.path.basename(x) for x in resources) == \
                   {"code", "data", "checkpoints"}

            computer = LocalComputer(task=None,  # we don't use task at all
                                     root_path=tempdir,
                                     success_callback=self.__verification_succ,
                                     error_callback=self.__verification_fail,
                                     get_compute_task_def=qed,
                                     additional_resources=resources,
                                     use_task_resources=False,
                                     tmp_dir=tempdir)
            computer.run()
            if computer.tt is not None:
                computer.tt.join()
            else:
                self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER  # noqa
            if self.verification_error:
                self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER  # noqa

            self.ver_states[subtask_id] = SubtaskVerificationState.VERIFIED