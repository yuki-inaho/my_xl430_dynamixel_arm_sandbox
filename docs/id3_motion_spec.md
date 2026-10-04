# ID3 bounded opening: control specification

## Fixed choices added by user decision D9 (2026-10-04)

`arm-id3-open --open-degrees 30` explicitly selects 341 counts (29.970703125°).
Omitting the option preserves 10° / 114 counts. Other magnitudes are rejected.
One immutable MovePlan determines the logged plan, dry-run target, actual target and
packet envelope; no global constant is mutated. Opening and return deadlines are
6 seconds for 10° and 18 seconds for 30°. Correction retains its 6-second deadline.
The 1-second early-progress check, PV5/PA1/PWM350, tolerances, correction bound,
all-five route checks and verified OFF/RAM restoration remain unchanged.
The goal window extends 15 counts toward the fold and 35 beyond the selected target.
This supersedes the historical symmetric ±15 envelope row below.
Only ID3 receives RAM writes; ID2 remains read-only. Observe before/open/return with
the connected camera. Relative visual confirmation does not establish absolute CAD
zero angles or approve a whole-arm trajectory. The wrist/hand link moves with the elbow;
the historical pre-run wording that it "will not swing" must not be relied upon.

Status: revised 2026-10-03 23:17 JST by Claude after two adversarial reviews, for workdoc
`temp/workdoc_Oct03-2026_id3_open_10deg.md` step 3. Values below are the
proposal recorded in that workdoc; they are not vendor requirements.

## Scope and authorization

- User instruction (Codex conversation 01a10159, 21:20:51 JST): recognise that
  ID3 (elbow) is fully folded, open it slowly by about 10 degrees and confirm
  the joint moves correctly. Direction: "はい、肘を開く方向" (21:22:41).
- User decision D-4 (22:38): "自分で制御して、エンコーダーが意図した角度になったか、
  収束したか確認すれば十分". MuJoCo comparison is out of scope.
- Stop hook goal: work until the workdoc DoD holds.
- Only motor ID 3 may receive writes. All other IDs stay read-only. No EEPROM,
  ID, Operating Mode, Drive Mode, Homing Offset, limit, LED, reboot, reset or
  firmware change. The read-only observer (`bus.py`, `arm-status`, `arm-live`)
  keeps its PING/READ/SYNC_READ guard unchanged.

## Preconditions (all read-only, fresh, same run)

| Item | Requirement |
|---|---|
| Serial ownership | `fuser` shows no owner; exclusive open. The arm-live bridge must be stopped. |
| Direction evidence (CAD, used for the unattended run, decision D-5) | `kind=cad_derivation` from `scripts/derive_id3_direction.py`: hashed R3 manifest/joints, derivation sign equal to `opening_count_sign`, `folded_count` from a completed READ log (fault frames excluded and counted). Confirmed at run time by the early-progress check. |
| Direction evidence (paired, alternative) | Hardware observation JSON from the viewer helper: both samples `simulated=false`, `motor_id=3`, same `session_id` and `context_fingerprint`, `before.physical_confirmed=true`, `physical_change_confirmed=true`, reported "opening", integer counts, `delta_counts` equal to the mode-3 shortest difference of the recorded counts, `20 <= abs(delta_counts) < 1024`, integer `s = opening_count_sign` matching the delta sign. |
| ID3 identity | model 1060, FW 42 (as last read), protocol 2, baud code 3 |
| ID3 settings | operating_mode 3, drive_mode 0, homing_offset 0, min/max position limit 0/4095, status_return_level 2; no device alert on these reads |
| All five motors | torque OFF, hardware_error 0, no alert, no fault |
| Folded start | `p0` = ID3 present position, stable (span <= 2 counts over 5 samples), within +-30 counts of the evidence's folded (`before`) count |

## Motion parameters

| Parameter | Value | Basis |
|---|---|---|
| Relative move | `s * 114` counts = 10.01953125 deg | 4096 counts/rev |
| Profile Acceleration(108) | 1 (214.577 rev/min^2 = 21.46 deg/s^2) | velocity-based profile, Drive Mode bit2=0 |
| Profile Velocity(112) | 5 (1.145 rev/min = 6.87 deg/s) | about 1.78 s for 10 deg (trapezoid) |
| Goal PWM(100) | 350 (about 39.6 %) | final PWM limiter in Position Control Mode |
| Goal before torque on | `p0` | do not trust an older goal register |
| Target | `p1 + s*114`, where `p1` is read after torque on | Present Position is re-based to single turn at torque on |
| Target bounds | inside 0..4095 and inside min/max position limit | out-of-limit goal handling is undocumented |
| Write envelope | ID3 only; registers 64/100/108/112/116; goal window `[min(p0,target)-15, max(p0,target)+15]`; PA/PV/PWM limited to the run value or the recorded original | `motion_guard.MotionPort`, refused packets release the SDK busy flag |

## Supervision (SYNC_READ of all five IDs, deadline-paced at 20 Hz; measured transaction time can lower the achieved rate, which is logged per stage)

Abort immediately (write Torque Enable=0 to ID3, stop, record) when any of:

- communication or status error on any write or read of ID3
- hardware_error != 0, alert or fault on any motor
- `abs(p1 - p0) > 10` counts after torque on (unexpected jump)
- ID3 moves against `s` by more than 10 counts from `p1`
- ID3 passes the target in direction `s` by more than 15 counts
- early progress: 1.0 s after a goal write, less than 15 counts of progress in the commanded
  direction (a blocked joint or a wrong direction pushing into the fold stop)
- three consecutive samples with unknown values (communication loss); an isolated missed
  sample is logged and re-read, never filled. Hardware error or alert aborts at once
- ID3 settles (stable, profile finished) more than 25 counts from the target
- not converged (see success criteria) within 6.0 s of the goal write (following timeout; stricter than "reached")
- any other ID moves more than 20 counts from its start, or shows torque ON
- KeyboardInterrupt, SIGTERM or SIGHUP (mapped to KeyboardInterrupt), or any exception including
  communication and log-file errors

## Load-sag correction (decision D-7, after hardware run 1 settled 19 counts short)

Position control is P-only (P gain 640, I gain 0), so the forearm load leaves a steady-state
error (run 1: about 100 PWM held at 1248 for target 1267). After the open stage settles, the
goal is offset by the measured error, `goal = goal - (settled - target)`, at most 3 rounds and
at most 30 counts from the target, inside the envelope. The envelope therefore extends 35
counts past the target on the opening side and 15 counts on the fold side. Correction stages
have no early-progress requirement (a blocked joint stops the correction instead of aborting
into a gravity drop) and overshoot is judged against the true target, so the joint can never
be driven more than 15 counts past the intended 10 deg. Gains are not changed.

## Success criteria (DoD-M3, D-4)

- settled: Moving Status bit1 (profile ongoing) is 0 and the last 20 samples (about 1.0 s)
  span at most 2 counts
- converged (status `converged`): settled with `abs(present - target) <= 5` counts (0.44 deg)
- settled with an error of 6 to 25 counts is reported as `settled_off_target` (for example
  gravity sag with I gain 0); it still returns and releases, and it does not satisfy DoD-M3
- no abort condition fired; other IDs unchanged within 20 counts

## End-state policy and release

1. Success path: hold the target for 2.0 s while supervising, then return to `p1` with the
   same profile; require return within 5 counts with the same stable-window criteria.
   ID3 torque must remain ON for every open/correction/hold/return sample. Loss aborts;
   it is never automatically re-enabled.
2. Release (every path after the first write, in `finally`): clear the SDK busy state, write
   Torque Enable=0 (alert-only status accepted), read back `torque_enable`; up to 3 attempts.
3. Only when torque OFF is confirmed: park Goal Position at the present count (if it lies in
   the window) so a later torque-on by any tool holds still, then restore Goal PWM, Profile
   Velocity and Profile Acceleration to their recorded originals (885/0/0 at last read).
   An older goal is never restored. If torque OFF is not confirmed, nothing else is written.
   Read each restored RAM register back and record the expected/observed values.
4. Read all five torque states once more and record them.
5. Exit codes: 0 converged with torque OFF confirmed; 2 refused or aborted with torque OFF
   confirmed; 130 interrupted with torque OFF confirmed; 3 torque OFF NOT confirmed (stderr
   tells the user to press the supply OUTPUT OFF).
   Exit 4 reports release/restoration problems even when torque OFF was confirmed;
   release failure changes an otherwise successful status to aborted. OFF failure (3)
   and interruption (130) retain priority.

Before any WRITE, read model number, primary ID and Secondary ID (12) from all five
configured motors. Reject missing/alerted identities or another motor with Secondary ID=3.
The packet's unicast ID alone cannot prevent RAM writes reaching a Secondary ID alias.
Do not change EEPROM to repair this condition automatically. See the
[ROBOTIS Secondary ID specification](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/#secondaryshadow-id12).

CAD-derived direction evidence is recomputed from the fixed R3 manifest/joints content
hashes in id3_direction.py. Both recorded signs agreeing is insufficient. The READ original
must exist, match its hash and independently computed summary, and contain one acquisition
session with explicit simulated=false metadata. All five identities/settings must agree;
hardware errors or alerts on any motor reject the entire log. Communication-fault frames
are excluded without filling values; at least 50 complete, torque-OFF frames are required.
Legacy logs lacking source/session markers remain historical observations but cannot be
used to authorize a new CAD-derived motion. Acquire a fresh finite hardware READ first.

Schema v2 metadata now optionally carries nullable simulated and acquisition_id fields.
Missing/null means unknown; it never means hardware. arm-status watch marks its hardware
acquisition explicitly, and arm-live marks injected acquisition as synthetic. The Rust
consumer accepts legacy missing fields as None. Regenerate contracts with
uv run --no-sync python scripts/export_contract.py after model changes.

Rationale: leave the arm folded and torque off as found, without an uncontrolled gravity
drop, and never report an unconfirmed torque-off as success.

## Signals and reporting (revised 2026-10-04 01:20)

`execute()` installs record-only SIGINT/SIGTERM/SIGHUP handlers before the first write; the
CLI never restores them, so no signal can turn into an exception during release or reporting.
Each motion write and sample checks the flag first. The log is closed before reporting, and
all verdict output is flushed through a best-effort writer that swaps a broken stream for
/dev/null, so a full disk or closed pipe cannot change the exit code. A signal that arrives
during CPython's own interpreter shutdown (after main returned) can still end the process with
the signal status; the verdict has already been printed and the summary written by then.

## Limits of the software stop

SIGKILL, a hung process, a USB unplug or a power loss of the host cannot run the release.
The Bus Watchdog is 0, so ID3 would keep its last goal with torque ON. The supply OUTPUT OFF
button is the only reliable stop; keep a hand on it during the run (about 8 s).

## Pre-run checklist (user)

- arm-live READ is stopped (`port_closed=true`); the viewer shows nothing live during the run.
- ID3 is back at the fully folded pose used in the direction evidence.
- The upper arm (shoulder to elbow) stays as it is; the wrist and gripper will not swing.
- A hand is on the supply OUTPUT OFF button; do not close the terminal during the run.

## Evidence

`reports/id3_motion_<timestamp>.jsonl` (plan, start, each write after its successful
status, every sample, converged events with sample count and achieved Hz, abort, released
with problems and final torque states, outcome) and `reports/id3_motion_<timestamp>.summary.json`.
Port closure is recorded after the context exits.
