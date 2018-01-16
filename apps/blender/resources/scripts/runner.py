#!/usr/bin/env python3
import io
import json
import os
import sys

import cv2
import Imath
import numpy as np
import OpenEXR
from PIL import Image
import pywt
from skimage.measure import compare_ssim as ssim

import params  # This module is generated before this script is run

class ImgMetrics:
    """
    ImgMetrics is a structure for storing img comparison metric.
    methods write/load are to facilitate file movement to/from docker.
    """

    def __init__(self, dictionary=None):
        self.imgCorr = None  # for intellisense
        self.SSIM_normal = None
        self.MSE_normal = None
        self.SSIM_canny = None
        self.MSE_canny =None
        self.SSIM_wavelet = None
        self.MSE_wavelet = None
        self.crop_resolution = None
        # ensure that the keys are correct
        keys = ['imgCorr',
                'SSIM_normal', 'MSE_normal',
                'SSIM_canny', 'MSE_canny',
                'SSIM_wavelet', 'MSE_wavelet',
                'crop_resolution']

        for key in keys:
            if key not in dictionary:
                raise KeyError("missing metric:" + key)

        # read into ImgMetrics object
        for key in dictionary:
            setattr(self, key, dictionary[key])

    def to_json(self):
        str_ = json.dumps(self,
                          default=lambda o: o.__dict__,
                          indent=4,
                          sort_keys=True,
                          separators=(',', ': '),
                          ensure_ascii=False)
        return str_


    def write_to_file(self, file_name='img_metrics.txt'):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        file_path = os.path.join(dir_path, file_name)

        data = self.to_json()
        with io.open(file_path, 'w', encoding='utf-8') as f:
            f.write(data)

        return file_path

    @classmethod
    def load_from_file(cls, file_path=None):
        with open(file_path, 'r') as f:
            dictionary = json.load(f)
            img_metrics = cls(dictionary)
            return img_metrics

def compare_crop_window(cropped_img_path,
                        rendered_scene_path,
                        xres, yres,
                        output_filename_path='metrics.txt'):
    """
    This is the entry point for calculation of metrics between the
    rendered_scene and the sample(cropped_img) generated for comparison.
    :param cropped_img_path:
    :param rendered_scene_path:
    :param xres: to match where the cropped_img is located comparing to the
    rendered_scene(full img)
    :param yres: as above
    :param output_filename_path:
    :return:
    """

    cropped_img, scene_crop = \
        _load_and_prepare_img_for_comparison(
            cropped_img_path,
            rendered_scene_path,
            xres, yres)

    img_metrics = compare_images(cropped_img, scene_crop)
    path_to_metrics = img_metrics.write_to_file(output_filename_path)

    return path_to_metrics


def _load_and_prepare_img_for_comparison(cropped_img_path,
                                         rendered_scene_path,
                                         xres, yres):

    """
    This function prepares (i.e. crops) the rendered_scene so that it will
    fit the sample(cropped_img) generated for comparison.
    :param cropped_img_path:
    :param rendered_scene_path:
    :param xres: to match where the cropped_img is located comparing to the
    rendered_scene(full img)
    :param yres: as above
    :return:
    """
    rendered_scene = None
    # if rendered scene has .exr format need to convert it for .png format
    if os.path.splitext(rendered_scene_path)[1] == ".exr":
        check_input = OpenEXR.InputFile(rendered_scene_path).header()[
            'channels']
        if 'RenderLayer.Combined.R' in check_input:
            sys.exit("There is no support for OpenEXR multilayer")
        file_name = "/tmp/scene.png"
        ConvertEXRToPNG(rendered_scene_path, file_name)
        rendered_scene = cv2.imread(file_name)
    elif os.path.splitext(rendered_scene_path)[1] == ".tga":
        file_name = "/tmp/scene.png"
        ConvertTGAToPNG(rendered_scene_path, file_name)
        rendered_scene = cv2.imread(file_name)
    else:
        rendered_scene = cv2.imread(rendered_scene_path)

    cropped_img = cv2.imread(cropped_img_path)
    (crop_height, crop_width) = cropped_img.shape[:2]

    scene_crop = rendered_scene[
                 yres:yres + crop_height,
                 xres:xres + crop_width]

    # print("x, x + crop_width, y, y + crop_height:",
    #       xres, xres + crop_width, yres,
    #       yres + crop_height)
    return cropped_img, scene_crop


def compare_images(image_a, image_b) -> ImgMetrics:
    """
    This the entry point for calculating metrics between image_a, image_b
    once they are cropped to the same size.
    :param image_a:
    :param image_b:
    :return: ImgMetrics
    """

    """imageA/B are images read by: cv2.imread(img.png)"""
    (crop_height, crop_width) = image_a.shape[:2]
    crop_resolution = str(crop_height) + "x" + str(crop_width)

    imageA_canny = cv2.Canny(image_a, 0, 0)
    imageB_canny = cv2.Canny(image_b, 0, 0)

    imageA_wavelet, imageB_wavelet = images_to_wavelet_transform(
        image_a, image_b, mode='db1')

    imgCorr = compare_histograms(image_a, image_b)
    SSIM_normal, MSE_normal = compare_mse_ssim(image_a, image_b)

    SSIM_canny, MSE_canny = compare_images_transformed(
        imageA_canny, imageB_canny)

    SSIM_wavelet, MSE_wavelet = compare_images_transformed(
        imageA_wavelet, imageB_wavelet)

    data = {
        "imgCorr": imgCorr,
        "SSIM_normal": SSIM_normal,
        "MSE_normal": MSE_normal,
        "SSIM_canny": SSIM_canny,
        "MSE_canny": MSE_canny,
        "MSE_wavelet": MSE_wavelet,
        "SSIM_wavelet": SSIM_wavelet,
        "crop_resolution": crop_resolution,
    }

    imgmetrics = ImgMetrics(data)
    return imgmetrics

# converting crop windows to histogram transfrom
def compare_histograms(image_a, image_b):
    color = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    hist_item = 0
    hist_item1 = 0
    for ch, col in enumerate(color):
        hist_item = cv2.calcHist([image_a], [ch], None, [256], [0, 255])
        hist_item1 = cv2.calcHist([image_b], [ch], None, [256], [0, 255])
        cv2.normalize(hist_item, hist_item, 0, 255, cv2.NORM_MINMAX)
        cv2.normalize(hist_item1, hist_item1, 0, 255, cv2.NORM_MINMAX)
    result = cv2.compareHist(hist_item, hist_item1, cv2.HISTCMP_CORREL)
    return result


# MSE metric
def mean_squared_error(image_a, image_b):
    mse = np.sum((image_a.astype("float") - image_b.astype("float")) ** 2)
    mse /= float(image_a.shape[0] * image_a.shape[1])
    return mse


# MSE and SSIM metric for crop windows without any transform
def compare_mse_ssim(image_a, image_b):
    structualSimilarity = 0
    meanSquaredError = mean_squared_error(
        cv2.cvtColor(image_a, cv2.COLOR_BGR2GRAY),
        cv2.cvtColor(image_b, cv2.COLOR_BGR2GRAY))

    structualSim = ssim(
        cv2.cvtColor(image_a, cv2.COLOR_BGR2GRAY),
        cv2.cvtColor(image_b, cv2.COLOR_BGR2GRAY))

    return structualSim, meanSquaredError


# MSE and SSIM metric from crop windows with transform
def compare_images_transformed(image_a, image_b):
    meanSquaredError = mean_squared_error(image_a, image_b)
    structualSim = ssim(image_a, image_b)

    return structualSim, meanSquaredError


# converting crop windows to wavelet transform
def images_to_wavelet_transform(image_a, image_b, mode='db1'):
    image_a = cv2.cvtColor(image_a, cv2.COLOR_BGR2GRAY)
    image_b = cv2.cvtColor(image_b, cv2.COLOR_BGR2GRAY)
    image_a = np.float32(image_a)
    image_b = np.float32(image_b)
    image_a /= 255
    image_b /= 255
    coeffs = pywt.dwt2(image_a, mode)
    coeffs2 = pywt.dwt2(image_b, mode)
    coeffs_H = list(coeffs)
    coeffs_H2 = list(coeffs2)
    coeffs_H[0] *= 0
    coeffs_H2[0] *= 0
    imArray_H = pywt.idwt2(coeffs_H, mode)
    imArray_H *= 255
    imArray_H = np.uint8(imArray_H)
    imArray_H2 = pywt.idwt2(coeffs_H2, mode)
    imArray_H2 *= 255
    imArray_H2 = np.uint8(imArray_H2)
    return imArray_H, imArray_H2

# converting .exr file to .png if user gave .exr file as a rendered scene
def ConvertEXRToPNG(exrfile, pngfile):
    File = OpenEXR.InputFile(exrfile)
    PixType = Imath.PixelType(Imath.PixelType.FLOAT)
    DW = File.header()['dataWindow']
    Size = (DW.max.x - DW.min.x + 1, DW.max.y - DW.min.y + 1)
    rgb = [np.frombuffer(File.channel(c, PixType), dtype=np.float32) for c in
           'RGB']
    for i in range(3):
        rgb[i] = np.where(rgb[i] <= 0.0031308,
                          (rgb[i] * 12.92) * 255.0,
                          (1.055 * (rgb[i] ** (1.0 / 2.4)) - 0.055) * 255.0)
    rgb8 = [Image.frombytes("F", Size, c.tostring()).convert("L") for c in rgb]
    Image.merge("RGB", rgb8).save(pngfile, "PNG")

# converting .tga file to .png if user gave .tga file as a rendered scene
def ConvertTGAToPNG(tgafile, pngfile):
    img = Image.open(tgafile)
    img.save(pngfile)


WORK_DIR = "/golem/work"
OUTPUT_DIR = "/golem/output"

def run_img_compare_task(cropped_img_path,
                        rendered_scene_path,
                        xres, yres):
    """
    This script is run as an entry point for docker.
    It follows the flow of running docker in golem_core.
    It requires cropped_img and rendered_scene to be mounted to the docker.
    The 'params' also must be mounted to the docker.
    Instead of passing the arguments through stdin,
    they are written to 'params.py' file.
    :param cropped_img_path:
    :param rendered_scene_path:
    :param xres:
    :param yres:
    :return:
    """

    # print("Current dir is: %s" %
    #       os.path.dirname(os.path.realpath(__file__)))

    if not os.path.exists(cropped_img_path):
        print("Scene file '{}' does not exist".format(cropped_img_path),
              file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(rendered_scene_path):
        print("Scene file '{}' does not exist".format(rendered_scene_path),
              file=sys.stderr)
        sys.exit(1)

    dir_path = os.path.dirname(os.path.realpath(__file__))
    results_path = os.path.join(dir_path, OUTPUT_DIR[1:])
    # file_path = os.path.join(results_path, 'result.txt' )
    file_path = os.path.join(OUTPUT_DIR, 'result.txt')
    if not os.path.exists(results_path):
        os.makedirs(results_path)

    results_path = compare_crop_window(cropped_img_path,
                                       rendered_scene_path, xres, yres,
                                       output_filename_path=file_path)

    # print(results_path)
    with open(results_path, 'r') as f:
        results = f.read()
        print(results)

run_img_compare_task(params.cropped_img_path,
                     params.rendered_scene_path,
                     params.xres, params.yres)

