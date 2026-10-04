@/home/inaho-omen/.codex/RTK.md

# Arm Workspace

The project/distribution name is my-dynamixel-arm-sandbox; the Python import
package is `arm_observer` under `src/arm_observer`. Keep the `arm-status` CLI name.

The user currently authorizes motor information reads only. Use `arm-status` from
this project. Motor instructions are restricted to unicast Protocol 2.0 PING,
READ, and SYNC_READ (0x82) for the two validated telemetry blocks. Do not change
torque, goals, IDs, modes, LED, EEPROM, firmware, or reset the
motors. Do not import `low_cost_robot.robot.Robot` for inspection: its constructor
changes torque. The older sandbox's movement/setup commands are outside this scope.

One recorded exception (user instruction, 2026-10-03): the bounded ID3 elbow opening
of `temp/workdoc_Oct03-2026_id3_open_10deg.md` may run only through
`arm-id3-open --execute` (`id3_motion.py`, `motion_guard.py`). It writes ID3 RAM
registers 64/100/108/112/116 inside a per-run envelope, needs hardware direction
evidence, and ends with ID3 torque OFF. Run it only after the user confirms support
and the supply OUTPUT OFF stop are ready. All other commands keep the read-only guard;
do not widen the envelope, add motors or registers, or reuse it for other motions.

User decision D9 (2026-10-04, robot_completion workdoc): ID3 elbow opening may
explicitly select `--open-degrees 30`, then hold, return and release. Default remains
10 degrees. Immutable MovePlan binds 114/341 counts to target, envelope and deadline
(6/18 seconds for opening/return); all other guards and the ID3 RAM whitelist remain.
No ID2 writes are authorized by this decision. Camera observation accompanies the run.

User decision D10 (2026-10-04): prioritize visually observed staged standby motion.
The separate standby_motion controller may hold IDs2/3/4 at freshly read positions,
open ID3 in bounded stages and adjust ID4 while ID2 remains held. IDs1/5 stay read-only.
Never expand the ID3-only guard. Use per-run RAM envelopes, all-five alias/health
checks, slow profiles and camera review between stages. Stop holds the current
position; torque OFF requires return to the observed stable baseline and support
verification. Approximate visual orientation is not absolute calibration.

User decision D11 (2026-10-04 15:36): photograph the real arm at rest, standby,
ID1 neutral +/-30 degrees, and about 20 nearby natural noninterfering poses while
ID1 is neutral. The separate pose_capture_motion controller may write IDs1..5
RAM 64/100/108/112/116 only within the fresh-baseline envelopes of
config/pose_capture_20261004.json, with Profile Velocity 6 (previously 5),
Acceleration 1 and Goal PWM 350. Hold each pose 2.5 seconds and capture/review
the actual USB camera before proceeding. Do not expand the observer/ID3-only
guard. Stop holds; return via wrist-neutral then staged elbow folding to the
original observed stable posture before torque OFF and verified RAM restoration.
No calibration/EEPROM/firmware changes. Camera unavailable blocks execution.

Implementation decision (2026-10-04, photo workdoc): one already-bounded load
correction (+/-30 counts, once per axis and waypoint) gets its one-second progress
check timed from that new Goal Position write. Direction/overshoot/holding checks
still run before correction against the true target; the total 18-second waypoint
deadline and every position/PWM/profile limit remain. A permanently blocked axis
must still stop after the correction's one-second progress window. Original
read-only, ID3 and standby controllers are unchanged.

Photo stationarity decision (2026-10-04 workdoc): the 20-count physical holding
drift limit is measured from the last accepted settled READ, separately from the
unchanged 20-count goal-error criterion at waypoint completion. Log both quantities;
never label command angles as precisely achieved physical angles. Every observed
position must also stay in its original per-run envelope. Keep the existing raw
supporting goal for an axis whose true target did not change while other axes move.

User decision D12 (2026-10-04, after the photo session): the user confirmed proceeding
after being asked to support the weight of the elbow-to-tip arm. Release from the
currently held, externally supported pose is authorized without completing the blocked
fold. Use python -m arm_observer.photo_supported_release with the original holding log;
verify live identities/profiles/holding goals, write only Torque OFF first and confirm
all five OFF before parking current goals and restoring the saved RAM profiles/PWM.
Do not attempt another fold or label the original baseline return successful. This
does not authorize torque ON, new motion, EEPROM changes or broader guard values.

Check serial ownership before connecting. Leave DYNAMIXEL Wizard and unrelated
processes running; if they own the port, stop the hardware inspection and report
the owner. Close the port in a finally block, including on errors and interrupts.

User decision D13 (2026-10-04): correct the out-of-focus photo batch and retake its
20 neutral-yaw variants; the user confirms power remains ON. Restart from the
externally supported all-OFF posture, retaining the original accepted encoder
baseline, original RAM values and exactly the original five-motor envelopes.
Validate fresh identity/configuration/all-OFF/stability, park live present counts
before enabling, and apply the original 15-count jump check against that fresh
starting pose. Do not force the blocked original fold. Capture 1920x1080 after
three seconds of autofocus settling and inspect actual image quality before each
next pose. Keep blurry originals; they are not accepted photos. The user's request
for minimum testing applies: no repeated unit-test suites for this retake.

User decision D14 (2026-10-04 18:27): the newly observed folded D405-mounted pose
is the camera-equipped neutral, counts [2102,3473,1147,3398,1951]. Generate and
photograph 20 poses with external D435 RGB-D at 1280x720/30fps. The separate
camera_pose_capture controller reuses PhotoController with fresh baseline +/-3,
ID1 +/-30 degrees, ID2/5 held, ID3 opening 0..30 degrees, ID4 +/-10 degrees.
Use config/camera_pose_capture_20261004.json and its smaller per-run windows.
Preserve PV6/PA1/PWM350, 2.5s holds and all existing jump/progress/health guards.
Review each real image before advancing. Return to this new stable neutral before
release/restoration. D405 had no USB connection then. Old plans remain unchanged.

Check serial ownership before connecting. Leave DYNAMIXEL Wizard and unrelated
processes running; if they own the port, stop the hardware inspection and report
the owner. Close the port in a finally block, including on errors and interrupts.

Use `config/arm.toml` for the stable device path, baudrate and expected IDs.
Physical joint roles are proposed; do not infer verified physical order from ping.
Save time-stamped JSON and Markdown in `reports/` and work notes in `diary/`.

Before hardware execution after code changes, run the offline tests that check
outgoing protocol instructions. No hardware access is needed for `uv run pytest`.

Keep SDK transport in `bus.py`/`reader.py`; acquisition depends on the `Reader`
protocol. Use immutable typed records, not ad hoc dictionaries, for domain data.
JSON/TOML and schema generation may use dictionaries at serialization boundaries.
Missing values are None, never stale values or assumed zero. The JSONL exchange
contract is schema version 2; regenerate fixtures with `scripts/export_contract.py`
and test the Rust consumer when changing exchanged fields.

Use finite `watch` runs for agent checks. Report achieved rate and missed deadlines;
this is best-effort monitoring, not hard real-time control. Do not tune motor
return delays, indirect addresses, firmware, or host USB settings without a separate
request. Default watch is 20 Hz and ten seconds; metadata refresh is thirty seconds.

Quality gates: `uv run pytest`, `uv run ruff check src tests scripts`,
`uv run ty check`, `uv run scripts/check_quality.py`, and Cargo tests/Clippy in
`rust/arm-observer-contract`. Prefix shell commands with `rtk proxy`.

2026-10-04 review/camera update: shared photo commands/resume/evidence live in
photo_session.py/photo_evidence.py. Old photo and supported-release CLIs accept
--config/--device; transport stays fixed at Protocol2/1Mbps/IDs1..5. Camera native
adapters are type-checked separately with ty --python in their existing capture/
point-cloud environments, rather than installing those SDKs into the observer.
Run the suite once after a refactor and repeat only affected failures/behavior changes.
Rust contract is unchanged by photo-session fields, so no Cargo rerun is needed here.

User then connected the wrist D405 USB cable. Camera-only verification and capture-
skill organization are authorized; this review did not move the arm or access serial.
D405 serial230322272284, USB3.2, RGB/depth/IR1280x720@30 verified. Preserve sensor-
specific option support, nonzero RGB distortion and actual frame/encoder timestamps.
Read skills/rgbd-arm-pose-capture/SKILL.md before the next pose shooting run; review
the new cable/load and reacquire the reference before reusing motion targets.
