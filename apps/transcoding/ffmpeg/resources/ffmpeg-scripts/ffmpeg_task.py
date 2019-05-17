import json
import os

# pylint: disable=import-error
from ffmpeg_tools import commands, meta
import m3u8
from m3u8_utils import create_and_dump_m3u8, join_playlists

OUTPUT_DIR = "/golem/output"
RESOURCES_DIR = "/golem/resources"
PARAMS_FILE = "params.json"


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


def do_merge(chunks, outputfilename):
    [output_playlist, _] = os.path.splitext(
        os.path.basename(outputfilename))
    merged = join_playlists(chunks)
    merged_filename = os.path.join(RESOURCES_DIR,
                                   output_playlist + ".m3u8")
    file = open(merged_filename, 'w')
    file.write(merged.dumps())
    file.close()

    commands.merge_videos(merged_filename, outputfilename)


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
        print("Invalid command.")


def run():
    params = None
    with open(PARAMS_FILE, 'r') as f:
        params = json.load(f)

    try:
        run_ffmpeg(params)
    except commands.CommandFailed as e:
        print(e.command)
        exit(e.error_code)


if __name__ == "__main__":
    run()
