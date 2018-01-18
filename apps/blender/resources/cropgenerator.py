import math
import numpy as np
import random

MIN_CROP_RES = 8
CROP_STEP = 0.01

def generate_crops(resolution, crop_scene_window, num_crops):
    res_x, res_y = resolution
    xmin, xmax, ymin, ymax = crop_scene_window

    crop_size_x = find_crop_size(res_x)
    crop_size_y = find_crop_size(res_y)

    blender_crops = []
    blender_crops_pixel = []

    # Randomisation cX and Y coordinate to render crop window
    # Blender cropping window from bottom left. Cropped window pixels
    # 0,0 are in top left
    for crop in range(num_crops):
        crop_x_min, crop_x_max = random_crop(xmin, xmax, crop_size_x)
        crop_y_min, crop_y_max = random_crop(ymin, ymax, crop_size_y)
        blender_crops.append((crop_x_min, crop_x_max, crop_y_min, crop_y_max))
        blender_crops_pixel.append(pixel(res_x, res_y, crop_x_min, crop_y_max,
                                         xmin, ymax))
    return blender_crops, blender_crops_pixel

def random_crop(min_, max_, size_):
    difference = round((max_ - size_) * 100, 2)
    crop_min = random.randint(round(min_ * 100), difference) / 100
    crop_max = round(crop_min + size_, 2)
    return crop_min, crop_max

def pixel(res_x, res_y, crop_x_min, crop_y_max, xmin, ymax):
    x_pixel_min = math.floor(np.float32(res_x) * np.float32(crop_x_min))
    y_pixel_max = math.floor(np.float32(res_y) * np.float32(crop_y_max))
    x_pixel_min = x_pixel_min - math.floor(np.float32(xmin) * np.float32(res_x))
    y_pixel_min = math.floor(np.float32(ymax) * np.float32(res_y)) - y_pixel_max
    return x_pixel_min, y_pixel_min

def find_crop_size(res):
    return max(math.ceil((MIN_CROP_RES / res) * 100) / 100, CROP_STEP)
