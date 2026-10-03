"""Validate and prepare STL/STEP artifacts for 3D printing.

This checker is deliberately stricter than CAD preservation gates: a source STL can be
acceptable as reverse-engineering evidence while still being unsafe for a slicer. The
script reports mesh watertightness/non-manifold edges and, with --repair, writes a
print-only package under outputs/print without replacing canonical outputs/parts files.

Run:
    rtk uv run python studies/xl430_lowcost/validate_print_readiness.py
    rtk uv run python studies/xl430_lowcost/validate_print_readiness.py --repair
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
import numpy as np
import trimesh

_STUDY_DIR = Path(__file__).resolve().parent
_PARTS_DIR = _STUDY_DIR / "parts"
for _p in (_STUDY_DIR, _PARTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cadre import PartIntent, checks, cylinder_faces, parametric  # noqa: E402
import domain  # noqa: E402
from parts import gripper_moving_part  # noqa: E402

_CADRE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PARTS_DIR = _CADRE_ROOT / "outputs" / "parts"
DEFAULT_PRINT_DIR = _CADRE_ROOT / "outputs" / "print"

PRINT_CANDIDATES = [
    "shoulder_to_elbow_xl430",
    "elbow_to_wrist_extension_xl430",
    "gripper_static_part_xl430",
    "gripper_moving_part_xl430",
    "shoulder_rotation_orig",
]

EXCLUDED_DESIGNS = {
    "elbow_to_wrist_xl430": (
        "2026-09-18 geometry review blocked this model: an outside rounded "
        "profile was interpreted as a bore, so the existing generated mesh is stale."
    ),
}


def _edge_anomalies(mesh: trimesh.Trimesh) -> tuple[int, list[dict]]:
    unique, counts = np.unique(mesh.edges_sorted, axis=0, return_counts=True)
    bad = unique[counts != 2]
    bad_counts = counts[counts != 2]
    examples = []
    for edge, count in zip(bad[:8], bad_counts[:8]):
        pts = mesh.vertices[edge]
        examples.append(
            {
                "occurrences": int(count),
                "points_mm": pts.round(6).tolist(),
                "midpoint_mm": pts.mean(axis=0).round(6).tolist(),
                "length_mm": round(float(np.linalg.norm(pts[0] - pts[1])), 6),
            }
        )
    return int(len(bad)), examples


def _mesh_report(path: Path) -> dict:
    mesh = trimesh.load(path, force="mesh")
    bad_edges, examples = _edge_anomalies(mesh)
    volume = round(float(mesh.volume), 3) if mesh.is_volume else None
    return {
        "file": str(path),
        "exists": path.exists(),
        "watertight": bool(mesh.is_watertight),
        "is_volume": bool(mesh.is_volume),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "triangles": int(len(mesh.faces)),
        "vertices": int(len(mesh.vertices)),
        "bbox_mm": [round(float(x), 3) for x in mesh.bounding_box.extents],
        "volume_mm3": volume,
        "nonmanifold_or_boundary_edges": bad_edges,
        "edge_anomaly_examples": examples,
    }


def _copy_pair(name: str, parts_dir: Path, print_dir: Path) -> dict:
    print_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for suffix in (".stl", ".step"):
        src = parts_dir / f"{name}{suffix}"
        dst = print_dir / f"{name}{suffix}"
        if src.exists():
            shutil.copy2(src, dst)
            copied.append(str(dst))
    return {"strategy": "copy_canonical", "files": copied}


def _repair_gripper_moving(print_dir: Path) -> dict:
    print_dir.mkdir(parents=True, exist_ok=True)
    intent = PartIntent.load(gripper_moving_part.INTENT)
    model = gripper_moving_part.make_gripper_moving_printable(domain.XL430, intent)
    stem = print_dir / "gripper_moving_part_xl430_print"
    files = parametric.export(model, stem, formats=("step", "stl"))

    repaired_step = Path(f"{stem}.step")
    source_step = DEFAULT_PARTS_DIR / "gripper_moving_part_xl430.step"
    source = cylinder_faces(source_step)
    repaired = cylinder_faces(repaired_step)
    family_checks = []
    for source_family in source["hole_families"]:
        candidates = [
            f
            for f in repaired["hole_families"]
            if abs(float(f["diameter"]) - float(source_family["diameter"])) <= 0.05
            and tuple(round(x, 1) for x in f["axis_dir"])
            == tuple(round(x, 1) for x in source_family["axis_dir"])
            and int(f["axes"]) == int(source_family["axes"])
        ]
        if not candidates:
            family_checks.append(
                {
                    "diameter_mm": source_family["diameter"],
                    "axes": source_family["axes"],
                    "passed": False,
                    "reason": "matching repaired family missing",
                }
            )
            continue
        best = min(
            (
                checks.hole_pattern_match(
                    source_family["centers"], f["centers"], tol_mm=0.15
                ),
                f,
            )
            for f in candidates
        )
        match, repaired_family = best
        family_checks.append(
            {
                "diameter_mm": source_family["diameter"],
                "axes": source_family["axes"],
                "passed": bool(match.passed),
                "center_nn_mm": match.value,
                "source_faces": source_family["faces"],
                "repaired_faces": repaired_family["faces"],
            }
        )

    return {
        "strategy": "print_only_outer_wall_relief",
        "edge_relief_mm": gripper_moving_part.PRINT_EDGE_RELIEF_MM,
        "rationale": (
            "Canonical gripper_moving_part has exact tangencies where the phi16 horn "
            "boss seat touches +X and -Y outer walls, producing two non-manifold STL "
            "edges. The print artifact adds material only outside those two walls; "
            "functional cylindrical families are checked against the canonical STEP."
        ),
        "files": files,
        "family_checks": family_checks,
        "family_preservation_passed": all(item["passed"] for item in family_checks),
    }


def _run(
    parts_dir: Path = DEFAULT_PARTS_DIR,
    print_dir: Path = DEFAULT_PRINT_DIR,
    repair: bool = False,
) -> tuple[int, dict]:
    parts_dir = Path(parts_dir)
    print_dir = Path(print_dir)
    part_reports = []
    package = {}

    for name in PRINT_CANDIDATES:
        stl = parts_dir / f"{name}.stl"
        step = parts_dir / f"{name}.step"
        item = {
            "name": name,
            "stl": str(stl),
            "step": str(step),
            "step_exists": step.exists(),
        }
        if not stl.exists():
            item.update({"passed": False, "reason": "stl missing"})
            part_reports.append(item)
            continue
        item["mesh"] = _mesh_report(stl)
        item["passed"] = bool(
            item["mesh"]["watertight"]
            and item["mesh"]["is_volume"]
            and item["mesh"]["nonmanifold_or_boundary_edges"] == 0
        )
        part_reports.append(item)

        if repair:
            if item["passed"]:
                package[name] = _copy_pair(name, parts_dir, print_dir)
            elif name == "gripper_moving_part_xl430":
                package[name] = _repair_gripper_moving(print_dir)
                repaired = _mesh_report(
                    print_dir / "gripper_moving_part_xl430_print.stl"
                )
                package[name]["repaired_mesh"] = repaired
                item["repair_passed"] = bool(
                    repaired["watertight"]
                    and repaired["is_volume"]
                    and repaired["nonmanifold_or_boundary_edges"] == 0
                    and package[name]["family_preservation_passed"]
                )
            else:
                item["repair_passed"] = False
                package[name] = {"strategy": "none", "reason": "no repair rule defined"}

    blocking_failures = [
        item
        for item in part_reports
        if not item.get("passed", False) and not item.get("repair_passed", False)
    ]
    result = {
        "schema": "xl430-print-readiness/v0",
        "parts_dir": str(parts_dir),
        "print_dir": str(print_dir),
        "repair_enabled": bool(repair),
        "passed": len(blocking_failures) == 0,
        "excluded_designs": EXCLUDED_DESIGNS,
        "blocking_failures": [
            {
                "name": item["name"],
                "reason": item.get(
                    "reason", "mesh is not print-ready and no repair passed"
                ),
                "mesh": item.get("mesh"),
            }
            for item in blocking_failures
        ],
        "parts": part_reports,
        "package": package,
    }
    if repair:
        print_dir.mkdir(parents=True, exist_ok=True)
        report_path = print_dir / "print_readiness_report.json"
        report_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        result["report"] = str(report_path)
    return (0 if result["passed"] else 2), result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parts-dir", type=Path, default=DEFAULT_PARTS_DIR)
    parser.add_argument("--print-dir", type=Path, default=DEFAULT_PRINT_DIR)
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--fail-on-error", action="store_true")
    args = parser.parse_args(argv)
    code, result = _run(args.parts_dir, args.print_dir, args.repair)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code if args.fail_on_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
