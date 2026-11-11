# Implicit heat: MPI Jacobi vs CG

This project solves the same 2D Backward Euler system with distributed Jacobi or unpreconditioned conjugate gradient. See `results/STATUS.md` for experiment provenance and limitations.

## Build and validate on the Illinois Campus Cluster

In a Slurm allocation or batch job, load the same MPI module for build and run:

```bash
module load openmpi
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 2
python3 tests/test_integration.py
```

The supplied `scripts/validate.sbatch` is based on the account and partition used by prior coursework; verify those settings before submitting. From the project directory: `sbatch scripts/validate.sbatch`. Do not run multi-rank experiments on the login node. Override `MPIEXEC` in the test environment if necessary.

Inside an allocation, an example single run is:

```bash
mpirun -np 4 ./build/implicit_heat --N 512 --steps 5 --solver cg --r 2 --tol 1e-8 --output run.json
```

Switch `--solver cg` to `--solver jacobi` for the matching comparison. `--help` lists the options. Each output is one JSON record. The warm-up field is reset before the measured steps. A nonconverged solve exits nonzero. `--dump-field file.csv` is intended **only for small tests**: the current implementation allocates a full grid on each rank for this optional diagnostic.

`solve_total_s` is the sum of per-step maximum rank elapsed times; each timing component comes from that step's same critical rank. Timings exclude initialization, verification, and output. They include necessary norm/reduction operations; packing is local compute. MPI time also includes waiting and is not a direct network-transfer measurement. Operation counts are per-rank solver calls summed over steps, excluding verification. Initial residual and norm checks are included.

## Preliminary pilot

`scripts/pilot.sbatch` runs a small two-node connectivity and measurement pilot using the prior course account. `scripts/run_matrix.py --mode pilot --dry-run --output-dir data/pilot` prints its commands. The core mode was used for the completed primary study documented in `results/STATUS.md`; it requires a suitable two-node allocation with at least 16 ranks per node. The runner verifies the observed node count for each case and writes one JSON and stderr file per run, preserving failures. Existing output files are skipped rather than overwritten.

To plot completed runs on a machine with Matplotlib:

```bash
python scripts/make_plots.py results/pilot-12296889 --output-dir results/pilot-12296889/figures
```

Pilot plots are pipeline checks only, not final results. `scripts/core.sbatch` runs the three-repeat core matrix on two exclusive AMD nodes; its account, partition and constraint may need adjusting for another environment. `srun` records each node's CPU details. The raw JSON files include actual rank hostnames; see `results/STATUS.md` for the selected dataset and excluded runs.

## Reproduce the analysis

With Python 3, NumPy and Matplotlib installed, from the project root:

```bash
python scripts/analyze_extended.py results/data/extended-12312735 --output results/extended-analysis-12312735
python scripts/render_pdf.py
```

These commands regenerate the extended-study CSV and plots, then render the checked-in Markdown report and slides to PDF. The Markdown deliverables summarize the measured extended data; review and update them if the underlying measurements change. Only successful records with a passing true residual are used; failures are listed. The field figure uses a separate small cluster run and is not a performance measurement. `results/core-12296980` is an earlier heterogeneous-node run and is retained for provenance. The legacy `scripts/analyze.py` regenerates the original three-trial report and slides and would overwrite the updated Markdown; do not run it over the current deliverables without backing them up.

All repetitions of a configuration share one allocation and were taken close in time. MPI timing includes wait and imbalance; crossovers are therefore operational, not direct measurements of network latency. P=1 and P≥2 differ in node count. Full per-rank timing distributions and separate step timings were not recorded in the measured core run; do not infer them from the aggregate breakdown.
