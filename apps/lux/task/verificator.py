from copy import deepcopy
import logging
import os
import shutil
import glob

from golem.core.fileshelper import common_dir, find_file_with_ext, has_ext
from golem.task.localcomputer import LocalComputer

from apps.core.task.verificator import SubtaskVerificationState
from apps.rendering.task.verificator import RenderingVerificator

from apps.rendering.resources.ImgVerificator import \
    ImgStatistics, ImgVerificator

from apps.rendering.resources.imgrepr import load_as_PILImgRepr

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
                dm.get_ref_data_dir(
                    task.header.task_id,
                    counter='flmMergingTest'),
                dm.tmp,
                dm.output
                )

        test_flm = glob.glob(os.path.join(dir, '*.flm'))
        return test_flm.pop()

    def _get_reference_imgs(self, task):
        ref_imgs = []
        dm = task.dirManager

        for i in range(0, task.reference_runs):
            dir = os.path.join(
                dm.get_ref_data_dir(task.header.task_id, counter=i),
                dm.tmp,
                dm.output)

            f = glob.glob(os.path.join(dir, '*.' + task.output_format))

            ref_img_pil = load_as_PILImgRepr(f.pop())
            ref_imgs.append(ref_img_pil)

        return ref_imgs

    def _extract_tr_files(self, tr_files, task):
        tr_preview_files = []
        tr_preview_paths = [os.path.normpath(f)
                            for f in tr_files
                            if has_ext(f, '.' + task.output_format)]

        for f in tr_preview_paths:
            ref_img_pil = load_as_PILImgRepr(f)
            tr_preview_files.append(ref_img_pil)

        tr_flm_files = [os.path.normpath(f)
                        for f in tr_files if has_ext(f, '.flm')]

        return tr_flm_files, tr_preview_files

    def _check_files(self, subtask_id, subtask_info, tr_files, task):
        # First, assume it is wrong ;p
        self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER

        try:
            tr_flm_files, tr_preview_files = \
                self._extract_tr_files(tr_files, task)

            # hack, advanced verification is enabled by default
            self.advanced_verification = True
            if self.advanced_verification:
                self.test_flm = self._get_test_flm(task)

                img_verificator = ImgVerificator()
                ref_imgs = self._get_reference_imgs(task)

                cropped_ref_imgs = []
                for ref_img in ref_imgs:
                    if task.output_format == "exr":
                        # exr comes already cropped
                        cropped_ref_img = ref_img
                    elif task.output_format == "png":
                        # crop manually
                        cropped_ref_img = \
                            img_verificator.crop_img_relative(
                                ref_img,
                                task.random_crop_window_for_verification)
                    else:
                        raise TypeError("Unsupported output format: "
                                        + task.output_format)

                    cropped_ref_imgs.append(cropped_ref_img)
                    # cropped_ref_img.img.save('aaa'
                    # + cropped_ref_img.get_name())

                # reference_stats are imgs rendered by requestor
                reference_stats = \
                    ImgStatistics(cropped_ref_imgs[0], cropped_ref_imgs[1])

                # golem_verificator todo render png from flm
                for img, flm_file in zip(tr_preview_files, tr_flm_files):
                    cropped_img = img_verificator.crop_img_relative(
                        img, task.random_crop_window_for_verification)
                    # cropped_img.img.save('aaa'
                    # + cropped_img.get_name())
                    imgstat = ImgStatistics(cropped_ref_imgs[0], cropped_img)

                    is_valid_against_reference = \
                        img_verificator.is_valid_against_reference(
                            imgstat, reference_stats)

                    is_flm_merging_validation_passed \
                        = self.merge_flm_files(flm_file, task, self.test_flm)

                    if is_valid_against_reference == \
                            SubtaskVerificationState.VERIFIED \
                            and is_flm_merging_validation_passed:
                                self.ver_states[subtask_id] = \
                                    SubtaskVerificationState.VERIFIED

                    logger.info("Subtask "
                                + str(subtask_id)
                                + " verification result: "
                                + self.ver_states[subtask_id].name
                                )

        except TypeError as e:
            logger.info("Exception during verification of subtask: "
                        + str(subtask_id) + " " + str(e))

    def query_extra_data_for_advanced_verification(self, new_flm):
        files = [os.path.basename(new_flm), os.path.basename(self.test_flm)]
        merge_ctd = deepcopy(self.merge_ctd)
        merge_ctd['extra_data']['flm_files'] = files
        return merge_ctd

    def merge_flm_files(self, new_flm, task, output):
        computer = LocalComputer(task, self.root_path, self.__verify_flm_ready,
                                 self.__verify_flm_failure,
                                 lambda:
                                 self.query_extra_data_for_advanced_verification
                                     (new_flm),
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
        stderr = [x for x in computer.tt.result['data']
                  if os.path.basename(x) == "stderr.log"]

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
