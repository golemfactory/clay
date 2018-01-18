from unittest import TestCase

from apps.blender.resources.cropgenerator import (find_crop_size,
                                                  generate_crops,
                                                  pixel,
                                                  random_crop)


class TestGenerateCrops(TestCase):
    def test_find_crop_size(self):
        assert find_crop_size(800) == 0.01
        assert find_crop_size(8000) == 0.01
        assert find_crop_size(400) == 0.02
        assert find_crop_size(799) == 0.02
        assert find_crop_size(399) == 0.03

    def test_random_crop(self):
        def _test_crop(min_, max_, step):
            crop_min, crop_max = random_crop(min_, max_, step)
            assert crop_min >= min_
            assert crop_max <= max_
            assert abs(crop_max - crop_min - step) <= 0.01

        _test_crop(0.0, 0.1, 0.01)
        _test_crop(0.0, 0.5, 0.5)
        _test_crop(0.0, 0.5, 0.02)
        _test_crop(0.032, 0.42, 0.01)

    def test_pixel(self):
        assert pixel(800, 600, 0.0, 1.0, 0.0, 1.0) == (0, 0)
        assert pixel(800, 600, 0.6, 0.9, 0.5, 1.0) == (80, 60)
        assert pixel(799, 600, 0.6, 0.9, 0.5, 1.0) == (80, 60)
