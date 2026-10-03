from pathlib import Path
from typing import Any

import yaml


class ArchitectureError(ValueError):
    """Raised when an architecture violates a user-approved boundary."""


def load_architecture(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ArchitectureError("architecture root must be a mapping")
    return data


def validate_architecture(data: dict[str, Any]) -> None:
    if data.get("schema_version") != 1:
        raise ArchitectureError("schema_version must be 1")

    camera = _mapping(data, "camera")
    mount_parent = _mapping(camera, "mount_parent")
    relationship = _mapping(camera, "kinematic_relationship")
    if (
        mount_parent.get("part") != "P05_wrist_XL430"
        or relationship.get("follows_parent") != "P05_wrist_XL430"
        or relationship.get("follows_cad_joint_J5_output_rotation") is not False
    ):
        raise ArchitectureError("camera architecture must remain P05-fixed and roll-independent")

    jaw = _mapping(data, "jaw")
    if jaw.get("physical_id") != 5:
        raise ArchitectureError("jaw actuator physical ID must be 5 by user requirement")
    if jaw.get("additional_motor_count") != 0:
        raise ArchitectureError("ID5 drives the jaw with no additional motor")
    if jaw.get("actuator_model") != "XL430-W250-T":
        raise ArchitectureError("jaw actuator must use XL430-W250-T")

    roll = _mapping(data, "roll")
    if (
        roll.get("required") is not False
        or roll.get("function_reserved") is not False
        or roll.get("physical_id_candidate") is not None
        or roll.get("may_drive_jaw") is not True
    ):
        raise ArchitectureError("roll is not required; stale ID5 roll reservation is invalid")

    mapping = _mapping(_mapping(data, "mapping"), "physical_to_cad")
    if mapping.get("jaw_drive_physical_id") is not None:
        raise ArchitectureError("jaw mapping must remain null until physical inspection")

    scope = _mapping(data, "scope")
    if scope.get("fabrication_approved") is not False:
        raise ArchitectureError("fabrication approval cannot be granted by architecture schema")
    if scope.get("powered_operation_approved") is not False:
        raise ArchitectureError(
            "powered operation approval cannot be granted by architecture schema"
        )


def _mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise ArchitectureError(f"{key} must be a mapping")
    return value
