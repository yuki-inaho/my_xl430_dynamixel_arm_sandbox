# Camera jig: single-job trial print

Date: 2026-09-22. The user requested all newly made jig parts in one print job
and confirmed the previous Ender-3 Pro / 0.4 mm nozzle / PLA setup.
This authorizes prototype printing, not mechanical or operational acceptance.

## Delivered File

- SD volume: `sd_card_3d`, removable Transcend card, `/dev/sdd1` at time of copy.
- SD root filename: **`camjig.gcode`**.
- Source: `outputs/print-camera-20260922-final/plate_1.gcode`.
- SHA-256: `ff535ae69a3583126634f063f86afe6b45f5cddeb75d59d1695b367deccf5c17`.
- Existing SD files were preserved. The copy was flushed with `sync -f`,
  reopened and hashed; source and destination hashes matched.
- `udisksctl unmount -b /dev/sdd1` succeeded. The card can be removed.
- Printing was NOT started remotely. No serial ports or motors were accessed.

Only the `final` run above is the SD deliverable. The `r1` and `r2` directories
are diagnostic runs and were not copied to the card.

## Contents And Settings

| Part | Quantity | Print orientation |
|---|---:|---|
| saddle | 1 | Upright on clamp bottom, with generated supports |
| front_jaw | 1 | Broad face flat, rotation +90 degrees about X |
| camera_spacer | 1 | Original local XY plane flat |

All three parts print layer by layer on **one plate**, not sequentially by
object. No motors, arm links, camera electronics or fasteners are printed.
The source CAD is unchanged; print preparation applies only rigid transforms.

| Setting | Value |
|---|---|
| Printer / nozzle | Creality Ender-3 Pro / 0.4 mm |
| Slicer | OrcaSlicer 2.4.2, headless CLI |
| Material | Generic PLA |
| Hotend / bed | 220 C / 60 C; initial hotend warmup 150 C |
| Model / initial layer height | 0.20 / 0.20 mm |
| Walls / infill | 4 / 35% gyroid |
| Supports | Normal automatic, including supports on model where needed |
| Support top / bottom gap | 0.20 / 0.20 mm |
| Support interface / XY gap | 3 layers / 0.35 mm |
| Brim | 5 mm, separation gap 0.1 mm |
| First-layer speed | 20 mm/s |
| Estimate | 2 h 42 min 37 s; 24.09 g PLA |

Support layers can occur between model layers. The reported 428 layer changes
are not a claim of 428 model layers at 0.20 mm. Actual extrusion height is
63.8 mm; the end-of-job parking move reaches Z150 mm.

## Verification And Warning Decision

- `uv run pytest -q`: **17 passed**, including rejected disconnected/open meshes,
  out-of-bounds moves, wrong temperatures, sequential printing, missing heater
  shutdown, pause commands and unreviewed slicer warnings.
- `uv run ruff check camera_jig/prepare_print.py tests/test_prepare_print.py
  scripts/orca_presets.py scripts/preview_gcode.py`: passed.
- Input STEP hashes match the source CAD validation record. Each print STL is
  closed, consistently wound, one connected component, with positive volume and
  volume deviation from B-rep below 0.5%. No implicit slicer mesh repairs.
- One plate, exactly three allowed objects, all present in emitted G-code.
  Motion is within the printer envelope and final heater shutdown is present.
- Actual extrusion paths were rendered and visually inspected in
  `outputs/print-camera-20260922-final/toolpath-preview.png`: separated objects,
  bed-contained layout, saddle supports and retained frame openings visible.
- G-code validation: `outputs/print-camera-20260922-final/gcode_validation.json`.
  Inputs, transforms, profile snapshots and slicer binary hash are retained
  beside it in `preparation.json`, `machine.json`, `process.json`, `filament.json`,
  `job.3mf`, `result.json` and `slicer.log`.

There is **one reviewed warning**, not zero warnings:
`bed_temperature_too_high_than_filament` / `1000C001` in the 3MF archive.
Orca 2.4.2 compares maximum bed temperature with configured vitrification
temperature using `>=`; this PLA preset sets both to 60 C.
See the [version-pinned Orca implementation](https://github.com/OrcaSlicer/OrcaSlicer/blob/v2.4.2/src/libslic3r/GCode/GCodeProcessor.cpp#L5551-L5577).

Decision: retain the standard 60 C bed used in the previous test print.
Do not falsify the material temperature to suppress the warning. The validator
defaults to rejection and permits this specific reviewed condition only with
PLA, a 60 C hot-plate preset and matching actual G-code. Tests confirm that a
65 C bed or additional warning remains rejected. This software warning review
does not establish PLA strength, creep life or real adhesion.

## Printing And Assembly Checks Still Required

Select `camjig.gcode` on the printer and observe first-layer adhesion. After
cooling, remove supports and brim, clear the holes and inspect the thin frame
and support-contact surfaces before trial fitting. Do not force a poor fit.

Fit camera and spacer to the saddle on the bench before attaching the clamp:
installed-camera tool access is known to fail in the checked arm pose.
Follow [the assembly sequence and unresolved checks](CAMERA_JIG.md).
Fasteners and tools are not yet selected. Retention, printed fit, PLA creep,
camera field of view, wiring and full joint-range clearance remain unverified.
The `fabrication_approved: false` field in the CAD evidence remains unchanged;
it denotes missing engineering acceptance, not withdrawal of this explicitly
requested trial-print deliverable.

## Reproduction

From the repository root, use a new output directory each time:

```bash
rtk proxy uv run python -m camera_jig.prepare_print --out outputs/print-camera-next
rtk proxy uv run python scripts/preview_gcode.py \
  outputs/print-camera-next/plate_1.gcode \
  outputs/print-camera-next/toolpath-preview.png
rtk proxy uv run pytest -q
```

Inspect the new validation, 3MF warnings and preview before any later SD copy.
The system presets are local inputs and may change; this run's flattened
snapshots and slicer hash are the evidence for the delivered job.
