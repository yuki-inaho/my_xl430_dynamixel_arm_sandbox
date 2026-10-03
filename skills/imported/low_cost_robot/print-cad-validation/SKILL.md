---
name: print-cad-validation
description: Validate CAD/STEP/STL artifacts before 3D printing, especially when a generated or reverse-engineered part must preserve source geometry while producing slicer-safe meshes. Use when asked to check print readiness, package STL/STEP files for printing, detect or repair non-watertight/non-manifold STL files, verify holes/fastening interfaces before printing, or record validation results in JSON/DuckDB-like lightweight audit stores.
---

# Print CAD Validation

Use this skill to separate three claims that are often confused:

1. **CAD preservation**: the generated part still matches the approved STEP/B-rep intent.
2. **Printability**: the STL is a watertight manifold volume that a slicer can process.
3. **Buildability**: holes, fasteners, contact faces, screw depth, and tool access are actually certified.

Never treat an existing STL as print-ready just because it exists. Run explicit checks and report
which claim is proven.

## Workflow

1. Identify print candidates.
   - Prefer generated `outputs/parts/*.step` and `*.stl` pairs when present.
   - Include the source STEP/STL paths in the report.
   - If the repo has local command rules such as `rtk`, obey them.

2. Run existing project gates first.
   - Unit/regression tests.
   - Rule catalog or design-intent validation if available.
   - Hole-family/liaison/assembly checks if the part bolts to motors, horns, links, or frames.

3. Run STL preflight.
   - `watertight == true`
   - `is_volume == true`
   - winding is consistent
   - boundary/non-manifold edge count is zero
   - bbox, triangle count, and volume are recorded

4. Classify failures before repair.
   - Boundary holes may indicate missing faces or an intentionally open model.
   - Non-manifold edges at exact tangencies usually require CAD-side print relief, not blind mesh patching.
   - Compare with source STEP/STL before claiming the generator caused the issue.

5. Repair only as a derived print artifact.
   - Do not overwrite canonical CAD unless the design owner approved the change.
   - Prefer minimal CAD-side repair that preserves functional holes/seats and adds/removes material only in a documented print-specific scope.
   - Re-check hole centers/diameters after repair.
   - Put repaired outputs in a separate print package directory, e.g. `outputs/print/`.

6. Report pass/fail honestly.
   - A print package can pass STL printability while assembly buildability remains unapproved.
   - Keep nonblocking characterization findings visible, especially hole-center mismatch, screw-depth unknowns, and tool-access unknowns.

## Reusable Script

Use `scripts/stl_preflight.py` for generic STL mesh checks when a project lacks its own checker:

```bash
python path/to/print-cad-validation/scripts/stl_preflight.py part1.stl part2.stl --json
```

It reports watertightness, volume validity, winding consistency, bbox, triangle count, and
boundary/non-manifold edge examples.

## Repair Standard

When generating a print-only repair, the report must include:

- source file and repaired file
- exact repair strategy
- changed bbox/volume
- whether holes and mounting centers were preserved
- whether the repaired STL is watertight and `is_volume`
- remaining buildability limits, if any

Do not hide slicer risks by weakening tests. If the part only passes after a repair, say that the
canonical artifact failed print preflight and the derived print artifact passed.
