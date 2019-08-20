import json
import re
import os
import sys

from ffmpeg_tools import commands, formats, meta

OUTPUT_DIR = "/golem/output"
WORK_DIR = "/golem/work"
RESOURCES_DIR = "/golem/resources"
PARAMS_FILE = "params.json"

TRANSCODED_VIDEO_REGEX = re.compile(r'_(\d+)_TC\.[^.]+')
FFCONCAT_LIST_BASENAME = "merge-input.ffconcat"


class InvalidCommand(Exception):
    pass


def do_extract(input_file,
               output_file,
               selected_streams,
               container=None):

    video_metadata = commands.get_metadata_json(input_file)
    if container is None:
        format_demuxer = meta.get_format(video_metadata)
        container = formats.\
            get_safe_intermediate_format_for_demuxer(format_demuxer)

    commands.extract_streams(
        input_file,
        output_file,
        selected_streams,
        container)

    results = {
        "metadata": video_metadata,
    }
    results_file = os.path.join(OUTPUT_DIR, "extract-results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f)

    return results


def do_split(path_to_stream, parts):
    video_metadata = commands.get_metadata_json(path_to_stream)
    video_length = meta.get_duration(video_metadata)
    format_demuxer = meta.get_format(video_metadata)
    container = formats.get_safe_intermediate_format_for_demuxer(format_demuxer)

    segment_list_path = commands.split_video(
        path_to_stream,
        OUTPUT_DIR,
        video_length / parts,
        container)

    with open(segment_list_path) as segment_list_file:
        segment_filenames = segment_list_file.read().splitlines()

    results = {
        "main_list": segment_list_path,
        "segments": [{"video_segment": s} for s in segment_filenames],
        "metadata": video_metadata,
    }

    results_file = os.path.join(OUTPUT_DIR, "split-results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f)

    return results


def do_extract_and_split(input_file, parts, container=None):
    input_basename = os.path.basename(input_file)
    [input_stem, input_extension] = os.path.splitext(input_basename)

    intermediate_file = os.path.join(
        WORK_DIR,
        f"{input_stem}[video-only]{input_extension}")

    extract_results = do_extract(input_file,
                                 intermediate_file,
                                 ['v'],
                                 container)

    split_results = do_split(intermediate_file, parts)

    results = {
        "main_list": split_results["main_list"],
        "segments": split_results["segments"],
        "metadata": extract_results["metadata"],
    }

    results_file = os.path.join(OUTPUT_DIR, "extract-and-split-results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f)


def do_transcode(track, targs, output):
    commands.transcode_video(track, targs, output)


def select_transcoded_video_paths(output_file_paths, output_extension):
    return [path
            for path in output_file_paths
            if path.endswith(f'_TC{output_extension}')]


def sorted_transcoded_video_paths(transcoded_video_paths):
    path_index = {int(re.findall(TRANSCODED_VIDEO_REGEX, path)[0]): path
                  for path in transcoded_video_paths}
    return [value for key, value in sorted(path_index.items())]


def build_and_store_ffconcat_list(chunks, output_filename, list_basename):
    if len(chunks) <= 0:
        raise commands.InvalidArgument(
            "Need at least one video segment to perform a merge operation")

    if len(set(os.path.dirname(chunk) for chunk in chunks)) >= 2:
        # It would be possible to handle chunks residing in different
        # directories but it's not implemented (and not needed right now).
        raise commands.InvalidArgument(
            "All video chunks to merge must be in the same directory")

    # NOTE: The way the ffmpeg merge command works now, the list file
    # must be in the same directory as the chunks.
    list_filename = os.path.join(os.path.dirname(chunks[0]), list_basename)

    [_output_basename, output_extension] = os.path.splitext(
        os.path.basename(output_filename))

    merge_input_files = sorted_transcoded_video_paths(
        select_transcoded_video_paths(
            chunks,
            output_extension))

    ffconcat_entries = [
        "file '{}'".format(path.replace("'", "\\'"))
        for path in merge_input_files
    ]

    with open(list_filename, 'w') as file:
        file.write('\n'.join(ffconcat_entries))

    return list_filename


def do_merge(chunks, outputfilename, container=None):
    if len(chunks) <= 0:
        raise commands.InvalidArgument(
            "Need at least one video segment to perform a merge operation")

    if len(set(os.path.dirname(chunk) for chunk in chunks)) >= 2:
        # It would be possible to handle chunks residing in different
        # directories but it's not implemented (and not needed right now).
        raise commands.InvalidArgument(
            "All video chunks to merge must be in the same directory")

    ffconcat_list_filename = build_and_store_ffconcat_list(
        chunks,
        outputfilename,
        FFCONCAT_LIST_BASENAME)
    commands.merge_videos(
        ffconcat_list_filename,
        outputfilename,
        container)


def do_replace(input_file,
               replacement_source,
               output_file,
               stream_type,
               container=None,
               strip_unsupported_data_streams=False,
               strip_unsupported_subtitle_streams=False):

    commands.replace_streams(
        input_file,
        replacement_source,
        output_file,
        stream_type,
        container,
        strip_unsupported_data_streams,
        strip_unsupported_subtitle_streams)


def do_merge_and_replace(input_file,
                         chunks,
                         output_file,
                         container=None,
                         strip_unsupported_data_streams=False,
                         strip_unsupported_subtitle_streams=False):

    output_basename = os.path.basename(output_file)
    [output_stem, output_extension] = os.path.splitext(output_basename)

    intermediate_file = os.path.join(
        WORK_DIR,
        f"{output_stem}[video-only]{output_extension}")

    do_merge(chunks, intermediate_file, container)
    do_replace(
        input_file,
        intermediate_file,
        output_file,
        'v',
        container,
        strip_unsupported_data_streams,
        strip_unsupported_subtitle_streams)


def compute_metric(cmd, function):
    video_path = os.path.join(RESOURCES_DIR, cmd["video"])
    reference_path = os.path.join(RESOURCES_DIR, cmd["reference"])
    output = os.path.join(OUTPUT_DIR, cmd["output"])
    log = os.path.join(OUTPUT_DIR, cmd["log"])

    function(video_path, reference_path, output, log)


def get_metadata(cmd):
    video_path = os.path.join(RESOURCES_DIR, cmd["video"])
    output = os.path.join(OUTPUT_DIR, cmd["output"])

    commands.get_metadata(video_path, output)


def compute_metrics(metrics_params):
    if "ssim" in metrics_params:
        compute_metric(metrics_params["ssim"], commands.compute_ssim)

    if "psnr" in metrics_params:
        compute_metric(metrics_params["psnr"], commands.compute_psnr)

    if "metadata" in metrics_params:
        for metadata_request in metrics_params["metadata"]:
            get_metadata(metadata_request)


def run_ffmpeg(params):
    if params['command'] == "extract":
        do_extract(
            params['input_file'],
            params['output_file'],
            params['selected_streams'],
            params.get('container'))
    elif params['command'] == "split":
        do_split(
            params['path_to_stream'],
            params['parts'])
    elif params['command'] == "extract-and-split":
        do_extract_and_split(
            params['input_file'],
            params['parts'],
            params.get('container'))
    elif params['command'] == "transcode":
        do_transcode(
            params['track'],
            params['targs'],
            params['output_stream'])
    elif params['command'] == "merge":
        do_merge(
            params['chunks'],
            params['output_stream'],
            params.get('container'))
    elif params['command'] == "replace":
        do_replace(
            params['input_file'],
            params['replacement_source'],
            params['output_file'],
            params['stream_type'],
            params.get('container'),
            params.get('strip_unsupported_data_streams'),
            params.get('strip_unsupported_subtitle_streams'))
    elif params['command'] == "merge-and-replace":
        do_merge_and_replace(
            params['input_file'],
            params['chunks'],
            params['output_file'],
            params.get('container'),
            params.get('strip_unsupported_data_streams'),
            params.get('strip_unsupported_subtitle_streams'))
    elif params['command'] == "compute-metrics":
        compute_metrics(
            params["metrics_params"])
    else:
        raise InvalidCommand(f"Invalid command: {params['command']}")


def run():
    params = None
    with open(PARAMS_FILE, 'r') as f:
        params = json.load(f)

    try:
        run_ffmpeg(params)
    except commands.CommandFailed as e:
        print(e.command, file=sys.stderr)
        exit(e.error_code)


if __name__ == "__main__":
    run()
