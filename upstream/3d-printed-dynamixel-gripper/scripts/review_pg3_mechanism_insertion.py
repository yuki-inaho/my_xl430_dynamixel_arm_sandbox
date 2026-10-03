"""Body insertion into the saved PG3 assembly, separate from tool access."""

import argparse
import json
import math
from pathlib import Path

import cadquery as cq
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.TopAbs import TopAbs_OUT

from gripper_design.interface_envelopes import axial_boss_cover
from gripper_design.pg2 import _solid_only, digest
from scripts.assembly_io import bounds, read_step
from scripts.certify_pg3_insertion import certify_pair
from scripts.review_pg3 import inspect_pairs
from scripts.review_pg3_motion_clearance import EPSILON_MM, DistanceTo, certify_interval
from scripts.review_pg3_motor_partition import PADDING, radial_distance
from scripts.review_pg3_washer_contacts import finite_solid
from scripts.verify_pg3_service_stages import mechanism_stages


def split_stage(before, after, later):
    before_names, after_names, later = set(before), set(after), set(later)
    if not before_names <= after_names or not later <= after_names - before_names:
        raise ValueError("prior components must remain; later screws must be new additions")
    if any(before[n] is not after[n] for n in before_names):
        raise ValueError("stage must retain exact previous shape instances")
    moving = after_names - before_names - later
    if not moving:
        raise ValueError("nonempty body insertion required")
    return {n: after[n] for n in sorted(moving)}, dict(before), later


def insertion_stages(shapes):
    tool_stages = mechanism_stages(shapes, horn_l_key=True)
    before = {
        n: s
        for n, s in shapes.items()
        if n.startswith("ARM_") or n in {"PG3_XL430_fixed", "PG3_XL430_horn"}
    }
    result = {}
    for name, prefix in (("G1_frame_case", "PG3_case_tapper"), ("G2_horn_drive", "PG3_horn_bolt_")):
        after = tool_stages[name][0]
        later = {n for n in after if n.startswith(prefix)}
        result[name] = split_stage(before, after, later)
        before = after
    return result


def enclosure_bounds(shape):
    if not shape.isValid():
        raise ValueError("invalid geometry cannot define a material enclosure")
    for solid in shape.Solids():
        classifier = BRepClass3d_SolidClassifier(solid.wrapped)
        classifier.PerformInfinitePoint(1e-7)
        if (
            classifier.State() != TopAbs_OUT
            or not math.isfinite(solid.Volume())
            or solid.Volume() <= 0
        ):
            raise ValueError("finite positive material required before bounding")
    bb = bounds(shape)
    if not all(math.isfinite(v) for v in bb):
        raise ValueError("finite bounds required")
    if not _solid_only(shape):
        bb = [v - 1e-5 if i < 3 else v + 1e-5 for i, v in enumerate(bb)]
    return bb


def swept_bounds(shape, offset):
    if len(offset) != 3 or not all(math.isfinite(v) for v in offset):
        raise ValueError("finite 3D translation required")
    bb = enclosure_bounds(shape)
    return [bb[i] + min(offset[i], 0) for i in range(3)] + [
        bb[i + 3] + max(offset[i], 0) for i in range(3)
    ]


def far(first, second):
    return any(first[i + 3] < second[i] - 1e-7 or second[i + 3] < first[i] - 1e-7 for i in range(3))


def aabb_overlap_upper(first, second):
    if len(first) != 6 or len(second) != 6 or not all(math.isfinite(v) for v in [*first, *second]):
        raise ValueError("finite 3D bounds required")
    if any(bb[i] > bb[i + 3] for bb in (first, second) for i in range(3)):
        raise ValueError("inverted bounds")
    return math.prod(
        max(0, min(first[i + 3], second[i + 3]) - max(first[i], second[i])) for i in range(3)
    )


def distance_certificate(mover, obstacle, offset):
    swept_bounds(mover, offset)
    for shape in (mover, obstacle):
        if not shape.isValid() or not _solid_only(shape):
            raise ValueError("valid solid-only distance operands required")
        for solid in shape.Solids():
            classifier = BRepClass3d_SolidClassifier(solid.wrapped)
            classifier.PerformInfinitePoint(1e-7)
            if (
                classifier.State() != TopAbs_OUT
                or not math.isfinite(solid.Volume())
                or solid.Volume() <= 0
            ):
                raise ValueError("finite positive material required")
    speed = math.sqrt(sum(v * v for v in offset))
    to_obstacle = DistanceTo(obstacle)
    proof = certify_interval(
        lambda t: to_obstacle(mover.translate(tuple(t * v for v in offset))),
        speed,
        0,
        1,
        min_span=1 / 1024,
        max_checks=256,
    )
    if "unresolved_interval_rad" in proof:
        proof["unresolved_offset_fraction_interval"] = proof.pop("unresolved_interval_rad")
    proof.update(
        parameter="dimensionless offset fraction",
        speed_bound_mm_per_fraction=speed,
        basis="all points translate by t*offset; occupied distance is speed-Lipschitz",
        min_fraction_span=1 / 1024,
        maximum_distance_evaluations=256,
    )
    return proof


def axial_boss_insertion_certificate(mover, obstacle, offset, *, seat, centre, radius):
    if (
        len(offset) != 3
        or not all(math.isfinite(v) for v in offset)
        or offset[0] < 0
        or tuple(offset[1:]) != (0, 0)
    ):
        raise ValueError("positive-X translation only; no transverse motion or rotation")
    finite_solid(obstacle)
    finite_solid(mover)
    cover, evidence = axial_boss_cover(obstacle, 0, seat, centre, radius)
    box_upper = aabb_overlap_upper(swept_bounds(mover, offset), bounds(cover["case"]))
    bb = bounds(mover)
    axis = cq.Edge.makeLine((bb[0] - 1, *centre), (bb[3] + 1, *centre))
    # A positive-X ray from any finite material exits a boundary at the same
    # radius. Excluding ALL boundary from this cylinder excludes all material.
    faces = [
        {"face": i, "axis_distance_mm": radial_distance(f, axis)}
        for i, f in enumerate(mover.Faces())
    ]
    gap = min(r["axis_distance_mm"] for r in faces) - PADDING - evidence["boss_radius_mm"]
    void = {
        "all_boundary_faces": faces,
        "whole_material_radial_gap_lower_bound_mm": gap,
        "all_material_outside_boss_cylinder": gap > EPSILON_MM,
        "basis": "finite material positive-X exit ray preserves radial coordinate",
    }
    upper = box_upper if void["all_material_outside_boss_cylinder"] else None
    return {
        "status": "BOUNDED_TRANSLATION" if upper is not None and upper <= 1e-4 else "UNPROVEN",
        "whole_obstacle_cover": evidence,
        "entire_mover_axial_cylinder_check": void,
        "case_swept_overlap_upper_mm3": box_upper,
        "continuous_volume_upper_bound_mm3": upper,
        "basis": "X translation preserves complete radial void; finite boss is inside its infinite cylinder; whole case stays behind",
        "positive_clearance_proven": False,
    }


def review_stage(movers, obstacles, offset, *, boss_pair=None):
    if set(movers) & set(obstacles):
        raise ValueError("movers cannot be their own stationary obstacles")
    boxes = {n: enclosure_bounds(s) for n, s in obstacles.items()}
    far_pairs, near = [], []
    for a, mover in movers.items():
        bb = swept_bounds(mover, offset)
        for b, obstacle in obstacles.items():
            if far(bb, boxes[b]):
                far_pairs.append([a, b])
                continue
            try:
                proof = certify_pair(mover, obstacle, offset)
            except Exception as exc:  # noqa: BLE001
                proof = {"status": "ERROR", "reason": f"{type(exc).__name__}: {exc}"}
            box_upper = aabb_overlap_upper(bb, boxes[b])
            try:
                distance = distance_certificate(mover, obstacle, offset)
            except Exception as exc:  # noqa: BLE001
                distance = {"status": "ERROR", "reason": f"{type(exc).__name__}: {exc}"}
            candidates = [box_upper]
            if proof["status"] == "PROVEN_CLEAR":
                candidates.append(proof["overlap_upper_bound_mm3"])
            if distance["status"] == "PROVEN_CLEAR":
                candidates.append(0.0)
            boss = None
            if boss_pair is not None and (a, b) == boss_pair:
                try:
                    boss = axial_boss_insertion_certificate(
                        mover, obstacle, tuple(offset), seat=18.8, centre=(234.9, 164.6), radius=4
                    )
                    if boss["status"] == "BOUNDED_TRANSLATION":
                        candidates.append(boss["continuous_volume_upper_bound_mm3"])
                except Exception as exc:  # noqa: BLE001
                    boss = {"status": "ERROR", "reason": f"{type(exc).__name__}: {exc}"}
            upper = min(candidates)
            samples = []
            if upper > 1e-4:
                for fraction in (0, 0.25, 0.5, 0.75, 1):
                    placed = mover.translate(tuple(fraction * v for v in offset))
                    check = inspect_pairs({a: placed, b: obstacle}, [(a, b)])
                    samples.append({"offset_fraction": fraction, **check})
            near.append(
                {
                    "a": a,
                    "b": b,
                    "continuous_cover": proof,
                    "swept_aabb_overlap_upper_mm3": box_upper,
                    "distance_certificate": distance,
                    "axial_boss_certificate": boss,
                    "selected_volume_upper_bound_mm3": upper,
                    "diagnostic_samples": samples,
                }
            )
            print(
                a,
                b,
                "cover",
                proof["status"],
                "distance",
                distance["status"],
                "upper",
                upper,
                flush=True,
            )
    expected = {(a, b) for a in movers for b in obstacles}
    actual = [tuple(p) for p in far_pairs] + [(r["a"], r["b"]) for r in near]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("incomplete or duplicated mover/obstacle coverage")
    failed_samples = [
        {"a": r["a"], "b": r["b"], "fraction": s["offset_fraction"], "pair": p}
        for r in near
        for s in r["diagnostic_samples"]
        for p in s["pairs"]
        if p["status"] == "FAIL"
    ]
    return {
        "movers": sorted(movers),
        "obstacles": sorted(obstacles),
        "start_offset_mm": list(offset),
        "end_offset_mm": [0, 0, 0],
        "far_pairs": far_pairs,
        "near_pairs": near,
        "pair_count": len(actual),
        "continuous_translation_volume_clear": sum(
            r["selected_volume_upper_bound_mm3"] for r in near
        )
        <= 1e-4,
        "summed_overlap_upper_bound_mm3": sum(r["selected_volume_upper_bound_mm3"] for r in near),
        "actual_penetration_samples": failed_samples,
        "sampled_clear_is_not_continuous_clear": True,
        "positive_clearance_proven": False,
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
    if len(rows) != len(shapes):
        raise ValueError("ambiguous occurrence identity")
    report = {"assembly_sha256": digest(path), "stages": {}, "installation_approved": False}
    for name, (movers, obstacles, later) in insertion_stages(shapes).items():
        report["stages"][name] = {
            **review_stage(
                movers, obstacles, (60, 0, 0), boss_pair=("PG3_horn_spacer", "PG3_XL430_horn")
            ),
            "installed_after_body_insertion": sorted(later),
        }
        print(name, "complete", flush=True)
    report["scope"] = "nominal fixed mid arm; body clusters move rigidly +X60 to0; no hands/cables"
    report["checker_sha256"] = digest(Path(__file__))
    report["dependencies"] = {
        n: digest(Path(n))
        for n in (
            "gripper_design/pg2.py",
            "gripper_design/pg3.py",
            "gripper_design/pg3_installation.py",
            "scripts/assembly_io.py",
            "scripts/certify_pg3_insertion.py",
            "scripts/review_pg3.py",
            "scripts/verify_pg3_service_stages.py",
            "scripts/review_pg3_pivot_stacks.py",
            "scripts/review_pg3_motion_clearance.py",
            "scripts/review_pg3_motor_partition.py",
            "scripts/review_pg3_washer_contacts.py",
            "gripper_design/interface_envelopes.py",
            "gripper_design/rotational_envelopes.py",
            "uv.lock",
        )
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    return 2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("checkpoint", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
