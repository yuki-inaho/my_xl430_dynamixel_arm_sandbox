---
name: sim-grasp-review
description: Review and repair an offline MuJoCo grasp submission against its workdoc, raw evidence and reproducibility contract. Use for imported simulation packages or claims of completed grasp/lift/hold; not for live robot motion.
---

# Review a simulation grasp submission

Preserve the original submission as immutable evidence. Establish the exact archive hash,
input/mesh identities, original success contract, model assumptions and hardware exclusion.
Trace each claimed workdoc completion to actual source, raw states/contacts and artifacts.
Record a severity, concrete trigger and resolution for each defect before changing code.

## Checks that change the conclusion

- A saved-log reevaluation is not a dynamics rerun. Install the frozen lock in an isolated
  environment, run the actual actuator/mj_step experiment, run the same-path no-close
  control, and compare a same-environment repeat. Compare imported traces separately;
  bit-exact cross-platform reproducibility is not guaranteed by a shared seed/version.
  Record changed IK roundoff and phase-specific differences without silently widening
  success thresholds or assigning an unproven cause.
- A freejoint name does not rule out hidden support. Inspect parentage, equality/mocap,
  spring/damping/frictionloss, gravity compensation, fluid effects, plugins/tendons,
  finite bounded actuation and runtime external-force/pose-write evidence. Use a small
  independent malformed-model control for a demonstrated loophole.
- Hash-check preserved input and collision-cache source, scale, part inventory and bytes.
  Check actual mesh assets as well as XML. Reject stale/missing input rather than searching
  an ancestor checkout or regenerating a manifest to bless changed source.
- Pair classification is not collision testing. Enumerate disabled/allowed groups and
  whether they exempt whole bodies or local mounting surfaces. Restrict the conclusion
  to the declared policy; do not claim a safe physical range from proxy contact success.
- Keep partial traces and FAILURE on interruption. Validate finite CLI parameters before
  creating a trial, preserve existing outputs, and retain negative/sensitivity failures.

Fix demonstrated defects using the existing builder, runner, evaluator and renderer.
Avoid a second framework, duplicate frozen models or broad unrelated test runs. Validate
only the changed behavior plus one fresh positive/repeat/negative experiment. Render the
actual selected trace from two useful viewpoints and inspect the resulting HTML/media.

## Portable delivery

Ship the source, lock, real model/input assets, raw acceptance evidence and precise run
commands. Gzip text logs losslessly when useful and let readers consume either format;
verify the byte roundtrip. Retained historical logs are evidence of failures, not proof
that every historical producer source is bundled. Distinguish that from final-run replay.

Recheck repository visibility and the user's publication scope. For technical-only public
delivery, keep real photos/conversations/original archives local; inspect nested metadata
and compressed text for private data and local absolute paths. Content-review synthetic
images/videos; a text scanner cannot determine whether a photograph is private.

Project example and commands: [sim-cap-grasp](../../packages/sim-cap-grasp/README.md).
Keep case-specific thresholds and observations there, not as universal skill defaults.
