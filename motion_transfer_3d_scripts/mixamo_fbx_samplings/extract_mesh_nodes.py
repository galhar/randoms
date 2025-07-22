import subprocess
import os
import argparse
import json
from datetime import datetime

def create_animation_gif(mesh_dir, output_name, interval=400):
    """Create an animated GIF from extracted mesh data"""
    try:
        import numpy as np
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D
        from matplotlib.animation import FuncAnimation, PillowWriter
        import glob
    except ImportError as e:
        print(f"Warning: Could not import required libraries for GIF creation: {e}")
        print("Skipping GIF creation...")
        return False
    
    # Load metadata
    metadata_file = os.path.join(mesh_dir, "metadata.json")
    if os.path.exists(metadata_file):
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        object_name = metadata['object_name']
        motion_name = metadata['motion_name']
    else:
        object_name = "unknown"
        motion_name = "unknown"
    
    # Get all frame files
    frame_files = sorted(glob.glob(os.path.join(mesh_dir, "frame_*_vertices.npy")))
    num_frames = len(frame_files)
    
    if num_frames == 0:
        print("No frame files found for GIF creation!")
        return False
    
    print(f"Creating GIF animation: {object_name} - {motion_name} ({num_frames} frames)")
    
    # Load all vertices and calculate bounds
    all_vertices = []
    for frame_file in frame_files:
        vertices = np.load(frame_file)
        all_vertices.append(vertices)
    
    all_vertices_stacked = np.vstack(all_vertices)
    x_min, x_max = all_vertices_stacked[:, 0].min(), all_vertices_stacked[:, 0].max()
    y_min, y_max = all_vertices_stacked[:, 1].min(), all_vertices_stacked[:, 1].max()
    z_min, z_max = all_vertices_stacked[:, 2].min(), all_vertices_stacked[:, 2].max()
    
    # Create figure and axis
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    def update(frame_idx):
        if frame_idx < len(all_vertices):
            vertices = all_vertices[frame_idx]
            ax.clear()
            ax.scatter(vertices[:, 0], vertices[:, 1], vertices[:, 2], 
                      c=vertices[:, 2], cmap='viridis', s=0.5, alpha=0.7)
            
            ax.set_xlim(x_min, x_max)
            ax.set_ylim(y_min, y_max)
            ax.set_zlim(z_min, z_max)
            ax.set_xlabel('X')
            ax.set_ylabel('Y')
            ax.set_zlabel('Z')
            ax.view_init(elev=15, azim=45)
            ax.set_title(f"{object_name} - {motion_name} - Frame {frame_idx}")
    
    # Create animation
    anim = FuncAnimation(fig, update, frames=num_frames, interval=interval, repeat=True)
    
    # Save as GIF
    try:
        writer = PillowWriter(fps=1000//interval)
        anim.save(output_name, writer=writer)
        print(f"GIF saved successfully: {output_name}")
        plt.close()
        return True
    except Exception as e:
        print(f"Error saving GIF: {e}")
        try:
            anim.save(output_name, writer='pillow', fps=1000//interval)
            print(f"GIF saved successfully with alternative method: {output_name}")
            plt.close()
            return True
        except Exception as e2:
            print(f"Failed to save GIF: {e2}")
            plt.close()
            return False

def apply_fps_sampling_and_prepare_gif(mesh_nodes_dir, output_subdir, target_name, motion_name):
    """
    Apply mesh surface sampling to generate uniform point clouds and prepare directory for GIF creation.
    
    Note: Mesh surface sampling is done here (not in blender script) because blender's python 
    environment has minimal external packages and doesn't include point_cloud_utils.
    
    Uses consistent point sampling: samples points from the first frame and interpolates 
    corresponding positions on all other frames for temporal consistency.
    
    Returns:
        str: Path to directory containing data for GIF creation (either sampled or original)
    """
    try:
        import point_cloud_utils as pcu
        import numpy as np
        import glob
        import shutil
        
        points_to_sample = 2048
        
        print(f"Applying consistent mesh surface sampling to generate {points_to_sample} points...")
        
        # Get all vertex and face files
        vertex_files = sorted(glob.glob(os.path.join(mesh_nodes_dir, "frame_*_vertices.npy")))
        face_files = sorted(glob.glob(os.path.join(mesh_nodes_dir, "frame_*_faces.npy")))
        
        if not vertex_files or not face_files:
            print("No vertex or face files found for mesh surface sampling")
            return mesh_nodes_dir
        
        if len(vertex_files) != len(face_files):
            print("Mismatch between number of vertex and face files")
            return mesh_nodes_dir
        
        # Load first frame to determine consistent sampling points
        first_frame_vertices = np.load(vertex_files[0])
        first_frame_faces = np.load(face_files[0])
        print(f"Original mesh: {len(first_frame_vertices)} vertices, {len(first_frame_faces)} faces")
        
        # Sample points from the first frame to get consistent barycentric coordinates
        print("Generating consistent sampling pattern from first frame...")
        fid, bc = pcu.sample_mesh_random(first_frame_vertices, first_frame_faces, points_to_sample)
        print(f"Sampled {len(fid)} face indices with barycentric coordinates")
        
        # Create sampled directory
        sampled_dir = os.path.join(output_subdir, "mesh_nodes_sampled")
        os.makedirs(sampled_dir, exist_ok=True)
        
        # Apply the same barycentric coordinates to all frames for consistency
        print("Applying consistent sampling to all frames...")
        for i, (vertex_file, face_file) in enumerate(zip(vertex_files, face_files)):
            vertices = np.load(vertex_file)  # [n, 3]
            faces = np.load(face_file)       # [m, 3]
            
            # Use the same face indices and barycentric coordinates from first frame
            # This ensures the same surface points are tracked across all frames
            sampled_positions = pcu.interpolate_barycentric_coords(faces, fid, bc, vertices)
            
            # Save sampled positions
            sampled_filename = f"frame_{i:04d}_vertices.npy"
            sampled_path = os.path.join(sampled_dir, sampled_filename)
            np.save(sampled_path, sampled_positions)
            
            if i == 0:
                print(f"Frame {i}: Sampled {len(sampled_positions)} consistent points")
            elif i % 5 == 0:  # Print progress every 5 frames
                print(f"Frame {i}: Applied consistent sampling")
        
        # Copy metadata to sampled directory
        metadata_src = os.path.join(mesh_nodes_dir, "metadata.json")
        metadata_dst = os.path.join(sampled_dir, "metadata.json")
        if os.path.exists(metadata_src):
            shutil.copy2(metadata_src, metadata_dst)
            
            # Update metadata with new vertex count
            with open(metadata_dst, 'r') as f:
                metadata = json.load(f)
            metadata['num_vertices'] = points_to_sample
            metadata['mesh_surface_sampled'] = True
            metadata['consistent_sampling'] = True
            metadata['original_vertices'] = len(first_frame_vertices)
            metadata['original_faces'] = len(first_frame_faces)
            with open(metadata_dst, 'w') as f:
                json.dump(metadata, f, indent=2)
        
        print(f"Using consistent mesh surface sampled points ({points_to_sample}) for GIF creation")
        return sampled_dir
        
    except ImportError:
        print("Warning: point_cloud_utils not available, using original mesh for GIF creation")
        return mesh_nodes_dir
    except Exception as e:
        print(f"Error during mesh surface sampling: {e}")
        print("Using original mesh for GIF creation")
        return mesh_nodes_dir

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
    parser.add_argument(
        "--create_gif",
        action="store_true",
        help="Create animated GIF from extracted mesh data"
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
            
            # Create output directory for this combination - new structure: {Motion}/{Object}
            motion_dir = os.path.join(args.output_dir, motion_name)
            output_subdir = os.path.join(motion_dir, target_name)
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
                    timeout=10 * 60,  # 10 minutes timeout
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=os.path.dirname(os.path.abspath(__file__))  # Run from script directory
                )
                print(res.stdout.decode("utf-8"))
                
                if res.returncode != 0:
                    print(f"Warning: Command failed with return code {res.returncode}")
                    continue
                
                # Create GIF if requested and extraction was successful
                if args.create_gif:
                    mesh_nodes_dir = os.path.join(output_subdir, "mesh_nodes")
                    if not os.path.exists(mesh_nodes_dir):
                        print(f"Mesh nodes directory not found, skipping GIF creation for {motion_name}/{target_name}")
                        continue
                    
                    # Apply mesh surface sampling to generate uniform point clouds before GIF creation
                    gif_input_dir = apply_fps_sampling_and_prepare_gif(mesh_nodes_dir, output_subdir, target_name, motion_name)
                    
                    # Create GIF using the appropriate directory (sampled or original)
                    gif_filename = f"{motion_name}_{target_name}_animation.gif"
                    gif_path = os.path.join(output_subdir, gif_filename)
                    print(f"Creating GIF animation: {gif_filename}")
                    success = create_animation_gif(gif_input_dir, gif_path, interval=400)
                    if not success:
                        print(f"Failed to create GIF for {motion_name}/{target_name}")
                
            except subprocess.TimeoutExpired:
                print('Timeout, continuing to next combination...')
                
    print("\nAll combinations processed!")
