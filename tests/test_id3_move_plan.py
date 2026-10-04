"""Fixed magnitude plans must constrain targets and actual SDK packets together."""
from dataclasses import FrozenInstanceError

import pytest
from dynamixel_sdk import PacketHandler
from test_id3_motion import (
    FakeActuator,
    FakeArm,
    FakeClock,
    FakeReader,
    evidence_record,
    write_evidence,
)
from test_id3_motion_emulator import emulated_port

from arm_observer import id3_motion as motion
from arm_observer.motion_guard import MotionViolation
from arm_observer.reader import SdkReader


@pytest.mark.parametrize("degrees,counts,timeout", [(10, 114, 6.0), (30, 341, 18.0)])
def test_fixed_plan(degrees, counts, timeout):
    plan = motion.MovePlan(degrees)
    assert plan.open_counts == counts
    assert plan.follow_timeout_s == timeout
    with pytest.raises(FrozenInstanceError):
        plan.open_degrees = 30


@pytest.mark.parametrize("value", [0, 9, 20, 31, -30, 360])
def test_arbitrary_magnitudes_rejected(value):
    with pytest.raises(ValueError):
        motion.MovePlan(value)


def test_default_and_cli_selection():
    parser = motion.build_parser()
    assert motion.MovePlan().open_counts == 114
    assert parser.parse_args(["--evidence", "x"]).open_degrees == 10
    assert parser.parse_args(["--evidence", "x", "--open-degrees", "30"]).open_degrees == 30
    with pytest.raises(SystemExit):
        parser.parse_args(["--evidence", "x", "--open-degrees", "20"])


@pytest.mark.parametrize("degrees", [10, 30])
def test_sdk_plan_target_window_and_release(tmp_path, degrees):
    plan = motion.MovePlan(degrees)
    port = emulated_port()
    packet = PacketHandler(2.0)
    evidence = motion.load_evidence(write_evidence(tmp_path, evidence_record()))
    clock, events = FakeClock(), []
    outcome = motion.run_motion(SdkReader(port, packet), motion.Id3Actuator(port, packet),
                                evidence, events.append, clock.monotonic, clock.sleep, plan=plan)
    assert outcome.status == "converged" and outcome.release_problems == ()
    assert outcome.target - outcome.torque_on_counts == plan.open_counts
    assert abs(outcome.return_error_counts) <= 5
    assert port.ser.torque() == 0 and port.is_using is False
    assert {mid for mid, _, _ in port.ser.writes()} == {3}
    assert {address for _, address, _ in port.ser.writes()} <= {64, 100, 108, 112, 116}
    logged = next(e for e in events if e["kind"] == "plan")
    assert logged["open_counts"] == plan.open_counts
    assert logged["follow_timeout_s"] == plan.follow_timeout_s
    envelope = port.envelope
    assert envelope.goal_low == outcome.start_counts - 15
    assert envelope.goal_high == outcome.start_counts + plan.open_counts + 35
    sent = len(port.ser.sent)
    with pytest.raises(MotionViolation):
        packet.write4ByteTxRx(port, 3, 116, envelope.goal_high + 1)
    with pytest.raises(MotionViolation):
        packet.write4ByteTxRx(port, 2, 116, outcome.target)
    assert len(port.ser.sent) == sent and port.is_using is False


def test_thirty_degree_timeout_keeps_early_progress_guard():
    arm = FakeArm(step=0)
    arm.torque = True
    tracker = motion.Tracker(1494, 1, 1153, {1: 2052, 2: 3354, 4: 2059, 5: 2059},
                             0.0, timeout_s=motion.MovePlan(30).follow_timeout_s)
    motors = motion.healthy(FakeReader(arm).telemetry((1, 2, 3, 4, 5), "sync"))
    with pytest.raises(motion.MotionAbort, match="no progress"):
        tracker.update(motors, 1.01)


def run_fake(tmp_path, arm):
    evidence = motion.load_evidence(write_evidence(tmp_path, evidence_record()))
    clock, events = FakeClock(), []
    outcome = motion.run_motion(FakeReader(arm), FakeActuator(arm), evidence, events.append,
                                clock.monotonic, clock.sleep, plan=motion.MovePlan(30))
    return outcome, events


def test_thirty_degree_travel_can_take_more_than_six_seconds(tmp_path):
    arm = FakeArm(step=1)
    outcome, events = run_fake(tmp_path, arm)
    assert outcome.status == "converged" and outcome.torque_off_confirmed is True
    opened = [e for e in events if e["kind"] == "sample" and e["stage"] == "open"]
    assert opened[-1]["t"] - opened[0]["t"] > 6.0


@pytest.mark.parametrize("fault", ["blocked", "reverse", "other_motion", "alias"])
def test_thirty_degree_faults_preserve_guards_and_release(tmp_path, fault):
    arm = FakeArm()
    if fault == "blocked":
        arm.step = 0
    elif fault == "reverse":
        arm.sign_bias = -1
    elif fault == "other_motion":
        arm.drift = {2: 1}
    else:
        arm.registers[2]["secondary_id"] = 3
    outcome, _ = run_fake(tmp_path, arm)
    assert outcome.status in ("aborted", "refused")
    assert arm.torque is False
    assert {name for name, _ in arm.writes} <= set(motion.ID3_WRITES)
    if fault == "alias":
        assert arm.writes == []
