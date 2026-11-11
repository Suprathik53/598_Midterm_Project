# Self-contained presentation

The separate 18-slide edition is `implicit-heat-self-contained.html`, with `implicit-heat-self-contained.pdf` for sharing or projection. It preserves the original deck's paper, graphite, orange, and temperature-field visual language.

The original `implicit-heat-presentation.html` and `.pdf`, and the older `presentation.md` and `.pdf`, remain byte-for-byte unchanged.

## What is different

- Defines grid size N, MPI rank count P, halos, global reductions, residual, physical steps, and solver iterations.
- Explains the 56 study-specific groups and five repeats that produce 280 runs, including settings reused across studies.
- Describes timing, warm-up/reset, accuracy checks, and process placement.
- Gives each grid size and each weak-scaling metric its own visible slide. Essential findings require no toggles or speaker notes.
- Includes interpretation next to each result, rather than relying on a separate speaking script.
- Retains the waiting/imbalance caveat, one-node versus two-node baseline distinction, and different physical durations at fixed r.

The audience is assumed to read the deck in order. Speaker notes contain supplementary provenance. All essential explanations are visible in both deliverables.

## Rebuild

From the project root:

```
python3 scripts/build_self_contained_deck.py
python3 scripts/render_self_contained_pdf.py
```

The builder reads the original HTML and verifies its 56 embedded rows against the current summary CSV, then writes only the new HTML file. The PDF renderer uses PyMuPDF and the same visible text and SVG evidence. It renders directly without opening a browser; line breaks can differ from browser printing. Both formats target desktop viewing and 16:9 projection.

## Verification

- Original deck file hashes checked before and after generation.
- Eighteen slides and PDF pages verified.
- All essential chart states included visibly, with units, parameters, and interpretation.
- Measured data compared with the source summary CSV.
- Generated JavaScript syntax checked with Node.
- All PDF pages rendered and visually inspected, including chart labels, tables, and dense text layouts; text bounds checked.
- The new HTML was not visually inspected in a browser during this revision. The existing navigation controller is retained and the user will open the file directly.

## Credits

Created using [Visualize](https://github.com/careerhackeralex/visualize) by careerhackeralex (MIT). The visual direction follows [Unslop](https://github.com/heydamir/unslop) by Damir Sokolovsky (CC BY 4.0).
