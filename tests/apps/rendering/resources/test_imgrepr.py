import os
import unittest

import Imath
from PIL import Image

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase

from apps.rendering.resources.imgrepr import (blend, EXRImgRepr, ImgRepr, load_img, logger,
                                              PILImgRepr, verify_img)


class TImgRepr(ImgRepr):

    def load_from_file(self, file_):
        super(TImgRepr, self).load_from_file(file_)

    def get_pixel(self, (i, j)):
        super(TImgRepr, self).get_pixel((i, j))

    def get_size(self):
        super(TImgRepr, self).get_size()

    def set_pixel(self, (i, j), color):
        super(TImgRepr, self).set_pixel((i, j), color)


class TestImgRepr(unittest.TestCase):

    def test_functions(self):
        t = TImgRepr()
        t.load_from_file("file_")
        t.get_pixel((0, 0))
        t.get_size()


def make_test_img(img_path, size=(10, 10), color=(255, 0, 0)):
    img = Image.new('RGB', size, color)
    img.save(img_path)
    img.close()


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
        make_test_img(img_path)

        p = PILImgRepr()

        p.load_from_file(img_path)
        assert isinstance(p.img, Image.Image)
        assert p.get_size() == (10, 10)
        assert p.get_pixel((0, 0)) == [255, 0, 0]
        assert p.get_pixel((5, 5)) == [255, 0, 0]
        assert p.get_pixel((9, 9)) == [255, 0, 0]
        with self.assertRaises(Exception):
            p.get_pixel((10, 10))

        p.set_pixel((3, 5), [10, 11, 12])
        assert p.get_pixel((3, 5)) == [10, 11, 12]


def _get_test_exr(alt=False):
    if not alt:
        filename = 'testfile.EXR'
    else:
        filename = 'testfile2.EXR'

    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


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

    def test_errors(self):
        e = EXRImgRepr()

        with self.assertRaises(Exception):
            e.load_from_file("unknown file")
        with self.assertRaises(Exception):
            e.get_size()
        with self.assertRaises(Exception):
            e.get_pixel((0, 0))

    def test_exr_repr(self):
        e = EXRImgRepr()
        img_file = _get_test_exr()
        e.load_from_file(img_file)
        assert e.img is not None
        assert e.dw is not None
        assert e.rgb is not None

        assert e.get_size() == (10, 10)

        assert e.get_pixel((0, 0)) == [0.5703125, 0.53076171875, 0.432373046875]
        assert e.get_pixel((5, 5)) == [0.6982421875, 0.73193359375, 0.70556640625]
        assert e.get_pixel((9, 9)) == [0.461181640625, 0.52392578125, 0.560546875]

        with self.assertRaises(Exception):
            e.get_pixel((10, 10))

    def test_set_pixel(self):
        e = EXRImgRepr()
        img_file = _get_test_exr()
        e.load_from_file(img_file)
        val1 = [0.4, 0.3, 0.2]
        e.set_pixel((0, 0), val1)
        val2 = [0.1, 0.131, 0.001]
        e.set_pixel((4, 4), val2)

        def almost_compare(v1, v2):
            assert abs(v1 - v2) < 0.001

        def almost_compare_pixels(pix1, pix2):
            for c1, c2 in zip(pix1, pix2):
                almost_compare(c1, c2)

        almost_compare_pixels(e.get_pixel((0, 0)), val1)
        almost_compare_pixels(e.get_pixel((4, 4)), val2)

        e.min = 0.5
        e.set_pixel((0, 0), val1)
        almost_compare_pixels(e.get_pixel((0, 0)), [0.5, 0.5, 0.5])

        e.max = 0.8
        val3 = [0.1, 0.6, 0.9]
        e.set_pixel((0, 0), val3)
        almost_compare_pixels(e.get_pixel((0, 0)), [0.5, 0.6, 0.8])

    def test_to_pil(self):
        e = EXRImgRepr()
        img_file = _get_test_exr()
        e.load_from_file(img_file)

        img = e.to_pil()
        img_file = os.path.join(self.path, "img1.jpg")
        img.save(img_file)
        img.close()
        p = PILImgRepr()
        p.load_from_file(img_file)


class TestImgFunctions(TempDirFixture, LogTestCase):
    def test_verify_img(self):
        file1 = self.temp_file_name('img.png')
        for y in range(100, 200):
            x = 100
            sample_img = Image.new("RGB", (x, y))
            sample_img.save(file1)
            self.assertTrue(os.path.isfile(file1))
            self.assertTrue(verify_img(file1, x, y))
            self.assertTrue(verify_img(file1, x, y + 1))
            self.assertTrue(verify_img(file1, x, y - 1))
            self.assertFalse(verify_img(file1, x + 1, y))

    def test_load_img(self):
        exr_img = load_img(_get_test_exr())
        assert isinstance(exr_img, EXRImgRepr)
        assert exr_img.get_size() == (10, 10)

        img_path = self.temp_file_name("img.jpg")
        make_test_img(img_path)
        pil_img = load_img(img_path)
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
        exr1 = EXRImgRepr()
        exr2 = EXRImgRepr()

        exr1_file = _get_test_exr()
        exr2_file = _get_test_exr(alt=True)

        exr1.load_from_file(exr1_file)
        exr2.load_from_file(exr2_file)

        print exr1.get_pixel((3, 2))
        exr = blend(exr1, exr2, 0)
        assert exr.get_pixel((3, 2)) == exr1.get_pixel((3, 2))

        exr = blend(exr1, exr2, 1)
        assert exr.get_pixel((3, 2)) == exr2.get_pixel((3, 2))

        assert exr2.get_pixel((3, 2)) == [0, 0, 0]

        print exr1.get_pixel((3, 2))
        assert False

        exr = blend(exr1, exr2, 0.5)






