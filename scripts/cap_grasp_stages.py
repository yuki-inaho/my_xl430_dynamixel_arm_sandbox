"""D19 camera-reviewed elbow/wrist stages; commands share the existing bounded engine."""
import argparse
import json
import time
from functools import partial
from pathlib import Path

from cap_grasp_probe import ProbeController, capture_pair

from arm_observer.camera_pose_capture import CameraPlan
from arm_observer.photo_session import (
    ARM_CONFIG,
    load_previous_plan,
    photo_device,
    stop_handler,
    write_event,
)
from arm_observer.standby_motion import open_standby_bus

POSES = {
    "elbow30": (0, 0, 30, 0, 0),
    "wrist-down10": (0, 0, 30, -10, 0),
    "wrist-down20": (0, 0, 30, -20, 0),
}
POSITIVE_POSES = {"elbow30": (0, 0, 30, 0, 0), "wrist-plus10": (0, 0, 30, 10, 0)}
REACH_POSES = {"elbow60": (0, 0, 60, 0, 0), "shoulder-minus10": (0, -10, 60, 0, 0)}
FORWARD_POSES = {
    "elbow60": (0, 0, 60, 0, 0), "elbow90": (0, 0, 90, 0, 0),
    "shoulder-plus15": (0, 15, 60, 0, 0), "shoulder-plus30": (0, 30, 60, 0, 0),
}
TRAVEL_POSES = {
    **REACH_POSES,
    **{f"shoulder-minus{a}": (0, -a, 60, 0, 0) for a in (20, 30, 45, 60)},
    **{f"elbow{a}": (0, 0, a, 0, 0) for a in (90, 120)},
}


class StagedController(ProbeController):
    window_offsets = ((-15, 15), (-15, 15), (-15, 371), (-258, 15), (-15, 15))

    def interpolation_origin(self, observed, target):
        return tuple(self.goal[i] if target[i] == self.goal[i] else observed[i]
                     for i in range(5))

    @staticmethod
    def photo_settled(recent, target):
        # Accept an observed approximate pose, not an exact commanded angle.
        return len(recent) == 10 and all(
            abs(recent[-1][i] - target[i]) <= 25
            and max(p[i] for p in recent) - min(p[i] for p in recent) <= 3
            for i in range(5)
        )

    def check_waypoint_follow(self, mid, measured, origin, target, elapsed):
        reference = target if mid in self.commanded_axes else origin
        self.check_follow(mid, measured, origin, reference, elapsed)

    def waypoint_settled(self, recent, target, origin):
        reference = tuple(target[i] if i + 1 in self.commanded_axes else origin[i]
                          for i in range(5))
        return self.photo_settled(recent, reference)

    def return_to_baseline(self):
        if self.plan is None:
            raise RuntimeError("Fresh baseline required")
        b = self.plan.baseline
        p = self.sample()
        self.move_photo((b[0], b[1], p[2], b[3], b[4]))
        self.move_photo(b)
        self.hold()


class PositiveWristController(StagedController):
    window_offsets = ((-15, 15), (-15, 15), (-15, 371), (-15, 144), (-15, 15))


class ReachController(StagedController):
    window_offsets = ((-15, 15), (-144, 15), (-15, 713), (-15, 15), (-15, 15))

    def make_plan(self, baseline):
        super().make_plan(baseline)
        # Preserve the same physical folded reference across runs; do not accumulate
        # a static load offset by redefining neutral after every return.
        return CameraPlan((2021, 3537, 1133, 3390, 2091))

    def return_to_baseline(self):
        if self.plan is None:
            raise RuntimeError("Fresh baseline required")
        b, p = self.plan.baseline, self.sample()
        self.move_photo((b[0], b[1], p[2], b[3], b[4]))
        self.move_photo(b)
        self.hold()


class ForwardController(ReachController):
    window_offsets = ((-15, 15), (-15, 371), (-15, 1054), (-15, 15), (-15, 15))


class TravelController(ReachController):
    window_offsets = ((-15, 15), (-713, 15), (-15, 1395), (-15, 15), (-15, 15))


class RecoveryController(TravelController):
    """Return only; acknowledge the failed held observation without approving exploration."""
    window_offsets = ((-201, 201), (-743, 15), (-15, 1395), (-35, 15), (-15, 15))

    def write(self, mid, name, value):
        if mid == 4 and name == "goal" and value not in (3380, 3390):
            raise RuntimeError("Recovery ID4 permits only retained support or original baseline")
        return super().write(mid, name, value)

    def return_to_baseline(self):
        if self.plan is None:
            raise RuntimeError("Fresh baseline required")
        b = self.plan.baseline
        self.move_photo((self.goal[0], b[1], self.goal[2], self.goal[3], b[4]))
        self.move_photo((self.goal[0], b[1], b[2], self.goal[3], b[4]))
        self.move_photo((self.goal[0], b[1], b[2], b[3], b[4]))
        self.move_photo(b)
        self.hold()


class WideRecoveryController(RecoveryController):
    window_offsets = ((-542, 542), (-743, 15), (-15, 1395), (-35, 15), (-15, 15))

    def return_to_baseline(self):
        if self.plan is None or self.sample()[0] > 1540:
            raise RuntimeError("Lateral escape required before final fold")
        b = self.plan.baseline
        self.move_photo((self.goal[0], self.goal[1], b[2], self.goal[3], b[4]))
        self.move_photo((self.goal[0], b[1], b[2], self.goal[3], b[4]))
        self.move_photo((self.goal[0], b[1], b[2], b[3], b[4]))
        self.move_photo(b)
        self.hold()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume-log", type=Path)
    parser.add_argument("--recovery-read", type=Path,
                        help="Read-only register evidence for an incomplete stop park")
    parser.add_argument("--phase",
                        choices=("wrist-down", "wrist-plus", "reach", "forward", "travel",
                                 "recovery", "recovery-wide"),
                        default="wrist-down")
    args = parser.parse_args()
    if args.recovery_read and (args.phase not in ("recovery", "recovery-wide")
                              or not args.resume_log):
        parser.error("recovery-read requires recovery phase and original resume log")
    args.output.mkdir(parents=True, exist_ok=False)
    requested = stop_handler()
    deadline = time.monotonic() + 600
    with (args.output / "events.jsonl").open("x") as log:
        with open_standby_bus(photo_device(ARM_CONFIG, None)) as (port, packet):
            cls, poses = {
                "wrist-down": (StagedController, POSES),
                "wrist-plus": (PositiveWristController, POSITIVE_POSES),
                "reach": (ReachController, REACH_POSES),
                "forward": (ForwardController, FORWARD_POSES),
                "travel": (TravelController, TRAVEL_POSES),
                "recovery": (RecoveryController, {
                    **{f"id3-return{a}": (0, 0, a, 0, 0) for a in (60, 40, 20)},
                    **{f"yaw{a:+d}": (a, 0, 60, 0, 0) for a in (-5, -15, 5, 15)},
                    "shoulder-return45": (0, -45, 20, 0, 0),
                }),
                "recovery-wide": (WideRecoveryController, {
                    **{f"yaw{a:+d}": (a, 0, 20, 0, 0) for a in (-30, -45)},
                    "id3-return0": (0, 0, 0, 0, 0),
                }),
            }[args.phase]
            c = cls(port, packet, partial(write_event, log),
                    stop_requested=lambda: requested() or time.monotonic() > deadline)
            resume = None
            if args.resume_log:
                resume = load_previous_plan(args.resume_log, held=not bool(args.recovery_read))
            if args.recovery_read:
                if resume is None:
                    raise RuntimeError("Original plan required for recovery")
                status = json.loads(args.recovery_read.read_text())
                goals = {
                    row["motor_id"]: next(r["raw"] for r in row["registers"]
                                          if r["name"] == "goal_position")
                    for row in status["metadata"]["metadata"]
                }
                resume = {**resume, "holding_goals": goals}
                c.event("recovery_read_reference", source=str(args.recovery_read),
                        goals=goals, original_stop=str(args.resume_log))
            baseline = c.prepare_photo(resume=resume)
            if not args.execute:
                return 0
            try:
                if resume is None:
                    capture_pair(args.output, "before", c)
                    c.enable_photo()
                else:
                    c.stage = "observed_stopped_hold"
                    c.hold()
                    capture_pair(args.output, "observed-stopped-hold", c)
                while True:
                    c.hold(0.1)
                    command = args.output / "command.txt"
                    if not command.exists():
                        continue
                    action = command.read_text().strip()
                    command.unlink()
                    (args.output / "ready.json").unlink(missing_ok=True)
                    if action == "finish":
                        c.return_and_release()
                        capture_pair(args.output, "returned-off", c)
                        return 0
                    if action not in poses:
                        raise ValueError("Unreviewed stage")
                    if action == "id3-return0" and c.sample()[0] > 1540:
                        raise RuntimeError("Lateral escape required before final fold")
                    if action.startswith("wrist") and c.sample()[2] < baseline[2] + 228:
                        raise RuntimeError("Wrist change requires observed elbow opening >=20 deg")
                    desired = c.target(poses[action])
                    axis = 1 if action.startswith("yaw") else (
                        4 if action.startswith("wrist") else (
                            2 if action.startswith("shoulder") else 3
                        )
                    )
                    target = tuple(desired[i] if i + 1 == axis else c.goal[i]
                                   for i in range(5))
                    c.move_photo(target)
                    c.hold()
                    capture_pair(args.output, action, c)
                    (args.output / "ready.json").write_text(json.dumps({
                        "action": action, "actual_positions": c.current, "at_unix_s": time.time(),
                        "nominal_degrees": poses[action], "exact_angles_achieved": False,
                    }) + "\n")
            except Exception as error:
                (args.output / "ready.json").unlink(missing_ok=True)
                c.freeze(f"{type(error).__name__}: {error}")
                return 2


if __name__ == "__main__":
    raise SystemExit(main())
