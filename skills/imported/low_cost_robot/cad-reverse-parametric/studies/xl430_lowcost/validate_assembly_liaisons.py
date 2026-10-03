"""Characterize actual assembly-side liaisons around connector solid 116.

This is the first assembly-level check beyond standalone part preservation. It loads
`hardware/follower/step/arm.step`, treats solid 116 as the connector corresponding to
the current extension investigation, and compares its cylindrical mounting features with
nearby actual CAD solids in the assembly.

Paper:
    "Liaison-Based Enriched CAD Model Representation for Assembly Tasks"
    Computer-Aided Design & Applications, 2024
    DOI: https://doi.org/10.14733/cadaps.2024.1045-1062

The checker is deliberately conservative: if the mating hole axes/centers are not aligned,
then screw length/depth and tool access are reported as failed/unknown instead of being
declared OK from an unrelated fastener.

Example:
    rtk uv run python studies/xl430_lowcost/validate_assembly_liaisons.py --fail-on-mismatch
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import cadquery as cq

from OCP.BRepExtrema import BRepExtrema_DistShapeShape

from cadre import PartIntent, checks
from cadre.geometry import DEFAULT_SCREW_BANDS
from cadre.probes import _raw_cylinders, group_cylinder_holes

PAPER_TITLE = "Liaison-Based Enriched CAD Model Representation for Assembly Tasks"
PAPER_DOI = "https://doi.org/10.14733/cadaps.2024.1045-1062"
ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ROOT.parents[1]
DEFAULT_ASSEMBLY = REPO_ROOT / "hardware" / "follower" / "step" / "arm.step"
INTENT = Path(__file__).resolve().parent / "intent" / "elbow_to_wrist_extension.yaml"


def _axis_key(axis: Iterable[float]) -> tuple[float, float, float]:
    return tuple(round(float(x), 1) for x in axis)


def _bbox(shape) -> dict:
    bb = shape.BoundingBox()
    return {
        "xmin": round(bb.xmin, 3), "xmax": round(bb.xmax, 3),
        "ymin": round(bb.ymin, 3), "ymax": round(bb.ymax, 3),
        "zmin": round(bb.zmin, 3), "zmax": round(bb.zmax, 3),
        "xlen": round(bb.xlen, 3), "ylen": round(bb.ylen, 3), "zlen": round(bb.zlen, 3),
    }


def _shape_distance(a, b) -> float:
    dss = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    dss.Perform()
    if not dss.IsDone():
        return float("nan")
    return round(float(dss.Value()), 6)


def _families(shape) -> list[dict]:
    cyls, _, _ = _raw_cylinders([shape], DEFAULT_SCREW_BANDS)
    return group_cylinder_holes(cyls, DEFAULT_SCREW_BANDS)


def _family(shape, diameter: float, axis=(1.0, 0.0, 0.0), expected_axes: int | None = None) -> dict:
    matches = [
        f for f in _families(shape)
        if abs(float(f["diameter"]) - diameter) <= 0.25
        and _axis_key(f["axis_dir"]) == _axis_key(axis)
        and (expected_axes is None or int(f["axes"]) == expected_axes)
    ]
    if not matches:
        raise RuntimeError(f"family not found: d~{diameter} axis={axis} expected_axes={expected_axes}")
    return sorted(matches, key=lambda f: (abs(float(f["diameter"]) - diameter), -int(f["axes"])))[0]


def _mounting_result(
    name: str,
    connector_family: dict,
    mating_family: dict,
    center_tol_mm: float,
    diameter_policy: str,
) -> dict:
    center = checks.hole_pattern_match(
        connector_family["centers"],
        mating_family["centers"],
        tol_mm=center_tol_mm,
    )
    diameter_delta = round(abs(float(connector_family["diameter"]) - float(mating_family["diameter"])), 6)
    passed = bool(center.passed)
    return {
        "name": name,
        "passed": passed,
        "center_tol_mm": center_tol_mm,
        "center_nn_mm": center.value,
        "center_detail": center.detail,
        "diameter_policy": diameter_policy,
        "diameter_delta_mm": diameter_delta,
        "connector": {
            "diameter_mm": connector_family["diameter"],
            "screw": connector_family["screw"],
            "axes": connector_family["axes"],
            "faces": connector_family["faces"],
            "axis_dir": connector_family["axis_dir"],
            "centers": connector_family["centers"],
        },
        "mating": {
            "diameter_mm": mating_family["diameter"],
            "screw": mating_family["screw"],
            "axes": mating_family["axes"],
            "faces": mating_family["faces"],
            "axis_dir": mating_family["axis_dir"],
            "centers": mating_family["centers"],
        },
    }


def _nearby_fasteners(solids: list, ids: list[int], axis=(1.0, 0.0, 0.0)) -> list[dict]:
    out = []
    for sid in ids:
        for family in _families(solids[sid]):
            screw = family.get("screw")
            if screw and _axis_key(family["axis_dir"]) == _axis_key(axis):
                out.append({
                    "solid_id": sid,
                    "diameter_mm": family["diameter"],
                    "screw": screw,
                    "axes": family["axes"],
                    "faces": family["faces"],
                    "centers": family["centers"],
                    "bbox": _bbox(solids[sid]),
                })
    return out


def _fastener_checks(
    mounting: dict,
    expected_screw: str,
    blind_depth_mm: float | None,
    nearby_fasteners: list[dict],
) -> dict:
    if not mounting["passed"]:
        return {
            "expected_screw": expected_screw,
            "nearby_fasteners": nearby_fasteners,
            "screw_length_depth_check": {
                "status": "fail",
                "reason": "mating hole centers are not aligned; screw insertion depth is not meaningful yet",
                "blind_depth_mm": blind_depth_mm,
            },
            "tool_access_check": {
                "status": "fail",
                "reason": "tool axis cannot be certified until a matching fastener/hole axis is aligned",
            },
        }
    if expected_screw is None:
        return {
            "expected_screw": None,
            "nearby_fasteners": nearby_fasteners,
            "screw_length_depth_check": {"status": "not_applicable", "reason": "not a fastening feature"},
            "tool_access_check": {"status": "not_applicable", "reason": "not a fastening feature"},
        }
    return {
        "expected_screw": expected_screw,
        "nearby_fasteners": nearby_fasteners,
        "screw_length_depth_check": {
            "status": "unknown",
            "reason": "hole centers align, but exact screw model engagement length is not resolved by this prototype",
            "blind_depth_mm": blind_depth_mm,
        },
        "tool_access_check": {
            "status": "unknown",
            "reason": "requires screwdriver/head clearance corridor, not only axis coincidence",
        },
    }


def _run(
    assembly: Path = DEFAULT_ASSEMBLY,
    target_solid_id: int = 116,
    center_tol_mm: float = 0.25,
    fail_on_mismatch: bool = False,
) -> tuple[int, dict]:
    intent = PartIntent.load(INTENT)
    features = {feature.name: feature for feature in intent.features}
    upstream_intent = features["upstream_horn_mount"].constraints
    downstream_intent = features["downstream_mount"].constraints

    solids = cq.importers.importStep(str(assembly)).solids().vals()
    target = solids[target_solid_id]
    connector_upstream = _family(target, 1.8, expected_axes=4)
    connector_downstream = _family(target, 2.2, expected_axes=2)

    # Actual CAD candidates observed around the connector in arm.step:
    # - solids 72/79 are the opposing horn/idler-like plates carrying the 4-hole pattern.
    # - solid 103 carries the closest downstream 2-hole M2 tap pattern; solid 101 is the
    #   opposite case solid with related openings.
    upstream_mating = _family(solids[72], 1.6, expected_axes=4)
    downstream_mating = _family(solids[103], 2.0, expected_axes=4)
    downstream_mating_2 = {
        **downstream_mating,
        "axes": 2,
        "faces": 2,
        "centers": [
            c for c in downstream_mating["centers"]
            if 199.0 <= float(c[1]) <= 200.5
        ],
    }

    upstream_mounting = _mounting_result(
        "connector phi1.8 tap diamond vs actual horn phi1.6 pattern",
        connector_upstream,
        upstream_mating,
        center_tol_mm,
        "connector is tap/pilot, mating horn opening may be smaller; center alignment is the gate",
    )
    downstream_mounting = _mounting_result(
        "connector phi2.2 clearance pair vs downstream M2-tap pair",
        connector_downstream,
        downstream_mating_2,
        center_tol_mm,
        "clearance-vs-tap diameter difference is acceptable only after center alignment",
    )

    upstream_distances = {sid: _shape_distance(target, solids[sid]) for sid in [72, 79]}
    downstream_distances = {sid: _shape_distance(target, solids[sid]) for sid in [101, 103]}

    liaisons = [
        {
            "id": "assembly.connector_116.upstream_horn_pair",
            "kind": "actual_assembly_liaison_characterization",
            "parts": {
                "connector_solid_id": target_solid_id,
                "mating_solid_ids": [72, 79],
                "mating_role": "opposing horn/idler-like plates with 4-hole pattern",
            },
            "contact": {
                "status": "contact_or_intersection" if min(upstream_distances.values()) == 0.0 else "separated",
                "min_distance_mm": min(upstream_distances.values()),
                "per_solid_distance_mm": upstream_distances,
                "note": "BRepExtrema distance 0 means contact or overlap; contact area is not yet classified",
            },
            "mountings": [upstream_mounting],
            "fastener_set": _fastener_checks(
                upstream_mounting,
                upstream_intent.get("screw"),
                upstream_intent.get("blind_depth_mm"),
                _nearby_fasteners(solids, [74, 75, 78, 81]),
            ),
        },
        {
            "id": "assembly.connector_116.downstream_mount_pair",
            "kind": "actual_assembly_liaison_characterization",
            "parts": {
                "connector_solid_id": target_solid_id,
                "mating_solid_ids": [101, 103],
                "mating_role": "downstream case/link solids with M2 tap pair candidate",
            },
            "contact": {
                "status": "contact_or_intersection" if min(downstream_distances.values()) == 0.0 else "separated",
                "min_distance_mm": min(downstream_distances.values()),
                "per_solid_distance_mm": downstream_distances,
                "note": "BRepExtrema distance 0 means contact or overlap; contact area is not yet classified",
            },
            "mountings": [downstream_mounting],
            "fastener_set": _fastener_checks(
                downstream_mounting,
                downstream_intent.get("screw"),
                None,
                _nearby_fasteners(solids, [108, 109]),
            ),
        },
    ]
    passed = all(
        liaison["contact"]["min_distance_mm"] <= 0.05
        and all(m["passed"] for m in liaison["mountings"])
        and liaison["fastener_set"]["screw_length_depth_check"]["status"] in {"pass", "not_applicable"}
        and liaison["fastener_set"]["tool_access_check"]["status"] in {"pass", "not_applicable"}
        for liaison in liaisons
    )
    result = {
        "schema": "assembly-liaison-characterization/v0",
        "paper_inspiration": {
            "title": PAPER_TITLE,
            "doi": PAPER_DOI,
        },
        "assembly": str(assembly),
        "target_solid_id": target_solid_id,
        "target_bbox": _bbox(target),
        "center_tol_mm": center_tol_mm,
        "passed": bool(passed),
        "liaisons": liaisons,
        "interpretation": (
            "This is an actual assembly-side characterization. Current result is expected "
            "to be stricter than standalone part preservation and may fail when arm.step "
            "uses a different connector occurrence or mismatched mating pattern."
        ),
        "source_notes": [
            "ROBOTIS e-Manual warns to choose screw length according to mounting point depth.",
            "This prototype reports depth/tool checks as fail/unknown when aligned fastener axes are not found.",
        ],
    }
    code = 0 if passed or not fail_on_mismatch else 2
    return code, result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assembly", type=Path, default=DEFAULT_ASSEMBLY)
    parser.add_argument("--target-solid-id", type=int, default=116)
    parser.add_argument("--center-tol-mm", type=float, default=0.25)
    parser.add_argument("--fail-on-mismatch", action="store_true")
    args = parser.parse_args(argv)
    code, result = _run(
        assembly=args.assembly,
        target_solid_id=args.target_solid_id,
        center_tol_mm=args.center_tol_mm,
        fail_on_mismatch=args.fail_on_mismatch,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
