"""Paths, provenance, and atomic writes for the unaccepted study."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any

STUDY_DIR = Path(__file__).resolve().parents[1]
CADRE_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = Path(__file__).resolve().parents[5]
OUTPUT_ROOT = CADRE_ROOT / "outputs/all_xl430_revision"
REFERENCE_DIR = REPO_ROOT / "hardware/follower/step"
FOLLOWER_SOURCE = STUDY_DIR.parent / "follower_geometry_revision/source"
STUDY_ID = "all_xl430_revision_20260919"
EXPECTED_LEAVES = 217
VOLUME_TOLERANCE_MM3 = 1e-4
LENGTH_TOLERANCE_MM = 1e-5
PART_NAMES = (
    "base_idler_clearance",
    "shoulder_rotation_unchanged",
    "shoulder_to_elbow_unchanged",
    "elbow_to_wrist_extension_round",
    "elbow_to_wrist_standoff",
    "gripper_static_unchanged",
    "gripper_moving_unchanged",
)
PENDING_CHECKS = (
    "all_xl430_part_compatibility",
    "full_motion_collision",
    "holding_torque",
    "strength",
    "fasteners_and_assembly",
    "physical_fit",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    def invalid_constant(value: str) -> None:
        raise ValueError(f"Non-finite JSON value: {value}")

    with path.open(encoding="utf-8") as stream:
        return json.load(stream, parse_constant=invalid_constant)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def study_run(run_id: str, *, root: Path | None = None) -> Path:
    """Keep every diagnostic candidate inside the ignored quarantine."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id):
        raise ValueError("run-id must be a simple name, not a filesystem path")
    quarantine = (root or OUTPUT_ROOT) / "unaccepted"
    if quarantine.is_symlink():
        raise ValueError("unaccepted must not be a symbolic link")
    path = quarantine / run_id
    if path.is_symlink() or path.resolve().parent != quarantine.resolve():
        raise ValueError("Output must remain under unaccepted")
    return path


def check_reference_hashes(
    manifest_path: Path | None = None,
    reference_dir: Path | None = None,
) -> dict[str, str]:
    manifest = manifest_path or FOLLOWER_SOURCE / "input_sha256.json"
    base = (reference_dir or REFERENCE_DIR).resolve()
    expected = read_json(manifest)
    if not isinstance(expected, dict) or not expected:
        raise ValueError("Reference manifest is empty or malformed")
    actual = {}
    for name, expected_hash in expected.items():
        path = base / name
        if (
            path.is_symlink()
            or not path.resolve().is_relative_to(base)
            or not path.is_file()
        ):
            raise ValueError(f"Reference missing or unsafe: {path}")
        actual[name] = sha256(path)
        if actual[name] != expected_hash:
            raise ValueError(f"Reference missing or changed: {name}")
    return actual


def candidate_inventory(run: Path) -> dict[str, str]:
    """Bind a result to every CAD byte and to its occurrence mapping."""
    paths = [
        run / "CAD/arm_all_XL430_static_UNACCEPTED.step",
        run / "replacement_manifest.json",
    ]
    paths.extend(
        run / f"CAD/parts/{name}.{extension}"
        for name in PART_NAMES
        for extension in ("step", "stl")
    )
    expected_parts = {
        f"{name}.{extension}" for name in PART_NAMES for extension in ("step", "stl")
    }
    part_directory = run / "CAD/parts"
    if (
        not part_directory.is_dir()
        or {path.name for path in part_directory.iterdir()} != expected_parts
    ):
        raise ValueError("Unexpected, missing or extra candidate part files")
    inventory = {}
    for path in paths:
        if (
            path.is_symlink()
            or not path.resolve().is_relative_to(run.resolve())
            or not path.is_file()
        ):
            raise ValueError(f"Candidate input absent or unsafe: {path.name}")
        inventory[path.relative_to(run).as_posix()] = sha256(path)
    return inventory


def finite_positive(value: float) -> bool:
    return math.isfinite(value) and value > 0
