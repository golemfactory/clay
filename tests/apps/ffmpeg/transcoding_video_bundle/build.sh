#!/bin/bash -e

output_dir="$1"


function print_frame_types() {
    local input_file="$1"

    ffprobe                                                \
        -v              error                              \
        -show_entries   frame=pict_type                    \
        -select_streams "v:0"                              \
        -of             default=noprint_wrappers=1:nokey=1 \
        "$input_file"
}


mkdir --parents "$output_dir/original/"
mkdir --parents "$output_dir/good/"
mkdir --parents "$output_dir/bad/"

grep --invert-match "^$" video-sources.txt | while IFS=' ' read -r url source_name video_name max_duration file_name; do
    original_file="$output_dir/original/$file_name"
    if [[ -e "$original_file" ]]; then
        echo "Skipping already downloaded file $original_file"
        continue
    fi

    echo "Downloading $file_name"
    curl "$url"                       \
        --output     "$original_file" \
        --user-agent ""               \
        --location

    if [[ "$max_duration" == "bad" ]]; then
        echo "File $file_name ($input_i_frame_count key frames) marked as bad. Not splitting"
        cp --link "$original_file" "$output_dir/bad/" 2> /dev/null || cp "$original_file" "$output_dir/bad/"
        continue
    fi

    input_i_frame_count="$(print_frame_types "$original_file" | grep I | wc -l)"

    echo "Cutting $file_name ($input_i_frame_count key frames) down to $max_duration seconds"
    "$(dirname ${BASH_SOURCE[0]})/shorten-video.sh" \
        "$original_file"                            \
        "$output_dir/good/$file_name"               \
        "$output_dir/tmp-splits"                    \
        "$max_duration"
    echo
done
