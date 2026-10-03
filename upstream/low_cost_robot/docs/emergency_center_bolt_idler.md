# XL430 center-bolt emergency idler

**Historical prototype, not an installation recommendation.** This page records
the earlier internal-flange design, whose full assembly sequence was not
established. The later external tube/guide candidate and unresolved acceptance
gates are documented in [the current assembly review](all_xl430_assembly_wiring_review.md).
Neither design is approved for fabrication or powered operation.

## Purpose

The source follower assembly supports the shoulder XL430 on both sides. The
output side uses the horn, and the opposite side uses the ROBOTIS HN11-I101
idler. If the HN11-I101 is unavailable, leaving the opposite wall unsupported
allows the printed shoulder link to float. Pulling that wall against the servo
case bends the link and can add large rotational resistance.

This prototype supplies the missing radial and axial support with a printed
cylindrical spacer. A center M3 bolt and wide washer clamp the spacer. The link
rotates around the spacer pilot and retains axial clearance after the bolt is
tightened.

This is an emergency, low-speed geometry prototype. It does not reproduce the
HN11-I101 bearing or patented hook mechanism and has no load-life qualification.

Official HN11-I101 reference:
https://www.robotis.us/products/hn11-i101-set

## Geometry

| Feature | Value | Basis |
|---|---:|---|
| support flange diameter | 20.0 mm | source idler is 20.5 mm; reduced for printed clearance |
| support flange thickness | 3.5 mm | source CAD motor face to link inner face |
| link pilot diameter | 9.5 mm | source link bore is 10.0 mm |
| radial clearance | 0.25 mm | `(10.0 - 9.5) / 2` |
| link thickness | 3.0 mm | source shoulder link wall |
| pilot extension | 3.25 mm | gives 0.25 mm axial clearance under the washer |
| center bolt clearance | 3.4 mm | M3 clearance hole |
| minimum pilot wall | 3.05 mm | `(9.5 - 3.4) / 2` |
| reference washer | OD 12.0, ID 3.4, t 1.0 mm | retains a link with a 10 mm bore |

For the nominal solid-PLA model at 1,240 kg/m3, the generated physical-properties
JSON contains the B-rep-integrated mass, center of mass, and full inertia tensor.
The current nominal mass is about 1.57 g. These values represent solid material;
actual print mass varies with extrusion, wall count, and voids.

The motor-side flange includes a small notch for the XL430 rear-case hook. A
full circular flange overlapped that hook by about 0.896 mm3 in the source CAD.

## Fastener condition

The source HN11-I101 set includes an FHS M3x5 center screw, and the source arm
CAD places that screw on the same axis. The replacement bolt must be longer
because it passes through the printed adapter and the retaining washer.

Do not select its length from the CAD alone. Measure the usable thread depth in
the actual servo center hole first. The length under the bolt head is:

`6.75 mm adapter + actual washer thickness + seat-to-thread-entry recess + desired thread engagement`

The source CAD's smooth 3.0 mm center bore starts 0.70 mm behind the mounting
plane and extends another 4.50 mm. The stack to that entrance with a 1.0 mm
washer is therefore 8.45 mm, not 7.75 mm. The reference M3x12 bolt overlaps this
smooth bore by 3.55 mm, leaving 0.95 mm to its modeled floor. The previous
4.25 mm value counted the recess as bore engagement and was incorrect.

This is **not verified thread engagement**: the STEP has no modeled thread and
does not establish usable thread depth or the strength of the center attachment.
The visual bolt includes a hex socket but no threads; its length is provisional.
Do not force a screw into an unidentified hole. Confirm the real thread and
usable depth, then choose the length without bottoming. ROBOTIS likewise warns
that an overlong bolt can damage the frame or servo:
[frame and horn assembly precautions](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/#precaution-of-frame-and-horn-assembly).

## Assembly

1. Turn off motor power and remove load from the joint.
2. Place the printed flange between the XL430 rear face and the unsupported link
   wall. Align the small notch with the rear-case hook.
3. Pass the 9.5 mm pilot through the link's 10 mm center bore.
4. Place a metal washer wider than the 10 mm link bore over the center bolt.
5. Only after confirming the real thread, seat the bolt against the end of the printed pilot. The link must retain
   visible axial play and rotate without being clamped.
6. If tightening the bolt makes the link stiff, stop and correct the spacer
   length or add a controlled shim before driving the motor.

## Validation evidence

The validator replaces the source HN11-I101 idler, cap, and screw while keeping
the actual shoulder XL430 leaves and shoulder link from
`hardware/follower/step/arm.step`.

- adapter versus 31 retained motor leaves: 0 mm3 intersection
- adapter versus link at the source pose: 0 mm3 intersection, supporting-face contact
- reference washer versus link: 0 mm3 intersection, 0.25 mm separation
- reference M3x12 envelope versus adapter, washer, link, and retained motor: 0 mm3 intersection
- all three additions versus the complete retained source arm at its saved pose: no intersection over 1e-6 mm3
- sampled 360 degree link sweep against adapter, washer, and bolt at 5 degree increments: 73 poses, 0 colliding poses
- generated STEP: one valid solid
- generated STL: watertight and winding-consistent
- generated URDF: SI mass/inertia with STL scale `0.001 0.001 0.001`

The sweep checks local geometric clearance only, not full-arm collision-free
motion or continuous swept volumes between samples. It does not predict
printed-part deformation, friction, fatigue, bolt pull-out, or bearing life.

## Self-review (2026-09-22)

The source motor and link are retained as imported B-reps, not reconstructed or
widened. Only the missing idler/cap/center-screw group is replaced. The exported
fit-check assembly contains the shoulder motor, its original output-side
hardware, original link, printed adapter, reference metal washer, and reference
center bolt. It is a local joint assembly, not a verified all-XL430 arm.

Corrections made during review:

- Measure link bore, pilot diameter and washer separation from generated/source
  geometry, instead of comparing declared input parameters with each other.
- Distinguish holes from outside cylindrical faces using oriented normals and
  radial vectors. A raw `FORWARD`/`REVERSED` flag alone misclassified extruded
  cylinders and initially produced an erroneous 3.3 mm radial clearance.
- Correct the bolt insertion accounting for the recessed bore entrance above.
- Check all additions against the entire retained source assembly at the saved
  pose, and include the bolt in the local link sweep.
- Add negative tests for insufficient axial clearance, insufficient radial
  clearance, a misplaced hook relief, a bolt bottoming in the motor and a bolt
  too short to reach the bore. Modeled bore overlap must meet the 3.5 mm target;
  this remains separate from actual threaded engagement.

**Release remains conditional**, even if the geometry report says `pass`:

- Actual thread identity, usable depth, engagement and permissible tightening
  torque remain unverified. The smooth CAD bore is not proof of a threaded joint.
- The 0.25 mm radial and axial gaps are nominal CAD values, not measured print
  tolerances. Check the real printed part and washer before applying torque.
- The flange touches the link's inner face at nominal dimensions. Printing error,
  bolt preload or PLA creep can remove axial play and recreate the original bind.
- No independent bushing/bearing, friction test, load qualification or complete
  all-fastener tool-access review has been validated. The later
  [all-XL430 assembly/wiring review](all_xl430_assembly_wiring_review.md) checks
  a provisional straight-driver envelope for this center bolt only and records
  a blocked flange insertion path. Keep the joint unloaded and unpowered
  during fit checks; a successful browser rendering is not operating approval.

Review execution: `uv run pytest -q` completed with **177 passed** (104.81 s).
This includes eight idler tests, of which five exercise deliberately invalid
variants. The reviewed CLI export exited 0 with all geometric checks passing
and `assembly_release=unverified_actual_thread_and_printed_fit`.

## Browser review

The reviewed files are isolated from older prototype outputs at
`skills/cad-reverse-parametric/outputs/review/emergency_idler_20260922/`.
Reproduce them with the validator's
`--out outputs/review/emergency_idler_20260922 --fail-on-mismatch` options.

Chili3D was opened headed via `playwright-cli -s=idler-review`, with two tabs:

- [Assembled joint](http://127.0.0.1:8081/?url=/idler_assembled_review_20260922.step)
- [Center-axis section, visualization only](http://127.0.0.1:8081/?url=/idler_section_visual_only_20260922.step)

The link is teal, printed adapter orange, metal washer blue, and reference bolt
dark gray. Both views preserve the assembly placement; the section removes one
half only to expose the center bolt and shoulder stack. Never print the section
artifact or use it for interference acceptance.

DOM inspection identified exactly one node each for `shoulder_to_elbow_link`,
`emergency_printed_idler`, `reference_wide_washer` and
`reference_M3x12_bolt_envelope` in the assembled tab. The browser-fetched STEP
matched the reviewed file's SHA-256:
`fdfc9f95f71e8dc1e67e33a3fe00913a30e0e4c534c41fefbac3b1cdf9323fed`.
Screenshots were inspected, not just generated. The console reported no errors;
the app emitted initialization warnings about unset properties.

Screenshots (repository-relative, not manufacturing evidence):

- `temp/idler_review_initial_20260922.png`: full motor/link overview
- `temp/idler_review_assembled_20260922.png`: assembled joint close-up
- `temp/idler_review_section_detail_20260922.png`: center-bolt section close-up

### Complete arm view

The primary browser tab was subsequently changed to the
[complete assembled arm](http://127.0.0.1:8081/?url=/arm_with_emergency_idler_full_20260922.step),
including the base, shoulder, elbow, wrist and gripper. This uses the original
mixed-servo `hardware/follower/step/arm.step`, not an all-XL430 conversion.

The export preserves 157 of the source's 161 occurrences with the exact original
B-rep, orientation and placement. Only four shoulder-idler occurrences are
removed; the printed adapter, washer and bolt replace them. The preservation
assertions and existing idler checks passed (`8 passed`, 54.17 s). DOM inspection
confirmed 157 source nodes and the three additions, with zero console errors.

Full-arm outputs are under
`skills/cad-reverse-parametric/outputs/review/emergency_idler_full_arm_20260922/`.
The full STEP is `arm_with_emergency_center_bolt_idler.step`; its browser-served
SHA-256 matches the generated file:
`512ad35d4e6f9b774298fc3dc11fcd6c7e56c236a760ac5a3eae8c7d308c744c`.
The inspected screenshot is `temp/idler_full_arm_assembled_20260922.png`.
This wider visualization does not extend the engineering acceptance scope.

## Reproduce

```bash
cd /home/inaho-omen/Project/low_cost_robot/skills/cad-reverse-parametric
uv run pytest -q tests/test_emergency_idler.py
uv run python studies/xl430_lowcost/validate_emergency_idler.py --fail-on-mismatch
```

Generated files are written to:

`skills/cad-reverse-parametric/outputs/prototypes/emergency_center_bolt_idler/`

- `emergency_center_bolt_idler_xl430.step`: printable adapter
- `emergency_center_bolt_idler_xl430.stl`: printable mesh
- `reference_M3_wide_washer.step`: simulation reference for the metal washer
- `reference_M3x12_bolt_envelope.step`: unthreaded bolt envelope used by the fit check
- `emergency_center_bolt_idler_xl430_physical_properties.json`: nominal PLA mass properties
- `emergency_center_bolt_idler_xl430.urdf`: standalone single-link URDF
- `emergency_center_bolt_idler_fit_check.step`: motor/link/adapter fit-check assembly
- `arm_with_emergency_center_bolt_idler.step`: complete source arm with the shoulder idler hardware replaced
- `emergency_center_bolt_idler_section_visual_only.step`: cutaway, not a printable part
- `validation.json`: machine-readable validation result
