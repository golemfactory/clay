import re


def make_scene_analysis(scene_file_src, return_data):
    resolution = get_resolution(scene_file_src)
    if resolution:
        return_data["resolution"] = resolution
    filename = get_filename(scene_file_src)
    if filename:
        return_data["filename"] = filename
    fileformat = get_file_format(scene_file_src)
    if fileformat:
        return_data["fileformat"] = fileformat
    haltspp = get_haltspp(scene_file_src)
    if haltspp:
        return_data["haltspp"] = haltspp


def get_resolution(scene_file_src):
    xresolution = re.search('"integer\s+xresolution"\s*\[\s*(\d*)\s*\]',
                            scene_file_src, re.MULTILINE)
    yresolution = re.search('"integer\s+yresolution"\s*\[\s*(\d*)\s*\]',
                            scene_file_src, re.MULTILINE)

    if xresolution and yresolution:
        return int(xresolution.group(1)), int(yresolution.group(1))


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


def get_haltspp(scene_file_src):
    haltspp = re.search('"integer\s+haltspp"\s*\[\s*(\d*)\s*\]', scene_file_src,
                        re.MULTILINE)
    if haltspp:
        return int(haltspp.group(1))
