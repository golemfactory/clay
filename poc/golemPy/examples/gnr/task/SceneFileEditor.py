import re

def renegerateFile( sceneFileSrc, xres, yres, pixelFilter, sampler, samplesPerPixel ):
    out = ""

    for l in sceneFileSrc.splitlines():
        line = re.sub( r'("integer\s+xresolution"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format( xres ), l )
        line = re.sub( r'("integer\s+yresolution"\s*)(\[\s*\d*\s*\])', r'\1[{}]'.format( yres ), line )
        line = re.sub( r'(Sampler\s+)("\w*")(\s+"integer\s+pixelsamples"\s+)(\[\s*\d*\s*\])', r'\1"{}"\3[{}]'.format( sampler, samplesPerPixel ), line )
        line = re.sub( r'(PixelFilter\s+)("\w*")', r'\1"{}"'.format( pixelFilter ), line )
        out += line + "\n"

    return out



if __name__ == "__main__":

    print renegerateFile( open( "d:/test_run/resources/scene.pbrt" ).read(), 3,2,"michell", "dupa22", 60 )
