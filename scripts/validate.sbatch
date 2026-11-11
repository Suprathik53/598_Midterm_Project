#!/bin/bash
#SBATCH --account=26fa-cs598pa-eng
#SBATCH --partition=eng-instruction
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --cpus-per-task=1
#SBATCH --time=00:10:00
#SBATCH --job-name=heat-validation
#SBATCH --output=heat-validation-%j.log
set -eo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
module load openmpi
export OMP_NUM_THREADS=1
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 2
mpirun -np 1 ./build/test_stencil
mpirun -np 2 ./build/test_stencil
mpirun -np 3 ./build/test_stencil
mpirun -np 4 ./build/test_stencil
python3 tests/test_integration.py
python3 tests/test_diagnostics.py
