# Findings, tips and struggles (ID3 elbow opening, 2026-10-03/04)

Concrete evidence lives in `diary/2026-10-04_id3-open-10deg.md` and
`temp/workdoc_Oct03-2026_id3_open_10deg.md`.

## Findings on hardware (5x XL430-W250, FW 42/43, 1 Mbps, E148 hub)

- The elbow opened in the CAD-predicted direction (counts increase). Holding the opened pose
  needed about 100-120 PWM (11-14 %); returning needed almost none, so gravity pulls toward the
  fold. Load behaviour is useful direction evidence when nobody can watch.
- Default gains (P 640, I 0) left a 19-count (1.7 deg) sag on the first run. One goal offset of
  +20 counts brought it to -4 counts. Gains were not changed.
- Breaking away from the folded rest briefly reached the 350 Goal PWM limit (static friction).
- Isolated SYNC_READ "no status packet" frames occur (about 0.5 %, up to 2 % after motion);
  the achieved rate fell from 19.9 to 15.9 Hz in one read-only run. Treat unknown samples as
  unknown and allow an isolated retry.

## Defects found by adversarial review before the first write

Each was reproduced offline, fixed test-first, and is now covered by tests.

- The SDK sets `is_using` in txPacket and clears it only at the end of rxPacket. An exception
  inside a transaction (guard refusal, KeyboardInterrupt, serial error) left it set, so every
  release write returned "port busy" and torque stayed on while the tool said it was off.
- Logging before sending meant a disk-full log error skipped Torque=0.
- Release restored PWM and profile limits to "unlimited" even when Torque=0 had not been
  confirmed, and the outcome did not report the failure.
- SIGTERM/SIGHUP skipped release entirely. A later design that raised KeyboardInterrupt from
  handlers still had windows at function entry and while restoring handlers; record-only
  handlers that the CLI never restores closed them.
- Pacing advanced the deadline twice (10 Hz instead of 20 Hz).
- Evidence parsing accepted a sign inconsistent with the recorded counts, bool signs, other
  sessions, and hand-written CAD records with unverifiable source hashes.
- After the verdict: a log close re-raised ENOSPC (exit 1), an unflushed stdout made the
  interpreter exit 120, and a signal right after handler restoration printed "interrupted
  before any write".

## Tips

- Fakes must model time-based profiles: a blocked joint ends its trajectory after its
  duration, it does not stay "profile ongoing" forever. Otherwise convergence tests lie.
- Shorten the guard window to what the code writes (fold side: jump tolerance; opening side:
  target plus correction budget), and judge overshoot against the true target even when the
  goal is offset.
- Strengthen negative tests with `match=` per gate and run mutants (remove a gate, check that
  a test fails); a new threshold can silently make old negative cases pass for the wrong reason.
- `rtk curl` reformats JSON; use `rtk proxy curl` when piping to a parser.
- Viewer HTML may be read per request, but server-side Python changes need a restart; check
  the port owner and that no user session is mid-operation before restarting.
- Unattended runs: record that the power-off stop is not available, keep the run finite, read
  back torque state with the monitor afterwards, and report exactly what was not observed.

## Multi-pose photographs and base stability (2026-10-04)

- Evidence: `reports/pose-capture-20261004/SHOT_TABLE.md`, `rejected/neutral_01.jpg`,
  `photos/stop_base_tilt.jpg`, and `run/events.jsonl`. Four requested poses were photographed;
  the first of twenty neutral-yaw variants showed the entire base leaning and the distal
  assembly appearing supported against the chair. Stop was requested before the next pose.
  Five present-position holding goals were confirmed, the serial port closed, and a separate
  READ showed all torque ON, zero velocity and no hardware errors. Release/return was not
  attempted without confirmation of physical support.
- Good encoder following does not prove the base remains on its support. A small commanded
  shoulder change and return from yaw can still accompany loss of base stability. The exact
  cause here is unknown; do not diagnose it solely from counts or the single camera image.
- For repeated poses, include the base and surrounding objects in the camera view. Review
  each captured image before issuing the next pose; reject base tilt, changed support or a
  new contact even when every motor register looks healthy. Ask for actual support/fixing
  after such an event, and retain the rejected image instead of marking the whole batch done.
- A camera busy in a preview application does not require terminating it. A timestamped
  screenshot of its live camera rectangle is usable evidence when its freshness is checked
  through observed motion; document the preview resolution and exclude unrelated thumbnails.
  Such an image is a preview screenshot, not a native-resolution V4L2 frame.

## Resuming a photographic batch and returning (2026-10-04)

- After the user stabilized the base with tools, a fresh native USB image and independent
  READ established the new physical condition. Resume verified live identities, modes,
  profiles and the five previous holding goals without toggling torque; preserve the original
  baseline and pre-run RAM values for eventual restoration. Evidence is in
  `reports/pose-capture-20261004/run-resumed*/events.jsonl` and `manifest.json`.
- If a bounded load correction is allowed, measure its progress interval from that new goal
  write, while retaining the total deadline, correction budget and direction/overshoot gates.
  Test a recoverable load deadband and a permanently blocked joint separately. This does not
  justify repeated retries or larger limits when the correction fails.
- Changing another joint must not rewrite an unchanged joint's compensated holding goal;
  doing so removes its existing load compensation. Test this through actual outgoing SDK
  packets, including the unchanged joint, rather than only checking final counts.
- Separate target error at arrival from subsequent physical drift. A steady 20-count bias
  followed by one count of jitter is not a 21-count physical movement. Record the commanded
  target, settled measured reference, target error and holding displacement independently;
  retain movement gates and validate actual positions against the original envelope.
  `tests/test_pose_capture_motion.py` covers jitter, real drift and out-of-envelope negatives.
- The requested batch allowed arbitrary natural poses. When the shoulder's return to 0°
  failed, the remaining recipe was changed to a demonstrated holding angle, with the original
  recipe retained. Report the changed coverage and unresolved tracking failure explicitly;
  finishing photographs is not a motor range-of-motion pass.
- Physical support added during recovery can change the return path. Observe folding in
  stages again. In this run, the elbow stopped partway back and the deadline froze all five
  joints; 24 photographed poses did not imply successful return or release. Record photos,
  torque state and RAM restoration as separate outcomes. Do not release an unsupported arm
  or declare an interrupted cleanup complete. See `photos/return_stop_1628.jpg`,
  `run-resumed4/events.jsonl` and `final_state.json`.
- If the user confirms external weight support after an interrupted return, record that as
  a separate release decision. A release-only path must not retry the blocked motion or
  enable torque: verify the original held session, turn all motors OFF, read each back and
  only then park current goals and restore saved RAM values. An unconfirmed OFF skips
  restoration. Record baseline return as failed even if the supported release succeeds.
  Evidence: `supported-release/events.jsonl` and `temp/release_photo_supported.py`.
- Keep verification proportional to the change and user urgency. Reuse tested guarded
  transport for routine actions; check actual OFF/restored registers directly. Do not
  repeatedly run broad test suites before each authorized physical action.

## Image quality and reusable capture work (2026-10-04)

- Before collecting a batch, inspect one native-resolution image for readable screw edges
  and markings, complete arm/base framing and exposure. A decoded JPEG or a healthy motor
  is not an acceptable-photo check. Review sharpness again before each next pose: autofocus
  can hunt even after a previously successful warmup. In this run, twenty 0.5-second USB
  captures were blurry; three seconds improved four retakes but the fifth blurred again.
- Retain rejected originals and mark their quality status separately from motion success.
  Use a new capture cohort for a camera change; preserve raw evidence, pose/count/time
  correspondence and provenance. Do not silently replace the old dataset.
- Keep motion transport, capture and presentation separate. Reuse the existing controller
  and camera implementation; parameterize output paths rather than copying whole scripts.
  Generate galleries and final diary snapshots from one manifest/workdoc instead of
  manually rewriting the same state in several places after each shot. Prefer the smallest
  adapter and existing environments over a new framework or dependency installation.
- For RGB-D, persist raw 16-bit depth, alignment target, actual meters-per-count, stream
  intrinsics/distortion model, device identity and frame times together. Do not assume
  raw depth means millimetres or reuse a generic viewer's axis swap as camera calibration.
  Use existing saved-data viewers while the user sets up a camera; avoid competing streams.
- A device disappearing during setup makes its current state unknown. Stop further
  commands, record the last successful read separately, and obtain a fresh read after
  reconnecting rather than treating a historical torque state as live evidence.
- When the user swaps the robot USB for a depth camera, use that time for camera-only
  acquisition and saved-data rendering. Reuse checkout implementations through explicit
  project-path arguments and their existing environments, without mixing motor transport
  into the camera server. Keep frame metadata null where unobserved. The working example
  and CLI instructions are in `docs/RGBD_CAPTURE.md`; actual D435 RGB-D/PLY/browser
  evidence is under `~/data/xl430-arm/2026-10-04/realsense-camera-check/`.
# 2026-10-04：カメラ取り付け後の撮影

- 取り付け・手合わせ後は旧neutral countを再利用しない。新しい全OFFの安定READと
  現物RGB-Dを保存し、ユーザー指定neutral・CAD zero・同期済み実測を区別する。
- 新基準が旧Planに合わなくても旧制約を広げない。専用の小さいper-run windowを
  選び、既存の監視・packet guard・停止/復元実装を再利用する。
- ホルダー装着後、手首-5°が未達停止した。再試行やPWM増加をせず、その軸を保持し
  他の確認済み軸の組合せで要求枚数を得た。元表と停止記録を残す。
- controller/支持解除処理はsrc/へ配置し、tempは互換entrypointのみ。SDK所有者は一つ。
  カメラは既存serverへPOST保存し、撮影前後の新telemetry/時刻を添付する。
- 固定焦点でも低照度ノイズは残る。実画像を毎回見てから次の動作へ進む。
  SDK profile 30fpsとalign/JPEG経路の実測約20Hzを分けて報告する。

## Loaded multi-axis observation and recovery (2026-10-05)

- Separate the newly commanded axes from stationary supporting axes. A loaded joint's
  residual error against its raw goal is not evidence that it has started a new move.
  Progress uses the commanded axes; physical holding drift uses the fresh accepted position.
  Preserve the raw supporting goal in every intermediate waypoint as well as the final one.
- Do not repeatedly park stationary supporting axes at present counts during stop/restart:
  P-only load sag repeats and accumulates. In the scoped D19 controller, stop the currently
  commanded axis at its observed count and retain existing supporting goals. Generic older
  stop behavior stays unchanged. Log actual park failures separately; never invent a WRITE.
- An incomplete five-axis stop log must fail normal resume. Recovery may use a saved read-only
  register snapshot for the missing retained goal, but fresh hardware must verify all identities,
  aliases, profiles, actual goals and drift before any new WRITE. Keep this separate from normal
  exploration; return-only adjustments do not turn the failed original range test green.
- A nominal reverse route can stall under a different load. Review the actual return geometry
  and object clearance: folding first may bring a wrist/frame into the object. A small lateral
  escape, then staged folding, is different from repeatedly pushing the same saturated joint.
  Rest, return, torque OFF, RAM restoration and physical supply OFF remain separate outcomes.
- Use one camera owner and one bounded motion owner; reuse logs and telemetry for snapshots.
  Run an affected boundary/regression check after a behavior change, not full suites per photo.
  Measure progress by observed physical changes and saved evidence, not the number of checks.
- Output limits in a manufacturer's control table do not establish safe mechanical clearance.
  The recorded one-time return-only ID2 revision from PWM350 to395 did not restore movement;
  it was restored to350 and further increases stopped. Do not interpret this as a diagnosed
  binding cause or as permission to keep increasing output. If physical support is unknown,
  report the live torque state and obtain support before release; read-only monitoring cannot
  provide gravity support or safely switch the supply off.
- Reuse the release algorithm, not an incompatible session controller: a gripper's held
  PWM and a displaced arm's windows still need fresh verification. A recovery-only goal
  restriction may wrongly reject parking the actual sagged count after confirmed OFF.
  Use a release-specific controller matching the recorded family; reject torque ON and
  park/restoration until all axes are confirmed OFF. Keep the old CLI default unchanged.
- Post-stop setting restoration is still evidence: the recorded D19 log has five valid
  park writes followed by ID2 PWM350 restoration. An exact-five-tail loader rejects that
  valid pattern. Handle only the explicitly recorded restore in its scoped adapter, retain
  the strict park validator, and verify the live settings before any release. Do not discard
  arbitrary trailing faults/writes or relabel incomplete evidence as complete.
