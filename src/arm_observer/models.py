"""Immutable domain records. Dictionaries belong only at TOML/JSON boundaries."""

from dataclasses import dataclass
from typing import Literal, NamedTuple

from beartype import beartype

ReadMode = Literal["sync", "unicast"]


@beartype
@dataclass(frozen=True, slots=True)
class BusConfig:
    device: str
    baudrate: int
    protocol: float
    expected_ids: tuple[int, ...]


@beartype
@dataclass(frozen=True, slots=True)
class JointRole:
    motor_id: int
    name: str


@beartype
@dataclass(frozen=True, slots=True)
class ArmConfig:
    bus: BusConfig
    roles: tuple[JointRole, ...] = ()
    physical_order_verified: bool = False

    def role(self, motor_id: int) -> str | None:
        return next((role.name for role in self.roles if role.motor_id == motor_id), None)


@beartype
@dataclass(frozen=True, slots=True)
class Fault:
    motor_id: int
    operation: str
    comm_result: int
    device_error: int
    message: str


@beartype
@dataclass(frozen=True, slots=True)
class Identity:
    motor_id: int
    model_number: int
    firmware_version: int | None
    observed_at: str
    device_error: int
    faults: tuple[Fault, ...] = ()


@beartype
@dataclass(frozen=True, slots=True)
class RegisterValue:
    name: str
    address: int
    size: int
    memory: str
    raw: int
    value: int
    device_alert: bool


class RegisterBatch(NamedTuple):
    readings: tuple[RegisterValue, ...]
    faults: tuple[Fault, ...]

    def value(self, name: str) -> int | None:
        return next((reading.value for reading in self.readings if reading.name == name), None)


@beartype
@dataclass(frozen=True, slots=True)
class MotorMetadata:
    motor_id: int
    identity: Identity | None
    proposed_role: str | None
    registers: tuple[RegisterValue, ...]
    faults: tuple[Fault, ...]
    skipped_registers: tuple[str, ...]

    def value(self, name: str) -> int | None:
        return RegisterBatch(self.registers, self.faults).value(name)


@beartype
@dataclass(frozen=True, slots=True)
class MotorTelemetry:
    motor_id: int
    torque_enabled: bool | None
    hardware_error: int | None
    position_counts: int | None
    velocity_raw: int | None
    pwm_raw: int | None
    load_raw: int | None
    voltage_raw: int | None
    temperature_c: int | None
    moving: bool | None
    moving_status: int | None
    tick_ms: int | None
    device_alert: bool
    faults: tuple[Fault, ...]

    @property
    def complete(self) -> bool:
        observed = (
            self.torque_enabled,
            self.hardware_error,
            self.position_counts,
            self.velocity_raw,
            self.pwm_raw,
            self.load_raw,
            self.voltage_raw,
            self.temperature_c,
            self.moving,
            self.moving_status,
            self.tick_ms,
        )
        return not self.faults and all(value is not None for value in observed)

    @property
    def voltage_v(self) -> float | None:
        return None if self.voltage_raw is None else self.voltage_raw / 10

    @property
    def velocity_rpm(self) -> float | None:
        return None if self.velocity_raw is None else self.velocity_raw * 0.229

    @property
    def estimated_load_percent(self) -> float | None:
        return None if self.load_raw is None else self.load_raw / 10


@beartype
@dataclass(frozen=True, slots=True)
class TelemetryFrame:
    sequence: int
    started_at: str
    finished_at: str
    monotonic_ns: int
    duration_ms: float
    requested_rate_hz: float
    deadline_missed: bool
    read_mode: ReadMode
    motors: tuple[MotorTelemetry, ...]


@beartype
@dataclass(frozen=True, slots=True)
class MetadataEvent:
    metadata: tuple[MotorMetadata, ...]
    config: ArmConfig
    observed_at: str
    kind: Literal["metadata"] = "metadata"
    schema_version: Literal[2] = 2
    simulated: bool | None = None
    acquisition_id: str | None = None


@beartype
@dataclass(frozen=True, slots=True)
class FrameEvent:
    frame: TelemetryFrame
    kind: Literal["frame"] = "frame"
    schema_version: Literal[2] = 2


@beartype
@dataclass(frozen=True, slots=True)
class StreamSummary:
    frames: int
    incomplete_frames: int
    deadline_misses: int
    elapsed_seconds: float
    achieved_rate_hz: float
    interrupted: bool
    port_closed: bool


@beartype
@dataclass(frozen=True, slots=True)
class EndEvent:
    summary: StreamSummary
    kind: Literal["end"] = "end"
    schema_version: Literal[2] = 2


@beartype
@dataclass(frozen=True, slots=True)
class Finding:
    motor_id: int | None
    level: Literal["info", "warning", "error"]
    code: str
    message: str


@beartype
@dataclass(frozen=True, slots=True)
class InspectionReport:
    metadata: MetadataEvent
    discovered: tuple[Identity, ...]
    frames: tuple[TelemetryFrame, ...]
    findings: tuple[Finding, ...]
    port_closed: bool
    schema_version: Literal[2] = 2
