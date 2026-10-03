"""Challenge local mating regions against conservative covers of actual saved motors."""

import argparse
import json
from pathlib import Path

import cadquery as cq

from gripper_design.interface_envelopes import axial_boss_cover, bounded_contact
from gripper_design.pg2 import digest
from gripper_design.pg3_installation import case_attachment_report, horn_attachment_report
from scripts.assembly_io import bounds, read_step
from scripts.review_pg3_components import inspect_components


def run(assembly, out):
    if out.exists():
        raise FileExistsError(out)
    loaded = read_step(assembly)[2]
    s = {r.name: r.world for r in loaded}
    if len(loaded) != len(s):
        raise ValueError("ambiguous occurrence identity")
    motor = s["ARM_M05_ref00"]
    support = s["ARM_P06_PG3_support"]
    m05_cover, m05_faces = axial_boss_cover(motor, 1, 183.9, (-0.2, 164.6), 4)
    horn_cover, horn_faces = axial_boss_cover(s["PG3_XL430_horn"], 0, 18.8, (234.9, 164.6), 4)
    horn_fit = horn_attachment_report(motor, support)
    case_fit = case_attachment_report(s["PG3_XL430_fixed"])
    if not horn_fit["nominal_geometry_pass"] or not case_fit["nominal_geometry_pass"]:
        raise ValueError("actual mating axes, seats or depths failed")
    box = bounds(s["PG3_XL430_fixed"])
    case_cover = {
        "case_aabb": cq.Solid.makeBox(*(box[i + 3] - box[i] for i in range(3)), tuple(box[:3]))
    }
    report = {
        "assembly_sha256": digest(assembly),
        "checker_sha256": digest(Path(__file__)),
        "cover_code_sha256": digest(
            Path(__file__).resolve().parents[1] / "gripper_design/interface_envelopes.py"
        ),
        "M05_cover": m05_faces,
        "PG3_horn_cover": horn_faces,
        "support_vs_M05_cover": inspect_components(
            cq.Compound.makeCompound(list(m05_cover.values())), support
        ),
        "spacer_vs_horn_cover": inspect_components(
            cq.Compound.makeCompound(list(horn_cover.values())), s["PG3_horn_spacer"]
        ),
        "horn_fit": horn_fit,
        "case_fit": case_fit,
        "fasteners": {},
        "physical_assembly_verified": False,
        "installation_approved": False,
    }
    for i, row in enumerate(horn_fit["bores"]):
        x, z = row["axis_xz_mm"]
        bottom = row["horn_cylindrical_span_y_mm"][0]
        seat = horn_fit["actual_horn_seat"]["coordinate_mm"]
        roi = cq.Solid.makeCylinder(1, seat - bottom, (x, bottom, z), (0, 1, 0))
        name = f"ARM_P06_horn_bolt_{i}_ENVELOPE"
        report["fasteners"][name] = {
            "region": {
                "kind": "nominal_M2_tapped_bore",
                "axis": [0, 1, 0],
                "origin_mm": [x, bottom, z],
                "radius_mm": 1,
                "length_mm": seat - bottom,
                "actual_face": row["horn_face"],
            },
            **bounded_contact(s[name], roi, m05_cover),
        }
    for i, row in enumerate(case_fit["bores"]):
        x, y = row["axis_xy_mm"]
        seat = case_fit["actual_case_seat"]["coordinate_mm"]
        depth = row["cylindrical_span_z_mm"][1] - seat
        roi = cq.Solid.makeCylinder(1.3, depth, (x, y, seat))
        name = f"ARM_P06_case_tapper_{i}_ENVELOPE"
        report["fasteners"][name] = {
            "region": {
                "kind": "M2.6_thread_forming_envelope_in_phi2.1_pilot",
                "axis": [0, 0, 1],
                "origin_mm": [x, y, seat],
                "radius_mm": 1.3,
                "length_mm": depth,
                "actual_face": row["face"],
            },
            **bounded_contact(s[name], roi, case_cover),
        }
    report["outside_thread_regions_all_clear"] = all(
        r["outside_allowed_region_clear"] for r in report["fasteners"].values()
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "support": report["support_vs_M05_cover"]["status"],
                "spacer": report["spacer_vs_horn_cover"]["status"],
                "outside_threads_clear": report["outside_thread_regions_all_clear"],
            }
        )
    )
    return 2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("assembly", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    raise SystemExit(run(a.assembly, a.out))
