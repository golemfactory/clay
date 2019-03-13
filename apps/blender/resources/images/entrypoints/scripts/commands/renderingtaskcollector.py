import logging
import numpy
import os
from typing import Optional

import cv2


logger = logging.getLogger(__name__)


class OpenCVError(OSError):
    pass


class OpenCVImgRepr:
    def __init__(self):
        self.img = None

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass

    def load_from_file(self, path):
        try:
            self.img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if self.img is None:
                raise RuntimeError('cv2 read image \"{}\" as None'
                                   .format(path))
        except (cv2.error, RuntimeError) as e:
            logger.error('Error reading image: {}'.format(str(e)))
            raise OpenCVError('Cannot read image: {}'
                              .format(str(e)))

    def empty(self, width, height, channels, dtype):
        self.img = numpy.zeros((height, width, channels),
                               dtype)

    def paste_image(self, img, x, y):
        self.img[y:y + img.shape[0], x:img.shape[1]] = img

    def save_with_extension(self, path, extension):
        # in PIL one can specify output name without extension
        # format was given as a second argument
        # in OpenCV extension must be given in a filename
        # some paths are without extension, need to rename it then

        file_path = '{}_{}.{}'.format(path,
                                      "tmp",
                                      extension.lower())
        self.save(file_path)
        os.replace(file_path, f'{path}.{extension}')

    def save(self, path):
        try:
            cv2.imwrite(path, self.img)
        except cv2.error as e:
            logger.error('Error saving image: {}'.format(str(e)))
            raise OpenCVError('Cannot save image {}: {}'.format(path,
                                                                str(e)))


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
