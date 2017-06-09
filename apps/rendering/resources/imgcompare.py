from __future__ import division
import logging
import math

from apps.rendering.resources.imgrepr import (EXRImgRepr, ImgRepr, load_img,
                                              PILImgRepr)
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


def get_random_starting_corner_of_the_box(img, box):
    """
    
    :param img: 
    :param box: describes the lengths of the sides of the box 
    :return: describes the the (x,y) coordinates of the SE corner
    """
    (res_x, res_y) = img.get_size()

    if res_x < box[0] or res_y < box[1]:
        raise ValueError('box cannot be larger then the image')

    from random import randint
    start = [randint(0, res_x - box[0]), randint(0, res_y - box[1])]

    return start


def calculate_sub_img_mse(base_img, other_images, start, box):

    mse_against_base_img = list()
    for img in other_images:
        mse = calculate_mse(img, base_img, start1=start, start2=start, box=box)
        mse_against_base_img.append(mse)

    return mse_against_base_img


def calculate_mse_psnr_ssim_metrics(base_img, other_images, start, box):

    mse_against_base_img = calculate_sub_img_mse(base_img, other_images, start, box)

    psnr_against_base_img = list()
    for mse in mse_against_base_img:
        psnr_against_base_img.append(calculate_psnr(mse))

    from ssim import compute_ssim
    ssim_against_base_img = list()

    # the PIL crop method starts from the NE corner.
    # in the PILs world the y-axis points downward.
    # However the start input parameter is defined as the SE corner
    # thus we have to make some CSYS alignment ;P
    pNWx = start[0]
    pNWy = start[1]
    pSEx = start[0] + box[0]
    pSEy = start[1] + box[1]

    cropped_base_img = base_img.to_pil().crop((pNWx, pNWy, pSEx, pSEy))

    for img in other_images:
        cropped_img = img.to_pil().crop((pNWx,pNWy,pSEx, pSEy))

        ssim_against_base_img.append(compute_ssim(cropped_base_img, cropped_img))

        #pil_base_img = base_img.to_pil()
        #pil_img = img.to_pil()
        #ssim_against_base_img.append(compute_ssim(base_img.to_pil(), img.to_pil()))

    return mse_against_base_img, psnr_against_base_img, ssim_against_base_img

def calculate_mse(img1, img2, start1=(0, 0), start2=(0, 0), box=None):
    """
    :param img1: 
    :param img2: 
    :param start1: 
    :param start2: 
    :param box: describes side lengths of the box
    :return: 
    """
    mse = 0
    if not isinstance(img1, ImgRepr) or not isinstance(img2, ImgRepr):
        raise TypeError("img1 and img2 must be ImgRepr")

    if box is not None:
        (res_x, res_y) = box
    else:
        if img1.get_size() == img2.get_size():
            (res_x, res_y) = img1.get_size()
        else:
             raise ValueError('img1 and img2 are of different sizes and there is no cropping box provided.')

    for i in range(0, res_x):
        for j in range(0, res_y):
            [r1, g1, b1] = img1.get_pixel((start1[0] + i, start1[1] + j))
            [r2, g2, b2] = img2.get_pixel((start2[0] + i, start2[1] + j))
            mse += (r1 - r2) * (r1 - r2) + \
                   (g1 - g2) * (g1 - g2) + \
                   (b1 - b2) * (b1 - b2)

    if res_x <= 0 or res_y <= 0:
        raise ValueError("Image or box resolution must be greater than 0")

    mse /= res_x * res_y * 3
    return mse





def compare_imgs(img1, img2, max_col=255, start1=(0, 0),
                 start2=(0, 0), box=None):
    mse = calculate_mse(img1, img2, start1, start2, box)
    logger.debug("MSE = {}".format(mse))
    if mse == 0:
        return True
    psnr = calculate_psnr(mse, max_col)
    logger.debug("PSNR = {}".format(psnr))
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


def advance_verify_img(file_, res_x, res_y, start_box, box_size, compare_file,
                       cmp_start_box):
    try:
        img = load_img(file_)
        cmp_img = load_img(compare_file)
        if img is None or cmp_img is None:
            return False
        if img.get_size() != (res_x, res_y):
            return False

        def _box_too_small(box):
            return box[0] <= 0 or box[1] <= 0

        def _box_too_big(box):
            return box[0] > res_x or box[1] > res_y

        if _box_too_small(box_size) or _box_too_big(box_size):
            logger.error("Wrong box size for advanced verification " \
                         "{}".format(box_size))

        if isinstance(img, PILImgRepr) and isinstance(cmp_img, PILImgRepr): #
            return compare_imgs(img, cmp_img, start1=start_box,
                                start2=cmp_start_box, box=box_size)
        else:
            return compare_imgs(img, cmp_img, max_col=1, start1=start_box,
                                start2=cmp_start_box, box=box_size)
    except Exception:
        logger.exception("Cannot verify images {} and {}".format(file_,
                                                                 compare_file))
        return False
