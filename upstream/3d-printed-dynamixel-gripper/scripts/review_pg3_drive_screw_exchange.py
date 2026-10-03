"""Check material paths for temporary drive screws and final washer exchange."""

import argparse
import json
import math
from pathlib import Path

import cadquery as cq

from gripper_design.pg2 import digest
from scripts.assembly_io import bounds, read_step
from scripts.review_pg3_local_contacts import reexpress
from scripts.review_pg3_mechanism_insertion import review_stage
from scripts.review_pg3_motor_partition import PADDING, radial_distance
from scripts.review_pg3_pivot_stacks import pick, profiles
from scripts.review_pg3_temporary_drive_screws import candidate
from scripts.review_pg3_washer_contacts import controlled_containment, cylinder, finite_solid
from scripts.verify_pg3_service_stages import mechanism_stages


def exchange_stages(shapes):
    prepared = candidate(shapes)
    screws = prepared["temporary_screws"]
    stages = {}
    bench = {n: s for n, s in prepared["stages"]["G2"][0].items() if n not in screws}
    for side in ("R", "L"):
        name = f"PG3_pivot_drive_{side}_bolt"
        stages[f"bench_{side}_bolt"] = ({name: screws[name]}, dict(bench), "insert")
        bench[name] = screws[name]
    movers, obstacles, _ = prepared["stages"]["G4_L_link"]
    present = obstacles | movers
    full = mechanism_stages(shapes, horn_l_key=True)["G4_link_pivots"][0]
    pending_carriage = {
        f"PG3_pivot_carriage_{s}_{part}" for s in ("R", "L") for part in ("bolt", "washer")
    }
    pending_drive = {f"PG3_pivot_drive_{s}_washer" for s in ("R", "L")}
    if set(present) != set(full) - pending_carriage - pending_drive or any(
        s is not (screws[n] if n in screws else shapes[n]) for n, s in present.items()
    ):
        raise ValueError("complete temporary installation state required")
    for side in ("R", "L"):
        bolt = f"PG3_pivot_drive_{side}_bolt"
        removed = present.pop(bolt)
        if removed is not screws[bolt]:
            raise ValueError("only the temporary target screw may be removed")
        stages[f"{side}_remove_temporary"] = ({bolt: removed}, dict(present), "remove")
        for label, name in (("washer", f"PG3_pivot_drive_{side}_washer"), ("final_bolt", bolt)):
            if name in present:
                raise ValueError("fastener addition cannot replace an installed part")
            stages[f"{side}_add_{label}"] = ({name: shapes[name]}, dict(present), "insert")
            present[name] = shapes[name]
    if set(present) != set(full) - pending_carriage or any(
        present[n] is not shapes[n] for n in present
    ):
        raise ValueError("final drive fasteners must match saved inventory and geometry")
    return stages


def axial_bolt_path_bound(bolt, obstacle, length=60):
    """Bound each complete cylinder sweep against the whole obstacle boundary."""
    if not math.isfinite(length) or length <= 0:
        raise ValueError("finite positive X travel required")
    finite_solid(bolt)
    finite_solid(obstacle)
    p = profiles(bolt)
    shaft, head = pick(p, 1, "convex"), pick(p, 1.9, "convex")
    cover = cylinder(shaft).fuse(cylinder(head))
    contained = controlled_containment(bolt, cover)
    result = {"status": "UNPROVEN", "whole_bolt_containment": contained, "components": []}
    if not contained["pass"]:
        return result
    bb = bounds(obstacle)
    for label, profile in (("shaft", shaft), ("head", head)):
        axis = cq.Edge.makeLine(
            (bb[0] - 1, *profile["axis_yz_mm"]), (bb[3] + 1, *profile["axis_yz_mm"])
        )
        faces = [
            {"face": i, "distance_mm": radial_distance(f, axis)}
            for i, f in enumerate(obstacle.Faces())
        ]
        inner = max(0, min(f["distance_mm"] for f in faces) - PADDING)
        radius = profile["radius_mm"] + PADDING
        low, high = profile["span_x_mm"]
        swept = [low - PADDING, high + length + PADDING]
        overlap = max(0, min(swept[1], bb[3] + PADDING) - max(swept[0], bb[0] - PADDING))
        upper = math.pi * max(0, radius**2 - inner**2) * overlap
        result["components"].append(
            {
                "name": label,
                "source_profile": profile,
                "swept_span_x_mm": swept,
                "whole_obstacle_faces": faces,
                "radial_void_lower_bound_mm": inner,
                "axial_overlap_upper_mm": overlap,
                "volume_upper_bound_mm3": upper,
            }
        )
    residual = max(contained["residuals_mm3"])
    upper = sum(c["volume_upper_bound_mm3"] for c in result["components"]) + residual
    result.update(
        status="BOUNDED_TRANSLATION" if upper <= 1e-4 else "UNPROVEN",
        continuous_volume_upper_bound_mm3=upper,
        containment_residual_allowance_mm3=residual,
        bound_scope="uniform instantaneous intersection bound at every translation parameter; not the swept union volume of containment residuals",
        padding_mm=PADDING,
        basis="finite outward material: any occupied axial ray exits via a boundary; all boundary-axis distances bound a full-length radial void; two cylinder sweeps cover the entire bolt",
        limits="nominal smooth proxy translation only; not screw rotation or physical thread engagement",
    )
    return result


def supplemented_path(movers, obstacles):
    if len(movers) != 1:
        raise ValueError("one moving fastener required")
    a, mover = next(iter(movers.items()))
    world = review_stage(movers, obstacles, (60, 0, 0))
    local = review_stage(
        {a: reexpress(mover, 90)}, {n: reexpress(s, 90) for n, s in obstacles.items()}, (0, 0, 60)
    )
    bounds_by_frame = []
    for proof in (world, local):
        values = {tuple(p): 0.0 for p in proof["far_pairs"]}
        values.update(
            {(r["a"], r["b"]): r["selected_volume_upper_bound_mm3"] for r in proof["near_pairs"]}
        )
        if set(values) != {(a, n) for n in obstacles}:
            raise ValueError("incomplete path pair coverage")
        bounds_by_frame.append(values)
    extra, selected = {}, {}
    for b, obstacle in obstacles.items():
        pair = (a, b)
        values = [v[pair] for v in bounds_by_frame]
        if a.endswith("_bolt") and min(values) > 1e-4:
            try:
                proof = axial_bolt_path_bound(mover, obstacle)
            except Exception as exc:  # noqa: BLE001
                proof = {"status": "ERROR", "reason": f"{type(exc).__name__}: {exc}"}
            extra[b] = proof
            if proof["status"] == "BOUNDED_TRANSLATION":
                values.append(proof["continuous_volume_upper_bound_mm3"])
        selected[b] = min(values)
    upper = sum(selected.values())
    no_penetration = (
        not world["actual_penetration_samples"] and not local["actual_penetration_samples"]
    )
    return {
        "world": world,
        "common_reexpression_mid90": local,
        "axial_bolt_bounds": extra,
        "selected_pair_upper_bounds_mm3": selected,
        "summed_upper_bound_mm3": upper,
        "supplemented_material_path_clear": upper <= 1e-4 and no_penetration,
        "nut_retention_proven": False,
    }


def run(checkpoint, out):
    if out.exists():
        raise FileExistsError(out)
    path = checkpoint / "arm_camera_mid_CANDIDATE.step"
    manifest = json.loads((checkpoint / "review.json").read_text())
    if digest(path) != manifest["output_sha256"][path.name]:
        raise ValueError("saved input SHA mismatch")
    rows = read_step(path)[2]
    shapes = {r.name: r.world for r in rows}
    if len(shapes) != len(rows):
        raise ValueError("ambiguous occurrence identity")
    report = {"assembly_sha256": digest(path), "stages": {}, "installation_approved": False}
    for name, (movers, obstacles, action) in exchange_stages(shapes).items():
        result = supplemented_path(movers, obstacles)
        result["operation"] = action
        result["physical_path_direction"] = (
            "offset_to_seat" if action == "insert" else "seat_to_offset"
        )
        report["stages"][name] = result
        print(
            name,
            action,
            result["supplemented_material_path_clear"],
            result["summed_upper_bound_mm3"],
            flush=True,
        )
    report["scope"] = (
        "fixed saved mid; two bench temporary-screw paths and six installed drive washer-exchange paths; intervening body stages are checked separately"
    )
    report["limits"] = [
        "all nuts and links are held at saved positions as an explicit unproven retention prerequisite",
        "removal reverses the same geometric path; real screws need rotation and thread identification",
        "canonical carriage retainers are not installed until after these drive operations",
        "no hand/tool/actual screw/PLA strength/cable/other pose approval",
        "raw world and rigidly reexpressed errors are preserved, not healed",
    ]
    report["checker_sha256"] = digest(Path(__file__))
    report["dependencies"] = {
        p: digest(Path(p))
        for p in (
            "scripts/review_pg3_temporary_drive_screws.py",
            "scripts/review_pg3_mechanism_insertion.py",
            "scripts/review_pg3_slider_link_insertion.py",
            "scripts/review_pg3_local_contacts.py",
            "scripts/verify_pg3_service_stages.py",
            "scripts/certify_pg3_insertion.py",
            "scripts/review_pg3.py",
            "scripts/assembly_io.py",
            "scripts/review_pg3_motion_clearance.py",
            "scripts/review_pg3_motor_partition.py",
            "scripts/review_pg3_pivot_stacks.py",
            "scripts/review_pg3_washer_contacts.py",
            "gripper_design/interface_envelopes.py",
            "gripper_design/rotational_envelopes.py",
            "gripper_design/pg2.py",
            "gripper_design/pg3.py",
            "gripper_design/pg3_installation.py",
            "uv.lock",
        )
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
