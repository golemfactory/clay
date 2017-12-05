
import math


from apps.rendering.task.verificator import FrameRenderingVerificator
from apps.blender.resources.imgcompare import check_size


class BlenderVerificator(FrameRenderingVerificator):
    def __init__(self, *args, **kwargs):
        super(BlenderVerificator, self).__init__(*args, **kwargs)
        self.box_size = [1, 1]
        self.compositing = False
        self.output_format = ""
        self.src_code = ""
        self.docker_images = []
        self.verification_timeout = 0

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
            # in this case task will be divided into not equal parts:
            # floor or ceil of (res_y/total_tasks)
            # ceiling will be height of subtasks with smaller num
            ceiling_height = int(math.ceil(self.res_y / self.total_tasks))
            ceiling_subtasks = self.total_tasks - \
                               (ceiling_height * self.total_tasks - self.res_y)
            if subtask_number > ceiling_subtasks:
                res_y = ceiling_height - 1
            else:
                res_y = ceiling_height
        return res_y

    def _check_size(self, file_, res_x, res_y):
        return check_size(file_, res_x, res_y)
