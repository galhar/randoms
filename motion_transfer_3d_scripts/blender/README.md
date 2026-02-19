# BlenderNeRF Rendering & 3DGS Training

## Prerequisites

- Blender installed via snap (`/snap/blender/current/blender`). If your Blender executable is at a different path, update it in `render_for_dataset.py`.
- Conda environment from `environment.yml` at the repo root:
  ```bash
  conda env create -f environment.yml
  conda activate general
  ```

## Rendering with BlenderNeRF

### Input Structure

Place your 3D model files (`.glb`, `.fbx`, or `.obj`) inside a single directory:

```
<objects_dir>/
├── low_poly_dolphin.glb
├── another_model.obj   # optional additional models
└── ...
```

### Run

```bash
cd motion_transfer_3d_scripts/blender

python render_for_dataset.py \
  --objects_dir <path_to_objects_dir> \
  --mode blendernerf
```

Example:

```bash
python render_for_dataset.py \
  --objects_dir /path/to/my_objects/dolphin \
  --mode blendernerf
```

where `dolphin/` contains `low_poly_dolphin.glb`.

### Output

A `datasets/` folder is created inside `<objects_dir>`:

```
<objects_dir>/
├── low_poly_dolphin.glb
└── datasets/
    └── low_poly_dolphin/
        └── ...  (rendered images + camera data)
```

## Creating 3D Gaussian Splatting (3DGS) Models

Given a working install of the [3DGS original repo](https://github.com/graphdeco-inria/gaussian-splatting) and its conda environment.

**Use this specific commit** ([`a2a91d9`](https://github.com/graphdeco-inria/gaussian-splatting/commit/a2a91d9093fd791fb01f556fa717f8d9f2cfbdd7)) — some other commits have breaking issues:

```bash
<path_to_3dgs_env>/bin/python train.py \
  -s "<dataset_path>/dataset" \
  --model_path "<dataset_path>/output" \
  --disable_viewer
```

Where `<dataset_path>` is the path to an extracted rendered dataset directory (e.g. `<objects_dir>/datasets/low_poly_dolphin`).

### Cleaning Up

The trained 3DGS may contain noisy/floating gaussians. If you need a clean result, you can manually remove them using the [SuperSplat Editor](https://superspl.at/editor) — load the `.ply` output and delete stray splats interactively.
