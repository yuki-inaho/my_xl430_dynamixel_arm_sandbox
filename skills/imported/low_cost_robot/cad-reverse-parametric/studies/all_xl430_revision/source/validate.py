"""Validate the current candidate without inheriting mixed-baseline verdicts."""

from __future__ import annotations

import csv
from pathlib import Path

import cadquery as cq
import trimesh

from collisions import scan
from common import (
    PART_NAMES,
    PENDING_CHECKS,
    STUDY_ID,
    candidate_inventory,
    check_reference_hashes,
    sha256,
    write_json,
)
from print_gate import evaluate


def validate_candidate(run: Path) -> dict:
    check_reference_hashes()
    initial = candidate_inventory(run)
    parts = {}
    for name in PART_NAMES:
        step_path = run / f"CAD/parts/{name}.step"
        stl_path = run / f"CAD/parts/{name}.stl"
        shape = cq.importers.importStep(str(step_path)).val()
        mesh = trimesh.load_mesh(str(stl_path), process=True)
        parts[name] = {
            "valid_brep": bool(shape.isValid()),
            "solid_count": len(shape.Solids()),
            "volume_mm3": float(sum(solid.Volume() for solid in shape.Solids())),
            "stl_watertight": bool(mesh.is_watertight),
            "stl_positive_volume": bool(mesh.volume > 0),
            "step_sha256": sha256(step_path),
            "stl_sha256": sha256(stl_path),
            "all_xl430_compatible": None,
            "claim": "mixed_baseline_geometry_only; no all-XL430 fit acceptance",
        }
    collision_result = scan(run, progress=lambda message: print(message, flush=True))
    final = candidate_inventory(run)
    if final != initial:
        raise ValueError("Candidate changed during validation; result is invalid")
    report = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "acceptance_state": "unaccepted",
        "candidate_sha256": final,
        "validator_sha256": {
            path.name: sha256(path)
            for path in sorted(Path(__file__).parent.glob("*.py"))
        },
        "parts": parts,
        "static_interference": collision_result,
        "required_checks": {
            name: {"status": "not_run", "evidence": None, "candidate_sha256": None}
            for name in PENDING_CHECKS
        },
        "print_status": "blocked",
        "interpretation": (
            "Static zero is necessary but not sufficient; this diagnostic study "
            "has no automatic approval path."
        ),
    }
    report["blocking_reasons"] = evaluate(report, final)
    reports = run / "reports"
    write_json(reports / "validation.json", report)
    write_json(reports / "collisions.json", collision_result)
    with (reports / "external_collision_pairs.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["left", "right", "left_unit", "right_unit", "volume_mm3"],
        )
        writer.writeheader()
        for hit in collision_result["external_collisions"]:
            writer.writerow({key: hit[key] for key in writer.fieldnames})
    write_json(
        reports / "print_gate.json",
        {
            "status": "blocked",
            "reasons": report["blocking_reasons"],
            "candidate_sha256": final,
        },
    )
    return report
