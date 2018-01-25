import math
import random

import numpy as np

MIN_CROP_RES = 8
CROP_STEP = 0.01


def generate_crops(resolution, crop_scene_window, num_crops,
                   crop_size=None):
    xmin, xmax, ymin, ymax = crop_scene_window

    if crop_size is None:
        crop_size = (find_crop_size(resolution[0]),
                     find_crop_size(resolution[1]))

    blender_crops = []
    blender_crops_pixel = []

    # Randomisation cX and Y coordinate to render crop window
    # Blender cropping window from bottom left. Cropped window pixels
    # 0,0 are in top left
    for _ in range(num_crops):
        crop_x = random_crop(xmin, xmax, crop_size[0])
        crop_y = random_crop(ymin, ymax, crop_size[1])
        blender_crops.append((crop_x[0], crop_x[1], crop_y[0], crop_y[1]))
        blender_crops_pixel.append(pixel(resolution, crop_x[0], crop_y[1],
                                         xmin, ymax))
    return blender_crops, blender_crops_pixel


def random_crop(min_, max_, size_):
    difference = round((max_ - size_) * 100, 2)
    crop_min = random.randint(round(min_ * 100), difference) / 100
    crop_max = round(crop_min + size_, 2)
    return crop_min, crop_max


def pixel(res, crop_x_min, crop_y_max, xmin, ymax):
    x_pixel_min = math.floor(np.float32(res[0]) * np.float32(crop_x_min))
    x_pixel_min -= math.floor(np.float32(xmin) * np.float32(res[0]))
    y_pixel_max = math.floor(np.float32(res[1]) * np.float32(crop_y_max))
    y_pixel_min = math.floor(np.float32(ymax) * np.float32(res[1]))
    y_pixel_min -= y_pixel_max
    return x_pixel_min, y_pixel_min


def find_crop_size(res):
    return max(math.ceil((MIN_CROP_RES / res) * 100) / 100, CROP_STEP)
