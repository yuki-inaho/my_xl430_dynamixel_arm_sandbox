"""Read complete live log records and require a freshly held, matching pose."""

import json
import time
from datetime import datetime


def tail_events(path, limit=None):
    with path.open("rb") as log:
        log.seek(0, 2)
        start = max(0, log.tell() - limit) if limit is not None else 0
        log.seek(start)
        raw = log.read()
    lines = raw.split(b"\n")
    if start:
        lines = lines[1:]
    # Ignore the last unfinished write, even if it happens to parse as JSON.
    return [json.loads(line) for line in lines[:-1] if line]


def held_sample(dataset, ready):
    events = tail_events(dataset / "events.jsonl")
    terminal = {"stop", "stop_hold_fault", "released_supported", "external_supported_release"}
    if any(e["kind"] in terminal for e in events):
        raise RuntimeError("Motion stopped or released; capture not accepted")
    sample = next((e for e in reversed(events) if e["kind"] == "sample"), None)
    if sample is None:
        raise RuntimeError("Missing robot sample")
    check_sample(sample, ready)
    announced = next((e for e in reversed(events) if e["kind"] == "photo_ready"), None)
    check_ready(announced, ready)
    return sample


def check_ready(announced, ready):
    if (
        announced is None
        or announced["name"] != ready["name"]
        or (announced.get("settled_at_unix_s", announced["at"]) != ready["at"])
    ):
        raise RuntimeError("Ready file does not match the live photo session")


def check_sample(sample, ready):
    if not 0 <= time.time() - sample_time(sample) <= 2:
        raise RuntimeError("No fresh robot telemetry")
    if sample["stage"] != "holding_photo" or any(
        sample.get("torque", {}).get(str(mid)) is not True for mid in range(1, 6)
    ):
        raise RuntimeError("Robot is not holding with all five motors")
    if len(sample["positions"]) != 5 or any(
        abs(p - r) > 20 for p, r in zip(sample["positions"], ready["positions"])
    ):
        raise RuntimeError("Robot drifted from the settled pose")


def sample_time(sample):
    return datetime.fromisoformat(sample["at"]).timestamp()
