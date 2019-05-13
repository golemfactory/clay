import os
import re
# todo review: unused import
from pprint import pprint
from typing import List

import numpy as np
from cv2 import cv2

WHITE = 0
BLACK = 765
OFFSET = 30


def round_to_black_and_white(image: np.ndarray) -> np.ndarray:
    """
    Function for squashing image array in to 0/1 array, which translate to
    black/white pixel
    """
    black_and_white_array = np.zeros((image.shape[0], image.shape[1]))
    for x, row in enumerate(image):
        for y, single_pixel in enumerate(row):
            pixel_sum = np.sum(single_pixel)
            if pixel_sum <= WHITE + OFFSET:
                black_and_white_array[x, y] = 0
            elif pixel_sum >= BLACK - OFFSET:
                black_and_white_array[x, y] = 1
            else:
                raise ValueError("Pixel incomparable. Neither black or white.")
    return black_and_white_array


def cut_out_crop_from_whole_image(
        top_left_corner_x: int,
        top_left_corner_y: int,
        height: int,
        width: int,
        whole_image: np.ndarray
) -> np.ndarray:
    crop_from_image = whole_image[
        top_left_corner_y:top_left_corner_y + height,
        top_left_corner_x:top_left_corner_x + width
    ]
    return crop_from_image


def find_crop_files_in_path(path: str) -> List[str]:
    _, _, files = next(os.walk(path))
    return sorted([os.path.join(path, f) for f in files if
            f.startswith('crop') and f.endswith('.png')])


def find_crops_positions(path_to_log):
    with open(path_to_log) as f:
        lines = f.readlines()

    left_pattern = re.compile(r"^left: (\d+)")
    top_pattern = re.compile(r"^top: (\d+)")

    x0_list = find_match(lines, left_pattern)
    y0_list = find_match(lines, top_pattern)

    return list(zip(x0_list, y0_list))


def find_match(lines, regex_pattern):
    positions = []
    for line in lines:
        match = regex_pattern.match(line)
        if match:
            positions.append(int(match.group(1)))
    return positions


def are_pixels_equal(
        crop_path: str,
        subtask_image_path: str,
        crop_x0: int,
        crop_y0: int,
) -> bool:
    cropped_image = cv2.imread(crop_path)
    subtask_image = cv2.imread(subtask_image_path)
    height, width, _colour = cropped_image.shape

    crop_to_compare = cut_out_crop_from_whole_image(
        crop_x0,
        crop_y0,
        height,
        width,
        subtask_image
    )
    is_result_positive = np.array_equal(
        round_to_black_and_white(cropped_image),
        round_to_black_and_white(crop_to_compare)
    )
    return is_result_positive