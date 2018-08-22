import os
import re
from bisect import insort

from golem.core.common import to_unicode


def make_log_analyses(log_content, return_data):
    _get_warnings(log_content, return_data)
    rendering_time = find_rendering_time(log_content)
    if rendering_time:
        return_data["rendering_time"] = to_unicode(rendering_time)
    output_path = find_filepath(log_content)
    if output_path:
        return_data["output_path"] = to_unicode(output_path)
    frames = find_frames(log_content)
    if frames:
        return_data["frames"] = frames
    resolution = find_resolution(log_content)
    if resolution:
        return_data["resolution"] = resolution
    file_format = find_file_format(log_content)
    if file_format:
        return_data["file_format"] = to_unicode(file_format)
    engine_type = find_engine_type(log_content)
    if engine_type:
        return_data['engine_type'] = to_unicode(engine_type)
        if engine_type == "CYCLES":
            samples_pp = find_samples_for_scenes(log_content)
            if samples_pp:
                return_data['samples'] = samples_pp


def find_samples_for_scenes(log_content):
    samples = re.search("^Info: Samples: (.*)", log_content,
                        re.MULTILINE)
    if samples:
        return samples.group(1)


def _get_warnings(log_content, return_data):
    warnings = {}
    missing_files = find_missing_files(log_content)
    if missing_files:
        warnings['missing_files'] = missing_files

    wrong_engine = find_wrong_renderer_warning(log_content)
    if wrong_engine:
        warnings['wrong_engine'] = wrong_engine

    if warnings:
        if return_data.get("warnings"):
            return_warnings = return_data.get("warnings")
            if return_warnings.get("missing_files"):
                return_data["warnings"]["missing_files"].extend(
                    warnings['missing_files'])
        else:
            return_data["warnings"] = warnings


def find_wrong_renderer_warning(log_content):
    engine_error = re.search("^Error: engine(.*)", log_content,
                             re.IGNORECASE | re.MULTILINE)
    if engine_error:
        return engine_error.group(1)
    return ""


def find_missing_files(log_content):
    warnings = list()
    for l in log_content.splitlines():
        missing_file = re.search("^Warning: Path '(.*)' not found", l,
                                 re.IGNORECASE)
        if missing_file:
            # extract filename from warning message
            missing_path = missing_file.group(1)
            fileInfo = (
                ('baseName', os.path.basename(missing_path)),
                ('dirName', os.path.dirname(missing_path))
            )
            insort(warnings, fileInfo)

    if warnings:
        return list(map(dict, set(warnings)))
    return warnings


def _format_missing_files_warning(missing_files):
    missing_files = ["    {}\n".format(missing_file)
                     for missing_file in missing_files]
    ret = "Additional data is missing:\n" + "".join(missing_files)
    ret += "\nTry to add missing files to resources before " \
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
        return list(range(start_frame, end_frame + 1, frame_step))


def find_file_format(log_content):
    file_format = re.search("^Info: File format: (\.\w+)", log_content,
                            re.MULTILINE | re.IGNORECASE)
    if file_format:
        return file_format.group(1)


def find_engine_type(log_content):
    file_format = re.search("^Info: Engine: (.*)", log_content,
                            re.MULTILINE | re.IGNORECASE)
    if file_format:
        return file_format.group(1)


def find_filepath(log_content):
    filepath = re.search("^Info: Filepath: (.*)", log_content,
                         re.MULTILINE | re.IGNORECASE)

    if filepath:
        return filepath.group(1)
