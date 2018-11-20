import logging
import math
import os
import random
from copy import deepcopy
from typing import Dict, Tuple, List, Callable, Optional, Any, Generator
from twisted.internet.defer import Deferred, inlineCallbacks

import numpy

from apps.blender.resources.scenefileeditor import generate_blender_crop_file
from golem.core.common import timeout_to_deadline
from golem.task.localcomputer import ComputerAdapter

logger = logging.getLogger("apps.blender.blender_reference_generator")


class Region:

    def __init__(self, left: float = -1, top: float = -1, right: float = -1,
                 bottom: float = -1) -> None:
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom

    def to_tuple(self):
        return self.left, self.top, self.right, self.bottom


class PixelRegion:

    def __init__(self, left: int = -1, top: int = -1, right: int = -1,
                 bottom: int = -1) -> None:
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom


class SubImage:

    CROP_RELATIVE_SIZE = 0.1
    PIXEL_OFFSET = numpy.float32(0.5)
    MIN_CROP_SIZE = 8

    def __init__(self, region: Region, resolution: Tuple[int, int]) -> None:
        self.region = region
        self.pixel_region = self.calculate_pixels(region, resolution[0],
                                                  resolution[1])
        self.width = self.pixel_region.right - self.pixel_region.left
        self.height = self.pixel_region.top - self.pixel_region.bottom
        self.image_width = resolution[0]
        self.image_height = resolution[1]

    @staticmethod
    def calculate_pixels(region: Region, width: int, height: int) \
            -> PixelRegion:
        #  This is how Blender is calculating pixel, check
        #  BlenderSync::get_buffer_params in blender_camera.cpp file
        #  BoundBox2D border = cam->border.clamp();
        #  params.full_x = (int)(border.left * (float)width);

        #  NOTE blender uses floats (single precision) while python operates on
        #  doubles
        #  Here numpy is used to emulate this loss of precision when assigning
        #  double to float:
        left = math.floor(
            numpy.float32(region.left) * numpy.float32(width) +
            SubImage.PIXEL_OFFSET)

        right = math.floor(
            numpy.float32(region.right) * numpy.float32(width) +
            SubImage.PIXEL_OFFSET)

        bottom = math.floor(
            numpy.float32(region.bottom) * numpy.float32(height) +
            SubImage.PIXEL_OFFSET)

        top = math.floor(
            numpy.float32(region.top) * numpy.float32(height) +
            SubImage.PIXEL_OFFSET)

        return PixelRegion(int(left), int(top), int(right), int(bottom))

    @staticmethod
    def __calculate_crop_side_length(subtask_side_length: int) -> int:
        calculated_length = int(
            SubImage.CROP_RELATIVE_SIZE * subtask_side_length)

        return max(SubImage.MIN_CROP_SIZE, calculated_length)

    def get_default_crop_size(self) -> Tuple[int, int]:
        x = self.__calculate_crop_side_length(self.width)
        y = self.__calculate_crop_side_length(self.height)
        return x, y


class Crop:

    @staticmethod
    def create_from_region(crop_id: str, crop_region: Region,
                           subimage: SubImage,
                           crops_path: str):
        crop = Crop(crop_id, subimage, crops_path)
        crop.crop_region = crop_region
        crop.pixel_region = crop.subimage.calculate_pixels(
            crop_region, subimage.image_width, subimage.image_height)
        return crop

    @staticmethod
    def create_from_pixel_region(crop_id: str, pixel_region: PixelRegion,
                                 subimage: SubImage, crops_path: str):
        crop = Crop(crop_id, subimage, crops_path)
        crop.pixel_region = pixel_region
        crop.crop_region = crop.calculate_borders()
        return crop

    def __init__(self, crop_id: str, subimage: SubImage, crops_path: str)\
            -> None:
        self.crop_id = crop_id
        self.subimage = subimage
        self.crop_path = os.path.join(crops_path, crop_id)
        self.pixel_region = PixelRegion()
        self.crop_region = Region()

    def get_relative_top_left(self) -> Tuple[int, int]:
        # get top left corner of crop in relation to particular subimage
        y = self.subimage.pixel_region.top - self.pixel_region.top
        logger.debug("X=%r, Y=%r", self.pixel_region.left, y)
        return self.pixel_region.left, y

    def calculate_borders(self):

        left = numpy.float32(
            (numpy.float32(self.pixel_region.left) + SubImage.PIXEL_OFFSET) /
            numpy.float32(self.subimage.image_width))

        right = numpy.float32(
            (numpy.float32(self.pixel_region.right) + SubImage.PIXEL_OFFSET) /
            numpy.float32(self.subimage.image_width))

        top = numpy.float32(
            (numpy.float32(self.pixel_region.top) + SubImage.PIXEL_OFFSET) /
            numpy.float32(self.subimage.image_height))

        bottom = numpy.float32(
            (numpy.float32(self.pixel_region.bottom) + SubImage.PIXEL_OFFSET) /
            numpy.float32(self.subimage.image_height))

        return Region(left, top, right, bottom)

    def get_path(self):
        return self.crop_path


# FIXME #2086
# pylint: disable=R0903
# pylint: disable=R0902
class VerificationContext:
    def __init__(self, crops_descriptors: List[Crop], computer,
                 subtask_data: Dict[str, Any], crops_number) -> None:
        self.crops = crops_descriptors
        self.computer = computer
        self.resources = subtask_data['resources']
        self.subtask_info = subtask_data['subtask_info']
        self.finished = [Deferred() for _ in range(crops_number)]

    def get_crop_path(self, crop_id: str) -> Optional[str]:
        crop = self.get_crop_with_id(crop_id)
        if crop:
            return crop.get_path()
        return None

    def get_crop_with_id(self, crop_id: str) -> Optional[Crop]:
        for crop in self.crops:
            if crop.crop_id == crop_id:
                return crop
        return None


CropRenderedSuccessCallbackType = Callable[[List[str],
                                            float,
                                            VerificationContext,
                                            int],
                                           None]
CropRenderedFailureCallbackType = Callable[[Exception], None]


class BlenderReferenceGenerator:
    DEFAULT_CROPS_NUMBER = 3

    def __init__(self, computer: Optional[ComputerAdapter] = None) -> None:
        self.computer = computer or ComputerAdapter()
        self.crops_desc: List[Crop] = []
        self.rendered_crops_results: Dict[int, List[Any]] = {}
        self.crop_jobs: Dict[str, Deferred] = dict()
        self.stopped = False

    def clear(self):
        self.rendered_crops_results = {}
        self.stopped = False

    # pylint: disable=R0914
    def generate_crops_data(self,
                            resolution: Tuple[int, int],
                            subtask_border: List[float],
                            crops_number: int, crops_path: str):
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
        :param crops_path: base crop path
        :return: Tuple of two list. First list is filled with float values
        useful for cropping with blender, second one are corresponding
        pixels. Each list has splits_num elements, one for each split.
        """

        logger.debug("Subtasks borders left = %r,"
                     " top = %r, right = %r, bottom=%r",
                     subtask_border[0], subtask_border[3],
                     subtask_border[1], subtask_border[2])

        subimage = SubImage(Region(subtask_border[0],
                                   subtask_border[3],
                                   subtask_border[1],
                                   subtask_border[2]), resolution)

        for i in range(crops_number):
            self.crops_desc.append(
                BlenderReferenceGenerator.generate_single_random_crop_data(
                    subimage,
                    subimage.get_default_crop_size(),
                    str(i), crops_path))

        return self.crops_desc

    @staticmethod
    def generate_single_random_crop_data(subimage: SubImage,
                                         crop_size_px: Tuple[int, int],
                                         crop_id: str,
                                         crops_path: str) \
            -> Crop:

        crop_horizontal_pixel_coordinates = \
            BlenderReferenceGenerator._get_random_interval_within_boundaries(
                subimage.pixel_region.left,
                subimage.pixel_region.right,
                crop_size_px[0])

        crop_vertical_pixel_coordinates = \
            BlenderReferenceGenerator._get_random_interval_within_boundaries(
                subimage.pixel_region.bottom,
                subimage.pixel_region.top,
                crop_size_px[1])

        crop = Crop.create_from_pixel_region(crop_id, PixelRegion(
            crop_horizontal_pixel_coordinates[0],
            crop_vertical_pixel_coordinates[1],
            crop_horizontal_pixel_coordinates[1],
            crop_vertical_pixel_coordinates[0]), subimage, crops_path)

        return crop

    @staticmethod
    def _get_random_interval_within_boundaries(begin: int,
                                               end: int,
                                               interval_length: int) \
            -> Tuple[int, int]:

        # survive in edge cases
        end -= 1
        begin += 1

        logger.debug("begin %r, end %r", begin, end)

        max_possible_interval_end = (end - interval_length)
        if max_possible_interval_end < 0:
            raise Exception("Subtask is too small for reliable verification")
        interval_begin = random.randint(begin, max_possible_interval_end)
        interval_end = interval_begin + interval_length
        return interval_begin, interval_end

    # pylint: disable-msg=too-many-arguments

    def render_crops(self,
                     resources: List[str],
                     subtask_info: Dict[str, Any],
                     num_crops: int = DEFAULT_CROPS_NUMBER) -> List[Deferred]:
        crops_path = os.path.join(subtask_info['tmp_dir'],
                                  subtask_info['subtask_id'])
        crops_descriptors = self.generate_crops_data(
            (subtask_info['res_x'], subtask_info['res_y']),
            subtask_info['crop_window'],
            num_crops, crops_path)

        verification_context = \
            VerificationContext(crops_descriptors,
                                self.computer,
                                {'resources': resources,
                                 'subtask_info': subtask_info}, num_crops)

        self.start(verification_context, num_crops)

        return verification_context.finished

    # FIXME it would be better to make this subtask agnostic, pass only data
    # needed to generate crops. Drop local computer.
    # Issue # 2447
    # pylint: disable-msg=too-many-arguments
    # pylint: disable=R0914
    @inlineCallbacks
    def start(self,
              verification_context: VerificationContext,
              crop_count: int) -> Generator:

        for i in range(0, crop_count):
            if self.stopped:
                break

            crop = verification_context.get_crop_with_id(str(i))
            if not crop:
                raise Exception("Crop %s not found " % i)

            left, top, right, bottom = crop.calculate_borders().to_tuple()

            script_src = generate_blender_crop_file(
                resolution=(verification_context.subtask_info['res_x'],
                            verification_context.subtask_info['res_y']),
                borders_x=(left, right),
                borders_y=(bottom, top),
                use_compositing=False,
                samples=verification_context.subtask_info['samples']
            )
            task_definition = BlenderReferenceGenerator\
                .generate_computational_task_definition(
                    verification_context.subtask_info,
                    script_src)

            yield self.schedule_crop_job(verification_context, task_definition,
                                         i)

        if not self.stopped:
            for i in range(0, crop_count):
                verification_context.finished[i].callback((
                    self.rendered_crops_results[i][0],
                    self.rendered_crops_results[i][1],
                    self.rendered_crops_results[i][2], i))

    def stop(self):
        self.stopped = True

    def schedule_crop_job(self, verification_context, task_definition,
                          crop_number):

        defer = Deferred()

        def success(results: List[str], time_spent: float):
            self.rendered_crops_results[crop_number] = [results,
                                                        time_spent,
                                                        verification_context]
            defer.callback(True)

        def failure(exc):
            self.stopped = True
            logger.error(exc)
            verification_context.finished[crop_number].errback(False)

        path = verification_context.get_crop_path(str(crop_number))
        if not path:
            raise Exception("Crop %s not found " % crop_number)

        verification_context.computer.start_computation(
            root_path=path,
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
