#!/bin/bash -e

input_dir="$1"


function print_frame_types() {
    local input_file="$1"

    ffprobe                                                \
        -v              error                              \
        -show_entries   frame=pict_type                    \
        -select_streams "v:0"                              \
        -of             default=noprint_wrappers=1:nokey=1 \
        "$input_file"
}


video_files="$(find "$input_dir" -type f)"
for video_file in $video_files; do
    i_frame_count="$(print_frame_types "$video_file" | grep I | wc -l)"
    printf "%5d key frames in %s\n" "$i_frame_count" "$video_file"
done
