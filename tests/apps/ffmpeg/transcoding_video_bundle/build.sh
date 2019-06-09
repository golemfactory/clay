#!/bin/bash -e

bundle_version="$1"

output_dir="$(dirname "${BASH_SOURCE[0]}")/transcoding-video-bundle"
index_file="$output_dir/index.md"


function get_extension {
    local file_path="$1"

    local file_basename="$(basename "$file_path")"
    local file_extension="${file_basename##*.}"

    printf "%s" $file_extension
}

function print_frame_types() {
    local input_file="$1"

    ffprobe                                                \
        -v              error                              \
        -show_entries   frame=pict_type                    \
        -select_streams "v:0"                              \
        -of             default=noprint_wrappers=1:nokey=1 \
        "$input_file"
}


mkdir --parents "$output_dir/download/"
mkdir --parents "$output_dir/original/"
mkdir --parents "$output_dir/good/"
mkdir --parents "$output_dir/bad/"

printf "| %110s | %120s |\n" "File name" "Source URL" > "$index_file"
printf "| %110s | %120s |\n" | tr " " "-"            >> "$index_file"

i=1
grep --invert-match "^$" video-sources.txt | while IFS=' ' read -r url source_name video_name max_duration; do
    original_file="$output_dir/download/$i-$(basename "$url")"

    echo "Downloading $(basename "$url")"
    curl "$url"                       \
        --output     "$original_file" \
        --user-agent ""               \
        --location

    input_i_frame_count="$(print_frame_types "$original_file" | grep I | wc -l)"
    meta_name="$(./build-name.sh "$original_file")"
    file_name="$source_name-$video_name$meta_name.$(get_extension "$original_file")"
    renamed_original_file="$output_dir/original/$file_name"
    mv "$original_file" "$renamed_original_file"
    echo "Renamed to $(basename "$renamed_original_file")"

    if [[ "$max_duration" == "bad" ]]; then
        echo "File $(basename "$url") ($input_i_frame_count key frames) marked as bad. Not splitting"
        cp --link "$renamed_original_file" "$output_dir/bad/" 2> /dev/null || cp "$renamed_original_file" "$output_dir/bad/"

        printf "| %110s | %120s |\n" "$(basename "$renamed_original_file")" "$url" >> "$index_file"
        i=$(( ++i ))
        continue
    fi

    echo "Cutting $renamed_original_file ($input_i_frame_count key frames) down to $max_duration seconds"
    "$(dirname ${BASH_SOURCE[0]})/shorten-video.sh" \
        "$renamed_original_file"                    \
        "$output_dir/good/$file_name"               \
        "$output_dir/tmp-splits"                    \
        "$max_duration"
    echo

    printf "| %110s | %120s |\n" "$(basename "$renamed_original_file")" "$url" >> "$index_file"
    i=$(( ++i ))
done


# NOTE: Surprisingly Using level 9 zip compression does save some space (5-10%) even though
# the archive contains only highly compressed videos.
cd "$(dirname "${BASH_SOURCE[0]}")"
zip                                                  \
    -9                                               \
    --recurse-paths                                  \
    "transcoding-video-bundle-v$bundle_version.zip"  \
    transcoding-video-bundle/                        \
    --exclude transcoding-video-bundle/original/\*   \
    --exclude transcoding-video-bundle/download/\*   \
    --exclude transcoding-video-bundle/tmp-splits/\*
zip                                                          \
    -9                                                       \
    --recurse-paths                                          \
    "transcoding-video-bundle-v$bundle_version-original.zip" \
    transcoding-video-bundle/                                \
    --exclude transcoding-video-bundle/bad/\*                \
    --exclude transcoding-video-bundle/good/\*               \
    --exclude transcoding-video-bundle/download/\*           \
    --exclude transcoding-video-bundle/tmp-splits/\*
