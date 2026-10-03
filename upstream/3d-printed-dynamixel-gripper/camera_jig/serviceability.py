"""Conservative nominal tool envelopes and discrete insertion checks, not approval."""

import argparse
import itertools
import json
from pathlib import Path

import cadquery as cq

from camera_jig.build import ARM, CAMERA_LOC, CX, collision_rows, sha
from camera_jig.spec import SPEC
from scripts.assembly_io import read_step


def screw_stack(length, grip, nut_thickness, pitch):
    remaining = length - grip - nut_thickness
    return {
        "length_mm": length,
        "grip_mm": grip,
        "nut_thickness_mm": nut_thickness,
        "tail_mm": remaining,
        "pitch_mm": pitch,
        "nominal_full_nut_and_one_thread": remaining >= pitch,
        "purchase_spec_confirmed": False,
    }


def tools():
    result = {}
    # Assumed envelopes, not manufacturer drawings: narrow shaft, then handle.
    for i, (x, y) in enumerate(itertools.product((-14.0, 14.0), repeat=2)):
        for side, z, direction, radius in (("head", 8.1, 1, 1.5), ("nut", -1.6, -1, 3.5)):
            shaft = cq.Solid.makeCylinder(radius, 75, (x, y, z), (0, 0, direction))
            handle = cq.Solid.makeCylinder(10, 30, (x, y, z + 75 * direction), (0, 0, direction))
            if side == "nut":
                shaft = shaft.cut(cq.Solid.makeCylinder(1.2, 6, (x, y, z), (0, 0, direction)))
            result[f"M2_{i}_{side}"] = shaft.fuse(handle).moved(CAMERA_LOC)
    for i, x in enumerate((CX - 28.5, CX + 28.5)):
        for side, y, direction, radius in (("head", 149.9, 1, 2.5), ("nut", 134.5, -1, 4.5)):
            shaft = cq.Solid.makeCylinder(radius, 75, (x, y, 188.6), (0, direction, 0))
            handle = cq.Solid.makeCylinder(
                10, 30, (x, y + 75 * direction, 188.6), (0, direction, 0)
            )
            if side == "nut":
                shaft = shaft.cut(cq.Solid.makeCylinder(1.7, 6, (x, y, 188.6), (0, direction, 0)))
            result[f"M3_{i}_{side}"] = shaft.fuse(handle)
    carrier = SPEC.clamp["interchangeable_carrier"]
    for i, (x, y) in enumerate(carrier["attachment_hole_centres_local_mm"]):
        shaft = cq.Solid.makeCylinder(1.5, 75, (x, y, -5.6), (0, 0, -1))
        handle = cq.Solid.makeCylinder(10, 30, (x, y, -80.6), (0, 0, -1))
        result[f"M2C_{i}_head"] = shaft.fuse(handle).moved(CAMERA_LOC)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--report-name", default="serviceability.json")
    args = parser.parse_args()
    run = args.run
    output = run / args.report_name
    if output.exists():
        raise FileExistsError(output)
    report = json.loads((run / "validation.json").read_text())
    for name, digest in report["output_sha256"].items():
        if sha(run / name) != digest:
            raise ValueError(f"Artifact changed: {name}")
    rows = read_step(run / "arm_with_jig_UNVALIDATED.step")[2]
    obstacles = {r.path: r.world for r in rows}
    evidence = []
    hits, errors = collision_rows(tools(), obstacles, non_solid_evidence=evidence)
    bench_obstacles = {k: v for k, v in obstacles.items() if "/JIG_" in k}
    bench_hits, bench_errors = collision_rows(
        {k: v for k, v in tools().items() if k.startswith(("M2_", "M2C_"))}, bench_obstacles
    )
    clamp_hits, clamp_errors = collision_rows(
        {k: v for k, v in tools().items() if k.startswith("M3_")}, obstacles
    )
    source = {r.path: r.world for r in read_step(ARM)[2]}
    insertions = []
    # Open-bottom jaw slots permit top-down installation. Sampled, NOT swept.
    preassembled = cq.Compound.makeCompound(
        [s for k, s in bench_obstacles.items() if "front_jaw" not in k and "M3" not in k]
    )
    jaw = cq.importers.importStep(str(run / "front_jaw_UNVALIDATED.step")).val()
    for name, shape in (("saddle_with_camera_and_M2", preassembled), ("front_jaw", jaw)):
        for dz in (0, 5, 10, 20, 40):
            h, e = collision_rows({name: shape.translate((0, 0, dz))}, source)
            insertions.append({"part": name, "offset_z_mm": dz, "collisions": h, "errors": e})
    result = {
        "scope": "nominal straight tools in saved R3 pose; five insertion samples per clamp part",
        "geometry_report_sha256": sha(run / "validation.json"),
        "code_sha256": sha(__file__),
        "screw_stacks": {
            "M2x10": screw_stack(10, 6.5, 1.6, 0.4),
            "M2x10_carrier": screw_stack(10, 7.0, 1.6, 0.4),
            "M3x16": screw_stack(16, 10, 2.4, 0.5),
        },
        "tool_envelopes": {
            "shaft_length_mm": 75,
            "handle_diameter_mm": 20,
            "handle_length_mm": 30,
            "shaft_radii_mm": {"M2_head": 1.5, "M2_nut": 3.5, "M3_head": 2.5, "M3_nut": 4.5},
        },
        "tool_collisions": hits,
        "tool_errors": errors,
        "camera_bench_preassembly": {"collisions": bench_hits, "errors": bench_errors},
        "clamp_on_arm": {"collisions": clamp_hits, "errors": clamp_errors},
        "nut_tool_tip_bore": {"depth_mm": 6, "M2_diameter_mm": 2.4, "M3_diameter_mm": 3.4},
        "non_solid_evidence": evidence,
        "insertion_samples": insertions,
        "continuous_insertion": "not_checked",
        "wrench_sweep_and_finger_room": "not_checked",
        "actual_tools_and_fasteners": "not_selected",
        "cable_and_connector_sweep": "unknown",
        "fabrication_approved": False,
    }
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    failed = hits or errors or any(r["collisions"] or r["errors"] for r in insertions)
    raise SystemExit(2 if failed else 0)


if __name__ == "__main__":
    main()
