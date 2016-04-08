import re


def regenerate_pbrt_file(scene_file_src, xres, yres, pixel_filter, sampler, samples_per_pixel):
    out = ""

    pixel_samples_samplers = ['bestcandidate', 'lowdiscrepancy', 'halton', 'random']
    min_max_samples_samplers = ['adaptive']
    jitter_samplers = ['stratified']

    for l in scene_file_src.splitlines():
        line = re.sub(r'("integer\s+xresolution"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format(xres), l)
        line = re.sub(r'("integer\s+yresolution"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format(yres), line)
        if sampler in pixel_samples_samplers:
            line = re.sub(r'(Sampler\s+)([\s*\d*\w*\"*\[*\]*]*)',
                          r'\1"{}" "integer pixelsamples" [{}]'.format(sampler, samples_per_pixel), line)
        if sampler in min_max_samples_samplers:
            line = re.sub(r'(Sampler\s+)([\s*\d*\w*\"*\[*\]*]*)',
                          r'\1"{}" "integer minsamples" [{}] "integer maxsamples" [{}]'.format(sampler,
                                                                                               samples_per_pixel,
                                                                                               samples_per_pixel), line)
        if sampler in jitter_samplers:
            line = re.sub(r'(Sampler\s+)([\s*\d*\w*\"*\[*\]*]*)',
                          r'\1"{}" "integer xsamples" [{}] "integer ysamples" [{}]'.format(sampler, samples_per_pixel,
                                                                                           samples_per_pixel), line)
        line = re.sub(r'(PixelFilter\s+)("\w*")', r'\1"{}"'.format(pixel_filter), line)
        out += line + "\n"

    return out


def regenerate_blender_crop_file(crop_file_src, xres, yres, min_x, max_x, min_y, max_y):
    out = ""

    for l in crop_file_src.splitlines():
        line = re.sub(r'(resolution_x\s*=)(\s*\d*\s*)', r'\1 {}'.format(xres), l)
        line = re.sub(r'(resolution_y\s*=)(\s*\d*\s*)', r'\1 {}'.format(yres), line)
        line = re.sub(r'(border_max_x\s*=)(\s*\d*.\d*\s*)', r'\1 {}'.format(max_x), line)
        line = re.sub(r'(border_min_x\s*=)(\s*\d*.\d*\s*)', r'\1 {}'.format(min_x), line)
        line = re.sub(r'(border_min_y\s*=)(\s*\d*.\d*\s*)', r'\1 {}'.format(min_y), line)
        line = re.sub(r'(border_max_y\s*=)(\s*\d*.\d*\s*)', r'\1 {}'.format(max_y), line)
        out += line + "\n"

    return out


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
    if output_format == "exr":
        exr = "true"
    elif output_format == "png":
        png = "true"
    elif output_format == "tga":
        tga = "true"

    next_line_add_halt = False
    next_line_add_crop = False
    next_line_add_haltspp = False
    next_line_add_write_resume_flm = False
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

    return out


if __name__ == "__main__":
    print regenerate_pbrt_file(open("d:/test_run/resources/scene.pbrt").read(), 3, 2, "michell", "dupa22", 60)
