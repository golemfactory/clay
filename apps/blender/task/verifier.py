from copy import deepcopy
import logging
import math
import os
from collections import Callable
from threading import Lock

from golem.core.common import timeout_to_deadline
from apps.rendering.task.verifier import FrameRenderingVerifier
from apps.blender.resources.cropgenerator import generate_crops
from apps.blender.resources.imgcompare import check_size
from apps.blender.resources.scenefileeditor import generate_blender_crop_file

logger = logging.getLogger("apps.blender")

NUM_CROPS = 3


class BlenderVerifier(FrameRenderingVerifier):

    def __init__(self, callback: Callable):
        super().__init__(callback)
        self.lock = Lock()
        self.verified_crops_counter = 0
        self.success = None
        self.failure = None

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

    # pylint: disable-msg=too-many-arguments
    def _verify_imgs(self, subtask_info, results, reference_data, resources,
                     success_=None, failure=None):
        def success():
            self.success = success_
            self.failure = failure
            self._render_crops(subtask_info, resources)

        super()._verify_imgs(
            subtask_info,
            results,
            reference_data,
            resources, success, failure)

    def _render_crops(self, subtask_info, resources,
                      num_crops=NUM_CROPS, crop_size=None):
        # pylint: disable=unused-argument
        if not self._check_computer():
            return False

        crops_info = generate_crops((subtask_info['res_x'],
                                     subtask_info['res_y']),
                                    subtask_info['crop_window'], num_crops,
                                    crop_size)
        for num in range(num_crops):
            self._render_one_crop(crops_info[0][num], subtask_info, num)
        return True

    def _render_one_crop(self, crop, subtask_info, num):
        minx, maxx, miny, maxy = crop

        script_src = generate_blender_crop_file(
            resolution=(subtask_info['res_x'], subtask_info['res_y']),
            borders_x=(minx, maxx),
            borders_y=(miny, maxy),
            use_compositing=False
        )
        ctd = self._generate_ctd(subtask_info, script_src)
        # FIXME issue #1955
        self.computer.start_computation(
            root_path=os.path.join(subtask_info['tmp_dir'],
                                   subtask_info['subtask_id'], str(num)),
            success_callback=self._crop_rendered,
            error_callback=self._crop_render_failure,
            compute_task_def=ctd,
            resources=self.resources,
            additional_resources=[]
        )

    @staticmethod
    def _generate_ctd(subtask_info, script_src):
        ctd = deepcopy(subtask_info['ctd'])

        ctd['extra_data']['outfilebasename'] = \
            "ref_" + subtask_info['outfilebasename']
        ctd['extra_data']['script_src'] = script_src
        ctd['deadline'] = timeout_to_deadline(subtask_info['subtask_timeout'])
        return ctd

    #  The verification function will generate three random crops, from results
    #  only after all three will be generated, we can start verification process
    def _crop_rendered(self, results, time_spend):
        logger.info("Crop for verification rendered. Time spent: %r, "
                    "results: %r", time_spend, results)
        with self.lock:
            self.verified_crops_counter += 1
            if self.verified_crops_counter == NUM_CROPS:
                self.success()

    #  One failure is enough to stop verification process, although this might
    #  changein future
    def _crop_render_failure(self, error):
        logger.warning("Crop for verification render failure %r", error)
        self.failure()
