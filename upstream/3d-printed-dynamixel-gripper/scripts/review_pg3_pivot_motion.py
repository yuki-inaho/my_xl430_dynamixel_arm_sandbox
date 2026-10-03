"""Continuous whole-host/link clearance, separating verified bores from other material.

The host's entire material is covered by all negative-X boundary rays. A cover
disk at a co-moving pivot may fit in a verified full-span link void. Every other
cover is checked over the full interval; matching axes never waive body checks.
"""

import argparse
import json
import math
from collections import Counter
from itertools import combinations
from pathlib import Path

import cadquery as cq
import numpy as np

from gripper_design.interface_envelopes import axial_ray_cover
from gripper_design.pg2 import digest
from gripper_design.pg3 import group_for, group_transform, position_mm, to_arm
from scripts.assembly_io import bounds, read_step
from scripts.review_pg3 import inspect_pairs
from scripts.review_pg3_motion_clearance import (
    EPSILON_MM,
    DistanceTo,
    axial_gap_certificate,
    certify_interval,
    point_speed_bound,
    verify_axial_motion_contract,
)
from scripts.review_pg3_pivot_stacks import profiles


def neutral(shape):
    return shape.translate((0.2, -234.9, -164.6)).rotate((0, 0, 0), (0, 1, 0), -90)


def moved(local, group, radians):
    transform = group_transform(group, math.degrees(radians))
    degrees = math.degrees(math.atan2(transform[1, 0], transform[0, 0]))
    return to_arm(local.rotate((0, 0, 0), (0, 0, 1), degrees).translate(tuple(transform[:3, 3])))


def relative_to_link(local, host_group, link_group, radians):
    """Place ``local`` in the link's construction frame at one opening angle.

    Euclidean distance is invariant under a common rigid motion, so
    distance(moved(A, host), moved(L, link)) == distance(T_link^-1 T_host A, L):
    to_arm cancels and the link stays fixed, letting one DistanceTo(L) serve every
    sample. Valid because every group_transform is Rz plus XY translation, which
    verify_axial_motion_contract binds to the reviewed kinematics source.
    """
    degrees = math.degrees(radians)
    rel = np.linalg.inv(group_transform(link_group, degrees)) @ group_transform(host_group, degrees)
    angle = math.degrees(math.atan2(rel[1, 0], rel[0, 0]))
    return local.rotate((0, 0, 0), (0, 0, 1), angle).translate(tuple(rel[:3, 3]))


def verified_link_voids(link):
    bb = bounds(link)
    result = []
    for row in profiles(link):
        if row["sense"] != "concave" or abs(row["radius_mm"] - 2.7) > 1e-6:
            continue
        if max(abs(row["span_x_mm"][i] - bb[3 * i]) for i in (0, 1)) > 1e-6:
            raise ValueError("link bore does not span the entire link")
        y, z = row["axis_yz_mm"]
        void = cq.Solid.makeCylinder(
            row["radius_mm"], bb[3] - bb[0] + 0.02, (bb[0] - 0.01, y, z), (1, 0, 0)
        )
        clear = inspect_pairs({"link": link, "void": void}, [("link", "void")])
        bad = inspect_pairs({"link": link, "void": void.translate((0, 0.3, 0))}, [("link", "void")])
        check = clear["pairs"][0]
        if (
            check["status"] != "PASS"
            or check.get("volume_mm3") != 0.0
            or bad["pairs"][0]["status"] != "FAIL"
        ):
            raise ValueError("link void or its displaced penetration control is unproven")
        result.append({**row, "empty_void_check": clear, "displaced_void_check": bad})
    if len(result) != 2:
        raise ValueError("two verified full-span link bores required")
    return result


def pivot_anchor(side, kind):
    if side not in ("L", "R") or kind not in ("drive", "carriage"):
        raise ValueError("explicit L/R side and drive/carriage pivot required")
    sign = 1 if side == "R" else -1
    return (
        np.array((234.9 + sign * 14, 164.6))
        if kind == "drive"
        else np.array((234.9, 164.6 - sign * position_mm(90)))
    )


def inspect_pivot_motion(host, link, side, kind):
    contract = verify_axial_motion_contract()
    anchor = pivot_anchor(side, kind)
    covers, evidence = axial_ray_cover(host)
    voids = verified_link_voids(link)
    bore = min(voids, key=lambda b: np.linalg.norm(np.asarray(b["axis_yz_mm"]) - anchor))
    bore_error = float(np.linalg.norm(np.asarray(bore["axis_yz_mm"]) - anchor))
    host_group = "drive" if kind == "drive" else side
    link_group = f"link_{side}"
    local_link = neutral(link)
    link_speed = point_speed_bound(local_link, link_group)
    to_link = DistanceTo(local_link)

    checks = []
    for meta in evidence["all_boundary_faces"]:
        piece = covers[meta["name"]]
        row = {"cover": meta["name"], "source_face": meta["face"]}
        axial = axial_gap_certificate(bounds(piece), bounds(link))
        if axial:
            row.update(axial)
        else:
            radial_gap = -math.inf
            if meta["kind"] == "cylinder":
                host_error = float(
                    np.linalg.norm(np.asarray(meta["centre_transverse_mm"]) - anchor)
                )
                radial_gap = bore["radius_mm"] - meta["radius_mm"] - host_error - bore_error
            if radial_gap > EPSILON_MM:
                row.update(
                    status="PROVEN_CLEAR",
                    method="verified_void_and_corresponding_pivot_trajectories",
                    continuous_distance_lower_bound_mm=radial_gap,
                    host_anchor_error_bound_mm=host_error,
                    bore_anchor_error_bound_mm=bore_error,
                    bore_face=bore["face"],
                    checks=0,
                )
            else:
                local = neutral(piece)
                speed = point_speed_bound(local, host_group) + link_speed
                row.update(
                    method="whole_remaining_cover_lipschitz", point_speed_bound_sum_mm_per_rad=speed
                )
                row.update(
                    certify_interval(
                        lambda t, local=local: to_link(
                            relative_to_link(local, host_group, link_group, t)
                        ),
                        speed,
                        math.radians(25),
                        math.radians(135),
                    )
                )
        checks.append(row)
    verify_axial_motion_contract()
    return {
        "status": "PROVEN_CLEAR"
        if all(c["status"] == "PROVEN_CLEAR" for c in checks)
        else "UNPROVEN",
        "side": side,
        "kind": kind,
        "axial_motion_contract": contract,
        "pivot_trajectory_basis": "drive=signed_r_cos_sin; carriage=signed_slider; link_fixed_length24_maps_both_endpoints",
        "neutral_expected_axis_yz_mm": list(anchor),
        "cover": evidence,
        "verified_link_voids": voids,
        "cover_checks": checks,
        "all_source_faces_covered": len(checks) == len(host.Faces()),
        "physical_fit_approved": False,
    }


def run(checkpoint, base_motion, out):
    if out.exists():
        raise FileExistsError(out)
    path = checkpoint / "arm_camera_mid_CANDIDATE.step"
    manifest = json.loads((checkpoint / "review.json").read_text())
    if digest(path) != manifest["output_sha256"][path.name]:
        raise ValueError("checkpoint hash mismatch")
    loaded = read_step(path)[2]
    shapes = {r.name: r.world for r in loaded}
    if len(shapes) != len(loaded):
        raise ValueError("ambiguous occurrence identity")
    base = json.loads(base_motion.read_text())
    if base["assembly_sha256"] != digest(path) or base["checker_sha256"] != digest(
        Path(__file__).with_name("review_pg3_motion_clearance.py")
    ):
        raise ValueError("base motion certificate version mismatch")
    if any(digest(Path(n)) != h for n, h in base["dependencies"].items()):
        raise ValueError("base motion dependency mismatch")
    groups = {n: group_for(n[4:]) if n.startswith("PG3_") else "fixed" for n in shapes}
    expected = {
        (a, b)
        for a, b in combinations(sorted(shapes), 2)
        if groups[a] != "fixed" or groups[b] != "fixed"
    }
    previous = {(r["a"], r["b"]): r for r in base["pairs"]}
    if (
        len(previous) != len(base["pairs"])
        or set(previous) != expected
        or base["motion_groups"] != groups
    ):
        raise ValueError("base motion pair coverage mismatch")
    rows = []
    negatives = {}
    for side in ("L", "R"):
        for kind in ("drive", "carriage"):
            a = "PG3_crank" if kind == "drive" else f"PG3_carriage_{side}"
            b = f"PG3_link_{side}"
            try:
                row = inspect_pivot_motion(shapes[a], shapes[b], side, kind)
            except Exception as exc:  # noqa: BLE001
                row = {"status": "ERROR", "detail": str(exc)}
            row.update(a=a, b=b)
            rows.append(row)
            print(a, b, row["status"], flush=True)
            shifted = shapes[a].translate((0, 0.3, 0))
            result = inspect_pivot_motion(shifted, shapes[b], side, kind)
            negatives[f"{kind}_{side}_axis_offset"] = {
                "shift_world_y_mm": 0.3,
                "mid_solid_distance_mm": shifted.distance(shapes[b]),
                "status": result["status"],
                "unproven_covers": [
                    c for c in result["cover_checks"] if c["status"] != "PROVEN_CLEAR"
                ],
            }
    link = shapes["PG3_link_L"]
    extra = shapes["PG3_carriage_L"].fuse(link.translate((-1, 0, 0)))
    if not extra.isValid() or len(extra.Solids()) != 1:
        raise ValueError("invalid extra-material negative fixture")
    result = inspect_pivot_motion(extra, link, "L", "carriage")
    negatives["extra_material_outside_pin"] = {
        "fixture": "carriage_L fused with link_L translated -1mm world X",
        "mid_solid_distance_mm": extra.distance(link),
        "status": result["status"],
        "unproven_covers": [c for c in result["cover_checks"] if c["status"] != "PROVEN_CLEAR"],
    }
    negative_pass = all(
        n["status"] == "UNPROVEN" and n["mid_solid_distance_mm"] <= EPSILON_MM
        for n in negatives.values()
    )
    accepted = []
    combined = Counter(r["status"] for r in previous.values())
    for row in rows:
        pair = tuple(sorted((row["a"], row["b"])))
        if pair not in previous or previous[pair]["status"] != "UNPROVEN":
            raise ValueError("expected unresolved whole-host/link pair missing from base")
        if negative_pass and row["status"] == "PROVEN_CLEAR" and row["all_source_faces_covered"]:
            accepted.append(list(pair))
            combined["UNPROVEN"] -= 1
            combined["PROVEN_CLEAR"] += 1
    deps = (
        "gripper_design/interface_envelopes.py",
        "gripper_design/pg3.py",
        "gripper_design/pg2.py",
        "scripts/assembly_io.py",
        "scripts/review_pg3.py",
        "scripts/review_pg3_motion_clearance.py",
        "scripts/review_pg3_pivot_stacks.py",
        "uv.lock",
    )
    report = {
        "scope": "four_whole_host_link_pairs_continuous_opening_25_to_135_fixed_upstream_arm",
        "assembly_sha256": digest(path),
        "checker_sha256": digest(Path(__file__)),
        "dependencies": {n: digest(Path(n)) for n in deps},
        "base_motion_sha256": digest(base_motion),
        "negative_controls": negatives,
        "negative_controls_rejected": negative_pass,
        "accepted_clear_pairs": accepted,
        "combined_motion_counts": dict(combined),
        "stationary_pairs_not_reassessed": base["stationary_pairs_not_reassessed"],
        "pairs": rows,
        "counts": dict(Counter(r["status"] for r in rows)),
        "base_reports_modified": False,
        "installation_approved": False,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(report["counts"], flush=True)
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--base-motion", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.base_motion, args.out))
