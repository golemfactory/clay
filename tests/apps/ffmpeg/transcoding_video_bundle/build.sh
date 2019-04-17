#!/bin/bash -e

output_dir="$1"


mkdir --parents "$output_dir/original/"

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
    echo
done
