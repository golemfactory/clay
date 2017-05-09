import os

from PIL import Image


from apps.rendering.resources.imgcompare import (advance_verify_img,
                                                 check_size, compare_exr_imgs,
                                                 compare_imgs,
                                                 compare_pil_imgs,
                                                 calculate_mse,
                                                 calculate_psnr, logger)
from apps.rendering.resources.imgrepr import load_img, PILImgRepr

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase

from imghelper import (get_exr_img_repr, get_pil_img_repr, get_test_exr,
                       make_test_img)


class TestCompareImgFunctions(TempDirFixture, LogTestCase):
    def test_check_size(self):
        file1 = self.temp_file_name('img.png')
        for y in [10, 11]:
            x = 10
            sample_img = Image.new("RGB", (x, y))
            sample_img.save(file1)
            self.assertTrue(os.path.isfile(file1))
            self.assertTrue(check_size(file1, x, y))
            self.assertFalse(check_size(file1, x, y + 1))
            self.assertFalse(check_size(file1, x, y - 1))
            self.assertFalse(check_size(file1, x + 1, y))

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
            assert not compare_pil_imgs(img_path2, get_test_exr())

    def test_compar_exr_imgs(self):
        assert compare_exr_imgs(get_test_exr(), get_test_exr())
        assert not compare_exr_imgs(get_test_exr(), get_test_exr(alt=True))
        with self.assertLogs(logger, level="INFO"):
            assert not compare_exr_imgs(get_test_exr(), "Not existing")

        pil_img_path = self.temp_file_name("img1.png")
        make_test_img(pil_img_path)
        with self.assertLogs(logger, level="INFO"):
            assert not compare_exr_imgs(get_test_exr(), pil_img_path)

    def test_calculate_psnr(self):
        assert calculate_psnr(10, 10) == 10
        assert calculate_psnr(10, 1) == -10
        assert calculate_psnr(1, 10) == 20
        assert int(calculate_psnr(0.5, 10)) == 23
        assert calculate_psnr(100, 20)
        with self.assertRaises(ValueError):
            calculate_psnr(0, 10)

        with self.assertRaises(ValueError):
            calculate_psnr(10, 0)

        with self.assertRaises(ValueError):
            calculate_psnr(-1, 10)

        with self.assertRaises(ValueError):
            calculate_psnr(10, -1)

        assert round(calculate_psnr(1514.6), 2) == 16.33
        assert round(calculate_psnr(703.4), 2) == 19.66
        assert round(calculate_psnr(710.4), 2) == 19.62
        assert round(calculate_psnr(396.1), 2) == 22.15
        assert round(calculate_psnr(326.0), 2) == 23.00
        assert round(calculate_psnr(221.2), 2) == 24.68
        assert round(calculate_psnr(164.7), 2) == 25.96
        assert round(calculate_psnr(113.8), 2) == 27.57
        assert round(calculate_psnr(82.5), 2) == 28.97
        assert round(calculate_psnr(78.5), 2) == 29.18
        assert round(calculate_psnr(66.1), 2) == 29.93
        assert round(calculate_psnr(64.4), 2) == 30.04
        assert round(calculate_psnr(57.4437), 2) == 30.54

    def test_calculate_mse(self):

        # Both arguments are not ImgRepr
        with self.assertRaises(TypeError):
            calculate_mse("notanimgrepr1", "notanimgrepr2")

        img_path = self.temp_file_name("img.png")
        img1 = get_pil_img_repr(img_path)

        # Only one argument is ImgRepr
        with self.assertRaises(TypeError):
            calculate_mse("notanimgrepr", img1)

        with self.assertRaises(TypeError):
            calculate_mse(img1, "notanimgrepr")

        # ImgRepr before being image is loaded
        img_before_loaded = PILImgRepr()
        with self.assertRaises(Exception):
            calculate_mse(img_before_loaded, img1)

        with self.assertRaises(Exception):
            calculate_mse(img1, img_before_loaded)

        # Proper comparison (same images)
        img2_path = self.temp_file_name("img2.png")
        img2 = get_pil_img_repr(img2_path)

        assert calculate_mse(img1, img2) == 0

        # Wrong box values
        with self.assertRaises(Exception):
            calculate_mse(img1, img2, box="Not box")

        with self.assertRaises(ValueError):
            calculate_mse(img1, img2, box=(0, 1))

        with self.assertRaises(ValueError):
            calculate_mse(img1, img2, box=(1, 0))

        with self.assertRaises(ValueError):
            calculate_mse(img1, img2, box=(0, 0))

        # Img2 too small
        img2 = get_pil_img_repr(img2_path, (5, 5))
        with self.assertRaises(Exception):
            calculate_mse(img1, img2)

        # Proper execution with smaller img2
        assert calculate_mse(img1, img2, box=(5, 5)) == 0
        assert calculate_mse(img1, img2, start1=(5, 5), box=(5, 5)) == 0

        img2 = get_pil_img_repr(img2_path, (10, 10), (253, 0, 0))
        assert calculate_mse(img1, img2) == 1

        img2 = get_pil_img_repr(img2_path, (10, 10))
        img2.set_pixel((0, 0), (0, 0, 0))
        assert calculate_mse(img1, img2) == 216

        assert calculate_mse(img1, img2, start1=(0, 0), start2=(2, 2), box=(7, 7)) == 0

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

    def test_advance_verify_img(self):
        img_path = self.temp_file_name("path1.png")
        make_test_img(img_path)

        assert not advance_verify_img("not an image", 10, 10, (0, 0), (2, 2),
                                      img_path, (0, 0))
        assert not advance_verify_img(img_path, 10, 10, (0, 0), (2, 2),
                                      "not an image", (0, 0))

        assert advance_verify_img(img_path, 10, 10, (0, 0), (2, 2), img_path,
                                  (0, 0))

        assert not advance_verify_img(img_path, 10, 9, (0, 0), (2, 2),
                                      img_path, (0, 0))
        assert not advance_verify_img(img_path, 9, 10, (0, 0), (2, 2),
                                      img_path, (0, 0))
        assert not advance_verify_img(img_path, 10, 10, (0, 0), (0, 2),
                                      img_path, (0, 0))
        assert not advance_verify_img(img_path, 10, 10, (0, 0), (2, 0),
                                      img_path, (0, 0))
        assert not advance_verify_img(img_path, 10, 10, (0, 0), (11, 10),
                                      img_path, (0, 0))
        assert not advance_verify_img(img_path, 10, 10, (0, 0), (10, 11),
                                      img_path, (0, 0))

        exr_path = get_test_exr()

        assert advance_verify_img(exr_path, 10, 10, (0, 0), (2, 2), exr_path,
                                  (0, 0))
        exr_path2 = get_test_exr(alt=True)
        assert not advance_verify_img(exr_path, 10, 10, (0, 0), (2, 2),
                                      exr_path2, (0, 0))
        assert not advance_verify_img(exr_path, 10, 10, (0, 0), (2, 2),
                                      img_path, (0, 0))
        assert not advance_verify_img(img_path, 10, 10, (0, 0), (2, 2),
                                      exr_path, (0, 0))
