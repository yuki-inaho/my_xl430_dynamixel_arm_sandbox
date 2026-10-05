"""Real SDK/serial guard checks; no robot hardware used."""

import json
import time
from datetime import datetime
from types import SimpleNamespace

import pytest
from dynamixel_sdk import PacketHandler
from xl430_emulator import EmuSerial, put

from arm_observer.motion_guard import MotionViolation
from arm_observer.pose_gui_control import PoseGuiController, PoseGuiPort


def controller():
    port = PoseGuiPort("offline-emulator")
    serial = EmuSerial(positions=(1518, 2841, 1139, 3372, 2091))
    port.ser = serial
    port.is_open, port.baudrate, port.tx_time_per_byte = True, 1000000, 0.01
    for mid, motor in serial.motors.items():
        put(motor.t, 100, 2, 310 if mid == 5 else 350)
        put(motor.t, 108, 4, 1)
        put(motor.t, 112, 4, 6)
        put(motor.t, 116, 4, 3000)  # stale goals must never be used on ON
    return PoseGuiController(port, PacketHandler(2), lambda _: None, sleep=lambda _: None), serial


def test_manual_torque_support_current_park_and_no_background_writes():
    c, serial = controller()
    c.snapshot()
    with pytest.raises(RuntimeError, match="Support"):
        c.torque(True, support_confirmed=False)
    assert serial.writes() == []
    with pytest.raises(MotionViolation):
        c.packet.write1ByteTxRx(c.port, 1, 64, 1)
    assert serial.writes() == []
    c.torque(True, support_confirmed=True)
    expected = [(mid, address, value) for mid, pos in enumerate((1518, 2841, 1139, 3372, 2091), 1)
                for address, value in ((116, pos), (64, 1))]
    assert serial.writes() == expected
    c.torque(True, support_confirmed=True)  # already ON: supporting goals unchanged
    assert serial.writes() == expected
    c.torque(False, support_confirmed=True)
    assert serial.writes()[10:] == [(mid, 64, 0) for mid in (5, 4, 3, 2, 1)]
    assert all(serial.torque(mid) == 0 for mid in range(1, 6))
    with pytest.raises(MotionViolation):
        c.packet.write2ByteTxRx(c.port, 2, 100, 395)


def test_unreviewed_profile_and_secondary_alias_refused_before_any_write():
    c, serial = controller()
    put(serial.motors[5].t, 100, 2, 0)
    with pytest.raises(RuntimeError, match="profile"):
        c.torque(True, support_confirmed=True)
    assert serial.writes() == []
    put(serial.motors[5].t, 100, 2, 310)
    put(serial.motors[4].t, 12, 1, 2)
    with pytest.raises(RuntimeError, match="alias"):
        c.torque(False, support_confirmed=True)
    assert serial.writes() == []


def test_on_from_power_cycle_profiles_caps_pwm_without_increasing_low_limits():
    c, serial = controller()
    for mid, motor in serial.motors.items():
        put(motor.t, 100, 2, 100 if mid == 1 else 885)
        put(motor.t, 108, 4, 0)
        put(motor.t, 112, 4, 0)
    c.torque(True, support_confirmed=True)
    for mid in range(1, 6):
        route = c.read(mid, ("goal_pwm", "profile_acceleration", "profile_velocity"))
        assert route == {"goal_pwm": 100 if mid == 1 else 310 if mid == 5 else 350,
                         "profile_acceleration": 1, "profile_velocity": 6}
    with pytest.raises(MotionViolation):
        c.packet.write4ByteTxRx(c.port, 1, 112, 6)


def test_capture_copies_rgbd_brackets_counts_and_does_not_promote_unknown_or_moving(
    monkeypatch, tmp_path
):
    from arm_observer import pose_gui

    source = tmp_path / "camera-owner"
    source.mkdir()
    files = ("color.png", "depth.png", "aligned_depth.png", "depth_preview.png", "ir_left.png",
             "ir_right.png", "metadata.json", "calibration.toml")
    for name in files:
        (source / name).write_bytes(b"preserved camera artifact")
    old_frame = [False]

    def http(_base, path, payload=None):
        serial = "d435" if _base == "http://d435" else "camera"
        if path == "/status.json":
            return json.dumps({"serial": serial, "age_seconds": 0}).encode()
        received = time.time() - (10 if old_frame[0] else 0)
        return json.dumps({"path": str(source), "metadata": {
            "requested_serial": serial,
            "host_frame_received_at": datetime.fromtimestamp(received).astimezone().isoformat()
        }}).encode()

    monkeypatch.setattr(pose_gui, "http", http)
    c, serial = controller()
    path = pose_gui.capture(c, "http://localhost", "camera", tmp_path)
    record = json.loads(path.read_text())
    assert record["accepted"] and record["counts"] == [1518, 2841, 1139, 3372, 2091]
    assert record["before"]["observed_at"] <= record["after"]["observed_at"]
    assert all((path.parent / name).read_bytes() == (source / name).read_bytes() for name in files)
    assert serial.writes() == []
    station = pose_gui.Station(SimpleNamespace(camera="http://d405", serial="camera",
                            d435_camera="http://d435", d435_serial="d435"), tmp_path)
    external = station.capture(c, "d435")
    d435 = json.loads(external.read_text())
    assert d435["camera_name"] == "D435" and d435["accepted"]
    assert d435["camera_receipt"]["metadata"]["requested_serial"] == "d435"
    assert d435["counts"] == record["counts"]
    assert external.parent.name.startswith("capture-d435-")
    with pytest.raises(ValueError, match="selection"):
        station.capture(c, "unknown-camera")
    put(serial.motors[2].t, 128, 4, 1)
    moving = json.loads(pose_gui.capture(c, "http://localhost", "camera", tmp_path).read_text())
    assert not moving["accepted"]
    path = pose_gui.capture(None, "http://localhost", "camera", tmp_path)
    camera_only = json.loads(path.read_text())
    assert camera_only["counts"] is None and not camera_only["accepted"]
    old_frame[0] = True
    with pytest.raises(RuntimeError, match="bracket"):
        pose_gui.capture(c, "http://localhost", "camera", tmp_path)
