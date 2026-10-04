"""Actual SDK transport checks for camera-reviewed three-joint standby."""
import pytest
from dynamixel_sdk import PacketHandler
from test_id3_motion import FakeClock
from xl430_emulator import EmuSerial, put

from arm_observer.motion_guard import MotionViolation
from arm_observer.standby_motion import Controller, Plan, StandbyPort


def setup(step=12):
    port = StandbyPort("offline-emulator")
    port.ser = EmuSerial(positions=(2064, 3128, 1156, 2058, 2059), step=step)
    port.is_open = True
    port.baudrate = 1000000
    port.tx_time_per_byte = 0.01
    clock, events = FakeClock(), []
    c = Controller(port, PacketHandler(2.0), events.append, clock.monotonic, clock.sleep)
    return c, port.ser, events


def test_sdk_staged_forward_return_release_and_restore():
    c, serial, events = setup()
    c.prepare()
    c.enable()
    for stage in ("elbow30", "elbow60", "elbow72", "wrist10", "wrist30"):
        c.move(stage)
    assert c.current == (2064, 3128, 1975, 1717, 2059)
    assert [serial.torque(i) for i in range(1, 6)] == [0, 1, 1, 1, 0]
    for stage in ("return_wrist", "return_elbow60", "return_elbow30", "return_fold"):
        c.move(stage)
    c.release_supported()
    assert all(serial.torque(i) == 0 for i in range(1, 6))
    assert {mid for mid, _, _ in serial.writes()} == {2, 3, 4}
    assert {addr for _, addr, _ in serial.writes()} <= {64, 100, 108, 112, 116}
    assert events[-1]["kind"] == "released_supported"
    for mid in (2, 3, 4):
        assert c.read(mid, ("goal_pwm",))["goal_pwm"] == 885
    first = next(i for i, f in enumerate(serial.sent) if f[7] == 3)
    assert {f[4] for f in serial.sent[:first]
            if f[7] == 2 and (f[8] | f[9] << 8) == 12} == {1, 2, 3, 4, 5}


@pytest.mark.parametrize("mid,address,size,value", [
    (1, 64, 1, 1), (5, 116, 4, 2059), (2, 7, 1, 9),
    (2, 64, 2, 1), (2, 116, 4, 3160), (3, 116, 4, 2200),
    (4, 116, 4, 1400), (4, 100, 2, 884)])
def test_sdk_refuses_wrong_id_eeprom_width_and_values(mid, address, size, value):
    c, serial, _ = setup()
    c.prepare()
    with pytest.raises(MotionViolation):
        getattr(c.packet, f"write{size}ByteTxRx")(c.port, mid, address, value)
    assert not serial.writes() and not c.port.is_using


def test_alias_other_motor_rejected_before_any_write():
    c, serial, _ = setup()
    serial.motors[5].t[12] = 2
    with pytest.raises(RuntimeError, match="alias"):
        c.prepare()
    assert not serial.writes()


def test_stage_skip_and_release_in_air_refused():
    c, _, _ = setup()
    c.prepare()
    c.enable()
    with pytest.raises(RuntimeError, match="skips"):
        c.move("elbow72")
    c.move("elbow30")
    with pytest.raises(RuntimeError, match="Return"):
        c.release_supported()


def test_blocked_motor_stops_and_holds_without_torque_off():
    c, serial, events = setup(step=0)
    c.prepare()
    c.enable()
    with pytest.raises(RuntimeError, match="no progress") as e:
        c.move("elbow30")
    c.freeze(str(e.value))
    assert all(serial.torque(i) == 1 for i in (2, 3, 4))
    assert not any(addr == 64 and value == 0 for _, addr, value in serial.writes())
    assert events[-1]["name"] == "goal"
    assert c.read(3, ("goal_position",))["goal_position"] == 1156


def test_holding_shoulder_drift_and_passive_neutral_drift_are_detected():
    c, serial, _ = setup()
    c.prepare()
    c.enable()
    put(serial.motors[2].t, 132, 4, 3080)
    with pytest.raises(RuntimeError, match="Holding"):
        c.move("elbow30")
    put(serial.motors[1].t, 132, 4, 2100)
    with pytest.raises(RuntimeError, match="Passive"):
        c.sample()


def test_interrupt_inside_sdk_read_freezes_available_motors():
    c, serial, _ = setup()
    c.prepare()
    c.enable()
    def interrupt(_serial):
        raise KeyboardInterrupt
    serial.read_hook = interrupt
    with pytest.raises(KeyboardInterrupt):
        c.sample()
    serial.read_hook = None
    c.freeze("interrupt")
    assert not c.port.is_using
    assert all(serial.torque(i) == 1 for i in (2, 3, 4))


def test_reference_bounds_are_not_factory_zero_or_unrestricted():
    with pytest.raises(ValueError):
        Plan((2048, 2048, 2048, 2048, 2048))
    c, _, _ = setup()
    with pytest.raises(MotionViolation):
        c.write(2, "torque", 1)


def test_reverse_motion_and_missing_samples_do_not_command_off():
    c, serial, _ = setup()
    c.prepare()
    c.enable()
    with pytest.raises(RuntimeError, match="reverse"):
        c.check_follow(3, 1130, 1156, 1497, 0.5)
    serial.motors.pop(5)
    with pytest.raises(RuntimeError):
        c.sample()
    c.freeze("missing ID5")
    assert all(serial.torque(i) == 1 for i in (2, 3, 4))
    assert not any(addr == 64 and value == 0 for _, addr, value in serial.writes())


def test_resume_keeps_original_baseline_and_restoration_metadata():
    c, serial, events = setup()
    c.prepare()
    c.enable()
    c.move("elbow30")
    c.freeze("review pause")
    prior = next(e for e in events if e["kind"] == "plan")
    resumed = Controller(c.port, c.packet, events.append, c.clock, c.sleep)
    resumed.prepare(prior)
    assert resumed.plan.baseline == (2064, 3128, 1156, 2058, 2059)
    assert resumed.saved[3]["goal_pwm"] == 885
    resumed.move("return_fold")
    resumed.release_supported()
    assert all(serial.torque(i) == 0 for i in range(1, 6))


def test_compensation_is_once_bounded_and_does_not_accept_large_fault():
    c, serial, _ = setup()
    c.prepare()
    c.enable()
    corrected = set()
    target = (2064, 3128, 1838, 2058, 2059)
    measured = (2064, 3128, 1802, 2058, 2059)
    c.compensate([measured] * 5, target, corrected)
    assert c.read(3, ("goal_position",))["goal_position"] == 1868
    before = len(serial.writes())
    c.compensate([measured] * 5, target, corrected)
    assert len(serial.writes()) == before
    c.compensate([(2064, 3128, 1700, 2058, 2059)] * 5, target, set())
    assert len(serial.writes()) == before


def test_resume_rejects_changed_settings():
    c, serial, events = setup()
    c.prepare()
    c.enable()
    prior = next(e for e in events if e["kind"] == "plan")
    serial.motors[2].t[10] = 1
    resumed = Controller(c.port, c.packet, events.append, c.clock, c.sleep)
    with pytest.raises(RuntimeError):
        resumed.prepare(prior)


def test_signal_during_move_is_checked_on_next_sample_without_off():
    c, serial, _ = setup()
    c.prepare()
    c.enable()
    c.stop_requested = lambda: True
    with pytest.raises(RuntimeError, match="Stop requested"):
        c.move("elbow30")
    c.freeze("signal")
    assert all(serial.torque(i) == 1 for i in (2, 3, 4))


def test_broken_log_does_not_prevent_freeze_all_three_goals():
    c, serial, _ = setup()
    c.prepare()
    c.enable()
    def broken(_event):
        raise OSError("disk full")
    c.emit = broken
    before = len(serial.writes())
    c.freeze("logging failed")
    assert [(mid, addr) for mid, addr, _ in serial.writes()[before:]] == [
        (2, 116), (3, 116), (4, 116)]
    assert all(serial.torque(i) == 1 for i in (2, 3, 4))
