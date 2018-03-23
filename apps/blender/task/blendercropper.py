import math
import random
import os
import logging
import numpy
from copy import deepcopy
from functools import partial

from apps.blender.resources.scenefileeditor import generate_blender_crop_file
from golem.core.common import timeout_to_deadline

logger = logging.getLogger("blendercroppper")


# FIXME #2086
# pylint: disable=R0903
class CropContext:
    def __init__(self, crops_data, computer,
                 subtask_data, callbacks):
        self.crops_path = crops_data['paths']
        self.crop_values = crops_data['position'][0]
        self.crop_pixels = crops_data['position'][1]
        self.computer = computer
        self.resources = subtask_data['resources']
        self.subtask_info = subtask_data['subtask_info']
        self.success = callbacks['success']
        self.errback = callbacks['errback']
        self.crop_size = crops_data['position'][2]

    def get_crop_path(self, crop_number):
        return os.path.join(self.crops_path, str(crop_number))


class BlenderCropper:
    MIN_CROP_RES = 8
    CROP_STEP = 0.01

    def __init__(self):
        self.crop_counter = 0
        self.crop_size = ()
        self.split_values = []
        self.split_pixels = []
        self.rendered_crops_results = {}

    def clear(self):
        self.crop_counter = 0
        self.crop_size = ()
        self.split_values = []
        self.split_pixels = []
        self.rendered_crops_results = {}

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
        logger.info("Values left=%r, right=%r, top=%r, bottom=%r",
                    image_border[0], image_border[1], image_border[3],
                    image_border[2])

        #  This is how Blender is calculating pixel check
        #  BlenderSync::get_buffer_params in blender_camers.cpp file
        #  BoundBox2D border = cam->border.clamp();
        #  params.full_x = (int)(border.left * (float)width);
        #
        #  NOTE BLENDER IS USING FLOATS Vgit stALUES
        #  that means single precision 4 bytes floats, python is not
        #  it is using double precision values. Here numpy is used to emulate
        #  that loss of precision when assigning double to float.
        left_p = math.floor(numpy.float32(image_border[0]) *
                            numpy.float32(resolution[0]))
        right_p = math.floor(numpy.float32(image_border[1]) *
                             numpy.float32(resolution[0]))
        bottom_p = math.floor(numpy.float32(image_border[2]) *
                              numpy.float32(resolution[1]))
        top_p = math.floor(numpy.float32(image_border[3]) *
                           numpy.float32(resolution[1]))

        logger.info("Pixels left=%r, right=%r, top=%r, bottom=%r", left_p,
                    right_p, top_p, bottom_p)

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

            # Here another conversion from double to float
            x_f = numpy.float32(numpy.float32(split_x[0])
                                / numpy.float32(resolution[0]))
            right_f = numpy.float32(numpy.float32(split_x[1]) /
                                    numpy.float32(resolution[0]))
            y_f = numpy.float32(numpy.float32(split_y[0])
                                / numpy.float32(resolution[1]))
            bottom_f = numpy.float32(numpy.float32(split_y[1])
                                     / numpy.float32(resolution[1]))

            # Recalculate pixel after converting to float
            split_x[0] = math.floor(x_f * numpy.float32(resolution[0]))
            split_y[1] = math.floor(bottom_f * numpy.float32(resolution[1]))

            self.split_values.append((x_f, right_f, y_f, bottom_f))
            self.split_pixels.append(self._pixel(split_x[0], split_y[1], top_p))
        return self.split_values, self.split_pixels, self.crop_size

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

        verify_ctx = CropContext({'paths': crops_path, 'position': crops_info},
                                 computer,
                                 {'resources': resources,
                                  'subtask_info': subtask_info},
                                 {'success': crop_rendered,
                                  'errback': crop_render_failure})
        self._render_one_crop(verify_ctx, self.crop_rendered,
                              crop_render_failure, self.crop_counter)
        self.crop_counter += 1
        return self.crop_size

    # FIXME it would be better to make this subtask agnostic, pass only data
    # needed to generate crops. Drop local computer.
    # Issue # 2447
    # pylint: disable-msg=too-many-arguments
    # pylint: disable=R0914
    @staticmethod
    def _render_one_crop(verify_ctx, crop_rendered, crop_render_failure,
                         crop_number):
        minx, maxx, miny, maxy = verify_ctx.crop_values[crop_number]

        def generate_ctd(subtask_info, script_src):
            ctd = deepcopy(subtask_info['ctd'])

            ctd['extra_data']['outfilebasename'] = \
                "ref_" + subtask_info['outfilebasename']
            ctd['extra_data']['script_src'] = script_src
            ctd['deadline'] = timeout_to_deadline(
                subtask_info['subtask_timeout'])
            return ctd

        script_src = generate_blender_crop_file(
            resolution=(verify_ctx.subtask_info['res_x'],
                        verify_ctx.subtask_info['res_y']),
            borders_x=(minx, maxx),
            borders_y=(miny, maxy),
            use_compositing=False
        )
        ctd = generate_ctd(verify_ctx.subtask_info, script_src)
        # FIXME issue #1955
        verify_ctx.computer.start_computation(
            root_path=verify_ctx.get_crop_path(crop_number),
            success_callback=partial(crop_rendered,
                                     verification_context=verify_ctx),
            error_callback=crop_render_failure,
            compute_task_def=ctd,
            resources=verify_ctx.resources,
            additional_resources=[]
        )

    def crop_rendering_finished(self):
        for i in range(1, 4):
            self.rendered_crops_results[i][2].success(
                self.rendered_crops_results[i][0],
                self.rendered_crops_results[i][1],
                self.rendered_crops_results[i][2], i-1)

    def crop_rendered(self, results, time_spend, verification_context):
        self.rendered_crops_results[self.crop_counter] \
            = [results, time_spend, verification_context]
        if self.crop_counter == 3:
            self.crop_rendering_finished()
            return

        self._render_one_crop(verification_context, self.crop_rendered,
                              verification_context.errback, self.crop_counter)
        self.crop_counter += 1

    @staticmethod
    def _random_split(min_, max_, size_):
        # survive in edge cases
        max_ -= 1
        min_ += 1
        difference = (max_ - size_)
        if difference < 0:
            raise Exception("Subtask is to small to reliable verifcation")
        split_min = random.randint(min_, difference)
        split_max = split_min + size_
        logger.info("split_min=%r, split_max=%r", split_min, split_max)
        return [split_min, split_max]

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
