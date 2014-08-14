import re

def regenerateFile( sceneFileSrc, xres, yres, pixelFilter, sampler, samplesPerPixel ):
    out = ""

    pixelSamplesSamplers = ['bestcandidate', 'lowdiscrepancy', 'halton', 'random']
    minMaxSamplesSamplers = ['adaptive']
    jitterSamplers = ['stratified']

    for l in sceneFileSrc.splitlines():
        line = re.sub( r'("integer\s+xresolution"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format( xres ), l )
        line = re.sub( r'("integer\s+yresolution"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format( yres ), line )
        if sampler in pixelSamplesSamplers:
            line = re.sub( r'(Sampler\s+)([\s*\d*\w*\"*\[*\]*]*)', r'\1"{}" "integer pixelsamples" [{}]'.format( sampler, samplesPerPixel ), line )
        if sampler in minMaxSamplesSamplers:
            line = re.sub( r'(Sampler\s+)([\s*\d*\w*\"*\[*\]*]*)', r'\1"{}" "integer minsamples" [{}] "integer maxsamples" [{}]'.format( sampler, samplesPerPixel, samplesPerPixel ), line )
        if sampler in jitterSamplers:
            line = re.sub( r'(Sampler\s+)([\s*\d*\w*\"*\[*\]*]*)', r'\1"{}" "integer xsamples" [{}] "integer ysamples" [{}]'.format( sampler, samplesPerPixel, samplesPerPixel ), line )
        line = re.sub( r'(PixelFilter\s+)("\w*")', r'\1"{}"'.format( pixelFilter ), line )
        out += line + "\n"

    return out



if __name__ == "__main__":

    print regenerateFile( open( "d:/test_run/resources/scene.pbrt" ).read(), 3,2,"michell", "dupa22", 60 )
