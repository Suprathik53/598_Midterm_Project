#!/bin/bash
#SBATCH --account=26fa-cs598pa-eng
#SBATCH --partition=eng-instruction
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=2
#SBATCH --cpus-per-task=1
#SBATCH --time=00:10:00
#SBATCH --job-name=heat-pilot
#SBATCH --output=heat-pilot-%j.log
set -eo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
module load openmpi
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
mkdir -p "data/pilot-${SLURM_JOB_ID}"
{ date -u; hostname; module list 2>&1; mpirun --version; mpicxx --version; lscpu; } > "data/pilot-${SLURM_JOB_ID}/environment.txt"
python3 scripts/run_matrix.py --mode pilot --repeats 1 --output-dir "data/pilot-${SLURM_JOB_ID}"
