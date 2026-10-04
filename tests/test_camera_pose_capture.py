"""Check new neutral and its narrower guard using actual SDK packets offline."""

from pathlib import Path

import pytest
from dynamixel_sdk import PacketHandler
from test_id3_motion import FakeClock
from xl430_emulator import EmuSerial

from arm_observer.camera_pose_capture import (
    CameraPhotoController,
    DiverseCameraPhotoController,
    load_plan,
)
from arm_observer.motion_guard import MotionViolation
from arm_observer.standby_motion import StandbyPort

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = (2102, 3473, 1147, 3398, 1951)


def controller(positions=REFERENCE, controller_class=CameraPhotoController):
    port = StandbyPort("offline-emulator")
    port.ser = EmuSerial(positions=positions, step=12)
    port.is_open = True
    port.baudrate = 1000000
    port.tx_time_per_byte = 0.01
    clock = FakeClock()
    c = controller_class(
        port, PacketHandler(2.0), lambda _: None, clock.monotonic, clock.sleep, reference=REFERENCE
    )
    return c, port.ser


def test_mounted_camera_new_baseline_refuses_old_pose_without_writes():
    c, serial = controller((2063, 3123, 1147, 2049, 2059))
    with pytest.raises(ValueError, match="neutral differs"):
        c.prepare_photo()
    assert not serial.writes()


def test_mounted_camera_sdk_pose_extremes_release_and_smaller_envelope():
    c, serial = controller()
    c.prepare_photo()
    with pytest.raises(MotionViolation):
        c.packet.write4ByteTxRx(c.port, 3, 116, REFERENCE[2] + 500)
    assert not serial.writes()
    c.enable_photo()
    spec = load_plan(ROOT / "config/camera_pose_capture_20261004.json")
    for pose in (spec["poses"][0], spec["poses"][3], spec["poses"][-1]):
        c.move_photo(c.target(pose["delta_deg"]))
    c.return_and_release()
    assert all(serial.torque(i) == 0 for i in range(1, 6))
    assert {address for _, address, _ in serial.writes()} <= {64, 100, 108, 112, 116}
    assert all(c.read(i, ("goal_pwm",))["goal_pwm"] == 885 for i in range(1, 6))
    assert all(
        c.read(i, ("profile_velocity", "profile_acceleration"))
        == {"profile_velocity": 0, "profile_acceleration": 0}
        for i in range(1, 6)
    )


def test_diverse_plan_small_shoulder_and_wrist_guard_and_return():
    c, serial = controller(controller_class=DiverseCameraPhotoController)
    c.prepare_photo()
    with pytest.raises(ValueError, match='Open elbow'):
        c.target([0, 3, 10, 0, 0])
    for mid, offset in ((2, 65), (4, -31), (4, 100), (5, 16)):
        with pytest.raises(MotionViolation):
            c.packet.write4ByteTxRx(c.port, mid, 116, REFERENCE[mid-1]+offset)
    assert not serial.writes()
    c.enable_photo()
    for delta in ([0, 0, 30, 0, 0], [0, 3, 30, 6, 0], [-30, -3, 20, 3, 0]):
        c.move_photo(c.target(delta))
    c.return_and_release()
    assert all(serial.torque(i) == 0 for i in range(1, 6))
    assert {address for _, address, _ in serial.writes()} <= {64, 100, 108, 112, 116}
