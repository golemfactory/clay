import math
import random
import os
import logging
from copy import deepcopy
from functools import partial

from apps.blender.resources.scenefileeditor import generate_blender_crop_file
from golem.core.common import timeout_to_deadline

logger = logging.getLogger("blendercroppper")


# FIXME #2086
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
        self.split_values = []
        self.split_pixels = []

    def clear(self):
        self.crop_counter = 0
        self.crop_size = ()
        self.split_values = []
        self.split_pixels = []

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
        left, right, bottom, top = image_border

        left_p = math.ceil(left * resolution[0])
        right_p = math.ceil(right * resolution[0])
        top_p = math.ceil(top * resolution[1])
        bottom_p = math.ceil(bottom * resolution[1])

        logger.info("Values left=%r, right=%r, top=%r, bottom=%r", left, right,
                    bottom, top)

        logger.info("Pixels left=%r, right=%r, top=%r, bottom=%r", left_p,
                    right_p, bottom_p, top_p)

        if crop_size is None:
            crop_size = (self._find_split_size(resolution[0]),
                         self._find_split_size(resolution[1]))
        else:
            crop_size = (int(crop_size[0] * resolution[0]),
                         int(crop_size[1] * resolution[1]))

        self.crop_size = (crop_size[0]/resolution[0],
                          crop_size[1]/resolution[1])

        # Randomisation cX and Y coordinate to render crop window
        # Blender cropping window from top left. Cropped window pixels
        # 0,0 are in top left
        for _ in range(splits_num):
            split_x = self._random_split(left_p, right_p, crop_size[0])
            split_y = self._random_split(bottom_p, top_p, crop_size[1])
            self.split_values.append((
                split_x[0]/resolution[0],
                split_x[1]/resolution[0],
                split_y[0]/resolution[1],
                split_y[1]/resolution[1]))
            self.split_pixels.append(self._pixel(split_x[0], split_y[1], top_p))
        return self.split_values, self.split_pixels

    # pylint: disable-msg=too-many-arguments
    def render_crops(self, computer, resources, crop_rendered,
                     crop_render_failure, subtask_info,
                     num_crops=3,
                     crop_size=None):
        # pylint: disable=unused-argument

        crops_path = os.path.join(subtask_info['tmp_dir'],
                                  subtask_info['subtask_id'])

        crops_info = self.generate_split_data((subtask_info['res_x'],
                                               subtask_info['res_y']),
                                              subtask_info['crop_window'],
                                              num_crops,
                                              crop_size)
        for _ in range(num_crops):
            verify_ctx = CropContext(crops_info[1], self.crop_counter,
                                     crops_path)
            self._render_one_crop(computer, resources,
                                  crops_info[0][self.crop_counter],
                                  subtask_info, verify_ctx, crop_rendered,
                                  crop_render_failure)
            self.crop_counter += 1
        return self.crop_size

    # FIXME it would be better to make this subtask agnostic, pass only data
    # needed to generate crops. Drop local computer.
    # pylint: disable-msg=too-many-arguments
    # pylint: disable=R0914
    @staticmethod
    def _render_one_crop(computer, resources, crop, subtask_info,
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
        difference = (max_ - size_)
        split_min = random.randint(min_, difference)
        split_max = split_min + size_
        logger.info("split_min=%r, split_max=%r", split_min, split_max)
        return split_min, split_max

    @staticmethod
    def _pixel(crop_x_min, crop_y_max, top):
        # In matrics calculation, y=0 is located on top. Where in blender in
        # bottom. Take then given top and substract it from y_max
        y = top - crop_y_max
        x = crop_x_min
        logger.info("X=%r, Y=%r", x, y)
        return x, y

    @staticmethod
    def _find_split_size(res):
        #  Int rounding, this hasn't to be exact, since its only have to be
        #  precise and constant
        return int(
            max(BlenderCropper.MIN_CROP_RES, BlenderCropper.CROP_STEP * res))
