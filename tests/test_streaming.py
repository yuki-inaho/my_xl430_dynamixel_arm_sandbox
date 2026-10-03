import io
import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import numpy as np
import pytest
from beartype.roar import BeartypeCallHintViolation
from dynamixel_sdk import COMM_TX_FAIL, PacketHandler
from jaxtyping import TypeCheckError
from jsonschema import Draft202012Validator
from test_readonly import instruction, recording_port

from arm_observer import observer
from arm_observer.bus import ReadOnlyViolation, validate_packet
from arm_observer.contracts import stream_schema
from arm_observer.diagnostics import configuration_findings, telemetry_findings
from arm_observer.models import (
    ArmConfig,
    BusConfig,
    FrameEvent,
    RegisterBatch,
    TelemetryFrame,
)
from arm_observer.numerics import joint_positions_radians, velocities_radians_per_second
from arm_observer.observer import Cadence, PollOptions, observe
from arm_observer.output import JsonlSink, encode
from arm_observer.reader import SdkReader, decode_telemetry
from arm_observer.registers import REGISTERS

ROOT = Path(__file__).resolve().parents[1]


def data_block(motor_id, address, size):
    data = bytearray(size)
    values = {
        64: 0,
        70: 0,
        120: 123,
        122: 0,
        123: 1,
        124: -20,
        126: -30,
        128: -10,
        132: -2048,
        144: 92,
        146: 30,
    }
    for register in REGISTERS:
        offset = register.address - address
        if 0 <= offset <= size - register.size:
            raw = values.get(register.address, 0) & ((1 << (8 * register.size)) - 1)
            data[offset : offset + register.size] = raw.to_bytes(register.size, "little")
    return tuple(data)


@pytest.fixture
def sdk_reader(monkeypatch):
    port = recording_port()
    packet = PacketHandler(2.0)
    monkeypatch.setattr(port, "clearPort", lambda: None)
    monkeypatch.setattr(port, "setPacketTimeout", lambda *args: None)

    def read_rx(port, motor_id, size):
        frame = port.ser.sent[-1]
        address = frame[8] | frame[9] << 8
        port.is_using = False
        return data_block(motor_id, address, size), 0, 0

    monkeypatch.setattr(packet, "readRx", read_rx)
    return SdkReader(port, packet)


def test_sdk_sync_uses_two_read_only_packets_for_all_motors(sdk_reader):
    motors = sdk_reader.telemetry((1, 2, 3, 4, 5), "sync")
    assert len(sdk_reader.port.ser.sent) == 2
    assert {packet[7] for packet in sdk_reader.port.ser.sent} == {0x82}
    assert all(motor.complete for motor in motors)
    assert motors[0].position_counts == -2048
    assert motors[0].load_raw == -30
    assert motors[0].pwm_raw == -20
    assert motors[0].torque_enabled is False


def test_previous_success_cannot_leak_into_failed_next_frame(sdk_reader, monkeypatch):
    assert sdk_reader.telemetry((1, 2), "sync")[0].complete
    monkeypatch.setattr(sdk_reader.packet, "syncReadTx", lambda *args: COMM_TX_FAIL)
    missing = sdk_reader.telemetry((1, 2), "sync")
    assert all(motor.position_counts is None and motor.torque_enabled is None for motor in missing)
    assert all(motor.faults and not motor.complete for motor in missing)


def test_per_device_error_is_not_discarded(sdk_reader, monkeypatch):
    original = sdk_reader.packet.readRx

    def erroneous(*args):
        data, result, _ = original(*args)
        return data, result, 4

    monkeypatch.setattr(sdk_reader.packet, "readRx", erroneous)
    motor = sdk_reader.telemetry((1,), "sync")[0]
    assert motor.position_counts is None
    assert motor.faults[0].device_error == 4


def test_short_sync_response_is_unknown(sdk_reader, monkeypatch):
    monkeypatch.setattr(sdk_reader.packet, "readRx", lambda *args: ((1,), 0, 0))
    motor = sdk_reader.telemetry((1,), "sync")[0]
    assert motor.position_counts is None
    assert not motor.complete


def test_alert_bit_preserves_valid_data(sdk_reader, monkeypatch):
    original = sdk_reader.packet.readRx

    def alerted(*args):
        data, result, _ = original(*args)
        return data, result, 128

    monkeypatch.setattr(sdk_reader.packet, "readRx", alerted)
    motor = sdk_reader.telemetry((1,), "sync")[0]
    assert motor.position_counts == -2048
    assert motor.device_alert


@pytest.mark.parametrize(
    "ids,address,size", [((1, 1), 120, 27), ((254,), 120, 27), ((1,), 64, 1), ((), 120, 27)]
)
def test_invalid_sync_read_is_rejected(ids, address, size):
    frame = instruction(0x82, [address, 0, size, 0, *ids], motor_id=254)
    with pytest.raises(ReadOnlyViolation):
        validate_packet(frame)


def test_valid_block_sync_read_is_allowed():
    validate_packet(instruction(0x82, [120, 0, 27, 0, 1, 2, 3], motor_id=254))


def test_records_are_immutable_and_runtime_checked():
    config = BusConfig("offline", 1000000, 2.0, (1,))
    with pytest.raises(FrozenInstanceError):
        config.baudrate = 57600
    with pytest.raises(BeartypeCallHintViolation):
        BusConfig("offline", "1000000", 2.0, (1,))


def test_calibration_has_correct_units_shapes_and_dtypes():
    angles = joint_positions_radians(
        np.array([2048, 1024], dtype=np.int32),
        np.zeros(2, dtype=np.int32),
        np.array([1, -1], dtype=np.int8),
        np.ones(2, dtype=np.float64),
    )
    np.testing.assert_allclose(angles, [np.pi, -np.pi / 2])
    speeds = velocities_radians_per_second(np.array([100], dtype=np.int32))
    np.testing.assert_allclose(speeds, [100 * 0.229 * 2 * np.pi / 60])
    with pytest.raises(TypeCheckError):
        joint_positions_radians(
            np.zeros(2, dtype=np.int32),
            np.zeros(3, dtype=np.int32),
            np.ones(2, dtype=np.int8),
            np.ones(2, dtype=np.float64),
        )
    with pytest.raises(TypeCheckError):
        velocities_radians_per_second(np.array([1.0], dtype=np.float64))


def test_conversion_avoids_int32_subtraction_overflow():
    actual = joint_positions_radians(
        np.array([2147483647], dtype=np.int32),
        np.array([-2147483648], dtype=np.int32),
        np.array([1], dtype=np.int8),
        np.array([1.0]),
    )
    assert actual[0] > 0


@pytest.mark.parametrize("ratio", [0.0, -1.0, np.inf, np.nan])
def test_invalid_gear_ratio_is_rejected(ratio):
    with pytest.raises(ValueError):
        joint_positions_radians(
            np.array([0], dtype=np.int32),
            np.array([0], dtype=np.int32),
            np.array([1], dtype=np.int8),
            np.array([ratio], dtype=np.float64),
        )


def test_schema_and_fixtures_match_generated_contract():
    schema = stream_schema()
    saved = json.loads((ROOT / "contracts/stream-v2.schema.json").read_text())
    assert saved == schema
    validator = Draft202012Validator(schema)
    for line in (ROOT / "tests/fixtures/stream_v2.jsonl").read_text().splitlines():
        validator.validate(json.loads(line))


def test_unknown_version_does_not_validate():
    event = json.loads((ROOT / "tests/fixtures/frame_v2.json").read_text())
    event["schema_version"] = 99
    assert list(Draft202012Validator(stream_schema()).iter_errors(event))


@pytest.mark.parametrize(
    "field,value", [("position_counts", 2**31), ("load_raw", -32769), ("motor_id", 253)]
)
def test_schema_rejects_values_outside_portable_integer_ranges(field, value):
    event = json.loads((ROOT / "tests/fixtures/frame_v2.json").read_text())
    event["frame"]["motors"][0][field] = value
    assert list(Draft202012Validator(stream_schema()).iter_errors(event))


def test_alert_has_a_finding_even_without_hardware_mask(sdk_reader):
    motor = replace(sdk_reader.telemetry((1,), "sync")[0], device_alert=True)
    assert "device_alert" in {note.code for note in telemetry_findings(motor)}


def test_reverse_drive_still_uses_velocity_profile():
    from test_readonly import OfflinePacket

    config = ArmConfig(BusConfig("offline", 1000000, 2.0, (1,)))
    motor = observer.read_metadata(SdkReader(None, OfflinePacket()), config, full=True).metadata[0]
    registers = tuple(
        replace(register, raw=1, value=1) if register.name == "drive_mode" else register
        for register in motor.registers
    )
    motor = replace(motor, registers=registers)
    assert "unbounded_velocity_profile" in {note.code for note in configuration_findings(motor)}


def test_jsonl_sink_writes_complete_records_without_buffering_history():
    file = io.StringIO()
    sink = JsonlSink(file)
    missing = decode_telemetry(2, RegisterBatch((), ()))
    event = FrameEvent(TelemetryFrame(0, "test", "test", 123, 5.0, 20.0, False, "sync", (missing,)))
    for _ in range(3):
        sink.emit(event)
    assert len(file.getvalue().splitlines()) == 3
    assert (
        json.loads(file.getvalue().splitlines()[1])["frame"]["motors"][0]["position_counts"] is None
    )
    assert encode(event) == file.getvalue().splitlines()[1]


def test_cadence_skips_backlog_instead_of_bursting(monkeypatch):
    monkeypatch.setattr(observer.time, "monotonic_ns", lambda: 350)
    cadence = Cadence(100, 0, None)
    cadence.advance()
    assert cadence.next_ns == 400


@pytest.mark.parametrize(
    "rate,duration,count", [(0.0, 1.0, 0), (np.nan, 1.0, 0), (20.0, -1.0, 0), (20.0, 1.0, -1)]
)
def test_invalid_polling_options_fail_before_hardware(rate, duration, count):
    with pytest.raises(ValueError):
        PollOptions(rate, duration, count)


def test_stream_records_failure_and_can_recover_without_stale_values(sdk_reader, monkeypatch):
    from test_readonly import OfflinePacket

    metadata_reader = SdkReader(None, OfflinePacket())

    class CombinedReader:
        identity = metadata_reader.identity
        registers = metadata_reader.registers
        cycles = 0

        def telemetry(self, ids, mode):
            self.cycles += 1
            original = sdk_reader.packet.syncReadTx
            if self.cycles == 2:
                monkeypatch.setattr(sdk_reader.packet, "syncReadTx", lambda *args: COMM_TX_FAIL)
            try:
                return sdk_reader.telemetry(ids, mode)
            finally:
                monkeypatch.setattr(sdk_reader.packet, "syncReadTx", original)

    records = []
    config = ArmConfig(BusConfig("offline", 1000000, 2.0, (1, 2)))
    summary = observe(CombinedReader(), config, PollOptions(200.0, 0.0, 3, 0.0), records.append)
    frames = tuple(event.frame for event in records if isinstance(event, FrameEvent))
    assert len(frames) == 3
    assert summary.frames == 3 and summary.incomplete_frames == 1
    assert [frame.sequence for frame in frames] == [0, 1, 2]
    assert frames[1].motors[0].position_counts is None
    assert frames[2].motors[0].position_counts == -2048
    assert summary.port_closed is False
