"""Real SDK packets for the separately authorized photo-session motion path."""

from pathlib import Path

import pytest
from dynamixel_sdk import PacketHandler
from test_id3_motion import FakeClock
from xl430_emulator import EmuSerial, get, put

from arm_observer import pose_capture_motion
from arm_observer.motion_guard import MotionViolation
from arm_observer.standby_motion import StandbyPort

ROOT = Path(__file__).resolve().parents[1]


def setup():
    m = pose_capture_motion
    port = StandbyPort("offline-emulator")
    port.ser = EmuSerial(positions=(2063, 3123, 1147, 2049, 2059), step=12)
    port.is_open = True
    port.baudrate = 1000000
    port.tx_time_per_byte = 0.01
    clock, events = FakeClock(), []
    c = m.PhotoController(port, PacketHandler(2.0), events.append, clock.monotonic, clock.sleep)
    c.prepare_photo()
    return m, c, port.ser, events


def test_sdk_pose_path_returns_all_off_and_restores_settings():
    m, c, serial, events = setup()
    c.enable_photo()
    poses = m.load_poses(ROOT / "config/pose_capture_20261004.json")
    # Same engine for each row: exercise staging, both yaw ends and the furthest variant.
    for pose in (poses[1], poses[2], poses[3], poses[-1]):
        c.move_photo(c.target(pose["delta_deg"]))
    c.return_and_release()
    assert all(serial.torque(i) == 0 for i in range(1, 6))
    assert {mid for mid, _, _ in serial.writes()} == {1, 2, 3, 4, 5}
    assert {a for _, a, _ in serial.writes()} <= {64, 100, 108, 112, 116}
    assert events[-1]["kind"] == "released_supported"
    for mid in range(1, 6):
        assert c.read(mid, ("goal_pwm",))["goal_pwm"] == 885


@pytest.mark.parametrize(
    "mid,address,size,value",
    [
        (6, 64, 1, 1),
        (1, 7, 1, 9),
        (1, 64, 2, 1),
        (1, 116, 4, 2500),
        (3, 116, 4, 2400),
        (4, 116, 4, 1500),
        (5, 116, 4, 2300),
    ],
)
def test_sdk_refuses_other_id_eeprom_and_outside_windows(mid, address, size, value):
    _, c, serial, _ = setup()
    with pytest.raises(MotionViolation):
        getattr(c.packet, f"write{size}ByteTxRx")(c.port, mid, address, value)
    assert not serial.writes() and not c.port.is_using


def test_alias_and_wrong_initial_pose_refuse_before_writes():
    m = pose_capture_motion
    port = StandbyPort("offline-emulator")
    port.ser = EmuSerial(positions=(2063, 3123, 1147, 2049, 2059))
    port.is_open = True
    port.baudrate = 1000000
    port.tx_time_per_byte = 0.01
    port.ser.motors[5].t[12] = 1
    c = m.PhotoController(port, PacketHandler(2.0), lambda _: None)
    with pytest.raises(RuntimeError, match="alias"):
        c.prepare_photo()
    assert not port.ser.writes()


def test_stop_holds_all_five_without_release():
    _, c, serial, _ = setup()
    c.enable_photo()
    c.stop_requested = lambda: True
    with pytest.raises(RuntimeError, match="Stop"):
        c.move_photo(c.target([0, 0, 30, 0, 0]))
    c.freeze("stop")
    assert all(serial.torque(i) == 1 for i in range(1, 6))


def test_resume_reads_held_pose_without_reenable_and_restores_original_ram():
    m, c, serial, events = setup()
    plan = next(e for e in events if e["kind"] == "plan")
    c.enable_photo()
    c.move_photo(c.target([0, -3, 66, -24, -10]))
    c.freeze("operator stop")
    goals = {mid: c.read(mid, ("goal_position",))["goal_position"] for mid in range(1, 6)}
    writes_before = len(serial.writes())
    clock = FakeClock()
    resumed = m.PhotoController(c.port, c.packet, events.append, clock.monotonic, clock.sleep)
    resumed.prepare_photo({**plan, "holding_goals": goals})
    assert len(serial.writes()) == writes_before
    assert resumed.plan.baseline == c.plan.baseline
    resumed.move_photo(resumed.target([0, -3, 66, -30, 0]))
    resumed.return_and_release()
    assert all(serial.torque(i) == 0 for i in range(1, 6))
    assert all(resumed.read(i, ("goal_pwm",))["goal_pwm"] == 885 for i in range(1, 6))


def test_resume_rejects_changed_profile_before_any_write():
    m, c, serial, events = setup()
    plan = next(e for e in events if e["kind"] == "plan")
    c.enable_photo()
    goals = {mid: c.read(mid, ("goal_position",))["goal_position"] for mid in range(1, 6)}
    serial.motors[2].t[112:116] = (7).to_bytes(4, "little")
    writes_before = len(serial.writes())
    resumed = m.PhotoController(c.port, c.packet, events.append)
    with pytest.raises(RuntimeError, match="profile"):
        resumed.prepare_photo({**plan, "holding_goals": goals})
    assert len(serial.writes()) == writes_before


@pytest.mark.parametrize("blocked", [False, True])
def test_single_bounded_correction_gets_its_own_progress_check(blocked):
    _, c, serial, events = setup()
    c.enable_photo()
    c.move_photo(c.target([0, -3, 78, -36, -10]))
    motor = serial.motors[2]
    put(motor.t, 132, 4, 3080)

    def loaded_step(amount):
        goal = get(motor.t, 116, 4)
        if blocked or goal <= 3123:
            return
        present = get(motor.t, 132, 4)
        put(motor.t, 132, 4, min(present + amount, goal - 30))

    motor.step = loaded_step
    if blocked:
        with pytest.raises(RuntimeError, match="ID2 no progress"):
            c.move_photo(c.target([0, 0, 78, -36, 0]))
    else:
        c.move_photo(c.target([0, 0, 78, -36, 0]))
        assert abs(c.current[1] - 3123) <= 20
    corrections = [e for e in events if e["kind"] == "load_compensation" and e["motor_id"] == 2]
    assert len(corrections) == 1 and corrections[0]["offset"] == 30
    assert all(serial.torque(i) == 1 for i in range(1, 6))


def test_holding_distinguishes_static_offset_jitter_from_actual_drift():
    _, c, serial, _ = setup()
    c.enable_photo()
    target = c.target([0, 0, 72, -24, 0])
    c.move_photo(target)
    motor = serial.motors[4]
    motor.step = lambda _: None
    put(motor.t, 132, 4, target[3] - 20)
    c.move_waypoint(target)
    put(motor.t, 132, 4, target[3] - 21)
    c.hold(0.2)  # one-count noise at an already accepted static offset
    put(motor.t, 132, 4, target[3] - 41)
    with pytest.raises(RuntimeError, match="holding drift"):
        c.hold(0.2)


def test_observed_position_outside_envelope_is_not_accepted_as_a_stable_hold():
    _, c, serial, _ = setup()
    c.enable_photo()
    motor = serial.motors[2]
    motor.step = lambda _: None
    put(motor.t, 132, 4, c.plan.baseline[1] + 65)
    with pytest.raises(RuntimeError, match="Observed.*envelope"):
        c.sample()


def test_moving_wrist_keeps_the_raw_goal_that_supports_unchanged_shoulder():
    _, c, serial, _ = setup()
    c.enable_photo()
    target = c.target([0, 0, 72, -36, 0])
    c.move_photo(target)
    c.write(2, "goal", target[1] + 30)
    motor = serial.motors[2]

    def gravity_step(_amount):
        put(motor.t, 132, 4, get(motor.t, 116, 4) - 30)

    motor.step = gravity_step
    c.move_photo(c.target([0, 0, 72, -30, 0]))
    assert c.current[1] == target[1]
    assert c.read(2, ("goal_position",))["goal_position"] == target[1] + 30
