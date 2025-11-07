"""Blender script to render human animation from OBJ sequence files."""

import argparse
import os
import re
import math
import sys

import bpy
from mathutils import Vector

# ----------------------- Utilities -----------------------
def natural_key(s):
    # sort like frame1, frame2, frame10...
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]

def purge_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for b in bpy.data.meshes: 
        if b.users == 0: 
            bpy.data.meshes.remove(b)
    for m in bpy.data.materials:
        if m.users == 0: 
            bpy.data.materials.remove(m)
    for w in bpy.data.worlds:
        if w.users == 0 and w.name != "World": 
            bpy.data.worlds.remove(w)

def get_scene_bbox(objects=None):
    """Calculate bounding box of given objects or all mesh objects in scene.
    
    Args:
        objects: List of objects to calculate bbox for, or None for all meshes
    
    Returns:
        Tuple[Vector, Vector]: (bbox_min, bbox_max)
    """
    if objects is None:
        objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    
    if not objects:
        return Vector((0, 0, 0)), Vector((0, 0, 0))
    
    bbox_min = Vector((math.inf, math.inf, math.inf))
    bbox_max = Vector((-math.inf, -math.inf, -math.inf))
    
    for obj in objects:
        for coord in obj.bound_box:
            coord = Vector(coord)
            coord = obj.matrix_world @ coord
            bbox_min = Vector((min(bbox_min.x, coord.x), min(bbox_min.y, coord.y), min(bbox_min.z, coord.z)))
            bbox_max = Vector((max(bbox_max.x, coord.x), max(bbox_max.y, coord.y), max(bbox_max.z, coord.z)))
    
    return bbox_min, bbox_max

def render_human_animation(
    obj_dir: str,
    file_prefix: str,
    fps: int,
    resolution: tuple,
    output_mp4: str,
    use_hdri: bool,
    hdri_path: str,
    cinematic_dolly: bool,
    max_frames: int = None,
) -> None:
    """Renders a human animation from OBJ sequence files.
    
    Args:
        obj_dir: Directory containing OBJ files
        file_prefix: Filename prefix (e.g., "frame")
        fps: Framerate
        resolution: (width, height) tuple
        output_mp4: Output MP4 file path
        use_hdri: Whether to use HDRI lighting
        hdri_path: Path to HDRI file (if use_hdri is True)
        cinematic_dolly: Whether to enable camera dolly
        max_frames: Maximum number of frames to process (None for all)
    """
    print(f"[Blender Script] Starting render_human_animation function")
    print(f"[Blender Script] Parameters: obj_dir={obj_dir}, prefix={file_prefix}, fps={fps}, resolution={resolution}, max_frames={max_frames}")
    
    # ----------------------- Start fresh ----------------------
    print(f"[Blender Script] Purging scene...")
    purge_scene()
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'GPU'
    # Set view layer pass vector if available (not essential)
    try:
        scene.view_layers[0].use_pass_vector = True
    except:
        pass
    scene.render.film_transparent = False
    scene.frame_current = 1
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    print(f"[Blender Script] Scene settings configured: engine=CYCLES, resolution={resolution[0]}x{resolution[1]}, fps={fps}")

    # Color management (cinematic/friendly contrast)
    scene.view_settings.view_transform = 'Filmic'
    scene.view_settings.look = 'Medium Contrast'

    # ----------------------- Import sequence ------------------
    print(f"[Blender Script] Looking for OBJ files in: {obj_dir}")
    if not os.path.isdir(obj_dir):
        raise ValueError(f"Folder not found: {obj_dir}")
    
    files = [f for f in os.listdir(obj_dir) if f.lower().endswith(".obj") and f.startswith(file_prefix)]
    if not files:
        raise ValueError(f"No OBJ files matching {file_prefix}*.obj in {obj_dir}")

    files.sort(key=natural_key)
    
    # Truncate to max_frames if specified
    if max_frames is not None and max_frames > 0:
        files = files[:max_frames]
        print(f"[Blender Script] Truncating to first {max_frames} frames for debugging")
    
    n_frames = len(files)
    scene.frame_start = 1
    scene.frame_end = n_frames
    print(f"[Blender Script] Found {n_frames} OBJ files to import (frames {scene.frame_start} to {scene.frame_end})")

    seq_coll = bpy.data.collections.new("OBJ_Sequence")
    bpy.context.scene.collection.children.link(seq_coll)

    imported_objects = []

    print(f"[Blender Script] Starting to import {n_frames} OBJ files...")
    for i, fname in enumerate(files, start=1):  # frames start at 1
        if i % 50 == 0 or i == 1 or i == n_frames:
            print(f"[Blender Script] Importing frame {i}/{n_frames}: {fname}")
        path = os.path.join(obj_dir, fname)
        # Use the same import function as reference code
        bpy.ops.wm.obj_import(filepath=path)
        # Grab imported objects (can be multiple if OBJ has groups). Join them.
        sel = [o for o in bpy.context.selected_objects if o.type == 'MESH']
        if not sel:
            continue
        if len(sel) > 1:
            bpy.ops.object.join()  # join into one mesh
            obj = bpy.context.active_object
        else:
            obj = sel[0]
        obj.name = f"motion_{i:04d}"
        # Put into collection
        for c in obj.users_collection:
            c.objects.unlink(obj)
        seq_coll.objects.link(obj)

        # Smooth shading & autosmooth for clean look
        bpy.ops.object.shade_smooth()
        # Set auto smooth (if available in this Blender version)
        try:
            obj.data.use_auto_smooth = True
            obj.data.auto_smooth_angle = math.radians(60)
        except AttributeError:
            # Auto smooth might not be available, just use smooth shading
            pass

        # Hide on all frames except its own
        obj.hide_viewport = True
        obj.hide_render = True
        obj.keyframe_insert("hide_viewport", frame=max(1, i-1))
        obj.keyframe_insert("hide_render", frame=max(1, i-1))

        obj.hide_viewport = False
        obj.hide_render = False
        obj.keyframe_insert("hide_viewport", frame=i)
        obj.keyframe_insert("hide_render", frame=i)

        obj.hide_viewport = True
        obj.hide_render = True
        obj.keyframe_insert("hide_viewport", frame=i+1)
        obj.keyframe_insert("hide_render", frame=i+1)

        imported_objects.append(obj)

    print(f"[Blender Script] Successfully imported {len(imported_objects)} objects")
    
    # ----------------------- Single material ------------------
    print(f"[Blender Script] Creating material...")
    # Create a pleasing principled material (skin-ish but generic)
    mat = bpy.data.materials.new("BodyMat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for n in list(nodes):
        if n.type not in {'OUTPUT_MATERIAL'}:
            nodes.remove(n)

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.63, 0.49, 0.42, 1.0)  # warm neutral
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.55
    # Set subsurface if available (might have different name in different Blender versions)
    try:
        bsdf.inputs["Subsurface"].default_value = 0.25
        bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.5, 0.25)
    except KeyError:
        # Try alternative name
        try:
            bsdf.inputs["Subsurface Weight"].default_value = 0.25
            bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.5, 0.25)
        except KeyError:
            # Subsurface not available in this Blender version, skip it
            pass

    out = nodes["Material Output"]
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    for obj in imported_objects:
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
    print(f"[Blender Script] Material applied to {len(imported_objects)} objects")

    # ----------------------- Lighting / World -----------------
    print(f"[Blender Script] Setting up lighting...")
    if use_hdri and hdri_path and os.path.isfile(hdri_path):
        world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
        scene.world = world
        world.use_nodes = True
        wnodes = world.node_tree.nodes
        wlinks = world.node_tree.links
        wnodes.clear()
        w_output = wnodes.new("ShaderNodeOutputWorld")
        w_bg = wnodes.new("ShaderNodeBackground")
        w_env = wnodes.new("ShaderNodeTexEnvironment")
        w_env.image = bpy.data.images.load(hdri_path)
        w_bg.inputs["Strength"].default_value = 1.2
        wlinks.new(w_env.outputs["Color"], w_bg.inputs["Color"])
        wlinks.new(w_bg.outputs["Background"], w_output.inputs["Surface"])
    else:
        # Three-point light rig
        def add_light(name, type, energy, loc, rot):
            light_data = bpy.data.lights.new(name=name, type=type)
            light_data.energy = energy
            light = bpy.data.objects.new(name, light_data)
            scene.collection.objects.link(light)
            light.location = loc
            light.rotation_euler = rot
            return light
        add_light("Key",  'AREA', 1200, (3.0, -3.0, 3.0), (math.radians(55), 0, math.radians(35)))
        add_light("Fill", 'AREA', 400, (-3.0, -1.0, 2.0), (math.radians(70), 0, math.radians(-15)))
        add_light("Rim",  'SPOT', 1500, (0.0, 3.5, 2.5), (math.radians(200), 0, 0))
        print(f"[Blender Script] Three-point light rig created")

    # ----------------------- Ground plane (soft shadow) -------
    print(f"[Blender Script] Creating ground plane...")
    # Calculate bounding box to position floor at bottom of human
    # Update view layer to ensure transforms are applied
    bpy.context.view_layer.update()
    if imported_objects:
        bbox_min, bbox_max = get_scene_bbox(imported_objects)
        floor_z = bbox_min.z - 0.01  # Slightly below the bottom to ensure contact
        print(f"[Blender Script] Human bounding box: min=({bbox_min.x:.3f}, {bbox_min.y:.3f}, {bbox_min.z:.3f}), max=({bbox_max.x:.3f}, {bbox_max.y:.3f}, {bbox_max.z:.3f})")
        print(f"[Blender Script] Positioning floor at Z={floor_z:.3f}")
    else:
        floor_z = 0.0
        print(f"[Blender Script] No objects found, using default floor position Z=0")
    
    bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, floor_z))
    ground = bpy.context.active_object
    ground.name = "Ground"
    ground_mat = bpy.data.materials.new("GroundMat")
    ground_mat.use_nodes = True
    g_nodes = ground_mat.node_tree.nodes
    g_nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
    g_nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05,0.05,0.05,1)
    ground.data.materials.append(ground_mat)
    print(f"[Blender Script] Ground plane created")

    # ----------------------- Camera ---------------------------
    print(f"[Blender Script] Setting up camera...")
    # Delete default camera if it exists
    if "Camera" in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects["Camera"], do_unlink=True)
    
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.location = (2.2, -3.2, 1.8)
    cam.rotation_euler = (math.radians(70), 0, math.radians(35))
    cam.data.lens = 55  # mild tele look
    cam.data.dof.use_dof = True
    # Focus to average location of meshes
    if imported_objects:
        ref = imported_objects[min(1, len(imported_objects)-1)]
        cam.data.dof.focus_object = ref
        cam.data.dof.aperture_fstop = 4.0

    # Subtle dolly for production feel
    if cinematic_dolly:
        cam.keyframe_insert(data_path="location", frame=1)
        cam.keyframe_insert(data_path="rotation_euler", frame=1)
        cam.location = (2.0, -3.0, 1.75)
        cam.rotation_euler = (math.radians(69), 0, math.radians(33))
        cam.keyframe_insert(data_path="location", frame=n_frames)
        cam.keyframe_insert(data_path="rotation_euler", frame=n_frames)
        print(f"[Blender Script] Camera dolly animation enabled")
    print(f"[Blender Script] Camera configured")

    # ----------------------- Cycles / Denoising ----------------
    print(f"[Blender Script] Configuring Cycles render settings...")
    scene.cycles.samples = 256
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    # Set up GPU device (similar to reference code)
    try:
        bpy.context.preferences.addons["cycles"].preferences.get_devices()
        bpy.context.preferences.addons["cycles"].preferences.compute_device_type = "CUDA"  # or "OPENCL"
    except:
        pass
    # Try to set denoiser, but handle if OPTIX is not available
    try:
        if 'OPTIX' in bpy.context.preferences.addons['cycles'].preferences.compute_device_type:
            scene.cycles.denoiser = 'OPTIX'
        else:
            scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    except:
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'

    # ----------------------- Output (FFmpeg/H.264) -------------
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'HIGH'
    scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
    scene.render.ffmpeg.max_b_frames = 2
    scene.render.filepath = output_mp4

    print(f"[Blender Script] ========================================")
    print(f"[Blender Script] Setup complete!")
    print(f"[Blender Script] - Imported {n_frames} OBJ frames")
    print(f"[Blender Script] - Output: {output_mp4}")
    print(f"[Blender Script] - Resolution: {resolution[0]}x{resolution[1]}")
    print(f"[Blender Script] - FPS: {fps}")
    print(f"[Blender Script] - Frame range: {scene.frame_start} to {scene.frame_end}")
    print(f"[Blender Script] ========================================")
    print(f"[Blender Script] Starting animation render...")
    print(f"[Blender Script] This may take a while depending on resolution and frame count...")
    
    # Render with progress updates
    import time
    start_time = time.time()
    bpy.ops.render.render(animation=True)
    elapsed_time = time.time() - start_time
    
    print(f"[Blender Script] ========================================")
    print(f"[Blender Script] Render complete!")
    print(f"[Blender Script] Total render time: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")
    print(f"[Blender Script] Output saved to: {output_mp4}")
    print(f"[Blender Script] ========================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render human animation from OBJ sequence files.")
    parser.add_argument(
        "--obj_dir",
        type=str,
        required=True,
        help="Directory containing OBJ files (e.g., frame000.obj, frame001.obj, ...)."
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
        default=False,
        help="Enable slow camera push-in."
    )
    parser.add_argument(
        "--max_frames",
        type=int,
        default=None,
        help="Maximum number of frames to process (for debugging/testing). If None, processes all frames."
    )
    
    # Parse arguments after -- separator (like reference code)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(argv)
    
    print(f"[Blender Script] ========================================")
    print(f"[Blender Script] Blender script started")
    print(f"[Blender Script] Arguments received: {args}")
    print(f"[Blender Script] ========================================")

    render_human_animation(
        obj_dir=args.obj_dir,
        file_prefix=args.file_prefix,
        fps=args.fps,
        resolution=tuple(args.resolution),
        output_mp4=args.output_mp4,
        use_hdri=args.use_hdri,
        hdri_path=args.hdri_path,
        cinematic_dolly=args.cinematic_dolly,
        max_frames=args.max_frames,
    )
