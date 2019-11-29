import os
from typing import List, Callable

import numpy as np
from cv2 import cv2

ZERO = 0
MAX = 255
ACCEPTABLE_OFFSET = 10


def round_to_pure_colors(image: np.ndarray) -> np.ndarray:
    """
    Function for squashing image array in to 0/255 for each channel, which
    translates to pure colour pixels
    """
    enhanced_colors_array = np.copy(image)
    for x, row in enumerate(image):
        for y, single_pixel in enumerate(row):
            for channel_index, channel in enumerate(single_pixel):
                if channel <= ZERO + ACCEPTABLE_OFFSET:
                    enhanced_colors_array[x, y, channel_index] = ZERO
                elif channel >= MAX - ACCEPTABLE_OFFSET:
                    enhanced_colors_array[x, y, channel_index] = MAX
                else:
                    raise ValueError(
                        "Pixel incomparable. Colour couldn't be identified: "
                        + str(single_pixel)
                    )
    return enhanced_colors_array


def find_crop_files_in_path(path: str) -> List[str]:
    return find_specific_files_in_path(
        path,
        lambda f: f.startswith('crop') and f.endswith('.png')
    )


def find_fragments_in_path(path: str):
    return find_specific_files_in_path(
        path,
        lambda f: f.startswith('fragment_corresponding_to_crop')
                  and f.endswith('.png')
    )


def find_specific_files_in_path(path: str, condition: Callable):
    _, _, files = next(os.walk(path))
    return sorted([os.path.join(path, f) for f in files if condition(f)])


def are_pixels_equal(
        crop_path: str,
        image_fragment_path: str,
) -> bool:
    cropped_image = cv2.imread(crop_path)
    subtask_fragment_image = cv2.imread(image_fragment_path)

    is_result_positive = np.array_equal(
        round_to_pure_colors(cropped_image),
        round_to_pure_colors(subtask_fragment_image)
    )
    return is_result_positive
