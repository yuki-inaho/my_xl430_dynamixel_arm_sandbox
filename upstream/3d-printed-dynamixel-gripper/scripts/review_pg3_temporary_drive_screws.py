"""Check a reversible no-washer temporary drive-screw assembly candidate."""

import argparse
import itertools
import json
import math
from pathlib import Path

from gripper_design.pg2 import digest
from scripts.assembly_io import read_step
from scripts.review_pg3 import inspect_pairs
from scripts.review_pg3_local_contacts import review_local_pairs
from scripts.review_pg3_mechanism_insertion import insertion_stages, review_stage, split_stage
from scripts.review_pg3_pivot_stacks import pick, profiles
from scripts.review_pg3_slider_link_insertion import later_stages
from scripts.review_pg3_washer_contacts import opposed_seat
from scripts.verify_pg3_service_stages import mechanism_stages


def candidate(shapes):
    screws, stacks = {}, {}
    host = shapes["PG3_crank"]
    hp = profiles(host)
    for side in ("R", "L"):
        prefix = f"PG3_pivot_drive_{side}"
        bolt = shapes[f"{prefix}_bolt"]
        bp = profiles(bolt)
        shank = pick(bp, 1, "convex")
        head = pick(bp, 1.9, "convex")
        centre = shank["axis_yz_mm"]
        shoulder = pick(hp, 2.5, "convex", centre)
        bore = pick(hp, 1.15, "concave", centre)
        nut = pick(profiles(shapes[f"{prefix}_nut"]), 1, "concave")
        link = pick(profiles(shapes[f"PG3_link_{side}"]), 2.7, "concave", centre)
        error = max(math.dist(p["axis_yz_mm"], centre) for p in (head, shoulder, bore, nut, link))
        if error > 1e-6 or abs(head["span_x_mm"][0] - shank["span_x_mm"][1]) > 1e-6:
            raise ValueError("coaxial intact saved pivot stack required")
        seat = shoulder["span_x_mm"][1]
        shift = seat - shank["span_x_mm"][1]
        if not math.isfinite(shift) or shift >= 0:
            raise ValueError("explicit inward no-washer seating displacement required")
        placed = bolt.translate((shift, 0, 0))
        contact = opposed_seat(
            host, placed, seat, math.pi * (head["radius_mm"] ** 2 - bore["radius_mm"] ** 2)
        )
        tip = shank["span_x_mm"][0] + shift
        nlo, nhi = nut["span_x_mm"]
        overlap = max(0, min(seat, nhi) - max(tip, nlo))
        screws[f"{prefix}_bolt"] = placed
        stacks[prefix] = {
            "translation_mm": [shift, 0, 0],
            "head_seat": contact,
            "axis_error_mm": error,
            "tip_x_mm": tip,
            "nominal_nut_span_overlap_mm": overlap,
            "nut_span_mm": nhi - nlo,
            "tip_beyond_nut_mm": nlo - tip,
            "head_to_link_radial_gap_mm": link["radius_mm"] - head["radius_mm"] - error,
            "nominal_seating_pass": contact["pass_contact"] and overlap >= nhi - nlo - 1e-6,
            "actual_thread_engagement_verified": False,
        }

    canonical = insertion_stages(shapes)
    movers, obstacles, later = canonical["G2_horn_drive"]
    if set(screws) & (set(movers) | set(obstacles) | set(later)):
        raise ValueError("temporary screws cannot already be installed")
    movers = movers | screws
    stages = {"G2": (movers, obstacles, later)}
    present = obstacles | movers | {n: shapes[n] for n in later}
    bodies = later_stages(shapes)
    for name in ("G3_R", "G3_L", "G4_R_link", "G4_L_link"):
        additions, _, deferred = bodies[name]
        if deferred or set(additions) & set(present):
            raise ValueError("body additions must be new with no deferred fasteners")
        if any(s is not shapes[n] for n, s in additions.items()):
            raise ValueError("body additions must retain saved shapes")
        after = present | additions
        stages[name] = split_stage(present, after, ())
        present = after
    final = mechanism_stages(shapes, horn_l_key=True)["G4_link_pivots"][0]
    deferred = {
        f"PG3_pivot_{kind}_{side}_washer" for kind in ("drive", "carriage") for side in ("R", "L")
    } | {f"PG3_pivot_carriage_{side}_bolt" for side in ("R", "L")}
    if set(present) != set(final) - deferred or any(
        s is not (screws[n] if n in screws else shapes[n]) for n, s in present.items()
    ):
        raise ValueError("temporary assembly inventory or geometry mismatch")
    return {"temporary_screws": screws, "stacks": stacks, "stages": stages}


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
    prepared = candidate(shapes)
    screws = prepared["temporary_screws"]
    cluster = prepared["stages"]["G2"][0]
    pairs = [(a, b) for a in screws for b in cluster if b not in screws] + list(
        itertools.combinations(screws, 2)
    )
    report = {
        "assembly_sha256": digest(path),
        "stacks": prepared["stacks"],
        "temporary_cluster_contacts": {
            "world": inspect_pairs(cluster, pairs),
            "common_reexpression_mid90": review_local_pairs(cluster, pairs, 90),
        },
        "stages": {},
        "installation_approved": False,
    }
    for name, (movers, obstacles, later) in prepared["stages"].items():
        result = review_stage(
            movers, obstacles, (60, 0, 0), boss_pair=("PG3_horn_spacer", "PG3_XL430_horn")
        )
        result["installed_after_body_insertion"] = sorted(later)
        report["stages"][name] = result
        print(
            name,
            "clear",
            result["continuous_translation_volume_clear"],
            "upper",
            result["summed_overlap_upper_bound_mm3"],
            flush=True,
        )
    report["scope"] = (
        "saved mid; temporary drive screws seated without washers; G2/G3/G4 bodies +X60 to0; both links before any pivot washer"
    )
    report["limits"] = [
        "existing G1 and carriage nut loading/holding remain separate prerequisites",
        "smooth screw/nut proxies do not prove thread engagement, strength or tightening torque",
        "world and common rigid-frame contacts are separate evidence; raw errors retained",
        "temporary screw insertion, removal, nut capture and washer exchange are not validated here",
        "no hand/cable/actual-tool/print tolerance/other-pose approval",
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
