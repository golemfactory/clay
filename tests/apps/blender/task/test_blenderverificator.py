from unittest import TestCase

from apps.blender.task.verificator import BlenderVerificator
from apps.core.task.verificator import SubtaskVerificationState


import os

from apps.rendering.resources.ImgVerificator import ImgStatistics, \
    ImgVerificator

from apps.core.task.verificator import \
    SubtaskVerificationState as VerificationState
from apps.rendering.resources.imgrepr import PILImgRepr

from golem.tools.assertlogs import LogTestCase
from golem import testutils
from golem.core.common import get_golem_path

from mock import Mock, MagicMock, patch


class TestBlenderVerificator(LogTestCase, testutils.PEP8MixIn):
    # PEP8_FILES = ['apps/rendering/resources/ImgVerificator.py']

    def test_get_part_size_from_subtask_number(self):
        bv = BlenderVerificator()

        bv.res_y = 600
        bv.total_tasks = 20
        assert bv._get_part_size_from_subtask_number(3) == 30
        bv.total_tasks = 13
        assert bv._get_part_size_from_subtask_number(2) == 47
        assert bv._get_part_size_from_subtask_number(3) == 46
        assert bv._get_part_size_from_subtask_number(13) == 46

    def test_get_part_size(self):
        bv = BlenderVerificator()
        bv.use_frames = False
        bv.res_x = 800
        bv.res_y = 600
        bv.total_tasks = 20
        assert bv._get_part_size({"start_task": 3}) == (800, 30)
        bv.use_frames = True
        bv.frames = list(range(40))
        assert bv._get_part_size({"start_task": 3}) == (800, 600)
        bv.frames = list(range(10))
        assert bv._get_part_size({"start_task": 3}) == (800, 300)

    def test_check_files(self):


        # arrange
        folder_path = os.path.join(get_golem_path(),
                                   "tests", "apps", "blender",
                                   "resources", "blender_imgs_for_verification_tests")

        tr_files = []
        tr_files.append(
            os.path.join(folder_path,'good_image0001.png'))

        subtask_id = "id1"

        subtask_info = {'frames' : [1], 'start_task' : [1]}

        # task = MagicMock
        task = {'main_scene_file':
                    '/home/ggruszczynski/Desktop/testy_renderingowe/benchmark_blender/bmw27_cpu.blend',
                'main_scene_dir' :
                    '/home/ggruszczynski/Desktop/testy_renderingowe/benchmark_blender/', }
        # act
        blenderVerificator = BlenderVerificator()
        blenderVerificator.total_tasks = 2
        blenderVerificator.res_x = 400
        blenderVerificator.res_3 = 300
        blenderVerificator.frames = [1]


        blenderVerificator._check_files(subtask_id, subtask_info, tr_files, task)


        # assert
        assert blenderVerificator.ver_states[subtask_id] == SubtaskVerificationState.VERIFIED


    def test_is_valid_against_reference(self):
        # arrange
        folder_path = os.path.join(get_golem_path(),
                                   "tests", "apps", "rendering",
                                   "resources", "imgs_for_verification_tests")

        ref_img0 = PILImgRepr()
        ref_img0.load_from_file(os.path.join(folder_path,
                                             'reference_300x400spp50_run0.png'))
        ref_img1 = PILImgRepr()
        ref_img1.load_from_file(os.path.join(folder_path,
                                             'reference_300x400spp50_run1.png'))

        images = list()
        for file_name in os.listdir(folder_path):
            if file_name.endswith(".png") and 'reference' not in file_name:
                p = PILImgRepr()
                p.load_from_file(os.path.join(folder_path, file_name))
                images.append(p)

        cropping_window = (0.55, 0.75, 0.6, 0.8)
        img_verificator = ImgVerificator()

        # act
        ref_img0 = img_verificator.crop_img_relative(ref_img0, cropping_window)
        ref_img1 = img_verificator.crop_img_relative(ref_img1, cropping_window)

        # these are img rendered by requestor
        reference_stats = ImgStatistics(ref_img0, ref_img1)
        #
        # ref_img0.img.save(('aaa' + ref_img0.get_name() + '.png'))
        # ref_img1.img.save(('aaa' + ref_img1.get_name() + '.png'))
        print(reference_stats.get_stats())

        print('SSIM \t\t MSE \t\t MSE_norm \t\t MSE_bw \t\t PSNR')
        imgstats = []
        validation_results = {}

        for img in images:
            croped_img = img_verificator.crop_img_relative(img, cropping_window)
            # croped_img.img.save('aaa'+croped_img.get_name())
            imgstat = ImgStatistics(ref_img0, croped_img)
            validation_result = img_verificator.is_valid_against_reference(
                imgstat, reference_stats)

            imgstats.append(imgstat)
            validation_results[imgstat.name] = validation_result
            print(imgstat.name, imgstat.get_stats(), validation_result)

        # assert
        should_be_rejected = [value for key, value
                              in validation_results.items()
                              if 'malicious' in key.lower()]

        for w in should_be_rejected:
            assert w == VerificationState.WRONG_ANSWER

        should_be_verified = [value for key, value
                              in validation_results.items()
                              if 'malicious' not in key.lower()]

        for w in should_be_verified:
            assert w == VerificationState.VERIFIED