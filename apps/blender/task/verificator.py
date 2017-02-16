import math
import random

from golem.core.common import timeout_to_deadline

from apps.rendering.task.verificator import FrameRenderingVerificator
from apps.blender.resources.scenefileeditor import generate_blender_crop_file


class BlenderVerificator(FrameRenderingVerificator):
    def __init__(self, *args, **kwargs):
        super(BlenderVerificator, self).__init__(*args, **kwargs)
        self.box_size = [1, 1]

    def change_scope(self, subtask_id, start_box, tr_file, subtask_info):
        extra_data, _ = super(BlenderVerificator, self).change_scope(subtask_id, start_box,
                                                                     tr_file, subtask_info)
        min_x = start_box[0] / float(self.task.res_x)
        max_x = (start_box[0] + self.verification_options.box_size[0] + 1) / float(self.task.res_x)
        shift_y = (extra_data['start_task'] - 1) * (self.task.res_y / float(extra_data['total_tasks']))
        start_y = start_box[1] + shift_y
        max_y = float(self.task.res_y - start_y) / self.task.res_y
        shift_y = start_y + self.verification_options.box_size[1] + 1
        min_y = max(float(self.task.res_y - shift_y) / self.task.res_y, 0.0)
        min_y = max(min_y, 0)
        script_src = generate_blender_crop_file(
            resolution=(self.task.res_x, self.task.res_y),
            borders_x=(min_x, max_x),
            borders_y=(min_y, max_y),
            use_compositing=self.task.compositing
        )
        extra_data['script_src'] = script_src
        extra_data['output_format'] = self.task.output_format
        return extra_data, (0, 0)

    def query_extra_data_for_advance_verification(self, extra_data):
        ctd = super(BlenderVerificator, self).query_extra_data_for_advance_verification(extra_data)
        ctd.subtask_id = str(random.getrandbits(128))
        ctd.src_code = self.task.src_code
        ctd.docker_images = self.task.docker_images
        ctd.deadline = timeout_to_deadline(self.task.verification_timeout)

    def _get_part_img_size(self, subtask_id, adv_test_file, subtask_info):
        x, y = self._get_part_size(subtask_id, subtask_info)
        return 0, 0, x, y

    def _get_part_size(self, subtask_id, subtask_info):
        start_task = subtask_info['start_task']
        if not self.task.use_frames:
            res_y = self._get_part_size_from_subtask_number(start_task)
        elif len(self.task.frames) >= self.task.total_tasks:
            res_y = self.task.res_y
        else:
            parts = self.task.total_tasks / len(self.task.frames)
            res_y = int(math.floor(float(self.task.res_y) / float(parts)))
        return self.task.res_x, res_y

    def _get_part_size_from_subtask_number(self, subtask_number):

        if self.task.res_y % self.task.total_tasks == 0:
            res_y = self.task.res_y / self.task.total_tasks
        else:
            # in this case task will be divided into not equal parts: floor or ceil of (res_y/total_tasks)
            # ceiling will be height of subtasks with smaller num
            ceiling_height = int(math.ceil(float(self.task.res_y) / float(self.task.total_tasks)))
            ceiling_subtasks = self.task.total_tasks - (ceiling_height * self.task.total_tasks - self.task.res_y)
            if subtask_number > ceiling_subtasks:
                res_y = ceiling_height - 1
            else:
                res_y = ceiling_height
        return res_y