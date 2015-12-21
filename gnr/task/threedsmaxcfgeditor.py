import re


def regenerate_file(cfg_file_src, thread_num):
    out = ""

    for l in cfg_file_src.splitlines():
        line = re.sub(r'(RenderThreadCount=)(\d+)', r'\g<1>{}'.format(thread_num), l)
        out += line + "\n"

    return out

