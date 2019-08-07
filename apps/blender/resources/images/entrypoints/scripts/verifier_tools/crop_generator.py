import os
import numpy
import math
import random
from typing import Dict, Tuple, List, Optional

WORK_DIR = "/golem/work"
OUTPUT_DIR = "/golem/output"

class Region:

    def __init__(self, left: float, top: float, right: float, bottom: float):
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom

class PixelRegion:

    def __init__(self, left: int, top: int, right: int, bottom: int):
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom

class SubImage:

    CROP_RELATIVE_SIZE = 0.1
    PIXEL_OFFSET = numpy.float32(0.5)
    MIN_CROP_SIZE = 8

    def __init__(self, region: Region, resolution: List[int]):
        self.region = region
        self.pixel_region = self.calculate_pixels(region, resolution[0], resolution[1])
        self.width = self.pixel_region.right - self.pixel_region.left
        self.height = self.pixel_region.top - self.pixel_region.bottom
        self.resolution = resolution

    def calculate_pixels(self, region: Region, width: int, height: int) -> None:
        # This is how Blender is calculating pixel, check
        # BlenderSync::get_buffer_params in blender_camera.cpp file
        # BoundBox2D border = cam->border.clamp();
        # params.full_x = (int)(border.left * (float)width);

        # NOTE blender uses floats (single precision) while python operates on
        # doubles
        # Here numpy is used to emulate this loss of precision when assigning
        # double to float:
        left = math.floor(
            numpy.float32(region.left) * numpy.float32(width) +
            SubImage.PIXEL_OFFSET)

        right = math.floor(
            numpy.float32(region.right) * numpy.float32(width) +
            SubImage.PIXEL_OFFSET)

        # NOTE we are exchanging here top with bottom, because borders
        # in blender are in OpenGL UV coordinate system (left, bottom is 0,0)
        # where pixel values are for use in classic coordinate system (left, top is 0,0)

        top = math.floor(
            numpy.float32(region.bottom) * numpy.float32(height) +
            SubImage.PIXEL_OFFSET)

        bottom = math.floor(
            numpy.float32(region.top) * numpy.float32(height) +
            SubImage.PIXEL_OFFSET)

        print("Pixels left=%r, top=%r, right=%r, bottom=%r" %
                        (left, top, right, bottom))
        return PixelRegion(left, top, right, bottom)

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
    def create_from_region(id: int, crop_region: Region, subimage: SubImage):
        crop = Crop(id, subimage)
        crop.crop_region = crop_region
        crop.pixel_region = crop.subimage.calculate_pixels(crop_region,
          subimage.width, subimage.height)
        return crop

    @staticmethod
    def create_from_pixel_region(id: int, pixel_region: PixelRegion, subimage: SubImage):
        crop = Crop(id, subimage)
        crop.pixel_region = pixel_region
        crop.crop_region = crop.calculate_borders(pixel_region, subimage.resolution[0], subimage.resolution[1])
        return crop

    def __init__(self, id: int, subimage: SubImage):
        self.id = id
        self.subimage = subimage
        self.pixel_region = None
        self.crop_region = None

    def get_relative_top_left(self) \
        -> Tuple[int, int]:
        # get top left corner of crop in relation to particular subimage
        print("Sumimag top=%r -  crop.top=%r" % (self.subimage.region.top, self.pixel_region.top))
        y = self.subimage.pixel_region.top - self.pixel_region.top
        print("X=%r, Y=%r" % (self.pixel_region.left, y))
        return self.pixel_region.left, y

    def calculate_borders(self, pixel_region: PixelRegion, width: int, height: int):

        left = numpy.float32(
            (numpy.float32(pixel_region.left) + SubImage.PIXEL_OFFSET) /
            numpy.float32(width))

        right = numpy.float32(
            (numpy.float32(pixel_region.right) + SubImage.PIXEL_OFFSET) /
            numpy.float32(width))

        bottom = numpy.float32(
            (numpy.float32(pixel_region.top) + SubImage.PIXEL_OFFSET) /
            numpy.float32(height))

        top = numpy.float32(
            (numpy.float32(pixel_region.bottom) + SubImage.PIXEL_OFFSET) /
            numpy.float32(height))

        return Region(left, top, right, bottom)

def generate_single_random_crop_data(subimage: SubImage, crop_size_px: Tuple[int, int], id: int) \
     -> Crop:

    crop_horizontal_pixel_coordinates = _get_random_interval_within_boundaries(
            subimage.pixel_region.left,
            subimage.pixel_region.right,
            crop_size_px[0])

    crop_vertical_pixel_coordinates = _get_random_interval_within_boundaries(
            subimage.pixel_region.bottom,
            subimage.pixel_region.top,
            crop_size_px[1])

    crop = Crop.create_from_pixel_region(id, PixelRegion(
        crop_horizontal_pixel_coordinates[0],
        crop_vertical_pixel_coordinates[1],
        crop_horizontal_pixel_coordinates[1],
        crop_vertical_pixel_coordinates[0]), subimage)

    return crop

def _get_random_interval_within_boundaries(begin: int,
                                            end: int,
                                            interval_length: int) \
        -> Tuple[int, int]:

    # survive in edge cases
    end -= 1
    begin += 1

    print("begin %r, end %r" % (begin, end))

    max_possible_interval_end = (end - interval_length)
    if max_possible_interval_end < 0:
        raise Exception("Subtask is too small for reliable verification")
    interval_begin = random.randint(begin, max_possible_interval_end)
    interval_end = interval_begin + interval_length
    return interval_begin, interval_end
