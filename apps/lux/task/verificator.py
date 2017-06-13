from copy import deepcopy
import logging
import os
import shutil

from golem.core.fileshelper import common_dir, find_file_with_ext, has_ext
from golem.task.localcomputer import LocalComputer

from apps.core.task.verificator import SubtaskVerificationState
from apps.rendering.task.verificator import RenderingVerificator

from apps.rendering.resources.ImgVerificator import ImgStatistics, ImgVerificator
from apps.rendering.resources.imgrepr import (PILImgRepr)

from golem.resource.dirmanager import DirManager

logger = logging.getLogger("apps.lux")


class LuxRenderVerificator(RenderingVerificator):
    def __init__(self, *args, **kwargs):
        super(LuxRenderVerificator, self).__init__(*args, **kwargs)
        self.test_flm = None
        self.merge_ctd = None
        self.verification_error = False

    def _check_files(self, subtask_id, subtask_info, tr_files, task):
        if len(tr_files) == 0:
            self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER
            return

        for tr_file in tr_files:
            tr_file = os.path.normpath(tr_file)

            if has_ext(tr_file, '.png'): # GG todo render png from flm
                if self.advanced_verification:
                    if not os.path.isfile(self.test_flm): # GG what for is test_flm?
                        logger.warning("Advanced verification set, but couldn't find test result!") #GG why not set self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER ?
                        logger.warning("Skipping verification")
                    else:
                     #   root_path = dirmanager.get_ref_data_path(task.header.task_id, self.root_path, 0)

                        ref_img_name = 'reference_task1.png'
                        ref_img0 = PILImgRepr()
                        ref_img0.load_from_file(os.path.join(
                            DirManager(self.root_path).get_ref_data_dir(task.header.task_id, counter=0),
                            ref_img_name.png
                        ))

                        ref_img1 = PILImgRepr()
                        ref_img1.load_from_file(os.path.join(
                            DirManager(self.root_path).get_ref_data_dir(task.header.task_id, counter=1),
                            ref_img_name
                        ))

                        cropping_window = task.random_crop_window_for_verification

                        ref_img0 = imgVerificator.crop_img_relative(ref_img0, cropping_window)
                        ref_img1 = imgVerificator.crop_img_relative(ref_img1, cropping_window)

                        reference_stats = ImgStatistics(ref_img0, ref_img1)  # these are img rendered by requestor

                        imgVerificator = ImgVerificator()

                        croped_img = imgVerificator.crop_img_relative(tr_file, cropping_window)
                        # croped_img.img.save('aaa'+croped_img.get_name())
                        imgstat = ImgStatistics(ref_img0, croped_img)

                        validation_result = imgVerificator.is_valid_against_reference(imgstat, reference_stats)
                        self.ver_states[subtask_id] = validation_result

                        if validation_result == SubtaskVerificationState.VERIFIED:
                            if not self.merge_flm_files(tr_file, task, self.test_flm): # just in case it fails?
                                logger.info("Subtask " + str(subtask_id) + " rejected.")
                                self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER
                                return



            ### OLD STUFF ###
            if has_ext(tr_file, '.FLM'):
                if self.advanced_verification:
                    if not os.path.isfile(self.test_flm):
                        logger.warning("Advanced verification set, but couldn't find test result!") #GG why not set self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER ?
                        logger.warning("Skipping verification")
                    else:
                        if not self.merge_flm_files(tr_file, task, self.test_flm):
                            logger.info("Subtask " + str(subtask_id) + " rejected.")
                            self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER
                            return
                self.ver_states[subtask_id] = SubtaskVerificationState.VERIFIED
        if self.ver_states.get(subtask_id) != SubtaskVerificationState.VERIFIED:
            self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER

    def query_extra_data_for_advanced_verification(self, new_flm):
        files = [os.path.basename(new_flm), os.path.basename(self.test_flm)]
        merge_ctd = deepcopy(self.merge_ctd)
        merge_ctd.extra_data['flm_files'] = files
        return merge_ctd

    def merge_flm_files(self, new_flm, task, output):
        computer = LocalComputer(task, self.root_path, self.__verify_flm_ready,
                                 self.__verify_flm_failure,
                                 lambda: self.query_extra_data_for_advanced_verification(new_flm), # GG why we need lambda?
                                 use_task_resources=False,
                                 additional_resources=[self.test_flm, new_flm])
        computer.run()
        if computer.tt is not None:
            computer.tt.join()
        else:
            return False
        if self.verification_error:
            return False
        commonprefix = common_dir(computer.tt.result['data'])
        flm = find_file_with_ext(commonprefix, [".flm"])
        stderr = filter(lambda x: os.path.basename(x) == "stderr.log", computer.tt.result['data'])
        if flm is None or len(stderr) == 0:
            return False
        else:
            try:
                with open(stderr[0]) as f:
                    stderr_in = f.read()
                if "ERROR" in stderr_in:
                    return False
            except (IOError, OSError):
                return False

            shutil.copy(flm, os.path.join(self.tmp_dir, "test_result.flm"))
            return True

    def __verify_flm_ready(self, results, time_spent):
        logger.info("Advance verification finished")
        self.verification_error = False

    def __verify_flm_failure(self, error):
        logger.info("Advance verification failure {}".format(error))
        self.verification_error = True
