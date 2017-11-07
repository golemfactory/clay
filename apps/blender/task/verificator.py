import math
import random

from golem.core.common import timeout_to_deadline

from apps.rendering.task.verificator import FrameRenderingVerificator
from apps.blender.resources.scenefileeditor import generate_blender_crop_file
from apps.blender.resources.imgcompare import check_size

# GG todo remove parser, sys etc..
import argparse
from argparse import RawTextHelpFormatter
import sys
from apps.blender.task.reference_img_generator import generate_random_crop
from apps.core.task.verificator import SubtaskVerificationState
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
from apps.rendering.resources.imgcomparer import \
    ConvertEXRToPNG, ConvertTGAToPNG, \
    average_of_each_measure, compare_crop_window


class BlenderVerificator(FrameRenderingVerificator):
    def __init__(self, *args, **kwargs):
        super(BlenderVerificator, self).__init__(*args, **kwargs)
        self.box_size = [1, 1]
        self.compositing = False
        self.output_format = ""
        self.src_code = ""
        self.docker_images = []
        self.verification_timeout = 0

    # todo GG integrate CP metrics into _check_files
    def _check_files(self, subtask_id, subtask_info, tr_files, task):
        if self.use_frames and self.total_tasks <= len(self.frames):
            frames_list = subtask_info['frames']
            if len(tr_files) < len(frames_list):
                self.ver_states[subtask_id] = \
                    SubtaskVerificationState.WRONG_ANSWER
                return
        if not self._verify_imgs(
                subtask_id,
                subtask_info,
                tr_files,
                task):
            self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER
        else:
            self.ver_states[subtask_id] = SubtaskVerificationState.VERIFIED

    def validation(self):
        parser = checking_parser() # GG todo
        args = parser.parse_args()
        blend_file = ".blend"
        # checking if what ugenerate_random_cropser gave .blend file as a parameter
        if (args.scene_file[-6:] != blend_file):
            sys.exit("No such file or wrong directory to .blender file!")
        # spliting all float numbers to get crop window size parametrs
        # checking if what user gave as parameters is correct
        crop_window_size = [float(x) for x in args.crop_window_size.split(",")]
        if (len(crop_window_size) == 4):
            for crop_window_number in crop_window_size:
                if (crop_window_number > 1 or crop_window_number < 0):
                    sys.exit(
                        "Wrong cropwindow size. Try example: 0.1,0.2,0.3,0.4")
        else:
            sys.exit("Too much, or too less arguments in cropwindow size."
                     " Try example: 0.1,0.2,0.3,0.4")
        number_of_tests = 3
        # spliting resolution parameters in two seperate X and Y
        # checking if what user gave as parameters is correct
        resolution = [int(x) for x in args.resolution.split(",")]
        if (len(resolution) == 2):
            for res in resolution:
                if (res <= 0):
                    sys.exit("Size of image can't be 0!")
        # checking if what user gave as rendered scene has correct format
        format_file = [".png", ".jpg", ".bmp", ".jp2", ".tif,", ".exr", ".tga"]
        scene_format = os.path.splitext(args.rendered_scene)[1]
        if scene_format not in format_file:
            sys.exit("No such file or wrong format of scene")
        rendered_scene = cv2.imread(args.rendered_scene)
        # if rendered scene has .exr format need to convert it for .png format
        if os.path.splitext(args.rendered_scene)[1] == ".exr":
            check_input = OpenEXR.InputFile(args.rendered_scene).header()[
                'channels']
            if 'RenderLayer.Combined.R' in check_input:
                sys.exit("There is no support for OpenEXR multilayer")
            ConvertEXRToPNG(args.rendered_scene, "/tmp/scene.png")
            rendered_scene = "/tmp/scene.png"
            rendered_scene = cv2.imread(rendered_scene)
        elif os.path.splitext(args.rendered_scene)[1] == ".tga":
            rendered_scene = ConvertTGAToPNG(args.rendered_scene,
                                             "/tmp/scene.png")
            rendered_scene = "/tmp/scene.png"
            rendered_scene = cv2.imread(rendered_scene)

        return args, crop_window_size, number_of_tests, resolution, rendered_scene, scene_format

    # main script for testing crop windows
    def assign_value(self, test_value=1):

        # values for giving answer if crop window test are true, or false
        border_value_corr = (0.8, 0.7)
        border_value_ssim = (0.94, 0.7)
        border_value_mse = (10, 30)
        args, crop_window_size, number_of_tests, resolution, rendered_scene, scene_format = self.validation()
        # generate all crop windows which are need to compare metrics
        crops_pixel = generate_random_crop(
            args.scene_file, crop_window_size, number_of_tests, resolution,
            rendered_scene, scene_format, test_value)

        crop_res = crops_pixel[0]
        crop_output = crops_pixel[1]
        crop_percentages = crops_pixel[2]
        number_of_crop = 0
        list_of_measurements = []
        # comparing crop windows generate in specific place with
        # crop windows cutted from rendered scene gave by user
        for coordinate in crop_res:
            if os.path.splitext(crop_output[number_of_crop])[1] == ".exr":
                ConvertEXRToPNG(crop_output[number_of_crop],
                                "/tmp/" + str(number_of_crop) + ".png")
                crop_output[number_of_crop] = "/tmp/" + str(
                    number_of_crop) + ".png"
            elif os.path.splitext(crop_output[number_of_crop])[1] == ".tga":
                ConvertTGAToPNG(crop_output[number_of_crop],
                                "/tmp/" + str(number_of_crop) + ".png")
                crop_output[number_of_crop] = "/tmp/" + str(
                    number_of_crop) + ".png"
            compare_measurements = compare_crop_window(
                crop_output[number_of_crop], rendered_scene, coordinate[0],
                coordinate[1], crop_percentages[number_of_crop], resolution)
            number_of_crop += 1
            list_of_measurements.append(compare_measurements)

        averages = average_of_each_measure(list_of_measurements,
                                           number_of_tests)
        print("AVERAGES - CORR:", averages[0], " SSIM:", averages[1], " MSE:",
              averages[2],
              " SSIM_CANNY:", averages[3], " SSIM_WAVELET:", averages[4],
              " MSE_WAVELET:", averages[5])

        # assign all values which are borders for correct crop window
        border_value = [border_value_corr, border_value_ssim, border_value_mse]
        border_position = 0
        pass_tests = []
        # checking if values which compare_crop_window test gave is correct
        for average in averages[:3]:
            border_value_max = border_value[border_position][0]
            border_value_min = border_value[border_position][1]
            # if MSE is testing then test in diffrent borders
            if border_position == 2:
                if (border_value_max > average) == True:
                    pass_tests.append(True)
                elif (border_value_min > average) == True and test_value == 1:
                    pass_tests.append("HalfTrue")
                else:
                    pass_tests.append(False)
            # if SSIM of any transform is testing then test in their borders
            else:
                if (border_value_max < average) == True:
                    pass_tests.append(True)
                elif (border_value_min < average) == True and test_value == 1:
                    pass_tests.append("HalfTrue")
                else:
                    pass_tests.append(False)

            border_position += 1
        print("Test passes: CORR: " + str(pass_tests[0]) + "  SSIM: " + str(
            pass_tests[1]) + "  MSE: " + str(pass_tests[2]))

        pass_test_result = all(pass_test == True for pass_test in pass_tests)
        pass_some_test = any(pass_test == True for pass_test in pass_tests)
        if pass_test_result == True and test_value < 3:
            result = "Bitmaps to compare are the same"
            print(result)
            self.save_result(args, result, resolution, number_of_crop, crop_res,
                             test_value, crop_window_size, \
                             crop_percentages, crop_output,
                             list_of_measurements,
                             averages, pass_tests)

        # if result of tests are "HalfTrue" then
        # repeat test second time with larger crop windows
        elif "HalfTrue" in pass_tests and test_value == 1 or pass_some_test == True and test_value == 1:
            result = "Running second test."
            print(result)
            test_value += 1
            self.save_result(args, result, resolution, number_of_crop, crop_res,
                             test_value, crop_window_size, \
                             crop_percentages, crop_output,
                             list_of_measurements,
                             averages, pass_tests)
            self.assign_value(test_value)
        else:
            result = 'Bitmaps are not the same'
            print(result)
            self.save_result(args, result, resolution, number_of_crop, crop_res,
                             test_value, crop_window_size, \
                             crop_percentages, crop_output,
                             list_of_measurements,
                             averages, pass_tests)

        return args.name_of_excel_file

    # saving result to log file
    def save_result(self, args, result, resolution, number_of_crop, crop_res,
                    test_value, crop_window_size, crop_percentages, crop_output,
                    list_of_measurements, averages, pass_tests):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        log_folder = "log"
        filepath = os.path.join(dir_path, log_folder, 'log.txt')
        log_folder = os.path.join(dir_path, log_folder)
        # if not exist creat new
        if not os.path.isfile(filepath):
            if not os.path.exists(log_folder):
                os.makedirs(log_folder)
            new = open(filepath, 'w+')
            new.close()
        # open and write infromations about tests
        with open('log/log.txt', 'a') as log:
            now = datetime.datetime.now()
            log.write('\n' + '-' * 95)
            log.write("\n" + now.strftime("%Y-%m-%d %H:%M"))
            log.write('\nBlend file: ' + str(
                args.scene_file) + "\nscene resolution: xres: " + str(
                resolution[0]) + " yres: " + str(
                resolution[1]) + "  number_of_crop: " + str(number_of_crop))
            log.write('   number_of_test: ' + str(test_value))
            log.write("\nscene_crop: x_min: " + str(
                crop_window_size[0]) + " x_max: " + str(
                crop_window_size[1]) + " y_min: " + str(
                crop_window_size[2]) + " y_max: " + str(crop_window_size[3]))
            number_crop = 0
            for crop in crop_percentages:
                crop_file = cv2.imread(crop_output[number_crop])
                height, width = crop_file.shape[:2]
                log.write("\n\ncrop_window " + str(
                    number_crop + 1) + ": x_min: " + str(
                    crop[0]) + " x_max: " + str(crop[1]) + " y_min: " + str(
                    crop[2]) + " y_max: " + str(crop[3]))
                log.write("\n" + " " * 15 + "x_min: " + str(
                    crop_res[number_crop][0]) + " x_max: " + str(
                    crop_res[number_crop][0] + width) + " y_min: " + str(
                    crop_res[number_crop][1]) + " y_max: " + str(
                    crop_res[number_crop][1] + height))
                log.write("\n" + " " * 15 + "width: " + str(
                    width) + " height: " + str(height))
                log.write("\n" + " " * 8 + "result: CORR: " + str(
                    list_of_measurements[number_crop][0]) + " SSIM: " + str(
                    list_of_measurements[number_crop][1]) + " MSE: " + str(
                    list_of_measurements[number_crop][2]) + " CANNY: " +
                          str(list_of_measurements[number_crop][
                                  3]) + " SSIM_wavelet: " + str(
                    list_of_measurements[number_crop][
                        4]) + " MSE_wavelet: " + str(
                    list_of_measurements[number_crop][5]))
                number_crop += 1
            log.write(
                "\n\nAVERAGES: CORR: " + str(averages[0]) + " SSIM: " + str(
                    averages[1]) + " MSE: " + str(averages[2]) +
                " SSIM_CANNY: " + str(averages[3]) + " SSIM_WAVELET: " + str(
                    averages[4]) + " MSE_WAVELET: " + str(averages[5]))
            log.write(
                "\nTest passes: CORR: " + str(pass_tests[0]) + "  SSIM: " + str(
                    pass_tests[1]) + "  MSE: " + str(pass_tests[2]))
            log.write("\n\nResult: " + str(result))
            log.close()

    def set_verification_options(self, verification_options):
        super(BlenderVerificator, self).set_verification_options(
            verification_options)
        if self.advanced_verification:
            box_x = min(verification_options.box_size[0], self.res_x)
            box_y = min(verification_options.box_size[1],
                        int(self.res_y / self.total_tasks))
            self.box_size = (box_x, box_y)

    def change_scope(self, subtask_id, start_box, tr_file, subtask_info):
        extra_data, _ = super(BlenderVerificator, self).change_scope(subtask_id,
                                                                     start_box,
                                                                     tr_file,
                                                                     subtask_info)
        min_x = start_box[0] / self.res_x
        max_x = (start_box[0] + self.verification_options.box_size[
            0] + 1) / self.res_x
        shift_y = (extra_data['start_task'] - 1) * (
        self.res_y / extra_data['total_tasks'])
        start_y = start_box[1] + shift_y
        max_y = (self.res_y - start_y) / self.res_y
        shift_y = start_y + self.verification_options.box_size[1] + 1
        min_y = max((self.res_y - shift_y) / self.res_y, 0.0)
        min_y = max(min_y, 0)
        script_src = generate_blender_crop_file(
            resolution=(self.res_x, self.res_y),
            borders_x=(min_x, max_x),
            borders_y=(min_y, max_y),
            use_compositing=self.compositing
        )
        extra_data['script_src'] = script_src
        extra_data['output_format'] = self.output_format
        return extra_data, (0, 0)

    def query_extra_data_for_advanced_verification(self, extra_data):
        ctd = super(BlenderVerificator,
                    self).query_extra_data_for_advanced_verification(extra_data)
        ctd.subtask_id = str(random.getrandbits(128))
        ctd.src_code = self.src_code
        ctd.docker_images = self.docker_images
        ctd.deadline = timeout_to_deadline(self.verification_timeout)
        return ctd

    def _get_part_img_size(self, subtask_info):
        x, y = self._get_part_size(subtask_info)
        return 0, 0, x, y

    def _get_part_size(self, subtask_info):
        start_task = subtask_info['start_task']
        if not self.use_frames:
            res_y = self._get_part_size_from_subtask_number(start_task)
        elif len(self.frames) >= self.total_tasks:
            res_y = self.res_y
        else:
            parts = int(self.total_tasks / len(self.frames))
            res_y = int(math.floor(self.res_y / parts))
        return self.res_x, res_y

    def _get_part_size_from_subtask_number(self, subtask_number):

        if self.res_y % self.total_tasks == 0:
            res_y = int(self.res_y / self.total_tasks)
        else:
            # in this case task will be divided into not equal parts: floor or ceil of (res_y/total_tasks)
            # ceiling will be height of subtasks with smaller num
            ceiling_height = int(math.ceil(self.res_y / self.total_tasks))
            ceiling_subtasks = self.total_tasks - (
            ceiling_height * self.total_tasks - self.res_y)
            if subtask_number > ceiling_subtasks:
                res_y = ceiling_height - 1
            else:
                res_y = ceiling_height
        return res_y

    def _check_size(self, file_, res_x, res_y):
        return check_size(file_, res_x, res_y)
