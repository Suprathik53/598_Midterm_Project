# Extended study: measured findings

Slurm job 12312735 completed 280 runs (56 groups, five trials per group), with no invalid or failed runs in the analysis. All ran five physical steps after one reset warm-up. Every true residual was at most 9.985e-9 for tolerance 1e-8. The two-node cases were evenly distributed across AMD nodes ccc0391 and ccc0392; P=1 used ccc0391. Raw records and metadata are in `../data/extended-12312735/`.

## Strong scaling and communication crossover

The operational communication fraction is critical-rank MPI-call time (halo plus reductions) divided by local compute plus MPI-call time, aggregated across the steps. Values below are medians, followed by minimum–maximum across five trials. A bracket identifies adjacent sampled rank counts, not an exact threshold.

| Solver | Grid | P below 50% | P above 50% | Observed bracket |
|---|---:|---:|---:|---:|
| Jacobi | 512 | P=16: 39.6% [39.4%, 40.6%] | P=24: 52.0% [50.5%, 52.9%] | 16–24 |
| CG | 512 | P=16: 37.7% [36.6%, 38.0%] | P=24: 58.2% [56.3%, 58.8%] | 16–24 |
| Jacobi | 1024 | P=48: 44.6% [43.7%, 45.0%] | P=64: 51.8% [51.6%, 53.6%] | 48–64 |
| CG | 1024 | P=48: 40.6% [39.1%, 41.9%] | P=64: 61.2% [60.7%, 62.8%] | 48–64 |

For N=512, both solvers' median solve times decreased through P=32 and then increased at P=48 and 64. For N=1024, median solve time continued decreasing through P=64 for both solvers, despite communication's share exceeding 50% at P=64: a communication-dominated breakdown does not imply that adding ranks must immediately increase total runtime.

## Weak scaling

The square grids (N,P)=(256,1),(512,4),(1024,16),(2048,64) keep 256×256 cells per rank. Jacobi's median five-step time rose from 0.0697 s to 0.1157 s and CG's from 0.0154 s to 0.0226 s. Iteration counts fell as N increased, so end-to-end time alone masks changes in per-iteration cost: median time per iteration rose from 0.127 to 0.289 ms for Jacobi and 0.262 to 1.027 ms for CG. These are solver-scaling measurements at fixed r, not equal physical-time simulations. The one-rank baseline uses one node while the other configurations use two.

## Timestep sensitivity

At N=1024, P=16, increasing r from 0.5 to 8 raised median total iterations over five steps from 150 to 1920 for Jacobi and from 11 to 85 for CG. Corresponding median solve times rose from 0.0307 to 0.3176 s and from 0.00806 to 0.0338 s. Increasing r changes the physical timestep and the linear system; this is not an equal-physical-time accuracy comparison.

## Limitations and reproducibility

MPI call time includes wait and imbalance, not just network transfer; 'compute' means measured local kernels rather than a hardware-level CPU-vs-memory characterization. Five close-in-time trials on one allocation do not measure day-to-day variability. The N=1024 Jacobi P=64 result is only modestly above the 50% threshold, despite all five trials being above it. The new runs are a separate allocation from the original core study and use a later source version with diagnostics compiled out; don't silently pool or claim bitwise-equivalent binaries without checking. Recreate `summary.csv` and plots using `python scripts/analyze_extended.py results/data/extended-12312735 --output results/extended-analysis-12312735`.
