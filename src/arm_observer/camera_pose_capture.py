"""Photo-reviewed D405-mounted poses, reusing the bounded photo controller."""

import argparse
import json
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from arm_observer.photo_session import (
    load_previous_plan,
    run_commands,
    stop_handler,
    validate_poses,
    write_event,
)
from arm_observer.pose_capture_motion import PhotoController
from arm_observer.standby_motion import open_standby_bus


@dataclass(frozen=True)
class CameraPlan:
    baseline: tuple[int, ...]


class CameraPhotoController(PhotoController):
    window_offsets = ((-371, 371), (-15, 15), (-15, 371), (-144, 144), (-15, 15))

    def __init__(self, *args, reference, **kwargs):
        super().__init__(*args, **kwargs)
        self.reference = tuple(reference)

    def make_plan(self, baseline):
        if (
            len(baseline) != 5
            or len(self.reference) != 5
            or any(
                type(p) is not int or not 0 <= p <= 4095 or abs(p - r) > 3
                for p, r in zip(baseline, self.reference)
            )
        ):
            raise ValueError("New camera-mounted neutral differs from observed reference")
        return CameraPlan(tuple(baseline))


def load_plan(path):
    spec = json.loads(path.read_text())
    if spec["profiles"] != dict(velocity=6, acceleration=1, pwm=350, hold_seconds=2.5):
        raise ValueError("Unreviewed motion profile")
    validate_poses(spec["poses"], 20, [(-30, 30), (0, 0), (0, 30), (-10, 10), (0, 0)])
    return spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume-log", type=Path)
    args = parser.parse_args()
    spec = load_plan(args.plan)
    if args.execute and not (args.output / "neutral/color.png").is_file():
        raise RuntimeError("Actual mounted-camera neutral RGB-D must be saved first")
    args.output.mkdir(parents=True, exist_ok=True)
    stopped = stop_handler()
    resume = load_previous_plan(args.resume_log, held=True) if args.resume_log else None
    with (args.output / "events.jsonl").open("x") as log:
        with open_standby_bus(spec["device"]) as (port, packet):
            controller = CameraPhotoController(
                port,
                packet,
                partial(write_event, log),
                reference=spec["reference_counts"],
                stop_requested=stopped,
            )
            controller.prepare_photo(resume)
            if not args.execute:
                return 0
            return run_commands(controller, spec["poses"], args.output, resume=resume is not None)


if __name__ == "__main__":
    raise SystemExit(main())
