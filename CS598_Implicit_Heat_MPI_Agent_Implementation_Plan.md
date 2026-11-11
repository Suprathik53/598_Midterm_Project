# CS 598 Midterm Project — Agent Implementation Plan
## Parallel implicit heat diffusion: Jacobi vs. Conjugate Gradient, computation vs. communication

> **Status:** Implementation specification, not measured results. Never invent cluster configurations, runtimes, crossover points, plots, or conclusions. Produce conclusions only after real benchmark data have been collected and validated.
>
> **Assignment context:** Two-student midterm project, presentation and short report. The instructor suggests a homework-scale implementation with a more challenging performance question and recommends under-subscribing compute resources across multiple nodes to isolate communication overhead from local contention. This plan intentionally prioritizes a reproducible **minimum viable study** over many complicated algorithmic extensions.
>
> **Verification boundary:** The original instructor prompt/rubric is not present in this workspace. Treat the assignment context, dates, deliverable length and other claimed instructor requirements as unverified until checked against the original. The numerical model and implementation instructions below have been reviewed for internal consistency; cluster observations are explicitly distinguished from assumptions.

## 0. Your role and definition of done

You are a coding/research agent. Implement an end-to-end, reproducible MPI/C++17 + Python benchmarking project that:

1. Simulates the 2D heat equation with **Backward Euler (implicit)** finite differences and zero Dirichlet boundaries.
2. Solves the **same matrix-free SPD linear system** using (a) parallel Jacobi iteration and (b) parallel Conjugate Gradient (CG), with the same numerical tolerance and initial guess.
3. Demonstrates correctness against analytic and serial-reference solutions before benchmarking.
4. Collects real multi-process / multi-node timings, iteration counts, and communication metrics for strong scaling (required); weak scaling and time-step sensitivity are secondary.
5. Determines separately for each solver **whether and at what measured process count communication time exceeds local computation time**, including both halo communication and collective reductions.
6. Automatically produces publication-ready performance figures, a heat-map visual, a data-driven short report, and presentation slides with explicit caveats.
7. Runs on a Slurm/MPI HPC cluster without needing root access. Also works for local testing with `mpirun -np N` if available.

**Never pretend to have executed anything that the environment cannot actually execute.** If the cluster is inaccessible, deliver complete source/scripts/tests and an honest `results/STATUS.md` documenting how to run the outstanding experiments. Don't write fabricated experimental conclusions.

## 1. Scope, assumptions and mathematical model

**Scope:** 2D square unit plate, constant thermal diffusivity `alpha = 1.0`, zero-temperature Dirichlet boundary at `x=0,1` and `y=0,1`. Interior is an `N x N` grid; `h = 1/(N+1)`. Choose equal spacings in both directions.

Governing PDE:

`dT/dt = alpha * (d²T/dx² + d²T/dy²)`.

For Backward Euler, given current interior temperature `b = T^n`, solve for `x = T^(n+1)`:

`(I - alpha*dt*L_h) x = b`, where `L_h` is the standard 5-point discrete Laplacian.

Let `r = alpha*dt/h²`. The matrix-free action at interior point `(i,j)` is:

`(A*x)[i,j] = (1 + 4*r)*x[i,j] - r*(x[i-1,j] + x[i+1,j] + x[i,j-1] + x[i,j+1])`.

An off-domain neighbor is **zero**, not a periodic wraparound. Thus `A` is symmetric positive definite (SPD) for `dt > 0`, making both Jacobi and CG applicable.

**Baseline parameterization:** Specify `r` directly via CLI and calculate `dt = r*h*h/alpha`, so the conditioning of the implicit system stays reasonably comparable as grid resolution changes. Baseline `r=2.0`; optional `r=8.0` stress test. Report `r`, `dt`, `h`, `N` in every record. Note that fixing `r` across `N` changes physical `dt`, so these are solver-scaling comparisons, not equal-physical-time accuracy comparisons.

**Initial condition for benchmarks:** Use a deterministic **multi-feature Gaussian field** with a zero-boundary envelope to avoid the pathological case where a single sine eigenmode makes CG converge in one iteration. Example:

`T0(x,y) = sin(pi*x)*sin(pi*y) * [0.25 + 1.1*exp(-((x-.30)^2+(y-.35)^2)/0.012) + 0.65*exp(-((x-.74)^2+(y-.63)^2)/0.006)]`.

No random seed needed. Use `x=(global_i+1)*h`, `y=(global_j+1)*h` for zero-based global interior indices. For analytic validation only, use `T0 = sin(pi*x) sin(pi*y)`, with continuous exact solution `T(x,y,t)=exp(-2*pi²*alpha*t)*sin(pi*x)*sin(pi*y)`. **Do not use the sine-only case for primary performance comparisons.**

**Numerical convergence criterion (both solvers):**

`relative_residual = ||b - A*x||_2 / max(||b||_2, 1e-30) <= tol`, with baseline `tol=1e-8` (allow CLI control), hard cap `max_iter=10000`, and record a nonconvergence status rather than silently treating it as success. Calculate distributed squared norms with `MPI_Allreduce(MPI_SUM)`; do not gather full grids just to compute norms. Both solvers start from the same guess `x0=b` for each physical step. Verify true residual outside timed region after the solve; the true residual must satisfy the stated tolerance. Record both true and recursive CG residuals; if they disagree materially, flag the run for investigation even if the true criterion passes. Handle `b=0` and an initially converged guess without dividing by zero.

**Physical time:** Benchmark a fixed *number* of Backward Euler steps (e.g. `steps=5`) rather than pretending fixed-`r` grids simulate equal physical durations. Include optional accuracy test with fixed physical final time and a mesh-refinement study separately.

## 2. MPI domain decomposition and shared numerical kernels

Implement **2D block decomposition** over `P` MPI ranks:

- `MPI_Dims_create(P,2,dims)`, then `MPI_Cart_create` with `periods={false,false}`; record `dims[0],dims[1]` in output.
- Correctly partition `N` across ranks even when `N % dims[axis] != 0` (quotient + remainder partition); compute local sizes and global offsets.
- Each rank owns a contiguous 2D interior block stored row-major, with a 1-cell ghost/halo on each side. Use `std::vector<double>` and an indexing helper; keep ghost cells separate from owned norm/dot operations.
- Implement exchange of north/south halo **rows** and east/west halo **columns** using `MPI_Sendrecv` (or paired `MPI_Irecv`/`MPI_Isend` + `MPI_Waitall`), with consistent distinct tags. Pack strided columns into contiguous arrays; rows can be contiguous. For ranks at the physical domain boundary, fill the corresponding ghost cells with `0.0` every exchange. Check orientation carefully.
- Implement one reusable `apply_A(local_x, local_Ax)` routine that exchanges halos and applies the 5-point stencil. This is the matrix-free equivalent of sparse matrix-vector multiplication. **Never form or distribute a dense `N² x N²` matrix.**
- Implement common local `dot`, `axpy`, `scale`, `copy`, `l2_error`, and deterministic initialization. Aggregate any needed global scalar via MPI collectives.
- Use `MPI_DOUBLE`, and `MPI_PROC_NULL` appropriately. Handle degenerate local blocks safely; if `N` is smaller than the process grid dimensions, reject with a useful error.

Implement an optional `--dump-field` gathering the final field onto root *only for visualization/small cases*, outside timing. For large problems, downsample or write a representative sample without overwhelming memory.

## 3. Solver A — distributed Jacobi

For the same `A*x=b`, diagonal `D=(1+4r)I`. Starting at `x=b`, each iteration uses the previous estimate to produce a new one:

`x_new[i,j] = x_old[i,j] + (b[i,j] - (A*x_old)[i,j])/(1+4r)`.

Implementation:

1. Halo exchange on `x_old`.
2. Compute local residual components `res_i = b_i - (A*x_old)_i` and new estimate `x_new`; count local arithmetic as compute, halo as communication.
3. Every `jacobi_check_every` iterations (default `10`; check on iteration 1 and at the cap too), use `MPI_Allreduce` on sum of `res_i²` to test convergence of **the current `x_old`**. If converged, return `x_old` (do not mistakenly return an extra update). Between checks, continue iterations; a delayed check is a deliberate communication-versus-iteration tradeoff.
4. Swap buffers when not converged. At end perform a true-residual verification. Never stop based only on `||x_new-x_old||`, because that is not directly comparable to CG's criterion.

Define `iterations` as the number of updates actually applied, not the number of residual evaluations. Explicitly check `x0` before updating and then check the returned iterate after updates 1, 10, 20, ... and `max_iter`; restructure the loop as needed so the cap checks the *post-update* iterate. Record initial and later checks consistently. This avoids an off-by-one error and permits zero iterations for an initially converged system. Delayed checks may overshoot the earliest possible stopping iteration.

Record `iterations`, `residual_checks`, `global_reductions`, `halo_exchanges`, `relative_residual`, `converged`. Optional sensitivity plot for `jacobi_check_every=1,5,10` if time permits; otherwise keep it fixed and describe it accurately.

## 4. Solver B — distributed Conjugate Gradient (unpreconditioned)

Because `A` is SPD, implement standard, matrix-free CG:

- Initial `x=b`; `r_vec=b-A*x`; `p=r_vec`; `rr = <r_vec,r_vec>` using global dot product.
- Check the initial residual against the same denominator and tolerance before entering the loop. Return success with zero iterations if already converged, including `b=0`; do not attempt `0/0` or report a false `pAp` breakdown.
- Repeat: `Ap=A*p` (uses one halo exchange), `pAp=<p,Ap>` (`MPI_Allreduce`), `a=rr/pAp`, `x+=a*p`, `r_vec-=a*Ap`, `rr_new=<r_vec,r_vec>` (`MPI_Allreduce`), test `sqrt(rr_new)/||b|| <= tol`, `beta=rr_new/rr`, `p=r_vec+beta*p`, `rr=rr_new`.
- Detect non-finite values and `pAp <= 0` as numerical failure, and cap iterations. Record number of dot-product reductions, halos, and convergence; CG should normally need fewer iterations, but do not hard-code a ranking.
- At end, recompute **true** residual `||b-A*x||` and verify the stated tolerance; this validation may be outside the timed solve but its cost and exclusion must be explicitly labeled. If an issue arises, implement periodic residual replacement as a documented extension, not as a silent change.
- **No preconditioner in required baseline**, to keep comparison clean. For this constant-coefficient operator the diagonal is a scalar multiple of identity, so Jacobi-preconditioned CG is mathematically equivalent to ordinary CG in exact arithmetic and is not a meaningful conditioning improvement. Only consider a nontrivial preconditioner as a separately motivated extension.

## 5. Timing design and operational definition of the bottleneck

The instructor's question is about **MPI runtime dominated by local numerical work vs interprocess communication**, not necessarily CPU-FLOP-bound versus DRAM-bandwidth-bound at the hardware level. Explicitly distinguish those definitions in the report. The numerical stencil may itself be *memory-bandwidth-bound* even when MPI communication is cheap.

Measure on **every rank** using `MPI_Wtime()`:

- `compute_s`: local stencil math, vector updates, local dot-product operations, and local residual calculation; exclude MPI calls.
- `halo_s`: time inside halo MPI communication calls, including blocking send/recv or nonblocking wait; count exposed communication time correctly. Include column packing/unpacking in a separately named local overhead/compute component, not invisibly inside MPI time; state the convention.
- `reduction_s`: time inside collective calls for global dot products/norms/convergence.
- `other_s`: small untimed-category overhead within the solver; calculate after measurement as `total_s - compute_s - halo_s - reduction_s` and flag any large discrepancy. Make no per-iteration barriers solely for timing.
- `solve_total_s`: the end-to-end time of all solver iterations **and necessary convergence checks**, measured from a synchronized start (single `MPI_Barrier` prior to measured region) to the locally completed solve, excluding initialization, allocations, validation, output, and setup. Record per-step and per-run totals.
- `total_steps_s`: total solver time across the same fixed number of physical timesteps; separately report wall time including physical-step setup if meaningful.
- Iteration count, convergence checks, halo exchange count, reduction count.

After the timed region, gather rank-local timing summaries. Define `T_total = max_r(solve_total_s[r])` (the critical/bottleneck rank wall time). To avoid a misleading breakdown from adding maxima of different ranks, report `compute_s`, `halo_s`, `reduction_s`, and `other_s` **from the same critical rank `r*`** that has the max end-to-end solve time. Also record means/maxima across ranks as diagnostics; don't sum independent maxima and call that total time.

For multiple steps, retain per-step/per-rank records. Define run-level solver time as the **sum of per-step maximum rank solve times**, and sum the components belonging to each step's own critical rank; the critical rank may change between steps. Store per-step critical ranks and document that this sum is not a continuously measured full-run wall time. Also measure full-run wall time separately, identifying what setup and verification it includes. Sum counts consistently across steps, noting whether they are per-rank call counts or rank-summed totals. Verification and reporting collectives are not solver communication; time and count them separately. Synchronization/setup between steps is outside the solver sum and must be labeled. Avoid using timing-gather collectives inside the measured interval.

Baseline uses **nonoverlapping/blocking halo exchange** so time categories have interpretable, largely disjoint durations. If adding nonblocking overlap later, account separately for overlapped communication and avoid adding asynchronous in-flight time to compute time as if they were serial; compare actual end-to-end runtime and exposed waiting instead.

For each repetition define:

- `communication_s = halo_s + reduction_s` (on critical rank).
- `communication_fraction = communication_s / (compute_s + communication_s)`, excluding small `other_s` from the numerator/denominator and reporting its contribution separately.
- **Communication-dominated** iff `communication_s > compute_s` (fraction > 0.5); **compute-dominated** iff reverse; near 50% call balanced. Operationally this is MPI-time vs local-kernel-time and may include waiting/load imbalance, so explain limitations.

For each solver and grid size, use the **median across repeated runs** of `communication_s/compute_s` or `communication_fraction` to classify each tested process count; include scatter/uncertainty. Define **observed crossover** as the first tested `P` where median communication exceeds compute *after* lower-P compute-dominated cases. If the crossover lies between two sampled P values, report an interval `[P_low, P_high]`, **not a fabricated precise threshold**. If not observed, write `no crossover observed for P <= P_max`, not a forced result. Document inconclusive/noisy cases.

**MPI timing caveat:** `MPI_Allreduce` time contains time waiting for lagging ranks, not just network transfer. Optional pair of `MPI_Barrier` microbenchmarks and/or per-rank variance helps describe imbalance, but must not be interpreted as precise network latency decomposition.

## 6. Experiment matrix — prioritize what is feasible before Nov 11/13

### Required minimal viable study (finish first)

- Solvers: `jacobi`, `cg`.
- Strong-scaling grids: `N=512`, `N=1024` interior cells per side; optional `N=256` for a smaller, more communication-sensitive case. Pilot first: with fixed `r` the condition number remains bounded as N increases, and this smooth initial field can make the solve very short or even initially converged at large N. Confirm meaningful nonzero iteration counts and timings above timer resolution; if not, document and choose a deterministic, resolved multi-scale initial field or revised grid/tolerance consistently for both solvers before collecting the main data. Do not change cases merely to force a crossover.
- MPI counts: `P=1,2,4,8,16`, and `P=32` if cluster allows. One rank cannot span two nodes, so `P=1` is necessarily a single-node reference.
- `r=2`, `tol=1e-8`, `steps=5`, `jacobi_check_every=10`, `max_iter=10000`.
- 1 warm-up solve excluded from timing where practical, then **at least 3 independent repeats**, ideally 5. Reset the field after warm-up and before every repetition so the measured five steps always start at the same `T0`; change only intended experimental parameters. Record whether trials share a job allocation, and interleave/randomize solver/order when practical to reduce time-dependent bias.
- Use **two physical nodes** for `P >= 2` whenever permitted, distributing ranks as evenly as possible; keep nodes undersubscribed (e.g. up to 16 ranks/node if actual allocated core counts permit). Preserve CPU binding. For `P=1`, use one node and clearly note the topology difference. Inspect actual node hardware rather than assuming 128 cores.
- Important: Slurm resource allocations sometimes prevent a 2-node job with only one task per node unless requested explicitly. Verify actual hostnames/rank placement (`MPI_Get_processor_name` / `srun hostname`) and log mapping; do not infer topology from a requested flag alone.
- Run `jacobi` and `cg` on identical grids, steps, initial fields, `r`, and residual tolerance. Solver-specific number of iterations is an **outcome**, not controlled to match.

### High-value optional study after the core is correct

1. **Weak scaling:** Fix local subdomain about `256x256` cells per rank using process-grid dimensions; e.g. P = 1, 4, 16 and global `N=256,512,1024` respectively. For non-square ranks, allow a rectangular global domain in a later extension or use square process counts only. Keep `r` fixed and show total time **and time per solver iteration**; iteration count can change as the global system changes.
2. **Solver difficulty vs timestep:** `r=0.5,2,8` at fixed N and P; report iteration count and runtime. Larger implicit timesteps can be stable but require more iterative work; avoid calling stability equivalent to accuracy.
3. **Same P on one vs two nodes:** For P=4,8,16, repeat with all ranks on one node vs split across two nodes to isolate inter-node penalties if the scheduler permits. Record topology.
4. **Communication overlap:** Only after all above is reproducible; compare to blocking baseline with clear exposed-wait measurements.

Avoid combinatorial blowup. If run budget is limited, the required strong-scaling matrix takes priority. Build `--quick` (small smoke tests), `--core` (minimal study), and `--full` (additional options) modes for launch scripts.

## 7. Running on Slurm without assuming unavailable cluster settings

- Use CMake and an MPI C++ compiler; prefer `find_package(MPI REQUIRED)` / `MPI::MPI_CXX`; C++17, `-O3 -DNDEBUG` for release and a separate sanitizer/debug configuration if supported. Do not hard-code module names, Slurm partitions, MPI launcher flags, or node names; put them in `config/cluster.env.example` and a README.
- Detect whether `srun` is supported and whether `srun --mpi=pmix` (or another MPI type) is actually valid; verify with `srun --mpi=list`. Provide a fallback `mpirun` launch pattern for interactive allocation if appropriate. Do not launch MPI ranks via a serial loop.
- Suggested Slurm pattern (adapt after inspecting the environment): request `--nodes=2`, an adequate maximum `--ntasks`, `--cpus-per-task=1`, optionally `--exclusive`; within a fixed allocation, use `srun --nodes=2 --ntasks=P --ntasks-per-node=P/2 --cpu-bind=cores ...` for even P. For 1 process, launch on 1 node. Ensure job steps actually map to two distinct nodes. If oversubscription/partition restrictions prevent this, document the deviation rather than silently proceeding.
- `OMP_NUM_THREADS=1`, no accidental threaded BLAS, and avoid simultaneous competing measurements on same allocated cores.
- Write environment metadata: CPU/node model (`lscpu`), MPI runtime/compiler versions, job ID, hostnames, allocated nodes, placement, Slurm partition, process grid, compiler flags, build commit/hash if available, and date.
- Use deterministic filenames with experiment ID. Preserve raw outputs, stderr, nonconvergence runs and logs. Jobs must be restartable; don't overwrite completed good runs, but allow `--force`.
- Process failures and timeouts should be clearly marked `failed` and excluded from performance plots; never silently omit them from a run summary.

### Workspace-specific cluster observations (verify again at run time)

- Existing HW2/HW3 jobs used `sv53@cc-login.campuscluster.illinois.edu`, account `26fa-cs598pa-eng`, partition `eng-instruction`, `module load openmpi`, and `mpirun` in Slurm allocations. These are prior working examples, not a guarantee of current access or available resources. In a test on the current login node, CMake 3.31.8 and Python 3.9.25 were available, and after loading `openmpi`, `mpicxx` and Open MPI 5.0.1 ran. Without loading that module the visible MPI commands failed on a missing `libpmix.so.2`; load the module before configuring, building, and running, and capture the actual compiler/module versions.
- `srun --mpi=list` advertised `pmix` and other plugins, but this does **not** verify compatibility with the loaded Open MPI. Test an actual small Slurm job before selecting a launcher. Prior HW2 output reported 64 logical CPUs on its allocated node; node types and core counts may differ. Request and verify mapping explicitly: the old HW3 `ppr:64:node` launch alone does not guarantee low-P runs occupy two nodes.
- The available shared SSH session can be reused from WSL via `ssh -S /root/.ssh/campus-cluster-control -o ControlMaster=no sv53@cc-login.campuscluster.illinois.edu`; the socket exists only while its authenticated master remains open. `scp -o ControlPath=/root/.ssh/campus-cluster-control ...` can use that same session. Keep credentials out of scripts and logs. Upload sources with `scp`, submit compute-intensive work with Slurm, and retrieve result archives with `scp`; don't benchmark on the login node.

## 8. Software structure and CLIs

Create the following organized repository (adjust names only for good reason):

```text
implicit-heat-mpi/
  CMakeLists.txt
  README.md
  LICENSE                      # optional
  config/
    cluster.env.example
    experiments.yaml
  src/
    main.cpp                   # CLI, solver selection, loop, JSONL output
    grid.hpp grid.cpp          # decomposition, index/offsets, halo buffers
    stencil.hpp stencil.cpp    # A*x and numerical kernels
    jacobi.hpp jacobi.cpp
    cg.hpp cg.cpp
    timing.hpp timing.cpp      # rank-local metrics + reduction to root
    initial_conditions.hpp initial_conditions.cpp
  tests/
    test_serial_reference.py   # scipy sparse or independent numpy reference
    test_integration.py        # invoke mpirun for tiny P, compare residual
  scripts/
    configure_build.sh
    smoke_test.sh
    run_local.sh
    submit_slurm.sh
    run_experiment_matrix.py   # constructs commands, dry-run/retry
    collect_results.py
    make_plots.py
    make_report.py
    make_slides.py
  data/
    raw/                       # one JSONL/JSON per completed run
    processed/                 # canonical cleaned CSV
    fields/                    # optional small snapshots
  figures/
    strong_scaling_runtime.png
    strong_scaling_speedup.png
    strong_scaling_efficiency.png
    communication_breakdown.png
    communication_fraction.png
    iterations_vs_processes.png
    solve_time_comparison.png
    temperature_snapshots.png
    weak_scaling.png            # optional
    timestep_sensitivity.png    # optional
  results/
    summary.csv
    crossover_summary.csv
    findings.md
    STATUS.md
  report/
    report.md
    report.pdf                  # render if feasible
  slides/
    presentation.pptx          # python-pptx, or .md slides if unavailable
  requirements.txt
```

**Main CLI**, with explicit help and nonzero exit on numerical failure:

```bash
./build/implicit_heat \
  --N 512 --alpha 1.0 --r 2.0 --steps 5 \
  --solver jacobi --tol 1e-8 --max-iter 10000 \
  --jacobi-check-every 10 --init gaussian \
  --output data/raw/experiment.jsonl \
  --trial 1 --warmup-steps 1
```

CG uses `--solver cg`. Support `--validate`, `--dump-field <path>`, `--help`, `--dry-run` for orchestration (not necessarily for the executable), and `--N` independent of process count. Optional `--Nx`/`--Ny` only if simple to add without destabilizing MVP. All rank zero file writes must be serialized/atomic; no concurrent append races. Create run outputs as separate files per P/solver/grid/repeat, then combine.

### Required raw output fields

Use machine-readable JSON (one record per trial, per solver) including at least:

`run_id, timestamp_utc, git_commit, status, reason_if_failed, solver, N, Nx, Ny, alpha, r, dt, h, steps, tol, max_iter, jacobi_check_every, P, cart_dims, nodes_requested, nodes_observed, hostname_by_rank, cpu_model, mpi_version, compiler, compile_flags, trial, warmup_steps, iteration_total, iteration_mean_per_step, halo_count, allreduce_count, residual_rel_max, max_abs_temperature, min_temperature, solve_total_s, compute_s, halo_s, reduction_s, other_s, communication_s, communication_fraction, per_step_critical_ranks, per_rank_timing_summary, step_timings`.

Use descriptive units (`_s` seconds). Some fields may be omitted/null when unavailable, but never fill with guesses. Include a schema validation step in Python.

## 9. Correctness gates — must pass BEFORE serious benchmarks

1. **Stencil test:** Tiny `N=4` or `N=8` with known arrays; check stencil against independent Python 5-point implementation for interior and physical boundary cells.
2. **MPI decomposition test:** For N not divisible by P decomposition (e.g. `N=17`, P=1,2,3,4), ensure each global interior cell is assigned once and global reconstruction is identical.
3. **Serial reference:** For small `N<=32`, construct sparse `A` in SciPy (or a separate dense NumPy reference for very small N) and solve via `spsolve`. Check both MPI Jacobi and CG `||x-x_ref||/||x_ref|| <= ~1e-6` and true relative residual <= tol (adjust reference error tolerance only with justification).
4. **Parallel invariance:** For each solver, N=32 or 64, compare P=1,2,4 (and 3 if possible), including N not evenly divisible, with relative difference consistent with floating-point reduction order; test zero Dirichlet behavior.
5. **Analytic heat solution:** Sine initial mode used only here. After several physical steps, compare to `exp(-2*pi²*alpha*t) sin(pi*x)sin(pi*y)` and show error decreases under refinement using a properly controlled physical-time experiment. Explain numerical spatial and temporal errors.
6. **Physical sanity:** With positive initial field and zero boundaries, backward Euler solution should remain finite and nonnegative within numerical tolerance, and max temperature should not increase above previous max; report violations, don't hide them.
7. **Solver stopping logic:** Validate exact relative residual for returned result, not merely internal recursively updated CG residual; add nonconvergence and invalid argument tests.
8. **Benchmark hygiene:** On a tiny grid, verify sum of compute/comm/other local timings agrees with per-rank wall clock within a small timing tolerance. Check same rank is used for critical path breakdown.
9. **Edge cases:** Test zero RHS and an initially converged nonzero guess, `max_iter=1`, convergence on the last allowed update, single-cell local blocks, both process-grid orientations, and invalid `N`, `r`, tolerance and iteration limits. All ranks must take consistent failure paths without hanging. Include a deliberately insufficient iteration cap and a case where the CG recurrence passes but independently recomputed residual does not.
10. **Discrete analytic check:** For the sine initial mode verify the exact discrete Backward Euler amplification `(1 + dt*alpha*8*sin(pi/(2*(N+1)))^2/h^2)^(-steps)` against the computed field. For continuous refinement hold final physical time fixed, choose integer step counts with `dt=final_time/steps`, and refine time along with space (e.g. `dt=O(h²)`); choose solver tolerance sufficiently small that algebraic error does not mask convergence. This test may require a `--dt` option or computing `r=alpha*dt/h²` externally.

`./scripts/smoke_test.sh` should build then run correctness tests with ranks 1,2,4 if available. Hard failure should prevent `--core` benchmark from proceeding.

## 10. Benchmark statistics, derived metrics, and plots

Repeat independent runs (core 3, preferred 5) and report **median** timing at each `(solver,N,P,r,topology)` plus min/max or bootstrap 95% intervals when repeats are enough. Record all raw trial values, not just averages. If variance is large (e.g. CV > 10%), flag the run and investigate placement/contention; do not smooth suspicious data away. Apply **same** process placement policy to both solvers.

For stacked timing bars, select the actual trial whose total is the median (for even counts, use a clearly specified representative trial) and stack its own per-step critical-rank components, rather than stacking independently computed component medians. Show medians and variability separately. The run-level communication fraction is computed from the summed same-step critical-rank components defined above; report per-step variation where critical ranks change.

Derived metrics:

- Strong scaling `S(P)=median(T(1))/median(T(P))`; efficiency `E(P)=S(P)/P`. P=1 baseline may have different topology, note this.
- Solver speed ratio `T_jacobi(P)/T_cg(P)` for matching problem/solver tolerance (ratio >1 means CG faster).
- `compute_fraction = compute/(compute+halo+reductions)`; `halo_fraction`, `reduction_fraction`, `communication_fraction` on the **critical rank**; preserve `other` separately.
- Solver work `iterations_total` (across fixed number of physical steps) and mean iteration wall time.
- Observed crossover (first tested P where median `comm > compute`, conditional on lower-P compute dominance); give a bracket or `not observed`.
- Optional performance model: local stencil cost `O(N²/P)`, halo cells per rank `O(N/sqrt(P))` for approximately square decomposition, plus reduction latency/global synchronization. Clearly distinguish volume scaling from actual elapsed MPI time.

### Required figure generation (Matplotlib, default non-hardcoded styling)

All plots: clear titles, axis labels with units, legends, grid resolution and topology subtitles, readable fonts, and 200+ DPI PNG plus PDF/SVG when possible. Save raw plotted data to `data/processed/` and annotate trial count. Never put fake curves on real-data figures.

1. `strong_scaling_runtime`: median wall clock vs P; 1 panel/facet or separate lines for both solvers, for N=512 and 1024; logarithmic P axis if helpful.
2. `strong_scaling_speedup`: speedup vs P and an ideal `S=P` reference.
3. `strong_scaling_efficiency`: parallel efficiency vs P, with definition.
4. `communication_breakdown`: stacked bars for **critical-rank** compute, halo, reductions, other per solver at N=1024; each stack corresponds to actual same-rank time and should approximately equal total.
5. `communication_fraction`: communication fraction vs P for both solvers and N sizes; draw 0.5 line and label any observed crossover bracket or `not observed`.
6. `iterations_vs_processes`: solver iterations vs P; highlight differences or surprising variance. This is essential for interpreting time-to-solution differences.
7. `solve_time_comparison`: side-by-side or ratio chart (Jacobi vs CG) for matched N/P.
8. `temperature_snapshots`: representative initial and final temperature heatmaps (same color limits, axis coordinates, boundary context) for a small or manageable domain, generated from actual field data (visual aid, not a performance result).
9. Optional `weak_scaling`: time per solver iteration AND end-to-end time vs P.
10. Optional `timestep_sensitivity`: `r` vs iterations, runtime and communication fraction, distinctly labeled.

**Crossover analysis:** Produce `results/crossover_summary.csv` with `solver,N,topology,P_low,P_high,crossover_status,median_comm_fraction_at_each_P` and flags for uncertain/noisy results. P=1 has no inter-rank halo traffic, although calls involving `MPI_PROC_NULL` and size-1 collectives can still have measurable local overhead; compute dominance is not guaranteed by construction. P=1 is not an inter-node communication measurement. A P=1-to-P=2 bracket also crosses a topology change and cannot isolate node count from process count.

## 11. Automated conclusion and reporting logic (no hallucinated results)

`make_report.py` must read actual cleaned outputs and generate:

- `results/findings.md`: plain-language answers to these questions, each supported by measured numbers and a linked plot:
  1. Which solver has lower total runtime for each grid size? Quantify ratio and state uncertainty.
  2. How does solver iteration count compare? Why can't per-iteration speed alone determine time to solution?
  3. For **each solver**, does communication exceed compute in tested range? At what measured P bracket, if any? Note halos vs reductions.
  4. Does the crossover shift to larger P for a larger grid? Show observed evidence; don't force the expected trend.
  5. Does performance degrade when moving from one to multiple nodes, where comparable data exist?
  6. What is the strongest limitation of these experiments (e.g., insufficient P range, noisy measurements, finite node count, different solver communication patterns, Jacobi check interval, fixed-r not fixed-time)?
- `report/report.md`: concise 2–4-page-equivalent short paper: objective and hypothesis; model/discretization; two solver algorithms; parallel decomposition; measurement and hardware setup; validation; graphs and results; discussion answering instructor's bottleneck question; limitations and reproducibility. Include mathematical equations and exact tested configurations. Render PDF if tools available; don't fail the whole pipeline if PDF tools are missing.
- `slides/presentation.pptx` using `python-pptx` if available (otherwise Markdown slides): 7–9 slides: problem/motivation; implicit discretization; Jacobi vs CG; parallel domain-decomposition diagram; methodology/hardware; runtime/speedup; breakdown/crossover; accuracy/temperature heatmap; takeaway/limitations. Use generated plots; generate an **original simple 2x2 rank-grid halo-exchange schematic**, not a stock image.
- `results/STATUS.md`: list completed versus missing experiments/figures, missing tools/environment issues, and exact next commands.

All generated narrative must be conditional on observed data. If a run or entire cluster access is missing, say `not measured` and omit unsupported numerical claims; use placeholders only if unmistakably labeled **PENDING DATA**, never unlabeled. Do not conclude that one solver is faster or that communication dominates merely because theory predicts it.

## 12. Execution sequence and checkpoints

Work in this order, stopping at each correctness gate and fixing defects before moving on:

**Phase 1 — Skeleton and numerical correctness**
1. Create repository, CMake build, CLI, config and documentation.
2. Implement MPI process grid and ghost-cell exchange; test odd grids and P=1,2,3,4.
3. Implement `apply_A`, Jacobi and CG; serial SciPy reference and true residual validation.
4. Run tests, establish correct analytical heat behavior; save a small initial/final heatmap.

**Phase 2 — Measurement instrumentation**
5. Add precise per-rank compute/halo/reduction/total timing and operation counters without extra per-iteration barriers.
6. Add JSON schema, run metadata, deterministic output names, aggregation scripts, failure handling.
7. Verify measurements are consistent on 1 and several ranks, including two nodes if available.

**Phase 3 — Required experiments**
8. Run core strong-scaling matrix (both solvers, N=512 and 1024, P=1..16/32, 3–5 repeats).
9. Validate all runs and clean CSV; inspect outliers/placement. Repeat only clearly compromised runs with notes.
10. Generate figures 1–8 and crossover table; ensure all graphs trace to raw records.

**Phase 4 — Interpretation and deliverables**
11. Write data-grounded findings and report. Create presentation deck from actual plots.
12. Run an automated end-to-end reproducibility check from clean checkout if feasible.
13. If time remains, add weak scaling, r sensitivity, or one-vs-two-node comparison **one at a time**; update report with observed results.

### Stop rules / priority

- **Must finish:** correct implicit discretization, correct parallel Jacobi+CG, true-residual test, at least two N values and multiple P values, timing decomposition, compute/communication crossover analysis, 4–6 core performance graphs, short report, presentation.
- **Do not jeopardize MVP to add:** preconditioners, direct solvers, MPI derived datatypes, sophisticated overlap, arbitrary boundary conditions, elaborate dashboards, or dozens of weak-scaling cases.
- If Jacobi is prohibitively slow at a chosen setting, record that accurately and restrict larger-N settings to a feasible smaller r/tolerance **only when explicitly logged**; do not secretly change conditions within the solver comparison.

## 13. Final acceptance checklist

- [ ] Builds in Release mode and runs with 1, 2, 4 MPI ranks on a development machine or cluster.
- [ ] Both solvers implement the identical Backward Euler matrix-free system and tolerance.
- [ ] Tests cover MPI halo indexing, physical boundary conditions, nondivisible N/P, and true residual.
- [ ] Parallel results agree with an independent small-grid serial reference.
- [ ] All measured data arise from actual MPI runs; system metadata and placement recorded.
- [ ] Strong-scaling plots with real repeated timings for Jacobi and CG.
- [ ] Separate halo and collective time analysis plus clearly defined compute/communication crossover for each solver.
- [ ] Rankings and conclusions are data-driven; uncertainty and `no observed crossover` cases handled.
- [ ] Consistent heatmap visual, clean short report, and presentable slide deck.
- [ ] README includes local quickstart, Slurm run commands, experiment matrix and one-command plot/report regeneration.
- [ ] If not all measurements could be run, STATUS documents exactly what remains; no fabricated data.

## 14. Immediate actions for the agent

Start by inspecting `mpicxx --version`, `cmake --version`, `python --version`, available MPI launchers, and any existing repository contents. Implement the minimum functioning code and run tiny local/MPI correctness tests immediately. Next instrument timers and generate a tiny *real* smoke-test dataset and one real plot to verify the full pipeline. Only then submit larger Slurm jobs. Report any unavailable cluster access or tools precisely and provide the commands needed to finish there. When you complete a phase, show file paths and test commands/results instead of broad claims.
