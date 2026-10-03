"""Validate the preservation contract for elbow_to_wrist_extension.

This is a study-specific acceptance helper for the 2026-06-13 corrective decision:
until a user-approved local change mask exists, the XL430 variant of this organic
historyless STEP must remain a geometric no-op and must not introduce the rejected R12
circular collar.

Run:
    uv run python studies/xl430_lowcost/validate_extension_preservation.py
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

_STUDY_DIR = Path(__file__).resolve().parent
_PARTS_DIR = _STUDY_DIR / "parts"
for _p in (_STUDY_DIR, _PARTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cadre import (  # noqa: E402
    EquivalenceThresholds,
    PartIntent,
    checks,
    compare,
    cylinder_faces,
    parametric,
    verdict,
)
import domain  # noqa: E402
from parts import elbow_to_wrist_extension as extension  # noqa: E402

_CADRE_ROOT = Path(__file__).resolve().parents[2]
_REPO = _CADRE_ROOT.parents[1]
_HW_STEP = _REPO / "hardware/follower/step/elbow_to_wrist_extension.step"
_HW_STL = _REPO / "hardware/follower/stl/elbow_to_wrist_extension.stl"


def _family_match(real_step: Path, candidate_step: Path) -> tuple[bool, list[str]]:
    real = cylinder_faces(real_step)["hole_families"]
    candidate = cylinder_faces(candidate_step)["hole_families"]

    def key(f):
        return (round(f["diameter"], 2), tuple(round(x, 1) for x in f["axis_dir"]))

    rb, cb = defaultdict(list), defaultdict(list)
    for f in real:
        rb[key(f)].append(f)
    for f in candidate:
        cb[key(f)].append(f)

    report: list[str] = []
    ok = set(rb) == set(cb)
    if not ok:
        report.append(f"family key set mismatch real={sorted(rb)} candidate={sorted(cb)}")
    for k in rb:
        real_families = rb[k]
        candidate_families = cb.get(k, [])
        if len(real_families) != len(candidate_families):
            ok = False
            report.append(f"{k}: family count {len(real_families)} vs {len(candidate_families)}")
            continue
        remaining = list(candidate_families)
        for real_family in real_families:
            best, best_index = None, -1
            for i, candidate_family in enumerate(remaining):
                if candidate_family["axes"] != real_family["axes"]:
                    continue
                match = checks.hole_pattern_match(
                    real_family["centers"], candidate_family["centers"], tol_mm=0.15
                )
                if match.passed and (best is None or match.value < best.value):
                    best, best_index = match, i
            if best is None:
                ok = False
                report.append(f"{k} axes={real_family['axes']}: no center-matching family")
                continue
            dia_delta = abs(real_family["diameter"] - remaining[best_index]["diameter"])
            family_ok = dia_delta <= 0.1
            ok = ok and family_ok
            report.append(
                f"{k} axes={real_family['axes']}: dia_delta={dia_delta:.3f} "
                f"center_nn={best.value} pass={family_ok}"
            )
            remaining.pop(best_index)
    return ok, report


def _run(samples: int) -> tuple[int, dict]:
    intent = PartIntent.load(extension.INTENT)
    features = {feature.name: feature for feature in intent.features}
    preservation = features["original_shape_preservation"].constraints

    result = {
        "part": "elbow_to_wrist_extension",
        "source_step": str(_HW_STEP),
        "source_stl": str(_HW_STL),
        "checks": {},
    }

    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        orig = extension.make_extension(domain.XL330, intent)
        swapped = extension.make_extension(domain.XL430, intent)
        parametric.export(orig, out / "candidate_orig", formats=("step", "stl"))
        parametric.export(swapped, out / "candidate_xl430", formats=("step", "stl"))

        c_a1 = compare(_HW_STL, out / "candidate_orig.stl", samples=samples)
        c_a1_verdict = verdict(c_a1, EquivalenceThresholds())
        result["checks"]["C_A1_original_shape"] = {
            "passed": c_a1_verdict["equivalent"],
            "bbox_delta_mm": c_a1["bbox_delta_mm"],
            "surface_distance": c_a1["surface_distance"],
            "volume_delta_pct": c_a1["volume_delta_pct"],
            "verdict": c_a1_verdict,
        }

        c_a2_ok, c_a2_report = _family_match(_HW_STEP, out / "candidate_orig.step")
        result["checks"]["C_A2_hole_families"] = {
            "passed": c_a2_ok,
            "report": c_a2_report,
        }

        swap_cmp = compare(out / "candidate_orig.stl", out / "candidate_xl430.stl", samples=samples)
        swap_verdict = verdict(swap_cmp, EquivalenceThresholds())
        result["checks"]["swap_is_noop_until_change_mask"] = {
            "passed": swap_verdict["equivalent"],
            "bbox_delta_mm": swap_cmp["bbox_delta_mm"],
            "surface_distance": swap_cmp["surface_distance"],
            "volume_delta_pct": swap_cmp["volume_delta_pct"],
            "verdict": swap_verdict,
        }

        families = cylinder_faces(out / "candidate_orig.step")["hole_families"]
        diameters = sorted({round(float(f["diameter"]), 2) for f in families})
        result["checks"]["no_unapproved_phi24_collar"] = {
            "passed": 24.0 not in diameters,
            "diameters": diameters,
        }

    result["checks"]["local_edit_inactive"] = {
        "passed": preservation["active_local_edit"] is False,
        "active_local_edit": preservation["active_local_edit"],
        "mask_status": preservation.get("change_mask_status"),
        "proposal_status": preservation.get("proposed_local_edit_mask", {}).get("status"),
    }

    all_passed = all(check["passed"] for check in result["checks"].values())
    result["passed"] = all_passed
    return (0 if all_passed else 2), result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=4000)
    args = parser.parse_args(argv)
    code, result = _run(args.samples)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
