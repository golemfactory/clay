import re


def regenerate_blender_crop_file(crop_file_src, xres, yres, min_x, max_x, min_y, max_y, compositing):
    out = ""

    for l in crop_file_src.splitlines():
        line = re.sub(r'(resolution_x\s*=)(\s*\d*\s*)', r'\1 {}'.format(xres), l)
        line = re.sub(r'(resolution_y\s*=)(\s*\d*\s*)', r'\1 {}'.format(yres), line)
        line = re.sub(r'(border_max_x\s*=)(\s*\d*.\d*\s*)', r'\1 {}'.format(max_x), line)
        line = re.sub(r'(border_min_x\s*=)(\s*\d*.\d*\s*)', r'\1 {}'.format(min_x), line)
        line = re.sub(r'(border_min_y\s*=)(\s*\d*.\d*\s*)', r'\1 {}'.format(min_y), line)
        line = re.sub(r'(border_max_y\s*=)(\s*\d*.\d*\s*)', r'\1 {}'.format(max_y), line)
        line = re.sub(r'(use_compositing\s*=)(\s*[A-Z,a-z]*\s*)', r'\1 {}'.format(compositing), line)
        out += line + "\n"
    return out
