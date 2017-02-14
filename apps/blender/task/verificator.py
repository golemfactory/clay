from apps.rendering.task.verificator import FrameRenderingVerificator
from apps.blender.resources.scenefileeditor import generate_blender_crop_file


class BlenderVerificator(FrameRenderingVerificator):
    def __init__(self, *args, **kwargs):
        super(BlenderVerificator, self).__init__(*args, **kwargs)
        self.box_size = [1, 1]

    def change_scope(self, subtask_id, start_box, tr_file):
        extra_data, _ = super(BlenderVerificator, self).change_scope(self, subtask_id, start_box,
                                                                      tr_file)
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
