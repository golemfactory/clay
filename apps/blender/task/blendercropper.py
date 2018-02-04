import math
import random
import os
import numpy as np

from copy import deepcopy
from functools import partial

from apps.blender.resources.scenefileeditor import generate_blender_crop_file
from golem.core.common import timeout_to_deadline


# pylint: disable=R0903
class CropContext:
    def __init__(self, crops_position, crop_id, crops_path):
        self.crop_id = crop_id
        self.crop_path = os.path.join(crops_path, str(crop_id))
        self.crop_position_x = crops_position[crop_id][0]
        self.crop_position_y = crops_position[crop_id][1]


class BlenderCropper:
    MIN_CROP_RES = 8
    CROP_STEP = 0.01

    def __init__(self):
        self.crop_counter = 0
        self.crop_size = ()

    def generate_split_data(self, resolution, image_border, splits_num,
                            crop_size=None):
        """
        This function will generate split data for performing random crops.
        Crops will be rendered from blend files using calculated values (
        floats that indicate position in original blender file ).

        :param resolution: This is the x, y resolution of whole image from
        which split data should be generated
        :param image_border: List of values. This is ROI from which split data
        should be generated. This is in blender crop values format, which means
        floats, where left, right, top, bottom. Values from 0 to 1. Where 1
        means top or right and 0 bottom or left.
        :param splits_num: Number of split data, sets
        :param crop_size: Crop size, in blender float values, width, height
        in percentage of particular dimension. Can be none so function will
        calculate smallest possible crop.
        :return: Tuple of two list. First list is filled with float values
        useful for cropping with blender, second one are corresponding
        pixels. Each list has splits_num elements, one for each split.
        """
        left, right, top, bottom = image_border

        if crop_size is None:
            self.crop_size = (self.find_split_size(resolution[0]),
                              self.find_split_size(resolution[1]))

        split_values = []
        split_pixels = []

        # Randomisation cX and Y coordinate to render crop window
        # Blender cropping window from top left. Cropped window pixels
        # 0,0 are in top left
        for _ in range(splits_num):
            split_x = self.random_split(left, right, self.crop_size[0])
            split_y = self.random_split(top, bottom, self.crop_size[1])
            split_values.append((split_x[0], split_x[1], split_y[0],
                                 split_y[1]))
            split_pixels.append(self.pixel(resolution, split_x[0], split_y[1],
                                           left, bottom))
        return split_values, split_pixels

    def render_crops(self, computer, resources, crop_rendered,
                     crop_render_failure, subtask_info,
                     num_crops=3,
                     crop_size=None):
        # pylint: disable=unused-argument

        crops_info = self.generate_split_data((subtask_info['res_x'],
                                               subtask_info['res_y']),
                                              subtask_info['crop_window'],
                                              num_crops,
                                              crop_size)
        for num in range(num_crops):
            verify_ctx = CropContext(crops_info[1], self.crop_counter,
                                     self.crops_path)
            self._render_one_crop(computer, resources,
                                  crops_info[0][self.crop_counter],
                                  subtask_info, verify_ctx, crop_rendered,
                                  crop_render_failure)
            self.crop_counter += 1
        return self.crop_size

    # FIXME it would be better to make this subtask agnostic, pass only data
    # needed to generate crops. Drop local computer.
    def _render_one_crop(self, computer, resources, crop, subtask_info,
                         verify_ctx, crop_rendered, crop_render_failure):
        minx, maxx, miny, maxy = crop

        def generate_ctd(subtask_info, script_src):
            ctd = deepcopy(subtask_info['ctd'])

            ctd['extra_data']['outfilebasename'] = \
                "ref_" + subtask_info['outfilebasename']
            ctd['extra_data']['script_src'] = script_src
            ctd['deadline'] = timeout_to_deadline(
                subtask_info['subtask_timeout'])
            return ctd

        script_src = generate_blender_crop_file(
            resolution=(subtask_info['res_x'], subtask_info['res_y']),
            borders_x=(minx, maxx),
            borders_y=(miny, maxy),
            use_compositing=False
        )
        ctd = generate_ctd(subtask_info, script_src)
        # FIXME issue #1955
        computer.start_computation(
            root_path=verify_ctx.crop_path,
            success_callback=partial(crop_rendered,
                                     verification_context=verify_ctx),
            error_callback=crop_render_failure,
            compute_task_def=ctd,
            resources=resources,
            additional_resources=[]
        )

    @staticmethod
    def _random_split(min_, max_, size_):
        difference = round((max_ - size_) * 100, 2)
        split_min = random.randint(int(round(min_ * 100)),
                                   int(difference)) / 100
        split_max = round(split_min + size_, 2)
        return split_min, split_max

    @staticmethod
    def _pixel(res, crop_x_min, crop_y_max, xmin, ymax):
        x_pixel_min = math.floor(np.float32(res[0]) * np.float32(crop_x_min))
        x_pixel_min -= math.floor(np.float32(xmin) * np.float32(res[0]))
        y_pixel_max = math.floor(np.float32(res[1]) * np.float32(crop_y_max))
        y_pixel_min = math.floor(np.float32(ymax) * np.float32(res[1]))
        y_pixel_min -= y_pixel_max
        return x_pixel_min, y_pixel_min

    @staticmethod
    def _find_split_size(res):
        return max(math.ceil((BlenderCropper.MIN_CROP_RES / res) * 100) / 100,
                   BlenderCropper.CROP_STEP)
