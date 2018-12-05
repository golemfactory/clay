import logging
import math

import numpy
from golem_verificator.common.rendering_task_utils import get_min_max_y

from apps.blender.blender_reference_generator import BlenderReferenceGenerator
from apps.blender.blender_reference_generator import SubImage, Region, Crop,\
    PixelRegion
from golem.testutils import TempDirFixture

logger = logging.getLogger(__name__)


class TestBlenderReferenceGenerator(TempDirFixture):

    def test_get_default_crop_size(self):
        sub_image = SubImage(Region(0, 1, 1, 0), (800, 8000))
        assert sub_image.get_default_crop_size() == (80, 800)

        sub_image = SubImage(Region(0, 1, 1, 0), (400, 799))
        assert sub_image.get_default_crop_size() == (40, 79)

        sub_image = SubImage(Region(0, 1, 1, 0), (399, 9000))
        assert sub_image.get_default_crop_size() == (39, 900)

    def test_get_random_interval_within_boundaries(self):
        def _test_crop(min_, max_, step):
            crop_min, crop_max = BlenderReferenceGenerator\
                ._get_random_interval_within_boundaries(min_, max_, step)

            assert round(crop_min, 2) >= round(min_, 2)
            assert round(crop_max, 2) <= round(max_, 2)
            assert abs(crop_max - crop_min - step) <= 0.1

        _test_crop(40, 60, 8)
        _test_crop(550, 570, 10)

    def test_get_relative_top_left(self):
        sub_image = SubImage(Region(0, 1, 1, 0), (400, 160))
        crop = Crop.create_from_pixel_region(
            "1",
            PixelRegion(40, 100, 100, 20),
            sub_image, "")
        assert crop.get_relative_top_left() == (40, 60)

        sub_image = SubImage(Region(0, 1, 1, 0), (400, 90))
        crop = Crop.create_from_pixel_region(
            "1",
            PixelRegion(40, 30, 100, 20),
            sub_image, "")
        assert crop.get_relative_top_left() == (40, 60)

        sub_image = SubImage(Region(0, 1, 1, 0), (400, 90))
        crop = Crop.create_from_pixel_region(
            "1",
            PixelRegion(40, 30, 100, 20),
            sub_image, "")
        assert crop.get_relative_top_left() == (40, 60)

    def test_generate_crops_data(self):

        def _test_crop(resolution, crop, num):
            blender_reference_generator = BlenderReferenceGenerator()
            crops_desc = blender_reference_generator\
                .generate_crops_data(resolution, crop, num, "")

            assert len(crops_desc) == 3
            for desc in crops_desc:
                assert 0 <= desc.pixel_region.left <= resolution[0]
                assert 0 <= desc.pixel_region.top <= resolution[1]
            for desc in crops_desc:
                assert crop[0] <= desc.crop_region.left <= crop[1]
                assert crop[0] <= desc.crop_region.right <= crop[1]
                assert desc.crop_region.left <= desc.crop_region.right

                assert crop[2] <= desc.crop_region.top <= crop[3]
                assert crop[2] <= desc.crop_region.bottom <= crop[3]
                assert desc.crop_region.bottom <= desc.crop_region.top

        for _ in range(100):
            _test_crop([800, 600], (numpy.float32(0.0),
                                    numpy.float32(0.3),
                                    numpy.float32(0.0),
                                    numpy.float32(0.3)), 3)
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
                                    numpy.float32(0.4)), 3)
            with self.assertRaises(Exception):
                _test_crop([800, 600], (numpy.float32(0.0),
                                        numpy.float32(0.01),
                                        numpy.float32(0.0),
                                        numpy.float32(0.01)), 3)

    def test_generate_crops_data_for_strange_resolutions(self):
        # pylint: disable=R0914
        strange_res = [313, 317, 953, 967, 1949, 1951, 3319, 3323, 9949, 9967]
        for l in range(0, 9):
            res = (strange_res[l], strange_res[l + 1])
            for i in range(1, 10):
                min_y, max_y = get_min_max_y(i, 9, res[1])
                min_y = numpy.float32(min_y)
                max_y = numpy.float32(max_y)
                crop_window = (0.0, 1.0, min_y, max_y)
                blender_reference_generator = BlenderReferenceGenerator()
                crops_desc = blender_reference_generator\
                    .generate_crops_data(res, crop_window, 3, "")
                for j in range(0, 3):
                    assert crops_desc[j].pixel_region.left < crops_desc[
                        j].pixel_region.right
                    assert crops_desc[j].pixel_region.top > crops_desc[
                        j].pixel_region.bottom
