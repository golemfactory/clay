import logging
import math
import numpy
from apps.blender.blender_reference_generator import BlenderReferenceGenerator
from golem.testutils import TempDirFixture
from golem_verificator.common.rendering_task_utils import get_min_max_y

logger = logging.getLogger(__name__)


class TestBlenderReferenceGenerator(TempDirFixture):
    def setUp(self):
        # pylint: disable=R0915
        super().setUp()

    def test_get_default_crop_size(self):
        assert BlenderReferenceGenerator\
                   ._get_default_crop_size((800, 8000)) == (8, 80)

        assert BlenderReferenceGenerator\
                   ._get_default_crop_size((400, 799)) == (8, 8)

        assert BlenderReferenceGenerator\
                   ._get_default_crop_size((399, 9000)) == (8, 90)

    def test_get_random_interval_within_boundaries(self):
        def _test_crop(min_, max_, step):
            crop_min, crop_max = BlenderReferenceGenerator\
                ._get_random_interval_within_boundaries(min_, max_, step)

            assert round(crop_min, 2) >= round(min_, 2)
            assert round(crop_max, 2) <= round(max_, 2)
            assert abs(crop_max - crop_min - step) <= 0.01

        _test_crop(40, 60, 8)
        _test_crop(550, 570, 10)

    def test_convert_bitmap_coordinates_to_traditional_y_direction(self):
        convert_to_traditional_y_direction = \
            BlenderReferenceGenerator\
            .convert_bitmap_coordinates_to_traditional_y_direction

        assert convert_to_traditional_y_direction(40, 20, 80) == (40, 60)
        assert convert_to_traditional_y_direction(40, 30, 90) == (40, 60)
        assert convert_to_traditional_y_direction(40, 10, 70) == (40, 60)

    def test_generate_crops_data(self):

        def _test_crop(resolution, crop, num, ncrop_size=None):
            blender_reference_generator = BlenderReferenceGenerator()
            if ncrop_size is None:
                crops_info = blender_reference_generator\
                    .generate_crops_data(resolution, crop, num)
            else:
                crops_info = blender_reference_generator\
                    .generate_crops_data(resolution, crop, num, ncrop_size)

            assert len(crops_info) == 3
            crops, pixels, _ = crops_info
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

    def test_generate_crops_data_for_strange_resolutions(self):
        # pylint: disable=R0914
        strange_res = [313, 317, 953, 967, 1949, 1951, 3319, 3323, 9949, 9967]

        for l in range(0, 8):
            res = (strange_res[l], strange_res[l + 1])
            for i in range(1, 14):
                min_y, max_y = get_min_max_y(i, 13, res[1])
                min_y = numpy.float32(min_y)
                max_y = numpy.float32(max_y)
                crop_window = (0.0, 1.0, min_y, max_y)
                left_p = math.floor(numpy.float32(crop_window[0]) *
                                    numpy.float32(res[0]))
                right_p = math.floor(numpy.float32(crop_window[1]) *
                                     numpy.float32(res[0]))
                bottom_p = math.floor(numpy.float32(crop_window[2]) *
                                      numpy.float32(res[1]))
                top_p = math.floor(numpy.float32(crop_window[3]) *
                                   numpy.float32(res[1]))
                blender_reference_generator = BlenderReferenceGenerator()
                values, pixels, _ = blender_reference_generator\
                    .generate_crops_data((res[0], res[1]), crop_window, 3)
                for j in range(0, 3):
                    height_p = math.floor(numpy.float32(
                        values[j][3] - values[j][2]) *
                                          numpy.float32(res[1]))
                    width_p = math.floor(numpy.float32(
                        values[j][1] - values[j][0]) *
                                         numpy.float32(res[0]))
                    assert left_p <= pixels[j][0] <= right_p
                    assert bottom_p <= top_p - pixels[j][1] <= top_p
                    assert left_p <= pixels[j][0] + width_p <= right_p
                    assert bottom_p <= top_p - pixels[j][1] - height_p <= top_p
