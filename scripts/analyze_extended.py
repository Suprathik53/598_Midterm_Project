#!/usr/bin/env python3
"""Summarize extended measurements without overwriting the original study."""
import argparse
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
from statistics import median
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument('raw', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
groups, failures = defaultdict(list), []
for path in sorted(args.raw.glob('*.json')):
    try:
        x = json.loads(path.read_text(encoding='utf-8'))
        if (x.get('status') != 'ok' or x['steps_completed'] != 5 or x['residual_rel_max'] > x['tol'] or
            len(set(x['hostname_by_rank'])) != (1 if x['P'] == 1 else 2) or
            any(not math.isfinite(x[k]) or x[k] < 0 for k in ('compute_s', 'halo_s', 'reduction_s', 'solve_total_s'))):
            failures.append((path.name, x.get('reason_if_failed', 'invalid record')))
            continue
        groups[(x['study'], x['solver'], x['N'], x['P'], x['r'])].append(x)
    except (ValueError, KeyError, ZeroDivisionError) as e:
        failures.append((path.name, str(e)))

rows = []
for (study, solver, n, p, r), records in sorted(groups.items()):
    times = [x['solve_total_s'] for x in records]
    fractions = [(x['halo_s']+x['reduction_s'])/(x['compute_s']+x['halo_s']+x['reduction_s']) for x in records]
    iterations = [x['iteration_total'] for x in records]
    rows.append(dict(study=study, solver=solver, N=n, P=p, r=r, trials=len(records),
                     median_s=median(times), min_s=min(times), max_s=max(times),
                     median_comm_fraction=median(fractions), min_comm_fraction=min(fractions), max_comm_fraction=max(fractions),
                     median_iterations=median(iterations), median_s_per_iteration=median([t/i for t,i in zip(times,iterations) if i])))
if not rows:
    raise SystemExit('No valid data')
with (args.output/'summary.csv').open('w', newline='', encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=rows[0]); w.writeheader(); w.writerows(rows)
(args.output/'failures.json').write_text(json.dumps(failures,indent=2)+'\n',encoding='utf-8')

for study, xkey, ykeys in [('strong','P',('median_s','median_comm_fraction')),
                            ('weak','P',('median_s','median_s_per_iteration')),
                            ('timestep','r',('median_s','median_iterations','median_comm_fraction'))]:
    subset = [row for row in rows if row['study']==study]
    if not subset: continue
    fig, axes = plt.subplots(1,len(ykeys),figsize=(6*len(ykeys),4.6),squeeze=False)
    keys = sorted({(v['solver'],v['N'] if study != 'weak' else None) for v in subset})
    for solver,n in keys:
        series=sorted([v for v in subset if v['solver']==solver and (n is None or v['N']==n)],key=lambda v:v[xkey])
        for ax,y in zip(axes[0],ykeys):
            ax.plot([v[xkey] for v in series],[v[y] for v in series],marker='o',label=f'{solver}'+(f', N={n}' if n else ', local 256×256'))
            if y=='median_s':
                ax.fill_between([v[xkey] for v in series],[v['min_s'] for v in series],[v['max_s'] for v in series],alpha=.12)
            if y=='median_comm_fraction': ax.axhline(.5,color='black',ls='--',lw=.8)
            ax.set(xlabel=xkey,ylabel=y.replace('_',' '),title=f'{study}: {y.replace("_"," ")}')
            ax.grid(alpha=.3); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(args.output/f'{study}.png',dpi=220); plt.close(fig)
print(f'{len(rows)} groups, {sum(len(x) for x in groups.values())} valid runs, {len(failures)} invalid/failed')
