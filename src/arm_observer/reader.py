"""A narrow read interface and the official SDK adapter."""

from datetime import datetime
from typing import NamedTuple, Protocol, runtime_checkable

from dynamixel_sdk import COMM_RX_CORRUPT, COMM_SUCCESS, GroupSyncRead, PortHandler
from dynamixel_sdk.protocol2_packet_handler import Protocol2PacketHandler

from arm_observer.bus import read_registers
from arm_observer.models import (
    Fault,
    Identity,
    MotorTelemetry,
    ReadMode,
    RegisterBatch,
    RegisterValue,
)
from arm_observer.registers import BY_NAME, TELEMETRY, Register


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


@runtime_checkable
class Reader(Protocol):
    def identity(self, motor_id: int) -> Identity | None: ...
    def registers(self, motor_id: int, registers: tuple[Register, ...]) -> RegisterBatch: ...
    def telemetry(self, ids: tuple[int, ...], mode: ReadMode) -> tuple[MotorTelemetry, ...]: ...


class ReadReply(NamedTuple):
    data: tuple[int, ...]
    comm_result: int
    device_error: int


class Receipt(NamedTuple):
    motor_id: int
    reply: ReadReply


class Block(NamedTuple):
    address: int
    size: int
    registers: tuple[Register, ...]


BLOCKS = (
    Block(64, 7, (BY_NAME["torque_enable"], BY_NAME["hardware_error_status"])),
    Block(
        120,
        27,
        (
            BY_NAME["realtime_tick"],
            *(register for register in TELEMETRY if register.address >= 120),
        ),
    ),
)


class ReceiptPacket:
    """Retain per-device error bytes that GroupSyncRead otherwise discards."""

    def __init__(self, packet: Protocol2PacketHandler):
        self.packet = packet
        self.receipts: tuple[Receipt, ...] = ()

    def getProtocolVersion(self) -> float:
        return self.packet.getProtocolVersion()

    def syncReadTx(
        self, port: PortHandler, address: int, size: int, ids: list[int], count: int, fast: bool
    ) -> int:
        self.receipts = ()
        return self.packet.syncReadTx(port, address, size, ids, count, fast)

    def readRx(self, port: PortHandler, motor_id: int, size: int) -> ReadReply:
        data, result, error = self.packet.readRx(port, motor_id, size)
        if result == COMM_SUCCESS and len(data) != size:
            result = COMM_RX_CORRUPT
        reply = ReadReply(tuple(data), result, error)
        self.receipts += (Receipt(motor_id, reply),)
        return reply


class SyncGroup(NamedTuple):
    block: Block
    capture: ReceiptPacket
    group: GroupSyncRead


def decode_block(motor_id: int, block: Block, receipt: Receipt) -> RegisterBatch:
    reply = receipt.reply
    if reply.comm_result != COMM_SUCCESS or reply.device_error & 0x7F:
        fault = Fault(
            motor_id,
            "sync_read",
            reply.comm_result,
            reply.device_error,
            "Invalid per-device status; values unavailable",
        )
        return RegisterBatch((), (fault,))
    readings = []
    for register in block.registers:
        offset = register.address - block.address
        raw = int.from_bytes(bytes(reply.data[offset : offset + register.size]), "little")
        readings.append(
            RegisterValue(
                register.name,
                register.address,
                register.size,
                register.memory,
                raw,
                register.decode(raw),
                bool(reply.device_error & 0x80),
            )
        )
    return RegisterBatch(tuple(readings), ())


def optional_bool(value: int | None) -> bool | None:
    return None if value is None else bool(value)


def decode_telemetry(motor_id: int, batch: RegisterBatch) -> MotorTelemetry:
    return MotorTelemetry(
        motor_id,
        optional_bool(batch.value("torque_enable")),
        batch.value("hardware_error_status"),
        batch.value("present_position"),
        batch.value("present_velocity"),
        batch.value("present_pwm"),
        batch.value("present_load"),
        batch.value("present_input_voltage"),
        batch.value("present_temperature"),
        optional_bool(batch.value("moving")),
        batch.value("moving_status"),
        batch.value("realtime_tick"),
        any(reading.device_alert for reading in batch.readings),
        batch.faults,
    )


class SdkReader:
    def __init__(self, port: PortHandler, packet: Protocol2PacketHandler):
        self.port = port
        self.packet = packet
        self._ids: tuple[int, ...] = ()
        self._groups: tuple[SyncGroup, ...] = ()

    def identity(self, motor_id: int) -> Identity | None:
        model, result, error = self.packet.ping(self.port, motor_id)
        if result != COMM_SUCCESS or error & 0x7F:
            return None
        batch = RegisterBatch((), ())
        if model == 1060:
            batch = self.registers(motor_id, (BY_NAME["firmware_version"],))
        return Identity(
            motor_id, model, batch.value("firmware_version"), timestamp(), error, batch.faults
        )

    def registers(self, motor_id: int, registers: tuple[Register, ...]) -> RegisterBatch:
        return read_registers(self.port, self.packet, motor_id, registers)

    def _prepare_groups(self, ids: tuple[int, ...]) -> None:
        if ids == self._ids:
            return
        groups = []
        for block in BLOCKS:
            capture = ReceiptPacket(self.packet)
            group = GroupSyncRead(self.port, capture, block.address, block.size)
            for motor_id in ids:
                if not group.addParam(motor_id):
                    raise ValueError(f"Cannot add ID {motor_id} to SYNC_READ")
            groups.append(SyncGroup(block, capture, group))
        self._groups, self._ids = tuple(groups), ids

    def _sync_block(self, ids: tuple[int, ...], sync: SyncGroup) -> tuple[RegisterBatch, ...]:
        # txRxPacket can leave last_result=True after TX failure; reset before every cycle.
        sync.group.last_result = False
        sync.capture.receipts = ()
        result = sync.group.txRxPacket()
        if result != COMM_SUCCESS:
            return tuple(
                RegisterBatch(
                    (), (Fault(mid, "sync_read", result, 0, self.packet.getTxRxResult(result)),)
                )
                for mid in ids
            )
        batches = []
        for motor_id in ids:
            receipt = next(
                (item for item in sync.capture.receipts if item.motor_id == motor_id), None
            )
            if receipt is None:
                batches.append(
                    RegisterBatch(
                        (), (Fault(motor_id, "sync_read", -3001, 0, "No fresh response"),)
                    )
                )
            else:
                batches.append(decode_block(motor_id, sync.block, receipt))
        return tuple(batches)

    def telemetry(self, ids: tuple[int, ...], mode: ReadMode) -> tuple[MotorTelemetry, ...]:
        if not ids:
            return ()
        if mode == "unicast":
            return tuple(
                decode_telemetry(mid, self.registers(mid, (BY_NAME["realtime_tick"], *TELEMETRY)))
                for mid in ids
            )
        self._prepare_groups(ids)
        blocks = tuple(self._sync_block(ids, group) for group in self._groups)
        motors = []
        for index, motor_id in enumerate(ids):
            readings = tuple(reading for block in blocks for reading in block[index].readings)
            faults = tuple(fault for block in blocks for fault in block[index].faults)
            motors.append(decode_telemetry(motor_id, RegisterBatch(readings, faults)))
        return tuple(motors)
