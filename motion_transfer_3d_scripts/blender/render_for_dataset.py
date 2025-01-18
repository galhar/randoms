import subprocess
import os
import argparse
from datetime import datetime

import imageio.v3 as imageio
import numpy as np

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate renders for files in a given directory.")
    parser.add_argument(
        "--objects_dir",
        type=str,
        help="The path to the objects_dir containing .glb files for rendering."
    )
    parser.add_argument(
        "--floor_texture_path",
        type=str,
        default=None,
        help="Path to the floor texture png",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="motions",
        choices=["motions", "blendernerf"],
        help="Mode to specify the rendering process. 'motions' for animation frames, 'blendernerf' for BlenderNeRF dataset.",
    )
    args = parser.parse_args()

    objects_dir = args.objects_dir

    # Ensure the provided objects_dir exists
    if not os.path.isdir(objects_dir):
        raise NotADirectoryError(f"The objects_dir '{objects_dir}' does not exist.")

    # Create 'renders' folder inside the input objects_dir if it doesn't exist
    # Determine the output folder name based on the mode
    output_folder_name = "renders" if args.mode == "motions" else "datasets"
    renders_dir = os.path.join(objects_dir, output_folder_name)
    os.makedirs(renders_dir, exist_ok=True)

    # Get all .glb, .fbx, and .obj files in the specified objects_dir
    supported_formats = [".glb", ".fbx", ".obj"]
    model_files = [file for file in os.listdir(objects_dir) if any(file.endswith(ext) for ext in supported_formats)]

    if not model_files:
        print(f"No supported files (.glb, .fbx, .obj) found in the objects_dir '{objects_dir}'.")
        exit(1)
    
    n_views = 16
    gpu_i = 0

    # Iterate over each .glb file in the objects_dir
    for model_file in model_files:
        obj_path = os.path.join(objects_dir, model_file)

        # Create a dedicated output folder for each .glb file
        output_dir = os.path.join(renders_dir, os.path.splitext(model_file)[0])  # renders/<glb_name>
        os.makedirs(output_dir, exist_ok=True)

        # Construct the blender command with dynamically populated paths
        blender_args = f"--object_path '{obj_path}' --num_renders {n_views} --output_dir '{output_dir}' --mode {args.mode}"# --engine CYCLES"
        if args.floor_texture_path is not None:
            blender_args += f" --floor_texture_path '{args.floor_texture_path}'"
        command = f"/snap/blender/current/blender --background --python blender_script.py -- {blender_args}"
        full_command = f"export DISPLAY=:0.{gpu_i} && {command}"

        # Render each object, capturing output
        print(datetime.now())
        print(full_command)
        try:
            res = subprocess.run(
                ["bash", "-c", full_command],
                timeout=40 * 60,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            print(res.stdout.decode("utf-8"))
        except subprocess.TimeoutExpired:
            print('Timeout, continue to next one...')

        # Create GIFs for each view angle directory
        for view_dir in os.listdir(output_dir):
            view_dir_path = os.path.join(output_dir, view_dir)
            if os.path.isdir(view_dir_path):
                # Collect all PNG files in the view directory, sorted by the numeric value in their filename
                png_files = sorted(
                    [os.path.join(view_dir_path, f) for f in os.listdir(view_dir_path) if f.endswith(".png")],
                    key=lambda x: int(os.path.splitext(os.path.basename(x))[0])
                )
        
                # Skip if no PNG files found
                if not png_files:
                    continue
                
                # Define GIF path
                gif_path = os.path.join(output_dir, f"{view_dir}.gif")
                
                # Create a GIF using imageio, ensuring a black background is added to each PNG
                frames = []
                for png in png_files:
                    img = imageio.imread(png)
                    if img.shape[-1] == 4:  # Check if the image has an alpha channel
                        background = np.ones(img.shape[:2] + (3,), dtype=img.dtype) * 255  # Create a white background
                        alpha = img[:, :, 3] / 255.0
                        for channel in range(3):  # Blend each color channel
                            background[:, :, channel] = (
                                img[:, :, channel] * alpha + background[:, :, channel] * (1 - alpha)
                            )
                        img = background.astype(img.dtype)
                    frames.append(img)
                imageio.imwrite(gif_path, frames, loop=0, duration=0.1)
                
                # Save the animation as an MP4 file
                mp4_path = os.path.join(output_dir, f"{view_dir}.mp4")
                imageio.imwrite(mp4_path, frames, fps=10)


