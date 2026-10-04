"""D11 photo session: fresh-baseline RAM-only motion, command gated camera review."""

import argparse
import json
import math
from functools import partial
from pathlib import Path

from arm_observer.id3_motion import healthy, position
from arm_observer.motion_guard import WriteEnvelope
from arm_observer.photo_session import (
    ARM_CONFIG,
    load_previous_plan,
    photo_device,
    run_commands,
    stop_handler,
    validate_poses,
    write_event,
)
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
    validate_poses(poses, 24, [(-30, 30), (-3, 3), (0, 78), (-36, 0), (-10, 10)])
    expected = [[0] * 5, [0, 0, 72, -30, 0], [-30, 0, 72, -30, 0], [30, 0, 72, -30, 0]]
    if [pose["delta_deg"] for pose in poses[:4]] != expected:
        raise ValueError("Rest/standby/yaw definitions changed")
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

    def prepare_photo(self, resume: dict | None = None, restart: dict | None = None):
        if resume is not None and restart is not None:
            raise ValueError("Resume and restart are mutually exclusive")
        if resume is not None:
            if resume.get("active_ids") != list(IDS):
                raise RuntimeError("Wrong resume motor set")
            self.enabled = set(IDS)
        self.read_photo_settings()
        observed = self.stable_start()
        self.initial_positions = observed
        previous = resume if resume is not None else restart
        if previous is None:
            self.plan = self.make_plan(observed)
            self.goal = observed
        else:
            self.restore_session_snapshot(previous, observed, held=resume is not None)
        self.configure_photo_envelopes(observed)
        if self.plan is None:
            raise RuntimeError("Fresh plan required")
        self.hold_reference = observed
        self.stage = "prepared"
        self.event(
            "plan",
            baseline=self.plan.baseline,
            active_ids=list(IDS),
            route=self.saved,
            calibration_verified=False,
            profile_velocity=6,
            hold_seconds=2.5,
            resumed=resume is not None,
            restarted_from_off=restart is not None,
            initial_positions=observed,
        )
        return self.plan.baseline

    def read_photo_settings(self):
        expected = {
            "model_number": 1060,
            "secondary_id": 255,
            "operating_mode": 3,
            "drive_mode": 0,
            "homing_offset": 0,
            "status_return_level": 2,
        }
        names = (
            *expected,
            "id",
            "min_position_limit",
            "max_position_limit",
            "profile_acceleration",
            "profile_velocity",
            "goal_pwm",
            "goal_position",
        )
        for mid in IDS:
            saved = self.read(mid, names)
            if saved["id"] != mid or any(saved[n] != value for n, value in expected.items()):
                raise RuntimeError(f"ID{mid} identity/mode/direction/alias changed")
            self.saved[mid] = saved

    def restore_session_snapshot(self, previous, observed, *, held):
        if previous.get("active_ids") != list(IDS):
            raise RuntimeError("Wrong previous motor set")
        self.plan = self.make_plan(tuple(previous["baseline"]))
        original = {int(mid): value for mid, value in previous["route"].items()}
        if set(original) != set(IDS):
            raise RuntimeError("Incomplete original session state")
        if held:
            goals = {int(mid): value for mid, value in previous["holding_goals"].items()}
            if set(goals) != set(IDS):
                raise RuntimeError("Incomplete original holding goals")
            self.check_held_snapshot(original, goals, observed)
            self.goal = tuple(goals[mid] for mid in IDS)
        else:
            self.check_off_snapshot(original)
            self.goal = observed
        self.saved = original

    def check_off_snapshot(self, original):
        for mid in IDS:
            if any(
                self.saved[mid][key] != value
                for key, value in original[mid].items()
                if key != "goal_position"
            ):
                raise RuntimeError("OFF motor configuration differs from original session")

    def check_held_snapshot(self, original, goals, observed):
        for mid in IDS:
            if (
                original[mid]["profile_acceleration"],
                original[mid]["profile_velocity"],
                original[mid]["goal_pwm"],
            ) != (0, 0, 885):
                raise RuntimeError("Original RAM snapshot differs from this session")
            expected = dict(original[mid])
            expected.update(
                profile_acceleration=1, profile_velocity=6, goal_pwm=350, goal_position=goals[mid]
            )
            if self.saved[mid] != expected:
                raise RuntimeError("Held profile/configuration/goal changed")
            if abs(observed[mid - 1] - goals[mid]) > 20:
                raise RuntimeError("Held pose drifted")

    def configure_photo_envelopes(self, observed):
        if self.plan is None:
            raise RuntimeError("Fresh plan required")
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
                self.compensate_photo(recent, target, corrected, corrected_at)
            for mid in IDS:
                age = self.clock() - corrected_at.get(mid, start)
                self.check_follow(mid, measured[mid - 1], origin[mid - 1], target[mid - 1], age)
            if self.photo_settled(recent, target):
                self.hold_reference = measured
                self.stage = "holding_photo"
                self.event("reached", target=target, positions=measured)
                return
            if elapsed > 18:
                raise RuntimeError("Photo waypoint deadline")
            self.sleep(0.05)

    def compensate_photo(self, recent, target, corrected, corrected_at):
        previous = set(corrected)
        self.compensate(recent, target, corrected)
        for mid in corrected - previous:
            corrected_at[mid] = self.clock()

    @staticmethod
    def photo_settled(recent, target):
        return len(recent) == 10 and all(
            abs(recent[-1][i] - target[i]) <= 20
            and max(p[i] for p in recent) - min(p[i] for p in recent) <= 3
            for i in range(5)
        )

    def hold(self, seconds=2.5):
        until = self.clock() + seconds
        while self.clock() < until:
            measured = self.sample()
            if any(abs(p - t) > 20 for p, t in zip(measured, self.hold_reference)):
                raise RuntimeError("Photo holding drift")
            self.sleep(0.05)

    def return_to_baseline(self):
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

    def return_and_release(self):
        self.return_to_baseline()
        if self.plan is None:
            raise RuntimeError("Fresh baseline missing")
        b = self.plan.baseline
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
        self.restore_ram(IDS)
        self.event(
            "released_supported", positions=self.current, all_torque_off=True, ram_restored=True
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--config", type=Path, default=ARM_CONFIG)
    parser.add_argument("--device")
    parser.add_argument("--resume-log", type=Path)
    parser.add_argument("--restart-from-off-log", type=Path)
    args = parser.parse_args()
    if args.resume_log and args.restart_from_off_log:
        parser.error("Resume and restart are mutually exclusive")
    poses = load_poses(args.plan)
    args.output.mkdir(parents=True, exist_ok=False)
    stopped = stop_handler()
    resume = load_previous_plan(args.resume_log, held=True) if args.resume_log else None
    restart = load_previous_plan(args.restart_from_off_log) if args.restart_from_off_log else None
    with (args.output / "events.jsonl").open("x") as log:
        with open_standby_bus(photo_device(args.config, args.device)) as (
            port,
            packet,
        ):
            controller = PhotoController(
                port, packet, partial(write_event, log), stop_requested=stopped
            )
            controller.prepare_photo(resume, restart)
            if not args.execute:
                return 0
            if not (args.output.parent / "photos/rest.jpg").is_file():
                raise RuntimeError("Actual rest camera image required before enabling")
            return run_commands(
                controller, poses, args.output, resume=resume is not None, allow_stage=True
            )


if __name__ == "__main__":
    raise SystemExit(main())
