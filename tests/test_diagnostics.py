#!/usr/bin/env python3
"""Diagnostic-only tests; never use the instrumented executable for benchmarks."""
import json
import math
import os
from pathlib import Path
import subprocess

exe = Path(__file__).resolve().parents[1] / 'build' / 'implicit_heat_diagnostics'
mpi = os.environ.get('MPIEXEC', 'mpirun')


def run(solver, tol, steps=3):
    cmd = [mpi, '-np', '4', str(exe), '--N', '17', '--steps', str(steps),
           '--warmup-steps', '0', '--solver', solver, '--tol', str(tol)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    record = json.loads(p.stdout.strip().splitlines()[-1])
    data = {}
    for line in p.stderr.splitlines():
        if line.startswith('DIAG '):
            parts = line.split()
            data.setdefault(int(parts[1]), {})[int(parts[2])] = list(map(float, parts[3:]))
    return p, record, data


for solver in ('jacobi', 'cg'):
    proc, rec, data = run(solver, 1e-8)
    assert proc.returncode == 0 and len(data) == 3
    sums = [0.0]*5
    for step, ranks in sorted(data.items()):
        assert len(ranks) == 4
        critical = min(ranks, key=lambda rank: (-ranks[rank][0], rank))
        assert critical == rec['critical_ranks'][step]
        total, compute, halo, reduction = ranks[critical][:4]
        for i, value in enumerate((total, compute, halo, reduction, total-compute-halo-reduction)):
            sums[i] += value
    for key, value in zip(('solve_total_s', 'compute_s', 'halo_s', 'reduction_s', 'other_s'), sums):
        assert math.isclose(rec[key], value, rel_tol=1e-12, abs_tol=1e-12), (key, rec[key], value)
    print(f'PASS {solver} critical-rank timing against gathered per-rank records', flush=True)

for tol in (1e-15, 1e-16, 1e-17, 1e-18, 1e-19, 1e-20):
    proc, rec, data = run('cg', tol, steps=1)
    recursive, true = data[0][0][4:]
    if recursive <= tol < true:
        assert proc.returncode != 0 and rec['status'] == 'nonconverged'
        print(f'PASS CG rejects recursive/true mismatch: tol={tol}, recursive={recursive}, true={true}', flush=True)
        break
else:
    raise AssertionError('No recursive/true residual mismatch found in tested tolerances')
