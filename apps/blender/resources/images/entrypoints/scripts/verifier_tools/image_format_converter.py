import numpy as np
from PIL import Image
import OpenEXR

import Imath


# converting .exr file to .png if user gave .exr file as a rendered scene
def convert_exr_to_png(exr_file, png_file):
    file = OpenEXR.InputFile(exr_file)
    pixel_type = Imath.PixelType(Imath.PixelType.FLOAT)
    data_window = file.header()['dataWindow']
    size = (data_window.max.x - data_window.min.x + 1,
            data_window.max.y - data_window.min.y + 1)
    rgb = [np.frombuffer(file.channel(color, pixel_type), dtype=np.float32) for
           color in 'RGB']
    for i in range(3):
        rgb[i] = np.where(rgb[i] <= 0.0031308,
                          (rgb[i] * 12.92) * 255.0,
                          (1.055 * (rgb[i] ** (1.0 / 2.4)) - 0.055) * 255.0)
    rgb_8 = [Image.frombytes("F", size, color.tostring()).convert("L") for color
             in rgb]
    Image.merge("RGB", rgb_8).save(png_file, "PNG")


# converting .tga file to .png if user gave .tga file as a rendered scene
def convert_tga_to_png(tga_file, png_file):
    image = Image.open(tga_file)
    image.save(png_file)
