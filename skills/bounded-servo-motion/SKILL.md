---
name: bounded-servo-motion
description: Design, verify and run a small, bounded motion of one serial-bus servo joint (for example DYNAMIXEL XL430 "open the elbow about 10 degrees slowly and confirm the encoder converged") next to a read-only monitoring stack. Covers direction evidence, a per-run write envelope, guaranteed torque-off release, signal-safe reporting, load-sag correction, emulator-based adversarial tests and unattended execution. Use for "ゆっくりN度動かして確認", single-joint motion tests, or adding the first write path to a read-only robot tool.
---

# Bounded servo motion

Use when a user authorizes one specific motion of one joint on hardware that otherwise runs
read-only. Keep the motion command separate from the observer; never widen the observer's
read-only guard. A worked implementation is `src/arm_observer/{motion_guard,id3_motion}.py`
in this repository; [lessons](references/lessons.md) lists what went wrong before and why.

## 1. Pin down the request and the authority

- Record the user's words, the joint, the start pose, the direction, the magnitude, the speed,
  and what "correct" means (encoder reached and settled, a model comparison, a visual check).
  Record later changes to these as decisions in the workdoc.
- Record the written authorization next to the read-only rule it relaxes (AGENTS.md or
  equivalent): which motor, which registers, which command. Nothing broader.
- Ask only for facts the agent cannot obtain. If the user wants autonomy, derive the rest
  from evidence and write the decision down instead of waiting.

## 2. Direction evidence

Preferred: a paired observation of a manual motion (two fresh reads, same session and
settings, torque off, physical confirmation at both ends). When nobody can move the joint,
derive the sign from the CAD: which side the horn faces (opposite the idler), which link holds
the case, which rotation folds the joint, and the servo's count convention (XL430 Drive Mode 0:
counts increase counter-clockwise seen from the horn). Hash the CAD sources. Back it up at run
time with an early-progress check: from a fold or stop, a wrong direction cannot progress.

## 3. Transport guard and actuator

- A port subclass that validates every outgoing packet: the read-only set plus WRITE frames to
  one motor ID, a short list of volatile registers, and per-run allowed values or a goal
  window. Refuse everything else before it reaches the serial line.
- When the guard refuses, clear the SDK's busy flag (`is_using`), or the following torque-off
  is silently skipped. After any interrupted transaction, clear it again before releasing.
- A named-register actuator (`write("goal_position", v)`), never a generic address write.
  Treat a status error as failure; accept an alert-only status for release writes and verify
  by reading the register back.

## 4. Motion plan (verify units in the official control table)

1. Preconditions from fresh reads: identity, firmware, mode, drive mode, offsets, limits,
   status return level, no alert, all torques off, stable start count near the expected pose.
   Any failure refuses before the first write. Default the command to a dry run.
2. Limit drive output (Goal PWM on XL430) and set a finite profile (Profile 0 means unlimited).
3. Write the current count as the goal, enable torque, then read again: position can be
   re-based when torque turns on. Check every sample for a jump, and compute the target from
   the count read after torque-on.
4. Supervise each sample: other joints still, no reverse motion, no overshoot past the true
   target, early progress within about 1 s, overall timeout, no hardware error. An isolated
   unknown sample (no status packet) is re-read, never filled; consecutive losses abort.
5. Convergence = profile finished, position stable for about 1 s, error within tolerance.
   P-only position control leaves a load sag; correct it by offsetting the goal a bounded
   number of times and counts instead of changing gains. Correction stages skip the
   early-progress check so a blocked joint stops correcting instead of being dropped.
6. Hold briefly, return slowly to the start, then release.

## 5. Release and reporting

- Release on every path after the first write: clear the busy flag, Torque=0, read back,
  retry; only after torque-off is confirmed park the goal at the present count and restore the
  changed volatile settings. If not confirmed, write nothing else and exit with a distinct code
  telling the operator to cut power.
- Make signals record-only from before the first write until the process exits (the CLI never
  restores them); poll the flag at each sample and write. Close logs before reporting, print
  the verdict first, flush every line, and replace a broken stdout/stderr with /dev/null so a
  closed pipe or full disk cannot change the exit code.
- Save a JSONL of plan, writes, samples, convergence (sample count, achieved Hz), release and
  outcome, plus a summary JSON, and validate them with a separate offline script.

## 6. Verify before hardware

Use fake readers for logic, the real SDK over a serial-level emulator for transactions
(`tests/xl430_emulator.py`), and adversarial reviews that inject signals at every tick, lost
packets, ENOSPC and broken pipes. Run the project's quality gates. Then: owner check, dry run,
hashes of the code that will run, execute once, read back with the monitor, validate, record.
State plainly what was not checked (no visual confirmation when unattended; software stops do
not cover SIGKILL, hangs or a lost USB link; cut power is the only reliable stop).
