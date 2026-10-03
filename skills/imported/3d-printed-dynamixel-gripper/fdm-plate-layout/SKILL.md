---
name: fdm-plate-layout
description: Compare and visualize OrcaSlicer print-bed arrangements, especially when automatic XY rotation may affect a one-plate job. Use for STL plate packing, support/time comparisons, and G-code placement review; not for changing a part's CAD design.
---

# FDM Plate Layout

Treat the chosen face on the bed (X/Y tilt) and rotation within the bed (Z yaw) as separate decisions. A packing request does not authorize changing the face on the bed: that can change support, strength, and mating-surface quality. Auto Arrange can rotate objects within the bed even when Auto Orient is not requested.

For an OrcaSlicer comparison, keep the same STL files and hashes, printer, filament, process profiles, and object count. Slice the current arrangement and a candidate using `--arrange 1 --allow-rotations=0`. In OrcaSlicer 2.4.2 this disables Auto Arrange's rotation; use the `=0` form, since a space-separated `0` is treated as an input filename. Confirm support for the option with the installed slicer's `--help` before relying on it. If a 0/90-degree choice is needed, prepare an explicit object placement and inspect its transforms; the CLI switch only permits or forbids automatic rotations.

Use expanded XY envelopes (brim, object spacing, bed keepouts) for an orthogonal rectangle-packing candidate. Rectangular feasibility is conservative for irregular parts and does not prove minimum print time. Accept a candidate only after OrcaSlicer reports every expected object on one plate with no unreviewed warning. Compare the slicer's estimated time and material, and inspect support contact regions in the full layer preview. XY yaw alone does not imply a dimensional-accuracy improvement; assess critical dimensions with a printed coupon or the actual part.

To inspect two G-codes from OrcaSlicer, run the bundled report with a fresh output directory:

```bash
uv run python skills/fdm-plate-layout/scripts/compare_gcode.py \
  --gcode current=path/to/current.gcode \
  --gcode constrained=path/to/constrained.gcode \
  --result current=path/to/current/result.json \
  --result constrained=path/to/constrained/result.json \
  --bed 220 220 --out outputs/plate-comparison-unique-id
```

It writes `comparison.json` and `comparison.png`. The plot uses extruded XY paths, including I/J-centered `G2/G3` arcs, with a projected outline and first-layer traces for each object. Unsupported arc forms fail explicitly rather than silently dropping material. Gray traces show first-layer support footprints, not every upper support contact. The support amount is estimated from G-code feature tags and deposited E; use the slicer's total filament figure as the total-material authority. Check the plot for part separation, labels, and printable bed bounds. Keep candidate G-code separate from existing print jobs until a choice is made.

OrcaSlicer references: [Auto Arrange](https://github.com/OrcaSlicer/OrcaSlicer/wiki/prepare_auto_arrange) and [CLI options](https://github.com/OrcaSlicer/OrcaSlicer/wiki/cli_misc).
