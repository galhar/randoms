#!/bin/bash

# Check if the root directory is provided
if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <root_directory>"
    exit 1
fi

ROOT_DIR="$1"

# Check if the provided directory exists
if [[ ! -d "$ROOT_DIR" ]]; then
    echo "Error: Directory '$ROOT_DIR' does not exist."
    exit 1
fi

# Iterate through all GIF files in subdirectories
# xargs instead of read, since read had issues of dropping the first characters randomly in the path
find "$ROOT_DIR" -type f -name "*.gif" -exec realpath {} \; | xargs -I{} sh -c '
    gif_file="{}"
    echo "Processing file: $gif_file"

    # Get the directory and filename without extension
    gif_dir=$(dirname "$gif_file")
    gif_base=$(basename "$gif_file" .gif)

    # Define the output MP4 file path
    mp4_file="$gif_dir/$gif_base.mp4"

    # Convert GIF to MP4 using ffmpeg
    echo "Converting $gif_file to $mp4_file..."
    ffmpeg -i "$gif_file" -movflags faststart -pix_fmt yuv420p -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" "$mp4_file" -y

    # Check the ffmpeg exit status
    if [ $? -eq 0 ]; then
        echo "Successfully converted $gif_file to $mp4_file"
    else
        echo "Error converting $gif_file. Check error.log for details."
    fi
'

echo "Conversion process completed."

echo "Conversion process completed."
