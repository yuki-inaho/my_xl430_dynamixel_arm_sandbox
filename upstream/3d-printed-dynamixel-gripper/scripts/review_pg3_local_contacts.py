"""Supplement raw PG3 contact errors by one explicit rigid coordinate change.

The same inverse arm placement and inverse drive rotation apply to every
operand. No alignment, healing, fuzzy tolerance, part deletion or automatic
fallback is performed. All original reports remain authoritative history.
"""

import argparse
import json
import math
from pathlib import Path

from gripper_design.pg2 import digest
from scripts.assembly_io import read_step
from scripts.review_pg3 import inspect_pairs


def reexpress(shape, angle):
    if not math.isfinite(angle) or not 25 <= angle <= 135:
        raise ValueError("finite relative mechanism angle within 25..135 required")
    return (
        shape.translate((0.2, -234.9, -164.6))
        .rotate((0, 0, 0), (0, 1, 0), -90)
        .rotate((0, 0, 0), (0, 0, 1), 90 - angle)
    )


def review_local_pairs(shapes, pairs, angle):
    names = {n for pair in pairs for n in pair}
    if not names or not names <= set(shapes):
        raise ValueError("nonempty pairs with existing occurrences required")
    local = {n: reexpress(shapes[n], angle) for n in sorted(names)}
    return inspect_pairs(local, pairs)


def run(checkpoint, out):
    if out.exists():
        raise FileExistsError(out)
    manifest = json.loads((checkpoint / "review.json").read_text())
    report = {
        "checker_sha256": digest(Path(__file__)),
        "base_checker_sha256": digest(Path(__file__).with_name("review_pg3.py")),
        "scope": "all_raw_non_PASS_PG3_to_PG3_pairs_in_each_saved_pose",
        "coordinate_change": [
            "translate all operands by (0.2,-234.9,-164.6) mm",
            "rotate all operands about origin Y by -90 degrees",
            "rotate all operands about origin Z by (90 - relative mechanism angle) degrees",
        ],
        "geometry_healed": False,
        "tolerances_changed": False,
        "poses": {},
        "installation_approved": False,
        "continuous_motion_verified": False,
    }
    for label, angle in (("open", 25), ("mid", 90), ("closed", 135)):
        assembly = checkpoint / f"arm_camera_{label}_CANDIDATE.step"
        raw_path = checkpoint / f"collisions_{label}.json"
        for path in (assembly, raw_path):
            if digest(path) != manifest["output_sha256"][path.name]:
                raise ValueError(f"checkpoint hash mismatch: {path}")
        loaded = read_step(assembly)[2]
        shapes = {r.name: r.world for r in loaded}
        if len(loaded) != len(shapes):
            raise ValueError("ambiguous occurrence identity")
        raw = json.loads(raw_path.read_text())
        unresolved = [r for r in raw["pairs"] if r["status"] != "PASS"]
        selected = [r for r in unresolved if all(r[n].startswith("PG3_") for n in ("a", "b"))]
        pairs = [(r["a"], r["b"]) for r in selected]
        check = review_local_pairs(shapes, pairs, angle)
        negative = {}
        for name, shift in (("PG3_horn_bolt_0", -0.5), ("PG3_pivot_drive_R_nut", 0.2)):
            moved = shapes | {name: shapes[name].translate((shift, 0, 0))}
            negative[name] = {
                "world_X_displacement_mm": shift,
                **review_local_pairs(moved, [("PG3_crank", name)], angle),
            }
        negative_pass = all(v["pairs"][0]["status"] == "FAIL" for v in negative.values())
        report["poses"][label] = {
            "assembly_sha256": digest(assembly),
            "raw_report_sha256": digest(raw_path),
            "relative_mechanism_angle_deg": angle,
            "raw_selected_pairs": selected,
            "raw_unresolved_outside_scope": [r for r in unresolved if r not in selected],
            "reexpressed_check": check,
            "negative_controls": negative,
            "negative_controls_detected": negative_pass,
            "accepted_clear_pairs": [
                [r["a"], r["b"]] for r in check["pairs"] if negative_pass and r["status"] == "PASS"
            ],
            "all_selected_contacts_clear": negative_pass
            and all(r["status"] == "PASS" for r in check["pairs"]),
        }
        print(label, check["counts"], "negative controls", negative_pass, flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return 2  # Supplemental evidence is not installation acceptance.


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
