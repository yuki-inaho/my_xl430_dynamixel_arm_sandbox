"""Outbound guard for the bounded ID3 opening; the read-only bus guard stays unchanged.

Only Protocol 2.0 WRITE (0x03) packets to one motor, for five listed RAM registers and
listed values, may pass in addition to the read-only PING/READ/SYNC_READ set.
"""

import fcntl
import termios
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

from beartype import beartype
from dynamixel_sdk import PacketHandler, PortHandler
from dynamixel_sdk.protocol2_packet_handler import Protocol2PacketHandler

from arm_observer.bus import port_owners, validate_header, validate_packet

WRITE = 0x03


class MotionViolation(RuntimeError):
    pass


@beartype
@dataclass(frozen=True, slots=True)
class WriteEnvelope:
    motor_id: int
    goal_low: int
    goal_high: int
    profile_acceleration: frozenset[int]
    profile_velocity: frozenset[int]
    goal_pwm: frozenset[int]

    def __post_init__(self) -> None:
        if not 0 <= self.motor_id <= 252:
            raise ValueError("Envelope motor ID must be a single primary ID")
        if not 0 <= self.goal_low <= self.goal_high <= 4095:
            raise ValueError("Goal window must be ordered and inside 0..4095")

    def allows(self, address: int, size: int, value: int) -> bool:
        allowed = {
            (64, 1): lambda v: v in (0, 1),
            (108, 4): lambda v: v in self.profile_acceleration,
            (112, 4): lambda v: v in self.profile_velocity,
            (100, 2): lambda v: v in self.goal_pwm,
            (116, 4): lambda v: self.goal_low <= v <= self.goal_high,
        }
        check = allowed.get((address, size))
        return check is not None and check(value)


def validate_write(packet: Sequence[int], envelope: WriteEnvelope | None) -> None:
    validate_header(packet)
    if envelope is None:
        raise MotionViolation("No motion envelope is active; writes are refused")
    if packet[4] != envelope.motor_id:
        raise MotionViolation("WRITE must address the single enveloped motor ID")
    size = len(packet) - 12
    address = packet[8] | packet[9] << 8
    value = int.from_bytes(bytes(packet[10 : 10 + size]), "little")
    if size not in (1, 2, 4) or not envelope.allows(address, size, value):
        raise MotionViolation("WRITE register, width or value outside the motion envelope")


def validate_motion_packet(packet: Sequence[int], envelope: WriteEnvelope | None) -> None:
    if len(packet) > 7 and packet[7] == WRITE:
        validate_write(packet, envelope)
    else:
        validate_packet(packet)


class MotionPort(PortHandler):
    envelope: WriteEnvelope | None = None

    def writePort(self, packet: list[int]) -> int:
        try:
            validate_motion_packet(packet, self.envelope)
        except Exception:
            # The SDK marks the port busy before writePort; release it so a refused packet
            # cannot block the following Torque OFF.
            self.is_using = False
            raise
        return super().writePort(packet)


@contextmanager
def open_motion_bus(
    device: str, baudrate: int
) -> Iterator[tuple[MotionPort, Protocol2PacketHandler]]:
    owners = port_owners(device)
    if owners:
        raise RuntimeError(f"Serial port busy, owner PID(s): {owners}")
    port = MotionPort(device)
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
