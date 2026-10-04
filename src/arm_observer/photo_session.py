"""Shared command and evidence handling for the two bounded photo controllers."""

import json
import signal
import time
from pathlib import Path

from arm_observer.configuration import load_config
from arm_observer.standby_motion import IDS

ARM_CONFIG = Path(__file__).resolve().parents[2] / "config/arm.toml"


def photo_device(config=ARM_CONFIG, device=None):
    bus = load_config(config, device).bus
    if (bus.baudrate, bus.protocol, bus.expected_ids) != (1000000, 2.0, IDS):
        raise ValueError("Photo controller requires Protocol 2.0, 1 Mbps and IDs 1..5")
    return bus.device


def write_event(log, event):
    line = json.dumps(event, ensure_ascii=False)
    log.write(line + "\n")
    log.flush()
    if event["kind"] != "sample":
        print(line, flush=True)


def stop_handler():
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    return lambda: stopped


def validate_poses(poses, count, bounds):
    if len(poses) != count or len({p["name"] for p in poses}) != count:
        raise ValueError(f"Exactly {count} unique poses required")
    for pose in poses:
        if not valid_delta(pose["delta_deg"], bounds):
            raise ValueError("Pose outside reviewed delta bounds")


def valid_delta(values, bounds):
    return len(values) == len(bounds) and all(
        type(v) is int and low <= v <= high for v, (low, high) in zip(values, bounds)
    )


def holding_write(event):
    return event.get("kind") == "write" and event.get("name") == "goal"


def load_previous_plan(path, *, held=False):
    events = [json.loads(line) for line in Path(path).read_text().splitlines()]
    plan = next(e for e in events if e["kind"] == "plan")
    if not held:
        return plan
    return {**plan, "holding_goals": holding_goals(events)}


def holding_goals(events):
    last = max(i for i, e in enumerate(events) if e["kind"] == "stop")
    writes = events[last + 1 :]
    if (
        events[last].get("enabled") != list(IDS)
        or len(writes) != 5
        or any(not holding_write(e) for e in writes)
        or {e.get("motor_id") for e in writes} != set(IDS)
    ):
        raise RuntimeError("Interrupted five-motor holding evidence is incomplete")
    return {e["motor_id"]: e["value"] for e in writes}


def run_commands(controller, poses, output, *, resume=False, allow_stage=False):
    lookup = {p["name"]: p for p in poses}
    command = output / "command.txt"
    ready = output / "ready.json"
    # A previous process's ready file must never authorize a new capture.
    ready.unlink(missing_ok=True)
    try:
        if not resume:
            controller.enable_photo()
        while not controller.stop_requested():
            if not command.exists():
                controller.hold(0.1)
                continue
            action = command.read_text().strip()
            command.unlink()
            ready.unlink(missing_ok=True)
            if action == "finish":
                controller.return_and_release()
                return 0
            if action == "stop":
                raise RuntimeError("Operator stop")
            name, delta = command_pose(action, lookup, allow_stage=allow_stage)
            controller.move_photo(controller.target(delta))
            controller.hold()
            publish_ready(controller, output, name, delta)
        raise RuntimeError("Signal stop")
    except BaseException as error:
        controller.freeze(f"{type(error).__name__}: {error}")
        try:
            ready.unlink(missing_ok=True)
        except OSError:
            pass  # Broken evidence storage must not prevent the holding writes.
        return 2


def command_pose(action, lookup, *, allow_stage):
    if allow_stage and action.startswith("stage:"):
        return "transition", json.loads(action[6:])
    return action, lookup[action]["delta_deg"]


def publish_ready(controller, output, name, delta):
    record = dict(
        name=name,
        positions=controller.current,
        at=time.time(),
        delta_deg=delta,
        goal_counts=controller.goal,
        commanded_goal_counts=controller.goal,
        settled_reference_counts=controller.hold_reference,
        goal_error_counts=[p - t for p, t in zip(controller.current, controller.goal)],
        hold_drift_counts=[p - t for p, t in zip(controller.current, controller.hold_reference)],
        hold_seconds=2.5,
        active_ids=list(IDS),
    )
    # Keep ready.json's Unix time for existing consumers; JSONL stays ISO 8601.
    controller.event(
        "photo_ready",
        **{k: v for k, v in record.items() if k != "at"},
        settled_at_unix_s=record["at"],
    )
    temporary = output / "ready.tmp"
    temporary.write_text(json.dumps(record))
    temporary.replace(output / "ready.json")
