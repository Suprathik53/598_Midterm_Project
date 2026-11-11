#!/usr/bin/env python3
"""Build the explanatory report, matching LaTeX source, and data figures.

The PDF renderer uses PyMuPDF rather than requiring a local TeX installation.
The generated report.tex can also be compiled independently with pdflatex.
"""
from pathlib import Path
import csv
import html
from html.parser import HTMLParser
import math
import re
import tempfile

import fitz
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIGURES = HERE / 'figures'
FIGURES.mkdir(exist_ok=True)
ROWS = list(csv.DictReader((ROOT / 'results/extended-analysis-12312735/summary.csv').open()))
for row in ROWS:
    for key in row:
        if key not in ('study', 'solver'):
            row[key] = float(row[key])


def record(study, solver, n, p, r=2):
    return next(v for v in ROWS if (v['study'], v['solver'], v['N'], v['P'], v['r']) ==
                (study, solver, n, p, r))


plt.rcParams.update({
    'font.family': 'DejaVu Serif', 'font.size': 9,
    'axes.labelsize': 9, 'axes.titlesize': 10, 'legend.fontsize': 8,
    'xtick.labelsize': 8, 'ytick.labelsize': 8,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.edgecolor': '#777777', 'axes.linewidth': .6,
    'pdf.fonttype': 42, 'savefig.facecolor': 'white',
})
COLORS = {'jacobi': '#3f4544', 'cg': '#ac492a'}
for metric, name, ylabel in [
    ('median_s', 'strong_runtime', 'Five-step solve time (ms)'),
    ('median_comm_fraction', 'communication_share', 'MPI share of compute + MPI time (%)'),
]:
    fig, axes = plt.subplots(1, 2, figsize=(6.5, 2.12), layout='constrained')
    for ax, n in zip(axes, (512, 1024)):
        for solver in ('jacobi', 'cg'):
            data = sorted([v for v in ROWS if v['study'] == 'strong' and
                           v['solver'] == solver and v['N'] == n], key=lambda v: v['P'])
            x = [v['P'] for v in data]
            mul = 1000 if metric == 'median_s' else 100
            y = [v[metric]*mul for v in data]
            ax.plot(x, y, color=COLORS[solver], label='CG' if solver == 'cg' else 'Jacobi',
                    marker='o', ms=3, lw=1.4)
            if metric == 'median_s':
                ax.fill_between(x, [v['min_s']*1000 for v in data],
                                [v['max_s']*1000 for v in data],
                                color=COLORS[solver], alpha=.13, linewidth=0)
        ax.set_xscale('log', base=2)
        ax.set_xticks([1, 2, 4, 8, 16, 32, 64], labels=['1', '2', '4', '8', '16', '32', '64'])
        ax.set_xlabel('MPI processes, P')
        ax.set_title(f'N = {n}')
        ax.grid(axis='y', color='#dddddd', lw=.5)
        if metric == 'median_s':
            ax.set_yscale('log')
            ax.set_ylim(3, 1300)
            ax.set_yticks([10, 100, 1000])
            ax.yaxis.set_major_formatter(ScalarFormatter())
        else:
            ax.set_ylim(0, 100)
            ax.set_yticks([0, 25, 50, 75, 100])
            ax.axhline(50, color='#888888', ls='--', lw=.8)
        ax.legend(frameon=False, loc='best')
    axes[0].set_ylabel(ylabel)
    fig.savefig(FIGURES / f'{name}.pdf')
    fig.savefig(FIGURES / f'{name}.png', dpi=220)
    plt.close(fig)


def tex_escape(text):
    chars = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
             '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}',
             '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(chars.get(c, c) for c in text)


def html_to_tex(text):
    class Convert(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts=[]

        def handle_starttag(self, tag, attrs):
            self.parts.append({'strong':r'\textbf{','em':r'\emph{',
                               'code':r'\texttt{','sup':r'$^{'}.get(tag,''))

        def handle_endtag(self, tag):
            self.parts.append('}$' if tag=='sup' else '}' if tag in ('strong','em','code') else '')

        def handle_data(self, data):
            self.parts.append(tex_escape(data).replace('×',r'$\times$')
                              .replace('≥',r'$\geq$').replace('≤',r'$\leq$'))
    converter=Convert()
    converter.feed(text)
    return ''.join(converter.parts)


PAGES = []
page = []


def new_page():
    global page
    if page:
        PAGES.append(page)
    page = []


def section(number, title):
    page.append(('section', f'{number} {title}', r'\section{' + title + '}'))


def subsection(number, title):
    page.append(('subsection', f'{number} {title}', r'\subsection{' + title + '}'))


def para(text):
    page.append(('paragraph', text, html_to_tex(text)))


def equation(formula, readable):
    name = f'equation_{sum(len(p) for p in PAGES) + len(page)}'
    fig = plt.figure(figsize=(6.5, .34))
    fig.text(.5, .5, '$' + formula + '$', fontsize=12, ha='center', va='center')
    fig.savefig(FIGURES / f'{name}.png', dpi=220, bbox_inches='tight', pad_inches=.02)
    plt.close(fig)
    page.append(('equation', (name, readable), '\\[\n' + formula + '\n\\]'))


def table(headers, rows, caption, aligns=None):
    aligns = aligns or ('l' + 'r'*(len(headers)-1))
    tex = '\\begin{table}[H]\n\\centering\\small\n\\begin{tabular}{' + aligns + '}\n\\toprule\n'
    tex += ' & '.join(tex_escape(v) for v in headers) + r' \\' + '\n\\midrule\n'
    tex += '\n'.join(' & '.join(tex_escape(v) for v in row) + r' \\' for row in rows)
    tex += '\n\\bottomrule\n\\end{tabular}\n\\caption{' + tex_escape(caption) + '}\n\\end{table}'
    page.append(('table', (headers, rows, caption), tex))


def figure(name, caption):
    tex = '\\begin{figure}[H]\n\\centering\\includegraphics[width=\\linewidth]{figures/' + name + '.pdf}\n'
    tex += '\\caption{' + tex_escape(caption) + '}\n\\end{figure}'
    page.append(('figure', (name, caption), tex))


section('1', 'Project overview')
para('This project asks how much a parallel solver benefits from additional processors, and when communication becomes its main cost. We compare Jacobi and conjugate gradient (CG) on the same heat-diffusion problem using MPI on the Illinois Campus Cluster. The comparison focuses on <strong>time to reach an equally accurate solution</strong>, rather than how quickly either method performs one iteration.')
para('The main finding is that CG was faster at every tested strong-scaling configuration. However, adding more processes eventually gives diminishing returns. On the smaller grid, both methods reached their best sampled runtime at 32 processes and became slower at 48 and 64. The larger grid continued to benefit through 64 processes, even after MPI accounted for more than half of the measured computation-plus-communication time.')

section('2', 'The physical problem and the two solvers')
para('Imagine a square plate with two warm regions inside and all four edges held at zero temperature. Heat spreads across the plate and escapes through its edges. We represent the interior by an N-by-N grid. A larger N gives a more detailed representation of the same plate.')
para('We advance the temperature with backward Euler. This implicit method requires solving a linear system at each physical time step:')
equation(r'A\,T^{n+1}=T^n', 'A times the next temperature field equals the current temperature field.')
para('Here, the right-hand side is the current temperature field and the unknown is the next field. The action of A involves only a grid point and its four immediate neighbors. The program applies this five-point stencil directly, so it does not store a large dense matrix.')
table(['Method', 'How it progresses', 'Main tradeoff'], [
    ['Jacobi', 'Repeated local corrections', 'Simple updates, many iterations'],
    ['CG', 'A sequence of search directions', 'Fewer iterations, more synchronization'],
], 'Both methods solve the same linear system. CG uses no preconditioner.', 'lll')
para('A <strong>physical time step</strong> advances the heat simulation. A <strong>solver iteration</strong> is one update toward solving the system within that step. These are different quantities: five physical steps can require hundreds of solver iterations.')

new_page()
section('3', 'How the work is distributed')
para('MPI divides the grid into rectangular blocks, one per process, also called a rank. Each rank updates its own temperatures. Along a block edge, it first obtains neighboring values from the adjacent rank. These exchanged border values are called <strong>halos</strong>. The partition also supports uneven block sizes.')
para('Halo exchanges involve neighboring ranks. Global reductions combine values from every rank to calculate a dot product or check convergence. CG performs two dot products per iteration. Jacobi checks convergence after the first update, every ten updates, and at its iteration limit. Both start each solve from the previous temperature field.')

section('4', 'Correctness and experimental method')
para('<strong>Accuracy comes before timing.</strong> Both solvers use a relative-residual tolerance of 10<sup>-8</sup>. The residual measures how well the computed field satisfies the system. An independent check after every solve rejects inaccurate results, even when the solver internally reports convergence.')
para('The stored cluster tests passed comparisons with an independent serial solver, an analytic sine solution, and a refinement study. They also cover uneven blocks, boundaries, zero input, and failure cases. Separate diagnostics verified timing selection and a CG case with a misleading internal residual. Performance runs exclude this extra instrumentation.')
table(['Experimental choice', 'Setting'], [
    ['Compute resources', 'Two exclusive AMD EPYC 7713 nodes'],
    ['Process placement', 'One node at P = 1; both nodes at P >= 2'],
    ['Strong-scaling grids', 'N = 512 and 1024'],
    ['Strong-scaling processes', 'P = 1, 2, 4, 8, 16, 24, 32, 48, 64'],
    ['Measured work', 'Five physical steps after a reset warm-up'],
    ['Repetitions', 'Five trials per configuration'],
], 'The extended study contains 280 valid runs across 56 configurations.', 'll')
para('Ranks were bound to physical cores. We report the median of five trials. Each trial sums the slowest-rank time for each of five steps, since all ranks must finish. Every timing component comes from that same rank within a step. The timer includes solver work and MPI calls, but excludes field initialization, final accuracy checks, and output.')
para('All 280 runs completed five steps and passed the tolerance; the largest residual was 9.985 &times; 10<sup>-9</sup>. Earlier experiments remain separate from this dataset.')

new_page()
section('5', 'Results and interpretation')
subsection('5.1', 'Strong scaling: solve the same problem faster')
para('<strong>Strong scaling keeps the total grid fixed and adds processes.</strong> Each process owns a smaller block. Ideally, doubling the process count halves runtime. We express speedup as the one-process runtime divided by the P-process runtime:')
equation(r'\mathrm{Speedup}(P)=\frac{T_1}{T_P},\qquad \mathrm{Efficiency}(P)=\frac{\mathrm{Speedup}(P)}{P}', 'Speedup equals T1 divided by TP. Efficiency equals speedup divided by P.')
figure('strong_runtime', 'Strong scaling for both grids. Each point is the median of five trials; shading shows the minimum-to-maximum trial range. Both axes use logarithmic spacing.')
strong_rows = []
for p in (1, 8, 16, 32, 64):
    strong_rows.append([str(p)] + [f"{record('strong', solver, n, p)['median_s']*1000:.3f}"
                                  for n in (512, 1024) for solver in ('jacobi', 'cg')])
table(['P', 'N=512 Jacobi', 'N=512 CG', 'N=1024 Jacobi', 'N=1024 CG'], strong_rows,
      'Selected median five-step solve times in milliseconds. All nine process counts appear in Figure 1.')
para('CG was faster in all 18 strong-scaling comparisons. At N = 512 and P = 32, CG took 4.525 ms versus 23.190 ms for Jacobi, a 5.13-fold advantage. At N = 1024 and P = 64, the corresponding times were 6.689 ms and 51.396 ms, a 7.68-fold advantage. These ratios compare medians from separate trials.')
para('CG achieves this by requiring far fewer updates. For N = 1024, the five steps require 24 CG updates versus 450 Jacobi updates. A CG update is more expensive, but the smaller update count more than compensates. Relative speedup alone can hide this distinction: at 64 processes, Jacobi has a 19.42-fold speedup over its own baseline and CG a 16.65-fold speedup, yet CG still has the much lower absolute runtime.')

new_page()
subsection('5.2', 'When communication becomes the larger cost')
para('As a fixed grid is split among more processes, each rank has less local work. It still exchanges halos and participates in global reductions. To describe that balance, we measure the MPI share as halo-plus-reduction time divided by computation-plus-MPI time. Other bookkeeping is excluded from this fraction. <strong>MPI time includes waiting and imbalance</strong>, so this is not a direct measurement of network-transfer time.')
figure('communication_share', 'The dashed line marks 50% MPI time. Larger grids postpone the point at which MPI becomes the majority of the measured computation-plus-communication time.')
para('For N = 512, both solvers cross 50% between 16 and 24 processes. For N = 1024, both cross between 48 and 64. These are brackets between sampled configurations, rather than exact thresholds. At N = 1024 and P = 64, the median MPI shares are 51.8% for Jacobi and 61.2% for CG.')
para('Communication dominance does not immediately imply worse runtime. The smaller grid becomes slower beyond 32 processes, while the larger grid still improves through 64. The larger grid retains enough local work for the additional processes to remain useful.')
subsection('5.3', 'Weak scaling: handle a larger problem in similar time')
para('<strong>Weak scaling grows the grid along with the process count</strong>, keeping the number of owned cells per process constant. Here, every process owns 256-by-256 cells. Ideal weak scaling would keep runtime constant as the total problem grows.')
weak_rows=[]
for n,p in ((256,1),(512,4),(1024,16),(2048,64)):
    weak_rows.append([str(p),f'{n} x {n}']+[f"{record('weak', solver, n, p)['median_s']*1000:.3f}" for solver in ('jacobi','cg')])
table(['P', 'Total grid', 'Jacobi (ms)', 'CG (ms)'],weak_rows,
      'Weak scaling with 256-by-256 cells per process. Times cover five physical steps.')
para('From 1 to 64 processes, Jacobi grows from 69.7 to 115.7 ms and CG from 15.4 to 22.6 ms. Iteration counts also fall as the grid grows, partly masking the higher cost of each update. Average solve time per update rises from 0.127 to 0.289 ms for Jacobi and from 0.262 to 1.027 ms for CG. This ratio includes solver checks and setup within the timed solve; it is not a measurement of the update kernel alone.')

new_page()
subsection('5.4', 'Larger timesteps increase the work per solve')
para('We use a timestep parameter r. With diffusivity fixed at 1, r is the physical timestep divided by the squared grid spacing. At a fixed grid, larger r advances the simulation farther per step and changes the linear system. The scaling studies use r = 2; here we vary it.')
time_rows=[]
for r in (.5,2,8):
    j,c=[record('timestep',solver,1024,16,r) for solver in ('jacobi','cg')]
    time_rows.append([f'{r:g}',f"{j['median_s']*1000:.3f}",f"{c['median_s']*1000:.3f}",f"{j['median_iterations']:.0f}",f"{c['median_iterations']:.0f}"])
table(['r','Jacobi (ms)','CG (ms)','Jacobi updates','CG updates'],time_rows,
      'Timestep sensitivity at N = 1024 and P = 16. Times and update counts cover five physical steps.')
para('From r = 0.5 to 8, Jacobi updates rise from 150 to 1920 and CG updates from 11 to 85. Both solvers take longer per step. Backward Euler remains stable, but stability does not guarantee equal accuracy or cheap solves. Five steps at different r values simulate different physical durations.')

section('6', 'Conclusions and limitations')
para('<strong>CG reaches the required accuracy faster in every tested strong-scaling configuration.</strong> Its smaller iteration count outweighs its extra work per update. Larger grids postpone communication dominance. The practical lesson is to examine complete time to solution alongside iteration counts and the timing breakdown.')
para('The five nearby trials share one two-node allocation and do not capture day-to-day variation. The one-process baseline uses one node; larger configurations use both, mixing a topology change with process count. A same-P comparison on one node and two nodes was not measured. MPI timings include waiting, and full timing distributions across ranks were not retained.')
para('The findings depend on the initial field, tolerance, timestep parameter, and implementations. Fixed r changes the physical timestep as N changes, so the scaling studies compare five-step solver workloads rather than equal physical durations. Neither the CG advantage nor the crossover is a universal guarantee.')

section('7', 'Reproduction and project files')
para('Build the C++ solver with CMake and OpenMPI, then run tests and benchmarks in an allocated compute-node job using the same MPI environment. The README provides exact commands. The repository also contains the tests, Slurm scripts, raw measurements, and analysis tools; this report omits code listings.')
para('Data are in <code>results/data/extended-12312735/</code>, with tables in its separate analysis directory. Use <code>scripts/analyze_extended.py</code> for analysis. Correctness evidence is in <code>results/validation-12312723.log</code>. The accompanying LaTeX source and figure PDFs rebuild the report without rerunning experiments.')
new_page()


TITLE = 'Parallel implicit heat diffusion: Jacobi versus conjugate gradient'
PREAMBLE = r'''\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{xcolor,mdframed,amsmath,amssymb,booktabs,graphicx,float,hyperref}
\usepackage[T1]{fontenc}
\hypersetup{colorlinks=true,linkcolor=blue,urlcolor=blue}
\setlength{\parindent}{0pt}
\setlength{\parskip}{5pt}
\setlength{\textfloatsep}{10pt}
\setlength{\intextsep}{9pt}
\renewcommand{\arraystretch}{1.15}
\begin{document}
\noindent\rule{\linewidth}{2pt}
{\large\textbf{Srikar Palani, Suprathik Vinayakula}}\hfill\textbf{CS 598: Midterm Project}\\
\href{mailto:palani3@illinois.edu}{palani3@illinois.edu},
\href{mailto:sv53@illinois.edu}{sv53@illinois.edu}\hfill Fall 2026\\[-3pt]
\noindent\rule{\linewidth}{2pt}
\begin{center}
{\Large\bfseries Parallel implicit heat diffusion}\\[3pt]
{\large Jacobi versus conjugate gradient}
\end{center}
'''
# Convert the few HTML superscripts before writing the TeX source.
tex_pages=[]
for blocks in PAGES:
    fragments=[]
    for kind,value,tex in blocks:
        tex=re.sub(r'10<sup>(.*?)</sup>',lambda m:r'$10^{'+m[1]+'}$',tex)
        fragments.append(tex)
    tex_pages.append('\n\n'.join(fragments))
(HERE/'report.tex').write_text(PREAMBLE+'\n\n\\clearpage\n\n'.join(tex_pages)+'\n\\end{document}\n')

md=['# '+TITLE,'','Srikar Palani, Suprathik Vinayakula  ',
    'palani3@illinois.edu, sv53@illinois.edu  ','CS 598 Midterm Project - Fall 2026','']
for blocks in PAGES:
    for kind,value,_ in blocks:
        if kind in ('section','subsection'):
            md += [('## ' if kind=='section' else '### ')+value,'']
        elif kind=='paragraph':
            text=value.replace('<strong>','**').replace('</strong>','**').replace('<code>','`').replace('</code>','`')
            text=re.sub(r'<sup>(.*?)</sup>',r'^(\1)',text)
            md += [html.unescape(text),'']
        elif kind=='equation': md += ['$$',_.strip()[2:-2].strip(),'$$','']
        elif kind=='figure': md += [f'![{value[1]}](figures/{value[0]}.png)','']
        elif kind=='table':
            headers,rows,caption=value
            md += ['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']
            md += ['| '+' | '.join(row)+' |' for row in rows]
            md += ['',caption,'']
(HERE/'report.md').write_text('\n'.join(md))

CSS='''
body { margin:0; font-family:serif; font-size:11pt; line-height:1.18; color:#111; }
p { margin:0 0 6pt; text-align:justify; }
h2 { font-size:14pt; margin:12pt 0 6pt; font-weight:bold; }
h3 { font-size:12pt; margin:9pt 0 5pt; font-weight:bold; }
strong { font-weight:bold; }
code { font-family:monospace; font-size:9pt; }
table { width:100%; border-collapse:collapse; font-size:9pt; margin-top:7pt; }
thead { border-top:1pt solid #111; border-bottom:.5pt solid #111; }
th { font-weight:bold; padding:4pt 5pt; text-align:left; }
td { padding:4pt 5pt; border-bottom:.25pt solid #ddd; }
tbody { border-bottom:1pt solid #111; }
.caption { font-size:9pt; line-height:1.14; margin:5pt 0 9pt; text-align:justify; }
.figure { margin:7pt 0 0; }
.equation { text-align:center; margin:4pt 0 6pt; }
'''


def block_html(blocks):
    parts=[]
    for kind,value,_ in blocks:
        if kind in ('section','subsection'):
            tag='h2' if kind=='section' else 'h3'
            parts.append(f'<{tag}>{html.escape(value)}</{tag}>')
        elif kind=='paragraph': parts.append('<p>'+value+'</p>')
        elif kind=='equation':
            image=fitz.Pixmap(str(FIGURES/f'{value[0]}.png'))
            width,height=image.width*72/220,image.height*72/220
            parts.append(f'<p class="equation"><img src="figures/{value[0]}.png" width="{width:.2f}" height="{height:.2f}"></p>')
        elif kind=='figure':
            name,caption=value
            parts.append(f'<p class="figure"><img src="figures/{name}.png" width="468" height="153"></p><p class="caption">Figure {1 if name=="strong_runtime" else 2}. {html.escape(caption)}</p>')
        elif kind=='table':
            headers,rows,caption=value
            table_number=sum(1 for earlier in sum(PAGES,[])[:sum(PAGES,[]).index((kind,value,_))] if earlier[0]=='table')+1
            parts.append('<table><thead><tr>'+''.join('<th>'+html.escape(v)+'</th>' for v in headers)+'</tr></thead><tbody>')
            parts += ['<tr>'+''.join('<td>'+html.escape(v)+'</td>' for v in row)+'</tr>' for row in rows]
            parts.append(f'</tbody></table><p class="caption">Table {table_number}. {html.escape(caption)}</p>')
    return ''.join(parts)


archive=fitz.Archive(str(HERE))
pdf_path=HERE/'report.pdf'
with tempfile.TemporaryDirectory() as tmp:
    raw=Path(tmp)/'body.pdf'
    writer=fitz.DocumentWriter(str(raw))
    for i,blocks in enumerate(PAGES):
        body=block_html(blocks)
        # The first page reserves space for the supplied-style author header.
        top=176 if i==0 else 66
        story=fitz.Story(html='<html><body>'+body+'</body></html>', user_css=CSS, archive=archive)
        more,filled=story.place(fitz.Rect(72,top,540,721))
        if more:
            raise RuntimeError(f'Page {i+1} overflows its text area: {filled}')
        dev=writer.begin_page(fitz.Rect(0,0,612,792)); story.draw(dev); writer.end_page()
    writer.close()
    doc=fitz.open(raw)
    first=doc[0]
    first.draw_line((72,72),(540,72),width=2)
    first.insert_text((72,91),'Srikar Palani, Suprathik Vinayakula',fontname='tibo',fontsize=12)
    course='CS 598: Midterm Project'
    first.insert_text((540-fitz.get_text_length(course,fontname='tibo',fontsize=10.5),91),course,fontname='tibo',fontsize=10.5)
    first.insert_text((72,108),'palani3@illinois.edu, sv53@illinois.edu',fontname='tiro',fontsize=10)
    first.insert_text((540-fitz.get_text_length('Fall 2026',fontname='tiro',fontsize=10),108),'Fall 2026',fontname='tiro',fontsize=10)
    first.draw_line((72,119),(540,119),width=2)
    title='Parallel implicit heat diffusion'
    subtitle='Jacobi versus conjugate gradient'
    first.insert_text((306-fitz.get_text_length(title,fontname='tibo',fontsize=17)/2,150),title,fontname='tibo',fontsize=17)
    first.insert_text((306-fitz.get_text_length(subtitle,fontname='tiro',fontsize=12)/2,168),subtitle,fontname='tiro',fontsize=12)
    for i,pg in enumerate(doc):
        pg.insert_textbox(fitz.Rect(72,748,540,766),str(i+1),fontname='tiro',fontsize=10,align=1)
    doc.set_metadata({'title':TITLE,'author':'Srikar Palani, Suprathik Vinayakula','subject':'CS 598 Midterm Project, Fall 2026'})
    doc.save(pdf_path,garbage=4,deflate=True)
print(f'Created {pdf_path}, report.tex, report.md, and figure sources ({len(PAGES)} pages).')
