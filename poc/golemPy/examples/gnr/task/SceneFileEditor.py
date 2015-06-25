import re

def regeneratePbrtFile(sceneFileSrc, xres, yres, pixelFilter, sampler, samplesPerPixel):
    out = ""

    pixelSamplesSamplers = ['bestcandidate', 'lowdiscrepancy', 'halton', 'random']
    minMaxSamplesSamplers = ['adaptive']
    jitterSamplers = ['stratified']

    for l in sceneFileSrc.splitlines():
        line = re.sub(r'("integer\s+xresolution"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format(xres), l)
        line = re.sub(r'("integer\s+yresolution"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format(yres), line)
        if sampler in pixelSamplesSamplers:
            line = re.sub(r'(Sampler\s+)([\s*\d*\w*\"*\[*\]*]*)', r'\1"{}" "integer pixelsamples" [{}]'.format(sampler, samplesPerPixel), line)
        if sampler in minMaxSamplesSamplers:
            line = re.sub(r'(Sampler\s+)([\s*\d*\w*\"*\[*\]*]*)', r'\1"{}" "integer minsamples" [{}] "integer maxsamples" [{}]'.format(sampler, samplesPerPixel, samplesPerPixel), line)
        if sampler in jitterSamplers:
            line = re.sub(r'(Sampler\s+)([\s*\d*\w*\"*\[*\]*]*)', r'\1"{}" "integer xsamples" [{}] "integer ysamples" [{}]'.format(sampler, samplesPerPixel, samplesPerPixel), line)
        line = re.sub(r'(PixelFilter\s+)("\w*")', r'\1"{}"'.format(pixelFilter), line)
        out += line + "\n"

    return out

def regenerateBlenderCropFile(cropFileSrc, xres, yres, min_x, max_x, min_y, max_y):
    out = ""

    for l in cropFileSrc.splitlines():
        line = re.sub(r'(resolution_x\s*=)(\s*\d*\s*)', r'\1 {}'.format(xres), l)
        line = re.sub(r'(resolution_y\s*=)(\s*\d*\s*)', r'\1 {}'.format(yres), line)
        line = re.sub(r'(border_max_x\s*=)(\s*\d*.\d*\s*)', r'\1 {}'.format(max_x), line)
        line = re.sub(r'(border_min_x\s*=)(\s*\d*.\d*\s*)', r'\1 {}'.format(min_x), line)
        line = re.sub(r'(border_min_y\s*=)(\s*\d*.\d*\s*)', r'\1 {}'.format(min_y), line)
        line = re.sub(r'(border_max_y\s*=)(\s*\d*.\d*\s*)', r'\1 {}'.format(max_y), line)
        print line
        out += line + "\n"

    return out

def regenerateLuxFile(sceneFileSrc, xres, yres, halttime, haltspp, writeinterval, crop, outputFormat):
    out = ""
    if "halttime" in sceneFileSrc:
        addHaltTime = False
    else:
        addHaltTime = True

    if "haltspp" in sceneFileSrc:
        addHaltspp = False
    else:
        addHaltspp = True

    if "cropwindow" in sceneFileSrc:
        addCropWindow = False
    else:
        addCropWindow = True

    exr = "false"
    png = "false"
    tga = "false"
    if outputFormat == "EXR":
        exr = "true"
    elif outputFormat == "PNG":
        png = "true"
    elif outputFormat == "TGA":
        tga = "true"

    nextLineAddHalt = False
    nextLineAddCrop = False
    nextLineAddHaltspp = False
    for l in sceneFileSrc.splitlines():
        if nextLineAddHalt:
            nextLineAddHalt = False
            out += '\t"integer halttime" [{}]\n'.format(halttime)
        if nextLineAddHaltspp:
            nextLineAddHaltspp = False
            out += '\t"integer haltspp" [{}]\n'.format(haltspp)
        if nextLineAddCrop:
            nextLineAddCrop = False
            out += '\t"float cropwindow" [{} {} {} {}]\n'.format(crop[0], crop[1], crop[2], crop[3])
        line = re.sub(r'("integer\s+xresolution"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format(xres), l)
        line = re.sub(r'("integer\s+yresolution"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format(yres), line)
        line = re.sub(r'("integer\s+halttime"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format(halttime), line)
        line = re.sub(r'("integer\s+haltspp"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format(haltspp), line)
        line = re.sub(r'("float\s+cropwindow"\s*)(\[\s*[0-9,\.,\s*]*\s*\])', r'\1[{} {} {} {}]'.format(crop[0], crop[1], crop[2], crop[3]), line)
        line = re.sub(r'("integer\s+writeinterval"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format(writeinterval), line)
        line = re.sub(r'("bool\s+write_exr"\s*)(\[\s*"[A-Z,a-z]*"\s*\])', r'\1["{}"]'.format(exr), line)
        line = re.sub(r'("bool\s+write_png"\s*)(\[\s*"[A-Z,a-z]*"\s*\])', r'\1["{}"]'.format(png), line)
        line = re.sub(r'("bool\s+write_tga"\s*)(\[\s*"[A-Z,a-z]*"\s*\])', r'\1["{}"]'.format(tga), line)
        line = re.sub(r'("bool\s+write_resume_flm"\s*)(\[\s*"[A-z,a-z]*"\s*\])', r'\1["{}"]'.format("true"), line)
        out += line + "\n"
        if addHaltTime and 'Film' in line:
            nextLineAddHalt = True
        if addCropWindow and 'Film' in line:
            nextLineAddCrop = True
        if addHaltspp and 'Film' in line:
            nextLineAddHaltspp = True

    return out


if __name__ == "__main__":

    print regeneratePbrtFile(open("d:/test_run/resources/scene.pbrt").read(), 3,2,"michell", "dupa22", 60)
