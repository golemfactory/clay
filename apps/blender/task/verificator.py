import random

from golem.core.common import timeout_to_deadline

from apps.rendering.task.verificator import FrameRenderingVerificator
from apps.blender.resources.scenefileeditor import generate_blender_crop_file


class BlenderVerificator(FrameRenderingVerificator):
    def __init__(self, *args, **kwargs):
        super(BlenderVerificator, self).__init__(*args, **kwargs)
        self.box_size = [1, 1]
        self.compositing = False
        self.output_format = ""
        self.src_code = ""
        self.docker_images = ""
        self.verification_timeout = 0

    def change_scope(self, subtask_id, start_box, tr_file, subtask_info):
        extra_data, _ = super(BlenderVerificator, self).change_scope(subtask_id, start_box,
                                                                     tr_file, subtask_info)
        min_x = start_box[0] / float(self.res_x)
        max_x = (start_box[0] + self.verification_options.box_size[0] + 1) / float(self.res_x)
        shift_y = (extra_data['start_task'] - 1) * (self.res_y / float(extra_data['total_tasks']))
        start_y = start_box[1] + shift_y
        max_y = float(self.res_y - start_y) / self.res_y
        shift_y = start_y + self.verification_options.box_size[1] + 1
        min_y = max(float(self.res_y - shift_y) / self.res_y, 0.0)
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

    def query_extra_data_for_advance_verification(self, extra_data):
        ctd = super(BlenderVerificator, self).query_extra_data_for_advance_verification(extra_data)
        ctd.subtask_id = str(random.getrandbits(128))
        ctd.src_code = self.src_code
        ctd.docker_images = self.docker_images
        ctd.deadline = timeout_to_deadline(self.verification_timeout)
