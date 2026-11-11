# Implicit heat: Jacobi vs CG

2D backward Euler • MPI scaling study

When does measured MPI time overtake local computation?

---

# Model and methods

Unit square, zero boundaries; five-point backward Euler system.

Both solvers use the same initial field, matrix and true-residual tolerance.

Jacobi checks every 10 updates; CG uses global reductions each iteration.

---

# Parallel decomposition and validation

![2D rank decomposition](../figures/domain_decomposition.png)

Serial reference, analytic refinement, halo tests, true residual and critical-rank diagnostics passed.

---

# Experiment

N=512 and 1024; 1–64 ranks; five trials per configuration.

Two exclusive AMD EPYC 7713 nodes; one node at P=1, two at P≥2.

Five measured steps after reset warm-up; fixed r=2 in strong scaling.

---

# Strong scaling and crossover

![Strong scaling and communication fraction](../results/extended-analysis-12312735/strong.png)

Communication crossover: N=512 between 16–24 ranks; N=1024 between 48–64 ranks, for both solvers.

---

# Weak scaling

![Weak scaling results](../results/extended-analysis-12312735/weak.png)

256×256 cells per rank; update counts change with grid size.

---

# Timestep sensitivity

![Timestep sensitivity results](../results/extended-analysis-12312735/timestep.png)

Larger r increases the work to solve each implicit step; this is not an equal-physical-time comparison.

---

# Temperature field

![Initial and final field](../figures/temperature_snapshots.png)

Visualization from a separate small measured run; shared color scale.

---

# Conclusions and limitations

CG was faster in every tested strong-scaling configuration.

For N=1024, both solvers were communication-dominated at 64 ranks, while total time still decreased.

MPI time includes waiting; five nearby trials and the P=1 topology change limit generalization.
