import os
import re


def find_wrong_renderer_warning(log_content):
    text = "error: engine"
    for l in log_content.splitlines():
        if l.lower().startswith(text):
            return l[len(text):]
    return ""


def find_missing_files(log_content):
    warnings = set()
    for l in log_content.splitlines():
        if l.lower().startswith("warning: path ") and l.lower().endswith(" not found"):
            # extract filename from warning message
            warnings.add(os.path.basename(l[14:-11]))
    return warnings


def format_missing_files_warning(missing_files):
    missing_files = [u"    {}\n".format(missing_file) for missing_file in missing_files]

    ret = u"Additional data is missing:\n" + "".join(missing_files)
    ret += u"\nTry to add missing files to resources before you start rendering."
    return ret


def find_rendering_time(log_content):
    time_ = re.search("(^ Time: )((\d)*):((\d|\.)*)", log_content, re.MULTILINE | re.IGNORECASE)
    time_ = int(time_.group(2)) * 60 + float(time_.group(3))
    return time_