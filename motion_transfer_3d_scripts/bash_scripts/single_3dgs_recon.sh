#!/bin/bash
#SBATCH --job-name=3dgs_reconstruction
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --time=00:15:00
#SBATCH --output=sbatch_logs/output_%j.log
#SBATCH --mem=0
#SBATCH --requeue


eval "$(/home/galhar/miniconda3/bin/conda shell.bash hook)"
conda activate 3dgs

# Using commit a2a91d9093fd791fb01f556fa717f8d9f2cfbdd7 of the repo https://github.com/graphdeco-inria/gaussian-splatting.git
# As the main commit " 54c035f7834b564019656c3e3fcc3646292f727d " didnt work good
cd /home/galhar/gits/gaussian-splatting-older-commit/gaussian-splatting

mkdir -p $dataset_path/dataset
mkdir -p $dataset_path/output
unzip -o $dataset_path/dataset.zip -d $dataset_path/dataset

/home/galhar/miniconda3/envs/3dgs/bin/python train.py -s "$dataset_path/dataset" --model_path "$dataset_path/output" --disable_viewer


# Handle job requeueing for preemption
if [[ $? -eq 99 ]]; then
    echo "Job preempted, requesting requeue..."
    scontrol requeue $SLURM_JOB_ID
else
    echo "Job completed or failed with status: $?"
fi
