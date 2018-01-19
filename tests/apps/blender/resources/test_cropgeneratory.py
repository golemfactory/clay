from unittest import TestCase

from apps.blender.resources.cropgenerator import (find_crop_size,
                                                  generate_crops,
                                                  pixel,
                                                  random_crop)

from golem.testutils import PEP8MixIn


class TestGenerateCrops(TestCase, PEP8MixIn):
    PEP8_FILES = ["apps/blender/resources/cropgenerator.py"]

    def test_find_crop_size(self):
        assert find_crop_size(800) == 0.01
        assert find_crop_size(8000) == 0.01
        assert find_crop_size(400) == 0.02
        assert find_crop_size(799) == 0.02
        assert find_crop_size(399) == 0.03

    def test_random_crop(self):
        def _test_crop(min_, max_, step):
            crop_min, crop_max = random_crop(min_, max_, step)
            assert round(crop_min, 2) >= round(min_, 2)
            assert round(crop_max, 2) <= round(max_, 2)
            assert abs(crop_max - crop_min - step) <= 0.01

        _test_crop(0.0, 0.1, 0.01)
        _test_crop(0.0, 0.5, 0.5)
        _test_crop(0.0, 0.5, 0.02)
        _test_crop(0.032, 0.42, 0.01)

    def test_pixel(self):
        assert pixel((800, 600), 0.0, 1.0, 0.0, 1.0) == (0, 0)
        assert pixel((800, 600), 0.6, 0.9, 0.5, 1.0) == (80, 60)
        assert pixel((799, 600), 0.6, 0.9, 0.5, 1.0) == (80, 60)

    def test_generate_crop(self):
        def _test_crop(resolution, crop, num, ncrop_size=None):
            if ncrop_size is None:
                crops_info = generate_crops(resolution, crop, num)
            else:
                crops_info = generate_crops(resolution, crop, num,
                                            ncrop_size)
            assert len(crops_info) == 2
            crops, pixels = crops_info
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
            _test_crop([800, 600], (0.0, 0.1, 0.0, 0.1), 3)
            _test_crop([800, 600], (0.5, 0.8, 0.2, 0.4), 3)
            _test_crop([1000, 888], (0.2, 0.4, 0.2, 0.5), 3)
            _test_crop([800, 600], (0.0, 0.1, 0.0, 0.1), 3, (0.04, 0.1))
