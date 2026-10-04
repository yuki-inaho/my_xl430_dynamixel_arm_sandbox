---
name: vision-cad-arm-tracking
description: Reproduce the imported articulated FilterReg fit or run image/CAD pose observation from matched RGB-D frames, with automatic foreground separation, explicit model provenance, and measured live tracking. Use for RGB-D/CAD fitting and vision-based arm pose recognition; this does not operate motors.
---

# Vision/CAD arm tracking

Read [the implementation guide](../../docs/ARTICULATED_POSE_RECOGNITION.md) for exact setup,
CLI options, coordinate conventions and supported model. Use existing source/segmentation/
renderer/tracker adapters rather than writing another camera or FK implementation.

- Separate static annotated reproduction from automatic live recognition. The imported
  original uses manual landmarks and arbitrary depth units; RealSense uses measured metres
  with scale fixed at one. Save new runs outside the imported results.
- Verify the actual mesh configuration, camera alignment, K, distortion, depth scale and
  timestamps before fitting. The current camera mount is nominal R5_65, with its physical
  65/75 distinction unresolved. Joint estimates are CAD-relative, not calibrated motor goals.
- Review an actual automatic mask and CAD overlay early. Low 3D residual alone can accept
  a wrong articulated pose under occlusion. Shoulder/elbow separation helps initialization;
  a folded pose requires stronger evidence of correspondence. Preserve lost/reacquiring.
- Acquire with separated links, then reuse the last successful vision state while the
  camera and base remain fixed. `--initial-pose` validates model hash, camera serial and
  metric state, then rechecks the new image. Invalidate it after moving the camera/base.
  Prefer the saved `last-good-pose.json`; never substitute motor counts for CAD angles.
- Keep camera processing outside CUDA's Python launch thread when native SDK/GIL contention
  is measured. Keep a latest-frame slot, not an inference queue. Propagate a timestamped
  mask to the current RGB; reject old masks and never show an old pose as current.
- Measure steady successful pose throughput and p95 frame age, separately from initial
  acquisition and camera FPS. Do not count lost frames as successful recognition. Reducing
  BiRefNet resolution from 512 to 384 failed on this arm; 512 occasionally kept only
  the cable. Compare identical frames at the official 1024 input and alternatives before
  selecting a size. This run uses 768 and one CPU intra-op thread, with measured masks
  and timing; it is not a universal setting. Keep raw and propagated/opened masks distinct.
- Count only successful fresh poses in the UI and measured throughput. Compute mask age
  against the current time, including during acquisition. Retain a converging candidate
  internally across rejected small steps, but publish no pose until quality passes.
  Reuse a last good state for short losses. Once the scene is anchored, retain its root
  even after repeated failures; reject missing/moved base depth and publish lost. Never
  consume the seed and silently search for another root on the background. A moved scene
  requires an explicit new acquisition without the old seed.
- Include a reviewed arm-absent image as a negative control. Compare base depth at the
  original anchor, not at an erroneous newly fitted background root. Verify positives
  too: black motors may be omitted by RGB masks, so a mask-coverage gate is unsuitable.
  A depth gate rejects this observed failure; it is not a universal object-identity proof.
- Compare held image-only relative joint changes against bracketing encoder READs. Keep
  sign-discovery observations separate from validation. Preserve stalled joints and axes
  without visible downstream geometry as unverified. Small-angle tests do not establish
  full-range accuracy or collision freedom.
- Profile the same saved frame before optimizing. Cache only value-identical State/K,
  reuse a mask distance field, and bound background evidence I/O to one pending snapshot.
  Save RGB-D/K/mask/overlay from the same immutable snapshot. Report fixed-frame timing
  separately from live throughput, and state when later fixes postdate that measurement.
- Gaussian moments and shared per-body twist assembly are the FilterReg core. Initial
  candidate distance ranking and explicit silhouette assistance are separate steps.
  Use the same geometry/image objective for the update and its line-search acceptance.
- Choose native lattice or CUDA exact explicitly using measured performance. GPU use is
  not evidence of speed. Keep unsupported modes as errors rather than silent fallbacks.

The meaningful checks are the imported numerical tests, Gaussian/direct comparison,
independent GPU projection, metric/K validation, synthetic joint recovery and real saved/live
observations. Run the full existing suite once after a change set, then only affected checks.
Do not turn this observation workflow into movement, encoder calibration, or a hardware test.
