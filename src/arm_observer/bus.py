"""Linux serial ownership and the read-only outbound protocol boundary."""

import fcntl
import shutil
import subprocess
import termios
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from dynamixel_sdk import COMM_SUCCESS, PacketHandler, PortHandler
from dynamixel_sdk.protocol2_packet_handler import Protocol2PacketHandler

from arm_observer.models import Fault, RegisterBatch, RegisterValue
from arm_observer.registers import REGISTERS, Register

SYNC_RANGES = frozenset({(64, 7), (120, 27)})
READABLE_RANGES = frozenset((register.address, register.size) for register in REGISTERS)
READABLE_RANGES = READABLE_RANGES | SYNC_RANGES


class ReadOnlyViolation(RuntimeError):
    pass


def validate_header(packet: Sequence[int]) -> None:
    valid = (
        len(packet) >= 10
        and bytes(packet[:4]) == b"\xff\xff\xfd\x00"
        and (packet[5] | packet[6] << 8) == len(packet) - 7
    )
    if not valid:
        raise ReadOnlyViolation("Malformed Protocol 2.0 frame")


def validate_unicast(packet: Sequence[int]) -> None:
    if not 0 <= packet[4] <= 252:
        raise ReadOnlyViolation("PING/READ must address a single primary ID in 0..252")
    if packet[7] == 1:
        if len(packet) != 10:
            raise ReadOnlyViolation("Invalid PING payload")
        return
    if len(packet) != 14:
        raise ReadOnlyViolation("Invalid READ payload")
    address, size = packet[8] | packet[9] << 8, packet[10] | packet[11] << 8
    if (address, size) not in READABLE_RANGES:
        raise ReadOnlyViolation("READ range outside the diagnostic control table")


def validate_sync(packet: Sequence[int]) -> None:
    if packet[4] != 254 or len(packet) < 15:
        raise ReadOnlyViolation("Invalid SYNC_READ envelope")
    address, size = packet[8] | packet[9] << 8, packet[10] | packet[11] << 8
    if (address, size) not in SYNC_RANGES:
        raise ReadOnlyViolation("SYNC_READ range outside the telemetry blocks")
    ids = tuple(packet[12:-2])
    if len(set(ids)) != len(ids) or any(not 0 <= motor_id <= 252 for motor_id in ids):
        raise ReadOnlyViolation("Invalid or repeated SYNC_READ IDs")


def validate_packet(packet: Sequence[int]) -> None:
    validate_header(packet)
    opcode = packet[7]
    if opcode in (1, 2):
        validate_unicast(packet)
    elif opcode == 0x82:
        validate_sync(packet)
    else:
        raise ReadOnlyViolation("Only PING, READ, and validated SYNC_READ are permitted")


class ReadOnlyPort(PortHandler):
    def writePort(self, packet: list[int]) -> int:
        validate_packet(packet)
        return super().writePort(packet)


def port_owners(device: str) -> list[int]:
    if not Path(device).exists():
        raise RuntimeError(f"Serial device not found: {device}")
    executable = shutil.which("fuser")
    if executable is None:
        raise RuntimeError("fuser is required (Ubuntu package: psmisc)")
    result = subprocess.run([executable, device], capture_output=True, text=True, check=False)
    if result.returncode == 0:
        return [int(pid) for pid in result.stdout.split()]
    if result.returncode != 1 or result.stderr.strip():
        raise RuntimeError(f"Cannot check serial ownership: {result.stderr.strip()}")
    return []


@contextmanager
def open_bus(device: str, baudrate: int) -> Iterator[tuple[ReadOnlyPort, Protocol2PacketHandler]]:
    owners = port_owners(device)
    if owners:
        raise RuntimeError(f"Serial port busy, owner PID(s): {owners}")
    port = ReadOnlyPort(device)
    try:
        if not port.setBaudRate(baudrate):
            raise RuntimeError(f"Unsupported host baudrate: {baudrate}")
        serial = port.ser
        if serial is None:
            raise RuntimeError("SDK opened no serial connection")
        serial.exclusive = True
        fcntl.ioctl(serial.fileno(), termios.TIOCEXCL)
        yield port, PacketHandler(2.0)
    finally:
        if port.is_open:
            port.closePort()


def fault_message(packet: Protocol2PacketHandler, result: int, error: int) -> str:
    return (
        packet.getTxRxResult(result) if result != COMM_SUCCESS else packet.getRxPacketError(error)
    )


def read_registers(
    port: PortHandler,
    packet: Protocol2PacketHandler,
    motor_id: int,
    registers: tuple[Register, ...],
) -> RegisterBatch:
    readings: list[RegisterValue] = []
    faults: list[Fault] = []
    for register in registers:
        raw, result, error = getattr(packet, f"read{register.size}ByteTxRx")(
            port, motor_id, register.address
        )
        if result != COMM_SUCCESS or error & 0x7F:
            faults.append(
                Fault(motor_id, register.name, result, error, fault_message(packet, result, error))
            )
        else:
            readings.append(
                RegisterValue(
                    register.name,
                    register.address,
                    register.size,
                    register.memory,
                    raw,
                    register.decode(raw),
                    bool(error & 0x80),
                )
            )
    return RegisterBatch(tuple(readings), tuple(faults))
