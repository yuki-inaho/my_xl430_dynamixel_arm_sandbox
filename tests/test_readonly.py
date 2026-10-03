from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest
from dynamixel_sdk import PacketHandler, PortHandler

from arm_observer import bus
from arm_observer.bus import ReadOnlyPort, ReadOnlyViolation, read_registers
from arm_observer.cli import main
from arm_observer.configuration import validate_config
from arm_observer.models import ArmConfig, BusConfig, RegisterBatch
from arm_observer.observer import read_metadata
from arm_observer.reader import SdkReader, decode_telemetry
from arm_observer.registers import BY_NAME, REGISTERS


class RecordingSerial:
    def __init__(self):
        self.sent = []

    def write(self, packet):
        self.sent.append(bytes(packet))
        return len(packet)


def recording_port():
    port = ReadOnlyPort("offline-test")
    port.ser = RecordingSerial()
    return port


def instruction(opcode, payload=(), motor_id=1):
    length = len(payload) + 3
    return [255, 255, 253, 0, motor_id, length & 255, length >> 8, opcode, *payload, 0, 0]


@pytest.mark.parametrize("opcode", [3, 4, 5, 6, 8, 0x10, 0x20, 0x82, 0x83, 0x92, 0x93])
def test_mutating_and_unapproved_instructions_never_reach_serial(opcode):
    port = recording_port()
    with pytest.raises(ReadOnlyViolation):
        port.writePort(instruction(opcode, [64, 0, 1]))
    assert port.ser.sent == []


@pytest.mark.parametrize(
    "packet",
    [
        instruction(1, motor_id=254),
        instruction(1, [1]),
        instruction(2),
        instruction(2, [200, 0, 4, 0]),
        [0] * 10,
    ],
)
def test_broadcast_malformed_and_unlisted_reads_are_blocked(packet):
    port = recording_port()
    with pytest.raises(ReadOnlyViolation):
        port.writePort(packet)
    assert port.ser.sent == []


def test_real_sdk_ping_and_every_schema_read_pass_guard(monkeypatch):
    port = recording_port()
    monkeypatch.setattr(port, "clearPort", lambda: None)
    monkeypatch.setattr(port, "setPacketTimeout", lambda length: None)
    packet = PacketHandler(2.0)

    def receive_timeout(port, *args):
        port.is_using = False
        return [], -3001

    monkeypatch.setattr(packet, "rxPacket", receive_timeout)
    packet.ping(port, 1)
    for register in REGISTERS:
        getattr(packet, f"read{register.size}ByteTxRx")(port, 1, register.address)
    assert len(port.ser.sent) == len(REGISTERS) + 1
    assert {frame[7] for frame in port.ser.sent} == {1, 2}


def test_sdk_write_to_torque_is_blocked_before_transmission(monkeypatch):
    port = recording_port()
    monkeypatch.setattr(port, "clearPort", lambda: None)
    with pytest.raises(ReadOnlyViolation):
        PacketHandler(2.0).write1ByteTxRx(port, 1, 64, 1)
    assert port.ser.sent == []


@pytest.mark.parametrize(
    "name,raw,expected",
    [
        ("present_position", 0xFFFFFFFF, -1),
        ("present_load", 0xFF9C, -100),
        ("present_pwm", 0x8000, -32768),
        ("homing_offset", 0xFFFFFFFE, -2),
        ("bus_watchdog", 255, -1),
        ("present_input_voltage", 92, 92),
    ],
)
def test_signed_registers_are_decoded(name, raw, expected):
    assert BY_NAME[name].decode(raw) == expected


def test_device_alert_preserves_read_value_and_does_not_hide_hardware_fault():
    packet = SimpleNamespace(read1ByteTxRx=lambda *args: (4, 0, 128))
    batch = read_registers(None, packet, 1, (BY_NAME["hardware_error_status"],))
    assert batch.faults == ()
    assert batch.readings[0].value == 4
    assert batch.readings[0].device_alert is True


def test_failed_read_is_unknown_not_zero():
    packet = SimpleNamespace(
        read4ByteTxRx=lambda *args: (0, -3001, 0), getTxRxResult=lambda result: "timeout"
    )
    batch = read_registers(None, packet, 1, (BY_NAME["present_position"],))
    assert batch.readings == ()
    assert batch.faults[0].operation == "present_position"


def test_missing_torque_sample_does_not_claim_all_off():
    motor = decode_telemetry(1, RegisterBatch((), ()))
    assert motor.torque_enabled is None
    assert motor.complete is False


def test_port_busy_stops_before_open(monkeypatch):
    monkeypatch.setattr(bus, "port_owners", lambda device: [123])
    monkeypatch.setattr(
        ReadOnlyPort, "setBaudRate", lambda *args: pytest.fail("Busy port must never be opened")
    )
    with pytest.raises(RuntimeError, match="123"):
        with bus.open_bus("offline", 1000000):
            pytest.fail("Busy port must not yield")


def test_fuser_reports_owner_even_when_device_label_is_on_stderr(monkeypatch, tmp_path):
    device = tmp_path / "serial"
    device.touch()
    monkeypatch.setattr(bus.shutil, "which", lambda name: "/usr/bin/fuser")
    monkeypatch.setattr(
        bus.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, " 123 456", "/dev/ttyUSB0:"
        ),
    )
    assert bus.port_owners(str(device)) == [123, 456]


def test_port_closes_on_interrupt(monkeypatch):
    closed = []

    def open_fake(port, baudrate):
        port.is_open = True
        port.ser = SimpleNamespace(fileno=lambda: 123)
        return True

    monkeypatch.setattr(bus, "port_owners", lambda device: [])
    monkeypatch.setattr(ReadOnlyPort, "setBaudRate", open_fake)
    monkeypatch.setattr(bus.fcntl, "ioctl", lambda *args: None)
    monkeypatch.setattr(PortHandler, "closePort", lambda port: closed.append(True))
    with pytest.raises(KeyboardInterrupt):
        with bus.open_bus("offline", 1000000):
            raise KeyboardInterrupt
    assert closed == [True]


class OfflinePacket:
    def __init__(self, model=1060):
        self.model = model
        self.calls = []

    def ping(self, port, motor_id):
        self.calls.append(("ping", motor_id))
        return self.model, 0, 0

    def read(self, port, motor_id, address):
        self.calls.append(("read", address))
        defaults = {
            0: 1060,
            6: 42,
            7: motor_id,
            8: 3,
            11: 3,
            13: 2,
            48: 4095,
            64: 0,
            70: 0,
            132: 2048,
            144: 92,
            146: 30,
        }
        return defaults.get(address, 0), 0, 0

    read1ByteTxRx = read
    read2ByteTxRx = read
    read4ByteTxRx = read


def test_whole_status_is_offline_readonly_and_skips_new_firmware_fields():
    packet = OfflinePacket()
    config = ArmConfig(BusConfig("offline", 1000000, 2.0, (1,)))
    metadata = read_metadata(SdkReader(None, packet), config, full=True)
    assert {kind for kind, _ in packet.calls} == {"read", "ping"}
    assert ("read", 60) not in packet.calls and ("read", 147) not in packet.calls
    motor = metadata.metadata[0]
    assert motor.value("torque_enable") == 0
    assert not motor.faults
    assert len(motor.skipped_registers) == 2


def test_unknown_model_is_only_pinged():
    packet = OfflinePacket(model=1030)
    config = ArmConfig(BusConfig("offline", 1000000, 2.0, (1,)))
    metadata = read_metadata(SdkReader(None, packet), config, full=True)
    assert packet.calls == [("ping", 1)]
    assert metadata.metadata[0].faults[0].operation == "model"


def test_duplicate_ids_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        validate_config(ArmConfig(BusConfig("offline", 1000000, 2.0, (1, 1))))


def test_cli_has_no_move_or_setup_command():
    with pytest.raises(SystemExit) as error:
        main(["move"])
    assert error.value.code == 2
