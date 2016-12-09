import re


def regenerate_lux_file(scene_file_src, xres, yres, halttime, haltspp, writeinterval, crop, output_format):
    out = ""
    if "halttime" in scene_file_src:
        add_halt_time = False
    else:
        add_halt_time = True

    if "haltspp" in scene_file_src:
        add_haltspp = False
    else:
        add_haltspp = True

    if "cropwindow" in scene_file_src:
        add_crop_window = False
    else:
        add_crop_window = True

    if '"bool write_resume_flm" ["true"]' in scene_file_src:
        add_write_resume_flm = False
    else:
        add_write_resume_flm = True

    exr = "false"
    png = "false"
    tga = "false"
    add_exr, add_png, add_tga = False, False, False
    if output_format.lower() == "exr":
        exr = "true"
        add_exr = '"bool write_exr"' not in scene_file_src
    elif output_format.lower() == "png":
        png = "true"
        add_png = '"bool write_png"' not in scene_file_src
    elif output_format.lower() == "tga":
        tga = "true"
        add_tga = '"bool write_tga"' not in scene_file_src

    next_line_add_halt = False
    next_line_add_crop = False
    next_line_add_haltspp = False
    next_line_add_write_resume_flm = False
    next_line_add_exr = False
    next_line_add_png = False
    next_line_add_tga = False

    for l in scene_file_src.splitlines():
        if next_line_add_halt:
            next_line_add_halt = False
            out += '\t"integer halttime" [{}]\n'.format(halttime)
        if next_line_add_haltspp:
            next_line_add_haltspp = False
            out += '\t"integer haltspp" [{}]\n'.format(haltspp)
        if next_line_add_crop:
            next_line_add_crop = False
            out += '\t"float cropwindow" [{} {} {} {}]\n'.format(crop[0], crop[1], crop[2], crop[3])
        if next_line_add_write_resume_flm:
            next_line_add_write_resume_flm = False
            out += '\t"bool write_resume_flm" ["true"]\n'
        if next_line_add_exr:
            next_line_add_exr = False
            out += '\t"bool write_exr" ["true"]\n'
        if next_line_add_png:
            next_line_add_png = False
            out += '\t"bool write_png" ["true"]\n'
        if next_line_add_tga:
            next_line_add_tga = False
            out += '\t"bool write_tga" ["true"]\n'

        line = re.sub(r'("integer\s+xresolution"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format(xres), l)
        line = re.sub(r'("integer\s+yresolution"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format(yres), line)
        line = re.sub(r'("integer\s+halttime"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format(halttime), line)
        line = re.sub(r'("integer\s+haltspp"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format(haltspp), line)
        line = re.sub(r'("float\s+cropwindow"\s*)(\[\s*[0-9,\.,\s*]*\s*\])',
                      r'\1[{} {} {} {}]'.format(crop[0], crop[1], crop[2], crop[3]), line)
        line = re.sub(r'("integer\s+writeinterval"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format(writeinterval), line)
        line = re.sub(r'("bool\s+write_exr"\s*)(\[\s*"[A-Z,a-z]*"\s*\])', r'\1["{}"]'.format(exr), line)
        line = re.sub(r'("bool\s+write_png"\s*)(\[\s*"[A-Z,a-z]*"\s*\])', r'\1["{}"]'.format(png), line)
        line = re.sub(r'("bool\s+write_tga"\s*)(\[\s*"[A-Z,a-z]*"\s*\])', r'\1["{}"]'.format(tga), line)
        line = re.sub(r'("bool\s+write_resume_flm"\s*)(\[\s*"[A-z,a-z]*"\s*\])', r'\1["{}"]'.format("true"), line)
        out += line + "\n"
        if add_halt_time and 'Film' in line:
            next_line_add_halt = True
        if add_crop_window and 'Film' in line:
            next_line_add_crop = True
        if add_haltspp and 'Film' in line:
            next_line_add_haltspp = True
        if add_write_resume_flm and 'Film' in line:
            next_line_add_write_resume_flm = True
        if add_exr and 'Film' in line:
            next_line_add_exr = True
        if add_png and 'Film' in line:
            next_line_add_png = True
        if add_tga and 'Film' in line:
            next_line_add_tga = True

    return out
