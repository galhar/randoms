import subprocess
import os
import argparse
from datetime import datetime

import imageio.v3 as imageio
import numpy as np

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate renders for .glb files in a given directory.")
    parser.add_argument(
        "--motions_dir",
        type=str,
        help="The path to the motions_dir containing .glb files for rendering."
    )
    parser.add_argument(
        "--floor_texture_path",
        type=str,
        default=None,
        help="Path to the floor texture png",
    )
    args = parser.parse_args()

    input_dir = args.motions_dir

    # Ensure the provided motions_dir exists
    if not os.path.isdir(input_dir):
        raise NotADirectoryError(f"The motions_dir '{input_dir}' does not exist.")

    # Create 'renders' folder inside the input motions_dir if it doesn't exist
    renders_dir = os.path.join(input_dir, "renders")
    os.makedirs(renders_dir, exist_ok=True)

    # Get all .glb files in the specified motions_dir
    glb_files = [file for file in os.listdir(input_dir) if file.endswith(".glb")]

    if not glb_files:
        print(f"No .glb files found in the motions_dir '{input_dir}'.")
        exit(1)
    
    n_views = 16
    gpu_i = 0

    # Iterate over each .glb file in the motions_dir
    for glb_file in glb_files:
        obj_path = os.path.join(input_dir, glb_file)

        # Create a dedicated output folder for each .glb file
        output_dir = os.path.join(renders_dir, os.path.splitext(glb_file)[0])  # renders/<glb_name>
        os.makedirs(output_dir, exist_ok=True)

        # Construct the blender command with dynamically populated paths
        args = f"--object_path '{obj_path}' --floor_texture_path '{args.floor_texture_path}' --num_renders {n_views} --output_dir '{output_dir}'"# --engine CYCLES"
        command = f"/snap/blender/current/blender --background --python blender_script.py -- {args}"
        full_command = f"export DISPLAY=:0.{gpu_i} && {command}"

        # Render each object, capturing output
        # TODO: continue debug why the dino get an animation only on its first frame (same happened a lot in the animals) then re-render the animals and human again, to have it for tomorrow
        print(datetime.now())
        print(full_command)
        res = subprocess.run(
            ["bash", "-c", full_command],
            timeout=40 * 60,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        print(res.stdout.decode("utf-8"))
        
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
                        background = np.zeros(img.shape[:2] + (3,), dtype=img.dtype)  # Create a black background
                        alpha = img[:, :, 3] / 255.0
                        for channel in range(3):  # Blend each color channel
                            background[:, :, channel] = (
                                img[:, :, channel] * alpha + background[:, :, channel] * (1 - alpha)
                            )
                        img = background.astype(img.dtype)
                    frames.append(img)
                imageio.imwrite(gif_path, frames, loop=0, duration=0.1)


