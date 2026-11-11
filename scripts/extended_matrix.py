#!/usr/bin/env python3
"""Measured extended studies, run inside a two-node Slurm allocation."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
cases = []
for n in (512, 1024):
    for p in (1, 2, 4, 8, 16, 24, 32, 48, 64):
        cases.append(('strong', n, p, 2.0))
for n, p in ((256, 1), (512, 4), (1024, 16), (2048, 64)):
    cases.append(('weak', n, p, 2.0))
for n in (512, 1024):
    for r in (0.5, 2.0, 8.0):
        cases.append(('timestep', n, 16, r))

failures = 0
for study, n, p, r in cases:
    for trial in range(1, 6):
        for solver in (('jacobi', 'cg') if trial % 2 else ('cg', 'jacobi')):
            name = f'{study}_{solver}_N{n}_P{p}_r{r:g}_trial{trial}'
            path = out / (name + '.json')
            if path.exists():
                print(f'SKIP {name}', flush=True)
                continue
            mapping = ['--map-by', 'core'] if p == 1 else ['--map-by', f'ppr:{p//2}:node']
            cmd = ['mpirun', '--bind-to', 'core', *mapping, '-np', str(p),
                   str(root/'build'/'implicit_heat'), '--N', str(n), '--solver', solver,
                   '--steps', '5', '--r', str(r), '--tol', '1e-8', '--trial', str(trial)]
            print('RUN', name, flush=True)
            record = {'status': 'failed', 'reason_if_failed': 'unknown'}
            stderr = ''
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                stderr = proc.stderr
                if proc.stdout.strip():
                    record = json.loads(proc.stdout.strip().splitlines()[-1])
                if proc.returncode:
                    record.update(status='failed', reason_if_failed=f'exit {proc.returncode}')
                elif record.get('status') != 'ok':
                    record['reason_if_failed'] = 'solver reported nonconvergence'
                elif len(set(record['hostname_by_rank'])) != (1 if p == 1 else 2):
                    record.update(status='failed', reason_if_failed='unexpected node placement')
                elif record['steps_completed'] != 5 or record['residual_rel_max'] > record['tol']:
                    record.update(status='failed', reason_if_failed='incomplete or invalid residual')
            except (subprocess.TimeoutExpired, ValueError, KeyError) as exc:
                record = {'status': 'failed', 'reason_if_failed': str(exc)}
                if isinstance(exc, subprocess.TimeoutExpired):
                    stderr = str(exc.stderr or '')
            (out/(name+'.stderr.txt')).write_text(stderr, encoding='utf-8')
            record.update(study=study, run_id=name, timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                          slurm_job_id=os.environ.get('SLURM_JOB_ID'), command=cmd)
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=out, delete=False) as f:
                json.dump(record, f, indent=2, allow_nan=False)
                f.write('\n')
            os.replace(f.name, path)
            if record['status'] != 'ok':
                failures += 1
                print('FAILED', name, record.get('reason_if_failed'), flush=True)
print(f'Finished: {failures} failures', flush=True)
raise SystemExit(bool(failures))
