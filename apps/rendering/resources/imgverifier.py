from __future__ import division
import logging
import math

from apps.rendering.resources.imgrepr import PILImgRepr


logger = logging.getLogger("apps.rendering")


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

        crop_window = [start[0], start[0] + dx, start[1], start[1] + dy]
        return crop_window
