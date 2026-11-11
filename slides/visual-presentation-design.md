# MPI heat diffusion presentation design

## Intent and scope

Create a standalone 12-slide HTML presentation for an 8–10 minute CS598 class talk. Explain the numerical problem and MPI implementation, then present the extended study's measured results and limitations. Preserve the existing Markdown and PDF deliverables. Use the linked Visualize skill for the HTML presentation and Unslop for its visual audit.

## Direction

- Product: A research presentation explaining how MPI communication affects Jacobi and conjugate gradient for implicit heat diffusion.
- Character: Precise, technical, warm.
- World: Scientific plots and a laboratory notebook, with paper-toned surfaces and graphite text.
- Moments: A real temperature field and large, directly labeled performance charts.
- Signature: A small five-point stencil mark used in slide numbering and diagram labels.

## Audit of the existing presentation

The existing PDF has restrained styling rather than heavy decorative slop. Its content needs better presentation hierarchy:

- Cover: The title and subtitle occupy a small area while most of the canvas is empty.
- Model slide: Paragraphs describe the model without a visual relationship between the PDE, stencil, and linear solve.
- Strong-scaling slide: Runtime and communication share a small figure with four series each. Labels are too small for projection.
- Results: Default chart colors change by solver and grid size, making comparison harder than necessary.
- Navigation: The PDF has no interactive overview, speaker notes panel, or chart configuration controls.

Keep the restrained appearance and scientific content. Improve composition, chart legibility, and navigation rather than adding decoration.

## Slide sequence

1. Heat diffusion in parallel: research question and measured temperature field.
2. The implicit heat model: backward Euler and the five-point matrix action.
3. MPI decomposition: owned cells, halos, neighbors, and global reductions.
4. Jacobi and conjugate gradient: iteration mechanics and synchronization tradeoffs.
5. Experimental design: hardware, rank counts, five trials, and reset warm-up.
6. Strong scaling: median five-step runtime, trial ranges, and grid-size selection.
7. Communication crossover: MPI fractions and sampled crossover brackets.
8. Why CG wins here: measured iteration counts and selected runtime comparisons.
9. Weak scaling: constant cells per rank, end-to-end time, and per-update cost.
10. Timestep sensitivity: r=0.5,2,8 and its effect on iterations and runtime.
11. Correctness and limitations: independent validation, timing interpretation, and topology caveat.
12. Conclusions and reproducibility: supported findings and source links.

## Approach

Use one self-contained HTML file with inline styles, embedded datasets, and editable diagrams. This follows the requested Visualize format and allows keyboard navigation, overview, speaker notes, and browser printing. Keep dependency-free visual fallbacks so the scientific content remains visible without network access. A conventional PPTX would prioritize desktop editing but would not follow the requested HTML skill as directly. A scrolling report would support reading but would be less suitable for a timed class presentation.

## Visual and interaction rules

- Paper background, graphite text, orange for CG, neutral dark gray for Jacobi. Keep those meanings consistent.
- One dominant diagram or chart per slide. No decorative gradients, glows, emoji labels, or repeated card grids.
- Align spacing to a 4 px scale. Use large slide titles and readable chart labels.
- Quiet previous/next controls, keyboard navigation, overview, notes, light/dark theme, and print/PDF support.
- Desktop presentation and 16:9 PDF are the acceptance targets, as subsequently clarified by the user. Reduced-motion support and visible keyboard focus.
- Keep factual caveats on relevant slides and detailed source references in speaker notes.

## Evidence and acceptance

The source is the current C++ implementation, report, validation logs, field snapshot, and extended study. All 56 summary configurations were independently checked against the 280 raw JSON records, including median runtimes, successful completion, and residual tolerance.

Check every slide visually, exercise desktop navigation and controls, verify source data and units, and audit the finished interface in Unslop's nine-pass order: spacing, color, icons, copy, type, layout, details, visuals, motion. Mobile acceptance is not required.

## Skill attribution

- Visualize by careerhackeralex: https://github.com/careerhackeralex/visualize (MIT).
- Unslop by Damir Sokolovsky: https://github.com/heydamir/unslop (CC BY 4.0).

## Approval and execution

The user approved this direction with “sounds good.” Implement the deck directly in this session. First embed the verified measurements and diagrams, then add presentation controls, and finally inspect the rendered deck and apply the Unslop audit. Keep existing deliverables unchanged and do not commit or publish.
