from copy import deepcopy
import logging
import os
import shutil

from apps.rendering.resources.imgrepr import load_as_PILImgRepr
from apps.rendering.resources.imgverifier import ImgVerifier, ImgStatistics
from apps.rendering.task.verifier import RenderingVerifier

from golem.core.fileshelper import common_dir, find_file_with_ext
from golem.verification.verifier import SubtaskVerificationState


logger = logging.getLogger("apps.lux")


class LuxRenderVerifier(RenderingVerifier):

    def _check_files(self, subtask_info, results, reference_data, resources):
        # First, assume it is wrong ;p
        self.state = SubtaskVerificationState.WRONG_ANSWER

        try:
            self._validate_lux_results(subtask_info, results, reference_data,
                                       resources)
        except TypeError as e:
            self.message = "Exception during verification of subtask: "
            self.message += str(subtask_info["subtask_id"]) + " " + str(e)
            logger.info(self.message)
        finally:
            self.verification_completed()

    # pylint: disable=unused-argument
    def _validate_lux_results(self, subtask_info, results, reference_data,
                              resources):
        tr_flm_files, tr_preview_files = \
            self._extract_tr_files(subtask_info, results)
        test_flm = self.reference_data[0]
        ref_imgs = self.reference_data[1:]
        img_verifier = ImgVerifier()

        cropped_ref_imgs = self.__prepare_reference_images(subtask_info,
                                                           ref_imgs,
                                                           img_verifier)
        reference_stats = ImgStatistics(cropped_ref_imgs[0],
                                        cropped_ref_imgs[1])

        for img, flm_file in zip(tr_preview_files, tr_flm_files):
            self.__compare_img_with_flm(img, flm_file, subtask_info,
                                        img_verifier, cropped_ref_imgs,
                                        reference_stats, test_flm)

    def __compare_img_with_flm(self, img, flm_file, subtask_info, img_verifier,
                               cropped_ref_imgs, reference_stats, test_flm):
        crop_window = subtask_info['verification_crop_window']
        cropped_img = img_verifier.crop_img_relative(img, crop_window)
        imgstat = ImgStatistics(cropped_ref_imgs[0], cropped_img)

        is_valid_against_reference = \
            img_verifier.is_valid_against_reference(imgstat,
                                                    reference_stats)

        is_flm_merging_validation_passed = \
            self.merge_flm_files(flm_file, subtask_info, test_flm)

        if is_valid_against_reference == \
                SubtaskVerificationState.VERIFIED and \
                is_flm_merging_validation_passed:
            self.state = SubtaskVerificationState.VERIFIED

        logger.info("Subtask "
                    + str(subtask_info["subtask_id"])
                    + " verification result: "
                    + self.state.name)

    def __prepare_reference_images(self, subtask_info, ref_imgs,
                                   img_verifier):
        cropped_ref_imgs = []
        for ref_img in ref_imgs:
            if subtask_info["output_format"] == "exr":
                # exr comes already cropped
                cropped_ref_img = ref_img
            elif subtask_info["output_format"] == "png":
                # crop manually
                cropped_ref_img = \
                    img_verifier.crop_img_relative(
                        ref_img,
                        subtask_info['verification_crop_window'])
            else:
                raise TypeError("Unsupported output format: "
                                + subtask_info["output_format"])
            cropped_ref_imgs.append(cropped_ref_img)
        return cropped_ref_imgs

    def _extract_tr_files(self, subtask_info, results):
        tr_preview_files = []
        ext = '.' + subtask_info["output_format"]
        tr_preview_paths = [os.path.normpath(f) for f in results
                            if self._has_ext(f, ext)]

        for f in tr_preview_paths:
            ref_img_pil = load_as_PILImgRepr(f)
            tr_preview_files.append(ref_img_pil)

        tr_flm_files = [os.path.normpath(f)
                        for f in results if self._has_ext(f, '.flm')]

        return tr_flm_files, tr_preview_files

    def _has_ext(self, filename, ext):
        return filename.lower().endswith(ext.lower())

    def merge_flm_files(self, new_flm, subtask_info, output):
        if not self._check_computer():
            return False

        ctd = self.query_extra_data_for_advanced_verification(new_flm,
                                                              subtask_info,
                                                              output)

        self.computer.start_computation(
            root_path=subtask_info["root_path"],
            success_callback=self._verify_flm_ready,
            error_callback=self._verify_flm_failure,
            compute_task_def=ctd,
            resources=self.resources,
            additional_resources=[output, new_flm]
        )

        if not self._wait_for_computer():
            return False
        if self.verification_error:
            self.state = SubtaskVerificationState.NOT_SURE
            self.message = "There was an verification error: {}".format(
                self.verification_error)
            return False
        result = self.computer.get_result()
        commonprefix = common_dir(result['data'])
        flm = find_file_with_ext(commonprefix, [".flm"])
        stderr = [x for x in result['data']
                  if os.path.basename(x) == "stderr.log"]

        if flm is None or not stderr:
            self.message = "No produre output produce in verification " \
                           "merging phase"
            return False
        else:
            try:
                with open(stderr[0]) as f:
                    stderr_in = f.read()
                if "ERROR" in stderr_in:
                    self.message = "Error while merging results"
                    return False
            except (IOError, OSError) as ex:
                self.message = "Cannot merge results {}".format(ex)
                return False

            shutil.copy(flm, os.path.join(subtask_info["tmp_dir"],
                                          "test_result.flm"))
            return True

    def query_extra_data_for_advanced_verification(self, new_flm,
                                                   subtask_info, test_flm):
        files = [os.path.basename(new_flm), os.path.basename(test_flm)]
        merge_ctd = deepcopy(subtask_info["merge_ctd"])
        merge_ctd['extra_data']['flm_files'] = files
        return merge_ctd

    def _verify_flm_ready(self, results, time_spend):
        logger.info("Advance verification finished")
        self.verification_error = False

    def _verify_flm_failure(self, error):
        logger.info("Advance verification failure {}".format(error))
        self.verification_error = True
