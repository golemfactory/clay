#!/bin/bash -e

input_file="$1"
output_file="$2"
tmp_dir="$3"
segment_duration="$4"


function get_extension() {
    local file_path="$1"

    local file_basename="$(basename "$file_path")"
    local file_extension="${file_basename##*.}"

    printf "%s" $file_extension
}


function strip_extension() {
    local file_path="$1"

    printf "%s" "${file_path%.*}"
}


function ffprobe_show_entries {
    local input_file="$1"
    local query="$2"

    printf "%s" $(
        ffprobe                                              \
            -v            error                              \
            -show_entries "$query"                           \
            -of           default=noprint_wrappers=1:nokey=1 \
            "$input_file"
    )
}


function count_files() {
    local dir="$1"

    printf "%d" "$(find "$dir" -maxdepth 1 -type f | wc --lines)"
}


function split_video() {
    local input_file="$1"
    local output_file="$2"
    local tmp_dir="$3"
    local segment_duration="$4"

    local split_dir="$tmp_dir/$(basename "$input_file")"
    mkdir --parents "$split_dir"

    local segment_name_pattern="$split_dir/$(strip_extension "$(basename "$input_file")")-%05d.$(get_extension "$input_file")"

    ffmpeg                                         \
        -nostdin                                   \
        -v                    warning              \
        -i                    "$input_file"        \
        -map                  0                    \
        -f                    segment              \
        -codec                copy                 \
        -copy_unknown                              \
        -segment_time         "$segment_duration"  \
        -segment_start_number 1                    \
        "$segment_name_pattern"

   num_segments="$(count_files "$split_dir")"

   if [[ "$num_segments" == 1 ]]; then
       chosen_segment="$input_file"
   else
       chosen_segment="$(printf "$segment_name_pattern" 1)"
       output_file="$(strip_extension "$output_file")[segment1of$num_segments].$(get_extension "$input_file")"
   fi

   echo "Copying or linking $chosen_segment -> $output_file"
   ln "$chosen_segment" "$output_file" 2> /dev/null || cp "$chosen_segment" "$output_file"
}


mkdir --parents "$(dirname "$output_file")"

echo "Splitting $input_file..."
split_video "$input_file" "$output_file" "$tmp_dir" "$segment_duration"
