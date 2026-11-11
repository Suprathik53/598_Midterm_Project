#!/bin/bash
#SBATCH --account=26fa-cs598pa-eng
#SBATCH --partition=eng-instruction
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=16
#SBATCH --constraint=amd
#SBATCH --cpus-per-task=1
#SBATCH --exclusive
#SBATCH --time=00:30:00
#SBATCH --job-name=heat-core
#SBATCH --output=heat-core-%j.log
set -eo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
module load openmpi
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
dir="data/core-${SLURM_JOB_ID}"
mkdir -p "$dir"
{ date -u; hostname; module list 2>&1; mpirun --version; mpicxx --version; lscpu; echo "SLURM_JOB_NODELIST=${SLURM_JOB_NODELIST}"; } > "$dir/environment.txt"
srun --nodes=2 --ntasks=2 --ntasks-per-node=1 bash -c 'hostname; lscpu' > "$dir/per-node-cpu.txt"
sha256sum src/main.cpp build/implicit_heat > "$dir/source.sha256"
python3 scripts/run_matrix.py --mode core --repeats 3 --output-dir "$dir"
