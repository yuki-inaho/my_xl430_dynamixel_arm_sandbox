"""D19 finite elbow observation; reuse guarded motion and existing camera owners."""
import argparse
import json
import shutil
import time
import urllib.request
from functools import partial
from pathlib import Path

from arm_observer.camera_pose_capture import CameraPlan
from arm_observer.photo_session import (
    ARM_CONFIG,
    load_previous_plan,
    photo_device,
    stop_handler,
    write_event,
)
from arm_observer.pose_capture_motion import PhotoController
from arm_observer.standby_motion import open_standby_bus


class ProbeController(PhotoController):
    window_offsets = ((-15, 15), (-15, 15), (-15, 200), (-15, 15), (-15, 15))

    def make_plan(self, baseline):
        reference = (2021, 3537, 1133, 3390, 2091)
        if any(abs(p - r) > 20 for p, r in zip(baseline, reference)):
            raise RuntimeError("Current mounted-gripper reference changed; observe again")
        return CameraPlan(baseline)

    def profile_pwm(self, mid):
        return 310 if mid == 5 else 350

    def sample(self):
        observed = super().sample()
        for mid, motor in self.last_motors.items():
            bound = 370 if mid == 5 else 450
            if motor.load_raw is None or abs(motor.load_raw) > bound:
                raise RuntimeError(f"ID{mid} unknown/excessive load")
        now = self.clock()
        if now >= getattr(self, "next_health_event", 0):
            self.event("motor_snapshot", stage=self.stage, positions=observed,
                       load={str(mid): m.load_raw for mid, m in self.last_motors.items()},
                       pwm={str(mid): m.pwm_raw for mid, m in self.last_motors.items()},
                       velocity={str(mid): m.velocity_raw for mid, m in self.last_motors.items()})
            self.next_health_event = now + 1
        if self.stage == "moving":
            if getattr(self, "progress_goal", None) != self.goal:
                self.progress_goal, self.progress_history = self.goal, []
            self.progress_history = [
                (t, p) for t, p in self.progress_history if t >= now - 1.6
            ] + [(now, observed)]
            if now - self.progress_history[0][0] >= 1.5:
                for i in range(5):
                    if i + 1 not in self.commanded_axes:
                        continue
                    span = max(p[i] for _, p in self.progress_history)
                    span -= min(p[i] for _, p in self.progress_history)
                    if abs(observed[i] - self.goal[i]) > 25 and span < 4:
                        raise RuntimeError(f"ID{i + 1} far-target stagnation")
        return observed

    def compensate_photo(self, recent, target, corrected, corrected_at):
        # This observation uses no automatic extra displacement against a stalled axis.
        pass

    def freeze(self, reason):
        self.freeze_moving_axes = (
            set(self.commanded_axes) if self.stage == "moving" else set()
        )
        super().freeze(reason)

    def freeze_goal(self, mid, observed):
        # Resetting an already stationary loaded goal to present count causes sag
        # again on every restart. Stop the commanded axis, retain supporting goals.
        return observed if mid in self.freeze_moving_axes else self.goal[mid - 1]

    def return_to_baseline(self):
        if self.plan is None:
            raise RuntimeError("Fresh baseline required")
        self.move_photo(self.plan.baseline)
        self.hold()


def capture_pair(output, label, controller):
    for camera, port in (("d435", 18108), ("d405", 18109)):
        observation = {"positions": controller.sample(), "host_at_unix_s": time.time(),
                       "active_ids": sorted(controller.enabled), "stage": controller.stage}
        if any(m.velocity_raw != 0 for m in controller.last_motors.values()):
            raise RuntimeError("Camera capture requested while an axis is moving")
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/capture", method="POST",
            data=json.dumps({"not_before_unix_s": observation["host_at_unix_s"]}).encode(),
            headers={"Content-Type": "application/json"},
        )
        receipt = json.load(urllib.request.urlopen(request, timeout=10))
        observation["after_positions"] = controller.sample()
        observation["after_host_at_unix_s"] = time.time()
        if any(m.velocity_raw != 0 for m in controller.last_motors.values()) or any(
            abs(p - b) > 20
            for p, b in zip(observation["after_positions"], observation["positions"])
        ):
            raise RuntimeError("Motion/drift during camera capture")
        source = Path(receipt["path"])
        destination = output / label / camera
        shutil.copytree(source, destination)
        (destination / "robot-before-capture.json").write_text(json.dumps(observation) + "\n")
        controller.event("capture", label=label, camera=camera,
                         source=str(source), relative=str(destination.relative_to(output)),
                         observation=observation)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume-log", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    stopped = stop_handler()
    with (args.output / "events.jsonl").open("x") as log:
        with open_standby_bus(photo_device(ARM_CONFIG, None)) as (port, packet):
            controller = ProbeController(port, packet, partial(write_event, log),
                                         stop_requested=stopped)
            resume = load_previous_plan(args.resume_log, held=True) if args.resume_log else None
            controller.prepare_photo(resume=resume)
            if not args.execute:
                return 0
            try:
                if resume is not None:
                    controller.stage = "observed_stopped_hold"
                    controller.hold()
                    capture_pair(args.output, "observed-stopped-hold", controller)
                    controller.return_and_release()
                    capture_pair(args.output, "returned-off", controller)
                    return 0
                capture_pair(args.output, "before", controller)
                controller.enable_photo()
                controller.move_photo(controller.target((0, 0, 15, 0, 0)))
                controller.hold()
                capture_pair(args.output, "elbow-open-15", controller)
                controller.return_and_release()
                capture_pair(args.output, "returned-off", controller)
                return 0
            except Exception as error:
                controller.freeze(f"{type(error).__name__}: {error}")
                return 2


if __name__ == "__main__":
    raise SystemExit(main())
