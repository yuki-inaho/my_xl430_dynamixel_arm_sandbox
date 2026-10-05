---
name: rgbd-arm-pose-capture
description: Verify a connected RealSense camera and capture RGB-D at reviewed, settled robot poses, preserving raw depth, calibration and fresh encoder evidence. Use for arm pose photo datasets, external-camera versus wrist-camera setup, and RGB-D capture verification.
---

# RGB-D arm pose capture

Use existing acquisition and motion tools. Repository-specific commands and evidence:
[RGB-D capture](../../docs/RGBD_CAPTURE.md). Resolve checkout paths, camera serial, output
root and localhost port explicitly; do not embed another machine's paths in new scripts.

For **manual reference-pose alignment / torque switching / single-frame capture**, use the
[D405 pose GUI](../../docs/D405_POSE_GUI.md) instead of recreating a capture pipeline or an
autonomous pose sequence. Reuse the camera owner and let one worker own serial. Require
physical weight support for each manual torque switch; ON parks fresh current counts rather
than loading a stored pose. Closing a GUI is not permission to release torque. Show missing
telemetry as UNKNOWN. Camera-only capture must be a separate explicit action, preserving
null counts and refusing promotion to a joint-pose reference. After communication faults,
use an explicit connection recheck rather than silently rearming controls. Native UI tests
can use xdotool while torque transitions are exercised with the existing SDK emulator.
For multiple cameras, select and validate each owner/serial independently; failure of a
different preview must not hide fresh joint telemetry or block the selected capture.
Bind Q/Esc to the same close path as the window button and verify port release with torque
unchanged; GUI exit is separate from torque OFF.

1. Separate **external observation camera** from **camera mounted on the arm**. Enumerate SDK
   devices and stream profiles; select by serial, then save the actual device, profiles and
   firmware. Connection of a new wrist cable changes the arm's load and cable envelope.
2. Start one camera owner and reuse it for preview/save. Configure only supported sensor
   options; a shared API does not mean D435 laser/emitter settings work on D405. Reuse the
   existing project environment instead of reinstalling SDKs or copying acquisition code.
   Moving either camera changes the observation geometry. Save a new reference frame, label
   the changed view separately, and invalidate old extrinsic/registration seeds before reuse.
3. Save and inspect one real RGB-D frame **before generating the full batch**: focus at the
   target distance, readable link edges/target, framing, exposure and occlusion. Inspect raw
   depth validity in the target region. A sharp background or global validity percentage
   does not validate the task region. Change physical framing when needed; preserve originals.
4. Make a shooting table once, including pose name, relative goals, holds, camera and support.
   Reuse the bounded motion controller; a camera-only verification does not authorize motion.
   Preserve its fresh baseline, transport guard, progress/health checks and release policy.
   For a new attached camera/cable, review the changed setup and transition before moving.
5. Command one pose, settle and hold for the agreed 2–3 seconds, capture, inspect, then advance.
   Require current all-motor holding telemetry and the matching live ready event. Remove old
   ready files on motion/finish/stop. Do not capture from a stopped/released run, a stale ready
   file or an unfinished JSONL record. Keep stop evidence and rejected attempts.
   The newest ready event must follow the newest motor write; verify zero velocity and bounded
   drift from its accepted actual count immediately before and after each camera receipt.
6. Request a frame acquired after the pre-capture encoder sample, then obtain a new sample
   after capture. Save both observations, host frame receipt and SDK timestamp/frame number.
   This is host-time bracketing, not hardware synchronization or precise angle calibration.
7. Preserve RGB, raw uint16 depth, aligned depth, IR when available, intrinsics/distortion,
   extrinsics with array order, measured depth scale, image hashes and acceptance/rejection.
   Generate the gallery from these records without reacquiring images. Preview it in a
   dedicated browser session and check image decoding; retain the screenshot.
8. For point clouds, use the matching calibration and depth units. The current pinhole exporter
   refuses nonzero distortion; choose an SDK-supported deprojection path before using such
   a capture. Do not drop distortion coefficients or relabel an unsupported export as valid.

Keep verification proportional: reuse existing packet/stop/release tests; add a regression
only for a distinct failure. A table of twenty poses does not need twenty repetitions of the
same offline controller path. Run the changed checks once and retest only failures or later
behavior changes. Record final torque/power states separately from camera stream status.
For camera owner shutdown, record-only SIGINT/SIGTERM handlers should request loop termination;
finish the current native SDK/OpenCV frame, close HTTP, then stop the pipeline. Do not throw
KeyboardInterrupt through native image processing. Verify the changed shutdown on one finite
camera-only run and preserve any original crash; a single successful stop is not proof against
all native-library races.

For vision/CAD recognition, reuse the observer's matched snapshot endpoint rather than
opening another camera pipeline. Store the inference inputs and vision output together;
encoder samples are evaluation evidence, never optimizer input. Define one shooting table
and retain amended continuation tables after stops. If a joint stalls, preserve the attempt,
exclude further movement of that joint and retain original progress/output guards. A
communication stop is also a stopped run; fresh state checks precede resumption. Do not
rewrite stopped runs as successful captures or infer whole-range collision safety from a
contact-disabled display model. See [vision/CAD tracking](../vision-cad-arm-tracking/SKILL.md).
