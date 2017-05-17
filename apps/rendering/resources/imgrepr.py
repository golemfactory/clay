import os
import abc
import logging
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

    @abc.abstractmethod
    def to_pil(self):
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

    def to_pil(self):
        return self.img


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
        return self.dw.max.x - self.dw.min.x + 1, \
               self.dw.max.y - self.dw.min.y + 1

    def get_pixel(self, (i, j)):
        return [c.getpixel((i, j)) for c in self.rgb]

    def set_pixel(self, (i, j), color):
        for c in range(0, len(self.rgb)):
            self.rgb[c].putpixel((i, j), max(min(self.max, color[c]),
                                             self.min))

    def get_rgbf_extrema(self):
        extrema = [im.getextrema() for im in self.rgb]
        darkest = min([lo for (lo, hi) in extrema])
        lightest = max([hi for (lo, hi) in extrema])
        return lightest, darkest

    def to_pil(self, use_extremas=False):
        if use_extremas:
            lightest, darkest = self.get_rgbf_extrema()
        else:
            lightest = self.max
            darkest = self.min

        if lightest == darkest:
            lightest = 0.1 + darkest
        scale = 255.0 / (lightest - darkest)

        def normalize_0_255(v):
            return v * scale

        rgb8 = [im.point(normalize_0_255).convert("L") for im in self.rgb]
        return Image.merge("RGB", rgb8)

    def to_l_image(self):
        img = self.to_pil()
        return img.convert('L')

    def copy(self):
        e = EXRImgRepr()
        e.load_from_file(self.file_path)
        e.dw = deepcopy(self.dw)
        e.rgb = deepcopy(self.rgb)
        e.min = self.min
        e.max = self.max
        return e


def load_img(file_):
    """
    Load image from file path and return ImgRepr
    :param str file_: path to the file  
    :return ImgRepr | None: Return ImgRepr for special file type or None 
    if there was an error 
    """
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


def load_as_pil(file_):
    """ Load image from file path and retun PIL Image representation
     :param str file_: path to the file 
     :return Image.Image | None: return PIL Image represantion or None 
     if there was an error
    """

    img = load_img(file_)
    if img:
        return img.to_pil()


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
