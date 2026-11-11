#!/usr/bin/env python3
"""Run the pilot or core matrix inside an existing Slurm allocation."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('pilot', 'core'), default='pilot')
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.repeats < 1 or args.timeout < 1:
        parser.error('repeats and timeout must be positive')
    out = Path(args.output_dir)
    if not args.dry_run:
        out.mkdir(parents=True, exist_ok=True)
    ns = (128,) if args.mode == 'pilot' else (512, 1024)
    ps = (1, 2, 4) if args.mode == 'pilot' else (1, 2, 4, 8, 16, 32)
    failures = 0
    for n in ns:
        for p in ps:
            for trial in range(1, args.repeats+1):
                for solver in (('jacobi', 'cg') if trial % 2 else ('cg', 'jacobi')):
                    name = f'{solver}_N{n}_P{p}_trial{trial}'
                    path = out / f'{name}.json'
                    mapping = ['--map-by', 'core'] if p == 1 else ['--map-by', f'ppr:{p//2}:node']
                    cmd = ['mpirun', '--bind-to', 'core', *mapping, '-np', str(p),
                           str(ROOT/'build'/'implicit_heat'), '--N', str(n), '--solver', solver,
                           '--steps', '5', '--r', '2', '--tol', '1e-8', '--trial', str(trial)]
                    if args.dry_run:
                        print(' '.join(cmd), flush=True)
                        continue
                    if path.exists():
                        print(f'SKIP existing {path}', flush=True)
                        continue
                    print(f'RUN {name}', flush=True)
                    record = {'status': 'failed', 'reason_if_failed': 'unknown'}
                    try:
                        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
                        if proc.stdout.strip():
                            record = json.loads(proc.stdout.strip().splitlines()[-1])
                        if proc.returncode:
                            record['status'] = 'failed'
                            record['reason_if_failed'] = f'exit {proc.returncode}'
                        if record.get('status') == 'ok' and len(set(record['hostname_by_rank'])) != (1 if p == 1 else 2):
                            record['status'] = 'failed'
                            record['reason_if_failed'] = 'unexpected node placement'
                        (out / f'{name}.stderr.txt').write_text(proc.stderr, encoding='utf-8')
                    except (subprocess.TimeoutExpired, ValueError, KeyError) as exc:
                        record = {'status': 'failed', 'reason_if_failed': str(exc)}
                    record.update({'run_id': name, 'timestamp_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                   'slurm_job_id': os.environ.get('SLURM_JOB_ID'), 'command': cmd})
                    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=out, delete=False) as tmp:
                        json.dump(record, tmp, indent=2, allow_nan=False)
                        tmp.write('\n')
                    os.replace(tmp.name, path)
                    if record['status'] != 'ok':
                        failures += 1
                        print(f'FAILED {name}: {record.get("reason_if_failed")}', flush=True)
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
