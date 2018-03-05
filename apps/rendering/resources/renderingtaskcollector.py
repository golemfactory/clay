
import logging
import math
import os

from PIL import Image, ImageChops

from apps.rendering.resources.imgrepr import EXRImgRepr, load_img

logger = logging.getLogger("apps.rendering")


class RenderingTaskCollector(object):
    def __init__(self, paste=False, width=None, height=None):

        self.accepted_img_files = []
        self.accepted_alpha_files = []
        self.paste = paste
        self.width = width
        self.height = height

    def add_img_file(self, img_file):
        """
        Add file path to the image with subtask result
        :param str img_file: path to the file
        """
        self.accepted_img_files.append(img_file)

    def add_alpha_file(self, img_file):
        """
        Add file path to the image with alpha channel
        :param str img_file: path to the file
        """
        self.accepted_alpha_files.append(img_file)

    def finalize(self):
        """
        Connect all collected files and return final image
        :return Image.Image:
        """
        if len(self.accepted_img_files) == 0:
            return None

        img_repr = load_img(self.accepted_img_files[0])
        if isinstance(img_repr, EXRImgRepr):
            final_img = self.finalize_exr(img_repr)
            self.finalize_alpha(final_img)
        else:
            final_img = self.finalize_pil()
        return final_img

    def finalize_alpha(self, final_img):
        """
        Load collected alpha files, add them as chops and put to final image as an alpha channel
        :param Image.Image final_img: image hat should have alpha channel added
        :return:
        """
        if len(self.accepted_alpha_files) == 0:
            return

        e = EXRImgRepr()
        e.load_from_file(self.accepted_alpha_files[0])
        final_alpha = e.to_l_image()

        for img in self.accepted_alpha_files[1:]:
            e = EXRImgRepr()
            e.load_from_file(img)
            l_im = e.to_l_image()
            final_alpha = ImageChops.add(final_alpha, l_im)
            l_im.close()

        final_img.putalpha(final_alpha)
        final_alpha.close()

    def finalize_exr(self, exr_repr):

        final_img = exr_repr.to_pil()

        if self.paste:
            if not self.width or not self.height:
                self.width, self.height = final_img.size
                self.height *= len(self.accepted_img_files)
            with Image.new('RGB', (self.width, self.height)) as img:
                final_img = self._paste_image(img, final_img, 0)

        for i, img_path in enumerate(self.accepted_img_files[1:], start=1):
            img = load_img(img_path)
            with img.to_pil() as rgb8_im:
                if not self.paste:
                    final_img = ImageChops.add(final_img, rgb8_im)
                else:
                    final_img = self._paste_image(final_img, rgb8_im, i)

        return final_img
        
    def finalize_pil(self):
        res_x, res_y = 0, 0

        for name in self.accepted_img_files:
            with Image.open(name) as img:
                res_x, img_y = img.size
                res_y += img_y

        self.width = res_x
        self.height = res_y
        with Image.open(self.accepted_img_files[0]) as img:
            bands = img.getbands()
        band = ""
        for b in bands:
            band += b
        final_img = Image.new(band, (res_x, res_y))
        offset = 0
        for img_path in self.accepted_img_files:
            with Image.open(img_path) as img:
                if not self.paste:
                    final_img = ImageChops.add(final_img, img)
                else:
                    final_img.paste(img, (0, offset))
                    _, img_y = img.size
                    offset += img_y
        return final_img

    def _paste_image(self, final_img, new_part, num):
        img_offset = Image.new("RGB", (self.width, self.height))
        offset = int(math.floor(num * float(self.height) / float(len(self.accepted_img_files))))
        img_offset.paste(new_part, (0, offset))
        return ImageChops.add(final_img, img_offset)
