---
name: robot-park-pose-definition
description: Define robot standby and supported power-off poses from world-frame goals, distinguish CAD angles from encoder calibration, and verify candidates in a simulator with reproducible evidence. Use when a user asks for standby, parking, rest, shutdown, or power-off positions for a physical arm.
---
# Robot park pose definition

Produce two named states: an energized standby orientation and a supported power-off posture. Keep pose geometry, hardware calibration, transition path, and support verification as distinct records.

1. Establish the user's world forward/up directions and the exact vector to orient: elbow-to-wrist, motor horn axis, palm, finger tips, or camera optical axis. A joint-relative angle does not establish world orientation. Preserve unspecified joints as parameters rather than picking hidden defaults.
2. Identify model revision, physical ID mapping, encoder zero/sign/mode and physical neutral. Factory count2048, CAD zero, a folded end-stop and neutral are different references. A recent READ is evidence of counts; it is not geometric calibration.
3. Specify world goals and derive joint relations using the verified model chain. Confirm them independently from transformed link endpoints/body axes. Store selected CAD examples separately from confirmed hardware targets; unresolved targets stay null. Include the model/source hashes and simulation input kind.
4. Preserve a user-reported stable existing pose when it is the selected power-off baseline. Reacquire/calibrate its geometry before creating a command target. Record the support surface, contact regions and load path. A cushion's height without footprint, compression and load transfer does not prove support. Prefer support through structural links; avoid relying on delicate camera brackets, fingers, or wires.
5. Verify the entire transition separately from endpoints. Report collision ERROR, UNKNOWN and failed controls explicitly. A kinematic viewer with gravity/contact disabled or placeholder inertia verifies orientation only. Do not step such a model and infer real power-off stability.
6. Define shutdown as reaching the supported posture, verifying support/load transfer, releasing torque under the agreed conditions, confirming no unexpected motion, then turning the supply off. Startup reads current counts/settings before torque enabling and avoids commanding an old target. Do not implement a multi-joint command by broadening a single-joint authorization/guard.
7. Save the candidate definition, independent numerical checks, orthogonal screenshots, residual unknowns and a reproducible command. Physical movement is a separate action requiring its actual calibration and verified operating conditions.

An existing all-torque-off pose may first be saved as an encoder reference with the original
READ/session/coordinate metadata, photo provenance, per-motor sample span and observed duration.
Keep support/contact status explicit. Stable counts do not prove a load path or actual supply
power-off. The reference has no executable targets until calibration and the return path are
verified. Record user-confirmed neutral separately from CAD zero, and do not promote a single
confirmed neutral into whole-arm calibration. Collection commands take input/output paths
explicitly rather than containing the current project's motor counts.

For R3/C7 examples and the limitations found during this task, read [references/r3-lessons.md](references/r3-lessons.md). Those joint equations and test values apply only after verifying that exact axis layout.

When the user explicitly chooses approximate visual positioning, separate that acceptance
from metrological calibration. Use the already observed motion direction, small reviewed
stages and fresh encoder differences; keep absolute geometric calibration unverified.
Hold the proximal joints so distal movement does not change the whole pose. Record each
camera review and selected encoder state as a candidate, not a universal default.
An airborne standby stops by holding, not by borrowing a single-joint test's automatic
torque-OFF cleanup. Bound load compensation separately from arrival tolerance; do not
relax a failed threshold. Resuming a stopped holding run must preserve its original
baseline and restore settings, while checking fresh mode/alias/torque/context again.
Check stop requests inside the following loop, and keep emergency holding writes
independent of logging failures. A successful event label cannot establish physical support:
report baseline stability, load support and actual supply-OFF as separate observations.

At a user-requested pause, save the last confirmed torque state and serial-closure
evidence, and distinguish a user's supply-OFF report from a voltage measurement.
Capture a post-OFF image if available without communicating with the unpowered motors.
Bundle an illustrated report with original-image hashes and logs; include an index of
remaining frames rather than embedding an entire continuous capture. Validate image
loading, links, enlarged views and narrow-screen layout in a dedicated browser session.
State the conversation-export cutoff and current branch, and preserve outstanding
calibration/support checks. Do not continue physical movement during record-only work.

For photographing settled positions, follow
[rgbd-arm-pose-capture](../rgbd-arm-pose-capture/SKILL.md); reuse its acquisition/evidence
steps rather than implementing a second motion or camera loop.
