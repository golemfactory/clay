from __future__ import division
import logging
import math

from apps.rendering.resources.imgrepr import (EXRImgRepr, ImgRepr, load_img, PILImgRepr)
from apps.core.task.verificator import SubtaskVerificationState as VerificationState

from ssim import compute_ssim

logger = logging.getLogger("apps.rendering")



class ImgStatistics:
    def __init__(self, base_img, img):
        if not isinstance(base_img, ImgRepr) or not isinstance(img, ImgRepr):
            raise TypeError("base_img and img must be ImgRepr")

        if base_img.get_size() != img.get_size():
             raise ValueError('base_img and img are of different sizes.')

        self.img = img
        self.ssim = compute_ssim(base_img.to_pil(), self.img.to_pil())
        self.mse, self.norm_mse = self._calculate_normalized_mse(base_img, self.img)
        self.psnr = self._calculate_psnr(self.mse)

    @property
    def name(self):
        name = None
        if isinstance(self.img, PILImgRepr):
            name = self.img.get_name()

        return name

    def _calculate_normalized_mse(self, img1, img2):
        mse = 0
        (res_x, res_y) = img1.get_size()

        for i in range(0, res_x):
            for j in range(0, res_y):
                [r1, g1, b1] = img1.get_pixel((i,j))
                [r2, g2, b2] = img2.get_pixel((i,j))
                mse += (r1 - r2) * (r1 - r2) + \
                       (g1 - g2) * (g1 - g2) + \
                       (b1 - b2) * (b1 - b2)

        mse /= res_x * res_y * 3

        max_possible_mse = res_x * res_y * 3 * 255 * 255  # max value of pixel is 255
        norm_mse = mse / max_possible_mse

        return  mse, norm_mse

    def _calculate_psnr(self, mse, max_=255):
        if mse <= 0 or max_ <= 0:
            raise ValueError("MSE & MAX_ must be higher than 0")
        return 20 * math.log10(max_) - 10 * math.log10(mse)

    def get_stats(self):
        return self.ssim, self.mse, self.norm_mse, self.psnr




class ImgVerificator:
    def __init__(self):
        pass

    def crop_img_relative(self, img, crop_window):
        """
        :param img: input PILImgRepr()
        :param crop_window: Values describing render region that range from min (0) to max (1) in order xmin, xmax, ymin,ymax. (0,0) is top left
        :return: a rectangular region from this image - left, upper, right, and lower pixel ordinate.
        """

        (res_x, res_y) = img.get_size()
        left  = int(res_x * crop_window[0])
        right = int(res_x * crop_window[1])
        lower = int(res_y * crop_window[2])
        upper = int(res_y * crop_window[3])

        cropped_img = img.to_pil().crop((left, lower, right, upper))  # in PIL's world (0,0) is bottom left ;p
        p = PILImgRepr()
        p.load_from_pil_object(cropped_img, img.get_name())
        return p



    def get_random_crop_window(self, coverage = 0.1, window=(0,1,0,1)):
        """
        :param coverage: determines coverage ratio
        :param window: if the window is already set then make a subwindow from it
        :return: Values describing render region that range from min (0) to max (1) in order xmin, xmax, ymin,ymax. (0,0) is top left
        """

        from random import uniform
        start = [ uniform(window[0], window[1]*(1-coverage)),
                  uniform(window[2], window[3]*(1-coverage))]

        end=[start[0]+coverage*window[1],start[1]+coverage*window[3]]
        crop_window = (start[0], end[1], start[1], end[1])

        return crop_window


    def is_valid_against_reference(self, imgStat, reference_imgStat, acceptance_ratio=0.75, maybe_ratio=0.6):
        if not isinstance(imgStat, ImgStatistics) and not isinstance (reference_imgStat, ImgStatistics):
            raise TypeError("imgStatistics be instance of ImgStatistics")


        if imgStat.ssim > acceptance_ratio*reference_imgStat.ssim and imgStat.psnr > acceptance_ratio*reference_imgStat.psnr:
            return VerificationState.VERIFIED

        if imgStat.ssim > maybe_ratio * reference_imgStat.ssim and imgStat.psnr > acceptance_ratio*reference_imgStat.psnr:
            return VerificationState.UNKNOWN

        return VerificationState.WRONG_ANSWER


    def find_outliers(self, imgStats):
        """

        :param imgStats: list of imgStats
        :return:
        """
        pass


class LuxReferenceImgGenerator:
    """
    This class will generate an luxrender Scene_file_format.lxs to be rendered locally by the requstor.
    The requestor will use image rendered by himself to validate results from providers.
    """
    def __init__(self):
        pass




    def generate_cropped_scene_file(self, original_scene_file, cropping_window):
        """
        This function adds a cropwindow to the Scene_file_format.lxs
        :return: cropped_scene_file.lxs
        """

        # some regex here...
        pass

