print("Script starting...") # Helping cursorai to not keyboard interrupt when running it

import subprocess
import os
import argparse
from datetime import datetime

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render human animation from OBJ sequence files.")
    parser.add_argument(
        "--obj_dir",
        type=str,
        required=True,
        help="The path to the directory containing .obj files for rendering (e.g., frame000.obj, frame001.obj, ...)."
    )
    parser.add_argument(
        "--file_prefix",
        type=str,
        default="frame",
        help="Filename prefix before numbers (default: 'frame')."
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Sequence framerate (default: 30)."
    )
    parser.add_argument(
        "--resolution",
        type=int,
        nargs=2,
        default=[1920, 1080],
        metavar=("WIDTH", "HEIGHT"),
        help="Render resolution (default: 1920 1080)."
    )
    parser.add_argument(
        "--output_mp4",
        type=str,
        required=True,
        help="Output path for the MP4 file."
    )
    parser.add_argument(
        "--use_hdri",
        action="store_true",
        help="Use an HDRI instead of lights."
    )
    parser.add_argument(
        "--hdri_path",
        type=str,
        default=None,
        help="Path to the HDRI file (only used if --use_hdri is set)."
    )
    parser.add_argument(
        "--cinematic_dolly",
        action="store_true",
        default=True,
        help="Enable slow camera push-in (default: True)."
    )
    parser.add_argument(
        "--no_cinematic_dolly",
        action="store_false",
        dest="cinematic_dolly",
        help="Disable slow camera push-in."
    )
    parser.add_argument(
        "--max_frames",
        type=int,
        default=None,
        help="Maximum number of frames to process (for debugging/testing). If None, processes all frames."
    )
    args = parser.parse_args()

    print(f"[Python Wrapper] Starting render_human_animation.py")
    print(f"[Python Wrapper] Arguments parsed:")
    print(f"  - OBJ directory: {args.obj_dir}")
    print(f"  - File prefix: {args.file_prefix}")
    print(f"  - FPS: {args.fps}")
    print(f"  - Resolution: {args.resolution[0]}x{args.resolution[1]}")
    print(f"  - Output MP4: {args.output_mp4}")
    print(f"  - Use HDRI: {args.use_hdri}")
    print(f"  - Cinematic dolly: {args.cinematic_dolly}")
    print(f"  - Max frames: {args.max_frames if args.max_frames else 'All'}")

    obj_dir = args.obj_dir

    # Ensure the provided obj_dir exists
    if not os.path.isdir(obj_dir):
        raise NotADirectoryError(f"The obj_dir '{obj_dir}' does not exist.")
    print(f"[Python Wrapper] OBJ directory verified: {obj_dir}")

    # Ensure output directory exists
    output_dir = os.path.dirname(os.path.abspath(args.output_mp4))
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"[Python Wrapper] Created output directory: {output_dir}")
    elif output_dir:
        print(f"[Python Wrapper] Output directory exists: {output_dir}")

    # Get the absolute path to the blender script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    blender_script_path = os.path.join(script_dir, "blender_render_obj_human_motion.py")
    print(f"[Python Wrapper] Blender script path: {blender_script_path}")

    # Construct the blender command with dynamically populated paths
    # Use proper escaping for paths with spaces
    import shlex
    blender_args = (
        f"--obj_dir {shlex.quote(obj_dir)} "
        f"--file_prefix {shlex.quote(args.file_prefix)} "
        f"--fps {args.fps} "
        f"--resolution {args.resolution[0]} {args.resolution[1]} "
        f"--output_mp4 {shlex.quote(args.output_mp4)}"
    )
    
    if args.use_hdri and args.hdri_path:
        blender_args += f" --use_hdri --hdri_path {shlex.quote(args.hdri_path)}"
    
    if args.cinematic_dolly:
        blender_args += " --cinematic_dolly"
    else:
        blender_args += " --no_cinematic_dolly"
    
    if args.max_frames is not None:
        blender_args += f" --max_frames {args.max_frames}"

    command = f"/snap/blender/current/blender --background --python {shlex.quote(blender_script_path)} -- {blender_args}"
    full_command = f"export DISPLAY=:0.0 && {command}"

    # Render the animation, capturing output
    print(f"[Python Wrapper] Starting Blender at {datetime.now()}")
    print(f"[Python Wrapper] Command: {command}")
    print(f"[Python Wrapper] Waiting for Blender to complete...")
    try:
        res = subprocess.run(
            ["bash", "-c", full_command],
            timeout=60 * 60,  # 1 hour timeout
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output = res.stdout.decode("utf-8")
        print(output)
        if res.returncode != 0:
            print(f"[Python Wrapper] WARNING: Blender exited with code {res.returncode}")
        else:
            print(f"[Python Wrapper] Blender completed successfully at {datetime.now()}")
            if os.path.exists(args.output_mp4):
                file_size = os.path.getsize(args.output_mp4)
                print(f"[Python Wrapper] Output file created: {args.output_mp4} ({file_size / (1024*1024):.2f} MB)")
            else:
                print(f"[Python Wrapper] WARNING: Output file not found at {args.output_mp4}")
    except subprocess.TimeoutExpired:
        print(f'[Python Wrapper] ERROR: Timeout after 1 hour, rendering took too long...')

