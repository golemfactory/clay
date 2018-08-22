import logging
import math
import os
import random
from copy import deepcopy
from functools import partial
from typing import Dict, Tuple, List, Callable, Optional, Any
from twisted.internet.defer import Deferred, inlineCallbacks

import numpy

from apps.blender.resources.scenefileeditor import generate_blender_crop_file
from golem.core.common import timeout_to_deadline
from golem.task.localcomputer import ComputerAdapter

logger = logging.getLogger("blender_reference_generator")


# FIXME #2086
# pylint: disable=R0903
# pylint: disable=R0902
class VerificationContext:
    def __init__(self, crops_data: Dict[str, Any], computer,
                 subtask_data: Dict[str, Any],
                 callbacks: Dict[str, Callable]) -> None:
        self.crops_path = crops_data['paths']
        self.crops_floating_point_coordinates = crops_data['position'][0]
        self.crops_pixel_coordinates = crops_data['position'][1]
        self.computer = computer
        self.resources = subtask_data['resources']
        self.subtask_info = subtask_data['subtask_info']
        self.success = callbacks['success']
        self.error_callback = callbacks['errback']
        self.crop_size = crops_data['position'][2]

    def get_crop_path(self, crop_number: int) -> str:
        return os.path.join(self.crops_path, str(crop_number))


CropRenderedSuccessCallbackType = Callable[[List[str],
                                            float,
                                            VerificationContext,
                                            int],
                                           None]
CropRenderedFailureCallbackType = Callable[[Exception], None]


class BlenderReferenceGenerator:
    MIN_CROP_SIZE = 8
    CROP_RELATIVE_SIZE = 0.1
    DEFAULT_CROPS_NUMBER = 3

    def __init__(self, computer: Optional[ComputerAdapter] = None) -> None:
        self.computer = computer or ComputerAdapter()
        self.crop_size_in_pixels: Tuple[int, int] = (0, 0)
        self.crops_blender_borders: List[Tuple[float, float, float, float]] = []
        self.crops_pixel_coordinates: List[Tuple[int, int]] = []
        self.rendered_crops_results: Dict[int, List[Any]] = {}
        self.crop_jobs: Dict[str, Deferred] = dict()
        self.stopped = False

    def clear(self):
        self.crop_size_in_pixels = ()
        self.crops_blender_borders = []
        self.crops_pixel_coordinates = []
        self.rendered_crops_results = {}
        self.stopped = False

    # pylint: disable=R0914
    def generate_crops_data(self,
                            resolution: Tuple[int, int],
                            subtask_border: List[float],
                            crops_number: int,
                            crop_size_as_fraction:
                            Optional[Tuple[float, float]]=None):
        """
        This function will generate split data for performing random crops.
        Crops will be rendered from blend files using calculated values
        (floats that indicate position in original blender file).

        :param resolution: This is the x, y resolution of whole image from
        which split data should be generated
        :param subtask_border: List of values. This is ROI from which split data
        should be generated. This is in blender crop values format, which means
        floats, where left, right, top, bottom. Values from 0 to 1. Where 1
        means top or right and 0 bottom or left.
        :param crops_number: Number of split data, sets
        :param crop_size_as_fraction: Crop size, in blender float values, width,
        heightin percentage of particular dimension. Can be none so function
        will calculate smallest possible crop.
        :return: Tuple of two list. First list is filled with float values
        useful for cropping with blender, second one are corresponding
        pixels. Each list has splits_num elements, one for each split.
        """
        subtask_pixel_coordinates = BlenderReferenceGenerator\
            .convert_blender_crop_border_to_pixel_coordinates(subtask_border,
                                                              resolution)

        if crop_size_as_fraction is None:
            self.crop_size_in_pixels = BlenderReferenceGenerator\
                ._get_default_crop_size(resolution)
            crop_size_as_fraction = (
                self.crop_size_in_pixels[0] / resolution[0],
                self.crop_size_in_pixels[1] / resolution[1])
        else:
            self.crop_size_in_pixels = (
                int(crop_size_as_fraction[0] * resolution[0]),
                int(crop_size_as_fraction[1] * resolution[1]))

        for _ in range(crops_number):
            self.generate_single_crop_data(subtask_pixel_coordinates,
                                           resolution)

        return self.crops_blender_borders, \
            self.crops_pixel_coordinates, \
            crop_size_as_fraction

    def generate_single_crop_data(self,
                                  subtask_pixel_coordinates: Dict[str, int],
                                  resolution: Tuple[int, int]) -> None:

        crop_horizontal_pixel_coordinates = BlenderReferenceGenerator \
            ._get_random_interval_within_boundaries(
                subtask_pixel_coordinates["left"],
                subtask_pixel_coordinates["right"],
                self.crop_size_in_pixels[0])

        crop_vertical_pixel_coordinates = BlenderReferenceGenerator \
            ._get_random_interval_within_boundaries(
                subtask_pixel_coordinates["bottom"],
                subtask_pixel_coordinates["top"],
                self.crop_size_in_pixels[1])

        blender_crop_border = BlenderReferenceGenerator \
            .convert_pixel_coordinates_to_blender_crop_border(
                crop_horizontal_pixel_coordinates,
                crop_vertical_pixel_coordinates,
                resolution)

        # Recalculate pixel after converting to float
        crop_horizontal_pixel_coordinates = \
            math.floor(
                blender_crop_border["left"] * numpy.float32(resolution[0])), \
            crop_horizontal_pixel_coordinates[1]

        crop_vertical_pixel_coordinates = crop_vertical_pixel_coordinates[0], \
            math.floor(blender_crop_border["bottom"]
                       * numpy.float32(resolution[1]))

        self.crops_blender_borders.append((blender_crop_border["left"],
                                           blender_crop_border["right"],
                                           blender_crop_border["top"],
                                           blender_crop_border["bottom"]))

        pixel_coordinates = BlenderReferenceGenerator\
            .convert_bitmap_coordinates_to_traditional_y_direction(
                crop_horizontal_pixel_coordinates[0],
                crop_vertical_pixel_coordinates[1],
                subtask_pixel_coordinates["top"])

        self.crops_pixel_coordinates.append(pixel_coordinates)

    @staticmethod
    def convert_blender_crop_border_to_pixel_coordinates(
            subtask_border: List[float],
            resolution: Tuple[int, int]) -> Dict[str, int]:

        logger.debug("Values left=%r, right=%r, top=%r, bottom=%r",
                     subtask_border[0],
                     subtask_border[1],
                     subtask_border[3],
                     subtask_border[2])
        # This is how Blender is calculating pixel check
        # BlenderSync::get_buffer_params in blender_camers.cpp file
        # BoundBox2D border = cam->border.clamp();
        # params.full_x = (int)(border.left * (float)width);

        # NOTE blender uses floats (single precision) while python operates on
        # doubles
        # Here numpy is used to emulate this loss of precision when assigning
        # double to float:
        left = math.floor(
            numpy.float32(subtask_border[0]) * numpy.float32(resolution[0]))

        right = math.floor(
            numpy.float32(subtask_border[1]) * numpy.float32(resolution[0]))

        bottom = math.floor(
            numpy.float32(subtask_border[2]) * numpy.float32(resolution[1]))

        top = math.floor(
            numpy.float32(subtask_border[3]) * numpy.float32(resolution[1]))

        logger.debug("Pixels left=%r, right=%r, top=%r, bottom=%r",
                     left,
                     right,
                     top,
                     bottom)
        return {"left": left, "right": right, "bottom": bottom, "top": top}

    @staticmethod
    def convert_pixel_coordinates_to_blender_crop_border(
            horizontal_pixel_coordinates: Tuple[int, int],
            vertical_pixel_coordinates: Tuple[int, int],
            resolution: Tuple[int, int]) -> Dict[str, float]:

        left = numpy.float32(
            numpy.float32(horizontal_pixel_coordinates[0])
            / numpy.float32(resolution[0]))

        right = numpy.float32(
            numpy.float32(horizontal_pixel_coordinates[1])
            / numpy.float32(resolution[0]))

        top = numpy.float32(
            numpy.float32(vertical_pixel_coordinates[0])
            / numpy.float32(resolution[1]))

        bottom = numpy.float32(
            numpy.float32(vertical_pixel_coordinates[1])
            / numpy.float32(resolution[1]))

        return {"left": left, "right": right, "bottom": bottom, "top": top}

    # pylint: disable-msg=too-many-arguments

    def render_crops(self,
                     resources: List[str],
                     crop_rendered_callback: CropRenderedSuccessCallbackType,
                     crop_render_fail_callback: CropRenderedFailureCallbackType,
                     subtask_info: Dict[str, Any],
                     num_crops: int = DEFAULT_CROPS_NUMBER,
                     crop_size: Optional[Tuple[int, int]] = None) \
            -> Tuple[int, int]:
        crops_path = os.path.join(subtask_info['tmp_dir'],
                                  subtask_info['subtask_id'])
        crops_info = self.generate_crops_data((subtask_info['res_x'],
                                               subtask_info['res_y']),
                                              subtask_info['crop_window'],
                                              num_crops,
                                              crop_size)

        verification_context = \
            VerificationContext({'paths': crops_path,
                                 'position': crops_info},
                                self.computer,
                                {'resources': resources,
                                 'subtask_info': subtask_info},
                                {'success': crop_rendered_callback,
                                 'errback': crop_render_fail_callback})

        self.start(verification_context, crop_render_fail_callback, num_crops)

        return self.crop_size_in_pixels

    # FIXME it would be better to make this subtask agnostic, pass only data
    # needed to generate crops. Drop local computer.
    # Issue # 2447
    # pylint: disable-msg=too-many-arguments
    # pylint: disable=R0914
    @inlineCallbacks
    def start(self,
              verification_context: VerificationContext,
              crop_render_failure: CropRenderedFailureCallbackType,
              crop_count: int) -> None:

        for i in range(0, crop_count):
            if self.stopped:
                break

            minx, maxx, miny, maxy = verification_context \
                .crops_floating_point_coordinates[i]

            script_src = generate_blender_crop_file(
                resolution=(verification_context.subtask_info['res_x'],
                            verification_context.subtask_info['res_y']),
                borders_x=(minx, maxx),
                borders_y=(miny, maxy),
                use_compositing=False,
                samples=verification_context.subtask_info['samples']
            )
            task_definition = BlenderReferenceGenerator\
                .generate_computational_task_definition(
                    verification_context.subtask_info,
                    script_src)

            yield self.schedule_crop_job(verification_context, task_definition,
                                         i, crop_render_failure)

        if not self.stopped:
            for i in range(0, crop_count):
                self.rendered_crops_results[i][2].success(
                    self.rendered_crops_results[i][0],
                    self.rendered_crops_results[i][1],
                    self.rendered_crops_results[i][2], i)

    def schedule_crop_job(self, verification_context, task_definition,
                          crop_number, crop_failure):

        defer = Deferred()

        def success(results: List[str], time_spent: float):
            logger.warning("Success callback %r", crop_number)
            self.rendered_crops_results[crop_number] = [results,
                                                        time_spent,
                                                        verification_context]
            defer.callback(True)

        def failure(exc):
            self.stopped = True
            logger.error(exc)
            defer.errback(False)

        defer.addErrback(crop_failure)

        verification_context.computer.start_computation(
            root_path=verification_context.get_crop_path(crop_number),
            success_callback=success,
            error_callback=failure,
            compute_task_def=task_definition,
            resources=verification_context.resources,
            additional_resources=[]
        )

        return defer

    @staticmethod
    def generate_computational_task_definition(subtask_info: Dict[str, Any],
                                               script_src: str) \
            -> Dict[str, Any]:

        task_definition = deepcopy(subtask_info['ctd'])

        task_definition['extra_data']['outfilebasename'] = \
            "ref_" + subtask_info['outfilebasename']

        task_definition['extra_data']['script_src'] = script_src

        task_definition['deadline'] = timeout_to_deadline(
            subtask_info['subtask_timeout'])

        return task_definition

    @staticmethod
    def _get_random_interval_within_boundaries(begin: int,
                                               end: int,
                                               interval_length: int) \
            -> Tuple[int, int]:

        # survive in edge cases
        end -= 1
        begin += 1
        max_possible_interval_end = (end - interval_length)
        if max_possible_interval_end < 0:
            raise Exception("Subtask is too small for reliable verification")
        interval_begin = random.randint(begin, max_possible_interval_end)
        interval_end = interval_begin + interval_length

        logger.info("interval_begin=%r, interval_end=%r",
                    interval_begin,
                    interval_end)

        return interval_begin, interval_end

    @staticmethod
    def convert_bitmap_coordinates_to_traditional_y_direction(x: int,
                                                              crop_y_max: int,
                                                              top: int) \
            -> Tuple[int, int]:
        # In bitmap terms y=0 is located on top but blender uses classic
        # vertical axis direction with y=0 at the bottom
        y = top - crop_y_max
        logger.info("X=%r, Y=%r", x, y)
        return x, y

    @staticmethod
    def _get_default_crop_size(resolution: Tuple[int, int]) -> Tuple[int, int]:
        x = BlenderReferenceGenerator._calculate_crop_side_length(resolution[0])
        y = BlenderReferenceGenerator._calculate_crop_side_length(resolution[1])
        return x, y

    @staticmethod
    def _calculate_crop_side_length(subtask_side_length: int) -> int:
        # Int rounding, this doesn't have to be exact
        # as long as it works consistently
        calculated_length = int(
            BlenderReferenceGenerator.CROP_RELATIVE_SIZE * subtask_side_length)

        return max(BlenderReferenceGenerator.MIN_CROP_SIZE, calculated_length)
