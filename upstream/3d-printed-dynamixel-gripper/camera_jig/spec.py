from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "specs/camera_mount.yaml"


@dataclass(frozen=True)
class CameraMountSpec:
    raw: dict[str, Any]

    @property
    def parent(self) -> dict[str, Any]:
        return self.raw["parent"]

    @property
    def assembly_source(self) -> dict[str, Any]:
        return self.raw["assembly_source"]

    @property
    def donor(self) -> dict[str, Any]:
        return self.raw["donor_reference"]

    @property
    def camera(self) -> dict[str, Any]:
        return self.raw["camera"]

    @property
    def clamp(self) -> dict[str, Any]:
        return self.raw["clamp_geometry"]

    @property
    def change_mask(self) -> dict[str, Any]:
        return self.raw["change_mask"]


def load_camera_mount_spec(path: Path = SPEC_PATH) -> CameraMountSpec:
    raw = yaml.safe_load(path.read_text())
    validate_camera_mount_spec(raw)
    return CameraMountSpec(raw)


def validate_camera_mount_spec(raw: dict[str, Any]) -> None:
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("camera mount spec must be a schema_version 1 mapping")
    if raw["parent"]["part"] != "P05_wrist_XL430":
        raise ValueError("camera mount parent must remain P05_wrist_XL430")
    if raw["parent"]["camera_follows_J5_output_roll"] is not False:
        raise ValueError("camera must not follow J5 output roll")
    if raw["parent"]["modification_allowed"] is not False:
        raise ValueError("source P05 mutation is outside the change mask")


SPEC = load_camera_mount_spec()
