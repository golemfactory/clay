#!/bin/bash -e

input_file="$1"

log_level=error

function strip_matching_line_endings {
    local lines="$1"
    local ending="$2"

    local IFS=$'\n'
    line_array=($lines)
    stripped_line_array=("${line_array[@]%$ending}")
    printf "%s\n" "${stripped_line_array[@]}"
}

function ffprobe_show_entries {
    local input_file="$1"
    local query="$2"
    local stream="$3"

    if [[ "$stream" != "" ]]; then
        stream_selector="-select_streams $stream"
    else
        stream_selector=""
    fi

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
            $stream_selector                             \
            -show_entries "$query"                       \
            -of           "compact=nokey=1"              \
            "$input_file"                                   |
            grep --invert-match --regexp "^program|stream|" |
            grep --invert-match --regexp "^$"               |
            cut --delimiter '|' --field 2
    )"

    printf "%s" "$(strip_matching_line_endings "$raw_result" side_data)"
}

width="$(ffprobe_show_entries  "$input_file" stream=width  "v:0")"
height="$(ffprobe_show_entries "$input_file" stream=height "v:0")"

duration="$(ffprobe_show_entries "$input_file" format=duration)"
if [[ "$duration" == "N/A" ]]; then
    duration_string="_"
else
    duration_string="$(printf "%.0fs" "$duration")"
fi

video_stream_count="$(ffprobe_show_entries    "$input_file" stream=codec_type v | grep --count "")" || true
audio_stream_count="$(ffprobe_show_entries    "$input_file" stream=codec_type a | grep --count "")" || true
subtitle_stream_count="$(ffprobe_show_entries "$input_file" stream=codec_type s | grep --count "")" || true
data_stream_count="$(ffprobe_show_entries     "$input_file" stream=codec_type d | grep --count "")" || true

stream_counts="$(printf "v%da%ds%dd%d" "$video_stream_count" "$audio_stream_count" "$subtitle_stream_count" "$data_stream_count")"

codecs="$(ffprobe_show_entries "$input_file" stream=codec_name "v:0" )"
for (( index=0; index < ${audio_stream_count}; index=index+1 )); do
    audio_codec="$(ffprobe_show_entries "$input_file" stream=codec_name "a:$index")"
    codecs="$codecs+$audio_codec"
done

frames=$(ffprobe_show_entries "$input_file" frame=pict_type v:0)
frame_count="$(echo   -n "$frames"                              | grep --count "")" || true
i_frame_count="$(echo -n "$frames" | tr --delete --complement I | wc --chars)"
p_frame_count="$(echo -n "$frames" | tr --delete --complement P | wc --chars)"
b_frame_count="$(echo -n "$frames" | tr --delete --complement B | wc --chars)"

frame_rate="$(ffprobe_show_entries "$input_file" stream=avg_frame_rate "v:0")"
if [[ "$frame_rate" != "0/0" ]]; then
    frame_rate_string="$(printf "%gfps" "$(python -c "print($frame_rate)")")"
else
    frame_rate_string="_"
fi

printf "[%s,%sx%s,%s,%s,i%dp%db%d,%s]\n" "$codecs" "$width" "$height" "$duration_string" "$stream_counts" "$i_frame_count" "$p_frame_count" "$b_frame_count" "$frame_rate_string"
