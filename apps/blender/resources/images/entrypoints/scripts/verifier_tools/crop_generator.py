import math
import random
from typing import Tuple, Optional, NamedTuple
import numpy

WORK_DIR = "/golem/work"
OUTPUT_DIR = "/golem/output"
CROP_RELATIVE_SIZE = 0.1
MIN_CROP_SIZE = 8


class Resolution(NamedTuple):
    width: int
    height: int


class FloatingPointBox:
    """
    This class stores values of image region expressed with floating point
    numbers as a percentage of image corresponding resolution.
    It mimic blender coordinate system, when trying to render partial image.
    """
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

    def __contains__(self, item: 'FloatingPointBox') -> bool:
        """
       l, t _______
           |    <--|-- self
           |  ____ |
           | |  <-||-- item
           | |____||
           |_______|r, b
        """
        return item.left >= self.left and item.right <= self.right and \
               item.top >= self.top and item.bottom <= self.bottom


class Crop:
    STEP_SIZE = 0.01

    def __init__(
            self,
            id: int,
            resolution: Resolution,
            subtask_box: FloatingPointBox,
            crop_box: Optional[FloatingPointBox] = None
    ):
        self.id = id
        self.resolution = resolution
        self._subtask_box = subtask_box
        self.box = crop_box or self._generate_random_crop_box()
        self._validate_crop_is_within_subtask()

    @property
    def x_pixels(self):
        return self._get_x_coordinates_as_pixels()

    @property
    def y_pixels(self):
        return self._get_y_coordinates_as_pixels()

    def _generate_random_crop_box(self) -> FloatingPointBox:
        crop_width, crop_height = self._get_relative_crop_size()

        print(f'-> subtask_box.left={self._subtask_box.left}')
        print(f'-> subtask_box.right={self._subtask_box.right}')
        print(f'-> subtask_box.top={self._subtask_box.top}')
        print(f'-> subtask_box.bottom={self._subtask_box.bottom}')

        x_beginning, x_end = self._get_coordinate_limits(
            lower_border=self._subtask_box.left,
            upper_border=self._subtask_box.right,
            span=crop_width
        )
        print(f"x_beginning={x_beginning}, x_end={x_end}")

        # left, top is (0,0) in image coordinates
        y_beginning, y_end = self._get_coordinate_limits(
            lower_border=self._subtask_box.top,
            upper_border=self._subtask_box.bottom,
            span=crop_height
        )
        print(f"y_beginning={y_beginning}, y_end={y_end}")

        return FloatingPointBox(
            left=x_beginning,
            right=x_end,
            top=y_beginning,
            bottom=y_end
        )

    @staticmethod
    def _get_coordinate_limits(lower_border, upper_border, span):
        beginning = numpy.float32(random.uniform(lower_border, upper_border - span))
        beginning = max(beginning, lower_border)
        end = min(numpy.float32(beginning + span), upper_border)
        return beginning, end

    def _get_relative_crop_size(self) -> Tuple[float, float]:
        subtask_relative_width = self._subtask_box.right - \
                                 self._subtask_box.left
        subtask_relative_height = self._subtask_box.bottom - \
                                  self._subtask_box.top
        relative_crop_width = numpy.float32(CROP_RELATIVE_SIZE) * numpy.float32(
            subtask_relative_width)
        relative_crop_height = numpy.float32(
            CROP_RELATIVE_SIZE) * numpy.float32(subtask_relative_height)
        print(
            f"initial relative_crop_width: {relative_crop_width}, "
            f"initial relative_crop_height: {relative_crop_height}"
        )
        while numpy.float32(relative_crop_width * self.resolution.width) < MIN_CROP_SIZE:
            relative_crop_width += numpy.float32(self.STEP_SIZE)
        while numpy.float32(relative_crop_height * self.resolution.height) < MIN_CROP_SIZE:
            relative_crop_height += numpy.float32(self.STEP_SIZE)
        print(
            f"relative_crop_width: {relative_crop_width}, "
            f"relative_crop_height: {relative_crop_height}"
        )
        return relative_crop_width, relative_crop_height

    def _validate_crop_is_within_subtask(self):
        if self.box not in self._subtask_box:
            raise ValueError("Crop box is not within subtask box!")

    def _get_x_coordinates_as_pixels(self) -> Tuple[int, int]:
        x_pixel_min = self._calculate_pixel_position(
            self.box.left, self._subtask_box.left, self.resolution.width
        )
        x_pixel_max = self._calculate_pixel_position(
            self.box.right, self._subtask_box.left, self.resolution.width
        )
        print(f"x_pixel_min={x_pixel_min}, x_pixel_max={x_pixel_max}")
        return x_pixel_min, x_pixel_max

    def _get_y_coordinates_as_pixels(self) -> Tuple[int, int]:
        y_pixel_min = self._calculate_pixel_position(
            self._subtask_box.bottom, self.box.bottom, self.resolution.height
        )
        y_pixel_max = self._calculate_pixel_position(
            self._subtask_box.bottom, self.box.top, self.resolution.height
        )
        print(f"y_pixel_min={y_pixel_min}, y_pixel_max={y_pixel_max}")
        return y_pixel_min, y_pixel_max

    @staticmethod
    def _calculate_pixel_position(
        minuend: float,
        subtrahend: float,
        resolution: int,
    ) -> int:
        return math.floor(
            numpy.float32(minuend) * numpy.float32(resolution)
        ) - math.floor(
            numpy.float32(subtrahend) * numpy.float32(resolution)
        )
