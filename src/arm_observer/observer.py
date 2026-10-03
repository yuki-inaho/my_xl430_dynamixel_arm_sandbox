"""Acquisition services depend on Reader, not on Linux or the vendor SDK."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event as StopEvent

from beartype import beartype

from arm_observer.configuration import validate_polling
from arm_observer.models import (
    ArmConfig,
    Fault,
    FrameEvent,
    Identity,
    MetadataEvent,
    MotorMetadata,
    ReadMode,
    RegisterBatch,
    StreamSummary,
    TelemetryFrame,
)
from arm_observer.reader import Reader, decode_telemetry, timestamp
from arm_observer.registers import BY_NAME, REGISTERS

ESSENTIAL_METADATA = tuple(
    BY_NAME[name]
    for name in (
        "id",
        "baud_rate",
        "protocol_type",
        "operating_mode",
        "drive_mode",
        "homing_offset",
    )
)
Event = MetadataEvent | FrameEvent


@beartype
@dataclass(frozen=True, slots=True)
class PollOptions:
    rate_hz: float = 20.0
    duration_seconds: float = 10.0
    frame_limit: int = 0
    metadata_every_seconds: float = 30.0
    read_mode: ReadMode = "sync"

    def __post_init__(self) -> None:
        validate_polling(self.rate_hz, self.duration_seconds, self.frame_limit)
        validate_polling(1.0, self.metadata_every_seconds, 0)


@beartype
def read_metadata(reader: Reader, config: ArmConfig, full: bool = False) -> MetadataEvent:
    motors = tuple(
        read_motor_metadata(reader, config, mid, full) for mid in config.bus.expected_ids
    )
    return MetadataEvent(motors, config, timestamp())


def read_motor_metadata(
    reader: Reader, config: ArmConfig, motor_id: int, full: bool
) -> MotorMetadata:
    identity = reader.identity(motor_id)
    role = config.role(motor_id)
    if identity is None:
        fault = Fault(motor_id, "identity", -3001, 0, "No PING response")
        return MotorMetadata(motor_id, None, role, (), (fault,), ())
    if identity.model_number != 1060:
        fault = Fault(motor_id, "model", -9000, 0, "Unsupported model; identity only")
        return MotorMetadata(motor_id, identity, role, (), (fault,), ())
    firmware = identity.firmware_version or 0
    candidates = REGISTERS if full else ESSENTIAL_METADATA
    supported = tuple(register for register in candidates if register.minimum_firmware <= firmware)
    skipped = tuple(
        register.name for register in candidates if register.minimum_firmware > firmware
    )
    batch = reader.registers(motor_id, supported)
    return MotorMetadata(
        motor_id, identity, role, batch.readings, identity.faults + batch.faults, skipped
    )


def discover(reader: Reader, ids: tuple[int, ...]) -> tuple[Identity, ...]:
    return tuple(identity for mid in ids if (identity := reader.identity(mid)) is not None)


def read_frame(
    reader: Reader, metadata: MetadataEvent, sequence: int, options: PollOptions, deadline_ns: int
) -> TelemetryFrame:
    started_at, started_ns = timestamp(), time.monotonic_ns()
    supported = tuple(
        motor.motor_id
        for motor in metadata.metadata
        if motor.identity is not None and motor.identity.model_number == 1060
    )
    readings = reader.telemetry(supported, options.read_mode)
    motors = []
    for motor in metadata.metadata:
        reading = next((item for item in readings if item.motor_id == motor.motor_id), None)
        if reading is None:
            fault = Fault(
                motor.motor_id, "telemetry", -9000, 0, "No eligible model or no fresh telemetry"
            )
            reading = decode_telemetry(motor.motor_id, RegisterBatch((), (fault,)))
        motors.append(reading)
    finished_ns = time.monotonic_ns()
    return TelemetryFrame(
        sequence,
        started_at,
        timestamp(),
        started_ns,
        (finished_ns - started_ns) / 1e6,
        options.rate_hz,
        finished_ns > deadline_ns,
        options.read_mode,
        tuple(motors),
    )


@dataclass(slots=True)
class Cadence:
    period_ns: int
    next_ns: int
    end_ns: int | None

    def wait(self, stop_event: StopEvent | None = None) -> bool:
        now = time.monotonic_ns()
        while now < self.next_ns:
            if stopped(stop_event):
                return False
            if self.end_ns is not None and now >= self.end_ns:
                return False
            time.sleep(min((self.next_ns - now) / 1e9, 0.1))
            now = time.monotonic_ns()
        return not stopped(stop_event) and (
            self.end_ns is None or now < self.end_ns
        )

    def advance(self) -> None:
        now = time.monotonic_ns()
        periods = max(1, (now - self.next_ns) // self.period_ns + 1)
        self.next_ns += periods * self.period_ns


@dataclass(slots=True)
class Counters:
    frames: int = 0
    incomplete: int = 0
    misses: int = 0
    first_frame_ns: int | None = None
    last_frame_ns: int | None = None

    def add(self, frame: TelemetryFrame) -> None:
        self.frames += 1
        self.incomplete += int(not all(motor.complete for motor in frame.motors))
        self.misses += int(frame.deadline_missed)
        if self.first_frame_ns is None:
            self.first_frame_ns = frame.monotonic_ns
        self.last_frame_ns = frame.monotonic_ns

    def summary(self, elapsed: float, interrupted: bool) -> StreamSummary:
        span = (self.last_frame_ns or 0) - (self.first_frame_ns or 0)
        rate = (self.frames - 1) * 1e9 / span if span > 0 else 0.0
        return StreamSummary(
            self.frames, self.incomplete, self.misses, elapsed, rate, interrupted, False
        )


@beartype
def observe(
    reader: Reader,
    config: ArmConfig,
    options: PollOptions,
    emit: Callable[[Event], None],
    full_metadata: bool = False,
    stop_event: StopEvent | None = None,
) -> StreamSummary:
    metadata = read_metadata(reader, config, full_metadata)
    emit(metadata)
    start = time.monotonic_ns()
    end = start + int(options.duration_seconds * 1e9) if options.duration_seconds else None
    cadence = Cadence(max(1, int(1e9 / options.rate_hz)), start, end)
    counters = Counters()
    refresh_ns = int(options.metadata_every_seconds * 1e9)
    next_refresh = start + refresh_ns
    interrupted = False
    try:
        while within_limit(counters.frames, options.frame_limit) and cadence.wait(stop_event):
            if refresh_ns and time.monotonic_ns() >= next_refresh:
                metadata = read_metadata(reader, config, full_metadata)
                emit(metadata)
                next_refresh = time.monotonic_ns() + refresh_ns
            if stopped(stop_event):
                break
            frame = read_frame(
                reader, metadata, counters.frames, options, cadence.next_ns + cadence.period_ns
            )
            counters.add(frame)
            emit(FrameEvent(frame))
            cadence.advance()
    except KeyboardInterrupt:
        interrupted = True
    return counters.summary(
        (time.monotonic_ns() - start) / 1e9,
        interrupted or stopped(stop_event),
    )


def within_limit(count: int, limit: int) -> bool:
    return limit == 0 or count < limit


def stopped(stop_event: StopEvent | None) -> bool:
    return stop_event is not None and stop_event.is_set()
