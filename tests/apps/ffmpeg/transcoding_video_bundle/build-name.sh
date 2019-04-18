#!/bin/bash -e

input_file="$1"

log_level=error

function ffprobe_show_entries {
    local input_file="$1"
    local query="$2"

    raw_result="$(
        # NOTE: ffprobe output in the compact format looks more or less like this:
        #
        # ```
        # program|stream|vp9
        # program|stream|h264
        # program|stream|aac
        # program|stream|subrip
        # program|stream|subrip
        #
        # stream|vp9
        # stream|h264
        # stream|aac
        # stream|subrip
        # stream|subripside_data|
        # ```
        #
        # The extra processing after the ffprobe call below is meant to strip the unnecessary stuff:
        # 1) If the container supports programs (like mpegts does for example), ffprobe prints stream
        #    info multiple times: once on its own and then again for each program. We use grep
        #    to filter out lines starting with 'program|stream|' and keep only those starting
        #    with 'stream|'.
        # 2) There are empty lines between sections. They get in the way when we want to use
        #    `wc --lines` to count the returned items so we strip them too.
        # 3) Some containers (e.g. webm) can store so called 'side data'. It should start
        #    on a new line just like 'stream|' but for some reason with 'nokey=1' ffprobe
        #    omits the newline. I don't see a way to tell ffprobe not to do it so we just
        #    strip it with a regex if present but it's not foolproof. If a field contains
        #   'side_data' it's going to get stripped too.
        ffprobe                                          \
            -v            error                          \
            -show_entries "$query"                       \
            -of           "compact=nokey=1"              \
            "$input_file"                                   |
            grep --invert-match --regexp "^program|stream|" |
            grep --invert-match --regexp "^$"               |
            cut --delimiter '|' --field 2
    )"

    result="${raw_result%side_data}"
    printf "%s" "$result"
}

function ffprobe_get_stream_attribute {
    local input_file="$1"
    local stream="$2"
    local attribute="$3"

    printf "%s" $(
        ffprobe                                                \
            -v              error                              \
            -select_streams "$stream"                          \
            -show_entries   "stream=$attribute"                \
            -of             default=noprint_wrappers=1:nokey=1 \
            "$input_file"
    )
}

width="$(ffprobe_get_stream_attribute "$input_file" "v:0" width)"
height="$(ffprobe_get_stream_attribute "$input_file" "v:0" height)"

duration="$(ffprobe_show_entries "$input_file" format=duration)"

video_stream_count="$(ffprobe -show_entries stream=codec_type -select_streams v -of default=noprint_wrappers=1:nokey=1 -hide_banner -v error "$input_file" | wc -l)"
audio_stream_count="$(ffprobe -show_entries stream=codec_type -select_streams a -of default=noprint_wrappers=1:nokey=1 -hide_banner -v error "$input_file" | wc -l)"
subtitle_stream_count="$(ffprobe -show_entries stream=codec_type -select_streams s -of default=noprint_wrappers=1:nokey=1 -hide_banner -v error "$input_file" | wc -l)"
data_stream_count="$(ffprobe -show_entries stream=codec_type -select_streams d -of default=noprint_wrappers=1:nokey=1 -hide_banner -v error "$input_file" | wc -l)"

stream_counts="$(printf "v%da%ds%dd%d" "$video_stream_count" "$audio_stream_count" "$subtitle_stream_count" "$data_stream_count")"

codecs="$(ffprobe_get_stream_attribute "$input_file" "v:0" codec_name)"
for (( index=0; index < ${audio_stream_count}; index=index+1 )); do
    audio_codec="$(ffprobe_get_stream_attribute "$input_file" "a:$index" codec_name)"
    codecs="$codecs+$audio_codec"
done

frames=$(ffprobe -show_frames "$input_file" 2> /dev/null | grep "pict_type=" | sed 's/pict_type=\(.*\)$/\1/' | tr -d '\n')
frame_count="$(echo -n "$frames"                   | wc --chars)"
i_frame_count="$(echo -n "$frames" | sed 's/[^I]//g' | wc --chars)"
p_frame_count="$(echo -n "$frames" | sed 's/[^P]//g' | wc --chars)"
b_frame_count="$(echo -n "$frames" | sed 's/[^B]//g' | wc --chars)"

frame_rate="$(ffprobe_get_stream_attribute "$input_file" "v:0" r_frame_rate)"
frame_rate_float=$(
    python -c "print($frame_rate)"
)

printf "[%s,%sx%s,%.0fs,%s,i%dp%db%d,fps%.2f]\n" "$codecs" "$width" "$height" "$duration" "$stream_counts" "$i_frame_count" "$p_frame_count" "$b_frame_count" "$frame_rate_float"
