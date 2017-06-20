from copy import deepcopy
import logging
import os
import shutil
import glob

from golem.core.fileshelper import common_dir, find_file_with_ext, has_ext
from golem.task.localcomputer import LocalComputer

from apps.core.task.verificator import SubtaskVerificationState
from apps.rendering.task.verificator import RenderingVerificator

from apps.rendering.resources.ImgVerificator import ImgStatistics, ImgVerificator
from apps.rendering.resources.imgrepr import (PILImgRepr)

logger = logging.getLogger("apps.lux")


class LuxRenderVerificator(RenderingVerificator):
    def __init__(self, *args, **kwargs):
        super(LuxRenderVerificator, self).__init__(*args, **kwargs)
        self.test_flm = None
        self.merge_ctd = None
        self.verification_error = False

    def _get_test_flm(self, task):
        dm = task.dirManager
        dir = os.path.join(
                dm.get_ref_data_dir(task.header.task_id, counter='flmMergingTest'),
                dm.tmp,
                dm.output
                )

        test_flm = glob.glob(os.path.join(dir,'*.flm'))
        return test_flm.pop()


    def _get_reference_imgs(self, task):
        ref_imgs = []
        dm=task.dirManager

        for i in range(0,task.referenceRuns):
            dir = os.path.join(
                dm.get_ref_data_dir(task.header.task_id, counter=i),
                dm.tmp,
                dm.output
                )

            f = glob.glob(os.path.join(dir,'*.png'))

            ref_img = PILImgRepr()
            ref_img.load_from_file(f.pop())
            ref_imgs.append(ref_img)

        return ref_imgs

    def _check_files(self, subtask_id, subtask_info, tr_files, task):
        if len(tr_files) == 0:
            self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER
            return

        if not self.advanced_verification:
            self.ver_states[subtask_id] = SubtaskVerificationState.VERIFIED
            return

        self.test_flm = self._get_test_flm(task)
        if not os.path.isfile(self.test_flm):
            logger.warning("Advanced verification set, but couldn't find flm for merging test!")
            logger.warning("No merge verification")


        imgVerificator = ImgVerificator()
        ref_imgs = self._get_reference_imgs(task)

        cropped_ref_imgs=[]
        for ref_img in ref_imgs:
            cropped_ref_img = imgVerificator.crop_img_relative(ref_img, task.random_crop_window_for_verification)
            cropped_ref_imgs.append(cropped_ref_img)
            # cropped_ref_img.img.save('aaa' + cropped_ref_img.get_name())

        reference_stats = ImgStatistics(cropped_ref_imgs[0], cropped_ref_imgs[1])  # these are imgs rendered by requestor

        tr_png_files = [os.path.normpath(f) for f in tr_files if has_ext(f, '.png')]
        tr_flm_files = [os.path.normpath(f) for f in tr_files if has_ext(f, '.flm')]

        for png_file, flm_file in zip(tr_png_files, tr_flm_files):  # GG todo render png from flm
            img = PILImgRepr()
            img.load_from_file(png_file)
            cropped_img = imgVerificator.crop_img_relative(img, task.random_crop_window_for_verification)
            # cropped_img.img.save('aaa' + cropped_img.get_name())
            imgstat = ImgStatistics(cropped_ref_imgs[0], cropped_img)

            self.ver_states[subtask_id] = imgVerificator.is_valid_against_reference(imgstat, reference_stats)

            if self.ver_states[subtask_id] == SubtaskVerificationState.VERIFIED and os.path.isfile(self.test_flm):
                flm_merging_validation_result = self.merge_flm_files(flm_file, task, self.test_flm)

                if not flm_merging_validation_result:
                    logger.info("Subtask " + str(subtask_id) + " rejected - flm merging failed.")
                    self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER


    def query_extra_data_for_advanced_verification(self, new_flm):
        files = [os.path.basename(new_flm), os.path.basename(self.test_flm)]
        merge_ctd = deepcopy(self.merge_ctd)
        merge_ctd.extra_data['flm_files'] = files
        return merge_ctd

    def merge_flm_files(self, new_flm, task, output):
        computer = LocalComputer(task, self.root_path, self.__verify_flm_ready,
                                 self.__verify_flm_failure,
                                 lambda: self.query_extra_data_for_advanced_verification(new_flm),
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
