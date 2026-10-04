"""Only the distinct ID5 boundary and contact behavior; no serial access."""

import json
import runpy
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_id3_motion import motion_port, write_packet

from arm_observer import gripper_motion
from arm_observer.gripper_motion import MotionAbort, Progress, Start
from arm_observer.motion_guard import MotionViolation


def test_id5_transport_scope_and_exact_limits():
    envelope = Start(
        (2020, 3537, 1133, 3390, 2067),
        (("profile_acceleration", 0), ("profile_velocity", 0), ("goal_pwm", 885)),
    ).envelope()
    port = motion_port(envelope)
    for mid, addr, value, size in [
        (3, 64, 1, 1),
        (254, 64, 1, 1),
        (5, 11, 3, 1),
        (5, 116, 2066, 4),
        (5, 116, 2669, 4),
    ]:
        with pytest.raises(MotionViolation):
            port.writePort(write_packet(mid, addr, value, size))
    assert port.ser.sent == []
    port.writePort(write_packet(5, 116, 2181, 4))
    port.writePort(write_packet(5, 64, 0, 1))
    assert len(port.ser.sent) == 2


def test_stall_contact_aborts_instead_of_pushing_harder():
    progress = Progress(2181, 2067, 0.0, 2067, 0.0)
    assert not progress.observe(2067, 1.0, 0)
    with pytest.raises(MotionAbort, match="stalled"):
        progress.observe(2068, 1.6, 0)


def test_nearby_load_error_requires_ten_stationary_reads_and_blocks_reverse():
    progress = Progress(2181, 2067, 0.0, 2067, 0.0)
    assert not progress.observe(2175, 1.0, 1)
    assert not progress.observe(2176, 1.1, 0)
    assert not progress.observe(2177, 1.2, 0)
    assert not progress.observe(2178, 1.3, 0)
    for i in range(9):
        reached = progress.observe(2178, 1.4 + i * 0.05, 0)
    assert reached
    with pytest.raises(MotionAbort, match="reverse"):
        progress.observe(2050, 1.4, 0)


def test_release_never_restores_high_pwm_without_confirmed_off(monkeypatch):
    session: Any = object.__new__(gripper_motion.Session)
    writes = []
    session.port = SimpleNamespace(is_using=True, clearPort=lambda: None)
    session.reader = None
    session.write = lambda name, value, **kwargs: writes.append((name, value))
    monkeypatch.setattr(
        gripper_motion, "registers", lambda *_: {"torque_enable": 1, "present_position": 2181}
    )
    with pytest.raises(MotionAbort, match="OFF could not"):
        session.release()
    assert writes == [("torque_enable", 0)]


def test_operator_stop_does_not_issue_next_waypoint():
    session: Any = SimpleNamespace(
        enable=lambda: None,
        start=SimpleNamespace(positions=(2020, 3537, 1133, 3390, 2067)),
        emit=lambda *a, **k: None,
    )
    with pytest.raises(MotionAbort, match="operator stop"):
        gripper_motion.run(session, Path("unused-command"), lambda: True)


def test_capture_rejects_previous_ready_after_a_new_goal(tmp_path):
    latest = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/capture_gripper_state.py")
    )["latest_sample"]
    events = [
        {"kind": "write"},
        {"kind": "ready", "actual": 2173},
        {
            "kind": "sample",
            "host_unix_s": time.time(),
            "motors": [
                {"motor_id": 5, "torque_enabled": True, "velocity_raw": 0, "position_counts": 2173}
            ],
        },
    ]
    journal = tmp_path / "motion.jsonl"
    journal.write_text("\n".join(map(json.dumps, events)))
    assert latest(journal)["motors"][0]["position_counts"] == 2173
    journal.write_text("\n".join(map(json.dumps, events + [{"kind": "write"}])))
    with pytest.raises(RuntimeError, match="matching ready"):
        latest(journal)
