import json
import re
import os
import sys
from typing import Any, Dict, Optional

from ffmpeg_tools import codecs, commands, formats, meta, validation

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
               intermediate_container=None):

    video_metadata = commands.get_metadata_json(input_file)
    if intermediate_container is None:
        format_demuxer = meta.get_format(video_metadata)
        intermediate_container = formats.\
            get_safe_intermediate_format_for_demuxer(format_demuxer)

    commands.extract_streams(
        input_file,
        output_file,
        selected_streams,
        intermediate_container)

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
    intermediate_container = formats.get_safe_intermediate_format_for_demuxer(
        format_demuxer)

    segment_list_path = commands.split_video(
        path_to_stream,
        OUTPUT_DIR,
        video_length / parts,
        intermediate_container)

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


def _fetch_encoder_info_if_requested(
        target_audio_codec: str,
        muxer_info: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:

    encoder_info_requested = (
        target_audio_codec is not None
        # Even if encoder info was not explicitly requested by specifying an
        # audio codec,
        or muxer_info is not None
        and "default_audio_codec" in muxer_info
    )
    if not encoder_info_requested:
        return None

    if target_audio_codec is not None:
        audio_codec_name = target_audio_codec
    else:
        audio_codec_name = muxer_info["default_audio_codec"]

    try:
        audio_codec = codecs.AudioCodec(audio_codec_name)
    except validation.UnsupportedAudioCodec:
        # Getting an unsupported codec is entirely possible here because
        # validations have not been performed yet. Now we know that they
        # won't pass so there's no point in crashing the container.
        # Just return empty encoder info and let the validations handle
        # the problem gracefully.
        print(
            f"WARNING: Could not fetch encoder info for unsupported codec "
            f"'{audio_codec_name}'",
            file=sys.stderr)
        return None

    encoder = audio_codec.get_encoder()
    if encoder is None:
        # There's no encoder assigned to this codec in ffmpeg_tools.
        # Probably ffmpeg does not even have an encoder for this format.
        # Again, this is something that should be detected by validations
        # but they have not been performed yet.
        print(
            f"WARNING: Could not fetch encoder info for codec "
            f"'{audio_codec_name}' because it has no encoder assigned.",
            file=sys.stderr)
        return None

    return commands.query_encoder_info(encoder)


def do_extract_and_split(input_file,
                         parts,
                         target_container=None,
                         target_audio_codec=None,
                         intermediate_container=None):
    input_basename = os.path.basename(input_file)
    [input_stem, input_extension] = os.path.splitext(input_basename)

    intermediate_file = os.path.join(
        WORK_DIR,
        f"{input_stem}[video-only]{input_extension}")

    extract_results = do_extract(input_file,
                                 intermediate_file,
                                 ['v'],
                                 intermediate_container)

    split_results = do_split(intermediate_file, parts)

    results = {
        "main_list": split_results["main_list"],
        "segments": split_results["segments"],
        "metadata": extract_results["metadata"],
    }

    if target_container is not None:
        results["muxer_info"] = commands.query_muxer_info(target_container)

    encoder_info = _fetch_encoder_info_if_requested(
        target_audio_codec,
        results["muxer_info"] if "muxer_info" in results else None,
    )
    if encoder_info is not None:
        results["encoder_info"] = encoder_info

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


def do_merge(chunks, outputfilename, target_container=None):
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
        target_container)


def do_replace(input_file,
               replacement_source,
               output_file,
               stream_type,
               targs,
               target_container=None,
               strip_unsupported_data_streams=False,
               strip_unsupported_subtitle_streams=False):

    commands.replace_streams(
        input_file,
        replacement_source,
        output_file,
        stream_type,
        targs,
        target_container,
        strip_unsupported_data_streams,
        strip_unsupported_subtitle_streams)


def do_merge_and_replace(input_file,
                         chunks,
                         output_file,
                         targs,
                         target_container=None,
                         strip_unsupported_data_streams=False,
                         strip_unsupported_subtitle_streams=False):

    output_basename = os.path.basename(output_file)
    [output_stem, output_extension] = os.path.splitext(output_basename)

    intermediate_file = os.path.join(
        WORK_DIR,
        f"{output_stem}[video-only]{output_extension}")

    do_merge(chunks, intermediate_file, target_container)
    do_replace(
        input_file,
        intermediate_file,
        output_file,
        'v',
        targs,
        target_container,
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


def query_muxer_info(muxer):
    results = {"muxer_info": commands.query_muxer_info(muxer)}
    results_file = os.path.join(OUTPUT_DIR, "query-muxer-info-results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f)


def query_encoder_info(encoder):
    results = {"encoder_info": commands.query_encoder_info(encoder)}
    results_file = os.path.join(OUTPUT_DIR, "query-encoder-info-results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f)


def run_ffmpeg(params):
    if params['command'] == "extract":
        do_extract(
            params['input_file'],
            params['output_file'],
            params['selected_streams'],
            params.get('intermediate_container'))
    elif params['command'] == "split":
        do_split(
            params['path_to_stream'],
            params['parts'])
    elif params['command'] == "extract-and-split":
        do_extract_and_split(
            params['input_file'],
            params['parts'],
            params.get('target_container'),
            params.get('target_audio_codec'),
            params.get('intermediate_container'))
    elif params['command'] == "transcode":
        do_transcode(
            params['track'],
            params['targs'],
            params['output_stream'])
    elif params['command'] == "merge":
        do_merge(
            params['chunks'],
            params['output_stream'],
            params.get('target_container'))
    elif params['command'] == "replace":
        do_replace(
            params['input_file'],
            params['replacement_source'],
            params['output_file'],
            params['stream_type'],
            params['targs'],
            params.get('target_container'),
            params.get('strip_unsupported_data_streams'),
            params.get('strip_unsupported_subtitle_streams'))
    elif params['command'] == "merge-and-replace":
        do_merge_and_replace(
            params['input_file'],
            params['chunks'],
            params['output_file'],
            params['targs'],
            params.get('target_container'),
            params.get('strip_unsupported_data_streams'),
            params.get('strip_unsupported_subtitle_streams'))
    elif params['command'] == "compute-metrics":
        compute_metrics(
            params["metrics_params"])
    elif params['command'] == "query-muxer-info":
        query_muxer_info(
            params["muxer"])
    elif params['command'] == "query-encoder-info":
        query_encoder_info(
            params["encoder"])
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
