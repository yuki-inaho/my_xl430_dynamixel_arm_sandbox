"""Fail-closed gate between diagnostic CAD and any print packaging."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from common import (
    EXPECTED_LEAVES,
    PART_NAMES,
    PENDING_CHECKS,
    STUDY_ID,
    VOLUME_TOLERANCE_MM3,
)


def evaluate(report: Any, current_inventory: dict[str, str]) -> list[str]:
    if not isinstance(report, dict):
        return ["missing_or_malformed_validation_report"]
    reasons = []
    if report.get("study_id") != STUDY_ID:
        reasons.append("wrong_study_or_baseline_report")
    if report.get("candidate_sha256") != current_inventory or not current_inventory:
        reasons.append("stale_or_missing_candidate_hashes")
    if report.get("acceptance_state") != "accepted_for_print":
        reasons.append("candidate_is_unaccepted")
    static = report.get("static_interference")
    if not isinstance(static, dict):
        reasons.append("missing_static_collision_check")
    else:
        if static.get("complete") is not True or static.get("errors") != []:
            reasons.append("collision_check_incomplete_or_failed")
        count = static.get("external_collision_count")
        hits = static.get("external_collisions")
        if (
            type(count) is not int
            or count < 0
            or not isinstance(hits, list)
            or count != len(hits)
        ):
            reasons.append("invalid_collision_count_or_missing_pair_evidence")
        elif count != 0:
            reasons.append(f"external_collisions_remaining:{count}")
        if (
            static.get("leaf_count") != EXPECTED_LEAVES
            or static.get("motor_occurrence_count") != 6
        ):
            reasons.append("unexpected_assembly_structure")
        attempted = static.get("boolean_attempted_pairs")
        candidates = static.get("boolean_candidate_pairs")
        if (
            type(attempted) is not int
            or type(candidates) is not int
            or attempted != candidates
            or attempted < 0
        ):
            reasons.append("not_all_candidates_checked")
        tolerance = static.get("volume_tolerance_mm3")
        if (
            type(tolerance) not in (float, int)
            or not math.isfinite(tolerance)
            or tolerance != VOLUME_TOLERANCE_MM3
        ):
            reasons.append("changed_or_missing_collision_tolerance")
    parts = report.get("parts")
    if not isinstance(parts, dict) or set(parts) != set(PART_NAMES):
        reasons.append("missing_part_validation")
    else:
        for name, item in parts.items():
            if (
                not isinstance(item, dict)
                or item.get("valid_brep") is not True
                or item.get("solid_count") != 1
                or item.get("stl_watertight") is not True
                or item.get("stl_positive_volume") is not True
            ):
                reasons.append(f"invalid_part_geometry:{name}")
            if (
                not isinstance(item, dict)
                or item.get("all_xl430_compatible") is not True
            ):
                reasons.append(f"all_xl430_part_fit_unverified:{name}")
    checks = report.get("required_checks", {})
    if not isinstance(checks, dict):
        checks = {}
    for name in PENDING_CHECKS:
        check = checks.get(name)
        if (
            not isinstance(check, dict)
            or check.get("status") != "passed"
            or check.get("candidate_sha256") != current_inventory
            or not check.get("evidence")
        ):
            reasons.append(f"missing_same_revision_evidence:{name}")
    return reasons


def assert_fresh_destination(path: Path, quarantine: Path) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError("Print destination already exists; nothing was replaced")
    if path.resolve().is_relative_to(quarantine.resolve()):
        raise ValueError("A print package cannot be placed inside diagnostic CAD")
