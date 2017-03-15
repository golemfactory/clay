import os
import unittest

import Imath
from PIL import Image

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase

from apps.rendering.resources.imgrepr import (blend, compare_exr_imgs, compare_imgs,
                                              compare_pil_imgs, count_mse, count_psnr, EXRImgRepr,
                                              ImgRepr, load_img, logger, PILImgRepr, verify_img)


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


class TestImgRepr(unittest.TestCase):

    def test_functions(self):
        t = TImgRepr()
        t.load_from_file("file_")
        t.get_pixel((0, 0))
        t.get_size()
        t.copy()


def make_test_img(img_path, size=(10, 10), color=(255, 0, 0)):
    img = Image.new('RGB', size, color)
    img.save(img_path)
    img.close()


def get_pil_img_repr(path, size=(10, 10), color=(255, 0, 0)):
    make_test_img(path, size, color)
    p = PILImgRepr()
    p.load_from_file(path)
    return p


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


def _get_test_exr(alt=False):
    if not alt:
        filename = 'testfile.EXR'
    else:
        filename = 'testfile2.EXR'

    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def get_exr_img_repr(alt=False):
    exr = EXRImgRepr()
    exr_file = _get_test_exr(alt)
    exr.load_from_file(exr_file)
    return exr


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

        assert e.get_pixel((0, 0)) == [0.5703125, 0.53076171875, 0.432373046875]
        assert e.get_pixel((5, 5)) == [0.6982421875, 0.73193359375, 0.70556640625]
        assert e.get_pixel((9, 9)) == [0.461181640625, 0.52392578125, 0.560546875]

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

        assert exr1.get_pixel((3, 2)) == [0.381103515625, 0.412353515625, 0.42236328125]
        assert exr2.get_pixel((3, 2)) == [0,  0, 0]

        exr = blend(exr1, exr2, 0.5)
        almost_equal_pixels(exr.get_pixel((3, 2)), [0.1905, 0.206, 0.211])

        exr = blend(exr1, exr2, 0.9)
        almost_equal_pixels(exr.get_pixel((3, 2)), [0.0381, 0.0412, 0.0422])

    def test_advance_verify_imgs(self):
        pass

    def test_compare_pil_imgs(self):
        img_path1 = self.temp_file_name("img1.jpg")
        img_path2 = self.temp_file_name("img2.jpg")
        make_test_img(img_path1)
        make_test_img(img_path2)

        assert compare_pil_imgs(img_path1, img_path2)

        img = load_img(img_path1)
        img.set_pixel((0, 0), [253, 1, 1])
        img.img.save(img_path1)
        assert compare_pil_imgs(img_path1, img_path2)

        make_test_img(img_path1, color=(200, 0, 0))
        assert not compare_pil_imgs(img_path1, img_path2)

        make_test_img(img_path1, size=[11, 10], color=(255, 0, 0))
        with self.assertLogs(logger, level="INFO"):
            assert not compare_pil_imgs(img_path1, img_path2)

        with self.assertLogs(logger, level="INFO"):
            assert not compare_pil_imgs(img_path2, _get_test_exr())

    def test_compar_exr_imgs(self):
        assert compare_exr_imgs(_get_test_exr(), _get_test_exr())
        assert not compare_exr_imgs(_get_test_exr(), _get_test_exr(alt=True))
        with self.assertLogs(logger, level="INFO"):
            assert not compare_exr_imgs(_get_test_exr(), "Not existing")

        pil_img_path = self.temp_file_name("img1.png")
        make_test_img(pil_img_path)
        with self.assertLogs(logger, level="INFO"):
            assert not compare_exr_imgs(_get_test_exr(), pil_img_path)

    def test_count_psnr(self):
        assert count_psnr(10, 10) == 10
        assert count_psnr(10, 1) == -10
        assert count_psnr(1, 10) == 20
        assert int(count_psnr(0.5, 10)) == 23
        assert count_psnr(100, 20)
        with self.assertRaises(ValueError):
            count_psnr(0, 10)

        with self.assertRaises(ValueError):
            count_psnr(10, 0)

        with self.assertRaises(ValueError):
            count_psnr(-1, 10)

        with self.assertRaises(ValueError):
            count_psnr(10, -1)

        assert round(count_psnr(1514.6), 2) == 16.33
        assert round(count_psnr(703.4), 2) == 19.66
        assert round(count_psnr(710.4), 2) == 19.62
        assert round(count_psnr(396.1), 2) == 22.15
        assert round(count_psnr(326.0), 2) == 23.00
        assert round(count_psnr(221.2), 2) == 24.68
        assert round(count_psnr(164.7), 2) == 25.96
        assert round(count_psnr(113.8), 2) == 27.57
        assert round(count_psnr(82.5), 2) == 28.97
        assert round(count_psnr(78.5), 2) == 29.18
        assert round(count_psnr(66.1), 2) == 29.93
        assert round(count_psnr(64.4), 2) == 30.04
        assert round(count_psnr(57.4437), 2) == 30.54

    def test_count_mse(self):

        # Both arguments are not ImgRepr
        with self.assertRaises(TypeError):
            count_mse("notanimgrepr1", "notanimgrepr2")

        img_path = self.temp_file_name("img.png")
        img1 = get_pil_img_repr(img_path)

        # Only one argument is ImgRepr
        with self.assertRaises(TypeError):
            count_mse("notanimgrepr", img1)

        with self.assertRaises(TypeError):
            count_mse(img1, "notanimgrepr")

        # ImgRepr before being image is loaded
        img_before_loaded = PILImgRepr()
        with self.assertRaises(Exception):
            count_mse(img_before_loaded, img1)

        with self.assertRaises(Exception):
            count_mse(img1, img_before_loaded)

        # Proper comparison (same images)
        img2_path = self.temp_file_name("img2.png")
        img2 = get_pil_img_repr(img2_path)

        assert count_mse(img1, img2) == 0

        # Wrong box values
        with self.assertRaises(Exception):
            count_mse(img1, img2, box="Not box")

        with self.assertRaises(ValueError):
            count_mse(img1, img2, box=(0, 1))

        with self.assertRaises(ValueError):
            count_mse(img1, img2, box=(1, 0))

        with self.assertRaises(ValueError):
            count_mse(img1, img2, box=(0, 0))

        # Img2 too small
        img2 = get_pil_img_repr(img2_path, (5, 5))
        with self.assertRaises(Exception):
            count_mse(img1, img2)

        # Proper execution with smaller img2
        assert count_mse(img1, img2, box=(5, 5)) == 0
        assert count_mse(img1, img2, start1=(5, 5), box=(5, 5)) == 0

        img2 = get_pil_img_repr(img2_path, (10, 10), (253, 0, 0))
        assert count_mse(img1, img2) == 1

        img2 = get_pil_img_repr(img2_path, (10, 10))
        img2.set_pixel((0, 0), (0, 0, 0))
        assert count_mse(img1, img2) == 216

        assert count_mse(img1, img2, start1=(0, 0), start2=(2, 2), box=(7, 7)) == 0

    def test_compare_imgs(self):
        img1_path = self.temp_file_name("img1.png")
        img2_path = self.temp_file_name("img2.png")

        img1 = get_pil_img_repr(img1_path)
        img2 = get_pil_img_repr(img2_path)

        assert compare_imgs(img1, img2)
        assert compare_imgs(img1, img2, start1=(4, 4), box=(5, 5))

        with self.assertRaises(Exception):
            compare_imgs(img1, img2, box=(0, 0))

        with self.assertRaises(Exception):
            compare_imgs(img1, img2, start2=(3, 3))

        exr_img1 = get_exr_img_repr()
        exr_img2 = get_exr_img_repr(alt=True)

        assert not compare_imgs(exr_img1, exr_img2, max_col=1)
        assert compare_imgs(exr_img1, exr_img1, max_col=1)
        exr_img2_copy = exr_img2.copy()

        for i in range(10):
            for j in range(10):
                exr_img2.set_pixel((j, i), [0.1, 0.1, 0.1])

        assert compare_imgs(exr_img2, exr_img2_copy)
        assert not compare_imgs(exr_img2, exr_img2_copy, max_col=1)


















