"""Validate fastening-interface hole alignment between STEP models.

This checker is intentionally narrower than a visual CAD review: it answers whether
the cylindrical functional interfaces in a reference STEP and a candidate STEP still
share the same hole-family diameters, axes, counts, and center patterns in the same
coordinate frame. Use it before claiming that a generated part can still be bolted to
the same mating motor/link/horn interface.

Assembly-liaison context:
    This is the low-level hole-family preservation gate used before building richer
    liaison records inspired by "Liaison-Based Enriched CAD Model Representation for
    Assembly Tasks" (Computer-Aided Design & Applications, 2024).
    DOI: https://doi.org/10.14733/cadaps.2024.1045-1062

Examples:

    # Red-pattern demo: intentionally shift candidate centers by +1mm in Y.
    rtk uv run python studies/xl430_lowcost/validate_fastening_interfaces.py \
      --candidate-translate 0,1,0 --fail-on-mismatch

    # Original STEP against itself.
    rtk uv run python studies/xl430_lowcost/validate_fastening_interfaces.py \
      --candidate ../../hardware/follower/step/elbow_to_wrist_extension.step \
      --fail-on-mismatch

    # Current generated no-op XL430-named part against the original STEP.
    rtk uv run python studies/xl430_lowcost/validate_fastening_interfaces.py --fail-on-mismatch
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import numpy as np

from cadre import cylinder_faces, checks

PAPER_TITLE = "Liaison-Based Enriched CAD Model Representation for Assembly Tasks"
PAPER_DOI = "https://doi.org/10.14733/cadaps.2024.1045-1062"
ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ROOT.parents[1]
DEFAULT_REFERENCE = REPO_ROOT / "hardware" / "follower" / "step" / "elbow_to_wrist_extension.step"
DEFAULT_CANDIDATE = ROOT / "outputs" / "parts" / "elbow_to_wrist_extension_xl430.step"


def _axis_key(axis: Iterable[float]) -> tuple[float, float, float]:
    return tuple(round(float(x), 1) for x in axis)


def _family_key(family: dict) -> tuple[float, tuple[float, float, float]]:
    return (round(float(family["diameter"]), 2), _axis_key(family["axis_dir"]))


def _translate_centers(centers: Iterable[Iterable[float]], vector: Iterable[float]) -> list[list[float]]:
    v = np.asarray(tuple(vector), float)
    return [(np.asarray(c, float) + v).round(6).tolist() for c in centers]


def _families_by_key(step: Path) -> dict[tuple[float, tuple[float, float, float]], dict]:
    report = cylinder_faces(step)
    if not report.get("available"):
        raise RuntimeError(f"B-rep inspection unavailable for {step}")
    families: dict[tuple[float, tuple[float, float, float]], dict] = {}
    for family in report["hole_families"]:
        key = _family_key(family)
        if key in families:
            raise RuntimeError(f"duplicate family key {key} in {step}; refine case config")
        families[key] = family
    return families


def _compare_family(
    key: tuple[float, tuple[float, float, float]],
    reference: dict,
    candidate: dict | None,
    candidate_translate: tuple[float, float, float],
    center_tol_mm: float,
    diameter_tol_mm: float,
) -> dict:
    if candidate is None:
        return {
            "key": {"diameter_mm": key[0], "axis_dir": key[1]},
            "passed": False,
            "reason": "candidate family missing",
            "reference_axes": reference["axes"],
            "candidate_axes": None,
            "reference_faces": reference["faces"],
            "candidate_faces": None,
            "center_nn_mm": None,
            "diameter_delta_mm": None,
        }

    candidate_centers = _translate_centers(candidate["centers"], candidate_translate)
    center_match = checks.hole_pattern_match(
        reference["centers"],
        candidate_centers,
        tol_mm=center_tol_mm,
    )
    diameter_delta = abs(float(reference["diameter"]) - float(candidate["diameter"]))
    axes_match = int(reference["axes"]) == int(candidate["axes"])
    diameter_match = diameter_delta <= diameter_tol_mm
    passed = bool(center_match.passed and axes_match and diameter_match)
    return {
        "key": {"diameter_mm": key[0], "axis_dir": key[1]},
        "passed": passed,
        "reference_axes": int(reference["axes"]),
        "candidate_axes": int(candidate["axes"]),
        "reference_faces": int(reference["faces"]),
        "candidate_faces": int(candidate["faces"]),
        "reference_centers": reference["centers"],
        "candidate_centers_after_transform": candidate_centers,
        "center_nn_mm": center_match.value,
        "center_detail": center_match.detail,
        "diameter_delta_mm": round(diameter_delta, 6),
        "axes_match": axes_match,
        "diameter_match": diameter_match,
    }


def _run(
    reference: Path = DEFAULT_REFERENCE,
    candidate: Path = DEFAULT_CANDIDATE,
    candidate_translate: tuple[float, float, float] = (0.0, 0.0, 0.0),
    center_tol_mm: float = 0.15,
    diameter_tol_mm: float = 0.1,
    fail_on_mismatch: bool = False,
) -> tuple[int, dict]:
    reference = Path(reference)
    candidate = Path(candidate)
    ref_families = _families_by_key(reference)
    cand_families = _families_by_key(candidate)

    family_results = []
    passed = True
    worst = 0.0
    for key in sorted(ref_families):
        result = _compare_family(
            key,
            ref_families[key],
            cand_families.get(key),
            candidate_translate,
            center_tol_mm,
            diameter_tol_mm,
        )
        family_results.append(result)
        passed = passed and bool(result["passed"])
        if result["center_nn_mm"] is not None:
            worst = max(worst, float(result["center_nn_mm"]))

    extra_keys = sorted(set(cand_families) - set(ref_families))
    if extra_keys:
        passed = False
    result = {
        "reference": str(reference),
        "candidate": str(candidate),
        "liaison_reference": {
            "paper": PAPER_TITLE,
            "doi": PAPER_DOI,
            "role": "low-level hole-family preservation gate before liaison extraction",
        },
        "candidate_translate_mm": [float(x) for x in candidate_translate],
        "tolerances": {
            "center_tol_mm": float(center_tol_mm),
            "diameter_tol_mm": float(diameter_tol_mm),
        },
        "passed": bool(passed),
        "worst_center_nn_mm": round(worst, 6),
        "families": family_results,
        "extra_candidate_families": [
            {"diameter_mm": key[0], "axis_dir": key[1]} for key in extra_keys
        ],
        "interpretation": (
            "PASS means same-frame fastening hole-family centers/diameters/axes match. "
            "It does not replace full assembly occurrence overlay or screw-length checks."
        ),
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
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
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
