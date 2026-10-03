"""Bench loading of the twelve PG3 nuts, separate from their later retention."""

import argparse
import json
import math
from pathlib import Path

import cadquery as cq
import numpy as np

from gripper_design.pg2 import digest
from scripts.assembly_io import bounds, read_step
from scripts.review_pg3 import inspect_pairs
from scripts.review_pg3_local_contacts import reexpress
from scripts.review_pg3_mechanism_insertion import enclosure_bounds, insertion_stages, review_stage
from scripts.review_pg3_motor_partition import PADDING
from scripts.review_pg3_slider_link_insertion import later_stages


def hex_translation_enclosure(shape, offset):
    """Intersect six whole-B-rep support halfplanes, then extend the X interval.

    The directions come from lateral planes, but support values bound the entire
    shape, including curved extrema. No nut vertex or Boolean containment test
    stands in for this whole-material bound. The centre hole is conservatively filled.
    """
    vector = np.asarray(offset, dtype=float)
    if vector.shape != (3,) or not np.isfinite(vector).all() or any(vector[1:] != 0):
        raise ValueError("finite X-only translation required")
    bb = enclosure_bounds(shape)
    centre = tuple((bb[i] + bb[i + 3]) / 2 for i in range(3))
    local = shape.translate(tuple(-c for c in centre))
    bb = enclosure_bounds(local)
    planes = []
    for i, face in enumerate(local.Faces()):
        if face.geomType() != "PLANE":
            continue
        normal = np.asarray(face.normalAt().toTuple())
        if abs(normal[0]) > 1e-8:
            continue
        n = normal[1:] / np.linalg.norm(normal[1:])
        theta = math.atan2(n[1], n[0])
        rotated = local.rotate((0, 0, 0), (1, 0, 0), -math.degrees(theta))
        support = bounds(rotated)[4]
        planes.append(
            {
                "face": i,
                "angle_rad": theta,
                "normal_yz": n.tolist(),
                "whole_material_support_mm": support,
                "padded_support_mm": support + PADDING,
            }
        )
    planes.sort(key=lambda row: row["angle_rad"])
    if len(planes) != 6:
        raise ValueError("six lateral planes required for this hex enclosure")
    angles = [row["angle_rad"] for row in planes]
    gaps = [(angles[(i + 1) % 6] - angles[i]) % (2 * math.pi) for i in range(6)]
    if not all(1e-8 < gap < math.pi - 1e-8 for gap in gaps):
        raise ValueError("bounded nondegenerate support polygon required")
    normals = np.asarray([row["normal_yz"] for row in planes])
    supports = np.asarray([row["padded_support_mm"] for row in planes])
    vertices = []
    for i in range(6):
        indices = [i, (i + 1) % 6]
        vertex = np.linalg.solve(normals[indices], supports[indices])
        if not np.isfinite(vertex).all() or np.any(normals @ vertex > supports + PADDING / 4):
            raise ValueError("inconsistent support polygon")
        vertices.append(vertex.tolist())
    low = bb[0] + min(0, vector[0]) - PADDING
    high = bb[3] + max(0, vector[0]) + PADDING
    plane = cq.Plane(origin=(low, 0, 0), xDir=(0, 1, 0), normal=(1, 0, 0))
    cover = (
        cq.Workplane(plane).polyline(vertices).close().extrude(high - low).val().translate(centre)
    )
    enclosure_bounds(cover)
    return cover, {
        "support_halfplanes": planes,
        "source_centre_mm": list(centre),
        "swept_local_x_mm": [float(low), float(high)],
        "polygon_vertices_yz_mm": vertices,
        "padding_mm": PADDING,
        "source_boolean_used_as_containment_proof": False,
        "centre_hole_conservatively_filled": True,
    }


def review_loaded_nut(movers, obstacles, offset=(-30, 0, 0)):
    result = review_stage(movers, obstacles, offset)
    covers, metadata = {}, {}
    for name, shape in movers.items():
        covers[name], metadata[name] = hex_translation_enclosure(shape, offset)
    shapes = covers | obstacles
    pairs = [(a, b) for a in movers for b in obstacles]
    world = inspect_pairs(shapes, pairs)
    local = inspect_pairs({n: reexpress(s, 90) for n, s in shapes.items()}, pairs)

    def proved_upper(row):
        if row["status"] != "PASS":
            return math.inf
        return row.get("volume_mm3", row.get("conservative_intersection_mm3", 0.0))

    raw_bounds = {tuple(pair): 0.0 for pair in result["far_pairs"]}
    raw_bounds.update(
        {(r["a"], r["b"]): r["selected_volume_upper_bound_mm3"] for r in result["near_pairs"]}
    )
    selected = []
    for w, r in zip(world["pairs"], local["pairs"], strict=True):
        key = (w["a"], w["b"])
        if key != (r["a"], r["b"]):
            raise ValueError("supplemental pair identity mismatch")
        selected.append(
            {
                "a": key[0],
                "b": key[1],
                "upper_bound_mm3": min(raw_bounds[key], proved_upper(w), proved_upper(r)),
            }
        )
    total = sum(r["upper_bound_mm3"] for r in selected)
    result["hex_enclosure"] = {
        "source_covers": metadata,
        "world": world,
        "common_reexpression_mid90": local,
        "selected_pairs": selected,
        "summed_overlap_upper_bound_mm3": total,
    }
    result["supplemented_continuous_translation_volume_clear"] = (
        total <= 1e-4 and not result["actual_penetration_samples"]
    )
    return result


def preload_stages(shapes):
    first, later = insertion_stages(shapes), later_stages(shapes)
    groups = {
        "G1": (first["G1_frame_case"][0], {"PG3_frame"}),
        "G2": (first["G2_horn_drive"][0], {"PG3_crank", "PG3_horn_spacer"}),
        "G3_R": (later["G3_R"][0], {"PG3_carriage_R"}),
        "G3_L": (later["G3_L"][0], {"PG3_carriage_L"}),
    }
    stages, seen = {}, []
    for group, (cluster, required_hosts) in groups.items():
        if any(n not in shapes or s is not shapes[n] for n, s in cluster.items()):
            raise ValueError("cluster must retain saved geometry")
        nuts = sorted(n for n in cluster if n.endswith("_nut"))
        present = {n: s for n, s in cluster.items() if n not in nuts}
        if set(present) != required_hosts:
            raise ValueError("bench host inventory mismatch")
        for name in nuts:
            movers = {name: shapes[name]}
            stages[name] = (movers, dict(present), group)
            present.update(movers)
            seen.append(name)
    expected = {n for n in shapes if n.startswith("PG3_") and n.endswith("_nut")}
    if set(seen) != expected or len(seen) != len(expected):
        raise ValueError("missing or duplicated preloaded nut inventory")
    return stages


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
    for name, (movers, obstacles, group) in preload_stages(shapes).items():
        result = review_loaded_nut(movers, obstacles)
        result["bench_group"] = group
        result["reverse_axial_exit_path_proven_in_same_bench_state"] = result[
            "supplemented_continuous_translation_volume_clear"
        ]
        report["stages"][name] = result
        print(
            name,
            "clear",
            result["supplemented_continuous_translation_volume_clear"],
            "upper",
            result["hex_enclosure"]["summed_overlap_upper_bound_mm3"],
            flush=True,
        )
    report["scope"] = (
        "four separate free-bench clusters before G1/G2/G3; nominal saved mid nut orientations; -X30 to0"
    )
    report["limits"] = [
        "bench loading is not in-situ access after the host is installed on the arm",
        "reversible insertion path proves no axial geometric retention along that same bench path",
        "fixtures, hands, tack, transport and nut holding during body insertion unverified",
        "nominal nut proxies do not validate actual nut tolerance, thread engagement or PLA friction",
        "camera nuts are not part of these PG3 clusters",
    ]
    report["checker_sha256"] = digest(Path(__file__))
    report["dependencies"] = {
        p: digest(Path(p))
        for p in (
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
