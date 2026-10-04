"""D11 photo session: fresh-baseline RAM-only motion, command gated camera review."""

import argparse
import json
import math
import signal
import time
from pathlib import Path

from arm_observer.id3_motion import healthy, position
from arm_observer.motion_guard import WriteEnvelope
from arm_observer.standby_motion import IDS, Controller, Plan, open_standby_bus


def load_poses(path):
    data = json.loads(Path(path).read_text())
    if (
        data["profile_velocity"],
        data["profile_acceleration"],
        data["goal_pwm"],
        data["hold_seconds"],
    ) != (6, 1, 350, 2.5):
        raise ValueError("Only reviewed photo-session profiles are permitted")
    poses = data["poses"]
    if len(poses) != 24 or len({p["name"] for p in poses}) != 24:
        raise ValueError("24 unique photo poses required")
    bounds = [(-30, 30), (-3, 3), (0, 78), (-36, 0), (-10, 10)]
    for pose in poses:
        values = pose["delta_deg"]
        if len(values) != 5 or any(
            type(v) is not int or not low <= v <= high for v, (low, high) in zip(values, bounds)
        ):
            raise ValueError("Pose outside reviewed delta bounds")
    if poses[0]["delta_deg"] != [0] * 5 or poses[1]["delta_deg"] != [0, 0, 72, -30, 0]:
        raise ValueError("Rest/standby definitions changed")
    if poses[2]["delta_deg"] != [-30, 0, 72, -30, 0] or poses[3]["delta_deg"] != [
        30,
        0,
        72,
        -30,
        0,
    ]:
        raise ValueError("Yaw definitions changed")
    if any(p["delta_deg"][0] for p in poses[4:]):
        raise ValueError("Twenty variants must keep ID1 neutral")
    return poses


class PhotoController(Controller):
    """Separate authorisation; original three-joint controller and guard are untouched."""

    window_offsets = ((-371, 371), (-64, 64), (-15, 917), (-440, 30), (-144, 144))

    def make_plan(self, baseline):
        return Plan(baseline)

    def sample(self):
        if self.stop_requested():
            raise RuntimeError("Stop requested")
        motors = healthy(self.reader.telemetry(IDS, "sync"))
        positions = tuple(position(motors[mid]) for mid in IDS)
        for mid in IDS:
            motor = motors[mid]
            if motor.torque_enabled != (mid in self.enabled):
                raise RuntimeError(f"ID{mid} torque unexpectedly changed")
            self.check_environment(mid, motor.temperature_c, motor.voltage_raw)
            if self.plan is not None and mid in self.port.envelopes:
                envelope = self.port.envelopes[mid]
                if not envelope.goal_low <= positions[mid - 1] <= envelope.goal_high:
                    raise RuntimeError("Observed position outside photo envelope")
        self.current = positions
        self.event(
            "sample",
            stage=self.stage,
            positions=positions,
            torque={str(mid): motors[mid].torque_enabled for mid in IDS},
        )
        return positions

    def prepare_photo(self, resume=None, restart=None):
        if resume is not None and restart is not None:
            raise ValueError("Resume and restart are mutually exclusive")
        if resume is not None:
            if resume.get("active_ids") != list(IDS):
                raise RuntimeError("Wrong resume motor set")
            self.enabled = set(IDS)
        names = (
            "id",
            "model_number",
            "secondary_id",
            "operating_mode",
            "drive_mode",
            "homing_offset",
            "min_position_limit",
            "max_position_limit",
            "profile_acceleration",
            "profile_velocity",
            "goal_pwm",
            "status_return_level",
            "goal_position",
        )
        expected_base = {
            "model_number": 1060,
            "secondary_id": 255,
            "operating_mode": 3,
            "drive_mode": 0,
            "homing_offset": 0,
            "status_return_level": 2,
        }
        for mid in IDS:
            saved = self.read(mid, names)
            if saved["id"] != mid or any(saved[n] != value for n, value in expected_base.items()):
                raise RuntimeError(f"ID{mid} identity/mode/direction/alias changed")
            self.saved[mid] = saved
        observed = self.stable_start()
        self.initial_positions = observed
        if resume is None and restart is None:
            self.plan = self.make_plan(observed)
        elif restart is not None:
            if restart.get("active_ids") != list(IDS):
                raise RuntimeError("Wrong restart motor set")
            self.plan = self.make_plan(tuple(restart["baseline"]))
            original = {int(mid): value for mid, value in restart["route"].items()}
            if set(original) != set(IDS):
                raise RuntimeError("Incomplete original restart state")
            for mid in IDS:
                if any(self.saved[mid][key] != value for key, value in original[mid].items()
                       if key != "goal_position"):
                    raise RuntimeError("OFF motor configuration differs from original session")
            self.saved = original
        else:
            self.plan = self.make_plan(tuple(resume["baseline"]))
            original = {int(mid): value for mid, value in resume["route"].items()}
            goals = {int(mid): value for mid, value in resume["holding_goals"].items()}
            if set(original) != set(IDS) or set(goals) != set(IDS):
                raise RuntimeError("Incomplete original resume state")
            for mid in IDS:
                saved = self.saved[mid]
                if (
                    saved["profile_acceleration"],
                    saved["profile_velocity"],
                    saved["goal_pwm"],
                ) != (1, 6, 350):
                    raise RuntimeError("Held profile changed")
                if (
                    original[mid]["profile_acceleration"],
                    original[mid]["profile_velocity"],
                    original[mid]["goal_pwm"],
                ) != (0, 0, 885):
                    raise RuntimeError("Original RAM snapshot differs from this session")
                if any(saved[key] != original[mid][key] for key in expected_base):
                    raise RuntimeError("Held motor configuration changed")
                if any(
                    saved[key] != original[mid][key]
                    for key in ("min_position_limit", "max_position_limit")
                ):
                    raise RuntimeError("Held position limits changed")
                if saved["goal_position"] != goals[mid] or abs(observed[mid - 1] - goals[mid]) > 20:
                    raise RuntimeError("Held goal changed or pose drifted")
            self.saved = original
        b = self.plan.baseline
        for mid, (low, high) in zip(IDS, self.window_offsets):
            low, high = b[mid - 1] + low, b[mid - 1] + high
            saved = self.saved[mid]
            if not saved["min_position_limit"] <= low <= high <= saved["max_position_limit"]:
                raise RuntimeError("Photo envelope exceeds register limits")
            self.port.envelopes[mid] = WriteEnvelope(
                mid,
                low,
                high,
                frozenset({1, saved["profile_acceleration"]}),
                frozenset({6, saved["profile_velocity"]}),
                frozenset({350, saved["goal_pwm"]}),
            )
        if any(
            not self.port.envelopes[mid].goal_low
            <= observed[mid - 1]
            <= self.port.envelopes[mid].goal_high
            for mid in IDS
        ):
            raise RuntimeError("Observed pose outside original photo envelope")
        self.goal = observed if restart is not None else (
            b if resume is None else tuple(goals[mid] for mid in IDS)
        )
        self.hold_reference = observed
        self.stage = "prepared"
        self.event(
            "plan",
            baseline=b,
            active_ids=list(IDS),
            route=self.saved,
            calibration_verified=False,
            profile_velocity=6,
            hold_seconds=2.5,
            resumed=resume is not None,
            restarted_from_off=restart is not None,
            initial_positions=observed,
        )
        return b

    def target(self, degrees):
        if self.plan is None:
            raise RuntimeError("Fresh plan required")
        return tuple(b + round(v * 4096 / 360) for b, v in zip(self.plan.baseline, degrees))

    def enable_photo(self):
        if self.plan is None:
            raise RuntimeError("Fresh plan required")
        self.stage = "enabling"
        for mid in IDS:
            if self.stop_requested():
                raise RuntimeError("Stop requested")
            for name, value in (
                ("acceleration", 1),
                ("velocity", 6),
                ("pwm", 350),
                ("goal", self.initial_positions[mid - 1]),
            ):
                self.write(mid, name, value)
            self.enabled.add(mid)
            self.write(mid, "torque", 1)
            observed = self.sample()
            if any(abs(p - b) > 15 for p, b in zip(observed, self.initial_positions)):
                raise RuntimeError("Arm jumped on torque enable")
        self.stage = "holding_baseline"

    def move_photo(self, target):
        if self.enabled != set(IDS) or self.plan is None:
            raise RuntimeError("All five motors must be holding")
        if len(target) != 5 or any(
            not self.port.envelopes[mid].goal_low
            <= target[mid - 1]
            <= self.port.envelopes[mid].goal_high
            for mid in IDS
        ):
            raise ValueError("Target outside photo envelope")
        # Return long moves to serial stages: no axis jumps over the reviewed 30 degrees.
        origin = self.sample()
        stages = max(1, math.ceil(max(abs(t - p) for t, p in zip(target, origin)) / 341))
        for step in range(1, stages + 1):
            waypoint = tuple(round(p + (t - p) * step / stages) for p, t in zip(origin, target))
            self.move_waypoint(waypoint)

    def move_waypoint(self, target):
        origin = self.sample()
        self.stage = "moving"
        previous_goal = self.goal
        self.goal = target
        for mid in IDS:
            if target[mid - 1] != previous_goal[mid - 1]:
                self.write(mid, "goal", target[mid - 1])
        start = self.clock()
        recent = []
        corrected = set()
        corrected_at = {}
        while True:
            measured = self.sample()
            elapsed = self.clock() - start
            for mid in IDS:
                # Direction/overshoot/holding checks always precede any adjustment.
                self.check_follow(mid, measured[mid - 1], origin[mid - 1], target[mid - 1], 0)
            recent = [*recent, measured][-10:]
            if elapsed >= 1:
                previous = set(corrected)
                self.compensate(recent, target, corrected)
                for mid in corrected - previous:
                    corrected_at[mid] = self.clock()
            for mid in IDS:
                age = self.clock() - corrected_at.get(mid, start)
                self.check_follow(mid, measured[mid - 1], origin[mid - 1], target[mid - 1], age)
            if len(recent) == 10 and all(
                abs(measured[i] - target[i]) <= 20
                and max(p[i] for p in recent) - min(p[i] for p in recent) <= 3
                for i in range(5)
            ):
                self.hold_reference = measured
                self.event("reached", target=target, positions=measured)
                return
            if elapsed > 18:
                raise RuntimeError("Photo waypoint deadline")
            self.sleep(0.05)

    def hold(self, seconds=2.5):
        until = self.clock() + seconds
        while self.clock() < until:
            measured = self.sample()
            if any(abs(p - t) > 20 for p, t in zip(measured, self.hold_reference)):
                raise RuntimeError("Photo holding drift")
            self.sleep(0.05)

    def return_and_release(self):
        if self.plan is None:
            raise RuntimeError("Fresh baseline missing")
        b = self.plan.baseline
        p = self.sample()
        self.move_photo((b[0], b[1], p[2], p[3], b[4]))
        p = self.sample()
        self.move_photo((b[0], b[1], p[2], b[3], b[4]))
        for degrees in (60, 30, 0):
            target = self.target([0, 0, degrees, 0, 0])
            if degrees == 0 or self.sample()[2] > target[2] + 20:
                self.move_photo(target)
        self.hold()
        before = self.sample()
        if any(abs(p - t) > 20 for p, t in zip(before, b)):
            raise RuntimeError("Not back at stable baseline")
        for mid in reversed(IDS):
            self.write(mid, "torque", 0)
            if self.read(mid, ("torque_enable",))["torque_enable"] != 0:
                raise RuntimeError(f"ID{mid} OFF unconfirmed")
            self.enabled.remove(mid)
        for _ in range(10):
            measured = self.sample()
            if any(abs(p - t) > 20 for p, t in zip(measured, before)):
                raise RuntimeError("Shift after release")
            self.sleep(0.05)
        for mid in IDS:
            for name, register in (
                ("pwm", "goal_pwm"),
                ("velocity", "profile_velocity"),
                ("acceleration", "profile_acceleration"),
            ):
                self.write(mid, name, self.saved[mid][register])
                if self.read(mid, (register,))[register] != self.saved[mid][register]:
                    raise RuntimeError("RAM restore mismatch")
        self.event("released_supported", positions=self.current, all_torque_off=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume-log", type=Path)
    parser.add_argument("--restart-from-off-log", type=Path)
    args = parser.parse_args()
    if args.resume_log and args.restart_from_off_log:
        parser.error("Resume and restart are mutually exclusive")
    poses = load_poses(args.plan)
    lookup = {p["name"]: p for p in poses}
    args.output.mkdir(parents=True, exist_ok=False)
    stopped = [False]

    def stop(_s, _f):
        stopped[0] = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    with (args.output / "events.jsonl").open("x") as log:

        def emit(event):
            log.write(json.dumps(event, ensure_ascii=False) + "\n")
            log.flush()
            if event["kind"] != "sample":
                print(json.dumps(event, ensure_ascii=False), flush=True)

        with open_standby_bus("/dev/serial/by-id/usb-BestTechnology_E148_E148-if00-port0") as (
            port,
            packet,
        ):
            controller = PhotoController(port, packet, emit, stop_requested=lambda: stopped[0])
            resume = None
            if args.resume_log:
                events = [json.loads(line) for line in args.resume_log.read_text().splitlines()]
                resume = next(e for e in events if e["kind"] == "plan")
                last_stop = max(i for i, e in enumerate(events) if e["kind"] == "stop")
                stop_event = events[last_stop]
                if stop_event.get("enabled") != list(IDS):
                    raise RuntimeError("Original stop did not hold five motors")
                writes = events[last_stop + 1 :]
                if len(writes) != 5 or any(
                    e["kind"] != "write" or e["name"] != "goal" for e in writes
                ):
                    raise RuntimeError("Original holding writes incomplete")
                resume["holding_goals"] = {e["motor_id"]: e["value"] for e in writes}
            restart = None
            if args.restart_from_off_log:
                original_events = [json.loads(line) for line in
                                   args.restart_from_off_log.read_text().splitlines()]
                restart = next(e for e in original_events if e["kind"] == "plan")
            controller.prepare_photo(resume, restart)
            if not args.execute:
                return 0
            # An actual initial photo is a precondition, supplied by the operator script.
            initial = args.output.parent / "photos/rest.jpg"
            if not initial.is_file():
                raise RuntimeError("Actual rest camera image required before enabling")
            command = args.output / "command.txt"
            try:
                if resume is None:
                    controller.enable_photo()
                while not stopped[0]:
                    if command.exists():
                        action = command.read_text().strip()
                        command.unlink()
                        if action == "finish":
                            controller.return_and_release()
                            return 0
                        if action == "stop":
                            raise RuntimeError("Operator stop")
                        if action.startswith("stage:"):
                            delta = json.loads(action[6:])
                            controller.move_photo(controller.target(delta))
                            name = "transition"
                        else:
                            pose = lookup[action]
                            controller.move_photo(controller.target(pose["delta_deg"]))
                            name = pose["name"]
                        controller.hold()
                        record = {
                            "name": name,
                            "positions": controller.current,
                            "at": time.time(),
                            "hold_seconds": 2.5,
                            "commanded_goal_counts": controller.goal,
                            "settled_reference_counts": controller.hold_reference,
                            "goal_error_counts": [
                                p - t for p, t in zip(controller.current, controller.goal)
                            ],
                            "hold_drift_counts": [
                                p - t for p, t in zip(controller.current, controller.hold_reference)
                            ],
                        }
                        temp = args.output / "ready.tmp"
                        temp.write_text(json.dumps(record))
                        temp.replace(args.output / "ready.json")
                        controller.event("photo_ready", **record)
                    else:
                        controller.hold(0.1)
                raise RuntimeError("Signal stop")
            except BaseException as exc:
                controller.freeze(f"{type(exc).__name__}: {exc}")
                return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
