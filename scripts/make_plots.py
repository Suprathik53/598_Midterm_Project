#!/usr/bin/env python3
"""Plot measured successful JSON runs only. Requires matplotlib."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import median
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('raw_dir', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    data = defaultdict(list)
    failed = 0
    for path in sorted(args.raw_dir.glob('*.json')):
        rec = json.loads(path.read_text(encoding='utf-8'))
        if rec.get('status') != 'ok':
            failed += 1
            continue
        data[(rec['solver'], rec['N'], rec['P'])].append(rec)
    if not data:
        raise SystemExit('No successful measurements found.')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for metric, filename, ylabel in (('solve_total_s', 'runtime.png', 'Solver time (s)'),
                                     ('iteration_total', 'iterations.png', 'Total iterations'),
                                     ('communication_fraction', 'communication_fraction.png', 'MPI / (compute + MPI)')):
        fig, ax = plt.subplots()
        for solver, n in sorted({(s, n) for s, n, _ in data}):
            ps = sorted(p for s, nn, p in data if s == solver and nn == n)
            def value(rec):
                if metric != 'communication_fraction':
                    return rec[metric]
                comm = rec['halo_s'] + rec['reduction_s']
                return comm/(comm + rec['compute_s'])
            ax.plot(ps, [median(value(r) for r in data[(solver, n, p)]) for p in ps], marker='o', label=f'{solver}, N={n}')
        if metric == 'communication_fraction':
            ax.axhline(.5, color='gray', linestyle='--')
        ax.set(xlabel='MPI ranks', ylabel=ylabel, title=f'Median measured runs ({failed} failed excluded)')
        ax.grid(True, alpha=.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(args.output_dir / filename, dpi=200)
        plt.close(fig)
    print(f'Plotted {sum(map(len, data.values()))} runs; {failed} failures excluded.')


if __name__ == '__main__':
    main()
