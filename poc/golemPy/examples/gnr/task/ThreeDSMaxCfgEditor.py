import re

def regenerateFile( cfgFileSrc, threadNum ):
    out = ""

    for l in cfgFileSrc.splitlines():
        line = re.sub( r'(RenderThreadCount=)(\d+)', r'\g<1>{}'.format(threadNum ), l )
        out += line + "\n"

    return out

