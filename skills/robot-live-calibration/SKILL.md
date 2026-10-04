---
name: robot-live-calibration
description: Build or verify a robot joint telemetry viewer with explicit physical calibration, read-only acquisition, stale-data handling and reproducible browser evidence.
---

# Robot live calibration

Use for encoder-to-CAD/MuJoCo pose reflection and calibration UI work. Preserve the chosen renderer and existing transport; do not introduce another model merely to make an image appear.

## Establish the contract
Find the workspace instructions, active workdoc, stable bus config, model provenance, typed acquisition API and telemetry schema. Separate physical IDs, model joints and CAD labels. Record which mappings are observations, proposals or verified calibrations. Model/firmware alone does not verify the physical joint.

Keep acquisition and rendering independently restartable. A status query or constructor should not acquire a serial port. Explicit start opens the validated reader; explicit stop cancels reads and waits for finally closure. Report stopping, closed and unknown closure distinctly. An agent hardware check is finite; a user-operated continuous mode may run until stopped.

Support independently observed nonzero poses as calibration anchors when moving to a zero
pose would itself require the unknown calibration. Save reference_count, reference_angle_deg
and sign, and convert as reference_angle + sign * count_delta * 360 / resolution. Do not
round an invented integer zero or silently set the observed pose to zero. Retain legacy zero
references separately, reject conflicting/missing anchors, and test mode-dependent wrap,
saved-file loading and the compiled model's world direction. The anchor angle still needs
physical evidence; a display candidate alone cannot authorize applying it as calibration.

## Calibrate and reflect
Require physical joint mapping, measured baseline counts, signs and any nonlinear mechanism reference. State exactly which CAD pose corresponds to the baseline. Do not call an arbitrary current pose zero. Imported calibration needs revision matching and current physical confirmation; never infer verification from stored true flags alone.

Bind calibration to model revision and acquisition session plus the metadata that changes the encoder coordinate system. Include torque transitions when the motor model can reset its position representation. Validate wrap handling against the operating mode and official motor specification. Preserve missing data as null.

On stale, ended, malformed, missing-ID or fault/alert input, hold the last pose and show that it is no longer verified current. Latch invalidated calibration until reconfirmed. Keep manual display controls separate from live pose application. Simulation fixtures must be labelled and cannot silently become hardware calibration.
Require an explicit boolean source at the acquisition boundary; missing, null, integer and
string flags are unknown/invalid, never hardware. Bind the source to calibration even if the
session and every motor setting are otherwise unchanged. Use the same conversion validator
for HTTP and recorded-file adapters. A source/session change or invalidation clears the UI's
physical-confirmation checkboxes, and the apply payload names the source to close races.

If automatic baseline alignment is requested, first establish that encoder-to-model offsets
are identifiable from independent geometry/assembly observations. Moving to a model angle
requires those offsets; commanding an assumed baseline does not measure them. A user-confirmed
neutral for one joint does not establish another joint's zero. Preserve partial known references
and report what independent observation is still required.

## Validate and improve

Make installed hardware an explicit part of calibration. An uninstalled nonlinear jaw must
keep its mechanism angle null; do not manufacture a 90-degree baseline to satisfy a form.
Render only installed parts and report unavailable metrics as null. Test saved/imported
configuration and null-angle rendering, while preserving source/session/context checks.
Keep manual and telemetry display intervals in one authoritative definition. A folded pose
accepted by manual controls but rejected by the live converter is an adapter defect; correcting
display coverage does not certify a larger collision-free or actuator motion range.
Use [verification matrix](references/verification-matrix.md) when implementing or reviewing the adapter. Test known synthetic angles on the actual compiled model, independently of the conversion routine; test negative inputs and lifecycle closure. Preserve numerical thresholds and transport guards.

Use an independent named headless Playwright session for automated checks, keeping user tabs intact. Wait for decoded image dimensions as well as frame sequence progression. Return browser evidence to the orchestrator when the CLI sandbox cannot import file-system modules; do not mistake a script error for a hardware attempt.

The [passive helper](scripts/probe_live_viewer.py) can inspect an existing local bridge/viewer pair.
Invoke it relative to this skill directory, independently of the repository working directory:
`python <skill-directory>/scripts/probe_live_viewer.py --viewer-url <local-origin> --bridge-url <local-origin> --output <report.json>`
It sends GET only and never starts acquisition. It does not prove physical calibration or collision safety.

Record achieved telemetry Hz separately from render fps, deadlines, raw values, calibration state, source, image dimensions, port closure and software/source provenance. Evolve the skill only from observed failure modes or real new use cases. Do not accumulate project-specific paths and motor defaults into generic instructions.

## Direction observation
To learn which count direction a physical motion produces, record two fresh reads of the same motor, session and coordinate-system metadata with torque off, each with its own explicit physical confirmation (start pose, then the observed change). Save the evidence once, exclusively and atomically: encode before creating the file, refuse an existing name, remove a partial file on failure, and consume the baseline after a saved record. A failed re-capture clears the old baseline. Treat jitter-sized or near-half-turn differences as undetermined and say so in the UI. The result is a count sign under a reported motion, not a CAD calibration sign; record that in the evidence itself.

## Motion requests
Read-only rendering does not require motion. If the user also requests a motion test, keep its workdoc and bounded write implementation separate. Follow that request's scope; require the actual direction, support/stop conditions and limits to make the authorized action concrete. Do not expand the reader's whitelist, treat torque-off as a universal safe stop, or move from a fully folded state in an unverified direction.

The `bounded-servo-motion` skill holds the full procedure and the failure history; in short, give the motion its own transport guard: a per-run envelope naming one motor, the few volatile registers it may write, and their allowed values or window, with every other instruction refused before transmission. Check that a refused packet does not leave the SDK port marked busy, or the following torque-off cannot be sent. Default the command to a read-only dry run. Take the start position from fresh stable reads, enable torque only after writing the current position as the goal, then compute the target from reads taken after torque-on, checking every sample for a jump because some servos re-base position at that moment. Limit drive output where the servo provides a limiter, use a finite profile instead of an unlimited default, and supervise direction, overshoot, timeout, faults and the other joints. End in a stated state (for example return slowly, then torque off and restore the changed volatile settings), and never restore an older goal.
