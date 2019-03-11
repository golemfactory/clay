import math
import random
from typing import Tuple, List
import numpy

WORK_DIR = "/golem/work"
OUTPUT_DIR = "/golem/output"


class Region:

    def __init__(
            self,
            left: float,
            top: float,
            right: float,
            bottom: float
    ) -> None:
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom


class PixelRegion:

    def __init__(self, left: int, top: int, right: int, bottom: int) -> None:
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom


class SubImage:

    CROP_RELATIVE_SIZE = 0.1
    PIXEL_OFFSET = numpy.float32(0.5)
    MIN_CROP_SIZE = 8

    def __init__(self, region: Region, resolution: List[int]) -> None:
        self.region = region
        self.pixel_region = self.calculate_pixels(region, resolution[0],
                                                  resolution[1])
        self.width = self.pixel_region.right - self.pixel_region.left
        self.height = self.pixel_region.top - self.pixel_region.bottom
        self.resolution = resolution

    @staticmethod
    def calculate_pixels(region: Region, width: int,
                         height: int) -> PixelRegion:
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
        # where pixel values are for use in classic coordinate system
        # (left, top is 0,0)

        top = math.floor(
            numpy.float32(region.bottom) * numpy.float32(height) +
            SubImage.PIXEL_OFFSET)

        bottom = math.floor(
            numpy.float32(region.top) * numpy.float32(height) +
            SubImage.PIXEL_OFFSET)

        print("Pixels left=%r, top=%r, right=%r, bottom=%r" % (
            left, top, right, bottom)
             )
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
    def __init__(
            self,
            id_: int,
            subimage: SubImage,
            pixel_region=None,
            crop_region=None
    ) -> None:
        self.id = id_
        self.subimage = subimage
        self.pixel_region = pixel_region
        self.crop_region = crop_region

    @staticmethod
    def create_from_region(id: int, crop_region: Region, subimage: SubImage):
        crop = Crop(id, subimage)
        crop.crop_region = crop_region
        crop.pixel_region = crop.subimage.calculate_pixels(
            crop_region,
            subimage.width,
            subimage.height
        )
        return crop

    @staticmethod
    def create_from_pixel_region(
            id_: int,
            pixel_region: PixelRegion,
            subimage: SubImage
    ) -> 'Crop':
        crop = Crop(id_, subimage)
        crop.pixel_region = pixel_region
        crop.crop_region = crop.calculate_borders(pixel_region,
                                                  subimage.resolution[0],
                                                  subimage.resolution[1])
        return crop

    def get_relative_top_left(self) -> Tuple[int, int]:
        # get top left corner of crop in relation to particular subimage
        print("Sumimag top=%r -  crop.top=%r" % (
            self.subimage.region.top, self.pixel_region.top))
        y = self.subimage.pixel_region.top - self.pixel_region.top
        print("X=%r, Y=%r" % (self.pixel_region.left, y))
        return self.pixel_region.left, y

    @staticmethod
    def calculate_borders(pixel_region: PixelRegion, width: int,
                          height: int) -> Region:

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


def generate_single_random_crop_data_old(
        subimage: SubImage,
        crop_size_px: Tuple[int, int],
        id_: int
) -> Crop:

    crop_horizontal_pixel_coordinates = _get_random_interval_within_boundaries(
        subimage.pixel_region.left,
        subimage.pixel_region.right,
        crop_size_px[0]
    )

    crop_vertical_pixel_coordinates = _get_random_interval_within_boundaries(
        subimage.pixel_region.bottom,
        subimage.pixel_region.top,
        crop_size_px[1]
    )

    crop = Crop.create_from_pixel_region(
        id_,
        PixelRegion(
            crop_horizontal_pixel_coordinates[0],
            crop_vertical_pixel_coordinates[1],
            crop_horizontal_pixel_coordinates[1],
            crop_vertical_pixel_coordinates[0]
        ),
        subimage
    )

    return crop


def _get_random_interval_within_boundaries(
        begin: int,
        end: int,
        interval_length: int
) -> Tuple[int, int]:

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


def generate_single_random_crop_data(  # pylint: disable=too-many-locals
        subimage: SubImage, id_: int
) -> Crop:

    crop_size_x = 0.1
    crop_size_y = 0.1
    # check resolution, make sure that crop is greather then 8px.
    while crop_size_x * subimage.resolution[0] < 8:
        crop_size_x += 0.01
    while crop_size_y * subimage.resolution[1] < 8:
        crop_size_y += 0.01
    print(f"crop_size_x: {crop_size_x}, crop_size_y: {crop_size_y}")

    crop_scene_xmax = subimage.region.right
    crop_scene_xmin = subimage.region.left
    crop_scene_ymax = subimage.region.bottom
    crop_scene_ymin = subimage.region.top

    x_difference = round((crop_scene_xmax - crop_size_x) * 100, 2)
    x_min = random.randint(int(crop_scene_xmin * 100), int(x_difference)) / 100
    x_max = round(x_min + crop_size_x, 2)
    print(f"x_difference={x_difference}, x_min={x_min}, x_max={x_max}")
    y_difference = round((crop_scene_ymax - crop_size_y) * 100, 2)
    y_min = random.randint(int(crop_scene_ymin * 100), int(y_difference)) / 100
    y_max = round(y_min + crop_size_y, 2)
    print(f"y_difference={y_difference}, y_min={y_min}, y_max={y_max}")

    x_pixel_min = math.floor(
        numpy.float32(subimage.resolution[0]) * numpy.float32(x_min)
    )
    x_pixel_min = x_pixel_min - math.floor(
        numpy.float32(crop_scene_xmin) * numpy.float32(subimage.resolution[0])
    )
    x_pixel_max = math.floor(
        numpy.float32(subimage.resolution[0]) * numpy.float32(x_max)
    )
    print(f"x_pixel_min={x_pixel_min}, x_pixel_max={x_pixel_max}")
    y_pixel_max = math.floor(
        numpy.float32(crop_scene_ymax) * numpy.float32(subimage.resolution[1])
    ) - math.floor(
        numpy.float32(subimage.resolution[1]) * numpy.float32(y_max)
    )
    y_pixel_min = math.floor(
        numpy.float32(crop_scene_ymax) * numpy.float32(subimage.resolution[1])
    ) - math.floor(
        numpy.float32(subimage.resolution[1]) * numpy.float32(y_min)
    )
    print(f"y_pixel_max={y_pixel_max}, y_pixel_min={y_pixel_min}")
    crop = Crop(
        id_,
        subimage=subimage,
        pixel_region=PixelRegion(
            left=x_pixel_min,
            right=x_pixel_max,
            top=y_pixel_max,
            bottom=y_pixel_min
        ),
        crop_region=Region(left=x_min, right=x_max, top=y_min, bottom=y_max)
    )

    return crop
