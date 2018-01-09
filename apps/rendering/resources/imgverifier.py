from __future__ import division
import logging
import math

from apps.rendering.resources.imgrepr import (ImgRepr, PILImgRepr)

from golem.verification.verifier import SubtaskVerificationState

from ssim import compute_ssim

logger = logging.getLogger("apps.rendering")


class ImgStatistics(object):
    def __init__(self, base_img: ImgRepr, img: ImgRepr):
        if not isinstance(base_img, ImgRepr) or not isinstance(img, ImgRepr):
            raise TypeError("base_img and img must be ImgRepr")

        if base_img.get_size() != img.get_size():
            raise ValueError('base_img and img are of different sizes.')

        self.img = img
        self.ssim = compute_ssim(base_img.to_pil(), self.img.to_pil())
        self.mse, self.norm_mse = \
            self._calculate_color_normalized_mse(base_img, self.img)
        self.mse_bw, norm_mse_bw = \
            self._calculate_greyscale_normalized_mse(base_img, self.img)
        self.psnr = self._calculate_psnr(self.mse)

    @property
    def name(self) -> str:
        name = None
        if isinstance(self.img, PILImgRepr):
            name = self.img.get_name()

        return name

    def _calculate_greyscale_normalized_mse(self, img1: ImgRepr, img2: ImgRepr):
        (res_x, res_y) = img1.get_size()

        img1_bw = img1.to_pil().convert('L')  # makes it greyscale
        img2_bw = img2.to_pil().convert('L')  # makes it greyscale

        import numpy
        npimg1 = numpy.array(img1_bw)
        npimg2 = numpy.array(img2_bw)

        npimg1 = npimg1.astype(numpy.float32, copy=False)
        npimg2 = npimg2.astype(numpy.float32, copy=False)

        mse_bw = 0
        for i in range(len(npimg1)):
            for j in range(len(npimg1[0])):
                mse_bw += (npimg1[i][j] - npimg2[i][j]) \
                          * (npimg1[i][j] - npimg2[i][j])

        mse_bw /= res_x * res_y

        # max value of pixel is 255
        max_possible_mse = res_x * res_y * 255
        norm_mse = mse_bw / max_possible_mse

        return mse_bw, norm_mse

    def _calculate_color_normalized_mse(self, img1, img2):
        mse = 0
        (res_x, res_y) = img1.get_size()

        for i in range(0, res_x):
            for j in range(0, res_y):
                [r1, g1, b1] = img1.get_pixel((i, j))
                [r2, g2, b2] = img2.get_pixel((i, j))
                mse += (r1 - r2) * (r1 - r2) + \
                       (g1 - g2) * (g1 - g2) + \
                       (b1 - b2) * (b1 - b2)

        mse /= res_x * res_y * 3

        # max value of pixel is 255
        max_possible_mse = res_x * res_y * 3 * 255
        norm_mse = mse / max_possible_mse

        return mse, norm_mse

    def _calculate_psnr(self, mse, max_=255):
        if mse <= 0 or max_ <= 0:
            raise ValueError("MSE & MAX_ must be higher than 0")
        return 20 * math.log10(max_) - 10 * math.log10(mse)

    def get_stats(self):
        return self.ssim, self.mse, self.norm_mse, self.mse_bw, self.psnr


class ImgVerifier(object):
    def __init__(self):
        pass

    def crop_img_relative(self, img, crop_window):
        """
        :param img: input PILImgRepr()
        :param crop_window:
        Values describing render region that range from min (0) to max (1)
        in order xmin, xmax, ymin,ymax. (0,0) is top left
        :return:
        a rectangular region from this image:
        left, upper, right, and lower pixel ordinate.
        """

        (res_x, res_y) = img.get_size()

        left = int(math.ceil(res_x * crop_window[0]))
        right = int(math.ceil(res_x * crop_window[1]))
        lower = int(math.ceil(res_y * crop_window[2]))
        upper = int(math.ceil(res_y * crop_window[3]))

        # in PIL's world (0,0) is bottom left ;p
        cropped_img = img.to_pil().crop((left, lower, right, upper))
        p = PILImgRepr()
        p.load_from_pil_object(cropped_img, img.get_name())
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
        from random import uniform
        start = [uniform(window[0], window[1] - dx),
                 uniform(window[2], window[3] - dy)]

        crop_window = (start[0], start[0] + dx, start[1], start[1] + dy)
        return crop_window

    def is_valid_against_reference(self,
                                   imgStat, reference_imgStat,
                                   acceptance_ratio=0.75, maybe_ratio=0.65):

        if not isinstance(imgStat, ImgStatistics) \
                and not isinstance(reference_imgStat, ImgStatistics):
            raise TypeError("imgStatistics be instance of ImgStatistics")

        if imgStat.ssim > acceptance_ratio * reference_imgStat.ssim:
            return SubtaskVerificationState.VERIFIED

        if imgStat.ssim > maybe_ratio * reference_imgStat.ssim:
            return SubtaskVerificationState.UNKNOWN

        return SubtaskVerificationState.WRONG_ANSWER
