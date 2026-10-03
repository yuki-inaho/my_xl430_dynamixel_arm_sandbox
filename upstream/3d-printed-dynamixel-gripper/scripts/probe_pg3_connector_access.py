"""Check external straight plug-access corridors, not seated mating or cable routing."""

import argparse
import json
from pathlib import Path

import cadquery as cq

from gripper_design.pg2 import digest
from scripts.assembly_io import bounds, read_step
from scripts.review_pg3 import inspect_pairs

# Rear planes and header centres belong to the saved R3 arm pose, not arbitrary
# joint configurations. Reject another pose rather than reusing stale planes.
HEADER_CENTRES = {
    "ARM_M05_ref03": (10.25, 159.7, 178.7),
    "ARM_M05_ref04": (-10.65, 159.7, 178.7),
    "ARM_M06_ref03": (-5.4, 220.8, 154.15),
    "ARM_M06_ref04": (-5.4, 220.8, 175.05),
}


def corridors(shapes):
    result, evidence = {}, {}
    for unit, axis, rear_plane in (("M05", 1, 147.9), ("M06", 0, -17.2)):
        for index in (3, 4):
            name = f"ARM_{unit}_ref{index:02d}"
            bb = bounds(shapes[name])
            size = [bb[i + 3] - bb[i] for i in range(3)]
            width_axis = 2 if axis == 1 else 1
            thickness_axis = next(i for i in range(3) if i not in (axis, width_axis))
            if any(
                abs(size[i] - expected) > 1e-5
                for i, expected in ((axis, 9.2), (width_axis, 10), (thickness_axis, 3.8))
            ):
                raise ValueError(f"header dimensions/orientation differ: {name}")
            low = [(bb[i] + bb[i + 3]) / 2 for i in range(3)]
            if any(abs(low[i] - HEADER_CENTRES[name][i]) > 1e-5 for i in range(3)):
                raise ValueError(f"header pose differs from fixed case-plane contract: {name}")
            low[axis] = rear_plane - 40
            low[width_axis] -= 9.5 / 2
            low[thickness_axis] -= 3.8 / 2
            dimensions = [0, 0, 0]
            dimensions[axis] = 40
            dimensions[width_axis] = 9.5
            dimensions[thickness_axis] = 3.8
            label = f"PORT_ACCESS_{unit}_{index}"
            result[label] = cq.Solid.makeBox(*dimensions, tuple(low))
            evidence[label] = {
                "header_occurrence": name,
                "header_bbox_mm": bb,
                "corridor_bbox_mm": bounds(result[label]),
                "source": "references/jst-eh/SOURCE.md",
                "scope": "nominal housing cross-section external to case, no hand margin",
                "mated_depth_or_cable_bend_confirmed": False,
            }
    return result, evidence


def run(assembly, out):
    if out.exists():
        raise FileExistsError(out)
    rows = read_step(assembly)[2]
    shapes = {r.name: r.world for r in rows}
    if len(rows) != len(shapes):
        raise ValueError("ambiguous occurrence identity")
    corridor, evidence = corridors(shapes)
    checks = inspect_pairs(shapes | corridor, [(a, b) for a in corridor for b in shapes])
    report = {
        "assembly_sha256": digest(assembly),
        "checker_sha256": digest(Path(__file__)),
        "catalog_sha256": digest(Path(__file__).resolve().parents[1] / "references/jst-eh/eEH.pdf"),
        "corridors": evidence,
        "checks": checks,
        "wiring_approved": False,
        "physical_assembly_verified": False,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(checks["counts"]))
    for row in checks["pairs"]:
        if row["status"] != "PASS":
            print(json.dumps(row))
    return 2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("assembly", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    raise SystemExit(run(a.assembly, a.out))
