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
            logger.error("Wrong box size for advanced verification "
                         "{}".format(box_size))
            return

        if box_size != img.get_size():
            img = crop_to_imgrepr(img, start_box, box_size)
        if box_size != cmp_img.get_size():
            cmp_img = crop_to_imgrepr(cmp_img, cmp_start_box, box_size)

        if isinstance(img, PILImgRepr) and isinstance(cmp_img, PILImgRepr):
            return compare_imgs(img, cmp_img)
        else:
            return compare_imgs(img, cmp_img, max_col=1)
    except Exception:
        logger.exception("Cannot verify images {} and {}".format(file_,
                                                                 compare_file))
        return False


def crop_to_imgrepr(img_repr, start_box, box_size):
    cropped_img = img_repr.crop(start_box, box_size)
    img_repr = PILImgRepr()
    img_repr.img = cropped_img
    return img_repr
