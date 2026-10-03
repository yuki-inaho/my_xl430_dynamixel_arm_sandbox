# Joint-Space Safety Protocol

This document records the reusable protocol used to confirm reachable,
collision-free joint-space regions for the low-cost robot arm.

The canonical pose identity is the actuator-order joint vector:

```text
q = [joint1, joint2, joint3, joint4, joint5]  # radians
```

DH parameters are useful for describing the kinematic chain, but they are not
the best audit key for collision safety. Collision safety depends on a concrete
model, a concrete joint vector, contact pairs, penetration thresholds, and
tracking error. Therefore this protocol records safety as replayed `q` vectors
plus replay evidence.

## Protocol

1. Choose a model pair.
   - Baseline model: `simulation/low_cost_robot/scene.xml`
   - XL430 proxy model: `temp/sim_xl430proxy/scene_xl430proxy.xml`
2. Generate a baseline reference set.
   - A reference pose is accepted only when it is reachable and collision-free
     in the baseline model.
3. Replay that reference set on the candidate model.
   - A candidate pose is safe when `ok=true`.
   - In `scripts/replay_poses.py`, `ok=true` means:
     - `reachable=true`
     - `self_interference_mm <= thresholds.penetration_mm`
4. Summarize the candidate replay JSON with
   `scripts/jointspace_safety_report.py`.
   - The report groups results by single joint levels and focus joint tuples.
   - The default focus tuple for this arm is `[joint2, joint3, joint4]`,
     because the dominant XL430-proxy loss is `joint4` versus `joint2`.

## Reproduction Commands

Quick 3-level smoke grid:

```bash
rtk bash -lc 'uv run --group sim python scripts/replay_poses.py \
  --model simulation/low_cost_robot/scene.xml \
  --emit-grid --fractions=-0.5,0,0.5 \
  --settle 1.5 \
  --save-reachable temp/replay_baseline_targets_smoke.json \
  --json > temp/replay_baseline_smoke.json'

rtk bash -lc 'uv run --group sim python scripts/replay_poses.py \
  --model temp/sim_xl430proxy/scene_xl430proxy.xml \
  --poses temp/replay_baseline_targets_smoke.json \
  --settle 1.5 \
  --json > temp/replay_xl430proxy_smoke.json'
```

5-level grid used for the current XL430-oriented finding:

```bash
rtk bash -lc 'uv run --group sim python scripts/replay_poses.py \
  --model simulation/low_cost_robot/scene.xml \
  --emit-grid --fractions=-0.6,-0.3,0,0.3,0.6 \
  --settle 2.0 \
  --save-reachable temp/replay_baseline_targets_5level.json \
  --json > temp/replay_baseline_5level.json'

rtk bash -lc 'uv run --group sim python scripts/replay_poses.py \
  --model temp/sim_xl430proxy/scene_xl430proxy.xml \
  --poses temp/replay_baseline_targets_5level.json \
  --settle 2.0 \
  --json > temp/replay_xl430_oriented.json'
```

Generate a reusable safety report:

```bash
rtk bash -lc 'uv run python scripts/jointspace_safety_report.py \
  --input temp/replay_xl430_oriented.json \
  --joint-names joint1,joint2,joint3,joint4,joint5 \
  --focus-joints joint2,joint3,joint4 \
  --output-md temp/jointspace_safety_xl430_oriented.md \
  --output-json temp/jointspace_safety_xl430_oriented.json'
```

## Current XL430-Oriented Result

Source replay:

- `temp/replay_xl430_oriented.json`
- Model: `temp/sim_xl430proxy/scene_xl430proxy.xml`
- Thresholds:
  - self penetration limit: `2.0 mm`
  - tracking tolerance: `0.2 rad`

| metric | value |
| :--- | :--- |
| baseline-safe reference poses replayed on XL430 proxy | `2001` |
| safe on XL430 proxy | `1637` |
| lost on XL430 proxy | `364` |
| lost rate | `18.2%` |
| worst self interference | `8.32 mm` |
| dominant lost pair | `xl430proxy_joint4 <-> joint2` (`360` cases) |

## One-Expression Safety Representation

Use this exact tuple shape for tables, filters, soft limits, and regression
fixtures:

```text
q = [q1, q2, q3, q4, q5]
q_i = actuator command for joint i, radians
safe(q) := replay(q).ok == true
```

For the current 5-level replay, the sampled levels are:

| joint | sampled levels rad |
| :--- | :--- |
| `joint1` | `[-1.8849, -0.9425, 0.0, 0.9425, 1.8849]` |
| `joint2` | `[-1.8849, -0.9425, 0.0, 0.9425, 1.8849]` |
| `joint3` | `[-0.9425, 0.0, 0.9425, 1.8849]` within the baseline-safe reference set |
| `joint4` | `[-1.8849, -0.9425, 0.0, 0.9425, 1.8849]` |
| `joint5` | `[-1.9536, -1.5813, -1.209, -0.8367, -0.4644]` |

## Safety Findings

### Single-Joint Risk

`joint3` is the strongest one-dimensional indicator in the current sampled set.

| condition | result | interpretation |
| :--- | :--- | :--- |
| `joint3 = -0.9425` | `361 / 451` lost (`80.0%`) | high-risk folded elbow/wrist region |
| `joint3 = 0.0` | `0 / 500` lost | sampled region is safe |
| `joint3 = 0.9425` | `0 / 500` lost | sampled region is safe |
| `joint3 = 1.8849` | `3 / 550` lost (`0.5%`) | nearly safe; losses are tracking-boundary cases, not dominant self-collision |

### Dominant Joint-Tuple Rule

The dominant self-collision region is captured by the focus tuple:

```text
[joint2, joint3, joint4]
```

In the current sampled data, the risky condition is:

```text
joint3 ~= -0.9425 rad
and joint4 != 0.0 rad
```

Most such tuples are completely lost, and the dominant pair is
`xl430proxy_joint4 <-> joint2`.

| `[joint2, joint3, joint4]` rad | lost / total | dominant pair |
| :--- | :--- | :--- |
| `[-0.9425, -0.9425, -1.8849]` | `25 / 25` | `xl430proxy_joint4 <-> joint2` |
| `[-0.9425, -0.9425, -0.9425]` | `25 / 25` | `xl430proxy_joint4 <-> joint2` |
| `[-0.9425, -0.9425, 0.9425]` | `24 / 24` | `xl430proxy_joint4 <-> joint2` |
| `[0.0, -0.9425, -1.8849]` | `25 / 25` | `xl430proxy_joint4 <-> joint2` |
| `[0.0, -0.9425, -0.9425]` | `25 / 25` | `xl430proxy_joint4 <-> joint2` |
| `[0.0, -0.9425, 0.9425]` | `25 / 25` | `xl430proxy_joint4 <-> joint2` |
| `[0.9425, -0.9425, -1.8849]` | `25 / 25` | `xl430proxy_joint4 <-> joint2` |
| `[0.9425, -0.9425, -0.9425]` | `25 / 25` | `xl430proxy_joint4 <-> joint2` |
| `[0.9425, -0.9425, 0.9425]` | `25 / 25` | `xl430proxy_joint4 <-> joint2` |
| `[1.8849, -0.9425, -0.9425]` | `25 / 25` | `xl430proxy_joint4 <-> joint2` |

Boundary exception:

| `[joint2, joint3, joint4]` rad | lost / total | note |
| :--- | :--- | :--- |
| `[-0.9425, -0.9425, 0.0]` | `10 / 25` | boundary region; `joint1` and `joint5` decide whether penetration crosses `2 mm` |
| `[0.0, -0.9425, 0.0]` | `0 / 25` | sampled safe |
| `[0.9425, -0.9425, 0.0]` | `0 / 25` | sampled safe |
| `[1.8849, -0.9425, 0.0]` | `0 / 25` | sampled safe |

### Pairwise Matrix

`joint3 x joint4` is the clearest collision table:

| `joint3 \ joint4` | `-1.8849` | `-0.9425` | `0.0` | `0.9425` | `1.8849` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `-0.9425` | `96/96` | `100/100` | `10/100` | `94/94` | `61/61` |
| `0.0` | `0/100` | `0/100` | `0/100` | `0/100` | `0/100` |
| `0.9425` | `0/100` | `0/100` | `0/100` | `0/100` | `0/100` |
| `1.8849` | `0/100` | `1/100` | `2/125` | `0/115` | `0/110` |

Cell format is `lost / total`.

## Suggested Operational Rule

For the current XL430 proxy model, the practical soft-limit guard is:

```text
Avoid q3 around -0.94 rad when q4 is away from 0 rad.
```

A conservative sampled-grid rule is:

```text
if abs(q3 - (-0.9425)) <= grid_step/2 and abs(q4) >= 0.9425:
    treat pose as high collision risk
```

The boundary case `q3 ~= -0.9425, q4 ~= 0` should be treated as a caution zone,
especially near `joint2 ~= -0.9425`; finer sampling or signed-distance geometry
should be used before turning it into a hard controller limit.

## Scope And Limits

- This protocol verifies MuJoCo replay safety for the model under test.
- The XL430 proxy model uses collision proxies, not final real XL430 meshes.
- The circular/oval flange change on `elbow_to_wrist_extension` is verified by
  CAD/B-rep tests separately. It is not automatically included in the MuJoCo
  mesh model unless generated assets are promoted into `simulation/.../assets`.
- Current results are grid-sampled, not a continuous mathematical proof over all
  joint angles.
- For production limits, re-run the report with a finer grid around the boundary
  region:

```text
joint3 ~= -0.94 rad
joint4 ~= 0 rad
joint2 ~= -0.94 rad
```

## Artifacts

- Generated report: `temp/jointspace_safety_xl430_oriented.md`
- Generated machine-readable summary: `temp/jointspace_safety_xl430_oriented.json`
- Reusable summarizer: `scripts/jointspace_safety_report.py`
- Replay harness: `scripts/replay_poses.py`
