import bpy
import os
import sys
import math
import mathutils
import json

# Required for external pip installed packages, as they arent installed by default into blender python site-packages rather into the user's site-packages. And trying to install into the correct blender site-packages results in READ ONLY ERRORS.
user_site_packages = os.path.expanduser("~/.local/lib/python3.11/site-packages")
if user_site_packages not in sys.path:
    sys.path.insert(0, user_site_packages)

import imageio  # New import for creating videos
from PIL import Image, ImageDraw  # For adding white background to transparent images
import tempfile  # Import for temporary file handling
import numpy as np
import argparse


# Function to load an FBX file
def load_fbx(filepath):
    print(f"Loading FBX: {filepath}")
    bpy.ops.import_scene.fbx(filepath=filepath)
    loaded_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE']
    if not loaded_objects:
        raise ValueError(f"No armature found in FBX: {filepath}")
    print(f"Loaded armature: {loaded_objects[-1].name}")
    return loaded_objects[-1]

# Function to standardize bone names
def standardize_bone_names(source_armature, target_armature):
    print("Standardizing bone names...")
    source_bones = [bone.name for bone in source_armature.data.bones]
    source_prefix = source_bones[0].split(':')[0]

    for bone in target_armature.data.bones:
        if ':' in bone.name:
            suffix = bone.name.split(':')[1]  # Extract the suffix
            new_name = f"{source_prefix}:{suffix}"
            print(f"Renaming '{bone.name}' to '{new_name}'")
            bone.name = new_name
    print("Bone names standardized.")

# Function to transfer animation from one armature to another
def transfer_animation(source_armature, target_armature):
    print("Transferring animation...")

    bpy.context.view_layer.objects.active = source_armature
    target_armature.select_set(True)
    bpy.ops.object.make_links_data(type='ANIMATION')

    # target_armature.animation_data_create()
    # target_armature.animation_data.action = source_armature.animation_data.action
    print(f"Animation transferred from '{source_armature.name}' to '{target_armature.name}'.")

# Function to set the frame range
def set_frame_range(start_frame, end_frame, animation_armature):
    action = animation_armature.animation_data.action 
    print("Setting frame range...")
    if start_frame == 0:
        start_frame = int(action.frame_range[0])

    # If end_frame is -1, use the action's last frame
    if end_frame == -1:
        end_frame = int(action.frame_range[1])
        
    bpy.context.scene.frame_start = start_frame
    bpy.context.scene.frame_end = end_frame
    print(f"Frame range set: {bpy.context.scene.frame_start} - {bpy.context.scene.frame_end}.")

# Function to set up the camera
def setup_camera(location, target):
    print("Setting up camera...")
    if "Camera" not in bpy.data.objects:
        bpy.ops.object.camera_add(location=location)
        camera = bpy.context.active_object
        camera.name = "Camera"
    else:
        camera = bpy.data.objects["Camera"]
        camera.location = location

    # Make the camera point at the target
    direction = target.location - camera.location
    camera.rotation_mode = 'XYZ'
    camera.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    print(f"Camera positioned at {camera.location} and oriented toward the target.")
    return camera

# Function to set render settings
def set_render_settings(output_path):
    print("Configuring render settings...")
    scene = bpy.context.scene
    # Set image format to PNG (supports transparency)
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'  # Enable alpha channel for transparency
    scene.render.film_transparent = True  # Keep transparent background
    # Set resolution and FPS
    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y
    scene.render.fps = fps
    scene.view_settings.exposure = exposure
    # Set output path
    scene.render.filepath = output_path
    print(f"Render output set to {output_path}")

# Function to render the animation
def render_animation(start_frame, end_frame):
    print("Rendering animation...")

    jj = 1
    frames_to_render = np.linspace(start_frame, end_frame, num=frames_n).astype(int)
    print(frames_to_render)
    base_path = bpy.context.scene.render.filepath  # The folder you originally set

    for f in frames_to_render:
        # Ensure the base path ends with a slash
        if not base_path.endswith("/"):
            current_path = base_path + "/"
        else:
            current_path = base_path

        # Create the filename
        filename = f"{jj:04d}.png"  # Adjust extension based on your format settings
        full_path = current_path + filename

        # Set file path and render frame
        bpy.context.scene.render.filepath = full_path
        bpy.context.scene.frame_set(f)
        bpy.ops.render.render(write_still=True)

        # Print log message
        print(f"Saved frame {f} as {full_path}")

        jj += 1

    print("Rendering complete.")

#def render_animation(k,u):
#    print("Rendering full animation...")

#    # Ensure the output path is correctly formatted
#    base_path = bpy.context.scene.render.filepath
#    if not base_path.endswith("/"):
#        bpy.context.scene.render.filepath = base_path + "/"

#    # Set Blender to render the entire animation
#    bpy.ops.render.render(animation=True)

#    print("Rendering complete.")

# Function to render the first frame
def render_first_frame(output_path):
    print("Rendering the first frame...")
    bpy.context.scene.frame_set(bpy.context.scene.frame_start)
    bpy.ops.render.render(write_still=True)
    print(f"First frame saved to {output_path}")

# Function to center the object
def align_hips_to_ground(obj):
    for bone_name in obj.pose.bones.keys():
        if "Hips" in bone_name:
            hips_bone_name = bone_name
            break
    # Get the bone's world position before adjustment
    bone_world_z = (obj.matrix_world @ obj.pose.bones[hips_bone_name].head).z
    print(f"Current world Z position of '{hips_bone_name}': {bone_world_z}")

    # Move the object to align the bone's Z position to 0
    obj.location.z -= bone_world_z
    bpy.context.view_layer.update()

    # Verify the adjustment
    new_bone_world_z = (obj.matrix_world @ obj.pose.bones[hips_bone_name].head).z
    print(f"Adjusted world Z position of '{hips_bone_name}': {new_bone_world_z}")

    # Apply transforms to lock the new position
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

def align_legs_to_specific(obj, target_z=-1):
    # Identify the leg bones (adjust the names to match your armature)
    for bone_name in obj.pose.bones.keys():
        if "LeftToe_End" in bone_name:  # Replace with actual left leg bone name
            left_leg_bone_name = bone_name
        elif "RightToe_End" in bone_name:  # Replace with actual right leg bone name
            right_leg_bone_name = bone_name
    
    left_foot_world_z = (obj.matrix_world @ obj.pose.bones[left_leg_bone_name].head).z
    right_foot_world_z = (obj.matrix_world @ obj.pose.bones[right_leg_bone_name].head).z
    avg_foot_world_z = (left_foot_world_z + right_foot_world_z) / 2.0
    print(f"Current average world Z position of legs: {avg_foot_world_z}")
    
    # Calculate the offset needed to bring the average Z position to the target Z
    offset_z = target_z - avg_foot_world_z
    print(f"Calculated offset to target Z ({target_z}): {offset_z}")

    # Move the object to align the average Z position of the feet to the target Z
    obj.location.z += offset_z
    bpy.context.view_layer.update()
    
    # Verify the adjustment
    new_left_foot_world_z = (obj.matrix_world @ obj.pose.bones[left_leg_bone_name].head).z
    new_right_foot_world_z = (obj.matrix_world @ obj.pose.bones[right_leg_bone_name].head).z
    print(f"Adjusted world Z position of left leg: {new_left_foot_world_z}")
    print(f"Adjusted world Z position of right leg: {new_right_foot_world_z}")

    # Apply transforms to lock the new position
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    
def add_floor_plane(target_z=-1, size=10,texture_path=''):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, target_z))
    floor_plane = bpy.context.object  # The newly created plane
    floor_plane.name = "Floor_Plane"
    
    # Create a new material
    material = bpy.data.materials.new(name="Floor_Material")
    material.use_nodes = True  # Enable nodes for the material
    
    # Get the material's node tree
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    
    # Clear existing nodes
    for node in nodes:
        nodes.remove(node)
    
    # Create new nodes
    output_node = nodes.new(type="ShaderNodeOutputMaterial")
    output_node.location = (400, 0)
    
    principled_node = nodes.new(type="ShaderNodeBsdfPrincipled")
    principled_node.location = (0, 0)
    links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])
    
    if texture_path:
        # Add an image texture node if a texture path is provided
        texture_node = nodes.new(type="ShaderNodeTexImage")
        texture_node.location = (-400, 0)
        texture_node.image = bpy.data.images.load(texture_path)
        links.new(texture_node.outputs['Color'], principled_node.inputs['Base Color'])
        print(f"Texture applied from: {texture_path}")
    else:
        print("No texture path provided. Default material applied.")
    
    # Assign the material to the plane
    if len(floor_plane.data.materials) == 0:
        floor_plane.data.materials.append(material)
    else:
        floor_plane.data.materials[0] = material
    
    print(f"Floor plane created at Z = {target_z} with size {size}")

def remove_floor_plane(plane_name="Floor_Plane"):
    # Search for the plane object by name
    plane = bpy.data.objects.get(plane_name)
    if plane:
        # Delete the object from the scene
        bpy.data.objects.remove(plane, do_unlink=True)
        print(f"Removed plane: {plane_name}")
    else:
        print(f"No plane found with the name: {plane_name}")
        
# Function to clean up objects from the scene while preserving the camera
def clean_up_scene():
    print("Cleaning scene!")
    objects_to_delete = [obj for obj in bpy.context.scene.objects if obj.type != 'CAMERA']
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects_to_delete:
        obj.select_set(True)
    bpy.ops.object.delete()
    for block_type in ['meshes', 'armatures', 'materials', 'images', 'curves', 'lights']:
        collection = getattr(bpy.data, block_type)
        for block in collection:
            if block.users == 0:
                collection.remove(block)

# Function to add a white background to transparent images
def add_white_background(image_path):
    img = Image.open(image_path).convert("RGBA")
    background = Image.new("RGBA", img.size, (255, 255, 255, 255))
    combined = Image.alpha_composite(background, img)
    return combined.convert("RGB")

# Function to create video from frames
def create_video_from_frames(frame_dir, video_path, fps):
    print(f"Creating video from frames in {frame_dir}...")
    frames = sorted([os.path.join(frame_dir, f) for f in os.listdir(frame_dir) if f.endswith('.png')])

    if not frames:
        raise ValueError(f"No frames found in directory: {frame_dir}")

    print(f"Frames to be used: {frames}")
    print(f"Saving video to: {video_path}")

    with imageio.get_writer(video_path, fps=fps) as writer:
        for frame in frames:
            print(f"Processing frame: {frame}")
            # Add white background to transparent image
            img_with_bg = add_white_background(frame)

            # Save modified image to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                img_with_bg.save(temp_file.name)
                writer.append_data(imageio.imread(temp_file.name))

    print(f"Video successfully saved to {video_path}")

# Function to create a GIF from frames
def create_gif_from_frames(frame_dir, gif_path, fps):
    print(f"Creating GIF from frames in {frame_dir}...")
    frames = sorted([os.path.join(frame_dir, f) for f in os.listdir(frame_dir) if f.endswith('.png')])
    if not frames:
        raise ValueError(f"No frames found in directory: {frame_dir}")

    images = []
    for frame in frames:
        print(f"Processing frame for GIF: {frame}")
        img_with_bg = add_white_background(frame)
        images.append(img_with_bg)

    images[0].save(
        gif_path, save_all=True, append_images=images[1:], duration=int(1000 / fps), loop=0
    )
    print(f"GIF successfully saved to {gif_path}")

# Main function to orchestrate the process
def main(animation_fbx, object_fbx, output_path, num_angles):
    # Step 0: Clean up the scene
    clean_up_scene()

    # Step 1: Load the animation
    animation_armature = load_fbx(animation_fbx)

    # Step 2: Load the object
    object_armature = load_fbx(object_fbx)

    # Step 3: Standardize bone names
    # TODO: This should be a redundant step, as the bone names are already standardized in the FBX files. I kept it since the reference code had it, but it works without it.
    # standardize_bone_names(animation_armature, object_armature)

    # Step 4: Transfer the animation
    transfer_animation(animation_armature, object_armature)
    
#    align_hips_to_ground(object_armature)
    align_legs_to_specific(object_armature)
    
    # texture_path = "/home/yarinbekor/Desktop/THESIS/MT_Data/final_dataset/Supplementary/laminate_floor_03_diff_4k.jpg"
    add_floor_plane()  # Use default material instead of texture

    # Step 5: Set the frame range
    start_frame = motion_parameters[animation_name]['starting_frame']
    end_frame = motion_parameters[animation_name]['end_frame']

    set_frame_range(start_frame, end_frame, animation_armature)
#    set_frame_range(0, -1, animation_armature)

    # Step 6: Set up the camera and render for each angle
    angle_step = 360 / num_angles
    for i in range(num_angles):
        angle = math.radians(i * angle_step)
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        z = 0
        camera_location = mathutils.Vector((x, y, z))
        setup_camera(camera_location, object_armature)

        # Step 7: Configure render settings for frames
        normalized_angle = (i * angle_step + 180) % 360 - 90
        frame_output_path = f"{output_path}/{normalized_angle}/"
        os.makedirs(frame_output_path, exist_ok=True)
        set_render_settings(frame_output_path)

        # Step 8: Render the animation as frames
        render_animation(start_frame, end_frame)

        # Step 9: Create video from rendered frames
        video_output_path = os.path.join(output_path, f"{normalized_angle}.mp4")
        create_video_from_frames(frame_output_path, video_output_path, fps)

        # Step 10: Create GIF from rendered frames
        gif_output_path = os.path.join(output_path, f"{normalized_angle}.gif")
        create_gif_from_frames(frame_output_path, gif_output_path, fps)

    
    #remove plain
    remove_floor_plane()
    for i in range(num_angles):
        # Step 11: Save the first frame
        angle = math.radians(i * angle_step)
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        z = 0
        camera_location = mathutils.Vector((x, y, z))
        setup_camera(camera_location, object_armature)
        # Step 7: Configure render settings for frames
        normalized_angle = (i * angle_step + 180) % 360 - 90
        first_frame_dir = os.path.join(output_base_path, f"{object_name}_{animation_name}", "masks")
        os.makedirs(first_frame_dir, exist_ok=True)
        first_frame_path = os.path.join(first_frame_dir, f"{normalized_angle}.png")
        set_render_settings(first_frame_path)
        render_first_frame(first_frame_path)

# Run the main function
if __name__ == "__main__":
    # Parse command line arguments
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Render motion transfer videos")
    parser.add_argument("--animation_fbx", type=str, required=False, help="Path to animation FBX file", default="/home/gal/datasets/experiments/motion_transfer_3d/MixamoData/Yarin_raw/Motions/Clapping.fbx")
    parser.add_argument("--object_fbx", type=str, required=False, help="Path to target object FBX file", default="/home/gal/datasets/experiments/motion_transfer_3d/MixamoData/Yarin_raw/Objects/Eve.fbx")
    parser.add_argument("--motion_name", type=str, required=False, help="Name of the motion (for JSON lookup)",default="Clapping")
    parser.add_argument("--frames_n", type=int, default=14, help="Number of frames to sample")
    parser.add_argument("--output_path", type=str, required=False, help="Output directory path", default='./test_renders/debug')
    parser.add_argument("--frames_json", type=str, required=False, help="Path to frames JSON file", default='/home/gal/datasets/experiments/motion_transfer_3d/MixamoData/Yarin_raw/frames_cut_per_motion.json')
    
    
    args = parser.parse_args(argv)
    
    # Set global variables
    animation_fbx = args.animation_fbx
    object_fbx = args.object_fbx
    animation_name = args.motion_name
    frames_n = args.frames_n
    output_path = args.output_path
    
    # Load motion parameters from JSON
    if args.frames_json:
        frames_json_path = args.frames_json
    else:
        # Try to find frames JSON in the same directory as the motion file
        motion_dir = os.path.dirname(args.animation_fbx)
        base_dir = os.path.dirname(motion_dir)
        frames_json_path = os.path.join(base_dir, "frames_cut_per_motion.json")
    
    print(f"Loading motion parameters from: {frames_json_path}")
    with open(frames_json_path, 'r') as file:
        motion_parameters = json.load(file)
    
    # Verify motion exists in JSON
    if animation_name not in motion_parameters:
        raise ValueError(f"Motion '{animation_name}' not found in frames JSON")
    
    # Set render parameters
    num_angles = 16
    resolution_x = 520
    resolution_y = 520
    fps = 7
    radius = 8  # default radius
    exposure = 8  # default exposure
    
    # Output path setup
    output_base_path = output_path
    object_name = os.path.splitext(os.path.basename(object_fbx))[0]
    
    print(f"Processing: {animation_name} -> {object_name}")
    print(f"Frames: {motion_parameters[animation_name]['starting_frame']} to {motion_parameters[animation_name]['end_frame']}")
    print(f"Sampling {frames_n} frames")
    print(f"Output: {output_base_path}")
    
    # Run the main function
    main(animation_fbx, object_fbx, output_base_path, num_angles)
