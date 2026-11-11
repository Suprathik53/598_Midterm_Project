#!/usr/bin/env python3
"""Render the checked-in Markdown report and slides, including their real figures."""
import re
import textwrap
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

ROOT = Path(__file__).resolve().parents[1]
IMAGE = re.compile(r'^!\[([^]]*)\]\(([^)]+)\)$')


def clean(line):
    return line.replace('`', '').replace('**', '')


def render_report(path, output):
    lines = path.read_text(encoding='utf-8').splitlines()
    with PdfPages(output) as pdf:
        fig = None
        y = 0

        def page():
            nonlocal fig, y
            if fig is not None:
                pdf.savefig(fig); plt.close(fig)
            fig = plt.figure(figsize=(8.5, 11))
            y = .94

        page()
        for line in lines:
            match = IMAGE.match(line.strip())
            if match:
                image = (path.parent / match.group(2)).resolve()
                if not image.is_file():
                    raise FileNotFoundError(image)
                if fig is not None:
                    pdf.savefig(fig); plt.close(fig); fig = None
                fig, ax = plt.subplots(figsize=(11.7, 8.3))
                ax.imshow(plt.imread(image)); ax.axis('off')
                ax.set_title(match.group(1), fontsize=14)
                fig.tight_layout(); pdf.savefig(fig); plt.close(fig); fig = None
                page()
                continue
            if not line.strip():
                y -= .012
                continue
            heading = line.startswith('#')
            text = clean(line.lstrip('#').strip()) if heading else clean(line.strip())
            chunks = textwrap.wrap(text, width=88 if heading else 103, break_long_words=False) or ['']
            font = 14 if line.startswith('# ') else 12 if heading else 9.5
            spacing = .022 if heading else .0165
            if y - spacing*len(chunks) < .06:
                page()
            for chunk in chunks:
                fig.text(.075, y, chunk, fontsize=font, weight='bold' if heading else 'normal', va='top')
                y -= spacing
            y -= .006 if heading else .008
        if fig is not None:
            pdf.savefig(fig); plt.close(fig)


def render_slides(path, output):
    slides = path.read_text(encoding='utf-8').split('\n---\n')
    with PdfPages(output) as pdf:
        for block in slides:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            title = clean(lines[0].lstrip('#').strip())
            images = [IMAGE.match(line) for line in lines[1:] if IMAGE.match(line)]
            body = [clean(line) for line in lines[1:] if not IMAGE.match(line)]
            fig = plt.figure(figsize=(12, 6.75))
            fig.text(.055, .94, title, fontsize=25, weight='bold', va='top')
            if images:
                image = (path.parent / images[0].group(2)).resolve()
                if not image.is_file():
                    raise FileNotFoundError(image)
                ax = fig.add_axes([.05, .20, .90, .64])
                ax.imshow(plt.imread(image)); ax.axis('off')
                y = .17
                size = 13
            else:
                y = .77
                size = 19
            for paragraph in body:
                for text in textwrap.wrap(paragraph, width=110 if images else 75, break_long_words=False):
                    fig.text(.07, y, text, fontsize=size, va='top')
                    y -= .048 if images else .065
                y -= .025
            if y < .015:
                raise ValueError(f'Slide text overflows: {title}')
            pdf.savefig(fig); plt.close(fig)


if __name__ == '__main__':
    render_report(ROOT/'report'/'report.md', ROOT/'report'/'report.pdf')
    render_slides(ROOT/'slides'/'presentation.md', ROOT/'slides'/'presentation.pdf')
