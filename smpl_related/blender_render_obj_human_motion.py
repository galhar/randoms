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

def calculate_motion_bbox(imported_objects, scene, frame_start, frame_end, frame_step=1):
    """Calculate the bounding box that encompasses the entire motion across all frames.
    
    This function iterates through all frames and calculates the union of all bounding boxes
    to determine the full extent of the human's movement in space.
    
    Args:
        imported_objects: List of imported mesh objects (one per frame
        scene: Blender scene object
        frame_start: Starting frame number
        frame_end: Ending frame number
        frame_step: Step between frames (default: 1)
    
    Returns:
        Tuple[Vector, Vector, Vector]: (bbox_min, bbox_max, bbox_center)
    """
    print(f"[Blender Script] Calculating motion bounding box across frames {frame_start} to {frame_end}...")
    
    motion_bbox_min = Vector((math.inf, math.inf, math.inf))
    motion_bbox_max = Vector((-math.inf, -math.inf, -math.inf))
    
    # Store original frame
    original_frame = scene.frame_current
    
    # Iterate through all frames to find the full extent of motion
    for frame in range(frame_start, frame_end + 1, frame_step):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        
        # Get visible objects at this frame (objects that are not hidden)
        visible_objects = [obj for obj in imported_objects if not obj.hide_render]
        
        if visible_objects:
            frame_bbox_min, frame_bbox_max = get_scene_bbox(visible_objects)
            
            # Update overall motion bbox
            motion_bbox_min = Vector((
                min(motion_bbox_min.x, frame_bbox_min.x),
                min(motion_bbox_min.y, frame_bbox_min.y),
                min(motion_bbox_min.z, frame_bbox_min.z)
            ))
            motion_bbox_max = Vector((
                max(motion_bbox_max.x, frame_bbox_max.x),
                max(motion_bbox_max.y, frame_bbox_max.y),
                max(motion_bbox_max.z, frame_bbox_max.z)
            ))
    
    # Restore original frame
    scene.frame_set(original_frame)
    bpy.context.view_layer.update()
    
    # Calculate center
    bbox_center = (motion_bbox_min + motion_bbox_max) / 2
    
    print(f"[Blender Script] Motion bbox: min=({motion_bbox_min.x:.3f}, {motion_bbox_min.y:.3f}, {motion_bbox_min.z:.3f}), "
          f"max=({motion_bbox_max.x:.3f}, {motion_bbox_max.y:.3f}, {motion_bbox_max.z:.3f}), "
          f"center=({bbox_center.x:.3f}, {bbox_center.y:.3f}, {bbox_center.z:.3f})")
    
    return motion_bbox_min, motion_bbox_max, bbox_center

def get_evenly_spaced_indices(total_frames: int, n_frames: int) -> list:
    """Get N evenly-spaced frame indices from total frames.
    
    Args:
        total_frames: Total number of frames available
        n_frames: Number of frames to select
    
    Returns:
        List of frame indices (0-based)
    """
    if n_frames >= total_frames:
        return list(range(total_frames))
    if n_frames <= 1:
        return [0]
    
    step = (total_frames - 1) / (n_frames - 1)
    indices = [int(round(i * step)) for i in range(n_frames)]
    # Ensure we don't exceed bounds
    indices = [min(idx, total_frames - 1) for idx in indices]
    return indices

def apply_gradient_colors(objects: list, start_color: tuple = (0.2, 0.4, 0.8, 1.0), end_color: tuple = (0.8, 0.4, 0.2, 1.0)):
    """Apply gradually alternating colors to a list of objects.
    
    Args:
        objects: List of mesh objects
        start_color: Starting color (RGBA tuple, 0-1 range)
        end_color: Ending color (RGBA tuple, 0-1 range)
    """
    n_objects = len(objects)
    if n_objects == 0:
        return
    
    for i, obj in enumerate(objects):
        # Calculate interpolation factor
        t = i / (n_objects - 1) if n_objects > 1 else 0
        
        # Interpolate color
        color = tuple(
            start_color[j] * (1 - t) + end_color[j] * t
            for j in range(4)
        )
        
        # Create material for this object
        mat = bpy.data.materials.new(name=f"GradientMat_{i:04d}")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        
        # Clear default nodes except output
        for n in list(nodes):
            if n.type not in {'OUTPUT_MATERIAL'}:
                nodes.remove(n)
        
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Metallic"].default_value = 0.0
        bsdf.inputs["Roughness"].default_value = 0.55
        
        out = nodes["Material Output"]
        links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        
        # Apply material to object
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)

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
    composite_frames: int = None,
    separate: bool = False,
) -> None:
    """Renders a human animation from OBJ sequence files.
    
    Args:
        obj_dir: Directory containing OBJ files
        file_prefix: Filename prefix (e.g., "frame")
        fps: Framerate
        resolution: (width, height) tuple
        output_mp4: Output MP4 file path (or PNG if composite mode)
        use_hdri: Whether to use HDRI lighting
        hdri_path: Path to HDRI file (if use_hdri is True)
        cinematic_dolly: Whether to enable camera dolly
        max_frames: Maximum number of frames to process (None for all)
        composite_frames: If set, creates static composite with N evenly-spaced frames
    """
    is_composite_mode = composite_frames is not None and composite_frames > 0
    is_separate_mode = is_composite_mode and separate
    print(f"[Blender Script] Starting render_human_animation function")
    print(f"[Blender Script] Parameters: obj_dir={obj_dir}, prefix={file_prefix}, fps={fps}, resolution={resolution}, max_frames={max_frames}, composite_frames={composite_frames}, separate={separate}")
    if is_composite_mode:
        if is_separate_mode:
            print(f"[Blender Script] SEPARATE MODE: Will create static image with {composite_frames} evenly-spaced frames placed on floor in equally spaced regions")
        else:
            print(f"[Blender Script] COMPOSITE MODE: Will create static image with {composite_frames} evenly-spaced frames")
    
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
    
    # Handle composite mode: select evenly-spaced frames
    if is_composite_mode:
        total_files = len(files)
        # Truncate to max_frames first if specified
        if max_frames is not None and max_frames > 0:
            total_files = min(total_files, max_frames)
        
        # Get evenly-spaced indices
        selected_indices = get_evenly_spaced_indices(total_files, composite_frames)
        selected_files = [files[i] for i in selected_indices]
        files = selected_files
        print(f"[Blender Script] Composite mode: Selected {len(files)} evenly-spaced frames from {total_files} total frames")
        print(f"[Blender Script] Selected frame indices: {selected_indices}")
    else:
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

        # In composite mode, keep all objects visible
        # In animation mode, hide on all frames except its own
        if is_composite_mode:
            obj.hide_viewport = False
            obj.hide_render = False
        else:
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
    
    # ----------------------- Materials ------------------
    if is_composite_mode:
        # Apply gradient colors in composite mode
        # All orange with increasing brightness
        print(f"[Blender Script] Applying gradient colors to {len(imported_objects)} objects...")
        apply_gradient_colors(
            imported_objects,
            start_color=(0.2, 0.1, 0.0, 1.0),   # Very dark orange (increased range)
            end_color=(1.0, 0.6, 0.2, 1.0)      # Bright orange
        )
        print(f"[Blender Script] Gradient colors applied (orange with increasing brightness)")
    else:
        # Single material for animation mode
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
        bsdf.inputs["Base Color"].default_value = (0.4, 0.2, 0.0, 1.0)  # Dark orange (same as composite mode start color)
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

    # ----------------------- Separate Mode: Reposition objects on floor -----------------
    if is_separate_mode:
        print(f"[Blender Script] SEPARATE MODE: Repositioning {len(imported_objects)} objects on floor...")
        
        # First, calculate local bounding box for each object and find the lowest Z
        object_local_centers = []
        object_local_bboxes = []
        lowest_z = math.inf
        
        for obj in imported_objects:
            # Calculate local bounding box (relative to object's origin)
            bbox_min = Vector((math.inf, math.inf, math.inf))
            bbox_max = Vector((-math.inf, -math.inf, -math.inf))
            
            for coord in obj.bound_box:
                coord = Vector(coord)
                # Transform to world space
                world_coord = obj.matrix_world @ coord
                bbox_min = Vector((min(bbox_min.x, world_coord.x), min(bbox_min.y, world_coord.y), min(bbox_min.z, world_coord.z)))
                bbox_max = Vector((max(bbox_max.x, world_coord.x), max(bbox_max.y, world_coord.y), max(bbox_max.z, world_coord.z)))
            
            # Calculate local center (world space center of this object)
            local_center = (bbox_min + bbox_max) / 2
            object_local_centers.append(local_center)
            object_local_bboxes.append((bbox_min, bbox_max))
            
            # Track lowest Z across all objects
            lowest_z = min(lowest_z, bbox_min.z)
        
        floor_z = lowest_z
        print(f"[Blender Script] Floor level determined: z={floor_z:.3f}")
        
        # Calculate spacing for equally spaced positions
        n_objects = len(imported_objects)
        if n_objects == 1:
            spacing = 2.0  # Default spacing for single object
        else:
            # Estimate spacing based on average object size
            avg_size = 0.0
            for bbox_min, bbox_max in object_local_bboxes:
                size = max(bbox_max.x - bbox_min.x, bbox_max.y - bbox_min.y)
                avg_size += size
            avg_size /= n_objects
            spacing = max(avg_size * 1.0, 1.0)  # Closer spacing: multiplier 1.0, minimum 1.0 units
        
        # Arrange objects in a line along X axis, equally spaced
        total_width = spacing * (n_objects - 1) if n_objects > 1 else spacing
        start_x = -total_width / 2
        
        # Reposition each object
        for i, obj in enumerate(imported_objects):
            # Get the object's current local center
            current_center = object_local_centers[i]
            
            # Calculate target position: equally spaced along X axis
            target_x = start_x + i * spacing if n_objects > 1 else 0.0
            target_y = 0.0  # Center on Y axis
            # Preserve original height relative to floor (don't center on floor)
            target_z = current_center.z  # Keep original Z position
            
            # Calculate offset needed to move object to target position (only X and Y change)
            offset = Vector((target_x, target_y, 0.0)) - Vector((current_center.x, current_center.y, 0.0))
            
            # Apply offset to object location (only X and Y change, Z stays the same)
            obj.location = obj.location + offset
            
            print(f"[Blender Script] Object {i+1}/{n_objects} repositioned: center moved from ({current_center.x:.3f}, {current_center.y:.3f}, {current_center.z:.3f}) to ({target_x:.3f}, {target_y:.3f}, {current_center.z:.3f}) [height preserved]")
        
        print(f"[Blender Script] SEPARATE MODE: All objects repositioned on floor with spacing={spacing:.3f}")
        
        # Update view layer to reflect new positions
        bpy.context.view_layer.update()

    # ----------------------- Lighting / World -----------------
    print(f"[Blender Script] Setting up lighting...")
    
    # Set up world with white background
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    wnodes = world.node_tree.nodes
    wlinks = world.node_tree.links
    wnodes.clear()
    w_output = wnodes.new("ShaderNodeOutputWorld")
    w_bg = wnodes.new("ShaderNodeBackground")
    
    if use_hdri and hdri_path and os.path.isfile(hdri_path):
        w_env = wnodes.new("ShaderNodeTexEnvironment")
        w_env.image = bpy.data.images.load(hdri_path)
        w_bg.inputs["Strength"].default_value = 1.2
        wlinks.new(w_env.outputs["Color"], w_bg.inputs["Color"])
        wlinks.new(w_bg.outputs["Background"], w_output.inputs["Surface"])
        print(f"[Blender Script] HDRI lighting enabled")
    else:
        # White background
        w_bg.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)  # White
        w_bg.inputs["Strength"].default_value = 1.0
        wlinks.new(w_bg.outputs["Background"], w_output.inputs["Surface"])
        print(f"[Blender Script] White background set")
        
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

    # ----------------------- Calculate motion bounding box ------------------
    # Calculate the full extent of human motion across all frames
    # In separate mode, this will reflect the new positions after repositioning
    motion_bbox_min = None
    motion_bbox_max = None
    motion_bbox_center = None
    
    if imported_objects:
        # Update view layer to ensure all transformations are applied
        bpy.context.view_layer.update()
        motion_bbox_min, motion_bbox_max, motion_bbox_center = calculate_motion_bbox(
            imported_objects, scene, scene.frame_start, scene.frame_end, scene.frame_step
        )
    
    # ----------------------- Ground plane (soft shadow) -------
    print(f"[Blender Script] Creating ground plane...")
    if motion_bbox_min is not None:
        # Calculate floor size to cover motion area with padding
        motion_size_x = motion_bbox_max.x - motion_bbox_min.x
        motion_size_y = motion_bbox_max.y - motion_bbox_min.y
        padding = 0.5  # Add 0.5 units padding on each side
        floor_size_x = motion_size_x + 2 * padding
        floor_size_y = motion_size_y + 2 * padding
        
        # Position floor exactly at the lowest point of the feet
        floor_z = motion_bbox_min.z
        floor_center_x = (motion_bbox_min.x + motion_bbox_max.x) / 2
        floor_center_y = (motion_bbox_min.y + motion_bbox_max.y) / 2
        
        print(f"[Blender Script] Floor size: {floor_size_x:.3f} x {floor_size_y:.3f}, center=({floor_center_x:.3f}, {floor_center_y:.3f}, {floor_z:.3f})")
        
        # Create floor plane with calculated size and position
        # Use the larger dimension as base size, then scale
        base_size = max(floor_size_x, floor_size_y)
        bpy.ops.mesh.primitive_plane_add(size=base_size, location=(floor_center_x, floor_center_y, floor_z))
        ground = bpy.context.active_object
        ground.name = "Ground"
        # Scale to match exact rectangular dimensions
        if base_size > 0:
            ground.scale = (floor_size_x / base_size, floor_size_y / base_size, 1.0)
    else:
        # Fallback to default
        floor_z = 0.0
        bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, floor_z))
        ground = bpy.context.active_object
        ground.name = "Ground"
        print(f"[Blender Script] No objects found, using default floor")
    
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
    
    if motion_bbox_min is not None and motion_bbox_max is not None and imported_objects:
        if is_separate_mode:
            # Separate mode: objects are arranged in a line along X axis
            # Position camera to see all poses from a good angle
            
            # Calculate the extent of all separated objects
            motion_size = Vector((
                motion_bbox_max.x - motion_bbox_min.x,
                motion_bbox_max.y - motion_bbox_min.y,
                motion_bbox_max.z - motion_bbox_min.z
            ))
            
            # Camera should be positioned to see the entire line of objects
            # Position at an angle: more in front, less to the side, and farther away
            camera_distance = max(motion_size.x * 1.2, 4.5)  # Farther distance based on width, minimum 4.5 units
            camera_height = motion_bbox_center.z + motion_size.z * 0.3  # Slightly elevated to see poses clearly
            
            # Position camera: less to the side, more in front (but a bit backward)
            cam_x = motion_bbox_center.x + camera_distance * 0.3  # Less to the right side
            cam_y = motion_bbox_center.y - camera_distance * 0.9  # A bit backward from previous position
            cam_z = camera_height
            
            cam.location = (cam_x, cam_y, cam_z)
            
            # Point camera at the center of all separated objects
            direction = motion_bbox_center - cam.location
            rot_quat = direction.to_track_quat("-Z", "Y")
            cam.rotation_euler = rot_quat.to_euler()
            
            cam.data.lens = 35  # Standard lens
            cam.data.dof.use_dof = True
            cam.data.dof.focus_distance = direction.length
            cam.data.dof.aperture_fstop = 4.0
            
            print(f"[Blender Script] SEPARATE MODE: Camera positioned at ({cam_x:.3f}, {cam_y:.3f}, {cam_z:.3f})")
            print(f"[Blender Script] Camera pointing at center ({motion_bbox_center.x:.3f}, {motion_bbox_center.y:.3f}, {motion_bbox_center.z:.3f})")
        else:
            # Normal composite or animation mode
            # Use motion center (like composite mode) to see entire motion
            # This ensures the camera can see the person throughout the entire walking motion
            
            # Calculate motion size for camera distance
            motion_size = Vector((
                motion_bbox_max.x - motion_bbox_min.x,
                motion_bbox_max.y - motion_bbox_min.y,
                motion_bbox_max.z - motion_bbox_min.z
            ))
            diagonal_size = math.sqrt(motion_size.x**2 + motion_size.y**2 + motion_size.z**2)
            
            # Position camera on the side, slightly angled to see the front
            # Camera should be mostly on the side but with a slight front angle
            camera_distance = diagonal_size * 1.5  # Distance to see entire motion
            camera_height = motion_bbox_center.z + motion_size.z * 0.3  # Slightly elevated
            
            # Position camera on the side (positive X) with slight front angle
            # Mostly side view, but slightly forward to see the front
            side_offset = camera_distance * 0.8  # Mostly to the side
            front_offset = camera_distance * 0.3  # Slight front angle
            cam_x = motion_bbox_center.x + side_offset  # To the right side
            cam_y = motion_bbox_min.y - front_offset  # Slightly in front (negative Y)
            cam_z = camera_height
            
            cam.location = (cam_x, cam_y, cam_z)
            
            # Point camera at motion center (not just starting position)
            direction = motion_bbox_center - cam.location
            rot_quat = direction.to_track_quat("-Z", "Y")
            cam.rotation_euler = rot_quat.to_euler()
            
            cam.data.lens = 35  # Standard lens
            cam.data.dof.use_dof = True
            cam.data.dof.focus_distance = direction.length
            cam.data.dof.aperture_fstop = 4.0
            
            print(f"[Blender Script] Camera positioned at ({cam_x:.3f}, {cam_y:.3f}, {cam_z:.3f})")
            print(f"[Blender Script] Camera pointing at motion center ({motion_bbox_center.x:.3f}, {motion_bbox_center.y:.3f}, {motion_bbox_center.z:.3f})")
        
        print(f"[Blender Script] Camera is STATIC (no movement during animation)")
    else:
        # Fallback to default camera position
        cam.location = (0, -3, 1.5)
        cam.rotation_euler = (math.radians(70), 0, 0)
        cam.data.lens = 35
        cam.data.dof.use_dof = True
        if imported_objects:
            ref = imported_objects[min(1, len(imported_objects)-1)]
            cam.data.dof.focus_object = ref
            cam.data.dof.aperture_fstop = 4.0
    
    # Ensure camera is static - no keyframes
    # Remove any existing animation data
    if cam.animation_data:
        cam.animation_data_clear()
    
    print(f"[Blender Script] Camera configured (static)")

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

    # ----------------------- Output -----------------------------
    if is_composite_mode:
        # Composite mode: render single PNG frame
        output_path = output_mp4
        # Change extension to PNG if it's MP4
        if output_path.lower().endswith('.mp4'):
            output_path = output_path[:-4] + '.png'
        
        scene.render.image_settings.file_format = 'PNG'
        scene.render.image_settings.color_mode = 'RGBA'
        scene.render.filepath = output_path
        
        print(f"[Blender Script] ========================================")
        print(f"[Blender Script] Setup complete!")
        print(f"[Blender Script] - Imported {len(imported_objects)} OBJ frames (composite mode)")
        print(f"[Blender Script] - Output: {output_path}")
        print(f"[Blender Script] - Resolution: {resolution[0]}x{resolution[1]}")
        print(f"[Blender Script] - All frames visible with gradient colors")
        print(f"[Blender Script] ========================================")
        print(f"[Blender Script] Starting single frame render...")
        
        # Render single frame
        import time
        start_time = time.time()
        scene.frame_set(1)
        bpy.ops.render.render(write_still=True)
        elapsed_time = time.time() - start_time
        
        print(f"[Blender Script] ========================================")
        print(f"[Blender Script] Render complete!")
        print(f"[Blender Script] Total render time: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")
        print(f"[Blender Script] Output saved to: {output_path}")
        print(f"[Blender Script] ========================================")
    else:
        # Animation mode: render MP4
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
        default=None,
        help="Output path for the MP4 file. If not provided, will use <obj_dir>/human_motion.mp4"
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
    parser.add_argument(
        "--composite_frames",
        type=int,
        default=None,
        help="If set, creates a static composite image with N evenly-spaced frames visible at once with gradient colors. Overrides animation rendering."
    )
    parser.add_argument(
        "--separate",
        action="store_true",
        help="When used with --composite_frames, places poses in equally spaced regions on the floor, removing global location information."
    )
    
    # Parse arguments after -- separator (like reference code)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(argv)
    
    # Set default output path if not provided
    if args.output_mp4 is None:
        args.output_mp4 = os.path.join(args.obj_dir, "human_motion.mp4")
        print(f"[Blender Script] No output path provided, using default: {args.output_mp4}")
    
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
        composite_frames=args.composite_frames,
        separate=args.separate,
    )
