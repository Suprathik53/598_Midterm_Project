#!/bin/bash
#SBATCH --account=26fa-cs598pa-eng
#SBATCH --partition=eng-instruction
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --time=00:05:00
#SBATCH --job-name=heat-snapshot
#SBATCH --output=heat-snapshot-%j.log
set -eo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
module load openmpi
export OMP_NUM_THREADS=1
mkdir -p data/fields
mpirun --bind-to core -np 4 ./build/implicit_heat --N 128 --steps 5 --solver cg --dump-field "data/fields/final-${SLURM_JOB_ID}.csv" --output "data/fields/snapshot-${SLURM_JOB_ID}.json"
