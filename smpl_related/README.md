# SMPL Human Animation Renderer

Renders human animations from OBJ sequence files using Blender.

## Setup

Create and activate the conda environment:

```bash
cd randoms
conda env create -f environment.yml
conda activate general
```

## Usage

```bash
python render_human_animation.py --obj_dir <path_to_obj_directory> [options]
```

## Example

```bash
python render_human_animation.py \
  --obj_dir ~/Documents/VideoMDM/smpl_renders/fit3d/videomdm_longer/sample83_rep00_obj \
  --composite_frames 12 \
  --separate \
  --max_frames 100 \
  --start_frame 30 \
  --resolution 2048 2048 \
  --spacing 1 \
  --camera_position up \
  --floor_position force_touch_all_frames
```

This creates a static composite image with 12 evenly-spaced poses arranged on the floor, starting from frame 30.

## Key Options

- `--composite_frames N`: Create static image with N evenly-spaced frames
- `--separate`: Place poses in equally spaced regions on floor
- `--camera_position`: `left`, `right`, `front`, or `up`
- `--floor_position`: `lowest_vertex_first_frame`, `zero`, or `force_touch_all_frames`
- `--resolution W H`: Render resolution (default: 512 512)

## Output

- Composite mode: Saves PNG image and `.blend` file for further editing
- Animation mode: Saves MP4 video

## Editing Colors and Lighting (Composite Mode)

You'll be provided with `example_obj_folders.zip` containing:
- `sample58_rep00_obj_for_composite_mode` - for testing composite mode
- `sample83_rep00_obj_for_separate_mode` - for testing separate mode

Extract and use these folders to test your edits. Run these commands to observe output when editing:

**Composite mode example:**
```bash
python render_human_animation.py \
  --obj_dir <path_to_extracted_folder>/sample58_rep00_obj_for_composite_mode \
  --composite_frames 7 \
  --resolution 512 512
```

**Separate mode example:**
```bash
python render_human_animation.py \
  --obj_dir <path_to_extracted_folder>/sample83_rep00_obj_for_separate_mode \
  --composite_frames 12 \
  --separate \
  --max_frames 100 \
  --start_frame 30 \
  --resolution 2048 2048 \
  --spacing 1 \
  --camera_position up \
  --floor_position force_touch_all_frames
```

To edit colors and lighting, modify `blender_render_obj_human_motion.py`:

**Colors** (lines 409-413):
- Edit the `start_color` and `end_color` RGBA tuples in the `apply_gradient_colors()` call
- Current: orange gradient from `(0.2, 0.1, 0.0, 1.0)` to `(1.0, 0.6, 0.2, 1.0)`
- Colors are in RGBA format (0-1 range)

**Lighting** (lines 573-585):
- Three-point light rig: Key, Fill, and Rim lights
- Adjust `energy`, `location` (x, y, z), and `rotation_euler` for each light
- For HDRI lighting, use `--use_hdri --hdri_path <path>` when running the script
- Or just change these lines completely

