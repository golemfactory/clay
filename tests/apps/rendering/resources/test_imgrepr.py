import os
import unittest

import Imath
from PIL import Image

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase

from apps.rendering.resources.imgrepr import (blend, EXRImgRepr, ImgRepr,
                                              load_as_pil, load_img, logger,
                                              PILImgRepr)

from imghelper import (get_exr_img_repr, get_pil_img_repr, get_test_exr,
                       make_test_img)


class TImgRepr(ImgRepr):

    def load_from_file(self, file_):
        super(TImgRepr, self).load_from_file(file_)

    def get_pixel(self, (i, j)):
        super(TImgRepr, self).get_pixel((i, j))

    def get_size(self):
        super(TImgRepr, self).get_size()

    def set_pixel(self, (i, j), color):
        super(TImgRepr, self).set_pixel((i, j), color)

    def copy(self):
        super(TImgRepr, self).copy()

    def to_pil(self):
        super(TImgRepr, self).to_pil()


class TestImgRepr(unittest.TestCase):

    def test_functions(self):
        t = TImgRepr()
        t.load_from_file("file_")
        t.get_pixel((0, 0))
        t.get_size()
        t.copy()
        t.to_pil()
        t.set_pixel((0, 0), (0, 0, 0))


class TestPILImgRepr(TempDirFixture):
    def test_init(self):
        p = PILImgRepr()
        assert isinstance(p, ImgRepr)
        assert p.img is None
        assert p.type == "PIL"

    def test_errors(self):
        p = PILImgRepr()

        with self.assertRaises(Exception):
            p.load_from_file("unknown file")
        with self.assertRaises(Exception):
            p.get_size()
        with self.assertRaises(Exception):
            p.get_pixel((0, 0))

    def test_pil_repr(self):
        img_path = self.temp_file_name('img.png')
        p = get_pil_img_repr(img_path)
        assert isinstance(p.img, Image.Image)
        assert p.get_size() == (10, 10)
        assert p.get_pixel((0, 0)) == [255, 0, 0]
        assert p.get_pixel((5, 5)) == [255, 0, 0]
        assert p.get_pixel((9, 9)) == [255, 0, 0]
        with self.assertRaises(Exception):
            p.get_pixel((10, 10))

        p_copy = p.copy()

        p.set_pixel((3, 5), [10, 11, 12])
        assert p.get_pixel((3, 5)) == [10, 11, 12]
        assert p_copy.get_pixel((3, 5)) == [255, 0, 0]

        p_copy.set_pixel((5, 3), [200, 210, 220])
        assert p_copy.get_pixel((5, 3)) == [200, 210, 220]
        assert p.get_pixel((5, 3)) == [255, 0, 0]


def almost_equal(v1, v2):
    assert abs(v1 - v2) < 0.001


def almost_equal_pixels(pix1, pix2):
    for c1, c2 in zip(pix1, pix2):
        almost_equal(c1, c2)


class TestExrImgRepr(TempDirFixture):
    def test_init(self):
        img = EXRImgRepr()
        assert isinstance(img, ImgRepr)
        assert img.img is None
        assert img.type == "EXR"
        assert img.dw is None
        assert isinstance(img.pt, Imath.PixelType)
        assert img.rgb is None
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
        assert e.dw is not None
        assert e.rgb is not None

        assert e.get_size() == (10, 10)

        assert e.get_pixel((0, 0)) == [0.5703125,
                                       0.53076171875,
                                       0.432373046875]
        assert e.get_pixel((5, 5)) == [0.6982421875,
                                       0.73193359375,
                                       0.70556640625]
        assert e.get_pixel((9, 9)) == [0.461181640625,
                                       0.52392578125,
                                       0.560546875]

        with self.assertRaises(Exception):
            e.get_pixel((10, 10))

    def test_set_pixel(self):
        e = get_exr_img_repr()

        val1 = [0.4, 0.3, 0.2]
        e.set_pixel((0, 0), val1)
        val2 = [0.1, 0.131, 0.001]
        e.set_pixel((4, 4), val2)

        almost_equal_pixels(e.get_pixel((0, 0)), val1)
        almost_equal_pixels(e.get_pixel((4, 4)), val2)

        e_copy = e.copy()

        e.min = 0.5
        e.set_pixel((0, 0), val1)
        almost_equal_pixels(e.get_pixel((0, 0)), [0.5, 0.5, 0.5])

        e.max = 0.8
        val3 = [0.1, 0.6, 0.9]
        e.set_pixel((0, 0), val3)
        almost_equal_pixels(e.get_pixel((0, 0)), [0.5, 0.6, 0.8])

        almost_equal_pixels(e_copy.get_pixel((0, 0)), val1)
        assert e_copy.min == 0.0
        assert e_copy.max == 1.0

    def test_to_pil(self):
        e = get_exr_img_repr()

        img = e.to_pil()
        img_file = os.path.join(self.path, "img1.jpg")
        img.save(img_file)
        img.close()
        p = PILImgRepr()
        p.load_from_file(img_file)

        img2 = e.to_pil(use_extremas=True)
        assert isinstance(img2, Image.Image)
        img_alt = get_exr_img_repr(alt=True)
        img3 = img_alt.to_pil(use_extremas=True)
        assert isinstance(img3, Image.Image)

    def test_to_l_image(self):
        e = get_exr_img_repr()
        img = e.to_l_image()
        assert isinstance(img, Image.Image)
        assert img.mode == "L"

    def test_get_rgbf_extrema(self):
        e = get_exr_img_repr(alt=True)
        assert e.get_rgbf_extrema() == (0.0, 0.0)
        e = get_exr_img_repr()
        assert e.get_rgbf_extrema() == (3.71875, 0.10687255859375)


class TestImgFunctions(TempDirFixture, LogTestCase):

    def test_load_img(self):
        exr_img = load_img(get_test_exr())
        assert isinstance(exr_img, EXRImgRepr)
        assert exr_img.get_size() == (10, 10)

        img_path = self.temp_file_name("img.jpg")
        pil_img = get_pil_img_repr(img_path)
        assert isinstance(pil_img, PILImgRepr)
        assert pil_img.get_size() == (10, 10)

        assert load_img("notexisting") is None

    def test_blend_pil(self):
        img_path1 = self.temp_file_name("img1.png")
        img_path2 = self.temp_file_name("img2.png")
        make_test_img(img_path1)
        make_test_img(img_path2)

        img1 = PILImgRepr()
        img2 = PILImgRepr()
        img1.load_from_file(img_path1)
        img2.load_from_file(img_path2)
        img1 = get_pil_img_repr(img_path1)

        img = blend(img1, img2, 0.5)
        assert isinstance(img, PILImgRepr)
        assert img.get_pixel((3, 2)) == [255, 0, 0]

        make_test_img(img_path2, size=(15, 15))
        img2.load_from_file(img_path2)

        with self.assertLogs(logger, "ERROR"):
            assert blend(img1, img2, 0.5) is None

        make_test_img(img_path2, color=(0, 255, 30))
        img2.load_from_file(img_path2)

        assert img1.get_pixel((3, 2)) == [255, 0, 0]
        assert img2.get_pixel((3, 2)) == [0, 255, 30]

        img = blend(img1, img2, 0)
        assert img.get_pixel((3, 2)) == [255, 0, 0]
        img = blend(img1, img2, 1)
        assert img.get_pixel((3, 2)) == [0, 255, 30]

        assert img1.get_pixel((3, 2)) == [255, 0, 0]
        assert img2.get_pixel((3, 2)) == [0, 255, 30]
        img = blend(img1, img2, 0.5)
        assert img.get_pixel((3, 2)) == [127, 127, 15]

        img = blend(img1, img2, 0.1)
        assert img.get_pixel((3, 2)) == [229, 25, 3]

    def test_blend_exr(self):
        exr1 = get_exr_img_repr()
        exr2 = get_exr_img_repr(alt=True)

        exr = blend(exr1, exr2, 0)
        assert exr.get_pixel((3, 2)) == exr1.get_pixel((3, 2))

        exr = blend(exr1, exr2, 1)
        assert exr.get_pixel((3, 2)) == exr2.get_pixel((3, 2))

        assert exr2.get_pixel((3, 2)) == [0, 0, 0]

        assert exr1.get_pixel((3, 2)) == [0.381103515625,
                                          0.412353515625,
                                          0.42236328125]
        assert exr2.get_pixel((3, 2)) == [0,  0, 0]

        exr = blend(exr1, exr2, 0.5)
        almost_equal_pixels(exr.get_pixel((3, 2)), [0.1905, 0.206, 0.211])

        exr = blend(exr1, exr2, 0.9)
        almost_equal_pixels(exr.get_pixel((3, 2)), [0.0381, 0.0412, 0.0422])

    def test_load_as_pil(self):
        img_path = self.temp_file_name("path1.png")
        make_test_img(img_path)
        img = load_as_pil(img_path)
        assert isinstance(img, Image.Image)
        exr_path = get_test_exr()
        img = load_as_pil(exr_path)
        assert isinstance(img, Image.Image)
