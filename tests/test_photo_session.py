"""Exercise shared commands and capture evidence without touching hardware."""

import json
import time
from datetime import datetime

import pytest
from test_pose_capture_motion import setup

from arm_observer.photo_evidence import held_sample, tail_events
from arm_observer.photo_session import load_previous_plan, photo_device, run_commands


@pytest.mark.parametrize("action", ["rest", "unknown-pose"])
def test_shared_runner_releases_on_finish_and_holds_on_invalid_command(tmp_path, action):
    _, controller, serial, events = setup()
    original_emit = controller.emit

    def emit(event):
        original_emit(event)
        if event["kind"] == "photo_ready":
            datetime.fromisoformat(event["at"])
            assert isinstance(event["settled_at_unix_s"], float)
            (tmp_path / "command.txt").write_text("finish")

    controller.emit = emit
    (tmp_path / "command.txt").write_text(action)
    (tmp_path / "ready.json").write_text('{"name":"old-run"}')
    code = run_commands(controller, [{"name": "rest", "delta_deg": [0] * 5}], tmp_path)
    assert code == (0 if action == "rest" else 2)
    assert not (tmp_path / "ready.json").exists()
    assert all(serial.torque(mid) == (action != "rest") for mid in range(1, 6))
    assert events[-1]["kind"] == ("released_supported" if action == "rest" else "write")


def test_resume_rejects_duplicate_motor_holding_writes(tmp_path):
    _, controller, _, events = setup()
    controller.enable_photo()
    controller.freeze("test stop")
    path = tmp_path / "events.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    assert set(load_previous_plan(path, held=True)["holding_goals"]) == set(range(1, 6))
    events[-1]["motor_id"] = 1
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    with pytest.raises(RuntimeError, match="incomplete"):
        load_previous_plan(path, held=True)


def test_device_override_preserves_fixed_transport_contract(tmp_path):
    config = tmp_path / "arm.toml"
    text = (
        '[bus]\ndevice="/dev/example"\nbaudrate=1000000\nprotocol=2.0\nexpected_ids=[1,2,3,4,5]\n'
    )
    config.write_text(text)
    assert photo_device(config) == "/dev/example"
    assert photo_device(config, "/dev/other") == "/dev/other"
    config.write_text(text.replace("1000000", "57600"))
    with pytest.raises(ValueError, match="1 Mbps"):
        photo_device(config)


@pytest.mark.parametrize("fault", [None, "released", "moving", "off", "stale-ready"])
def test_capture_requires_current_held_pose_and_reads_short_complete_log(tmp_path, fault):
    now = time.time()
    ready = dict(name="pose_01", at=now, positions=[2000] * 5)
    announcement = dict(
        kind="photo_ready",
        at=datetime.now().astimezone().isoformat(),
        name=ready["name"],
        settled_at_unix_s=now,
    )
    sample = dict(
        kind="sample",
        at=announcement["at"],
        stage="holding_photo",
        positions=ready["positions"],
        torque={str(mid): True for mid in range(1, 6)},
    )
    if fault == "moving":
        sample["stage"] = "moving"
    elif fault == "off":
        sample["torque"]["3"] = False
    elif fault == "stale-ready":
        ready["at"] -= 1
    events = [announcement, sample]
    if fault == "released":
        events.append(dict(kind="released_supported"))
    path = tmp_path / "events.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events) + '{"unfinished":')
    assert tail_events(path) == events
    if fault is None:
        assert held_sample(tmp_path, ready) == sample
    else:
        with pytest.raises(RuntimeError):
            held_sample(tmp_path, ready)
