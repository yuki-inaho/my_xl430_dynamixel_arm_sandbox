"""Audit actual saved mating shapes with the current seat/depth checker.

This can add stronger measurements to a frozen generation run without rewriting
its provenance or claiming the old generator included these additional checks.
"""

import argparse
import json
from pathlib import Path

from gripper_design.pg2 import digest
from gripper_design.pg3 import shape_signature_difference
from gripper_design.pg3_installation import (
    case_attachment_report,
    horn_attachment_report,
    horn_hardware,
    support_candidate,
    support_hardware,
)
from scripts.assembly_io import read_step


def verify(path):
    rows = read_step(path)[2]
    shapes = {r.name: r.world for r in rows}
    if len(rows) != len(shapes):
        raise ValueError("ambiguous occurrence names")
    support = shapes["ARM_P06_PG3_support"]
    expected = {"ARM_P06_PG3_support": support_candidate(), **support_hardware(), **horn_hardware()}
    signatures = {n: shape_signature_difference(s, shapes[n]) for n, s in expected.items()}
    same = all(
        s["vertex_distance_mm"] < 1e-5
        and s["volume_error_mm3"] < 1e-3
        and s["vertex_count_equal"]
        and s["face_count_equal"]
        for s in signatures.values()
    )
    case = case_attachment_report(shapes["PG3_XL430_fixed"])
    horn = horn_attachment_report(shapes["ARM_M05_ref00"], support)
    hardware = {
        n: support.intersect(shapes[n]).Volume() for n in expected if n != "ARM_P06_PG3_support"
    }
    return {
        "assembly_sha256": digest(path),
        "assembly_path": str(path.resolve()),
        "checker_sha256": digest(Path(__file__)),
        "checker_module_sha256": digest(
            Path(__file__).resolve().parents[1] / "gripper_design/pg3_installation.py"
        ),
        "geometry_matches_current_candidate": same,
        "signatures": signatures,
        "case": case,
        "horn": horn,
        "hardware_support_intersection_mm3": hardware,
        "attachment_geometry_pass": same
        and case["nominal_geometry_pass"]
        and horn["nominal_geometry_pass"]
        and all(abs(v) < 1e-5 for v in hardware.values()),
        "scope": "saved_CAD_axes_seats_depth_bearing_footprint_and_support_clearance",
        "physical_assembly_verified": False,
        "strength_verified": False,
        "full_interference_scan_replaced_by_this_report": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assembly", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    r = verify(args.assembly)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(r, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: r[k]
                for k in (
                    "geometry_matches_current_candidate",
                    "attachment_geometry_pass",
                    "physical_assembly_verified",
                )
            },
            indent=2,
        )
    )
    raise SystemExit(0 if r["attachment_geometry_pass"] else 2)
