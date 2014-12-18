import re

def regenerateFile( cfgFileSrc, threadNum ):
    out = ""

    for l in cfgFileSrc.splitlines():
        line = re.sub( r'(RenderThreadCount=)(\d+)', r'\g<1>{}'.format(threadNum ), l )
        out += line + "\n"

    return out



if __name__ == "__main__":

    print regenerateFile( open( "d:/test_run/resources/scene.pbrt" ).read(), 3,2,"michell", "dupa22", 60 )
