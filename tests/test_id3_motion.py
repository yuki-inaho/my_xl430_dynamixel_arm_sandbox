"""Offline tests for the bounded ID3 opening. No serial device is opened."""
from __future__ import annotations

import hashlib
import json
import os
import signal
from dataclasses import replace
from pathlib import Path

import pytest
from dynamixel_sdk import COMM_SUCCESS, COMM_TX_FAIL, PacketHandler
from test_readonly import RecordingSerial, instruction

from arm_observer import id3_motion as motion
from arm_observer.bus import ReadOnlyViolation
from arm_observer.models import Fault, Identity, MotorTelemetry, RegisterBatch, RegisterValue
from arm_observer.motion_guard import MotionPort, MotionViolation, WriteEnvelope
from arm_observer.registers import BY_NAME

ENVELOPE = WriteEnvelope(
    motor_id=3, goal_low=1113, goal_high=1307,
    profile_acceleration=frozenset({0, 1}), profile_velocity=frozenset({0, 5}),
    goal_pwm=frozenset({350, 885}),
)


def write_packet(motor_id, address, value, size):
    payload = [address & 255, address >> 8, *value.to_bytes(size, "little", signed=value < 0)]
    return instruction(3, payload, motor_id)


def motion_port(envelope=ENVELOPE):
    port = MotionPort("offline-test")
    port.ser = RecordingSerial()
    port.envelope = envelope
    return port


# --- outbound guard ---------------------------------------------------------


@pytest.mark.parametrize(
    "address,value,size",
    [(64, 1, 1), (64, 0, 1), (108, 1, 4), (112, 5, 4), (100, 350, 2), (116, 1153, 4),
     (116, 1267, 4), (108, 0, 4), (112, 0, 4), (100, 885, 2)],
)
def test_listed_id3_ram_writes_reach_serial(address, value, size):
    port = motion_port()
    port.writePort(write_packet(3, address, value, size))
    assert len(port.ser.sent) == 1


@pytest.mark.parametrize(
    "motor_id,address,value,size",
    [
        (2, 64, 1, 1),        # another motor
        (254, 64, 1, 1),      # broadcast
        (3, 64, 2, 1),        # torque value
        (3, 116, 1308, 4),    # goal above window
        (3, 116, 1112, 4),    # goal below window
        (3, 112, 0x7FFF, 4),  # unlisted profile velocity
        (3, 108, 3, 4),       # unlisted profile acceleration
        (3, 100, 885 - 1, 2), # unlisted goal PWM
        (3, 11, 4, 1),        # operating mode (EEPROM)
        (3, 10, 1, 1),        # drive mode
        (3, 20, 0, 4),        # homing offset
        (3, 7, 9, 1),         # ID
        (3, 8, 1, 1),         # baud rate
        (3, 48, 4095, 4),     # position limit
        (3, 65, 1, 1),        # LED
        (3, 104, 10, 4),      # goal velocity
        (3, 116, 1153, 2),    # wrong width for goal position
        (3, 64, 1, 4),        # wrong width for torque
    ],
)
def test_unlisted_writes_never_reach_serial(motor_id, address, value, size):
    port = motion_port()
    with pytest.raises((MotionViolation, ReadOnlyViolation)):
        port.writePort(write_packet(motor_id, address, value, size))
    assert port.ser.sent == []


@pytest.mark.parametrize("opcode", [4, 5, 6, 8, 0x10, 0x20, 0x83, 0x92, 0x93])
def test_other_mutating_instructions_are_blocked(opcode):
    port = motion_port()
    with pytest.raises((MotionViolation, ReadOnlyViolation)):
        port.writePort(instruction(opcode, [64, 0, 1], 3))
    assert port.ser.sent == []


def test_without_envelope_only_reads_pass():
    port = motion_port(None)
    with pytest.raises(MotionViolation):
        port.writePort(write_packet(3, 64, 1, 1))
    port.writePort(instruction(2, [132, 0, 4, 0], 3))
    port.writePort(instruction(1, (), 3))
    assert [frame[7] for frame in port.ser.sent] == [2, 1]


def test_malformed_write_length_is_blocked():
    port = motion_port()
    packet = write_packet(3, 116, 1153, 4)
    packet[5] += 1
    with pytest.raises((MotionViolation, ReadOnlyViolation)):
        port.writePort(packet)
    assert port.ser.sent == []


def test_real_sdk_write_packets_pass_only_inside_the_envelope(monkeypatch):
    port = motion_port()
    monkeypatch.setattr(port, "clearPort", lambda: None)
    monkeypatch.setattr(port, "setPacketTimeout", lambda length: None)
    packet = PacketHandler(2.0)

    def receive_timeout(port, *args):
        port.is_using = False
        return [], -3001

    monkeypatch.setattr(packet, "rxPacket", receive_timeout)
    packet.write4ByteTxRx(port, 3, 116, 1267)
    packet.write1ByteTxRx(port, 3, 64, 1)
    packet.write2ByteTxRx(port, 3, 100, 350)
    assert [frame[7] for frame in port.ser.sent] == [3, 3, 3]
    with pytest.raises(MotionViolation):
        packet.write4ByteTxRx(port, 3, 116, 2000)
    with pytest.raises(MotionViolation):
        packet.write1ByteTxRx(port, 2, 64, 1)
    assert len(port.ser.sent) == 3
    # A refused packet must not leave the SDK port busy: Torque OFF still goes out.
    packet.write1ByteTxRx(port, 3, 64, 0)
    assert len(port.ser.sent) == 4 and port.ser.sent[-1][8:11] == bytes([64, 0, 0])


def test_envelope_rejects_inverted_or_out_of_range_window():
    with pytest.raises(ValueError):
        WriteEnvelope(3, 1300, 1200, frozenset({0}), frozenset({0}), frozenset({885}))
    with pytest.raises(ValueError):
        WriteEnvelope(3, -1, 100, frozenset({0}), frozenset({0}), frozenset({885}))
    with pytest.raises(ValueError):
        WriteEnvelope(3, 4000, 4096, frozenset({0}), frozenset({0}), frozenset({885}))


# --- direction evidence -------------------------------------------------------


def evidence_record(**changes):
    sample = {"motor_id": 3, "position_counts": 1153, "finished_at": "t", "sequence": 1,
              "mode": 3, "session_id": "s", "context_fingerprint": "f", "simulated": False,
              "physical_confirmed": True}
    record = {"before": sample, "after": {**sample, "position_counts": 1267, "sequence": 9},
              "delta_counts": 114, "degrees_signed": 10.01953125, "opening_count_sign": 1,
              "physical_change_confirmed": True, "physical_change_reported": "opening",
              "scope_note": "x"}
    if type(changes.get("delta_counts")) is int:
        record["after"]["position_counts"] = (1153 + changes["delta_counts"]) % 4096
    for key, value in changes.items():
        if key in ("simulated", "motor_id"):
            record["before"][key] = value
            record["after"][key] = value
        else:
            record[key] = value
    return record


def write_evidence(tmp_path, record):
    path = tmp_path / "observation.json"
    path.write_text(json.dumps(record))
    return path


@pytest.mark.parametrize("sign,delta", [(1, 114), (-1, -60)])
def test_hardware_evidence_gives_sign_and_folded_count(tmp_path, sign, delta):
    path = write_evidence(tmp_path, evidence_record(opening_count_sign=sign, delta_counts=delta))
    evidence = motion.load_evidence(path)
    assert evidence.sign == sign
    assert evidence.folded_count == 1153
    assert evidence.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "changes",
    [
        {"simulated": True},
        {"motor_id": 2},
        {"physical_change_confirmed": False},
        {"physical_change_reported": "closing"},
        {"delta_counts": 5, "opening_count_sign": 1},
        {"delta_counts": 1500, "opening_count_sign": 1},
        {"delta_counts": 114, "opening_count_sign": -1},
        {"opening_count_sign": 0},
        {"opening_count_sign": True},
    ],
)
def test_unusable_evidence_is_rejected(tmp_path, changes):
    with pytest.raises(ValueError):
        motion.load_evidence(write_evidence(tmp_path, evidence_record(**changes)))


# --- fake motor bus -----------------------------------------------------------

FULL = {
    "model_number": 1060, "firmware_version": 42, "id": 3, "baud_rate": 3, "protocol_type": 2,
    "operating_mode": 3, "drive_mode": 0, "homing_offset": 0, "min_position_limit": 0,
    "max_position_limit": 4095, "goal_pwm": 885, "profile_velocity": 0,
    "profile_acceleration": 0, "torque_enable": 0, "hardware_error_status": 0,
    "status_return_level": 2, "secondary_id": 255,
}


class FakeArm:
    """Five motors; ID3 follows its goal by `step` counts per telemetry read when torque is on."""

    def __init__(self, positions=(2052, 3354, 1153, 2059, 2059), step=12, sign_bias=1):
        self.positions = dict(zip(range(1, 6), positions))
        self.registers = {mid: dict(FULL, id=mid) for mid in range(1, 6)}
        self.goal = self.positions[3]
        self.torque = False
        self.step = step
        self.writes = []
        self.reads = 0
        self.fail_write = None
        self.drift = {}
        self.error_after = None
        self.busy = False
        self.torque_write_fails = False
        self.rebase = 0
        self.settle_offset = 0
        self.open_shortfall = 0
        self.drop_reads = set()
        self.sync_torque_lie = False
        self.hard_stop_high = None
        self.profile_left = 0
        self.sign_bias = sign_bias

    def offset(self):
        # Gravity-like shortfall only while holding the opened target.
        opened = abs(self.goal - 1153) > 50
        return self.settle_offset + (self.open_shortfall if opened else 0)

    # Reader protocol
    def identity(self, motor_id):
        regs = self.registers[motor_id]
        return Identity(motor_id, regs["model_number"], regs["firmware_version"], "t", 0)

    def registers_batch(self, motor_id, registers):
        regs = dict(self.registers[motor_id], present_position=self.positions[motor_id])
        if motor_id == 3:
            regs["torque_enable"] = int(self.torque)
        values = tuple(
            RegisterValue(r.name, r.address, r.size, r.memory, regs[r.name], regs[r.name], False)
            for r in registers if r.name in regs
        )
        return RegisterBatch(values, ())

    def telemetry(self, ids, mode):
        self.reads += 1
        ongoing = self.profile_left > 0
        self.profile_left = max(0, self.profile_left - 1)
        if self.torque:
            delta = self.goal + self.offset() - self.positions[3]
            move = max(-self.step, min(self.step, delta)) * self.sign_bias
            self.positions[3] += move
            if self.hard_stop_high is not None:
                self.positions[3] = min(self.positions[3], self.hard_stop_high)
        for mid, amount in self.drift.items():
            self.positions[mid] += amount
        error = 4 if self.error_after is not None and self.reads > self.error_after else 0
        if self.reads in self.drop_reads:  # SYNC_READ block lost: values unknown, comm fault
            fault = Fault(3, "sync_read", -3001, 0, "There is no status packet!")
            return tuple(MotorTelemetry(mid, None, None, self.positions[mid], 0, 0, 0, 91, 35,
                                        False, 0, 100, False, (replace(fault, motor_id=mid),))
                         for mid in ids)
        lying = self.sync_torque_lie and self.writes and not self.torque
        id3_torque = True if lying else self.torque
        return tuple(
            MotorTelemetry(mid, id3_torque if mid == 3 else False, error if mid == 3 else 0,
                           self.positions[mid], 0, 0, 0, 91, 35, False,
                           # a trajectory ends after its duration, even when the joint is blocked
                           2 if mid == 3 and self.torque and ongoing else 0,
                           100, False, ())
            for mid in ids
        )


class FakeReader:
    def __init__(self, arm):
        self.arm = arm

    def identity(self, motor_id):
        return self.arm.identity(motor_id)

    def registers(self, motor_id, registers):
        return self.arm.registers_batch(motor_id, registers)

    def telemetry(self, ids, mode):
        return self.arm.telemetry(ids, mode)


class FakeActuator:
    def __init__(self, arm):
        self.arm = arm
        self.envelopes = []

    def set_envelope(self, envelope):
        self.envelopes.append(envelope)

    def recover(self):
        self.arm.busy = False

    def write(self, name, value, allow_alert=False):
        if self.arm.busy:
            raise motion.MotionAbort("Port is in use!")
        if self.arm.fail_write == (name, value):
            raise motion.MotionAbort(f"write failed: {name}")
        if name == "torque" and value == 0 and self.arm.torque_write_fails:
            raise motion.MotionAbort("torque write failed")
        self.arm.writes.append((name, value))
        if name == "torque":
            self.arm.torque = bool(value)
            if value:
                self.arm.positions[3] += self.arm.rebase
        elif name == "goal_position":
            distance = abs(value - self.arm.positions[3])
            self.arm.profile_left = -(-distance // self.arm.step) if self.arm.step else 36
            self.arm.goal = value
        else:
            self.arm.registers[3][name] = value


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def run(tmp_path, arm, record=None):
    evidence = motion.load_evidence(write_evidence(tmp_path, record or evidence_record()))
    clock = FakeClock()
    events = []
    outcome = motion.run_motion(
        FakeReader(arm), FakeActuator(arm), evidence, events.append, clock.monotonic, clock.sleep
    )
    return outcome, events


def written(arm):
    return arm.writes


# --- full sequence ------------------------------------------------------------


def test_successful_opening_reaches_converges_returns_and_restores(tmp_path):
    arm = FakeArm()
    outcome, events = run(tmp_path, arm)
    assert outcome.status == "converged"
    assert outcome.target == 1153 + 114
    assert outcome.final_error_counts == 0
    assert written(arm) == [
        ("profile_acceleration", 1), ("profile_velocity", 5), ("goal_pwm", 350),
        ("goal_position", 1153), ("torque", 1), ("goal_position", 1267),
        ("goal_position", 1153), ("torque", 0), ("goal_position", 1153), ("goal_pwm", 885),
        ("profile_velocity", 0), ("profile_acceleration", 0),
    ]
    assert arm.torque is False
    assert outcome.torque_off_confirmed is True and outcome.release_problems == ()
    assert motion.exit_code(outcome) == 0
    kinds = [event["kind"] for event in events]
    assert kinds[0] == "plan" and kinds[-1] == "outcome"
    assert any(event["kind"] == "converged" and event["stage"] == "open" for event in events)


def test_negative_opening_sign_moves_down(tmp_path):
    arm = FakeArm()
    outcome, _ = run(tmp_path, arm, evidence_record(opening_count_sign=-1, delta_counts=-114))
    assert outcome.status == "converged"
    assert ("goal_position", 1153 - 114) in written(arm)


def test_target_is_computed_from_the_count_read_after_torque_on(tmp_path):
    arm = FakeArm()
    arm.settle_offset = 4  # holds 4 counts off its goal under load
    outcome, _ = run(tmp_path, arm)
    assert outcome.status == "converged"
    assert outcome.torque_on_counts == 1157
    assert outcome.target == 1157 + 114
    assert ("goal_position", 1157) in written(arm)  # return goes to the torque-on count


@pytest.mark.parametrize(
    "mutate,reason",
    [
        (lambda arm: arm.registers[3].update(operating_mode=4), "operating_mode"),
        (lambda arm: arm.registers[3].update(drive_mode=1), "drive_mode"),
        (lambda arm: arm.registers[3].update(homing_offset=5), "homing_offset"),
        (lambda arm: arm.registers[3].update(max_position_limit=1200), "limit"),
        (lambda arm: arm.registers[3].update(model_number=1190), "model"),
        (lambda arm: arm.positions.update({3: 1200}), "folded"),
    (lambda arm: arm.registers[3].update(status_return_level=1), "status_return_level"),
    ],
)
def test_preconditions_block_all_writes(tmp_path, mutate, reason):
    arm = FakeArm()
    mutate(arm)
    outcome, _ = run(tmp_path, arm)
    assert outcome.status == "refused"
    assert reason in outcome.reason
    assert written(arm) == []


def test_torque_already_on_blocks_all_writes(tmp_path):
    arm = FakeArm()
    arm.torque = True
    outcome, _ = run(tmp_path, arm)
    assert outcome.status == "refused"
    assert written(arm) == []


def test_jump_at_torque_on_aborts_with_torque_off(tmp_path):
    arm = FakeArm()
    arm.rebase = 40
    outcome, _ = run(tmp_path, arm)
    assert outcome.status == "aborted"
    assert "jump" in outcome.reason
    assert ("goal_position", 1153 + 40 + 114) not in written(arm)
    names = [name for name, _ in written(arm)]
    assert names[-5:] == ["torque", "goal_position", "goal_pwm", "profile_velocity",
                          "profile_acceleration"]
    assert written(arm)[-5] == ("torque", 0)
    assert outcome.torque_off_confirmed is True


def test_wrong_direction_aborts(tmp_path):
    arm = FakeArm(sign_bias=-1)
    outcome, _ = run(tmp_path, arm)
    assert outcome.status == "aborted"
    assert "against" in outcome.reason
    assert arm.torque is False


def test_stall_against_a_stop_aborts_early(tmp_path):
    arm = FakeArm(step=0)  # e.g. pushing into the fold stop: no progress at all
    outcome, events = run(tmp_path, arm)
    assert outcome.status == "aborted"
    assert "no progress" in outcome.reason
    assert arm.torque is False
    abort = next(e for e in events if e["kind"] == "abort")
    write = next(e for e in events if e["kind"] == "write" and e["value"] == 1267)
    assert abort["t"] - write["t"] <= motion.EARLY_PROGRESS_S + 0.2


def test_slow_follower_still_times_out(tmp_path):
    arm = FakeArm(step=1)  # 20 counts/s at 20 Hz: passes early progress, cannot settle in time
    outcome, _ = run(tmp_path, arm)
    assert outcome.status == "aborted"
    assert "timeout" in outcome.reason
    assert arm.torque is False


@pytest.mark.parametrize("shortfall", [-12, -19, -24])
def test_gravity_shortfall_is_corrected_by_moving_the_goal(tmp_path, shortfall):
    arm = FakeArm()
    arm.open_shortfall = shortfall  # P-only position control sags under the forearm load
    outcome, events = run(tmp_path, arm)
    assert outcome.status == "converged"
    assert outcome.final_error_counts == 0
    assert outcome.correction_counts == -shortfall
    assert ("goal_position", 1267 - shortfall) in written(arm)
    assert ("goal_position", 1153) in written(arm)  # still returns slowly before torque off
    assert any(e["kind"] == "converged" and e["stage"] == "correct" for e in events)


def test_correction_is_capped_and_reports_off_target(tmp_path):
    arm = FakeArm()
    arm.hard_stop_high = 1250  # something blocks the joint below the target
    outcome, _ = run(tmp_path, arm)
    assert outcome.status == "settled_off_target"
    assert outcome.final_error_counts == -17
    assert 0 < outcome.correction_counts <= motion.MAX_CORRECTION_COUNTS
    goals = [value for name, value in written(arm) if name == "goal_position"]
    assert max(goals) <= 1267 + motion.MAX_CORRECTION_COUNTS
    assert outcome.torque_off_confirmed is True
    assert motion.exit_code(outcome) == 2


def test_settling_far_from_target_aborts(tmp_path):
    arm = FakeArm()
    arm.open_shortfall = -40
    outcome, _ = run(tmp_path, arm)
    assert outcome.status == "aborted"
    assert "far" in outcome.reason


def test_other_motor_motion_aborts(tmp_path):
    arm = FakeArm()
    arm.drift = {2: 3}
    outcome, _ = run(tmp_path, arm)
    assert outcome.status == "aborted"
    assert "ID2" in outcome.reason
    assert arm.torque is False


def test_hardware_error_aborts(tmp_path):
    arm = FakeArm()
    arm.error_after = 12
    outcome, _ = run(tmp_path, arm)
    assert outcome.status == "aborted"
    assert "hardware" in outcome.reason
    assert arm.torque is False


def test_failed_goal_write_turns_torque_off(tmp_path):
    arm = FakeArm()
    arm.fail_write = ("goal_position", 1267)
    outcome, _ = run(tmp_path, arm)
    assert outcome.status == "aborted"
    assert ("torque", 0) in written(arm)
    assert arm.torque is False


@pytest.mark.parametrize("error", [KeyboardInterrupt, OSError])
def test_interrupt_or_read_error_mid_transaction_still_turns_torque_off(tmp_path, error):
    arm = FakeArm()
    original = arm.telemetry
    calls = {"n": 0}

    def interrupted(ids, mode):
        calls["n"] += 1
        if calls["n"] == 15:
            arm.busy = True  # the SDK leaves the port marked busy mid-transaction
            raise error("serial read interrupted")
        return original(ids, mode)

    arm.telemetry = interrupted
    outcome, events = run(tmp_path, arm)
    assert outcome.status == "aborted"
    assert outcome.interrupted is (error is KeyboardInterrupt)
    assert ("torque", 0) in written(arm)
    assert arm.torque is False
    assert outcome.torque_off_confirmed is True
    assert events[-1]["kind"] == "outcome"


def test_goal_window_matches_plan(tmp_path):
    arm = FakeArm()
    evidence = motion.load_evidence(write_evidence(tmp_path, evidence_record()))
    actuator = FakeActuator(arm)
    clock = FakeClock()
    motion.run_motion(FakeReader(arm), actuator, evidence, lambda e: None, clock.monotonic,
                      clock.sleep)
    (envelope,) = actuator.envelopes
    assert envelope.motor_id == 3
    assert envelope.goal_low <= 1153 - motion.JUMP_TOLERANCE
    assert envelope.goal_high >= 1153 + 114 + motion.JUMP_TOLERANCE
    assert envelope.goal_high - envelope.goal_low <= 114 + 2 * 40
    assert envelope.goal_low == 1153 - motion.FOLD_SIDE_MARGIN
    assert envelope.goal_high == 1153 + 114 + motion.MAX_CORRECTION_COUNTS + 5


# --- actuator status handling -------------------------------------------------


class StatusPacket:
    def __init__(self, result=COMM_SUCCESS, error=0):
        self.result, self.error, self.calls = result, error, []

    def write1ByteTxRx(self, port, motor_id, address, value):
        self.calls.append((motor_id, address, value))
        return self.result, self.error

    write2ByteTxRx = write4ByteTxRx = write1ByteTxRx

    def getTxRxResult(self, result):
        return "tx failed"

    def getRxPacketError(self, error):
        return "device error"


@pytest.mark.parametrize(
    "result,error", [(COMM_TX_FAIL, 0), (COMM_SUCCESS, 1), (COMM_SUCCESS, 0x80)]
)
def test_actuator_rejects_failed_or_alerted_writes(result, error):
    actuator = motion.Id3Actuator(object(), StatusPacket(result, error))
    with pytest.raises(motion.MotionAbort):
        actuator.write("torque", 1)


def test_actuator_writes_only_named_id3_registers():
    packet = StatusPacket()
    actuator = motion.Id3Actuator(object(), packet)
    actuator.write("goal_position", 1267)
    actuator.write("profile_velocity", 5)
    assert packet.calls == [(3, 116, 1267), (3, 112, 5)]
    with pytest.raises(KeyError):
        actuator.write("operating_mode", 4)


def test_observer_guard_is_unchanged():
    from arm_observer.bus import READABLE_RANGES, SYNC_RANGES, validate_packet
    assert SYNC_RANGES == frozenset({(64, 7), (120, 27)})
    assert (116, 4) in READABLE_RANGES
    with pytest.raises(ReadOnlyViolation):
        validate_packet(write_packet(3, 64, 1, 1))


def test_cli_defaults_to_dry_run():
    args = motion.build_parser().parse_args(["--evidence", "x.json"])
    assert args.execute is False


def test_entry_point_is_installed():
    from importlib.metadata import distribution
    entry = next(e for e in distribution("my-dynamixel-arm-sandbox").entry_points
                 if e.name == "arm-id3-open")
    assert entry.value == "arm_observer.id3_motion:main"


def test_register_table_matches_actuator_map():
    for name, (address, size) in motion.ID3_WRITES.items():
        register = BY_NAME[name if name != "torque" else "torque_enable"]
        assert (register.address, register.size) == (address, size)


def test_guard_refusal_becomes_an_abort_so_release_continues():
    class RefusingPacket(StatusPacket):
        def write4ByteTxRx(self, port, motor_id, address, value):
            from arm_observer.motion_guard import MotionViolation
            raise MotionViolation("outside envelope")

    actuator = motion.Id3Actuator(object(), RefusingPacket())
    with pytest.raises(motion.MotionAbort):
        actuator.write("goal_position", 4000)


def test_logging_failure_still_sends_torque_off(tmp_path):
    arm = FakeArm()
    evidence = motion.load_evidence(write_evidence(tmp_path, evidence_record()))
    clock = FakeClock()
    count = {"n": 0}

    def failing_emit(event):
        count["n"] += 1
        if count["n"] > 30:
            raise OSError(28, "No space left on device")

    outcome = motion.run_motion(FakeReader(arm), FakeActuator(arm), evidence, failing_emit,
                                clock.monotonic, clock.sleep)
    assert outcome.status == "aborted"
    assert "No space left" in outcome.reason
    assert ("torque", 0) in written(arm)
    assert arm.torque is False
    assert outcome.torque_off_confirmed is True


def test_unconfirmed_torque_off_skips_restores_and_is_reported(tmp_path):
    arm = FakeArm()
    arm.torque_write_fails = True
    arm.fail_write = ("goal_position", 1267)
    outcome, events = run(tmp_path, arm)
    assert outcome.status == "aborted"
    assert outcome.torque_off_confirmed is False
    assert outcome.release_problems
    names = [name for name, _ in written(arm)]
    assert "goal_pwm" in names[:3]  # only the initial limit write, never the restore
    assert names.count("goal_pwm") == 1 and names.count("profile_velocity") == 1
    assert motion.exit_code(outcome) == 3


def test_release_parks_goal_at_present_after_abort(tmp_path):
    arm = FakeArm(sign_bias=-1)
    outcome, _ = run(tmp_path, arm)
    assert outcome.status == "aborted"
    torque_off = written(arm).index(("torque", 0))
    parked = written(arm)[torque_off + 1]
    assert parked == ("goal_position", arm.positions[3])


def test_alert_only_status_is_accepted_only_for_release_writes():
    packet = StatusPacket(COMM_SUCCESS, 0x80)
    actuator = motion.Id3Actuator(object(), packet)
    actuator.write("torque", 0, allow_alert=True)
    with pytest.raises(motion.MotionAbort):
        actuator.write("torque", 1)
    with pytest.raises(motion.MotionAbort):
        motion.Id3Actuator(object(), StatusPacket(COMM_SUCCESS, 0x81)).write(
            "torque", 0, allow_alert=True)


def test_recover_clears_sdk_busy_state():
    class Port:
        is_using = True
        cleared = False

        def clearPort(self):
            self.cleared = True

    port = Port()
    motion.Id3Actuator(port, StatusPacket()).recover()
    assert port.is_using is False and port.cleared is True


def test_exit_codes_separate_success_abort_interrupt_and_unconfirmed_release():
    assert motion.exit_code(motion.Outcome("converged", "", torque_off_confirmed=True)) == 0
    assert motion.exit_code(motion.Outcome("refused", "x")) == 2
    assert motion.exit_code(motion.Outcome("aborted", "x", torque_off_confirmed=True)) == 2
    assert motion.exit_code(motion.Outcome("aborted", "x", torque_off_confirmed=True,
                                           interrupted=True)) == 130
    assert motion.exit_code(motion.Outcome("converged", "", torque_off_confirmed=False)) == 3


@pytest.mark.parametrize("mutate", [
    lambda r: r["after"].update(position_counts=1040),        # recorded delta disagrees (-113)
    lambda r: r["after"].update(session_id="other"),
    lambda r: r["after"].update(context_fingerprint="other"),
    lambda r: r["before"].update(position_counts=1153.0),
    lambda r: r["after"].update(position_counts=None),
])
def test_evidence_must_be_internally_consistent(tmp_path, mutate):
    record = evidence_record()
    mutate(record)
    with pytest.raises(ValueError):
        motion.load_evidence(write_evidence(tmp_path, record))


def test_evidence_delta_is_recomputed_across_the_wrap(tmp_path):
    record = evidence_record(delta_counts=36)
    record["before"]["position_counts"], record["after"]["position_counts"] = 4090, 30
    assert motion.load_evidence(write_evidence(tmp_path, record)).sign == 1


def test_alerted_metadata_read_refuses(tmp_path):
    arm = FakeArm()
    original = arm.registers_batch

    def alerted(motor_id, registers):
        batch = original(motor_id, registers)
        return RegisterBatch(tuple(r.__class__(r.name, r.address, r.size, r.memory, r.raw,
                                               r.value, True) for r in batch.readings), ())

    arm.registers_batch = alerted
    outcome, _ = run(tmp_path, arm)
    assert outcome.status == "refused" and "alert" in outcome.reason
    assert written(arm) == []


def test_release_records_final_torque_of_all_motors(tmp_path):
    arm = FakeArm()
    _, events = run(tmp_path, arm)
    released = next(e for e in events if e["kind"] == "released")
    assert released["final_torque"] == {"1": False, "2": False, "3": False, "4": False,
                                        "5": False}


def test_stage_rates_are_logged(tmp_path):
    _, events = run(tmp_path, FakeArm())
    opened = next(e for e in events if e["kind"] == "converged" and e["stage"] == "open")
    assert opened["samples"] >= motion.STABLE_SAMPLES and opened["achieved_hz"] > 0


def test_termination_signals_become_interrupts():
    import os
    import signal
    before = signal.getsignal(signal.SIGTERM)
    with pytest.raises(KeyboardInterrupt):
        with motion.termination_as_interrupt():
            os.kill(os.getpid(), signal.SIGTERM)
    assert signal.getsignal(signal.SIGTERM) is before


def test_summary_json_is_written_next_to_the_log(tmp_path):
    outcome = motion.Outcome("converged", "", target=1267, final_error_counts=0,
                             start_counts=1153, torque_on_counts=1153, sign=1,
                             torque_off_confirmed=True)
    path = motion.write_summary(tmp_path / "id3_motion_x.jsonl", outcome)
    data = json.loads(path.read_text())
    assert data["status"] == "converged" and data["torque_off_confirmed"] is True
    assert path.name == "id3_motion_x.summary.json"


def cad_record(tmp_path, **changes):
    from test_id3_direction import direction_record
    record = direction_record(tmp_path)
    record.update(changes)
    return record


def test_cad_derivation_evidence_is_accepted(tmp_path):
    evidence = motion.load_evidence(write_evidence(tmp_path, cad_record(tmp_path)))
    assert (evidence.kind, evidence.sign, evidence.folded_count) == ("cad_derivation", 1, 1153)
    outcome, _ = run(tmp_path, FakeArm(), cad_record(tmp_path))
    assert outcome.status == "converged"


@pytest.mark.parametrize("changes", [
    {"motor_id": 2}, {"opening_count_sign": 0}, {"opening_count_sign": True},
    {"folded_count": 1153.0}, {"sources": {}}, {"derivation": {"opening_count_sign": -1}},
    {"folded_read": {"frames": 0, "folded_count": 1153}},
    {"folded_read": {"frames": 200, "folded_count": 1100}},
    {"kind": "guess"},
    {"sources": {"/nonexistent/manifest.json": "b" * 64}},
    {"sources": ["not-a-hash"]},
])
def test_bad_cad_derivation_is_rejected(tmp_path, changes):
    with pytest.raises(ValueError):
        motion.load_evidence(write_evidence(tmp_path, cad_record(tmp_path, **changes)))


def test_cad_source_hash_mismatch_is_rejected(tmp_path):
    record = cad_record(tmp_path)
    first = next(iter(record["sources"]))
    Path(first).write_text("changed")
    with pytest.raises(ValueError):
        motion.load_evidence(write_evidence(tmp_path, record))


def test_supervision_runs_at_the_sample_period(tmp_path):
    arm = FakeArm()
    evidence = motion.load_evidence(write_evidence(tmp_path, evidence_record()))
    clock = FakeClock()
    reader = FakeReader(arm)
    original = reader.telemetry

    def slow_telemetry(ids, mode):
        clock.now += 0.01  # a 10 ms transaction
        return original(ids, mode)

    reader.telemetry = slow_telemetry
    events = []
    motion.run_motion(reader, FakeActuator(arm), evidence, events.append, clock.monotonic,
                      clock.sleep)
    opened = next(e for e in events if e["kind"] == "converged" and e["stage"] == "open")
    assert 18.0 <= opened["achieved_hz"] <= 21.0


@pytest.mark.parametrize("raw", [b"[]", b"null", b'"x"', b'{"before": "x", "after": [],'
                                 b' "opening_count_sign": 1, "delta_counts": 114}'])
def test_non_object_evidence_is_a_value_error(tmp_path, raw):
    path = tmp_path / "bad.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        motion.load_evidence(path)


@pytest.mark.parametrize("mutate", [
    lambda r: r["after"].update(sequence=0),
    lambda r: (r["before"].update(mode=4), r["after"].update(mode=4)),
])
def test_paired_evidence_needs_newer_sample_and_mode3(tmp_path, mutate):
    record = evidence_record()
    mutate(record)
    with pytest.raises(ValueError):
        motion.load_evidence(write_evidence(tmp_path, record))


def test_isolated_missed_samples_are_retried_and_logged(tmp_path):
    arm = FakeArm()
    arm.drop_reads = {12, 25, 26, 40}
    outcome, events = run(tmp_path, arm)
    assert outcome.status == "converged"
    assert sum(1 for e in events if e["kind"] == "missed_sample") == 4


def test_consecutive_missed_samples_abort_as_communication_loss(tmp_path):
    arm = FakeArm()
    arm.drop_reads = set(range(15, 15 + motion.MAX_CONSECUTIVE_MISSES + 1))
    outcome, _ = run(tmp_path, arm)
    assert outcome.status == "aborted"
    assert "communication" in outcome.reason
    assert outcome.torque_off_confirmed is True


def test_hardware_error_is_not_retried(tmp_path):
    arm = FakeArm()
    arm.error_after = 12
    outcome, events = run(tmp_path, arm)
    assert outcome.status == "aborted" and "hardware" in outcome.reason
    assert not any(e["kind"] == "missed_sample" for e in events)


def test_stop_request_mid_run_aborts_through_release(tmp_path):
    arm = FakeArm()
    evidence = motion.load_evidence(write_evidence(tmp_path, evidence_record()))
    clock = FakeClock()
    outcome = motion.run_motion(FakeReader(arm), FakeActuator(arm), evidence, lambda e: None,
                                clock.monotonic, clock.sleep, lambda: arm.reads >= 15)
    assert outcome.status == "aborted" and outcome.interrupted is True
    assert outcome.torque_off_confirmed is True and arm.torque is False


def test_deferred_signals_only_record_and_restore_handlers():
    before = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    with motion.deferred_signals() as flag:
        os.kill(os.getpid(), signal.SIGTERM)
        os.kill(os.getpid(), signal.SIGINT)
        assert flag.signal == signal.SIGTERM and flag.requested()
    assert {sig: signal.getsignal(sig) for sig in before} == before


def test_final_sync_contradiction_marks_torque_unconfirmed_and_skips_restores(tmp_path):
    arm = FakeArm()
    arm.sync_torque_lie = True
    outcome, _ = run(tmp_path, arm)
    assert outcome.torque_off_confirmed is False
    names = [name for name, _ in written(arm)]
    assert names.count("goal_pwm") == 1  # restore skipped
    assert motion.exit_code(outcome) == 3


def test_verdict_is_reported_before_summary_and_stdout(tmp_path, monkeypatch, capsys):
    from contextlib import contextmanager
    arm = FakeArm()
    arm.torque_write_fails = True
    arm.fail_write = ("goal_position", 1267)

    @contextmanager
    def fake_bus(device, baudrate):
        yield object(), object()

    monkeypatch.setattr(motion, "open_motion_bus", fake_bus)
    monkeypatch.setattr(motion, "SdkReader", lambda port, packet: FakeReader(arm))
    monkeypatch.setattr(motion, "Id3Actuator", lambda port, packet: FakeActuator(arm))

    def broken_summary(path, outcome):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(motion, "write_summary", broken_summary)
    evidence = motion.load_evidence(write_evidence(tmp_path, evidence_record()))
    code = motion.execute("dev", 1000000, evidence, tmp_path / "out")
    err = capsys.readouterr().err
    assert code == 3
    assert "NOT confirmed" in err


def test_summary_write_is_atomic(tmp_path, monkeypatch):
    outcome = motion.Outcome("aborted", "x", torque_off_confirmed=True)
    target = motion.write_summary(tmp_path / "id3_motion_y.jsonl", outcome)
    assert json.loads(target.read_text())["status"] == "aborted"
    assert not list(tmp_path.glob("*.tmp"))


def test_correction_never_lets_the_joint_pass_the_true_target(tmp_path):
    arm = FakeArm()
    arm.open_shortfall = -19
    original = arm.offset

    def load_released():  # the sag vanishes once the goal is moved past the target
        return 0 if arm.goal > 1267 else original()

    arm.offset = load_released
    outcome, _ = run(tmp_path, arm)
    assert outcome.status == "aborted"
    assert "overshot" in outcome.reason
    assert max(pos for pos in [arm.positions[3]]) <= 1267 + motion.OVERSHOOT_TOLERANCE + 12
    assert outcome.torque_off_confirmed is True


def fake_cli(tmp_path, monkeypatch, arm):
    from contextlib import contextmanager

    @contextmanager
    def fake_bus(device, baudrate):
        yield object(), object()

    monkeypatch.setattr(motion, "open_motion_bus", fake_bus)
    monkeypatch.setattr(motion, "SdkReader", lambda port, packet: FakeReader(arm))
    monkeypatch.setattr(motion, "Id3Actuator", lambda port, packet: FakeActuator(arm))
    config = tmp_path / "arm.toml"
    config.write_text('[bus]\ndevice = "dev"\nbaudrate = 1000000\nprotocol = 2.0\n'
                      'expected_ids = [1, 2, 3, 4, 5]\n')
    evidence = write_evidence(tmp_path, evidence_record())
    return ["--config", str(config), "--evidence", str(evidence), "--execute",
            "--output-dir", str(tmp_path / "out")]


@pytest.fixture
def keep_handlers():
    saved = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    yield
    for sig, handler in saved.items():
        signal.signal(sig, handler)


def test_cli_execute_never_reopens_a_signal_window(tmp_path, monkeypatch, keep_handlers):
    arm = FakeArm()
    code = motion.main(fake_cli(tmp_path, monkeypatch, arm))
    assert code == 0
    # Late signals after the verdict are only recorded; the process exits with that code.
    assert isinstance(signal.getsignal(signal.SIGINT), motion.StopFlag)
    os.kill(os.getpid(), signal.SIGINT)  # must not raise


def test_log_close_failure_keeps_the_verdict(tmp_path, monkeypatch, keep_handlers):
    arm = FakeArm()
    arm.torque_write_fails = True
    arm.fail_write = ("goal_position", 1267)

    class FailingClose:
        def __init__(self, path):
            self.file = path.open("x", encoding="utf-8")

        def write(self, text):
            return self.file.write(text)

        def flush(self):
            self.file.flush()

        def close(self):
            self.file.close()
            raise OSError(28, "No space left on device")

    monkeypatch.setattr(motion, "open_log", FailingClose)
    assert motion.main(fake_cli(tmp_path, monkeypatch, arm)) == 3


def test_broken_stdout_keeps_the_exit_code(tmp_path, monkeypatch, keep_handlers):
    import sys as system

    class Broken:
        def write(self, text):
            raise BrokenPipeError(32, "Broken pipe")

        def flush(self):
            raise BrokenPipeError(32, "Broken pipe")

    monkeypatch.setattr(system, "stdout", Broken())
    assert motion.main(fake_cli(tmp_path, monkeypatch, FakeArm())) == 0
    assert not isinstance(system.stdout, Broken)  # replaced so the exit flush cannot fail


def test_stop_before_the_first_write_sends_nothing(tmp_path):
    arm = FakeArm()
    evidence = motion.load_evidence(write_evidence(tmp_path, evidence_record()))
    clock = FakeClock()
    outcome = motion.run_motion(FakeReader(arm), FakeActuator(arm), evidence, lambda e: None,
                                clock.monotonic, clock.sleep, lambda: arm.reads >= 5)
    assert outcome.interrupted is True
    assert written(arm) == []
    assert outcome.torque_off_confirmed is True  # read back as OFF, nothing to release
