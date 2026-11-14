#!/usr/bin/env python3
"""Build a two-page report summary, preserving the detailed report."""
from pathlib import Path
from html.parser import HTMLParser
import csv
import html
import re
import tempfile
import zipfile
import fitz

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
rows=list(csv.DictReader((ROOT/'results/extended-analysis-12312735/summary.csv').open()))
assert len(rows)==56 and all(int(r['trials'])==5 for r in rows)


def get(n,p,solver):
    return next(r for r in rows if r['study']=='strong' and int(r['N'])==n and int(r['P'])==p and r['solver']==solver)


table_rows=[]
for n,p in ((512,32),(1024,64)):
    j,c=[float(get(n,p,s)['median_s'])*1000 for s in ('jacobi','cg')]
    table_rows.append([str(n),str(p),f'{j:.3f}',f'{c:.3f}',f'{j/c:.2f} times'])

pages=[[
    ('h','1 Goal and approach'),
    ('p','We compare the time needed by Jacobi and conjugate gradient (CG) to solve the same heat-diffusion problem with MPI. The model is a unit-square plate with warm regions inside and edges held at zero temperature. Backward Euler advances the simulation by solving A x = b: b is the current temperature field, and x is the next field.'),
    ('p','MPI processes own rectangular grid blocks and exchange neighboring temperatures through halos. Global reductions combine information across all processes. Jacobi makes simple local corrections but needs many iterations. CG uses more global information per iteration, but usually requires far fewer iterations. We compare <strong>complete time to the same residual tolerance</strong>, not just the cost of one update.'),
    ('h','2 Experimental design'),
    ('p','The extended study contains <strong>280 runs: 56 study-specific groups, five trials each</strong>. It uses two exclusive AMD EPYC 7713 nodes, each with two 64-core sockets. Each rank is bound to a physical core. The one-rank baseline uses one node; larger runs use both. Every run measures five physical steps after a discarded warm-up and field reset. We report median runtime, summing each step\'s slowest-rank time.'),
    ('p','<strong>Strong scaling</strong> fixes N = 512 or 1024 and increases P from 1 to 64. <strong>Weak scaling</strong> grows the total grid while each rank owns 256-by-256 cells. A separate timestep study varies r = 0.5, 2, and 8 at P = 16. Here, N is grid points per side, P is MPI process count, and r sets the timestep relative to grid spacing.'),
    ('figure','Strong scaling: lower curves mean faster solves. Points are five-trial medians; shading shows the observed min-max range. Both axes use logarithmic spacing.'),
],[
    ('h','3 Main findings'),
    ('table',table_rows),
    ('p','<strong>CG was faster in all 18 strong-scaling comparisons.</strong> For N = 1024 and P = 64, CG requires 24 updates across five steps, versus Jacobi\'s 450. Its lower update count outweighs the higher cost per update. For N = 512, both solvers are fastest at the sampled P = 32 and slow down at 48 and 64. For N = 1024, both still improve through P = 64; the optimal process count was not established.'),
    ('p','<strong>Larger grids postpone communication dominance.</strong> MPI time exceeds half of computation-plus-MPI time between 16 and 24 ranks for N = 512, and between 48 and 64 for N = 1024. MPI time includes waiting and imbalance; other bookkeeping is excluded from this fraction. Crossing 50% does not immediately make added processes harmful, and the data do not establish a universal optimal MPI percentage.'),
    ('h','4 Weak scaling and timestep effects'),
    ('p','With 256-by-256 cells per rank, increasing P from 1 to 64 raises Jacobi runtime from 69.7 to 115.7 ms and CG from 15.4 to 22.6 ms. CG initially gets slightly faster because its update count falls enough to offset its rising cost per update. <strong>Fixed cells per rank do not guarantee fixed iteration counts.</strong> The scaling studies hold r fixed, so finer grids use smaller physical timesteps and can give a better starting guess.'),
    ('p','At N = 1024 and P = 16, increasing r from 0.5 to 8 increases Jacobi updates from 150 to 1920 and CG from 11 to 85. Median runtimes rise from 30.7 to 317.6 ms and from 8.06 to 33.8 ms, respectively. Larger steps change the linear system. These five-step runs cover different physical durations, rather than equal final simulation times.'),
    ('h','5 Correctness, limits, and conclusion'),
    ('p','All 280 runs passed an independently recomputed relative-residual tolerance of 10<sup>-8</sup>. Tests also compare small cases with an independent serial solver and a known sine-mode solution, and check halos, boundaries, uneven partitions, and failure handling. Five nearby trials in one allocation do not capture day-to-day variability. The one-node baseline versus two-node runs also mixes topology changes with process count.'),
    ('p','<strong>For this workload, CG gives lower time to solution, while useful parallelism depends on grid size and communication cost.</strong> Results are specific to the initial field, tolerance, timestep parameter, implementations, and hardware.'),
    ('source','Measurements: results/extended-analysis-12312735/summary.csv. The detailed report and raw records remain in the repository.'),
]]

HEADERS=['N','P','Jacobi (ms)','CG (ms)','CG advantage']
CSS='''body { margin:0; font-family:serif; font-size:11pt; line-height:1.18; color:#111; }
p { margin:0 0 7pt; text-align:justify; } h2 { font-size:13pt; margin:11pt 0 6pt; }
table { border-collapse:collapse; width:100%; font-size:10pt; margin:7pt 0; }
th { text-align:left; padding:5pt 7pt; border-bottom:1pt solid #333; }
td { padding:5pt 7pt; border-bottom:.3pt solid #ddd; }
.caption { font-size:9pt; line-height:1.15; margin:5pt 0 8pt; }
.source { font-size:9pt; margin-top:9pt; text-align:left; }'''


def table_html(data):
    return '<table><thead><tr>'+''.join('<th>'+h+'</th>' for h in HEADERS)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+v+'</td>' for v in row)+'</tr>' for row in data)+'</tbody></table><p class="caption">Selected median solve times in milliseconds, each covering five physical steps.</p>'


def body_html(blocks):
    out=[]
    for kind,value in blocks:
        if kind=='h':out.append('<h2>'+value+'</h2>')
        elif kind=='p':out.append('<p>'+value+'</p>')
        elif kind=='table':out.append(table_html(value))
        elif kind=='figure':out.append('<p><img src="figures/strong_runtime.png" width="468" height="153"></p><p class="caption">'+value+'</p>')
        elif kind=='source':out.append('<p class="source">'+html.escape(value)+'</p>')
    return ''.join(out)


def escape(s):
    return ''.join({'&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_'}.get(c,c) for c in s)


def tex_text(s):
    class Convert(HTMLParser):
        def __init__(self):super().__init__();self.parts=[]
        def handle_starttag(self,t,a):self.parts.append(r'\textbf{' if t=='strong' else r'$^{' if t=='sup' else '')
        def handle_endtag(self,t):self.parts.append('}' if t=='strong' else '}$' if t=='sup' else '')
        def handle_data(self,data):self.parts.append(escape(data))
    c=Convert();c.feed(s);return ''.join(c.parts)


preamble=r'''\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{amsmath,booktabs,graphicx,float,hyperref}
\usepackage[T1]{fontenc}
\setlength{\parindent}{0pt}
\setlength{\parskip}{5pt}
\setlength{\intextsep}{8pt}
\begin{document}
\noindent\rule{\linewidth}{2pt}
{\large\textbf{Srikar Palani, Suprathik Vinayakula}}\hfill\textbf{CS 598: Midterm Project}\\
palani3@illinois.edu, sv53@illinois.edu\hfill Fall 2026\\[-3pt]
\noindent\rule{\linewidth}{2pt}
\begin{center}{\Large\bfseries Parallel implicit heat diffusion}\\[3pt]
Two-page summary: Jacobi versus conjugate gradient\end{center}
'''
tex=[];md=['# Parallel implicit heat diffusion: two-page summary','','Srikar Palani, Suprathik Vinayakula - CS 598, Fall 2026','']
for i,blocks in enumerate(pages):
    if i:tex.append(r'\clearpage')
    for kind,value in blocks:
        if kind=='h':
            tex.append(r'\section*{'+value+'}');md.extend(['## '+value,''])
        elif kind in ('p','source'):
            tex.append((r'{\small ' if kind=='source' else '')+tex_text(value)+('}' if kind=='source' else ''))
            md.extend([value.replace('<strong>','**').replace('</strong>','**').replace('<sup>','^(').replace('</sup>',')'),''])
        elif kind=='table':
            tex.append('\\begin{table}[H]\n\\centering\\small\n\\begin{tabular}{rrrrr}\n\\toprule\n'+' & '.join(HEADERS)+r' \\'+'\n\\midrule\n'+'\n'.join(' & '.join(v)+r' \\' for v in value)+'\n\\bottomrule\n\\end{tabular}\n\\caption{Median five-step solve times in milliseconds.}\n\\end{table}')
            md.extend(['| '+' | '.join(HEADERS)+' |','| '+' | '.join(['---']*5)+' |',*['| '+' | '.join(v)+' |' for v in value],''])
        elif kind=='figure':
            tex.append('\\begin{figure}[H]\n\\centering\\includegraphics[width=\\linewidth]{figures/strong_runtime.pdf}\n\\caption{'+escape(value)+'}\n\\end{figure}')
            md.extend(['!['+value+'](figures/strong_runtime.png)',''])
(HERE/'summary.tex').write_text(preamble+'\n\n'.join(tex)+'\n\\end{document}\n')
(HERE/'summary.md').write_text('\n'.join(md))

with tempfile.TemporaryDirectory() as tmp:
    raw=Path(tmp)/'summary-body.pdf';writer=fitz.DocumentWriter(str(raw))
    for i,blocks in enumerate(pages):
        story=fitz.Story(html='<html><body>'+body_html(blocks)+'</body></html>',user_css=CSS,archive=fitz.Archive(str(HERE)))
        more,filled=story.place(fitz.Rect(72,176 if i==0 else 64,540,722))
        if more:raise RuntimeError(f'Summary page {i+1} overflows: {filled}')
        device=writer.begin_page(fitz.Rect(0,0,612,792));story.draw(device);writer.end_page()
    writer.close();doc=fitz.open(raw);p=doc[0]
    p.draw_line((72,72),(540,72),width=2)
    p.insert_text((72,91),'Srikar Palani, Suprathik Vinayakula',fontname='tibo',fontsize=12)
    course='CS 598: Midterm Project'
    p.insert_text((540-fitz.get_text_length(course,fontname='tibo',fontsize=10.5),91),course,fontname='tibo',fontsize=10.5)
    p.insert_text((72,108),'palani3@illinois.edu, sv53@illinois.edu',fontname='tiro',fontsize=10)
    p.insert_text((540-fitz.get_text_length('Fall 2026',fontname='tiro',fontsize=10),108),'Fall 2026',fontname='tiro',fontsize=10)
    p.draw_line((72,119),(540,119),width=2)
    for title,size,y in [('Parallel implicit heat diffusion',17,150),('Two-page summary: Jacobi versus conjugate gradient',12,168)]:
        p.insert_text((306-fitz.get_text_length(title,fontname='tibo' if size==17 else 'tiro',fontsize=size)/2,y),title,fontname='tibo' if size==17 else 'tiro',fontsize=size)
    for i,p in enumerate(doc):p.insert_text((303,757),str(i+1),fontname='tiro',fontsize=10)
    doc.set_metadata({'title':'Parallel implicit heat diffusion: two-page summary','author':'Srikar Palani, Suprathik Vinayakula'})
    doc.save(HERE/'summary.pdf',garbage=4,deflate=True)
with zipfile.ZipFile(HERE/'summary-latex-source.zip','w',zipfile.ZIP_DEFLATED) as z:
    z.write(HERE/'summary.tex','summary.tex')
    z.write(HERE/'figures/strong_runtime.pdf','figures/strong_runtime.pdf')
print('Created summary.pdf (2 pages), summary.tex, summary.md, and summary-latex-source.zip. Detailed report unchanged.')
