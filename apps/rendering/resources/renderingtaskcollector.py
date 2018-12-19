import logging
import math
from typing import Optional

from PIL import Image, ImageChops

from apps.rendering.resources.imgrepr import OpenCVImgRepr

logger = logging.getLogger("apps.rendering")


class RenderingTaskCollector(object):
    def __init__(self, width=None, height=None):

        self.accepted_img_files = []
        self.width = width
        self.height = height
        self.channels = 1
        self.dtype = None

    def add_img_file(self, img_file):
        """
        Add file path to the image with subtask result
        :param str img_file: path to the file
        """
        self.accepted_img_files.append(img_file)

    def finalize(self) -> Optional[OpenCVImgRepr]:
        """
        Connect all collected files and return final image
        :return OpenCV Image Representation or None
        """
        if len(self.accepted_img_files) == 0:
            return None

        return self.finalize_img()

    def finalize_img(self):
        res_x, res_y = 0, 0

        for name in self.accepted_img_files:
            image = OpenCVImgRepr()
            image.load_from_file(name)
            img_y, res_x = image.img.shape[:2]
            res_y += img_y
            self.dtype = image.img.dtype
            if len(image.img.shape) == 3:
                self.channels = image.img.shape[2]

        self.width = res_x
        self.height = res_y

        final_img = OpenCVImgRepr()
        final_img.empty(self.width, self.height,
                        self.channels,
                        self.dtype)
        offset = 0
        for img_path in self.accepted_img_files:
            image = OpenCVImgRepr()
            image.load_from_file(img_path)
            final_img.paste_image(image.img, x=0, y=offset)
            offset += image.img.shape[0]
        return final_img

    def _paste_image(self, final_img, new_part, num):
        with Image.new("RGB", (self.width, self.height)) as img_offset:
            offset = int(math.floor(num * float(self.height)
                                    / float(len(self.accepted_img_files))))
            img_offset.paste(new_part, (0, offset))
            result = ImageChops.add(final_img, img_offset)
        return result
