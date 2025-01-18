#!/bin/bash

SBATCH_SCRIPT="$(pwd)/single_3dgs_recon.sh"

# Default to current directory if no argument is provided
if [[ $# -eq 1 ]]; then
    ROOT_DIR="$1"
else
    ROOT_DIR="$(pwd)"
fi

# Navigate to the root directory
cd "$ROOT_DIR" || { echo "Error: Cannot access directory $ROOT_DIR"; exit 1; }

# Check if the root directory contains subfolders
if [[ ! -d "$ROOT_DIR" ]]; then
    echo "Error: Root directory '$ROOT_DIR' does not exist."
    exit 1
fi

# Iterate through each dataset.zip file in the structure
find "$ROOT_DIR" -type f -name "dataset.zip" | while read -r dataset_zip; do
    # Get the directory containing the dataset.zip file
    dataset_path=$(dirname "$dataset_zip")

    # Check if the target file exists
    target_file="$dataset_path/output/point_cloud/iteration_30000/point_cloud.ply"
    if [[ -f "$target_file" ]]; then
        #echo "Skipping job submission for $dataset_path as $target_file exists."
        continue
    fi

    # Submit the sbatch job
    echo "Submitting job for: $dataset_path"
    sbatch --export=dataset_path="$dataset_path" "$SBATCH_SCRIPT"
done

echo "All jobs have been submitted."
