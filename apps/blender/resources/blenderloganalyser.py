import os
import re


def find_wrong_renderer_warning(log_content):
    engine_error = re.search("^Error: engine(.*)", log_content,
                             re.IGNORECASE | re.MULTILINE)
    if engine_error:
        return engine_error.group(1)
    return ""


def find_missing_files(log_content):
    warnings = set()
    for l in log_content.splitlines():
        missing_file = re.search("^Warning: Path '(.*)' not found", l,
                                 re.IGNORECASE)
        if missing_file:
            # extract filename from warning message
            warnings.add(os.path.basename(missing_file.group(1)))
    return warnings


def format_missing_files_warning(missing_files):
    missing_files = [u"    {}\n".format(missing_file)
                     for missing_file in missing_files]
    ret = u"Additional data is missing:\n" + "".join(missing_files)
    ret += u"\nTry to add missing files to resources before " \
           "you start rendering."
    return ret


def find_rendering_time(log_content):
    time_ = re.search("(^\s*Time:\s*)(\d+):(\d+\.\d+)", log_content,
                      re.MULTILINE | re.IGNORECASE)
    if time_:
        time_ = int(time_.group(2)) * 60 + float(time_.group(3))
        return time_


def find_output_file(log_content):
    output_file = re.search("^Saved: '(.*)'", log_content,
                            re.MULTILINE | re.IGNORECASE)
    if output_file:
        return output_file.group(1)


def find_resolution(log_content):
    resolution = re.search("^Info: Resolution: (\d+) x (\d+)", log_content,
                           re.MULTILINE | re.IGNORECASE)
    if resolution:
        return int(resolution.group(1)), int(resolution.group(2))


def find_frames(log_content):
    frames = re.search("^Info: Frames: (\d+)-(\d+);(\d+)", log_content,
                       re.MULTILINE | re.IGNORECASE)
    if frames:
        start_frame = int(frames.group(1))
        end_frame = int(frames.group(2))
        frame_step = int(frames.group(3))
        return range(start_frame, end_frame + 1, frame_step)


def find_file_format(log_content):
    file_format = re.search("^Info: File format: (\.\w+)", log_content,
                            re.MULTILINE | re.IGNORECASE)
    if file_format:
        return file_format.group(1)


def find_filepath(log_content):
    filepath = re.search("^Info: Filepath: (.*)", log_content,
                         re.MULTILINE | re.IGNORECASE)

    if filepath:
        return filepath.group(1)
