# Parallel-jaw mechanism decision

## Decision status

2026-09-23 self-review: the rack implementation is an envelope illustration, not
a functioning transmission: teeth/guides/retention are absent and rack length
changes with opening. The selection below is historical, not a final mechanism
decision. The new PG2 R5 candidate uses a central crank, two connecting rods and
printed captured rectangular slides. It is a separate supported diagnostic
variant, not a parallelogram and not an automatically approved replacement.
See `REVIEW_PG2_AND_SELF_AUDIT.md` and `specs/gripper_variants.yaml`.

This is a **concept selection**, not a fabrication release. The target object, required opening,
normal force, speed, holding time, life, and allowable backlash are unknown. Those unknowns keep
`fabrication_approved=false` even when the geometric and kinematic tests pass.

The latest architecture reserves physical ID 5 as the wrist-roll candidate. Jaw motion therefore
uses a separate downstream XL430-W250-T geometry candidate (CAD J6/M06); its physical bus ID is
unassigned. The camera remains fixed to P05 and is not part of the rolling or jaw mechanism.

## Compared concepts

| Criterion | Existing fixed + rotating finger | Symmetric parallel linkage | Opposed racks + central pinion |
| --- | --- | --- | --- |
| Jaw faces stay parallel | No | Yes, with two constrained parallelograms | Yes, with two linear guides |
| Symmetric about tool center | No | Yes | Yes |
| One XL430 input | Yes | Yes, with equalizer | Yes |
| Printed part count | Low | High: links, pins, spacers, guides | Medium: 2 racks, pinion, 2 guides |
| Backlash sources | Horn and flexure | Pin clearances and link compliance | Gear mesh and guide clearance |
| Singularities | None, but arc motion | Dead-center/folded linkage | No kinematic singularity in travel; hard stops required |
| Side-load support | Existing concept is one-sided | Dual support can be designed | Pinion needs output horn plus opposite idler/bearing support |
| PLA printability | Simple | Many tolerance-sensitive pivots | Gear and guide coupons required |
| Current user requirement | Reject: not a parallel jaw | Feasible alternate | **Provisional concept candidate** |

## Provisional selection

Use two opposed linear racks driven by one central pinion. Each rack carries one jaw and is
constrained by its own guide. The pinion is driven by a downstream XL430 through the measured
PCD16 output interface. A coaxial opposite-side idler/bearing supports pinion bending load; a
single horn cantilever is not accepted as the final load path.

The parameterized concept shall use:

- `r_p`: pinion pitch radius,
- `theta`: signed motor rotation from the centered pose,
- `g_0`: opening at the centered pose,
- `g(theta) = g_0 + 2 * r_p * theta` over the declared, hard-stop-limited travel,
- `x_left = -g(theta)/2`, `x_right = +g(theta)/2`,
- opposed, parallel jaw-face normals with orientation error measured independently,
- estimated per-jaw normal force `F_jaw = eta * T_motor / (2 * r_p)`, explicitly an estimate until
  efficiency, motor operating torque, PLA creep, and friction are measured.

No value for `r_p`, `g_0`, jaw length, or motor angle limit is a fabrication dimension until the
object envelope and force requirements are supplied. The concept implementation may use named
diagnostic defaults, but every output must retain `design_state=concept_only`.

## Required tests

`test_parallel_jaw_orientation_error`:

- sample at least the minimum, center, and maximum declared motor angles;
- assert both jaw-face normals remain antiparallel within `0.1 deg` in the ideal CAD model;
- assert the face planes do not rotate with motor angle;
- reject a fixture where either jaw is attached directly as a rotating finger.

`test_opening_mapping_monotonic`:

- compute at least 21 ordered samples over the declared interval;
- assert `g(theta)` is finite, positive, symmetric, and strictly monotonic in the selected closing
  direction;
- assert the analytic opening agrees with measured jaw-face separation within `0.05 mm`;
- reject zero pitch radius, inverted rack direction, duplicate rack direction, and any interval
  crossing a hard stop;
- report backlash allowance separately; do not hide it by loosening the ideal kinematic tolerance.

## Fabrication stop gates

Do not generate a production-named STL or G-code until all of the following are known or measured:

1. target object minimum/maximum envelope and permitted contact geometry;
2. required opening, normal force per jaw, speed, hold duration, payload, and duty cycle;
3. XL430 operating-torque limit for the actual voltage and thermal duty, not stall torque alone;
4. exact horn, idler/bearing, shaft, screw, nut, washer, and tool dimensions;
5. selected PLA, printer/process tolerances, rack/pinion coupon result, and guide clearance;
6. cable bend radius and keep-out through wrist roll and full jaw travel;
7. physical ID to CAD joint mapping.

If any gate remains unknown, the permitted output is a diagnostic concept model and comparison
report only. It must not be named or described as print-ready.
