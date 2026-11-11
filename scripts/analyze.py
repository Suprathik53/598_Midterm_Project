#!/usr/bin/env python3
"""Analyze measured solver records; no synthetic performance observations."""
import argparse
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
from statistics import median, stdev, mean
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def save(fig, path):
    fig.tight_layout()
    fig.savefig(path.with_suffix('.png'), dpi=220)
    fig.savefig(path.with_suffix('.pdf'))
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('raw', type=Path)
    parser.add_argument('--snapshot', type=Path)
    args = parser.parse_args()
    grouped = defaultdict(list)
    failures = []
    for file in sorted(args.raw.glob('*.json')):
        record = json.loads(file.read_text(encoding='utf-8'))
        if record.get('status') != 'ok':
            failures.append((file.name, record.get('reason_if_failed', record.get('status'))))
            continue
        if record['residual_rel_max'] > record['tol'] or record['steps_completed'] != record['steps_requested']:
            failures.append((file.name, 'invalid residual or incomplete run'))
            continue
        if len(set(record['hostname_by_rank'])) != (1 if record['P']==1 else 2):
            failures.append((file.name, 'unexpected node count'))
            continue
        if not all(math.isfinite(record[k]) and record[k] >= 0 for k in ('solve_total_s','compute_s','halo_s','reduction_s')):
            failures.append((file.name, 'invalid timing'))
            continue
        grouped[(record['solver'], record['N'], record['P'])].append(record)
    if not grouped:
        raise SystemExit('No valid results to analyze')
    figures, results = ROOT/'figures', ROOT/'results'
    figures.mkdir(exist_ok=True); results.mkdir(exist_ok=True)
    rows = []
    for (solver, n, p), runs in sorted(grouped.items()):
        for field in ('r','alpha','tol','steps_requested','init','jacobi_check_every'):
            if len({r[field] for r in runs}) != 1:
                raise SystemExit(f'Inconsistent {field} in {(solver, n, p)}; do not mix experiments')
        times = [r['solve_total_s'] for r in runs]
        fractions = [(r['halo_s']+r['reduction_s'])/(r['compute_s']+r['halo_s']+r['reduction_s']) for r in runs]
        rows.append(dict(solver=solver, N=n, P=p, trials=len(runs), median_s=median(times), min_s=min(times), max_s=max(times),
                         cv=stdev(times)/mean(times) if len(times)>1 else 0, median_iterations=median(r['iteration_total'] for r in runs),
                         median_comm_fraction=median(fractions), min_comm_fraction=min(fractions), max_comm_fraction=max(fractions)))
    with (results/'summary.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    bykey = {(r['solver'], r['N'], r['P']):r for r in rows}
    curves = sorted({(r['solver'], r['N']) for r in rows})
    def lineplot(name, ylabel, fn, baseline=False, threshold=False):
        fig, ax = plt.subplots(figsize=(7.2,4.8))
        for solver,n in curves:
            rr = sorted([r for r in rows if r['solver']==solver and r['N']==n], key=lambda r:r['P'])
            base=bykey.get((solver,n,1));
            if baseline and not base: continue
            vals=[fn(r,base) for r in rr]
            ax.plot([r['P'] for r in rr],vals,marker='o',label=f'{solver.upper()}, N={n} (n={min(r["trials"] for r in rr)})')
            if name == 'strong_scaling_runtime':
                ax.fill_between([r['P'] for r in rr],[r['min_s'] for r in rr],[r['max_s'] for r in rr],alpha=.10)
        if threshold: ax.axhline(.5,color='black',linestyle='--',linewidth=.8,label='50%')
        if name == 'strong_scaling_speedup':
            ideal=sorted({r['P'] for r in rows}); ax.plot(ideal,ideal,color='gray',linestyle=':',label='Ideal')
        if name == 'strong_scaling_efficiency': ax.axhline(1,color='gray',linestyle=':',label='Ideal')
        ax.set_xscale('log',base=2); ax.set_xticks(sorted({r['P'] for r in rows}),labels=sorted({r['P'] for r in rows}))
        ax.set(xlabel='MPI ranks (P=1: one node; P≥2: two nodes)',ylabel=ylabel); ax.grid(alpha=.25); ax.legend(fontsize=8)
        save(fig,figures/name)
    lineplot('strong_scaling_runtime','Five-solve time (s)',lambda r,b:r['median_s'])
    lineplot('strong_scaling_speedup','Speedup vs P=1',lambda r,b:b['median_s']/r['median_s'],True)
    lineplot('strong_scaling_efficiency','Efficiency vs P=1',lambda r,b:b['median_s']/r['median_s']/r['P'],True)
    lineplot('iterations_vs_processes','Total solver updates (five steps)',lambda r,b:r['median_iterations'])
    lineplot('communication_fraction','MPI / (compute + MPI)',lambda r,b:r['median_comm_fraction'],threshold=True)
    maxn=max(r['N'] for r in rows)
    fig,ax=plt.subplots(figsize=(9,5)); labels=[]; bottoms=[]; selected=[]
    for solver,n in curves:
        if n != maxn: continue
        for p in sorted({r['P'] for r in rows if r['solver']==solver and r['N']==n}):
            runs=grouped[(solver,n,p)]; target=median(r['solve_total_s'] for r in runs)
            selected.append(min(runs,key=lambda r:abs(r['solve_total_s']-target))); labels.append(f'{solver}\n{p}')
    x=np.arange(len(selected)); bottom=np.zeros(len(selected))
    for key,label in [('compute_s','Local computation'),('halo_s','Halo MPI'),('reduction_s','Allreduce MPI'),('other_s','Other')]:
        values=np.array([r[key] for r in selected]); ax.bar(x,values,bottom=bottom,label=label); bottom+=values
    ax.set(xticks=x,xticklabels=labels,ylabel='Five-solve time (s)',title=f'N={maxn}: representative median-total trial'); ax.legend(fontsize=8); save(fig,figures/'communication_breakdown')
    fig,ax=plt.subplots(figsize=(7,4.5))
    for n in sorted({r['N'] for r in rows}):
        ps=sorted(p for s,nn,p in grouped if s=='jacobi' and nn==n and ('cg',n,p) in grouped)
        ax.plot(ps,[bykey[('jacobi',n,p)]['median_s']/bykey[('cg',n,p)]['median_s'] for p in ps],marker='o',label=f'N={n}')
    ax.axhline(1,color='black',linestyle='--',linewidth=.8); ax.set_xscale('log',base=2); ax.set(xlabel='MPI ranks',ylabel='Jacobi / CG median time'); ax.legend(); ax.grid(alpha=.25); save(fig,figures/'solve_time_comparison')
    if args.snapshot:
        final=np.loadtxt(args.snapshot,delimiter=','); n=final.shape[0]; axis=np.arange(1,n+1)/(n+1); x,y=np.meshgrid(axis,axis,indexing='ij')
        initial=np.sin(np.pi*x)*np.sin(np.pi*y)*(.25+1.1*np.exp(-((x-.30)**2+(y-.35)**2)/.012)+.65*np.exp(-((x-.74)**2+(y-.63)**2)/.006))
        fig,axes=plt.subplots(1,2,figsize=(9,4),constrained_layout=True)
        for ax,field,title in zip(axes,(initial,final),('Initial field','After five steps')):
            im=ax.imshow(field.T,origin='lower',extent=(0,1,0,1),vmin=0,vmax=float(initial.max()),cmap='inferno'); ax.set(title=title,xlabel='x',ylabel='y')
        fig.colorbar(im,ax=axes,label='Temperature'); fig.savefig(figures/'temperature_snapshots.png',dpi=220); fig.savefig(figures/'temperature_snapshots.pdf'); plt.close(fig)
    # Original schematic: 2x2 blocks with representative halo traffic.
    fig,ax=plt.subplots(figsize=(5,4))
    for i in range(2):
        for j in range(2):
            ax.add_patch(plt.Rectangle((j,i),1,1,fill=False,linewidth=2))
            ax.text(j+.5,i+.5,f'Rank {2*(1-i)+j}',ha='center',va='center')
    for a,b in [((.75,1.5),(1.25,1.5)),((.75,.5),(1.25,.5)),((.5,.75),(.5,1.25)),((1.5,.75),(1.5,1.25))]:
        ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'<->','color':'tab:blue','lw':2})
    ax.set(xlim=(-.1,2.1),ylim=(-.1,2.1),title='Example: 2×2 process grid and halo exchanges'); ax.set_aspect('equal'); ax.axis('off'); save(fig,figures/'domain_decomposition')
    cross=[]
    for solver,n in curves:
        rr=sorted([r for r in rows if r['solver']==solver and r['N']==n], key=lambda r:r['P'])
        prev=None; low=high=''; status='not observed';
        for r in rr:
            if r['median_comm_fraction']>.5:
                if prev is not None: low=prev['P']; high=r['P']; status='bracketed'
                else: status='already communication-dominated at lowest P'
                break
            prev=r
        uncertain=any(r['min_comm_fraction']<=.5<r['max_comm_fraction'] for r in rr)
        cross.append(dict(solver=solver,N=n,P_low=low,P_high=high,status=status,uncertain=uncertain, fractions='; '.join(f'{r["P"]}:{r["median_comm_fraction"]:.4f} [{r["min_comm_fraction"]:.4f},{r["max_comm_fraction"]:.4f}]' for r in rr)))
    with (results/'crossover_summary.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=cross[0].keys()); writer.writeheader(); writer.writerows(cross)
    generate_documents(rows, cross, failures, args.raw, figures)
    print(f'Analyzed {sum(len(v) for v in grouped.values())} valid runs in {len(rows)} groups; {len(failures)} failures.')


def generate_documents(rows, cross, failures, raw, figures):
    bykey={(r['solver'],r['N'],r['P']):r for r in rows}
    cpu_lines=[]
    metadata=raw/'per-node-cpu.txt'
    if metadata.exists():
        cpu_lines=sorted({line.split(':',1)[1].strip() for line in metadata.read_text(encoding='utf-8').splitlines() if line.startswith('Model name:')})
    cpu_description=', '.join(cpu_lines) if cpu_lines else 'not recorded'
    lines=['# Findings (measured data)', '',f'Input: `{raw}`. {sum(r["trials"] for r in rows)} successful runs; {len(failures)} failed/invalid runs. Values are medians; ranges show trial minima and maxima.', '']
    if failures: lines += ['Failures:']+[f'- {a}: {b}' for a,b in failures]+['']
    for n in sorted({r['N'] for r in rows}):
        lines += [f'## N={n}', '']
        ps=sorted({r['P'] for r in rows if r['N']==n})
        for p in ps:
            a=bykey.get(('jacobi',n,p)); b=bykey.get(('cg',n,p))
            if a and b:
                ratio=a['median_s']/b['median_s']
                lines.append(f'- P={p}: Jacobi {a["median_s"]:.6g} s [{a["min_s"]:.6g}, {a["max_s"]:.6g}]; CG {b["median_s"]:.6g} s [{b["min_s"]:.6g}, {b["max_s"]:.6g}]; Jacobi/CG = {ratio:.3g}; iterations {a["median_iterations"]:g} vs {b["median_iterations"]:g}.')
        lines.append('')
    lines += ['## Communication crossover','']
    for c in cross:
        desc=f'between P={c["P_low"]} and P={c["P_high"]}' if c['status']=='bracketed' else c['status']
        lines.append(f'- {c["solver"]}, N={c["N"]}: {desc}; uncertainty flag (trial range crosses 0.5): {c["uncertain"]}; P: median fraction [min,max] = {c["fractions"]}.')
    lines += ['', 'Fractions are MPI call time divided by local compute plus MPI time; MPI includes waiting and imbalance, not just network transfers. The bracket is between sampled process counts, not a measured exact threshold. P=1 is on one node; P≥2 is distributed across two, so a bracket involving P=1 also changes topology. Three trials provide limited uncertainty information. See `../figures/communication_fraction.png` and `../figures/strong_scaling_runtime.png`.', '']
    noisy=[f'{r["solver"]} N={r["N"]} P={r["P"]} ({100*r["cv"]:.1f}%)' for r in rows if r['trials']>1 and r['cv']>.1]
    lines += ['Groups with time CV above 10%: '+(', '.join(noisy) if noisy else 'none in the observed trials')+'. Same-P one-node vs two-node data were not collected, so an inter-node penalty cannot be isolated.', '']
    (ROOT/'results'/'findings.md').write_text('\n'.join(lines),encoding='utf-8')
    report=['# Parallel implicit heat diffusion: Jacobi versus conjugate gradient','','## Objective','Compare time to solution, scaling, and exposed MPI time for two solvers of the same backward Euler heat equation.','','## Model and methods', 'The unit square has zero Dirichlet boundaries and an N×N interior grid. With h=1/(N+1), α=1 and r=αΔt/h²=2, each step solves (I−αΔt L_h)x=b. Matrix-free 5-point application uses a nonperiodic 2D MPI Cartesian decomposition and packed halo exchanges. Both solvers use x₀=b and a true relative residual tolerance of 10⁻⁸. Jacobi checks residual after the first update and every ten updates; CG uses two global reductions per ordinary iteration. Five time steps follow one discarded, reset warm-up. Fixed r means physical Δt varies with N.', '', '## Correctness','Cluster integration tests checked an independent dense serial reference, 1–4 ranks including uneven decomposition, exact discrete sine-mode amplification, fixed-physical-time refinement, zero input, and nonconvergence. The final true residual is verified outside timed solves. See `../results/validation-12297025.log`.', '', '## Experimental method','Three runs per configuration use N=512 and 1024, and P=1, 2, 4, 8, 16, 32 where records exist. P=1 uses one node and P≥2 is evenly spread over two, with core binding; verify actual hosts in raw JSON. The allocation is exclusive and constrained to AMD nodes; per-node CPU metadata, environment and source hashes are stored with raw data. Time is summed over per-step slowest-rank solver durations; components for each step are taken from that same rank. MPI call time includes waiting, and packing is counted as local computation. The timing decomposition is an operational measure, not hardware-level compute versus memory bandwidth.', '', '## Results and discussion']
    report += [f'CPU model(s) reported across allocated nodes: {cpu_description}. MPI: Open MPI 5.0.1; compiler: GCC 11.5.0; CMake Release flags: -O3 -DNDEBUG. Raw per-node details are retained alongside the results.']
    report += lines[1:]
    report += ['![Median runtime and trial ranges](../figures/strong_scaling_runtime.png)', '![Communication fraction](../figures/communication_fraction.png)', '![Critical-rank timing breakdown](../figures/communication_breakdown.png)', '## Interpretation and limitations','See also the speedup, efficiency and iterations figures under `../figures/`. Jacobi checks less frequently than CG, which changes its reduction costs and may perform extra updates. Ratios compare medians, not paired causal effects. The P=1 baseline differs in node topology; within this study one-vs-two-node penalties cannot be isolated independently from P. The field is smooth and uses constant r, so results do not generalize automatically to fixed physical time, other initial fields, larger r, or other preconditioners. Three repetitions on one allocation do not capture day-to-day variation; interpret overlapping ranges and high variation cautiously. The raw records contain run-level component sums and per-step critical rank IDs but not separate per-step timings or all-rank timing distributions. No weak scaling or timestep sensitivity was measured.', '', '## Reproducibility',f'Raw records and environment: `{raw}`. Regenerate using `python scripts/analyze.py {raw} --snapshot <field.csv>`. Solver and launch scripts are in the project directory; run validation before benchmarking. See `../results/STATUS.md` for scope and outstanding items.']
    (ROOT/'report').mkdir(exist_ok=True); (ROOT/'report'/'report.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8')
    slides=['# Implicit heat: Jacobi vs CG','Course project • measured MPI scaling','---','# Model','Backward Euler on a 2D unit square; fixed r=2; zero boundaries.','Same matrix and tolerance for both solvers.','---','# Parallel methods','![Domain decomposition](../figures/domain_decomposition.png)','Jacobi: periodic convergence checks. CG: halo exchange plus global reductions.','---','# Validation','Independent serial solve, nondivisible decomposition, analytic sine mode, refinement, zero input and failed convergence tests.','---','# Experimental design','N=512,1024; 1–32 ranks; 3 trials; P=1 one node, P≥2 two nodes. Measured critical-rank solver timing.','---','# Runtime','![Runtime](../figures/strong_scaling_runtime.png)','---','# Communication','![Communication fraction](../figures/communication_fraction.png)','---','# Iterations and field','![Iterations](../figures/iterations_vs_processes.png)','---','# Conclusions and limitations','Refer to `../results/findings.md` for measured ratios and crossover brackets. MPI time includes waiting; three runs and topology changes limit interpretation.']
    (ROOT/'slides').mkdir(exist_ok=True); (ROOT/'slides'/'presentation.md').write_text('\n\n'.join(slides)+'\n',encoding='utf-8')


if __name__ == '__main__': main()
