import re


def get_resolution(scene_file_src):
    xresolution = re.search('"integer\s+xresolution"\s*\[\s*(\d*)\s*\]',
                            scene_file_src, re.MULTILINE)
    yresolution = re.search('"integer\s+yresolution"\s*\[\s*(\d*)\s*\]',
                            scene_file_src, re.MULTILINE)

    if xresolution:
        xresolution = int(xresolution.group(1))
    if yresolution:
        yresolution = int(yresolution.group(1))
    return xresolution, yresolution


def get_filename(scene_file_src):
    filename = re.search('"string\s+filename"\s*\[\s*"(.*)"\s*\]\s*$',
                         scene_file_src, re.MULTILINE)
    if filename:
        return filename.group(1)


def get_file_format(scene_file_src):
    ext = re.search('"bool\s+write_(\w{3})"\s*\[\s*"true"\s*\]',
                    scene_file_src, re.MULTILINE)

    if ext and ext.group(1) in ["png", "exr", "tga"]:
        return "." + ext.group(1)
