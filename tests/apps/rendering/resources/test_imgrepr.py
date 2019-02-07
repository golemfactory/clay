import os
import unittest

import pytest
import cv2

import numpy as np
from apps.rendering.resources.imgrepr import (EXRImgRepr, ImgRepr,
                                              load_img,
                                              OpenCVImgRepr,
                                              OpenCVError)

from golem.testutils import TempDirFixture, PEP8MixIn
from golem.tools.assertlogs import (LogTestCase)

from tests.apps.rendering.resources.imghelper import \
    (get_exr_img_repr, get_test_exr, make_test_img)

from tests.apps.rendering.resources.test_renderingtaskcollector import \
    make_test_img_16bits


class TImgRepr(ImgRepr):
    def load_from_file(self, file_):
        super(TImgRepr, self).load_from_file(file_)

    def get_pixel(self, xy):
        super(TImgRepr, self).get_pixel(xy)

    def get_size(self):
        super(TImgRepr, self).get_size()

    def set_pixel(self, xy, color):
        super(TImgRepr, self).set_pixel(xy, color)

    def copy(self):
        super(TImgRepr, self).copy()

    def close(self):
        super(TImgRepr, self).close()


class TestImgRepr(unittest.TestCase, PEP8MixIn):
    PEP8_FILES = [
        'apps/rendering/resources/imgrepr.py',
    ]

    def test_functions(self):
        t = TImgRepr()
        t.load_from_file("file_")
        t.get_pixel((0, 0))
        t.get_size()
        t.copy()
        t.set_pixel((0, 0), (0, 0, 0))


class TestExrImgRepr(TempDirFixture, PEP8MixIn):
    PEP8_FILES = [
        'apps/rendering/resources/imgrepr.py',
    ]

    def test_init(self):
        img = EXRImgRepr()
        assert isinstance(img, ImgRepr)
        assert img.img is None
        assert img.type == "EXR"
        assert img.bgr is None
        assert img.min == 0.0
        assert img.max == 1.0
        assert img.file_path is None

    def test_errors(self):
        e = EXRImgRepr()

        with self.assertRaises(Exception):
            e.load_from_file("unknown file")
        with self.assertRaises(Exception):
            e.get_size()
        with self.assertRaises(Exception):
            e.get_pixel((0, 0))

    def test_exr_repr(self):
        e = get_exr_img_repr()
        assert e.img is not None
        assert e.bgr is not None

        assert e.get_size() == (10, 10)

        assert e.get_pixel((0, 0)) == [145, 135, 110]
        assert e.get_pixel((5, 5)) == [178, 187, 180]
        assert e.get_pixel((9, 9)) == [118, 134, 143]

        with self.assertRaises(Exception):
            e.get_pixel((10, 10))

    def test_set_pixel(self):
        e = get_exr_img_repr()

        val1 = [102, 77, 51]
        e.set_pixel((0, 0), val1)
        val2 = [26, 33, 0]
        e.set_pixel((4, 4), val2)

        assert e.get_pixel((0, 0)) == val1
        assert e.get_pixel((4, 4)) == val2


class TestImgFunctions(TempDirFixture, LogTestCase):
    def test_load_img(self):
        exr_img = load_img(get_test_exr())
        assert isinstance(exr_img, EXRImgRepr)
        assert exr_img.get_size() == (10, 10)
        assert load_img("notexisting") is None

    def test_opencv_load_from_file(self):
        img_path = self.temp_file_name("path1.png")
        make_test_img(img_path, (10, 20), (10, 20, 30))
        img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
        # OpenCV stores (height,width,channels)
        assert img.shape == (20, 10, 3)
        # OpenCV stores channels as BGR
        assert img[0][0][0] == 30
        assert img[0][0][1] == 20
        assert img[0][0][2] == 10

        img1 = cv2.imread(get_test_exr(), cv2.IMREAD_UNCHANGED)
        assert img1 is not None
        assert img1.shape == (10, 10, 3)

        make_test_img_16bits("path2.png", width=10, height=20,
                             color=(10, 69, 30))
        img2 = cv2.imread("path2.png", cv2.IMREAD_UNCHANGED)
        assert img2 is not None
        assert img2.shape == (20, 10, 3)
        assert img2.dtype == np.uint16
        assert img2[0][0][0] == 10
        assert img2[0][0][1] == 69
        assert img2[0][0][2] == 30
        os.remove("path2.png")
        assert os.path.isfile("path2.png") is False

    def test_opencv_read_and_write(self):
        img = OpenCVImgRepr()
        with pytest.raises(OpenCVError):
            img.load_from_file("path1.png")
        assert img.img is None

        img = OpenCVImgRepr.empty(width=10, height=20, channels=3,
                                  dtype=np.uint16)
        assert img.img is not None
        assert img.img.shape == (20, 10, 3)
        assert img.img.dtype == np.uint16
        img.save("path1.png")
        assert os.path.isfile("path1.png")
        img.save_with_extension("path2.png", "PNG")
        assert os.path.isfile("path2.png")

        img2 = cv2.imread("path1.png", cv2.IMREAD_UNCHANGED)
        assert img2.shape == (20, 10, 3)
        assert img2.dtype == np.uint16
        assert img2[0][0][0] == 0

        os.remove("path1.png")
        assert os.path.isfile("path1.png") is False
        os.remove("path2.png")
        assert os.path.isfile("path2.png") is False
