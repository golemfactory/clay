from copy import copy
import logging
import math
import os

from apps.rendering.task.verifier import FrameRenderingVerifier
from apps.blender.resources.imgcompare import check_size

from golem.verification.verifier import SubtaskVerificationState

logger = logging.getLogger("apps.blender")


class BlenderVerifier(FrameRenderingVerifier):

    def _get_part_img_size(self, subtask_info):
        x, y = self._get_part_size(subtask_info)
        return 0, 0, x, y

    def _get_part_size(self, subtask_info):
        total_tasks = subtask_info['total_tasks']
        if not subtask_info['use_frames']:
            res_y = self._get_part_size_from_subtask_number(subtask_info)
        elif len(subtask_info['all_frames']) >= total_tasks:
            res_y = subtask_info['res_y']
        else:
            parts = int(total_tasks / len(subtask_info['all_frames']))
            res_y = int(math.floor(subtask_info['res_y'] / parts))
        return subtask_info['res_x'], res_y

    def _get_part_size_from_subtask_number(self, subtask_info):

        if subtask_info['res_y'] % subtask_info['total_tasks'] == 0:
            res_y = int(subtask_info['res_y'] / subtask_info['total_tasks'])
        else:
            # in this case task will be divided into not equal parts:
            # floor or ceil of (res_y/total_tasks)
            # ceiling will be height of subtasks with smaller num
            ceiling_height = int(math.ceil(subtask_info['res_y'] /
                                           subtask_info['total_tasks']))
            additional_height = ceiling_height * subtask_info['total_tasks']
            additional_pixels = additional_height - subtask_info['res_y']
            ceiling_subtasks = subtask_info['total_tasks'] - additional_pixels

            if subtask_info['start_task'] > ceiling_subtasks:
                res_y = ceiling_height - 1
            else:
                res_y = ceiling_height
        return res_y

    def _check_size(self, file_, res_x, res_y):
        return check_size(file_, res_x, res_y)

    def _verify_imgs(self, subtask_info, results, reference_data, resources):
        if not super(BlenderVerifier, self)._verify_imgs(subtask_info, results,
                                                         reference_data,
                                                         resources):
            return False

        if not self._render_full_subtask(subtask_info, results, reference_data,
                                         resources):
            return False
        comp_results = self.computer.get_result()
        if not comp_results or 'data' not in comp_results:
            self.state = SubtaskVerificationState.NOT_SURE
            self.message ="No reference data produced in verification"
            return False
        self.extra_data['results'] = copy(self.computer.get_result()['data'])
        print(self.extra_data['results'])
        images = [res for res in self.extra_data['results']
                  if res.upper().endswith(subtask_info['output_format'])]
        self._verify_results(results, images)
        return True

    def _render_full_subtask(self, subtask_info, results, reference_data,
                             resource):
        print("RENDER FULL SUBTASK")
        if not self.computer:
            self.state = SubtaskVerificationState.NOT_SURE
            self.message = "No computer available to verify data"
            return False

        self.computer.start_computation(
            root_path=os.path.join(subtask_info["tmp_dir"],
                                   subtask_info['subtask_id']),
            success_callback=self._subtask_rendered,
            error_callback=self._subtask_render_failure,
            compute_task_def=subtask_info['ctd'],
            resources=self.resources,
            additional_resources=[],
        )
        if not self.computer.wait():
            self.state = SubtaskVerificationState.NOT_SURE
            self.message = "computation was not run correctly"
            return False
        if self.verification_error:
            self.state = SubtaskVerificationState.NOT_SURE
            self.message = "There was an verification error: {}".format(
                self.verification_error)
            return False
        return True

    def _subtask_rendered(self, results, time_spend):
        logger.info("Subtask for verification rendered")
        self.verification_error = False

    def _subtask_render_failure(self, error):
        logger.info("Subtask for verification rendered failure {}".format(
            error))
        self.verification_error = True

    def _verify_results(self, results, images):
        pass  #FIXME Fill me