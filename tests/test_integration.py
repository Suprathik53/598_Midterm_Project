#!/usr/bin/env python3
"""Small MPI correctness checks; execute inside a compute-node allocation."""
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

EXE = Path(__file__).resolve().parents[1] / 'build' / 'implicit_heat'
MPI = os.environ.get('MPIEXEC', 'mpirun')


def run(p, solver, n=17, init='gaussian', extra=(), success=True):
    with tempfile.TemporaryDirectory() as d:
        field = Path(d) / 'field.csv'
        cmd = [MPI, '-np', str(p), str(EXE), '--N', str(n), '--steps', '2',
               '--warmup-steps', '0', '--solver', solver, '--init', init,
               '--tol', '1e-10', '--dump-field', str(field), *extra]
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=90)
        if success:
            assert result.returncode == 0, (cmd, result.stdout, result.stderr)
            record = json.loads(result.stdout.strip().splitlines()[-1])
            values = [float(v) for row in field.read_text().splitlines() for v in row.split(',')]
            assert record['status'] == 'ok' and record['residual_rel_max'] <= record['tol']
            assert abs(record['solve_total_s'] - sum(record[k] for k in ('compute_s', 'halo_s', 'reduction_s', 'other_s'))) < 1e-9
            return record, values
        assert result.returncode != 0, (cmd, result.stdout, result.stderr)


def serial_reference(n, steps, r=2.0):
    """Independent dense Gaussian elimination, intentionally only for tiny grids."""
    count = n*n
    h = 1/(n+1)
    b = []
    for i in range(n):
        for j in range(n):
            x, y = (i+1)*h, (j+1)*h
            b.append(math.sin(math.pi*x)*math.sin(math.pi*y) *
                     (0.25 + 1.1*math.exp(-((x-.30)**2+(y-.35)**2)/.012) +
                      .65*math.exp(-((x-.74)**2+(y-.63)**2)/.006)))
    a = [[0.0]*count for _ in range(count)]
    for i in range(n):
        for j in range(n):
            k = i*n+j
            a[k][k] = 1+4*r
            for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ii, jj = i+di, j+dj
                if 0 <= ii < n and 0 <= jj < n:
                    a[k][ii*n+jj] = -r
    for _ in range(steps):
        rows = [row[:] + [value] for row, value in zip(a, b)]
        for k in range(count):
            for i in range(k+1, count):
                scale = rows[i][k] / rows[k][k]
                for j in range(k, count+1):
                    rows[i][j] -= scale*rows[k][j]
        b = [0.0]*count
        for i in reversed(range(count)):
            b[i] = (rows[i][-1] - sum(rows[i][j]*b[j] for j in range(i+1, count))) / rows[i][i]
    return b


def independent_residual(values, n, r=2.0):
    """Recompute ||b-Ax||/||b|| from the dumped one-step solution."""
    b = []
    for i in range(n):
        for j in range(n):
            x, y = (i+1)/(n+1), (j+1)/(n+1)
            b.append(math.sin(math.pi*x)*math.sin(math.pi*y) *
                     (0.25 + 1.1*math.exp(-((x-.30)**2+(y-.35)**2)/.012) +
                      .65*math.exp(-((x-.74)**2+(y-.63)**2)/.006)))
    residual = []
    for i in range(n):
        for j in range(n):
            k = i*n+j
            neighbors = sum(values[ii*n+jj] for ii, jj in
                            ((i-1,j), (i+1,j), (i,j-1), (i,j+1))
                            if 0 <= ii < n and 0 <= jj < n)
            residual.append(b[k] - ((1+4*r)*values[k] - r*neighbors))
    return math.sqrt(sum(v*v for v in residual)/sum(v*v for v in b))


def main():
    for solver in ('jacobi', 'cg'):
        reference = None
        for p in (1, 2, 3, 4):
            rec, values = run(p, solver)
            if reference is None:
                reference = values
            assert max(abs(a-b) for a, b in zip(reference, values)) < 1e-9
            initial_peak = max(math.sin(math.pi*(i+1)/18)*math.sin(math.pi*(j+1)/18) *
                               (0.25 + 1.1*math.exp(-(((i+1)/18-.30)**2+((j+1)/18-.35)**2)/.012) +
                                .65*math.exp(-(((i+1)/18-.74)**2+((j+1)/18-.63)**2)/.006))
                               for i in range(17) for j in range(17))
            assert min(values) >= -1e-10 and max(values) <= initial_peak + 1e-10
            print(f'PASS {solver} nondivisible N=17 P={p}, iterations={rec["iteration_total"]}', flush=True)
        n = 8
        rec, values = run(4, solver, n=n, init='sine')
        factor = (1 + 8 * 2.0 * math.sin(math.pi / (2*(n+1)))**2)**-2
        exact = [factor * math.sin(math.pi*(i+1)/(n+1)) * math.sin(math.pi*(j+1)/(n+1)) for i in range(n) for j in range(n)]
        assert max(abs(a-b) for a, b in zip(values, exact)) < 1e-9
        print(f'PASS {solver} discrete analytic sine', flush=True)
        _, values = run(3, solver, n=6)
        reference = serial_reference(6, 2)
        assert max(abs(a-b) for a, b in zip(values, reference)) < 1e-9
        print(f'PASS {solver} independent dense serial solve', flush=True)
        rec, values = run(4, solver, n=17, extra=('--steps', '1'))
        residual = independent_residual(values, 17)
        assert residual <= 1e-10 and abs(residual-rec['residual_rel_max']) < 1e-14
        print(f'PASS {solver} independently recomputed true residual: {residual}', flush=True)
        rec, values = run(2, solver, n=8, init='zero')
        assert rec['iteration_total'] == 0 and max(map(abs, values)) == 0
        print(f'PASS {solver} zero RHS', flush=True)
        rec, values = run(2, solver, n=8, init='sine', extra=('--tol', '10'))
        assert rec['iteration_total'] == 0 and max(values) > 0
        print(f'PASS {solver} initially converged nonzero RHS', flush=True)
        _, values = run(4, solver, n=2)
        reference = serial_reference(2, 2)
        assert max(abs(a-b) for a, b in zip(values, reference)) < 1e-9
        print(f'PASS {solver} single-cell rank blocks', flush=True)
        run(2, solver, n=17, extra=('--max-iter', '1'), success=False)
        print(f'PASS {solver} nonconvergence', flush=True)
        rec, _ = run(1, solver, n=1, init='sine', extra=('--max-iter', '1'))
        assert rec['iteration_total'] == 2
        print(f'PASS {solver} convergence on final allowed update', flush=True)
        errors = []
        for n, steps in ((7, 4), (15, 16), (31, 64)):
            _, values = run(2, solver, n=n, init='sine', extra=('--steps', str(steps)))
            decay = math.exp(-2*math.pi**2 * .125)
            exact = [decay*math.sin(math.pi*(i+1)/(n+1))*math.sin(math.pi*(j+1)/(n+1)) for i in range(n) for j in range(n)]
            errors.append(math.sqrt(sum((a-b)**2 for a, b in zip(values, exact))/len(values)))
        assert errors[0] > errors[1] > errors[2], errors
        print(f'PASS {solver} fixed-time continuous refinement: {errors}', flush=True)
    run(2, 'cg', n=1, success=False)
    for option, value in (('--N', '0'), ('--r', '0'), ('--r', 'nan'),
                          ('--tol', '-1'), ('--tol', 'nan'), ('--max-iter', '0'),
                          ('--jacobi-check-every', '0'), ('--steps', '0'),
                          ('--alpha', '0'), ('--warmup-steps', '-1')):
        run(2, 'cg', n=8, extra=(option, value), success=False)
    print('PASS invalid decomposition and arguments on multiple ranks', flush=True)
    print('All integration tests passed.', flush=True)


if __name__ == '__main__':
    main()
