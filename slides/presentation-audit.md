# Presentation design audit

## Direction

The approved direction is precise, technical, and warm: paper-toned slides, graphite text, and orange for CG. The temperature field and measured charts carry the color. The user subsequently narrowed the acceptance target to desktop presentation and PDF; mobile support is not required.

## Unslop passes

1. **Spacing:** Aligned the slide layout to a consistent spacing scale. Reserved footer clearance, including under the MPI decomposition caption and chart findings.
2. **Color:** Used one neutral ramp. CG remains orange and Jacobi graphite across charts. The field colors encode temperature.
3. **Icons:** Removed emoji from the Visualize skeleton's menu. Navigation uses quiet monochrome symbols.
4. **Copy:** Replaced broad labels with the actual numerical model, solver behavior, and measured findings. Retained limits on interpretation.
5. **Type:** Used a consistent sans-serif hierarchy, tabular figures, and monospaced axis labels. Enlarged chart labels relative to the source slides.
6. **Layout:** Gave the model, decomposition, runtime, and communication findings separate compositions. Avoided repeated card grids.
7. **Details:** Added visible focus states, descriptive chart alternatives, accessible data tables, overview, notes, timer, and theme controls.
8. **Visuals:** Used the stored temperature snapshot and real benchmark values. Charts and diagrams are inline SVG. No stock imagery or decorative filler.
9. **Motion:** Kept one short entrance transition and reduced-motion support. Removed ornamental movement.

## Review findings addressed

- Corrected the weak-scaling time-per-update axis from 0–6 ms to 0–1.3 ms.
- Increased the chart width and retained explicit units and logarithmic-axis labels.
- Added visible N labels that survive printing.
- Reduced chart height and constrained the decomposition diagram to preserve footer clearance.
- Kept readable chart widths in the narrow-screen CSS. Mobile acceptance was subsequently waived by the user; the deliverables target desktop and 16:9 PDF.

## Verification

- Compared all 56 embedded configurations with the stored summary CSV. The preceding source review independently checked the CSV against all 280 raw records.
- Parsed the generated JavaScript with Node.
- Opened the HTML in Chrome. Verified keyboard advancement, slide overview, switching from N=512 to N=1024, and the corresponding speaker notes.
- Printed the final deck through Chrome as 12 landscape PDF pages, 960 × 540 points each.
- Rendered and inspected all 12 PDF pages as a contact sheet, with enlarged checks of the decomposition and runtime slides. Checked that PDF text stays within every page's bounds.

## Use

Open `implicit-heat-presentation.html` in a desktop browser. Use Left/Right to navigate, O for the overview, N for speaker notes, F for fullscreen, T to start/pause the timer, and R to reset it. The menu provides theme, PNG, and print controls. The PDF is ready for a projector or sharing.

The core presentation, diagrams, data, and controls are embedded. Optional web fonts and PNG export use external resources. Links to the report, README, and CSV require the surrounding repository. Printing exports the currently selected chart state on each slide; the supplied PDF uses the default states.

## Credits

Created with [Visualize](https://github.com/careerhackeralex/visualize) by careerhackeralex, MIT. Design audit follows [Unslop](https://github.com/heydamir/unslop) by Damir Sokolovsky, CC BY 4.0. The approved deck uses project-specific scientific content rather than a reproduced reference design.
