import logging
import math
from random import uniform
from typing import Optional

import numpy
from ssim import compute_ssim

from apps.rendering.resources.imgrepr import (ImgRepr, PILImgRepr)
from golem.verificator.constants import SubtaskVerificationState


logger = logging.getLogger('apps.rendering')


class ImgStatistics:
    def __init__(self, base_image: ImgRepr, image: ImgRepr) -> None:
        if base_image.get_size() != image.get_size():
            raise ValueError('base_image and image are of different sizes.')

        self.image = image
        self.ssim = compute_ssim(base_image.to_pil(), self.image.to_pil())
        self.mse, self.norm_mse = \
            self._calculate_color_normalized_mse(base_image, self.image)
        self.mse_bw, norm_mse_bw = \
            self._calculate_greyscale_normalized_mse(base_image, self.image)
        self.psnr = self._calculate_psnr(self.mse)

    @property
    def name(self) -> Optional[str]:
        name = None
        if isinstance(self.image, PILImgRepr):
            name = self.image.get_name()

        return name

    @staticmethod
    def _calculate_greyscale_normalized_mse(image_1: ImgRepr,
                                            image_2: ImgRepr):  # pylint: disable=too-many-locals
        (resolution_x, resolution_y) = image_1.get_size()

        image_1_greyscale = image_1.to_pil().convert('L')  # makes it greyscale
        image_2_greyscale = image_2.to_pil().convert('L')  # makes it greyscale

        numpy_image_1 = numpy.array(image_1_greyscale).astype(
            numpy.float32, copy=False)
        numpy_image_2 = numpy.array(image_2_greyscale).astype(
            numpy.float32, copy=False)

        mse_bw = 0
        for i, numpy_image_1_item in enumerate(numpy_image_1):
            for j in range(len(numpy_image_1[0])):
                mse_bw += (numpy_image_1_item[j] - numpy_image_2[i][j]) \
                          * (numpy_image_1_item[j] - numpy_image_2[i][j])

        mse_bw /= resolution_x * resolution_y

        # max value of pixel is 255
        max_possible_mse = resolution_x * resolution_y * 255
        norm_mse = mse_bw / max_possible_mse

        return mse_bw, norm_mse

    @staticmethod
    def _calculate_color_normalized_mse(image_1, image_2):  # pylint: disable=too-many-locals
        mse = 0
        (resolution_x, resolution_y) = image_1.get_size()

        for i in range(0, resolution_x):
            for j in range(0, resolution_y):
                [r1, g1, b1] = image_1.get_pixel((i, j))
                [r2, g2, b2] = image_2.get_pixel((i, j))
                mse += (r1 - r2) * (r1 - r2) + \
                       (g1 - g2) * (g1 - g2) + \
                       (b1 - b2) * (b1 - b2)

        mse /= resolution_x * resolution_y * 3

        # max value of pixel is 255
        max_possible_mse = resolution_x * resolution_y * 3 * 255
        norm_mse = mse / max_possible_mse

        return mse, norm_mse

    @staticmethod
    def _calculate_psnr(mse, max_=255):
        if mse <= 0 or max_ <= 0:
            raise ValueError('MSE & MAX_ must be higher than 0')
        return 20 * math.log10(max_) - 10 * math.log10(mse)

    def get_stats(self):
        return self.ssim, self.mse, self.norm_mse, self.mse_bw, self.psnr


class ImgVerifier:

    @staticmethod
    def crop_img_relative(image, crop_window):
        """
        :param image: input PILImgRepr()
        :param crop_window:
        Values describing render region that range from min (0) to max (1)
        in order xmin, xmax, ymin,ymax. (0,0) is top left
        :return:
        a rectangular region from this image:
        left, upper, right, and lower pixel ordinate.
        """

        (resolution_x, resolution_y) = image.get_size()

        left = int(math.ceil(resolution_x * crop_window[0]))
        right = int(math.ceil(resolution_x * crop_window[1]))
        lower = int(math.ceil(resolution_y * crop_window[2]))
        upper = int(math.ceil(resolution_y * crop_window[3]))

        # in PIL's world (0,0) is bottom left ;p
        cropped_img = image.to_pil().crop((left, lower, right, upper))
        p = PILImgRepr()
        p.load_from_pil_object(cropped_img, image.get_name())
        return p

    def get_random_crop_window(self, coverage=0.33, window=(0, 1, 0, 1)):
        """
        :param coverage:
        determines area coverage ratio
        :param window:
        if the window is already set then make a subwindow from it
        :return:
        Values describing render region that range from min (0) to max (1)
        in order xmin, xmax, ymin,ymax. (0,0) is top left
        """

        alfa = math.sqrt(coverage)
        dx = alfa * (window[1] - window[0])
        dy = alfa * (window[3] - window[2])
        start = [uniform(window[0], window[1] - dx),
                 uniform(window[2], window[3] - dy)]

        crop_window = (start[0], start[0] + dx, start[1], start[1] + dy)
        return crop_window

    def is_valid_against_reference(self,
                                   image_stat, reference_image_stat,
                                   acceptance_ratio=0.75, maybe_ratio=0.65):

        if not isinstance(image_stat, ImgStatistics) \
                and not isinstance(reference_image_stat, ImgStatistics):
            raise TypeError('imgStatistics be instance of ImgStatistics')

        if image_stat.ssim > acceptance_ratio * reference_image_stat.ssim:
            return SubtaskVerificationState.VERIFIED

        if image_stat.ssim > maybe_ratio * reference_image_stat.ssim:
            return SubtaskVerificationState.UNKNOWN

        return SubtaskVerificationState.WRONG_ANSWER
