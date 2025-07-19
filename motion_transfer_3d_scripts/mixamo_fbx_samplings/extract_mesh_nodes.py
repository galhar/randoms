import subprocess
import os
import argparse
import json
from datetime import datetime

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Render motion transfer videos for FBX files.")
    parser.add_argument(
        "--motions_dir",
        type=str,
        required=True,
        help="Path to directory containing motion FBX files"
    )
    parser.add_argument(
        "--targets_dir", 
        type=str,
        required=True,
        help="Path to directory containing target object FBX files"
    )
    parser.add_argument(
        "--frames_json",
        type=str,
        required=True,
        help="Path to JSON file containing frame ranges for each motion"
    )
    parser.add_argument(
        "--frames_n",
        type=int,
        default=14,
        help="Number of frames to sample (default: 14)"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="./renders",
        help="Base output directory for rendered videos (default: ./renders)"
    )
    
    args = parser.parse_args()
    
    # Validate input directories and files
    if not os.path.isdir(args.motions_dir):
        raise NotADirectoryError(f"Motions directory '{args.motions_dir}' does not exist.")
    if not os.path.isdir(args.targets_dir):
        raise NotADirectoryError(f"Targets directory '{args.targets_dir}' does not exist.")
    if not os.path.isfile(args.frames_json):
        raise FileNotFoundError(f"Frames JSON file '{args.frames_json}' does not exist.")
    
    # Load frames JSON
    with open(args.frames_json, 'r') as f:
        frames_data = json.load(f)
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Get all motion and target FBX files
    motion_files = [f for f in os.listdir(args.motions_dir) if f.endswith('.fbx')]
    target_files = [f for f in os.listdir(args.targets_dir) if f.endswith('.fbx')]
    
    if not motion_files:
        print(f"No motion FBX files found in '{args.motions_dir}'")
        exit(1)
    if not target_files:
        print(f"No target FBX files found in '{args.targets_dir}'")
        exit(1)
        
    print(f"Found {len(motion_files)} motion files and {len(target_files)} target files")
    
    gpu_i = 0
    
    # Process each motion-target combination
    for motion_file in motion_files:
        motion_name = os.path.splitext(motion_file)[0]
        motion_path = os.path.join(args.motions_dir, motion_file)
        
        # Check if frame data exists for this motion
        if motion_name not in frames_data:
            print(f"Warning: No frame data found for motion '{motion_name}', skipping...")
            continue
            
        for target_file in target_files:
            target_name = os.path.splitext(target_file)[0]
            target_path = os.path.join(args.targets_dir, target_file)
            
            # Create output directory for this combination
            output_subdir = os.path.join(args.output_dir, f"{target_name}_{motion_name}")
            os.makedirs(output_subdir, exist_ok=True)
            
            # Construct blender command arguments
            blender_args = f"--animation_fbx '{motion_path}' --object_fbx '{target_path}' --motion_name '{motion_name}' --frames_n {args.frames_n} --frames_json '{args.frames_json}' --output_path '{output_subdir}'"
            
            # Full blender command
            command = f"/snap/blender/current/blender --background --python b_extract_mesh_nodes.py -- {blender_args}"
            full_command = f"export DISPLAY=:0.{gpu_i} && {command}"
            
            print(f"\n{datetime.now()}")
            print(f"Processing: {motion_name} -> {target_name}")
            print(f"Command: {full_command}")
            
            try:
                res = subprocess.run(
                    ["bash", "-c", full_command],
                    timeout=40 * 60,  # 40 minutes timeout
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=os.path.dirname(os.path.abspath(__file__))  # Run from script directory
                )
                print(res.stdout.decode("utf-8"))
                
                if res.returncode != 0:
                    print(f"Warning: Command failed with return code {res.returncode}")
                    
            except subprocess.TimeoutExpired:
                print('Timeout, continuing to next combination...')
                
    print("\nAll combinations processed!")
