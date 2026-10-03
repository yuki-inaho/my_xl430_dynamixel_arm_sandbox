"""Export and audit a removable bench aid, not an installation release."""

import argparse
import json
import math
import sys
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh

from gripper_design.pg2 import digest
from gripper_design.pg3_bench_support import build_support, to_print, to_world
from scripts.assembly_io import bounds, read_step
from scripts.review_pg3 import inspect_pairs
from scripts.review_pg3_bench_cluster import bench_cluster
from scripts.review_pg3_mechanism_insertion import review_stage
from scripts.review_pg3_washer_contacts import controlled_containment, opposed_seat


def linkage(shapes):
    prepared = bench_cluster(shapes)
    bodies = {n: s for n, s in prepared["movers"].items() if n != "PG3_horn_spacer"}
    if len(bodies) != 17:
        raise ValueError("17-part linkage without separately held horn spacer required")
    return bodies, prepared["bench_tools"]


def inspect_support(world, design, shapes):
    bodies, tools = linkage(shapes)
    report = {
        "body_pairs": inspect_pairs(bodies | {"JIG": world}, [("JIG", n) for n in bodies]),
        "tool_pairs": inspect_pairs(
            bodies | tools | {"JIG": world},
            [(t, n) for t in tools for n in [*bodies, "JIG"]],
        ),
        "nut_seats": {},
        "present_occurrences": sorted(bodies),
        "tool_occurrences": sorted(tools),
        "installation_approved": False,
    }
    dimensions = design["dimensions"]
    area = math.pi * (
        dimensions["post_outer_radius_mm"] ** 2 - dimensions["tip_hole_radius_mm"] ** 2
    )
    for name, seat in design["seats"].items():
        try:
            result = opposed_seat(world, shapes[name], seat["nut_back_x_mm"], area)
        except Exception as exc:  # noqa: BLE001 - Preserve failed measurements as errors.
            result = {"status": "ERROR", "pass_contact": False, "reason": str(exc)}
        report["nut_seats"][name] = result
    report["nominal_static_pass"] = (
        report["body_pairs"]["counts"] == {"PASS": 17}
        and report["tool_pairs"]["counts"] == {"PASS": 144}
        and all(v["pass_contact"] for v in report["nut_seats"].values())
    )
    return report


def run(checkpoint, out, render_images=True):
    path = checkpoint / "arm_camera_mid_CANDIDATE.step"
    manifest = json.loads((checkpoint / "review.json").read_text())
    if digest(path) != manifest["output_sha256"][path.name]:
        raise ValueError("saved input SHA mismatch")
    rows = read_step(path)[2]
    shapes = {r.name: r.world for r in rows}
    if len(shapes) != len(rows):
        raise ValueError("ambiguous occurrence identity")
    design = build_support(shapes)
    out.mkdir(parents=True, exist_ok=False)
    step, stl = out / "bench_support_CANDIDATE.step", out / "bench_support_CANDIDATE.stl"
    cq.exporters.export(design["print_shape"], str(step))
    cq.exporters.export(design["print_shape"], str(stl), tolerance=0.02, angularTolerance=0.1)
    loaded = cq.importers.importStep(str(step)).val()
    equivalence = controlled_containment(design["print_shape"], loaded, equal=True)
    mesh = trimesh.load_mesh(stl, process=True)
    mesh_report = {
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "component_count": len(mesh.split(only_watertight=False)),
        "bounds_mm": mesh.bounds.tolist(),
        "positive_volume": bool(mesh.volume > 0),
        "step_bounds_error_mm": float(np.max(np.abs(mesh.bounds.ravel() - bounds(loaded)))),
    }
    mesh_report["nominal_pass"] = (
        mesh_report["watertight"]
        and mesh_report["winding_consistent"]
        and mesh_report["component_count"] == 1
        and mesh_report["positive_volume"]
        and mesh_report["step_bounds_error_mm"] <= 0.02
    )
    world = to_world(loaded, design["frame"])
    report = inspect_support(world, design, shapes)
    report.update(
        assembly_sha256=digest(path),
        frame=design["frame"],
        dimensions=design["dimensions"],
        seats=design["seats"],
        step_equivalence=equivalence,
        mesh=mesh_report,
        print_release_approved=False,
    )
    bodies, _ = linkage(shapes)
    print("static", report["nominal_static_pass"], flush=True)
    report["removal"] = review_stage(bodies, {"JIG": world}, (60, 0, 0))
    report["nominal_geometry_pass"] = (
        report["nominal_static_pass"]
        and equivalence["pass"]
        and mesh_report["nominal_pass"]
        and report["removal"]["continuous_translation_volume_clear"]
        and not report["removal"]["actual_penetration_samples"]
    )
    report["scope"] = "saved-mid bench aid; fixed-pose linkage lift along source +X60mm"
    report["limits"] = [
        "4 loose nuts require hand placement; posts provide axial support, not capture or lateral location",
        "final-linkage removal does not validate the staged loading of loose nuts, hosts, links and screws",
        "articulated linkage pose must be maintained; hand envelopes and actual tools are unverified",
        "horn spacer absent on bench; held separately during subsequent arm insertion",
        "0.7mm annular walls, layer-rounded post heights, PLA deformation and printed fit unverified",
        "screw threads, nut standards, torque and preload remain unverified",
        "jig must be removed before installation; no arm, camera, wiring or motor-motion approval",
    ]
    if render_images:
        from PIL import Image

        from scripts.render_cad import render

        views = {}
        local_bodies = [(to_print(s, design["frame"]), (0.85, 0.49, 0.16)) for s in bodies.values()]
        for name, content, direction in (
            ("jig_iso", [(loaded, (0.19, 0.65, 0.61))], (1, 1, 1)),
            ("bench_iso", [(loaded, (0.19, 0.65, 0.61)), *local_bodies], (1, 1, 1)),
            ("bench_side", [(loaded, (0.19, 0.65, 0.61)), *local_bodies], (0, 1, 0)),
            ("bench_top", [(loaded, (0.19, 0.65, 0.61)), *local_bodies], (0, 0, 1)),
        ):
            target = out / f"{name}.png"
            render(content, target, direction=direction, size=(1200, 900))
            pixels = np.asarray(Image.open(target).convert("RGB"))
            views[name] = {
                "direction": direction,
                "sha256": digest(target),
                "rgb_channel_std": pixels.std(axis=(0, 1)).tolist(),
                "nonblank": bool(np.min(pixels.std(axis=(0, 1))) > 5),
            }
        report["views"] = views
    root = Path.cwd().resolve()
    dependencies = set()
    for module in list(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename:
            absolute = Path(filename).resolve()
            if absolute.is_relative_to(root) and absolute.suffix == ".py":
                relative = absolute.relative_to(root)
                if relative.parts[0] in {"scripts", "gripper_design", "camera_jig"}:
                    dependencies.add(relative.as_posix())
    report["dependencies"] = {p: digest(Path(p)) for p in sorted(dependencies | {"uv.lock"})}
    report["output_sha256"] = {p.name: digest(p) for p in (step, stl)}
    (out / "review.json").write_text(json.dumps(report, indent=2) + "\n")
    print("nominal geometry", report["nominal_geometry_pass"], "installation false", flush=True)
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.out, not args.no_render))
