import glob
import logging
import math
import OpenEXR
import Imath
import os
from PIL import Image, ImageChops

from golem.core.common import is_windows

logger = logging.getLogger("gnr.task")


def print_progress(i, total):
    print "\rProgress: {} %       ".format(100.0 * float(i + 1) / total),


def open_exr_as_rgbf_images(exr_file):
    file = OpenEXR.InputFile(exr_file)
    pt = Imath.PixelType(Imath.PixelType.FLOAT)
    dw = file.header()['dataWindow']
    size = (dw.max.x - dw.min.x + 1, dw.max.y - dw.min.y + 1)

    rgbf = [Image.frombytes("F", size, file.channel(c, pt)) for c in "RGB"]

    return rgbf


def convert_rgbf_images_to_rgb8_image(rgbf, lightest=255.0, darkest=0.0):
    scale = 255 / (lightest - darkest)

    def normalize_0_255(val):
        scale = 255.0
        darkest = 0.0
        return (val * scale) + darkest

    rgb8 = [im.point(normalize_0_255).convert("L") for im in rgbf]

    img = Image.merge("RGB", rgb8)

    return img


def convert_rgbf_images_to_l_image(rgbf, lightest=255.0, darkest=0.0):
    scale = 255 / (lightest - darkest)

    def normalize_0_255(val):
        scale = 255.0
        darkest = 0.0
        return (val * scale) + darkest

    rgb8 = [im.point(normalize_0_255).convert("L") for im in rgbf]

    img = Image.merge("RGB", rgb8)
    img = img.convert("L")

    return img


def get_single_rgbf_extrema(rgbf):
    extrema = [im.getextrema() for im in rgbf]
    darkest = min([lo for (lo, hi) in extrema])
    lightest = max([hi for (lo, hi) in extrema])

    return darkest, lightest


def get_list_rgbf_extrema(rgbf_list):
    assert len(rgbf_list) > 0

    darkest, lightest = get_single_rgbf_extrema(rgbf_list[0])

    for i in range(1, len(rgbf_list)):
        d, l = get_single_rgbf_extrema(rgbf_list[i])

        darkest = min(d, darkest)
        lightest = max(l, lightest)

        print_progress(i, len(rgbf_list))

    print ""

    return darkest, lightest


def compose_final_image(open_exr_files):
    rgbfs = []

    print "Reading input files"
    for i, open_exr_im_file in enumerate(open_exr_files):
        rgbf = open_exr_as_rgbf_images(open_exr_im_file)
        rgbfs.append(rgbf)

        print_progress(i, len(open_exr_files))

    print "\nFinding extremas for all chunks"
    darkest, lightest = get_list_rgbf_extrema(rgbfs)

    rgb8_images = []

    print "Converting chunks to rgb8 images"
    for i, rgbf in enumerate(rgbfs):
        rgb8_im = convert_rgbf_images_to_rgb8_image(rgbf, lightest, darkest)
        rgb8_images.append(rgb8_im)
        rgb8_im.close()

        print_progress(i, len(rgbfs))

    final_img = rgb8_images[0]

    print "\nCompositing the final image"
    for i in range(1, len(rgb8_images)):
        final_img = ImageChops.add(final_img, rgb8_images[i])

        print_progress(i, len(rgb8_images))

    return final_img


def get_exr_files(path):
    if is_windows():
        return glob.glob(path + "/*.exr")
    else:
        return glob.glob(path + "/*.exr") + glob.glob(path + "/*.EXR")


def test_it():
    image = 'test/test_chunk_00000.tga'
    watermark = 'test/test_chunk_00001.png'

    wmark = Image.open(watermark)
    img = Image.open(image)

    out = ImageChops.add(img, wmark)

    out.save("result.png", "PNG")
    wmark.close()
    img.close()


def exr_to_pil(exr_file):
    file = OpenEXR.InputFile(exr_file)
    pt = Imath.PixelType(Imath.PixelType.FLOAT)
    dw = file.header()['dataWindow']
    size = (dw.max.x - dw.min.x + 1, dw.max.y - dw.min.y + 1)

    rgbf = [Image.frombytes("F", size, file.channel(c, pt)) for c in "RGB"]

    #   extrema = [im.getextrema() for im in rgbf]
    #   darkest = min([lo for (lo,hi) in extrema])
    #    lightest = max([hi for (lo,hi) in extrema])
    #    scale = 255.0 / (lightest - darkest)

    scale = 255.0

    def normalize_0_255(v):
        return v * scale

    rgb8 = [im.point(normalize_0_255).convert("L") for im in rgbf]
    return Image.merge("RGB", rgb8)


class RenderingTaskCollector:
    def __init__(self, paste=False, width=1, height=1):
        self.darkest = None
        self.lightest = None
        self.alpha_darkest = None
        self.alpha_lightest = None
        self.accepted_img_files = []
        self.accepted_alpha_files = []
        self.paste = paste
        self.width = width
        self.height = height

    def add_img_file(self, img_file):
        if img_file.upper().endswith("EXR"):
            rgbf = open_exr_as_rgbf_images(img_file)
            d, l = get_single_rgbf_extrema(rgbf)

            if self.darkest:
                self.darkest = min(d, self.darkest)
            else:
                self.darkest = d

            if self.lightest:
                self.lightest = max(l, self.lightest)
            else:
                self.lightest = l
        
        self.accepted_img_files.append(img_file)

    def add_alpha_file(self, img_file):
        if img_file.upper().endswith("EXR"):
            rgbf = open_exr_as_rgbf_images(img_file)
            d, l = get_single_rgbf_extrema(rgbf)

            if self.alpha_darkest:
                self.alpha_darkest = min(d, self.alpha_darkest)
            else:
                self.alpha_darkest = d

            if self.alpha_lightest:
                self.alpha_lightest = max(l, self.alpha_lightest)
            else:
                self.alpha_lightest = l

        self.accepted_alpha_files.append(img_file)

    def finalize(self, show_progress=False):
        if len(self.accepted_img_files) == 0:
            return None
        are_exr = self.accepted_img_files[0].upper().endswith("EXR")
        if show_progress:
            print "Adding all accepted chunks to the final image"
        if are_exr:
            final_img = self.finalize_exr(show_progress)
        else:
            final_img = self.finalize_not_exr(show_progress)
                    
        if len(self.accepted_alpha_files) > 0:
            final_alpha = convert_rgbf_images_to_l_image(open_exr_as_rgbf_images(self.accepted_alpha_files[0]),
                                                         self.lightest, self.darkest)

            for i in range(1, len(self.accepted_alpha_files)):
                l_im = convert_rgbf_images_to_l_image(open_exr_as_rgbf_images(self.accepted_alpha_files[i]),
                                                      self.lightest, self.darkest)
                final_alpha = ImageChops.add(final_alpha, l_im)
                l_im.close()

            final_img.putalpha(final_alpha)
            final_alpha.close()

        return final_img

    def finalize_exr(self, show_progress=False):
        if self.lightest == self.darkest:
            self.lightest = self.darkest + 0.1

        final_img = convert_rgbf_images_to_rgb8_image(open_exr_as_rgbf_images(self.accepted_img_files[0]),
                                                    self.lightest, self.darkest)

        if self.paste:
            if not self.width or not self.height:
                self.width, self.height = final_img.size
                self.height *= len(self.accepted_img_files)
            img = Image.new('RGB', (self.width, self.height))
            final_img = self._paste_image(img, final_img, 0)
            img.close()

        for i in range(1, len(self.accepted_img_files)):
            rgb8_im = convert_rgbf_images_to_rgb8_image(open_exr_as_rgbf_images(self.accepted_img_files[i]),
                                                        self.lightest, self.darkest)
            if not self.paste:
                final_img = ImageChops.add(final_img, rgb8_im)
            else:
                final_img = self._paste_image(final_img, rgb8_im, i)
                
            rgb8_im.close()
            
            if show_progress:
                print_progress(i, len(self.accepted_img_files))
        return final_img
        
    def finalize_not_exr(self, show_progress=False):
        _, output_format = os.path.splitext(self.accepted_img_files[0])
        output_format = output_format[1:].upper()
        res_y = 0
        
        for name in self.accepted_img_files:
            img = Image.open(name)
            res_x, img_y = img.size
            res_y += img_y
            img.close()
        
        self.width = res_x
        self.height = res_y
        img = Image.open(self.accepted_img_files[0])
        bands = img.getbands()
        img.close()
        band = ""
        for b in bands:
            band += b
        final_img = Image.new(band, (res_x, res_y))
        #self.accepted_img_files.sort()
        offset = 0
        for i in range(0, len(self.accepted_img_files)):
            if not self.paste:
                final_img = ImageChops.add(final_img, self.accepted_img_files[i])
            else:
                img = Image.open(self.accepted_img_files[i])
                final_img.paste(img, (0, offset))
                _, img_y = img.size
                offset += img_y
                img.close()
            if show_progress:
                print_progress(i, len(self.accepted_img_files))        
        return final_img

    def _paste_image(self, final_img, new_part, num):
        img_offset = Image.new("RGB", (self.width, self.height))
        offset = int(math.floor(num * float(self.height) / float(len(self.accepted_img_files))))
        img_offset.paste(new_part, (0, offset))
        return ImageChops.add(final_img, img_offset)
