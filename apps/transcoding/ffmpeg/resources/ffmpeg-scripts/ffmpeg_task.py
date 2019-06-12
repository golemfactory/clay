import json
import re
import os
import sys

from ffmpeg_tools import commands, meta

# pylint: disable=import-error
import m3u8
from m3u8_utils import create_and_dump_m3u8

OUTPUT_DIR = "/golem/output"
RESOURCES_DIR = "/golem/resources"
PARAMS_FILE = "params.json"

TRANSCODED_VIDEO_REGEX = re.compile(r'_(\d+)_TC\.[^.]+')
FFCONCAT_LIST_BASENAME = "merge-input.ffconcat"


class InvalidCommand(Exception):
    pass


def do_split(path_to_stream, parts):

    video_metadata = commands.get_metadata_json(path_to_stream)
    video_length = meta.get_duration(video_metadata)
    split_file = commands.split_video(path_to_stream,
                                      OUTPUT_DIR, video_length / parts)
    m3u8_main_list = m3u8.load(split_file)

    results = dict()
    segments_list = list()

    for segment in m3u8_main_list.segments:
        segment_info = dict()

        filename = create_and_dump_m3u8(OUTPUT_DIR, segment)

        segment_info["playlist"] = os.path.basename(filename)
        segment_info["video_segment"] = segment.uri

        segments_list.append(segment_info)

    results["main_list"] = split_file
    results["segments"] = segments_list
    results["metadata"] = video_metadata

    results_file = os.path.join(OUTPUT_DIR, "split-results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f)


def do_transcode(track, targs, output, use_playlist):
    commands.transcode_video(track, targs, output, use_playlist)


def select_transcoded_video_paths(output_file_paths, output_extension):
    return [path
            for path in output_file_paths
            if path.endswith(f'_TC{output_extension}')]


def sorted_transcoded_video_paths(transcoded_video_paths):
    path_index = {int(re.findall(TRANSCODED_VIDEO_REGEX, path)[0]): path
                    for path in transcoded_video_paths}
    return [value for key, value in sorted(path_index.items())]


def build_and_store_ffconcat_list(chunks, output_filename, list_basename):
    assert len(chunks) >= 1
    assert len(set(os.path.dirname(chunk) for chunk in chunks)) == 1, \
        "Merge won't work if chunks are not all in the same directory"

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


def do_merge(chunks, outputfilename):
    ffconcat_list_filename = build_and_store_ffconcat_list(
        chunks,
        outputfilename,
        FFCONCAT_LIST_BASENAME)
    commands.merge_videos(ffconcat_list_filename, outputfilename)


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
    if params['command'] == "split":
        do_split(
            params['path_to_stream'],
            params['parts'])
    elif params['command'] == "transcode":
        do_transcode(
            params['track'],
            params['targs'],
            params['output_stream'],
            params['use_playlist'])
    elif params['command'] == "merge":
        do_merge(
            params['chunks'],
            params['output_stream'])
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
