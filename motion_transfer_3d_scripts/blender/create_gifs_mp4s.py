import os
import re

from tqdm import tqdm
from PIL import Image
import cv2
import numpy as np


def find_angle_directories(root_directory, regex_pattern):
    matching_dirs = []
    for dirpath, dirnames, _ in os.walk(root_directory):
        for dirname in dirnames:
            if re.match(regex_pattern, dirname):
                matching_dirs.append(os.path.join(dirpath, dirname))
    return matching_dirs


def create_gif_and_mp4(root_directory):
    # Regex for directories like 90.0, 180.0
    regex_pattern = r"^-*[0-9]+\.[0-9]+$"

    # Find all matching angle directories
    angle_dirs = find_angle_directories(root_directory, regex_pattern)

    for angle_dir in tqdm(angle_dirs):
        angle_name = os.path.basename(angle_dir)
        obj_dir = os.path.dirname(angle_dir)

        # Collect PNG images in the directory
        png_files = [f for f in os.listdir(angle_dir) if f.endswith('.png')]
        if not png_files:
            continue

        # Sort PNG files for consistent ordering
        png_files.sort()
        images = []

        for png_file in png_files:
            img_path = os.path.join(angle_dir, png_file)
            img = Image.open(img_path).convert("RGBA")

            # Add white background
            background = Image.new("RGBA", img.size, (255, 255, 255, 255))
            combined = Image.alpha_composite(background, img)
            images.append(combined.convert("RGB"))

        # Create GIF
        gif_path = os.path.join(obj_dir, f"{angle_name}.gif")
        images[0].save(
            gif_path,
            save_all=True,
            append_images=images[1:],
            duration=200,  # Adjust duration as needed
            loop=0
        )

        # Create MP4
        mp4_path = os.path.join(obj_dir, f"{angle_name}.mp4")
        height, width = images[0].size
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_writer = cv2.VideoWriter(mp4_path, fourcc, 5, (width, height))

        for img in images:
            frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            video_writer.write(frame)

        video_writer.release()


if __name__ == "__main__":
    root_directory = "/home/gal/datasets/experiments/motion_transfer_3d/skeleton_free_justification/motions/"  # Replace with your root directory path
    create_gif_and_mp4(root_directory)
