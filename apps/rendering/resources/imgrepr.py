import os
import abc
import logging
from copy import deepcopy
from typing import Optional
import numpy
import cv2
import OpenEXR
import Imath

logger = logging.getLogger("apps.rendering")


class OpenCVError(Exception):
    pass


class ImgRepr(object, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def load_from_file(self, file_):
        return

    @abc.abstractmethod
    def get_pixel(self, xy):
        return

    @abc.abstractmethod
    def set_pixel(self, xy, color):
        return

    @abc.abstractmethod
    def get_size(self):
        return

    @abc.abstractmethod
    def copy(self):
        return

    @abc.abstractmethod
    def close(self):
        return


class OpenCVImgRepr:
    RGB = 3
    RGBA = 4
    IMG_F32 = numpy.float32
    IMG_U8 = numpy.uint8
    IMG_U16 = numpy.uint16

    def __init__(self):
        self.img = None

    def set_pixel(self, xy, color):
        xy = tuple(reversed(xy))
        bgr_color = tuple(reversed(color))
        if self.img.shape[2] == 4 and len(bgr_color) == 3:
            bgr_color = bgr_color + (255,)
        self.img[xy] = bgr_color

    def get_pixel(self, xy):
        # reverse because OpenCV stores colors as BGR
        return tuple(reversed(self.img[xy[1], xy[0]]))

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass

    def get_height(self):
        return self.img.shape[0]

    def get_width(self):
        return self.img.shape[1]

    def resize(self, width, height, interpolation=cv2.INTER_LINEAR):
        self.img = cv2.resize(self.img, (width, height),
                              interpolation=interpolation)

        return self

    def load_from_file(self, path, mode=cv2.IMREAD_UNCHANGED):
        try:
            self.img = cv2.imread(path, mode)
            if self.img is None:
                raise OpenCVError('cv2 read image \"{}\" as None'.format(path))
        except cv2.error as e:
            logger.error('Error reading image: {}'.format(str(e)))
            raise OpenCVError('Cannot read image: {}'.format(str(e))) from e

    @staticmethod
    def empty(width, height, channels=3, dtype=numpy.uint8, color=None):
        imgRepr = OpenCVImgRepr()
        imgRepr.img = numpy.zeros((height, width, channels), dtype)
        if channels == 4:
            imgRepr.img[:] = (0, 0, 0, 255)
        if color:
            imgRepr.img[:] = tuple(reversed(color))

        return imgRepr

    def get_channels(self):
        return self.img.shape[2]

    def get_type(self):
        return self.img.dtype

    @staticmethod
    def from_image_file(image_path):
        imgRepr = OpenCVImgRepr()
        imgRepr.load_from_file(image_path)
        return imgRepr

    def get_size(self):
        return tuple(reversed(self.img.shape[:2]))

    def paste_image(self, img_repr, x, y):
        try:
            self.img[y:y + img_repr.img.shape[0], x:img_repr.img.shape[1]] = \
                img_repr.img
        except (cv2.error, ValueError) as e:
            raise OpenCVError('Pasting image failed') from e

    def add(self, other):
        try:
            self.img = cv2.add(self.img, other.img)
        except cv2.error as e:
            raise OpenCVError('opencv adding images failed') from e

    def try_adjust_type(self, mode):
        if mode == self.get_type():
            return
        elif self.get_type() == OpenCVImgRepr.IMG_F32:
            self._img32F_to_img8U()
        elif self.get_type() == OpenCVImgRepr.IMG_U16:
            self._img16U_to_img8U()
        else:
            raise OpenCVError('Conversion from {} to {} is not supported'
                              .format(str(self.get_type()), str(mode)))

    def save_with_extension(self, path, extension):
        # in OpenCV extension must be given in a filename
        # some paths are without extension, need to rename it then

        file_path = '{}_{}.{}'.format(path, "tmp", extension.lower())
        self.save(file_path)
        os.replace(file_path, path)

    def save(self, path):
        try:
            cv2.imwrite(path, self.img)
        except cv2.error as e:
            logger.error('Error saving image: {}'.format(str(e)))
            raise OpenCVError('Cannot save image {}: {}'.format(path,
                                                                str(e))) from e

    @staticmethod
    def load_from_file_or_empty(img_path, width, height, channels=3,
                                dtype=numpy.uint8):
        imgRepr = OpenCVImgRepr()
        imgRepr.img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED) or \
            OpenCVImgRepr.empty(width, height, channels, dtype)
        return imgRepr

    def _img32F_to_img8U(self):
        self.img = cv2.convertScaleAbs(self.img, alpha=255, beta=0)

    def _img16U_to_img8U(self):
        self.img = cv2.convertScaleAbs(self.img, alpha=255.0/65535.0, beta=0)


class EXRImgRepr(ImgRepr):
    def __init__(self):
        self.img = None
        self.type = "EXR"
        self.dw = None
        self.pixel_type = Imath.PixelType(Imath.PixelType.FLOAT)
        self.bgr = None
        self.min = 0.0
        self.max = 1.0
        self.file_path = None

    def _convert_openexr_to_opencv_bgr(self):
        width, height = self.get_size()
        bytes_r, bytes_g, bytes_b = self.img.channels("RGB")
        r = numpy.fromstring(bytes_r, dtype=numpy.float32)
        g = numpy.fromstring(bytes_g, dtype=numpy.float32)
        b = numpy.fromstring(bytes_b, dtype=numpy.float32)

        for channel in r, g, b:
            for pixel_value in numpy.nditer(channel, op_flags=['readwrite']):
                pixel_value[...] = round(pixel_value * 255)

        opencv_img = numpy.zeros((height, width, 3), dtype=numpy.uint8)
        r = numpy.reshape(r, (-1, width))
        g = numpy.reshape(g, (-1, width))
        b = numpy.reshape(b, (-1, width))
        opencv_img[:, :, 0] = b
        opencv_img[:, :, 1] = g
        opencv_img[:, :, 2] = r
        return opencv_img

    def load_from_file(self, file_):
        self.img = OpenEXR.InputFile(file_)
        self.dw = self.img.header()['dataWindow']
        self.bgr = self._convert_openexr_to_opencv_bgr()

        self.file_path = file_
        self.name = os.path.basename(file_)

    def get_size(self):
        return self.dw.max.x - self.dw.min.x + 1, \
               self.dw.max.y - self.dw.min.y + 1

    def get_pixel(self, xy):
        return self.bgr[xy[::-1]].tolist()[::-1]

    def set_pixel(self, xy, color):
        x, y = xy
        self.bgr[y, x] = color[::-1]

    def copy(self):
        e = EXRImgRepr()
        e.load_from_file(self.file_path)
        e.dw = deepcopy(self.dw)
        e.bgr = deepcopy(self.bgr)
        e.min = self.min
        e.max = self.max
        return e

    def close(self):
        if self.img:
            self.img.close()


def load_img(file_: str) -> Optional[ImgRepr]:
    """
    Load image from file path and return ImgRepr
    :param file_: path to the file
    :return: Return ImgRepr for special file type or None
    if there was an error
    """
    try:
        _, ext = os.path.splitext(file_)
        if ext.upper() != ".EXR":
            img = OpenCVImgRepr()
        else:
            img = EXRImgRepr()
        img.load_from_file(file_)
        return img
    except Exception as err:
        logger.warning("Can't load img file {}:{}".format(file_, err))
        return None
