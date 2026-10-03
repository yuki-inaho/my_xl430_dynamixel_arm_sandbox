"""Prototype liaison-style records for fastening interface preservation.

The CAD paper's liaison concept describes a relation between two mating parts using
couplings, mountings, and fastening sets. This prototype is deliberately smaller: it
wraps the existing reference-vs-candidate hole-family alignment check into a liaison-like
JSON record, so later assembly-level work has a concrete structure to grow into.

Paper:
    "Liaison-Based Enriched CAD Model Representation for Assembly Tasks"
    Computer-Aided Design & Applications, 2024
    DOI: https://doi.org/10.14733/cadaps.2024.1045-1062

Important limitation:
    The two "parts" here are a reference STEP and a generated candidate STEP in the same
    local frame. This proves preservation of the candidate side of a future liaison, not
    a full assembly mating proof against the actual motor/horn/link CAD.

Example:
    rtk uv run python studies/xl430_lowcost/build_liaison_interfaces.py --fail-on-mismatch
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from cadre import PartIntent

import validate_fastening_interfaces as vfi

PAPER_TITLE = "Liaison-Based Enriched CAD Model Representation for Assembly Tasks"
PAPER_DOI = "https://doi.org/10.14733/cadaps.2024.1045-1062"
INTENT = Path(__file__).resolve().parent / "intent" / "elbow_to_wrist_extension.yaml"


def _axis_key(axis: Iterable[float]) -> tuple[float, float, float]:
    return tuple(round(float(x), 1) for x in axis)


def _feature_specs() -> list[dict]:
    intent = PartIntent.load(INTENT)
    features = {feature.name: feature for feature in intent.features}

    upstream = features["upstream_horn_mount"].constraints
    relief = features["upstream_partial_relief"].constraints
    downstream = features["downstream_mount"].constraints

    return [
        {
            "liaison_id": "elbow_to_wrist_extension.upstream_horn_mount",
            "interface_role": "upstream horn/link fastening",
            "mating_part": "upstream horn or link; not loaded in this prototype",
            "feature": "upstream_horn_mount",
            "feature_type": "mounting",
            "mounting_type": "hole-pattern preservation",
            "diameter_mm": float(upstream["hole_diameter_mm"]),
            "axis_dir": _axis_key(upstream["horn_axis_dir"]),
            "screw": upstream.get("screw"),
            "hole_function": upstream.get("hole_function"),
            "through": bool(upstream["through"]),
            "blind_depth_mm": upstream.get("blind_depth_mm"),
            "fastener_set_status": "candidate-side only; actual fastener/mating CAD not checked",
        },
        {
            "liaison_id": "elbow_to_wrist_extension.upstream_partial_relief",
            "interface_role": "upstream clipped relief preservation",
            "mating_part": "unknown clearance/relief counterpart; not treated as a fastener",
            "feature": "upstream_partial_relief",
            "feature_type": "relief",
            "mounting_type": "relief preservation",
            "diameter_mm": float(relief["diameter_mm"]),
            "axis_dir": _axis_key(relief["axis_dir"]),
            "screw": None,
            "hole_function": "relief",
            "through": bool(relief["through"]),
            "blind_depth_mm": relief.get("blind_depth_mm"),
            "fastener_set_status": "not a fastening set until mating intent is proven",
        },
        {
            "liaison_id": "elbow_to_wrist_extension.downstream_mount",
            "interface_role": "downstream link fastening",
            "mating_part": "downstream link; not loaded in this prototype",
            "feature": "downstream_mount",
            "feature_type": "mounting",
            "mounting_type": "hole-pattern preservation",
            "diameter_mm": float(downstream["hole_diameter_mm"]),
            "axis_dir": _axis_key(downstream["mount_axis_dir"]),
            "screw": downstream.get("screw"),
            "hole_function": downstream.get("hole_function"),
            "through": bool(downstream["through"]),
            "blind_depth_mm": downstream.get("blind_depth_mm"),
            "fastener_set_status": "candidate-side only; actual fastener/mating CAD not checked",
        },
    ]


def _family_result_by_key(validation: dict) -> dict[tuple[float, tuple[float, float, float]], dict]:
    by_key = {}
    for family in validation["families"]:
        key = (
            round(float(family["key"]["diameter_mm"]), 2),
            tuple(float(x) for x in family["key"]["axis_dir"]),
        )
        by_key[key] = family
    return by_key


def _build_liaison(spec: dict, family: dict | None) -> dict:
    if family is None:
        mounting = {
            "feature": spec["feature"],
            "mounting_type": spec["mounting_type"],
            "passed": False,
            "reason": "feature family not found in validation result",
            "diameter_mm": spec["diameter_mm"],
            "axis_dir": list(spec["axis_dir"]),
        }
    else:
        mounting = {
            "feature": spec["feature"],
            "feature_type": spec["feature_type"],
            "mounting_type": spec["mounting_type"],
            "passed": bool(family["passed"]),
            "diameter_mm": spec["diameter_mm"],
            "axis_dir": list(spec["axis_dir"]),
            "screw": spec["screw"],
            "hole_function": spec["hole_function"],
            "through": spec["through"],
            "blind_depth_mm": spec["blind_depth_mm"],
            "reference_axes": family["reference_axes"],
            "candidate_axes": family["candidate_axes"],
            "reference_faces": family["reference_faces"],
            "candidate_faces": family["candidate_faces"],
            "diameter_delta_mm": family["diameter_delta_mm"],
            "center_nn_mm": family["center_nn_mm"],
            "center_detail": family["center_detail"],
            "reference_centers": family["reference_centers"],
            "candidate_centers_after_transform": family["candidate_centers_after_transform"],
        }

    return {
        "id": spec["liaison_id"],
        "kind": "reference_candidate_interface_preservation",
        "scope_note": (
            "Prototype liaison record: candidate-side interface preservation only; "
            "not a full assembly mating liaison."
        ),
        "parts": {
            "reference": "hardware/follower/step/elbow_to_wrist_extension.step",
            "candidate": "outputs/parts/elbow_to_wrist_extension_xl430.step",
            "mating_part": spec["mating_part"],
        },
        "couplings": [
            {
                "type": "same-frame overlay",
                "contact_status": "not evaluated",
                "axis_dir": list(spec["axis_dir"]),
                "note": "face contact and actual mating part geometry are deferred to assembly overlay",
            }
        ],
        "mountings": [mounting],
        "fastener_set": {
            "status": spec["fastener_set_status"],
            "screw": spec["screw"],
            "screw_length_depth_check": "not_checked",
            "head_clearance_check": "not_checked",
            "tool_access_check": "not_checked",
        },
        "passed": bool(mounting["passed"]),
    }


def _run(
    reference: Path = vfi.DEFAULT_REFERENCE,
    candidate: Path = vfi.DEFAULT_CANDIDATE,
    candidate_translate: tuple[float, float, float] = (0.0, 0.0, 0.0),
    center_tol_mm: float = 0.15,
    diameter_tol_mm: float = 0.1,
    fail_on_mismatch: bool = False,
) -> tuple[int, dict]:
    _, validation = vfi._run(
        reference=reference,
        candidate=candidate,
        candidate_translate=candidate_translate,
        center_tol_mm=center_tol_mm,
        diameter_tol_mm=diameter_tol_mm,
        fail_on_mismatch=False,
    )
    families = _family_result_by_key(validation)
    liaisons = []
    for spec in _feature_specs():
        key = (round(float(spec["diameter_mm"]), 2), tuple(float(x) for x in spec["axis_dir"]))
        liaisons.append(_build_liaison(spec, families.get(key)))

    passed = bool(validation["passed"] and all(liaison["passed"] for liaison in liaisons))
    result = {
        "schema": "liaison-interface-prototype/v0",
        "paper_inspiration": {
            "title": PAPER_TITLE,
            "doi": PAPER_DOI,
        },
        "passed": passed,
        "validation_summary": {
            "reference": validation["reference"],
            "candidate": validation["candidate"],
            "candidate_translate_mm": validation["candidate_translate_mm"],
            "worst_center_nn_mm": validation["worst_center_nn_mm"],
            "tolerances": validation["tolerances"],
        },
        "liaisons": liaisons,
        "limits": [
            "Does not load the actual mating motor/horn/link CAD.",
            "Does not compute planar contact faces or contact area.",
            "Does not check screw length vs blind depth, head clearance, or tool access.",
            "Use this as a candidate-side preservation gate before assembly-level liaison extraction.",
        ],
    }
    code = 0 if passed or not fail_on_mismatch else 2
    return code, result


def _parse_vec3(value: str) -> tuple[float, float, float]:
    parts = [float(x.strip()) for x in value.split(",") if x.strip()]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("expected comma-separated vector x,y,z")
    return (parts[0], parts[1], parts[2])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, default=vfi.DEFAULT_REFERENCE)
    parser.add_argument("--candidate", type=Path, default=vfi.DEFAULT_CANDIDATE)
    parser.add_argument("--candidate-translate", type=_parse_vec3, default=(0.0, 0.0, 0.0))
    parser.add_argument("--center-tol-mm", type=float, default=0.15)
    parser.add_argument("--diameter-tol-mm", type=float, default=0.1)
    parser.add_argument("--fail-on-mismatch", action="store_true")
    args = parser.parse_args(argv)
    code, result = _run(
        reference=args.reference,
        candidate=args.candidate,
        candidate_translate=args.candidate_translate,
        center_tol_mm=args.center_tol_mm,
        diameter_tol_mm=args.diameter_tol_mm,
        fail_on_mismatch=args.fail_on_mismatch,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
