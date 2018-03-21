import numpy

from unittest import TestCase

from apps.blender.task.blendercropper import BlenderCropper

from golem.testutils import PEP8MixIn


class TestGenerateCrops(TestCase, PEP8MixIn):
    PEP8_FILES = ["apps/blender/task/blendercropper.py"]

    def setUp(self):
        self.cropper = BlenderCropper()

    def test_find_crop_size(self):
        assert self.cropper._find_split_size(800) == 8
        assert self.cropper._find_split_size(8000) == 80
        assert self.cropper._find_split_size(400) == 8
        assert self.cropper._find_split_size(799) == 8
        assert self.cropper._find_split_size(399) == 8

    def test_random_crop(self):
        def _test_crop(min_, max_, step):
            crop_min, crop_max = self.cropper._random_split(min_, max_, step)
            assert round(crop_min, 2) >= round(min_, 2)
            assert round(crop_max, 2) <= round(max_, 2)
            assert abs(crop_max - crop_min - step) <= 0.01

        _test_crop(40, 60, 8)
        _test_crop(550, 570, 10)

    def test_pixel(self):
        assert self.cropper._pixel(40, 20, 80) == (40, 60)
        assert self.cropper._pixel(40, 30, 90) == (40, 60)
        assert self.cropper._pixel(40, 10, 70) == (40, 60)

    def test_generate_crop(self):
        def _test_crop(resolution, crop, num, ncrop_size=None):
            self.cropper.clear()
            if ncrop_size is None:
                crops_info = self.cropper.generate_split_data(resolution, crop,
                                                              num)
            else:
                crops_info = self.cropper.generate_split_data(resolution, crop,
                                                              num, ncrop_size)
            assert len(crops_info) == 3
            crops, pixels, size = crops_info
            assert len(crops) == num
            assert len(pixels) == num
            for pixel_ in pixels:
                assert 0 <= pixel_[0] <= resolution[0]
                assert 0 <= pixel_[1] <= resolution[1]
            for ncrop in crops:
                assert crop[0] <= ncrop[0] <= crop[1]
                assert crop[0] <= ncrop[1] <= crop[1]
                assert ncrop[0] <= ncrop[1]

                assert crop[2] <= ncrop[2] <= crop[3]
                assert crop[2] <= ncrop[3] <= crop[3]
                assert ncrop[2] <= ncrop[2]

        for _ in range(100):
            _test_crop([800, 600], (numpy.float32(0.0),
                                    numpy.float32(0.1),
                                    numpy.float32(0.0),
                                    numpy.float32(0.1)), 3)
            _test_crop([800, 600], (numpy.float32(0.5),
                                    numpy.float32(0.8),
                                    numpy.float32(0.2),
                                    numpy.float32(0.4)), 3)
            _test_crop([1000, 888], (numpy.float32(0.2),
                                     numpy.float32(0.4),
                                     numpy.float32(0.2),
                                     numpy.float32(0.5)), 3)
            _test_crop([800, 600], (numpy.float32(0.0),
                                    numpy.float32(0.1),
                                    numpy.float32(0.0),
                                    numpy.float32(0.4)), 3, (0.04, 0.1))
            with self.assertRaises(Exception):
                _test_crop([800, 600], (numpy.float32(0.0),
                                        numpy.float32(0.1),
                                        numpy.float32(0.0),
                                        numpy.float32(0.1)), 3, (0.04, 0.1))
