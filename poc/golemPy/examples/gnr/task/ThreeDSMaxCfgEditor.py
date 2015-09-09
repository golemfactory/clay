import re

def regenerateFile(cfg_file_src, threadNum):
    out = ""

    for l in cfg_file_src.splitlines():
        line = re.sub(r'(RenderThreadCount=)(\d+)', r'\g<1>{}'.format(threadNum), l)
        out += line + "\n"

    return out

