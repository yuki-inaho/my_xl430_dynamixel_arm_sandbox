"""B-rep collision scan for the exported and re-imported candidate."""

from __future__ import annotations

import itertools
import math
import sys
import time
from pathlib import Path
from typing import Callable

import cadquery as cq
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common

from build_all_xl430 import REFERENCE_XL430, TARGETS, component_name
from common import (
    EXPECTED_LEAVES,
    FOLLOWER_SOURCE,
    LENGTH_TOLERANCE_MM,
    REFERENCE_DIR,
    VOLUME_TOLERANCE_MM3,
    read_json,
)

sys.path.insert(0, str(FOLLOWER_SOURCE))

from assembly_io import bounds, read_step  # noqa: E402

MOTOR_PATHS = frozenset(
    [REFERENCE_XL430, "/Robot Arm v14/XL-430_new v1:2"]
    + [path for _, path, _ in TARGETS]
)


def original_unit(path: str) -> str:
    matches = [motor for motor in MOTOR_PATHS if path.startswith(f"{motor}/")]
    if len(matches) > 1:
        raise ValueError("Ambiguous physical motor occurrence")
    return matches[0] if matches else path


def trusted_membership() -> dict[str, str]:
    """Derive unit membership from the source STEP, never from a report flag."""
    _, _, original = read_step(REFERENCE_DIR / "arm.step")
    reference_leaves = [
        row for row in original if row.path.startswith(f"{REFERENCE_XL430}/")
    ]
    if len(original) != 161 or len(reference_leaves) != 35:
        raise ValueError("Reference structure changed")
    target_paths = [path for _, path, _ in TARGETS]
    result = {}
    for row in original:
        if any(row.path.startswith(f"{target}/") for target in target_paths):
            continue
        result[component_name(f"KEEP_{row.index:03d}_{row.name}")] = original_unit(
            row.path
        )
    for tag, target, _ in TARGETS:
        for index, leaf in enumerate(reference_leaves):
            result[component_name(f"{tag}_XL430_{index:02d}_{leaf.name}")] = target
    if len(result) != EXPECTED_LEAVES:
        raise ValueError("Physical-unit membership is incomplete")
    return result


def bbox_overlaps(left: list[float], right: list[float]) -> bool:
    return all(
        min(left[index + 3], right[index + 3]) - max(left[index], right[index])
        > LENGTH_TOLERANCE_MM
        for index in range(3)
    )


def common_volume(left: cq.Shape, right: cq.Shape) -> tuple[float, cq.Shape]:
    operation = BRepAlgoAPI_Common(left.wrapped, right.wrapped)
    operation.Build()
    if not operation.IsDone():
        raise RuntimeError("BRepAlgoAPI_Common did not complete")
    raw = operation.Shape()
    if raw.IsNull():
        raise RuntimeError("Boolean result is null, not a verified empty intersection")
    common = cq.Shape.cast(raw)
    if not common.isValid():
        raise RuntimeError("Boolean returned an invalid shape")
    volumes = [float(solid.Volume()) for solid in common.Solids()]
    if any(
        not math.isfinite(volume) or volume < -VOLUME_TOLERANCE_MM3
        for volume in volumes
    ):
        raise RuntimeError("Boolean returned invalid solid volume")
    return float(sum(volumes)), common


def scan(run: Path, progress: Callable[[str], None] = print) -> dict:
    start = time.monotonic()
    membership = trusted_membership()
    _, _, rows = read_step(run / "CAD/arm_all_XL430_static_UNACCEPTED.step")
    names = [row.name for row in rows]
    if len(names) != len(set(names)) or set(names) != set(membership):
        raise ValueError(
            "Re-imported occurrence identities differ from source structure"
        )
    manifest = read_json(run / "replacement_manifest.json")
    if (
        not isinstance(manifest, list)
        or len(manifest) != EXPECTED_LEAVES
        or {item["name"] for item in manifest} != set(names)
    ):
        raise ValueError("Candidate manifest does not cover the re-imported STEP")

    errors = []
    non_solid_names = []
    solids = {}
    boxes = {}
    for row in rows:
        try:
            shape = row.world
            if not shape.isValid():
                raise ValueError("Invalid B-rep occurrence")
            if not shape.Solids():
                non_solid_names.append(row.name)
                if membership[row.name] not in MOTOR_PATHS:
                    raise ValueError("External structural part is not a solid")
                continue
            volume = float(sum(solid.Volume() for solid in shape.Solids()))
            if not math.isfinite(volume) or volume <= 0:
                raise ValueError("Invalid solid volume")
            solids[row.name] = shape
            boxes[row.name] = bounds(shape)
        except Exception as error:  # CAD kernel errors must become blocking evidence.
            errors.append({"occurrence": row.name, "error": str(error)})

    pairs = [
        (left, right)
        for left, right in itertools.combinations(solids, 2)
        if bbox_overlaps(boxes[left], boxes[right])
    ]
    progress(
        f"B-rep scan: {len(rows)} leaves, {len(solids)} solid occurrences, "
        f"{len(pairs)} candidate pairs"
    )
    external = []
    internal = []
    for number, (left, right) in enumerate(pairs, 1):
        try:
            volume, common = common_volume(solids[left], solids[right])
            if volume > VOLUME_TOLERANCE_MM3:
                left_unit = membership[left]
                right_unit = membership[right]
                item = {
                    "left": left,
                    "right": right,
                    "left_unit": left_unit,
                    "right_unit": right_unit,
                    "volume_mm3": volume,
                    "bounds_mm": bounds(common),
                }
                supplier_internal = left_unit == right_unit and left_unit in MOTOR_PATHS
                (internal if supplier_internal else external).append(item)
        except Exception as error:  # A failed pair is not equivalent to no collision.
            errors.append({"left": left, "right": right, "error": str(error)})
        if number % 50 == 0:
            progress(
                f"Checked {number}/{len(pairs)}; external overlaps={len(external)}"
            )
    return {
        "check_kind": "static_exported_BREP_not_full_motion",
        "complete": not errors,
        "errors": errors,
        "leaf_count": len(rows),
        "valid_brep_occurrences": len(rows) - len(errors),
        "solid_occurrences": len(solids),
        "non_solid_reference_occurrences": len(non_solid_names),
        "non_solid_reference_names": non_solid_names,
        "total_solid_pairs": len(solids) * (len(solids) - 1) // 2,
        "boolean_candidate_pairs": len(pairs),
        "boolean_attempted_pairs": len(pairs),
        "external_collision_count": len(external),
        "external_collisions": external,
        "supplier_internal_collision_count": len(internal),
        "supplier_internal_collisions": internal,
        "motor_occurrence_count": len(
            {value for value in membership.values() if value in MOTOR_PATHS}
        ),
        "volume_tolerance_mm3": VOLUME_TOLERANCE_MM3,
        "bbox_length_tolerance_mm": LENGTH_TOLERANCE_MM,
        "elapsed_seconds": round(time.monotonic() - start, 3),
    }
