Usage examples:
1. Render motions:  
<motions_dir>  
-- <animated_object_1>.glb    
-- <animated_object_1>.json  
-- <animated_object_2>.glb  
-- <animated_object_2>.json  
-- ...    
example for a manually created json per animation:   
{"rotate_by": 0,"frame_start": 15, "frame_end": 80, "frame_step": 3}  
One can use the default values instead, but most motions will require adjusting the frame_step, rotate_by, and can require frame_start, and “frame_end” cutting for rendering speed.  
<floor_texture_img.jpg> can come from a website like this https://polyhaven.com/a/forrest_ground_01 

```bash
python render_for_dataset.py --objects_dir <motions_dir> --floor_texture_path <floor_texture_img.jpg>
```


2. Create 3dgs:  
<objects_dir>   
-- <object_1.glb>  
-- <object_2.glb>  
-- ...
 
```bash
python render_for_dataset.py --objects_dir <objects_dir> --mode blendernerf
```

3. Then create the reconstruction:  
First for the dataset.zip files created, each need to be unzipped into <dataset_path> each.  
Then, get into the https://github.com/graphdeco-inria/gaussian-splatting.git repository, to commit a2a91d9093fd791fb01f556fa717f8d9f2cfbdd7 ( as the current main commit, 54c035f7834b564019656c3e3fcc3646292f727d, doesn't work well).   
After setting up the conda env and making it runnable, run:

```bash
python train.py -s "<dataset_path>/dataset" --model_path "<dataset_path>/output" --disable_viewer
```
or you can just cd "bash_scripts" then run "send_3dgs_recon_sbatch.sh"

4. Then manually align in pose and scale the 3dgs:
Take as reference another ply for pose and scale.  
Open https://playcanvas.com/supersplat/editor and import there the reference and all the plys to align.  
Then, one by one, go over them and rotate them and scale them and save them back as “.._aligned.ply”
