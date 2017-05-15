from __future__ import division
import math
import random

from golem.core.common import timeout_to_deadline

from apps.rendering.task.verificator import FrameRenderingVerificator
from apps.blender.resources.scenefileeditor import generate_blender_crop_file
from apps.blender.resources.imgcompare import check_size


class BlenderVerificator(FrameRenderingVerificator):
    def __init__(self, *args, **kwargs):
        super(BlenderVerificator, self).__init__(*args, **kwargs)
        self.box_size = [8, 8]
        self.compositing = False
        self.output_format = ""
        self.src_code = ""
        self.docker_images = []
        self.verification_timeout = 0

    def set_verification_options(self, verification_options):
        super(BlenderVerificator, self).set_verification_options(verification_options)
        if self.advanced_verification:
            box_x = min(verification_options.box_size[0], self.res_x)
            box_y = min(verification_options.box_size[1],
                        int(self.res_y / self.total_tasks))
            box_x = max(box_x, self.box_size[0])
            box_y = max(box_y, self.box_size[1])
            self.box_size = (box_x, box_y)

    def change_scope(self, subtask_id, start_box, tr_file, subtask_info):
        extra_data, _ = super(BlenderVerificator, self).change_scope(subtask_id, start_box,
                                                                     tr_file, subtask_info)
        min_x = start_box[0] / self.res_x
        max_x = (start_box[0] + self.verification_options.box_size[0] + 1) / self.res_x
        shift_y = (extra_data['start_task'] - 1) * (self.res_y / extra_data['total_tasks'])
        start_y = start_box[1] + shift_y
        max_y = (self.res_y - start_y) / self.res_y
        shift_y = start_y + self.verification_options.box_size[1] + 1
        min_y = max((self.res_y - shift_y) / self.res_y, 0.0)
        min_y = max(min_y, 0)
        script_src = generate_blender_crop_file(
            resolution=(self.res_x, self.res_y),
            borders_x=(min_x, max_x),
            borders_y=(min_y, max_y),
            use_compositing=self.compositing
        )
        extra_data['script_src'] = script_src
        extra_data['output_format'] = self.output_format
        return extra_data, (0, 0)

    def query_extra_data_for_advanced_verification(self, extra_data):
        ctd = super(BlenderVerificator, self).query_extra_data_for_advanced_verification(extra_data)
        ctd.subtask_id = str(random.getrandbits(128))
        ctd.src_code = self.src_code
        ctd.docker_images = self.docker_images
        ctd.deadline = timeout_to_deadline(self.verification_timeout)
        return ctd

    def _get_part_img_size(self, subtask_info):
        x, y = self._get_part_size(subtask_info)
        return 0, 0, x, y

    def _get_part_size(self, subtask_info):
        start_task = subtask_info['start_task']
        if not self.use_frames:
            res_y = self._get_part_size_from_subtask_number(start_task)
        elif len(self.frames) >= self.total_tasks:
            res_y = self.res_y
        else:
            parts = int(self.total_tasks / len(self.frames))
            res_y = int(math.floor(self.res_y / parts))
        return self.res_x, res_y

    def _get_part_size_from_subtask_number(self, subtask_number):

        if self.res_y % self.total_tasks == 0:
            res_y = int(self.res_y / self.total_tasks)
        else:
            # in this case task will be divided into not equal parts: floor or ceil of (res_y/total_tasks)
            # ceiling will be height of subtasks with smaller num
            ceiling_height = int(math.ceil(self.res_y / self.total_tasks))
            ceiling_subtasks = self.total_tasks - (ceiling_height * self.total_tasks - self.res_y)
            if subtask_number > ceiling_subtasks:
                res_y = ceiling_height - 1
            else:
                res_y = ceiling_height
        return res_y

    def _check_size(self, file_, res_x, res_y):
        return check_size(file_, res_x, res_y)