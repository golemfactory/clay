import os
from typing import List, Callable

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
        round_to_black_and_white(cropped_image),
        round_to_black_and_white(subtask_fragment_image)
    )
    return is_result_positive
