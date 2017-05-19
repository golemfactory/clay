import logging
import math

from apps.rendering.resources.imgrepr import (crop_to_imgrepr, EXRImgRepr,
                                              ImgRepr, load_img, PILImgRepr)

logger = logging.getLogger("apps.rendering")

PSNR_ACCEPTABLE_MIN = 30


def check_size(file_, res_x, res_y):
    img = load_img(file_)
    if img is None:
        return False
    return img.get_size() == (res_x, res_y)


def calculate_psnr(mse, max_=255):
    if mse <= 0 or max_ <= 0:
        raise ValueError("MSE & MAX_ must be higher than 0")
    return 20 * math.log10(max_) - 10 * math.log10(mse)


def calculate_mse(img1, img2):
    mse = 0
    if not isinstance(img1, ImgRepr) or not isinstance(img2, ImgRepr):
        raise TypeError("img1 and img2 must be ImgRepr")

    (res_x, res_y) = img1.get_size()

    for i in range(0, res_x):
        for j in range(0, res_y):
            [r1, g1, b1] = img1.get_pixel((i, j))
            [r2, g2, b2] = img2.get_pixel((i, j))
            mse += (r1 - r2) * (r1 - r2) + \
                   (g1 - g2) * (g1 - g2) + \
                   (b1 - b2) * (b1 - b2)

    if res_x <= 0 or res_y <= 0:
        raise ValueError("Image or box resolution must be greater than 0")
    mse /= res_x * res_y * 3

    return mse


def compare_imgs(img1, img2, max_col=255):
    mse = calculate_mse(img1, img2)
    logger.error("MSE = {}".format(mse))
    if mse == 0:
        return True
    psnr = calculate_psnr(mse, max_col)
    logger.error("PSNR = {}".format(psnr))
    return psnr >= PSNR_ACCEPTABLE_MIN


def compare_pil_imgs(file1, file2):
    try:
        img1 = PILImgRepr()
        img1.load_from_file(file1)
        img2 = PILImgRepr()
        img2.load_from_file(file2)
        return compare_imgs(img1, img2)
    except Exception as err:
        logger.info("Can't compare images {}, {}: {}".format(file1, file2,
                                                             err))
        return False


def compare_exr_imgs(file1, file2):
    try:
        img1 = EXRImgRepr()
        img1.load_from_file(file1)
        img2 = EXRImgRepr()
        img2.load_from_file(file2)
        return compare_imgs(img1, img2, 1)
    except Exception as err:
        logger.info("Can't compare images {}, {}: {}".format(file1, file2,
                                                             err))
        return False
