"""Photo-reviewed D405-mounted poses, reusing the bounded photo controller."""
import argparse
import json
import signal
import time
from dataclasses import dataclass
from pathlib import Path

from arm_observer.pose_capture_motion import PhotoController
from arm_observer.standby_motion import IDS, open_standby_bus


@dataclass(frozen=True)
class CameraPlan:
    baseline: tuple[int, ...]


class CameraPhotoController(PhotoController):
    window_offsets = ((-371, 371), (-15, 15), (-15, 371), (-144, 144), (-15, 15))

    def __init__(self, *args, reference, **kwargs):
        super().__init__(*args, **kwargs)
        self.reference = tuple(reference)

    def make_plan(self, baseline):
        if len(baseline) != 5 or len(self.reference) != 5 or any(
            type(p) is not int or not 0 <= p <= 4095 or abs(p-r) > 3
            for p, r in zip(baseline, self.reference)
        ):
            raise ValueError("New camera-mounted neutral differs from observed reference")
        return CameraPlan(tuple(baseline))


def load_plan(path):
    spec = json.loads(path.read_text())
    if spec["profiles"] != dict(velocity=6, acceleration=1, pwm=350, hold_seconds=2.5):
        raise ValueError("Unreviewed motion profile")
    if len(spec["poses"]) != 20 or len({p["name"] for p in spec["poses"]}) != 20:
        raise ValueError("Exactly 20 unique poses required")
    for pose in spec["poses"]:
        v = pose["delta_deg"]
        if len(v) != 5 or any(type(x) is not int for x in v):
            raise ValueError("Five integer degree deltas required")
        if not (-30 <= v[0] <= 30 and v[1] == v[4] == 0
                and 0 <= v[2] <= 30 and -10 <= v[3] <= 10):
            raise ValueError("Camera pose exceeds authorized bounds")
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
    stop = [False]
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__(0, True))
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__(0, True))
    with (args.output / "events.jsonl").open("x") as log:
        def emit(event):
            log.write(json.dumps(event, ensure_ascii=False) + "\n")
            log.flush()
            if event["kind"] != "sample":
                print(json.dumps(event, ensure_ascii=False), flush=True)

        with open_standby_bus(spec["device"]) as (port, packet):
            controller = CameraPhotoController(
                port, packet, emit, reference=spec["reference_counts"],
                stop_requested=lambda: stop[0],
            )
            resume = None
            if args.resume_log:
                events = [json.loads(line) for line in args.resume_log.read_text().splitlines()]
                resume = next(e for e in events if e["kind"] == "plan")
                last_stop = max(i for i, e in enumerate(events) if e["kind"] == "stop")
                if events[last_stop].get("enabled") != list(IDS):
                    raise RuntimeError("Resume requires all five motors held")
                writes = events[last_stop+1:]
                if len(writes) != 5 or {e.get("motor_id") for e in writes} != set(IDS) or any(
                    e["kind"] != "write" or e["name"] != "goal" for e in writes
                ):
                    raise RuntimeError("Five holding writes required for resume")
                resume["holding_goals"] = {e["motor_id"]: e["value"] for e in writes}
            controller.prepare_photo(resume)
            if not args.execute:
                return 0
            lookup = {pose["name"]: pose for pose in spec["poses"]}
            command = args.output / "command.txt"
            try:
                if resume is None:
                    controller.enable_photo()
                while not stop[0]:
                    if not command.exists():
                        controller.hold(0.1)
                        continue
                    action = command.read_text().strip()
                    command.unlink()
                    if action == "finish":
                        controller.return_and_release()
                        return 0
                    if action == "stop":
                        raise RuntimeError("Operator stop")
                    pose = lookup[action]
                    controller.move_photo(controller.target(pose["delta_deg"]))
                    controller.hold()
                    record = dict(
                        name=action, positions=controller.current, at=time.time(),
                        delta_deg=pose["delta_deg"], goal_counts=controller.goal,
                        hold_seconds=2.5, active_ids=list(IDS),
                    )
                    ready = args.output / "ready.tmp"
                    ready.write_text(json.dumps(record))
                    ready.replace(args.output / "ready.json")
                    controller.event("photo_ready", **record)
                raise RuntimeError("Signal stop")
            except BaseException as error:
                controller.freeze(f"{type(error).__name__}: {error}")
                return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
