import math
import tomllib
from pathlib import Path

from beartype import beartype

from arm_observer.models import ArmConfig, BusConfig, JointRole
from arm_observer.registers import BAUDRATES


@beartype
def validate_ids(ids: tuple[int, ...]) -> None:
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("Motor IDs must be nonempty and unique")
    if any(type(motor_id) is not int or not 0 <= motor_id <= 252 for motor_id in ids):
        raise ValueError("Motor IDs must be integers in 0..252")


@beartype
def validate_config(config: ArmConfig) -> None:
    validate_ids(config.bus.expected_ids)
    if config.bus.protocol != 2.0:
        raise ValueError("Only Protocol 2.0 is supported")
    if config.bus.baudrate not in BAUDRATES.values():
        raise ValueError("Unknown XL430 baudrate")
    if not config.bus.device:
        raise ValueError("Device path must be nonempty")


@beartype
def load_config(
    path: Path,
    device: str | None = None,
    baudrate: int | None = None,
    ids: tuple[int, ...] | None = None,
) -> ArmConfig:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    bus = raw["bus"]
    arm = raw.get("arm", {})
    config = ArmConfig(
        BusConfig(
            device if device is not None else bus["device"],
            baudrate if baudrate is not None else bus["baudrate"],
            float(bus["protocol"]),
            ids if ids is not None else tuple(bus["expected_ids"]),
        ),
        tuple(JointRole(int(key), value) for key, value in arm.get("roles", {}).items()),
        arm.get("physical_order_verified", False),
    )
    validate_config(config)
    return config


@beartype
def validate_polling(rate_hz: float, duration: float, limit: int) -> None:
    if not math.isfinite(rate_hz) or not 0 < rate_hz <= 200:
        raise ValueError("Rate must be finite and in (0, 200] Hz")
    if not math.isfinite(duration) or duration < 0 or limit < 0:
        raise ValueError("Duration and count must be finite and nonnegative")
