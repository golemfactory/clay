import os
import abc
import logging
import math
from copy import deepcopy
import OpenEXR
import Imath
from PIL import Image

logger = logging.getLogger("apps.rendering")


class ImgRepr(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def load_from_file(self, file_):
        return

    @abc.abstractmethod
    def get_pixel(self, (i, j)):
        return

    @abc.abstractmethod
    def set_pixel(self, (i, j), color):
        return

    @abc.abstractmethod
    def get_size(self):
        return

    @abc.abstractmethod
    def copy(self):
        return


class PILImgRepr(ImgRepr):
    def __init__(self):
        self.img = None
        self.type = "PIL"

    def load_from_file(self, file_):
        self.img = Image.open(file_)
        self.img = self.img.convert('RGB')

    def get_size(self):
        return self.img.size

    def get_pixel(self, (i, j)):
        return list(self.img.getpixel((i, j)))

    def set_pixel(self, (i, j), color):
        color = tuple(int(c) for c in color)
        self.img.putpixel((i, j), color)

    def copy(self):
        return deepcopy(self)


class EXRImgRepr(ImgRepr):
    def __init__(self):
        self.img = None
        self.type = "EXR"
        self.dw = None
        self.pt = Imath.PixelType(Imath.PixelType.FLOAT)
        self.rgb = None
        self.min = 0.0
        self.max = 1.0
        self.file_path = None

    def load_from_file(self, file_):
        self.img = OpenEXR.InputFile(file_)
        self.dw = self.img.header()['dataWindow']
        self.rgb = [Image.frombytes("F", self.get_size(),
                                    self.img.channel(c, self.pt))
                    for c in "RGB"]
        self.file_path = file_

    def get_size(self):
        return self.dw.max.x - self.dw.min.x + 1, self.dw.max.y - self.dw.min.y + 1

    def get_pixel(self, (i, j)):
        return [c.getpixel((i, j)) for c in self.rgb]

    def set_pixel(self, (i, j), color):
        for c in range(0, len(self.rgb)):
            self.rgb[c].putpixel((i, j), max(min(self.max, color[c]), self.min))

    def to_pil(self):
        extrema = [im.getextrema() for im in self.rgb]
        darkest = min([lo for (lo, hi) in extrema])
        lightest = max([hi for (lo, hi) in extrema])
        scale = 255.0 / (lightest - darkest)

        def normalize_0_255(v):
            return v * scale

        rgb8 = [im.point(normalize_0_255).convert("L") for im in self.rgb]
        return Image.merge("RGB", rgb8)

    def copy(self):
        e = EXRImgRepr()
        e.load_from_file(self.file_path)
        e.dw = deepcopy(self.dw)
        e.rgb = deepcopy(self.rgb)
        e.min = self.min
        e.max = self.max
        return e


def load_img(file_):
    try:
        _, ext = os.path.splitext(file_)
        if ext.upper() != ".EXR":
            img = PILImgRepr()
        else:
            img = EXRImgRepr()
        img.load_from_file(file_)
        return img
    except Exception as err:
        logger.warning("Can't verify img file {}:{}".format(file_, err))
        return None


def advance_verify_img(file_, res_x, res_y, start_box, box_size, compare_file, cmp_start_box):
    try:
        img = load_img(file_)
        cmp_img = load_img(compare_file)
        if img is None or cmp_img is None:
            return False
        if img.get_size() != (res_x, res_y):
            return False
        if box_size[0] <= 0 or box_size[1] <= 0 or box_size[0] > res_x or box_size[1] > res_y:
            logger.error("Wrong box size for advanced verification {}".format(box_size))

        if isinstance(img, PILImgRepr) and isinstance(cmp_img, PILImgRepr):
            return compare_imgs(img, cmp_img, start1=start_box, start2=cmp_start_box, box=box_size)
        else:
            return compare_imgs(img, cmp_img, max_col=1, start1=start_box, start2=cmp_start_box,
                                box=box_size)
    except Exception:
        logger.exception("Cannot verify images {} and {}".format(file_, compare_file))
        return False


def verify_img(file_, res_x, res_y):
    # allow +/-1 difference in y size - workaround for blender inproperly rounding floats
    img = load_img(file_)
    if img is None:
        return False
    img_x, img_y = img.get_size()
    return (img_x == res_x) and (abs(img_y - res_y) <= 1)


def compare_pil_imgs(file1, file2):
    try:
        img1 = PILImgRepr()
        img1.load_from_file(file1)
        img2 = PILImgRepr()
        img2.load_from_file(file2)
        return compare_imgs(img1, img2)
    except Exception as err:
        logger.info("Can't compare images {}, {}: {}".format(file1, file2, err))
        return False


def compare_exr_imgs(file1, file2):
    try:
        img1 = EXRImgRepr()
        img1.load_from_file(file1)
        img2 = EXRImgRepr()
        img2.load_from_file(file2)
        return compare_imgs(img1, img2, 1)
    except Exception as err:
        logger.info("Can't compare images {}, {}: {}".format(file1, file2, err))
        return False


def blend(img1, img2, alpha):
    (res_x, res_y) = img1.get_size()
    if img2.get_size() != (res_x, res_y):
        logger.error("Both images must have the same size.")
        return

    img = img1.copy()

    for x in range(0, res_x):
        for y in range(0, res_y):
            p1 = img1.get_pixel((x, y))
            p2 = img2.get_pixel((x, y))
            p = map(lambda c1, c2: c1 * (1 - alpha) + c2 * alpha, p1, p2)
            img.set_pixel((x, y), p)

    return img


PSNR_ACCEPTABLE_MIN = 30


def compare_imgs(img1, img2, max_col=255, start1=(0, 0), start2=(0, 0), box=None):
    mse = count_mse(img1, img2, start1, start2, box)
    logger.debug("MSE = {}".format(mse))
    if mse == 0:
        return True
    psnr = count_psnr(mse, max_col)
    logger.debug("PSNR = {}".format(psnr))
    return psnr >= PSNR_ACCEPTABLE_MIN


def count_psnr(mse, max_=255):
    if mse <= 0 or max_ <= 0:
        raise ValueError("MSE & MAX_ must be higher than 0")
    return 20 * math.log10(max_) - 10 * math.log10(mse)


def count_mse(img1, img2, start1=(0, 0), start2=(0, 0), box=None):
    mse = 0
    if not isinstance(img1, ImgRepr) or not isinstance(img2, ImgRepr):
        raise TypeError("img1 and img2 must be ImgRepr")

    if box is None:
        (res_x, res_y) = img1.get_size()
    else:
        (res_x, res_y) = box
    for i in range(0, res_x):
        for j in range(0, res_y):
            [r1, g1, b1] = img1.get_pixel((start1[0] + i, start1[1] + j))
            [r2, g2, b2] = img2.get_pixel((start2[0] + i, start2[1] + j))
            mse += (r1 - r2) * (r1 - r2) + (g1 - g2) * (g1 - g2) + (b1 - b2) * (b1 - b2)

    if res_x <= 0 or res_y <= 0:
        raise ValueError("Image or box resolution must be greater than 0")
    mse /= res_x * res_y * 3
    return mse
