---
name: cad-reverse-parametric
description: >-
  Reverse-engineer STEP/STL CAD parts and reconstruct them parametrically with a
  uv + Python toolchain (CadQuery/OCP, trimesh). Use when asked to investigate
  CAD impact of a hardware change (e.g. swapping a servo/motor/bearing), recover
  mounting-hole patterns / axes / envelopes from STEP files without the original
  parametric source, build an equivalent-shape-first parametric model, or check
  geometric equivalence between an original and a reconstructed part, or package
  validated STEP/STL artifacts for a 3D-printer slicer. Triggers:
  "CAD逆エンジニアリング", "STEPをパース", "パラメトリック再構成", "CAD影響範囲",
  "穴パターン抽出", "同等性チェック", "スライサー用に整理", "印刷用G-code",
  "工具アクセス", "締結確認", "配線干渉",
  reverse engineer a STEP, parametric CAD swap, prepare a printable CAD package.
---

# CAD Reverse-Parametric Toolkit (`cadre`)

Reverse-engineer existing CAD (STEP/STL) and rebuild it as a parametric model,
using only open Python libraries in a `uv` environment. Built for the workflow:
**measure the original → reconstruct an equivalent parametric shape → prove
equivalence → then change the parameter** (e.g. swap a servo).

## Non-destructive original-shape rule

Do not turn a local CAD concern into a full redesign. For imported STEP parts
without reliable design history, the original B-rep is the source of truth.
Parametric work must preserve the original shape first, then edit only the
approved local features.

Use this rule before implementing any geometry change:

1. Define the user's real objective, not just the local feature that caught
   attention. A suggestion such as "make the hole area rounder" may be partly
   right, but it does not authorize replacing the whole end of the part with a
   large circular flange.
2. Define a **change mask**: allowed faces/edges, local coordinate ranges, hole
   families, and functional dimensions. Everything outside the mask is
   preserve-by-default.
3. If the original has organic, asymmetric, forked, blended, or sculpted shape,
   do not remodel it from scratch unless the Stage-1 reconstruction proves
   geometric equivalence. Prefer local B-rep boolean/patch edits on the original
   STEP, or stop and report that human CAD judgement is required.
4. Make original-shape preservation the first acceptance gate. Tests for
   min-wall, boltability, and interference are necessary but not sufficient: if
   the unchanged outline, asymmetry, thickness, or neighboring clearances drift
   outside the change mask, the design fails even when all local tests pass.
5. Always compare original vs candidate visually in the same camera orientations
   (X/Y/Z, or six faces when needed) and numerically (bbox, surface distance,
   key edge/face families). Record the comparison before saying the design is
   done.

## Architecture (SOLID / KISS / DRY)

Two layers. Keep them separate; never let domain terms leak into the core.

- **`src/cadre/` — generic core.** File-agnostic, domain-agnostic, reusable,
  portable. Knows geometry, not servos.
  - `geometry.py` — `Envelope`, `Component`, fit test, screw classification.
  - `probes.py` — 3 tiers: `step_text_probe` (no kernel), `stl_geometry_probe`
    (trimesh), `brep_probe` (CadQuery/OCP). Keyword policy is **injected**.
  - `parametric.py` — `envelope_proxy`, `clearance_pocket`, `adapter_plate`
    driven by `Envelope` + hole lists; STEP/STL export.
  - `equivalence.py` — mesh bbox/volume/surface-distance compare + verdict.
  - `checks.py` — functional/characterization checks: `axes_collinear`,
    `hole_pattern_match`, `envelope_clearance`.
  - `intent.py` — `PartIntent`/`Feature`: a human-readable YAML **design-intent
    layer** (the "latent": what each feature is for, what to preserve).
  - `descriptor.py` — compact structured descriptor + prompt for LLM intent
    labelling (extract with code, label intent with an LLM — not raw STEP).
  - `impact.py` — `analyze_tree` orchestrator; classifier is **injected**
    (`RuleClassifier`), dependency-inverted.
  - `report.py` — CSV + Markdown writers (title/intro injected).
  - `cli.py` — `python -m cadre.cli {probe,inspect,edges,edge-match,equiv,scaffold}`,
    works on ANY file. `inspect` dumps bbox, cylindrical surface sense,
    angular spans and axial ranges. `axis_pt` is an axis reference point, not a
    face center; use `axial_range_mm` to locate the actual trimmed face.
    `edges`/`edge-match` bridge viewer selections back to B-rep edges.
- **`studies/<name>/` — specialized layer.** Thin. Supplies the domain: specs,
  keyword policy, classifier rules, drivers. `studies/xl430_lowcost/` targets the
  Dynamixel XL330→XL430 swap on this repo's `hardware/` tree.

> Rule of thumb: if a function names a servo or a part file, it belongs in a
> study, not in `cadre`.

## Setup

```bash
cd skills/cad-reverse-parametric
uv sync          # installs cadre (editable) + cadquery/OCP, trimesh, rtree, ezdxf
```

## The 3-tier probe (cheap → precise)

```bash
# Tier 1+3 on any STEP (text products/keywords + B-rep holes/axes/bbox):
uv run python -m cadre.cli probe path/to/part.step --brep

# Tier 2 on any STL (envelope, volume, watertight):
uv run python -m cadre.cli probe path/to/part.stl
```

Tier 1 (text) needs no CAD kernel — use it to triage hundreds of files fast.
Tier 3 (B-rep) recovers **cylindrical surface families**, not verified mounting
interfaces. The legacy `hole_families` field includes outside rounded profiles;
use `bore_families` (concave) and `outer_cylinder_families` (convex) to distinguish
them. Surface sense assumes an outward-oriented solid. `axes` counts distinct
axis lines; `faces` counts raw faces. Neither proves physical hole count,
blind/through status, or thread function. Diameter-based screw labels are guesses.
Confirm openings, material, axial spans and neighbouring faces before assigning
intent. Probes degrade gracefully without CadQuery.

For code/CAD reviews or a model that passes family checks but looks wrong, read
`references/geometry-review.md`. It describes executable negative checks and the
browser-to-B-rep evidence loop.

## Resolve viewer-selected edges to B-rep meaning

When a browser/CAD viewer reports selected edge metadata (edge indexes, lengths,
endpoints, or an owning node), do not stop at the UI label. Resolve the selection
against STEP topology:

```bash
# Print specific edge records: length, curve type, endpoints, circle data,
# and adjacent face types (plane/cylinder/etc.).
uv run python -m cadre.cli edges path/to/part.step --indexes 48,49,0

# When viewer edge indexes do not match the standalone STEP traversal, match by
# measured lengths first, then confirm by coordinates and curve/surface type.
uv run python -m cadre.cli edge-match path/to/part.step \
  --lengths 9.146160652,2.265450228,3.091413309 --tolerance 0.01
```

Use this workflow for selection interpretation:

1. Record the viewer owner path/id, selected indexes, lengths, and endpoints.
2. If the selection came from an assembly, identify duplicate display names by
   owner id, tree order, STEP occurrence lines, and coordinate range. Never rely
   on a repeated display name such as `connector` alone.
3. Run `inspect` on candidate standalone STEP files to identify nearby hole
   families and absolute centers.
4. Run `edges` when viewer indexes map directly; otherwise run `edge-match`.
5. Classify each selected edge:
   - `circle` adjacent to a concave `cylinder` = candidate bore/seat rim; confirm
     the opening and material. A convex cylinder instead indicates an outside
     profile or boss, not a hole.
   - `line`/`bspline` adjacent to a cylinder and a plane/surface = cut boundary
     or blend around a bore/seat.
   - `line`/`bspline` on only outer faces = outer profile/outline.
6. Report the conclusion as: selected owner, assembly occurrence, actual part
   STEP, local coordinate range, related hole family, edge classification, and
   design implication.

## Equivalent-shape-first reconstruction

1. **Measure** the original (tier 3) → hole pattern, axes, envelope.
2. **Reconstruct** parametrically with the *original* spec using `cadre.parametric`.
3. **Check geometric equivalence** before changing anything:
   ```bash
   uv run python -m cadre.cli equiv original.stl reconstructed.stl --fail-on-non-equivalent
   # exits non-zero unless verdict.equivalent is true
   # default thresholds: bbox ≤0.5mm, surface max ≤0.5mm, vol ≤2%
   ```
   This is a tolerance check using sampled surfaces, not an exhaustive proof of
   every feature. Also check topology and the declared preservation constraints.
4. **Swap the parameter** (new `Envelope`/spec) only after the gate passes, and
   re-export STEP/STL. Diagnostic prototypes must remain labelled as unvalidated;
   exporting one must not turn a failed gate into success.
5. **Interference-check** the new envelope proxy against neighbours.

See `references/workflow.md` for the full procedure and `references/servo_specs.md`
for the XL330/XL430 driver values (verify against the ROBOTIS e-Manual). To
visually inspect a STEP (reconstruction or original) in the browser CAD chili3d —
including how to rotate/pan/zoom and drive it headlessly — see
`references/chili3d_viewing.md`.

Study-specific acceptance helpers may wrap these generic gates. For example, the
current XL430 low-cost study has a preservation contract check for the extension
part:

```bash
uv run python studies/xl430_lowcost/validate_extension_preservation.py
```

## Assembly, fasteners and wiring

For assembly feasibility, bolt selection, tool clearance or cable routing, read
`references/assembly-serviceability.md`. Hole alignment and a collision-free
final pose do not prove that a part can be inserted, fastened or serviced. Keep
thread engagement, tool motion, hand clearance, assembly order and electrical
limits as separate evidence gates. Do not modify preserved geometry just to
clear a guessed tool or harness envelope.

## Package validated parts for a slicer

When the request includes preparing STEP files for a 3D printer, read
`references/step-to-slicer.md` and use
`studies/xl430_lowcost/prepare_print_package.py` after the CAD and mesh gates.
The package command copies accepted STEP/STL pairs into separate directories,
records hashes and exclusions, and can run OrcaSlicer headlessly for a Creality
K1C profile. It must not promote an old generated file when a design review has
blocked the corresponding part. A successful G-code slice is still not evidence
of assembly fit, strength, or safe operation.

For the mixed-servo follower geometry revision received on 2026-09-19, use
`studies/follower_geometry_revision/README_ja.md` first. Run its
`source/rebuild.py` against the repository's hashed `hardware/follower/step`
inputs, then use `studies/follower_geometry_revision/prepare_print_package.py`.
This revision has its own seven-part allow-list and validates every OrcaSlicer
plate; it is not an XL430-all-joints conversion and must not be merged
conceptually with the older XL430-only package.

For the all-XL430 static replacement received on the same date, read
`studies/all_xl430_revision/README_ja.md`. Never inherit an interference or
mounting-axis verdict from the mixed-servo baseline after replacing assembly
occurrences. Re-import and scan the converted assembly itself. Motor inventory,
leaf count, a readable STEP, and watertight reused meshes do not prove that the
new motor envelopes fit the retained brackets. The current all-XL430 prototype
has 54 post-conversion external intersections in the original `current` run.
The `j4-datum-20260922` placement-only correction has 46 (11 removed, 43 retained,
3 new), plus 168 same-motor internal overlaps counted separately. Its four
replacement rotation axes match the baseline, but seats, fasteners and retained
brackets are not accepted. Both revisions stay
under `outputs/all_xl430_revision/unaccepted/<run-id>/` and
`source/study.py print-package` re-validates every time and fails closed
(exit code 2) while any external interference or missing engineering evidence
remains.

## Run an impact study

```bash
PYTHONPATH=studies/xl430_lowcost \
  uv run python studies/xl430_lowcost/run.py <parts_dir> --out outputs/impact
# -> step_impact.csv, stl_stats.csv, brep.json, IMPACT_REPORT.md
```

## Retargeting to another change

Copy `studies/xl430_lowcost/` to a new study, edit `domain.py` (the two
`Component`s, the `KeywordPolicy`, the classifier rules). The core is untouched.
