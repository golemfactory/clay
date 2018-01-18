from copy import copy
import logging
import math
import os

import golem_messages.message

from apps.rendering.task.verifier import FrameRenderingVerifier
from apps.blender.resources.cropgenerator import generate_crops
from apps.blender.resources.imgcompare import check_size
from apps.blender.resources.scenefileeditor import generate_blender_crop_file

from golem.core.common import get_golem_path
from golem.docker.image import DockerImage
from golem.verification.verifier import SubtaskVerificationState

logger = logging.getLogger("apps.blender")

NUM_CROPS = 3


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

        if not self._render_crops(subtask_info, results, reference_data,resources):
            return False
        comp_results = self.computer.get_result()
        if not comp_results or 'data' not in comp_results:
            self.state = SubtaskVerificationState.NOT_SURE
            self.message ="No reference data produced in verification"
            return False
        self.extra_data['results'] = copy(self.computer.get_result()['data'])
        images = [res for res in self.extra_data['results']
                  if res.upper().endswith(subtask_info['output_format'])]
        self._verify_results(subtask_info, results, images)
        return True

    def _render_crops(self, subtask_info, results, reference_data, resource,
                      num_crops=NUM_CROPS):
        if not self.computer:
            self.state = SubtaskVerificationState.NOT_SURE
            self.message = "No computer available to verify data"
            return False

        crops_info = generate_crops((subtask_info['res_x'],
                                     subtask_info['res_y']),
                                    subtask_info['crop_window'], num_crops)

        for num in range(num_crops):
            self._render_one_crop(crops_info[0][num], subtask_info, num)
            print(self.computer.get_result()['data'])

    def _render_one_crop(self, crop, subtask_info, num):
        minx, maxx, miny, maxy = crop

        script_src = generate_blender_crop_file(
            resolution=(subtask_info['res_x'], subtask_info['res_y']),
            borders_x=(minx, maxx),
            borders_y=(miny, maxy),
            use_compositing=False
        )

        ctd = copy(subtask_info['ctd'])
        ctd["extra_data"]["script_src"] = script_src
        ctd['extra_data']['outfilebasename'] = \
            "ref_" + ctd['extra_data']["outfilebasename"]

        self.computer.start_computation(
            root_path=os.path.join(subtask_info["tmp_dir"],
                                   subtask_info['subtask_id'],
                                   str(num)),
            success_callback=self._subtask_rendered,
            error_callback=self._subtask_render_failure,
            compute_task_def=ctd,
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

    def _verify_results(self, subtask_info, results, images):
        print("VERIFY RESUTLS")
        ctd = golem_messages.message.ComputeTaskDef()
        ctd['docker_images'] = [DockerImage(repository="golemfactor/img_stats",
                                            tag="1.0")]
        ctd['subtask_id'] = subtask_info['subtask_id']

        _, _, x, y = self._get_part_img_size(subtask_info)
        ctd['extra_data'] = {
            'cropped_img_path': "/golem/resources/" +
                                os.path.basename(images[0]),
            'rendered_scene_path': "/golem/resources/" +
                                   os.path.basename(results[0]),
            'xres': x,
            'yres': y}

        runner_script = os.path.join(get_golem_path(), "apps", "blender",
                                     "resources", "scripts", "runner.py")
        with open(runner_script) as f:
            src_code = f.read()
        ctd['src_code'] = src_code

        self.computer.start_computation(
            root_path=os.path.join(subtask_info["tmp_dir"],
                                   subtask_info['subtask_id'],
                                   "compare"),
            success_callback=self._images_compared,
            error_callback=self._images_failure,
            compute_task_def=ctd,
            resources=[],
            additional_resources=results + images,
        )

    def _images_compared(self, results, time_spend):
        logger.info("Images comparison finished")
        self.verification_error = False

    def _images_failure(self, error):
        logger.info("Subtask for image comparison failure {}".format(
            error))
        self.verification_error = True