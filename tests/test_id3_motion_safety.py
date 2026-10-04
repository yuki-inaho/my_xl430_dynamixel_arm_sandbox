"""Regression cases from the adversarial delivery review; no hardware access."""
from dataclasses import replace

import pytest
from test_id3_motion import FakeActuator, FakeArm, FakeClock, FakeReader, run
from test_id3_motion_emulator import emulated_port
from test_id3_motion_emulator import run as run_sdk
from xl430_emulator import put

from arm_observer import id3_motion as motion


@pytest.mark.parametrize("motor_id", [1, 2, 4, 5])
def test_secondary_id_alias_refuses_before_first_write(tmp_path, motor_id):
    port = emulated_port()
    put(port.ser.motors[motor_id].t, 12, 1, 3)
    outcome = run_sdk(tmp_path, port)
    assert outcome.status == "refused"
    assert "secondary" in outcome.reason.lower()
    assert port.ser.writes() == []
    assert all(port.ser.torque(mid) == 0 for mid in range(1, 6))


@pytest.mark.parametrize("field", ["secondary_id", "model_number", "id"])
def test_missing_motor_identity_refuses_before_first_write(tmp_path, field):
    arm = FakeArm()
    del arm.registers[1][field]
    outcome, _ = run(tmp_path, arm)
    assert outcome.status == "refused"
    assert arm.writes == []


def test_follow_requires_id3_torque_on():
    arm = FakeArm()
    tracker = motion.Tracker(1267, 1, 1153, {}, 0)
    motors = {m.motor_id: m for m in arm.telemetry(range(1, 6), "sync")}
    with pytest.raises(motion.MotionAbort, match="torque"):
        tracker.update(motors, 0)


def test_hold_requires_id3_torque_on():
    arm = FakeArm()
    clock = FakeClock()
    session = motion.Session(FakeReader(arm), None,
                             motion.MotionLog(lambda event: None, clock.monotonic),
                             clock.monotonic, clock.sleep)
    with pytest.raises(motion.MotionAbort, match="torque"):
        session.hold(1153, {1: 2052, 2: 3354, 4: 2059, 5: 2059})


@pytest.mark.parametrize("stage", ["open", "hold", "return"])
def test_torque_loss_aborts_each_motion_phase_without_reenable(stage):
    arm = FakeArm()
    clock = FakeClock()

    def emit(event):
        if event.get("kind") == "sample" and event.get("stage") == stage:
            arm.torque = False

    evidence = motion.Evidence("offline", "offline", 1, 1153, "paired_observation")
    outcome = motion.run_motion(FakeReader(arm), FakeActuator(arm), evidence, emit,
                                clock.monotonic, clock.sleep)
    assert outcome.status == "aborted" and "torque" in outcome.reason
    assert outcome.torque_off_confirmed is True
    assert arm.writes.count(("torque", 1)) == 1


class ReturnShortArm(FakeArm):
    def offset(self):
        had_open = ("goal_position", 1267) in self.writes
        return 20 if had_open and self.goal == 1153 else 0


def test_return_twenty_counts_short_is_not_success(tmp_path):
    arm = ReturnShortArm()
    outcome, _ = run(tmp_path, arm)
    assert motion.exit_code(outcome) != 0
    assert outcome.status == "aborted"
    assert outcome.torque_off_confirmed is True
    assert arm.positions[3] == 1173


def test_restore_write_failure_is_not_success(tmp_path):
    arm = FakeArm()
    arm.fail_write = ("profile_velocity", 0)
    outcome, _ = run(tmp_path, arm)
    assert outcome.release_problems
    assert outcome.torque_off_confirmed is True
    assert motion.exit_code(outcome) == 4


def test_restore_write_ack_with_wrong_readback_is_not_success(tmp_path):
    arm = FakeArm()
    original = arm.registers_batch

    def altered(mid, registers):
        batch = original(mid, registers)
        restored = ("torque", 0) in arm.writes
        if mid == 3 and restored:
            readings = tuple(replace(r, value=5) if r.name == "profile_velocity" else r
                             for r in batch.readings)
            return batch._replace(readings=readings)
        return batch

    arm.registers_batch = altered
    outcome, _ = run(tmp_path, arm)
    assert any("profile_velocity" in p for p in outcome.release_problems)
    assert motion.exit_code(outcome) == 4
