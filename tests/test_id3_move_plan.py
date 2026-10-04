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


@pytest.mark.parametrize("value", [20, True])
def test_arbitrary_magnitudes_rejected(value):
    with pytest.raises(ValueError):
        motion.MovePlan(value)


def test_default_and_cli_selection():
    parser = motion.build_parser()
    assert motion.MovePlan().open_counts == 114
    assert parser.parse_args(["--evidence", "x"]).open_degrees == 10
    assert parser.parse_args(["--evidence", "x"]).execute is False
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
    outcome = motion.run_motion(
        SdkReader(port, packet),
        motion.Id3Actuator(port, packet),
        evidence,
        events.append,
        clock.monotonic,
        clock.sleep,
        plan=plan,
    )
    assert outcome.status == "converged" and outcome.release_problems == ()
    assert outcome.target - outcome.torque_on_counts == plan.open_counts
    assert abs(outcome.return_error_counts) <= 5
    assert port.ser.torque() == 0 and port.is_using is False
    assert {mid for mid, _, _ in port.ser.writes()} == {3}
    assert {address for _, address, _ in port.ser.writes()} <= {64, 100, 108, 112, 116}
    assert {frame[7] for frame in port.ser.sent} <= {0x02, 0x03, 0x82}
    first_write = next(i for i, frame in enumerate(port.ser.sent) if frame[7] == 3)
    route_reads = {
        frame[4]
        for frame in port.ser.sent[:first_write]
        if frame[7] == 2 and (frame[8] | frame[9] << 8) == 12
    }
    assert route_reads == {1, 2, 3, 4, 5}
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


def run_fake(tmp_path, arm):
    evidence = motion.load_evidence(write_evidence(tmp_path, evidence_record()))
    clock, events = FakeClock(), []
    outcome = motion.run_motion(
        FakeReader(arm),
        FakeActuator(arm),
        evidence,
        events.append,
        clock.monotonic,
        clock.sleep,
        plan=motion.MovePlan(30),
    )
    return outcome, events


def test_thirty_degree_travel_can_take_more_than_six_seconds(tmp_path):
    arm = FakeArm(step=1)
    outcome, events = run_fake(tmp_path, arm)
    assert outcome.status == "converged" and outcome.torque_off_confirmed is True
    opened = [e for e in events if e["kind"] == "sample" and e["stage"] == "open"]
    assert opened[-1]["t"] - opened[0]["t"] > 6.0


def test_thirty_degree_blocked_motion_preserves_guards_and_release(tmp_path):
    arm = FakeArm(step=0)
    outcome, _ = run_fake(tmp_path, arm)
    assert outcome.status in ("aborted", "refused")
    assert arm.torque is False
    assert {name for name, _ in arm.writes} <= set(motion.ID3_WRITES)
