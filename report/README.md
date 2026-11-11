# Revised project report

`report.pdf` is the five-page, reader-focused report. `report.tex` follows the supplied article template with the team header, numbered sections, equations, tables, and figures. It contains no code listings. `report.md` contains the same narrative for easy reading in the repository.

## Compile the LaTeX source

Keep `report.tex` beside the `figures/` directory. Compile from this directory with `pdflatex report.tex`, or upload `report-latex-source.zip` to Overleaf and choose `report.tex` as the main document. The source ZIP includes both figure PDFs.

A LaTeX compiler was unavailable during creation. The supplied PDF was rendered locally from the same report content using PyMuPDF, with a matching article layout. Compiling the LaTeX source may produce different line and page breaks.

## Regenerate from the measured data

From the project root, run `python3 report/build_report.py`. It requires Matplotlib and PyMuPDF. It rebuilds the PDF, LaTeX, Markdown, tables, and figures from `results/extended-analysis-12312735/summary.csv`. The narrative reflects the current measurements and should be reviewed if those measurements change. This step does not rerun experiments on the cluster.

The older `scripts/render_pdf.py` also writes `report/report.pdf`, but uses the previous simple Markdown renderer. Use the report builder above to retain the revised layout.
