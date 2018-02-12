import logging

from PIL import Image

logger = logging.getLogger("apps.rendering")


def save_image_or_log_error(image: Image, fp, image_format):
    try:
        image.save(fp, image_format)
    except KeyError as e:
        logger.exception("Failed to save image file: unsupported image "
                         "format '%s'", image_format)
    except IOError as e:
        logger.exception("Failed to save image file.")
