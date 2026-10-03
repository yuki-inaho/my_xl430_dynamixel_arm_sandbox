# Camera-Mount Handoff Code Index

Updated: 2026-09-24. Paths are relative to the repository root. This index is a
navigation aid; the cited acceptance records and exact STEP inputs remain the
source of truth.

## Current Task

Design a new camera-mount candidate above the ID5 XL430 motor, looking diagonally
down at the PG3 grasp zone. The camera is not purchased. Preserve the 28 x 28 mm
four-hole interface, but do not infer the camera body or field of view from that
pattern. The old P05-side mount is historical and rejected as the requested
layout. This task has not yet implemented the new mount or approved fabrication.

Start with:

1. `AGENTS.md`
2. `docs/CAMERA_MOUNT_ID5_CORNER.md`
3. `specs/camera_mount_id5_corner.yaml`
4. `temp/workdoc_Sep24-2026_camera_mount_id5_corner.md`
5. `docs/HANDOFF.md` and `docs/REQUIREMENTS.md`

## Code Map

| Path | Responsibility / status |
|---|---|
| `camera_jig/spec.py` | Legacy P05-side camera-mount parameters; do not silently repurpose. |
| `camera_jig/build.py` | Legacy mount and assembly candidate generator. |
| `camera_jig/serviceability.py` | Legacy tool-access and assembly-service checks. |
| `gripper_design/pg3_id5.py` | Current PG3 / ID5-driven end-effector assembly representation. |
| `gripper_design/pg3.py` | PG3 linkage geometry and pose definitions. |
| `gripper_design/pg3_crank_representation.py` | Crank geometry representation used by assembly candidates. |
| `gripper_design/pg3_installation.py` | Installation and mating-interface checks. |
| `gripper_design/assembly_contracts.py` | Assembly-level acceptance contracts and status handling. |
| `gripper_design/fastener_ledger.py` | Fastener stack and evidence bookkeeping. |
| `gripper_design/interface_envelopes.py` | Mating-interface geometry and clearance envelopes. |
| `gripper_design/p05_cable_relief.py` | Local P05 cable-clearance candidate; preserve as a separate arm change. |
| `scripts/review_pg3_id5.py` | Re-evaluate the ID5-only arm candidate. |
| `scripts/review_p05_cable_relief.py` | Review P05 local cable-relief candidate. |
| `scripts/assembly_io.py` | STEP assembly read/write and placement helpers. |
| `simulation/pg3_scene.py` | PG3 scene and pose visualization/simulation support. |
| `tests/` | Regression tests; inspect fixtures before changing legacy contracts. |
| `skills/cad-reverse-parametric/SKILL.md` | Project CAD reverse-engineering and validation workflow. |
| `skills/playwright-cli/SKILL.md` | Independent browser automation workflow for headless visual checks. |
| `skills/write-workdoc-uv/SKILL.md` | Workdoc authoring workflow. |
| `skills/review-written-workdoc/SKILL.md` | Workdoc review workflow. |

There is intentionally no `camera_jig/id5_corner.py` implementation yet. Add a
separate variant and dedicated tests; keep the old `camera_jig/` behavior intact
until a reviewed migration is explicitly chosen.

## CAD Inputs And Evidence

| Path | Meaning |
|---|---|
| `references/arm-r3/arm_XL430_R3.step` | Source arm geometry; preserve unchanged. |
| `references/arm-r3/P05_wrist_XL430.step` | ID4-ID5 link source geometry. |
| `references/pg3-c9/PG3_C92_J28/CAD/parts/` | PG3 donor part STEP files. |
| `references/robonine/` | SO101-referenced camera mounting pattern and source/license notes. |
| `outputs/pg3-id5-only-r1/arm_camera_{open,mid,closed}_ID5_CANDIDATE.step` | Earlier three-pose full-arm candidate. |
| `outputs/pg3-id5-p05-windows-r2/ID5_mid_P05_windows_CANDIDATE.step` | Latest provisional mid-pose arm candidate. |
| `outputs/pg3-id5-p05-windows-r2/review.json` | Existing candidate review: 1806 PASS / 1 ERROR / 6 UNKNOWN / 0 FAIL; not fabrication-approved. |
| `outputs/pg3-id5-chili3d-20260924/` | Headless Chili3D full-arm views for visual reference. |
| `outputs/camera-jig-20260922-r11/` | Rejected P05-side camera candidate; historical comparison only. |

The current P05-window candidate is not a validated whole-arm release. Preserve
its ERROR/UNKNOWN findings and the physical ID-to-CAD mapping uncertainty.
Generated `outputs/` and `temp/` are Git-ignored; the handoff archive includes
only a curated set of outputs and workdocs.

## Reproduction Environment

```bash
rtk proxy uv sync --locked
rtk proxy uv run pytest -q
rtk proxy uv run ruff check .
```

Use a unique output directory for new runs. Do not generate G-code, print, write
to removable media, energize motors, or imply fabrication approval as part of
the camera-mount design task.
