#!/usr/bin/env python3
"""Create a separate explanatory HTML deck without changing either old deck.

Reuses the approved deck's visual system and its embedded measured SVG charts.
Every essential chart state is visible on its own slide, including in print.
"""
from pathlib import Path
import csv
import hashlib
import html
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'slides/implicit-heat-presentation.html'
TARGET = ROOT / 'slides/implicit-heat-self-contained.html'
source = SOURCE.read_text()
source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
rows = list(csv.DictReader((ROOT/'results/extended-analysis-12312735/summary.csv').open()))
embedded = json.loads(re.search(r'<script id="measurement-data" type="application/json">(.*?)</script>', source, re.S)[1])
assert len(rows) == len(embedded) == 56
for actual, expected in zip(embedded, rows):
    assert all(actual[k] == (expected[k] if k in ('study', 'solver') else float(expected[k])) for k in actual)


def old_section(number):
    return re.search(r'<section\b[^>]*id="slide-'+str(number)+r'".*?</section>', source, re.S)[0]


def visual(number, index=0):
    return re.findall(r'<svg\b.*?</svg>', old_section(number), re.S)[index]


def chart(number, index=0):
    s = old_section(number)
    pairs = re.findall(r'(<svg class="data-chart".*?</svg>)(<table class="sr-only">.*?</table>)', s, re.S)
    assert len(pairs) == 2
    return ''.join(pairs[index])


slides = []


def add(title, context, body, takeaway, note, chapter='Methods', cls=''):
    n = len(slides)+1
    slides.append(f'''<section class="slide explained {cls}" id="slide-{n}" aria-labelledby="title-{n}" data-title="{html.escape(title, quote=True)}" {'hidden' if n>1 else ''}>
<div class="slide-meta"><span class="stencil-mark" aria-hidden="true">✛</span><span>CS598 / MPI heat diffusion</span><span class="chapter">{chapter}</span></div>
<{"h1" if n==1 else "h2"} id="title-{n}">{title}</{"h1" if n==1 else "h2"}>
<p class="context-line">{context}</p>
<div class="slide-body">{body}</div>
<p class="slide-takeaway">{takeaway}</p>
<footer class="slide-footer"><span>Extended study 12312735 · Jacobi and CG · Self-contained edition</span><span>{n:02d} / TOTAL_SLIDES</span></footer>
<aside class="speaker-notes" hidden>{note}</aside></section>''')


def textcol(title, text, extra=''):
    return f'<article><h3>{title}</h3><p>{text}</p>{extra}</article>'


def table(headers, data, label):
    return '<table class="explain-table"><caption class="sr-only">'+html.escape(label)+'</caption><thead><tr>'+''.join('<th scope="col">'+v+'</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+v+'</td>' for v in row)+'</tr>' for row in data)+'</tbody></table>'


def result_chart(number, index, left_title, left, right_title, right):
    return '<figure class="chart-figure">'+chart(number,index)+'</figure><div class="interpretation">'+textcol(left_title,left)+textcol(right_title,right)+'</div>'


add('Heat diffusion,<br>in parallel', '',
    '<div class="explained-cover"><div><p class="cover-description">We simulate a cooling plate and compare two ways to solve the same temperature equations: <strong>Jacobi</strong> and <strong>conjugate gradient (CG)</strong>.</p><div class="cover-question"><span>Research question</span><p>How much faster do more processes make the solve, and when does MPI communication become the main cost?</p></div><p class="cover-authors">Srikar Palani and Suprathik Vinayakula<br>CS598 Midterm Project · Fall 2026</p></div><figure>'+visual(1)+'<figcaption>Brighter cells are warmer. This separate visualization uses a 128 × 128 grid after five time steps.</figcaption></figure></div>',
    'The study compares time to the same residual tolerance, across 1–64 MPI processes and 280 measured runs.',
    'The temperature field is a separate measured visualization: results/fields/final-12296983.csv and snapshot-12296983.json. The performance dataset is results/data/extended-12312735/.', 'Overview', 'explain-cover')

add('Each time step requires a linear solve',
    'Physical model: a unit-square plate, warm regions inside, and edges held at zero temperature.',
    '<div class="two-col model-explanation"><article><h3>The temperature model</h3><p>An <strong>N × N grid</strong> represents the interior. Heat moves between neighbors; larger N gives a finer grid. Backward Euler advances one physical step by solving:</p><p class="large-equation">A x = b</p><p><strong>b</strong> is the current temperature field.<br><strong>x</strong> is the next temperature field.<br><strong>A</strong> describes the neighbor interactions.</p></article><article class="model-visual">'+visual(2)+'<p>Each point interacts with four neighbors. The code calculates these five-point interactions directly instead of storing a huge matrix.</p></article></div>',
    'A physical time step advances the simulation. Solver iterations are the repeated updates needed to solve A x = b within that step.',
    'Source: src/main.cpp, Grid::apply and main. The diagonal is 1+4r and neighbor coefficients are −r. Diffusivity alpha=1; physical boundaries are zero.', 'Model')

add('MPI processes share the plate',
    'P is the number of MPI processes. A process is also called a rank; each rank owns one grid block.',
    '<div class="two-col mpi-explanation"><figure>'+visual(3)+'<figcaption>Four-rank example. Orange strips indicate exchanged border values, called halos.</figcaption></figure><article><h3>Two communication patterns</h3><div class="definition"><strong>Neighbors exchange halos</strong><p>A rank needs values just beyond its block to update points along the edge.</p></div><div class="definition"><strong>All ranks combine scalars</strong><p>Global reductions combine local results for dot products and convergence checks. These calls can include waiting for other ranks.</p></div></article></div>',
    'More ranks reduce the cells owned by each process, but halo exchanges and global reductions remain necessary.',
    'Source: src/main.cpp: Grid constructor, apply, and dot. MPI_Sendrecv handles halos; MPI_Allreduce computes global scalar sums. Uneven block sizes are supported.', 'Parallel method')

add('Two solvers, one accuracy target',
    'Each physical step solves the same A x = b, starting from x = b. Only the iterative method changes.',
    '<div class="two-col solver-explanation">'+textcol('Jacobi', 'Repeatedly corrects each temperature estimate using the current residual. Each update is simple, but many may be needed.', '<ul><li>Neighbor exchange every update</li><li>Convergence check after update 1, every 10 updates, and at the iteration cap</li></ul>')+textcol('Conjugate gradient (CG)', 'Builds search directions that usually make more progress per update. Each update costs more because it needs additional calculations and global communication.', '<ul><li>Neighbor exchange every update</li><li>Two global dot products per update</li></ul>')+'</div><div class="accuracy-strip"><strong>Residual:</strong> how well the computed x satisfies A x = b, relative to the size of b. Both methods must pass an independently recomputed residual ≤ 10⁻⁸.</div>',
    'We compare complete time to solution. A cheap iteration is useful only if the method does not need too many of them.',
    'Source: src/main.cpp: solve. CG is unpreconditioned. Both algorithms use the same initial guess. Final true-residual verification is outside the timed interval.', 'Solvers')

add('What the 56 experiment groups contain',
    'A configuration chooses a solver, grid size N, process count P, and timestep parameter r.',
    table(['Study', 'Settings', 'Groups'],[
        ['Strong scaling', '2 solvers × N = 512, 1024 × 9 process counts<br>P = 1, 2, 4, 8, 16, 24, 32, 48, 64; r = 2', '36'],
        ['Weak scaling', '2 solvers × (N, P) = (256, 1), (512, 4),<br>(1024, 16), (2048, 64); r = 2', '8'],
        ['Timestep sensitivity', '2 solvers × N = 512, 1024 × r = 0.5, 2, 8<br>P = 16', '12'],
    ], 'The 56 study-specific experiment groups')+'<div class="experiment-count"><strong>56 groups × 5 trials = 280 runs</strong><p>Every run measures five physical time steps. Some numerical settings repeat across studies; they remain separate experiment groups.</p></div>',
    'The timestep parameter r sets the size of a physical step relative to grid spacing; its effect is explained on slides 15–16.',
    'Source: scripts/extended_matrix.py and results/extended-analysis-12312735/summary.csv. There are 56 study-specific groups, not 56 distinct tuples after removing the study label.', 'Experiment')

add('How the timings were collected',
    'Two exclusive AMD EPYC 7713 nodes on the Illinois Campus Cluster, with ranks bound to physical cores.',
    '<div class="two-col measurement">'+textcol('One measured run', 'Discard a warm-up, reset the temperature field, then measure five physical steps. Runtime is the sum of each step’s slowest-rank time.', '<p>All ranks must finish. Each step’s compute and MPI breakdown comes from that same selected rank.</p>')+textcol('A fair reading of the results', 'We report the median of five trials. Whiskers show the observed min–max range, not confidence intervals.', '<p>Timing includes solver calculations, checks, and MPI calls. Field initialization, final accuracy verification, and output are excluded.</p>')+'</div><div class="accuracy-strip"><strong>Placement matters:</strong> P = 1 uses one node. P ≥ 2 spreads the ranks evenly over both nodes. Five nearby trials share the same allocation.</div>',
    'All plotted runtime values are milliseconds for the entire five-step solve, rather than a single iteration or a single physical step.',
    'Source: scripts/extended.sbatch, scripts/extended_matrix.py, src/main.cpp timing aggregation, and the extended allocation environment records.', 'Measurement')

add('Strong scaling on a 512 × 512 grid',
    'Strong scaling fixes the total grid and adds ranks. Ideal behavior: twice as many ranks would halve runtime. Here r = 2.',
    result_chart(6,0,'CG is faster at every sampled P', 'At P = 32: CG takes 4.525 ms; Jacobi takes 23.190 ms. That is a 5.13-fold runtime advantage.', 'More ranks eventually stop helping', 'Both methods reach their best sampled runtime at 32 ranks. Runtime increases at 48 and 64.'),
    'Read downward as faster. Both axes use logarithmic spacing; points are five-trial medians, with min–max whiskers.',
    'Source: summary.csv, study=strong, N=512, r=2. Every timing covers five physical steps. CG/Jacobi comparisons are ratios of separate medians.', 'Strong scaling', 'chart-slide')

add('A larger grid benefits through 64 ranks',
    'Strong scaling with N = 1024, r = 2, and the same solvers, accuracy target, hardware, and five-step timing.',
    result_chart(6,1,'CG retains the lower runtime', 'At P = 64: CG takes 6.689 ms; Jacobi takes 51.396 ms. CG is 7.68 times faster.', 'The larger workload scales farther', 'Both methods still improve at 64 ranks. Each rank retains more useful work than on the 512 × 512 grid.'),
    'Speedup is T₁ / Tₚ for the same solver. A higher relative speedup does not necessarily mean a lower absolute runtime.',
    'Source: summary.csv, study=strong, N=1024, r=2. At P64 Jacobi speedup is approximately 19.42 and CG speedup 16.65, despite CG being faster in absolute time.', 'Strong scaling', 'chart-slide')

add('MPI dominates sooner on the smaller grid',
    'N = 512, r = 2. MPI share = (halo + reduction time) / (local compute + halo + reduction time).',
    result_chart(7,0,'The crossover is between 16 and 24 ranks', 'Both solvers move from below 50% MPI time at P = 16 to above 50% at P = 24.', 'Why the share grows', 'Each rank owns fewer cells as P rises, while neighbor exchanges and global reductions remain necessary.'),
    'The dashed line marks a measured 50% share. MPI time includes waiting and imbalance; other bookkeeping is excluded.',
    'Source: summary.csv, study=strong, N=512. Jacobi median fraction is 39.6% at P16 and 52.0% at P24; CG is 37.7% and 58.2%.', 'Communication', 'chart-slide')

add('Larger grids postpone MPI dominance',
    'N = 1024, r = 2. The same MPI-share definition and 50% threshold apply to both solvers.',
    result_chart(7,1,'The crossover moves to 48–64 ranks', 'At P = 64, the MPI shares reach 51.8% for Jacobi and 61.2% for CG.', 'A high MPI share can still accompany gains', 'Both runtimes continue falling through 64 ranks, even though MPI becomes the larger measured component.'),
    'A percentage describes the balance of time, not its absolute size. Compare it with the runtime plot before choosing P.',
    'Source: summary.csv, study=strong, N=1024. Crossover brackets lie between sampled process counts, not exact estimated thresholds. The threshold annotation is separated from endpoint labels.', 'Communication', 'chart-slide')

add('CG wins by needing far fewer updates',
    'Same problem: N = 1024, P = 64, r = 2, tolerance 10⁻⁸. Counts and times cover all five physical steps.',
    table(['Measured quantity', 'Jacobi', 'CG'],[
        ['Total solver updates', '450', '24'],
        ['Median five-step runtime', '51.396 ms', '6.689 ms'],
        ['Runtime divided by updates', '0.114 ms/update', '0.279 ms/update'],
    ], 'Why CG has lower time to solution')+'<div class="two-col compact-insight">'+textcol('One CG update costs more', 'It performs extra vector work and global dot products. The per-update figure also includes solver setup and checks.')+textcol('Its smaller update count wins overall', 'Jacobi performs 18.75 times as many updates. CG’s fewer updates outweigh its higher cost per update.')+'</div>',
    'These are solver iterations within five simulation steps. They do not mean that the two methods simulated different physical durations.',
    'Source: summary.csv, study=strong, N=1024, P=64, r=2. This explains the measured implementations and is not a universal ranking of iterative methods.', 'Solver comparison')

add('Weak scaling keeps cells per rank fixed',
    'Weak scaling asks whether more processes can handle a proportionally larger problem in a similar amount of time.',
    table(['MPI ranks P', 'Total interior grid', 'Owned cells per rank'],[
        ['1', '256 × 256', '256 × 256'],
        ['4', '512 × 512', '256 × 256'],
        ['16', '1024 × 1024', '256 × 256'],
        ['64', '2048 × 2048', '256 × 256'],
    ], 'Weak-scaling grid and process combinations')+'<div class="two-col compact-insight">'+textcol('Strong scaling', 'The total problem stays fixed. More processes should reduce runtime.')+textcol('Weak scaling', 'The problem grows with P. Ideal runtime stays constant if work per rank and iteration counts stay constant.')+'</div>',
    'These weak-scaling runs use r = 2, the same two solvers and tolerance, and five physical steps per run.',
    'Source: scripts/extended_matrix.py and summary.csv, study=weak. MPI process grids keep exactly 256×256 owned cells per rank in the four sampled cases.', 'Weak scaling')

add('Weak-scaling runtime increases overall',
    'Total grid grows from 256 × 256 at P = 1 to 2048 × 2048 at P = 64. Each rank still owns 256 × 256 cells.',
    result_chart(9,0,'Jacobi: 69.7 to 115.7 ms', 'Its total five-step runtime rises as the overall problem and process count grow.', 'CG: 15.4 to 22.6 ms', 'CG remains faster. Its intermediate runtimes fall before the increase at 64 ranks.'),
    'A perfectly flat curve would indicate constant runtime. Here, changing iteration counts also affect the curve; the next slide separates that effect.',
    'Source: summary.csv, study=weak. These are separate weak-study measurements, not reused strong-study records. Medians use five trials.', 'Weak scaling', 'chart-slide')

add('Per-update time exposes hidden overhead',
    'Same weak-scaling runs. Time per update = total measured solve time divided by total solver updates.',
    result_chart(9,1,'The cost per update rises', 'Jacobi: 0.127 to 0.289 ms. CG: 0.262 to 1.027 ms, from 1 to 64 ranks.', 'Fewer updates partly mask that rise', 'Jacobi update counts fall from 550 to 400; CG counts fall from 59 to 22 across the five steps.'),
    'This ratio includes setup and convergence checks within the solve. It is not an isolated update-kernel timer or a pure network measurement.',
    'Source: summary.csv, study=weak, median_s_per_iteration and median_iterations. Fixed-r grids change the numerical problem and physical timestep as N changes.', 'Weak scaling', 'chart-slide')

add('Larger timesteps make each solve harder',
    'At N = 1024 and P = 16, vary r = αΔt / h². Here α = 1 is diffusivity, Δt is timestep, and h is grid spacing.',
    result_chart(10,0,'r = 0.5 to 8 increases runtime', 'Jacobi: 30.7 to 317.6 ms. CG: 8.06 to 33.8 ms. Each measurement still covers five steps.', 'What changing r means', 'With the grid fixed, larger r advances farther in physical time per step and changes the system A x = b.'),
    'These runs simulate different physical durations. The plot compares solve workloads, not the cost of reaching the same final physical time.',
    'Source: summary.csv, study=timestep, N=1024, P=16. The separate sensitivity study also includes N=512, but this plot shows the larger grid for clarity.', 'Timestep study', 'chart-slide')

add('More iterations explain the extra time',
    'Timestep sensitivity at N = 1024, P = 16. All values below are totals or medians over the same five-step workload.',
    table(['Timestep r', 'Jacobi updates', 'CG updates', 'Jacobi time', 'CG time'],[
        ['0.5', '150', '11', '30.675 ms', '8.060 ms'],
        ['2', '450', '24', '81.935 ms', '12.983 ms'],
        ['8', '1920', '85', '317.589 ms', '33.782 ms'],
    ], 'Solver work as the timestep parameter increases')+'<div class="two-col compact-insight">'+textcol('The numerical system changes', 'A larger r needs more solver updates for this initial field and tolerance. CG still needs far fewer updates than Jacobi.')+textcol('Stability is only one consideration', 'Backward Euler is stable for large timesteps, but a stable step can still be expensive or less accurate.')+'</div>',
    'A larger timestep is not automatically the cheaper or more accurate choice. Equal step counts do not imply equal simulated durations.',
    'Source: summary.csv, study=timestep, N=1024, P=16. Times are medians; all trials pass the independent true-residual check.', 'Timestep study')

add('Correctness checks and interpretation limits',
    'Every benchmark passed the same independently recomputed relative-residual tolerance of 10⁻⁸.',
    '<div class="two-col limits-explanation">'+textcol('Why trust the computed solutions?', 'Tests match an independent serial solver and analytic sine solution. They also cover refinement, halos, physical boundaries, uneven partitions, and failure cases.', '<p>All 280 runs passed. The maximum residual was <strong>9.985 × 10⁻⁹</strong>. Diagnostics checked timing selection and rejected a CG result with a misleading internal residual.</p>')+textcol('What the measurements cannot establish', 'MPI time includes waiting and imbalance. P = 1 uses one node while larger P uses two, so topology and rank count change together.', '<p>Trials share one allocation; they do not capture day-to-day variation. Fixed r changes the physical timestep with N. Results depend on this initial field, tolerance, hardware, and implementation.</p>')+'</div>',
    'Residual tolerance checks the linear solve. It does not by itself guarantee that different grids and timesteps have the same physical accuracy.',
    'Sources: tests/test_integration.py, tests/test_stencil.cpp, tests/test_diagnostics.py, results/validation-12312723.log, and raw extended records. No same-P one-node versus two-node control was measured.', 'Validation')

add('What the study establishes',
    'Two solvers, the same implicit heat model, and 280 validated measurements on a two-node allocation.',
    '<div class="conclusion-layout"><div class="conclusion-points"><article><span>01</span><h3>CG lowers time to solution</h3><p>It wins every tested strong-scaling comparison because far fewer updates offset its higher cost per update.</p></article><article><span>02</span><h3>Grid size changes useful parallelism</h3><p>The 512 × 512 grid is fastest at 32 sampled ranks. The 1024 × 1024 grid still improves at 64.</p></article><article><span>03</span><h3>Read runtime and MPI share together</h3><p>MPI can exceed half the measured time while additional ranks still reduce total runtime.</p></article></div><aside class="reproduction-panel"><h3>Evidence and reproduction</h3><p>The repository contains the solver, automated tests, Slurm scripts, raw JSON records, and analysis.</p><p>Build with CMake and OpenMPI. Run MPI work in an allocated compute-node job.</p><div class="source-links"><a href="../README.md">Build and run instructions</a><a href="../report/report.pdf">Reader-focused project report</a><a href="../results/extended-analysis-12312735/summary.csv">Measured summary CSV</a></div></aside></div>',
    'These findings apply to this workload; other hardware, initial fields, tolerances, or solvers can change the outcome.',
    'Sources: README.md, report/report.pdf, and results/extended-analysis-12312735/summary.csv. This deck is a separate explanatory edition; the original deck is preserved.', 'Conclusions')

count = len(slides)
assert count == 18
content = ''.join(slides).replace('TOTAL_SLIDES', str(count))
start = source.index('<div class="stage">')+len('<div class="stage">')
end = source.index('</section>', source.index('id="slide-12"',start))+len('</section>')
result = source[:start]+content+source[end:]
result = result.replace('<span id="slideCounter" class="slide-counter" aria-live="polite">1 / 12</span>',f'<span id="slideCounter" class="slide-counter" aria-live="polite">1 / {count}</span>')
result = result.replace('A 12-slide MPI heat diffusion presentation', 'An 18-slide self-contained MPI heat diffusion presentation')
result = result.replace('<title>Implicit heat diffusion · Jacobi and CG</title>', '<title>Implicit heat diffusion · Self-contained edition</title>')
result = result.replace('<span class="header-context">Jacobi / Conjugate gradient</span>', '<span class="header-context">Self-contained edition · Jacobi / CG</span>')
result = result.replace("getItem('heat-viz-theme')", "getItem('heat-self-contained-theme')").replace("setItem('heat-viz-theme'", "setItem('heat-self-contained-theme'")
result = re.sub(r'@media\(max-width:700px\) \{.*?(?=@media\(max-width:375px\))', '', result, flags=re.S)
css = '''
/* Explanatory edition: preserve the approved visual language, add visible context. */
.explained h2 { font-size:44px; top:100px; }
.explained .context-line { position:absolute; top:166px; left:64px; right:64px; font-size:19px; line-height:1.4; color:var(--text-secondary); }
.explained .slide-body { top:224px; bottom:120px; }
.explained .slide-footer { bottom:24px; }
.explained .slide-takeaway { position:absolute; left:64px; right:64px; bottom:68px; font-size:18px; line-height:1.4; padding-top:12px; border-top:1px solid var(--border); color:var(--text-secondary); }
.two-col { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:64px; }
.two-col h3 { font-size:28px; font-weight:500; line-height:1.2; margin-bottom:16px; }
.two-col p { font-size:23px; line-height:1.4; color:var(--text-secondary); margin-bottom:20px; }
.two-col p strong { color:var(--text); font-weight:500; }
.large-equation { font-size:38px!important; color:var(--text)!important; margin:16px 0!important; }
.model-explanation .stencil { display:block; height:244px; max-height:none; }
.model-explanation .model-visual p { font-size:21px; line-height:1.4; text-align:center; margin-top:4px; }
.mpi-explanation .decomp { height:272px; }
.mpi-explanation figcaption { font-size:18px; line-height:1.4; margin-top:12px; }
.definition { margin-top:20px; }
.definition strong { font-size:23px; font-weight:500; }
.definition p { font-size:21px; margin:8px 0 0; }
.solver-explanation p { font-size:23px; }
.solver-explanation ul { padding-left:24px; margin-top:16px; }
.solver-explanation li { font-size:20px; line-height:1.45; margin-bottom:8px; color:var(--text-secondary); }
.accuracy-strip { padding-top:16px; margin-top:24px; border-top:1px solid var(--border); font-size:20px; line-height:1.4; color:var(--text-secondary); }
.accuracy-strip strong { color:var(--text); font-weight:500; }
.explain-table { border-collapse:collapse; width:100%; font-size:22px; line-height:1.4; }
.explain-table th { text-align:left; font-weight:500; font-size:19px; color:var(--text-secondary); padding:12px 16px; border-bottom:1px solid var(--border); }
.explain-table td { padding:12px 16px; border-bottom:1px solid var(--border); vertical-align:top; }
.explain-table th:first-child,.explain-table td:first-child { padding-left:0; }
.explain-table th:last-child,.explain-table td:last-child { padding-right:0; }
.explain-table tbody td:last-child { font-variant-numeric:tabular-nums; }
.experiment-count { display:grid; grid-template-columns:1fr 1fr; gap:48px; margin-top:24px; align-items:center; }
.experiment-count strong { font-size:28px; font-weight:500; color:var(--accent); }
.experiment-count p { font-size:20px; color:var(--text-secondary); line-height:1.4; }
.measurement p { font-size:22px; line-height:1.4; margin-bottom:20px; }
.measurement+.accuracy-strip { margin-top:8px; font-size:19px; line-height:1.35; padding-top:12px; }
.measurement p { font-size:21px; line-height:1.35; margin-bottom:16px; }
.chart-slide .slide-body { top:218px; bottom:116px; }
.explained .chart-figure { height:260px; margin:0; }
.explained .chart-figure .data-chart { height:100%; width:100%; }
.interpretation { display:grid; grid-template-columns:1fr 1fr; gap:48px; margin-top:12px; }
.interpretation h3 { font-size:22px; font-weight:500; line-height:1.25; margin-bottom:8px; }
.interpretation p { font-size:20px; line-height:1.35; color:var(--text-secondary); }
.compact-insight { margin-top:20px; }
.compact-insight h3 { font-size:24px; margin-bottom:12px; }
.compact-insight p { font-size:21px; line-height:1.35; margin:0; }
.limits-explanation p { font-size:21px; line-height:1.4; }
.conclusion-layout { display:grid; grid-template-columns:1.45fr 1fr; gap:64px; }
.conclusion-points article { padding-left:44px; position:relative; margin-bottom:24px; }
.conclusion-points article>span { position:absolute; left:0; top:4px; font-family:ui-monospace,monospace; color:var(--accent); font-size:18px; }
.conclusion-points h3 { font-size:26px; font-weight:500; margin-bottom:8px; }
.conclusion-points p,.reproduction-panel p { font-size:20px; line-height:1.35; color:var(--text-secondary); }
.reproduction-panel { padding-left:32px; border-left:1px solid var(--border); }
.reproduction-panel h3 { font-size:26px; margin-bottom:20px; }
.reproduction-panel p { margin-bottom:20px; }
.reproduction-panel .source-links { font-size:18px; margin-top:24px; }
.explain-cover h1 { position:absolute; top:116px; left:64px; font-size:76px; width:624px; line-height:1.04; }
.explain-cover .context-line { display:none; }
.explain-cover .slide-body { top:116px; bottom:124px; }
.explained-cover { display:grid; grid-template-columns:1.2fr 440px; gap:64px; height:100%; }
.explained-cover>div { padding-top:176px; }
.cover-description { font-size:22px; line-height:1.4; color:var(--text-secondary); }
.cover-description strong { font-weight:500; color:var(--text); }
.cover-question { margin-top:20px; border-left:3px solid var(--accent); padding-left:20px; }
.cover-question>span { font-size:16px; color:var(--text-secondary); }
.cover-question p { font-size:23px; line-height:1.35; margin-top:8px; }
.cover-authors { font-size:15px; color:var(--text-secondary); margin-top:20px; }
.explained-cover .heatmap { width:400px; height:400px; display:block; margin-left:16px; }
.explained-cover figcaption { font-size:16px; line-height:1.4; margin:12px 0 0 16px; }
.model-explanation p { font-size:21px; line-height:1.35; margin-bottom:12px; }
.model-explanation .large-equation { line-height:1.2; margin:12px 0!important; }
.solver-explanation p { font-size:22px; line-height:1.35; }
.solver-explanation li { font-size:18px; line-height:1.4; margin-bottom:6px; }
.solver-explanation .accuracy-strip { margin-top:16px; }
#slide-4 .accuracy-strip { font-size:19px; line-height:1.35; padding-top:12px; margin-top:16px; }
#slide-5 .explain-table { font-size:20px; line-height:1.3; }
#slide-5 .explain-table td,#slide-5 .explain-table th { padding:10px 12px; }
#slide-5 .explain-table td:first-child,#slide-5 .explain-table th:first-child { padding-left:0; }
#slide-5 .experiment-count { margin-top:16px; }
#slide-5 .experiment-count p { font-size:18px; line-height:1.4; }
#slide-12 .explain-table td { padding-top:8px; padding-bottom:8px; }
.chart-slide .slide-takeaway { font-size:16px; }

@media screen and (max-width:700px) {
  /* This edition targets desktop projection; preserve its 16:9 composition. */
  html,body { height:100%; overflow:hidden; }
  main#main-content { position:fixed; left:50%; top:50%; transform:translate(-50%,-50%); padding:0!important; }
  .stage { width:1280px; height:720px; }
}
@media print {
  .explained .context-line,.explained .slide-takeaway { display:block!important; }
  .explain-cover .context-line { display:none!important; }
}
'''
result = result.replace('</style>', css+'\n</style>', 1)
# Avoid the old responsive reading layout; this edition targets desktop and PDF.
result = result.replace('if (window.innerWidth <= 700) return;', '')
result = result.replace("var scale = Math.min((window.innerWidth - 64) / 1280, (window.innerHeight - 168) / 720, 1.4);", "var scale = Math.min((window.innerWidth - 64) / 1280, (window.innerHeight - 168) / 720, 1.4);")
assert len(re.findall(r'<section class="slide\b', result)) == count
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash
TARGET.write_text(result)
print(f'Created {TARGET.name}: {count} slides; all original deck files left unchanged.')
