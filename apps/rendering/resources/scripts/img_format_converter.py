import Imath
import numpy as np
from PIL import Image
import OpenEXR


# converting .exr file to .png if user gave .exr file as a rendered scene
def ConvertEXRToPNG(exrfile, pngfile):
    File = OpenEXR.InputFile(exrfile)
    PixType = Imath.PixelType(Imath.PixelType.FLOAT)
    DW = File.header()['dataWindow']
    Size = (DW.max.x - DW.min.x + 1, DW.max.y - DW.min.y + 1)
    rgb = [np.frombuffer(File.channel(c, PixType), dtype=np.float32) for c in
           'RGB']
    for i in range(3):
        rgb[i] = np.where(rgb[i] <= 0.0031308,
                          (rgb[i] * 12.92) * 255.0,
                          (1.055 * (rgb[i] ** (1.0 / 2.4)) - 0.055) * 255.0)
    rgb8 = [Image.frombytes("F", Size, c.tostring()).convert("L") for c in rgb]
    Image.merge("RGB", rgb8).save(pngfile, "PNG")


# converting .tga file to .png if user gave .tga file as a rendered scene
def ConvertTGAToPNG(tgafile, pngfile):
    img = Image.open(tgafile)
    img.save(pngfile)
