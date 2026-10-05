# R3/C7 cap grasp — reproducible nominal simulation

Offline MuJoCo experiment: four arm joints, one driven C7 jaw, six asymmetric scanfit outer shapes, and the long D405 R5 65° candidate. Physical ID5 drives the jaw; it is not a fifth arm rotation joint. CAD labels and hardware encoder calibration remain separate.

This package imports and improves the external 18-part submission identified in `SOURCE_MANIFEST.json`. Source geometry, final scene, controller gains/force limits, and evaluation thresholds remain unchanged. Earlier failed trials and sensitivity trials are retained, including raw per-step states and losslessly compressed contacts. Public material contains code, model data, synthetic imagery and technical records. Real captures, conversations and the original archive remain local.

## Run from this directory

```sh
uv sync --frozen
MUJOCO_GL=egl uv run --no-sync python run.py --seed 0 --output results/replayed-nominal
uv run --no-sync python evaluate.py results/replayed-nominal
uv run --no-sync python audit_raw_trial.py results/replayed-nominal
MUJOCO_GL=egl uv run --no-sync python run.py --seed 0 --no-close --output results/replayed-no-close
uv run --no-sync pytest -q tests
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
MUJOCO_GL=egl uv run --no-sync python report.py
```

The no-close trial is expected to exit 1 and record FAILURE/NO_GRIP/INSUFFICIENT_LIFT. Existing output directories are never overwritten. `report.py` renders the committed `review-repeat` and `review-no-close` physics traces; replaying a trace to render it is different from reexecuting dynamics with `run.py`. Contact readers accept either `contacts.jsonl` or `contacts.jsonl.gz`, not both. Decompression restores the original bytes.

The committed model and plan are ready to run. After deliberately editing the builder or IK, regenerate them with the original final settings:

```sh
uv run --no-sync python build_scene.py
uv run --no-sync python verify_model.py
uv run --no-sync python ik.py --fixed-pitch -50 --y-offset 0 --close-angle 90 --grasp-pitch -50 --grasp-z-offset .006
```

The builder uses only hash-verified bundled inputs and caches. A stale source, changed scale, missing input, altered cache part, or changed model mesh fails explicitly. It does not search neighbouring repositories or regenerate an input manifest to conceal changes. When intentionally creating new proxy assets, record and review the new source/cache hashes before adopting them.

Python 3.12 and numerical/render dependencies are pinned in `pyproject.toml`/`uv.lock`. The renderer needs working EGL and the DejaVu Sans font discoverable by Pillow; MP4 generation additionally needs ffmpeg. PNG evidence is generated even when ffmpeg is unavailable. No serial, camera, hardware transport or live actuator connection is used.

## Evidence and limits

`review-verification.json` records fresh nominal/repeat/no-close results and their raw-state comparison against the imported final trial. `raw-audit-review-repeat.json` independently recomputes FK, contact forces and acceptance. `REPORT.html` shows two viewpoints, stage images, metrics, all retained failures and sensitivity results. Full excluded collision group pairs are in `model/collision_pairs.json`; summary exclusions are in `collision-exclusions.json`.

Fixed success contract: cap bottom at least 20mm above initial support for 2 continuous seconds in hold, bilateral force-bearing contact at least 80%, grip-frame center displacement at most 5mm, approach position error at most 2mm; no forbidden collision, boundary violation or numerical failure. Tilted-cylinder bottom and every physics step are evaluated. The planned hold lasts 2.5 seconds; a later slip fails the whole trial even if an earlier 2-second interval passed. Release after hold deliberately lets the cap fall.

The target is registered nominally: box height50mm, cap center[0,180,57.5]mm, diameter28mm, height15mm, mass1.5g, friction0.7. Contact impratio10 is an unmeasured numerical assumption. Half timestep succeeds but increases drift; low friction and low mass fail. This is not a claim of material robustness or successful real hardware grasping.

Adjacent arm-body pairs, same-rigid-body pairs and declared mounting pairs are excluded as whole groups. Classified pair coverage is not proof of testing excluded contacts. Results mean **no forbidden contact under this declared policy**, not a verified collision-free physical arm range. Mounting contact ROI, deformable softtip interiors, all motor details, cables, servo-to-CAD phase and base-camera extrinsics remain unverified. The actual holder's 65°/75° revision is unresolved.

## Source model identity

Upstream arm: [yuki-inaho/low_cost_robot](https://github.com/yuki-inaho/low_cost_robot), user's `all-xl430-arm` branch family, R3 donor `arm_XL430_R3.step`. Recorded software reference: [f29f33b3b99320b3ad35171ec08897bede459fbb](https://github.com/yuki-inaho/low_cost_robot/tree/f29f33b3b99320b3ad35171ec08897bede459fbb); this is not proof of the exact printed mesh revision. Bundled `source_inputs/design_reference/{manifest,joints}.json` and all mesh hashes preserve the concrete donor identity. Gripper uses the old C7 r14mm/L24mm crank-slider design, not the later C9/V2 jaw. Holder is the long R5 65° candidate from the September24 design family. No new fabrication or assembly approval is inferred.

Model semantics: normal gravity, independent free cap, bounded arm1Nm/jaw0.08Nm actuation, five planar jaw coordinates constrained by rank4 closure to one effective jaw DOF. Original viewer had no contact dynamics and used mocap for rods; the dynamic model replaces that mechanism with passive coordinates and connect constraints. Five source-FK poses are verified by `verify_model.py`.

Review and completion records: `../../diary/2026-10-05/sim-grasp-review/`. The original full archive is deliberately not versioned.
