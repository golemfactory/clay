import argparse
from argparse import RawTextHelpFormatter
import sys
from apps.blender.task.reference_img_generator import generate_random_crop
import cv2
import datetime
import numpy as np
import os
from skimage.measure import compare_ssim as ssim
import pandas as pd
import pywt
import OpenEXR
import Imath
from PIL import Image

from apps.rendering.resources.imgrepr import (ImgRepr, PILImgRepr)

# todo GG this is from CP, run cv2 in docker

lp = []
cord_list = []
ssim_list = []
corr_list = []
mse_list = []
ssim_canny_list = []
ssim_wavelet_list = []
mse_wavelet_list = []
mse_canny_list = []
resolution_list = []

# converting crop windows to histogram transfrom
def compare_histograms(imageA, imageB):
    color = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    hist_item = 0
    hist_item1 = 0
    for ch, col in enumerate(color):
        hist_item = cv2.calcHist([imageA], [ch], None, [256], [0, 255])
        hist_item1 = cv2.calcHist([imageB], [ch], None, [256], [0, 255])
        cv2.normalize(hist_item, hist_item, 0, 255, cv2.NORM_MINMAX)
        cv2.normalize(hist_item1, hist_item1, 0, 255, cv2.NORM_MINMAX)
    result = cv2.compareHist(hist_item, hist_item1, cv2.HISTCMP_CORREL)
    return result

# MSE metric
def mean_squared_error(imageA, imageB):
    mse = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
    mse /= float(imageA.shape[0] * imageA.shape[1])
    return mse

# MSE and SSIM metric for crop windows without any transform
def compare_images(imageA, imageB):
    structualSimilarity = 0
    meanSquaredError = mean_squared_error(cv2.cvtColor(
        imageA, cv2.COLOR_BGR2GRAY), cv2.cvtColor(imageB, cv2.COLOR_BGR2GRAY))
    structualSim = ssim(cv2.cvtColor(imageA, cv2.COLOR_BGR2GRAY),
                        cv2.cvtColor(imageB, cv2.COLOR_BGR2GRAY))
    return structualSim, meanSquaredError

# MSE and SSIM metric from crop windows with transform
def compare_images_transformed(imageA, imageB):
    meanSquaredError = mean_squared_error(imageA, imageB)
    structualSim = ssim(imageA, imageB)
    return structualSim, meanSquaredError

# converting crop windows to wavelet transform
def images_to_wavelet_transform(imageA, imageB, mode='db1'):
    imageA = cv2.cvtColor(imageA, cv2.COLOR_BGR2GRAY)
    imageB = cv2.cvtColor(imageB, cv2.COLOR_BGR2GRAY)
    imageA = np.float32(imageA)
    imageB = np.float32(imageB)
    imageA /= 255
    imageB /= 255
    coeffs = pywt.dwt2(imageA, mode)
    coeffs2 = pywt.dwt2(imageB, mode)
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

def compare_crop_window(crop, scene, xres, yres, crop_percentages, resolution):
    crop = cv2.imread(crop)
    crop_canny = cv2.Canny(crop, 0, 0)
    x_min = crop_percentages[0]
    x_max = crop_percentages[1]
    y_min = crop_percentages[2]
    y_max = crop_percentages[3]
    print(x_min, x_max, y_min, y_max)
    (crop_hight, crop_width) = crop.shape[:2]
    print("crop hight and width:", crop_hight, crop_width)
    scene_crop = scene[yres:yres + crop_hight, xres:xres + crop_width]
    print(xres, xres + crop_width, yres, yres + crop_hight)
    scene_crop_canny = cv2.Canny(scene_crop, 0, 0)
    imgCorr = compare_histograms(crop, scene_crop)
    SSIM_normal, MSE_normal = compare_images(crop, scene_crop)
    SSIM_canny, MSE_canny = compare_images_transformed(
        crop_canny, scene_crop_canny)
    crop_wavelet, scene_wavelet = images_to_wavelet_transform(
        crop, scene_crop, mode='db1')
    SSIM_wavelet, MSE_wavelet = compare_images_transformed(
        crop_wavelet, scene_wavelet)
    i = len(cord_list) + 1
    lp.append(i)
    cord = str(xres) + "x" + str(yres)
    cord_list.append(cord)
    ssim_list.append(SSIM_normal)
    corr_list.append(imgCorr)
    mse_list.append(MSE_normal)
    mse_wavelet_list.append(MSE_wavelet)
    ssim_wavelet_list.append(SSIM_wavelet)
    ssim_canny_list.append(SSIM_canny)
    resolution = str(crop_hight) + "x" + str(crop_width)
    resolution_list.append(resolution)
    mse_canny_list.append(MSE_canny)
    print("CORR:", imgCorr, "SSIM:", SSIM_normal, "MSE:", MSE_normal, "CANNY:",
          SSIM_canny, "SSIM_wavelet:", SSIM_wavelet, "MSE_wavelet:", MSE_wavelet)
    return [imgCorr, SSIM_normal, MSE_normal, SSIM_canny, SSIM_wavelet, MSE_wavelet]

# counting average of all tests
def average_of_each_measure(measure_lists, number_of_tests):
    corr_value = 0
    ssim_value = 0
    mse_value = 0
    ssim_canny_value = 0
    ssim_wavelet_value = 0
    mse_wavelet_value = 0
    for measure_list in measure_lists:
        corr_value += measure_list[0]
        ssim_value += measure_list[1]
        mse_value += measure_list[2]
        ssim_canny_value += measure_list[3]
        ssim_wavelet_value += measure_list[4]
        mse_wavelet_value += measure_list[5]
    corr_average = corr_value / number_of_tests
    ssim_average = ssim_value / number_of_tests
    mse_average = mse_value / number_of_tests
    ssim_canny_average = ssim_canny_value / number_of_tests
    ssim_wavelet_average = ssim_wavelet_value / number_of_tests
    mse_wavelet_average = mse_wavelet_value / number_of_tests
    return [corr_average, ssim_average, mse_average, ssim_canny_average, ssim_wavelet_average, mse_wavelet_average]

# converting .exr file to .png if user gave .exr file as a rendered scene
def ConvertEXRToPNG(exrfile, pngfile):
    File = OpenEXR.InputFile(exrfile)
    PixType = Imath.PixelType(Imath.PixelType.FLOAT)
    DW = File.header()['dataWindow']
    Size = (DW.max.x - DW.min.x + 1, DW.max.y - DW.min.y + 1)
    rgb = [np.frombuffer(File.channel(c, PixType), dtype=np.float32) for c in 'RGB']
    for i in range(3):
        rgb[i] = np.where(rgb[i]<=0.0031308,
                (rgb[i]*12.92)*255.0,
                (1.055*(rgb[i]**(1.0/2.4))-0.055) * 255.0)
    rgb8 = [Image.frombytes("F", Size, c.tostring()).convert("L") for c in rgb]
    Image.merge("RGB", rgb8).save(pngfile, "PNG")

# converting .tga file to .png if user gave .tga file as a rendered scene
def ConvertTGAToPNG(tgafile, pngfile):
    img = Image.open(tgafile)
    img.save(pngfile)