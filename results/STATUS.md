# Project and experiment status

The required comparison, strong-scaling measurements, analysis, short report and presentation are complete for the experiment described below. The original instructor prompt was not present in the workspace, so its exact rubric and submission format still need to be checked by the course participants.

## Validation

`validation-12297025.log` contains the final cluster test run: both solvers passed independent dense serial comparison, uneven 1–4-rank decompositions, a discrete analytic sine solution, fixed-final-time refinement, zero RHS, convergence at the iteration cap, intentional nonconvergence and invalid inputs. Every benchmark solve also checked its independently recomputed true residual; the maximum recorded value was 9.728e-9 for a 1e-8 tolerance.

`validation-12312539.log` records a later successful cluster rerun using the unchanged solver source and expanded tests. Direct stencil tests cover 1–4 ranks, uneven blocks, physical boundaries and both Cartesian grid orientations. Integration tests additionally cover a nonzero initially converged guess, single-cell blocks on four ranks, more invalid arguments on multiple ranks, and an independent Python recomputation of the returned field's true residual. The special case where a CG recursive residual passes but the true residual fails has not been directly tested; the solver does not expose the recursive residual. Detailed independent verification of per-rank timing selection also remains untested because per-rank records are not retained.

`validation-12312723.log` records additional passing diagnostics using a separate `HEAT_DIAGNOSTICS` build, which gathers per-rank timings after the timed solves. For both solvers, the selected ranks and component sums matched independent selection from those records. A CG test with tolerance 1e-15 measured a recursive residual of 6.01e-16 and true residual of 2.86e-15, and correctly returned nonconvergence. This later diagnostic supersedes the two coverage gaps noted in the preceding paragraph; the original benchmark data themselves do not contain per-rank records or recursive residuals.

## Primary study

`core-12297017/` contains 72 successful records: two solvers, N=512 and 1024, P=1,2,4,8,16,32, three repetitions, five time steps and a reset warm-up. For P>=2, hostnames confirm two nodes. The exclusive allocation used ccc0391 and ccc0392, both AMD EPYC 7713 nodes; per-node hardware, versions, source/binary hashes, stderr and job log are preserved alongside the records. The original local source hash matched the recorded experiment hash before later diagnostic-only conditional instrumentation was added; the current source hash is therefore different.

`core-12296980/` is an earlier full run on one AMD and one Intel node. It is deliberately excluded from the primary analysis because heterogeneous computation can confound the MPI-time breakdown. `pilot-12296889/` is a single-repetition test of the execution pipeline, not a final result. `fields/` contains the separately measured visualization snapshot.

## Extended study completed

Slurm job `12312735` completed from `~/implicit-heat-extended-20261110` after successful validation: 280 successful validated records, five repetitions per case, on two exclusive AMD nodes. Data are under `data/extended-12312735/`, and `extended-analysis-12312735/` contains a separate summary, figures and findings. The study includes strong scaling for N=512 and 1024 at P=1,2,4,8,16,24,32,48,64, weak scaling at (N,P)=(256,1),(512,4),(1024,16),(2048,64), and r=0.5,2,8 at N=512,1024 and P=16, for both solvers. Regenerate the analysis with `python scripts/analyze_extended.py results/data/extended-12312735 --output results/extended-analysis-12312735`. The extended runs use an uninstrumented release executable built from the later source with diagnostic-only code disabled; do not silently merge them with the original allocation. The report and presentation now summarize the extended study; render their PDFs using `python scripts/render_pdf.py`.

## Outputs and limitations

- `summary.csv`, `crossover_summary.csv`, `findings.md`: measured statistics and caveats.
- `../figures/`: runtime, speedup, efficiency, iteration, solver-ratio, timing-breakdown, communication-fraction, field, and process-grid graphics.
- `../report/report.md` and `.pdf`; `../slides/presentation.md` and `.pdf`.
- `../README.md` contains build, run and regeneration commands.

MPI call time includes waiting/load imbalance and does not isolate network transfer. P=1 uses one node while P>=2 uses two, so topology and rank-count changes are confounded. In the original study, two timing groups have CV >10% across three repetitions; retain and interpret their full ranges. Repetitions within an allocation do not capture day-to-day variance. Fixed r changes physical timestep with N. The recorded timing breakdown aggregates each step's critical rank but does not retain per-step component timings or all-rank distributions; recursive CG residuals were not separately retained. Weak scaling and timestep sensitivity were subsequently measured in the extended study; one-node vs two-node controls and communication overlap were not run. Markdown/PDF slides are provided rather than PPTX.
