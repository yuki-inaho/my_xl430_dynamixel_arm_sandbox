"""Bound the displayed horn's full rotation against retained supplier spacers.

The donor horn is a visualization split, not a certified physical bearing model.
All its boundary faces must fit the rotation-invariant cylinder before distance
to that cylinder can certify either complete spacer clear. Source Boolean
identity failures are recorded, never used to prove containment.
"""

import argparse
import json
import math
from collections import Counter
from itertools import combinations
from pathlib import Path

from gripper_design.interface_envelopes import axial_ray_cover
from gripper_design.pg2 import digest
from gripper_design.pg3 import group_for
from gripper_design.rotational_envelopes import rotational_cover
from scripts.assembly_io import read_step
from scripts.review_pg3 import inspect_pairs
from scripts.review_pg3_motion_clearance import EPSILON_MM, verify_axial_motion_contract


def inspect_horn_sweep(horn, spacers):
    contract = verify_axial_motion_contract()
    cover, envelope = rotational_cover(horn, 0, (234.9, 164.6), 10.3)
    source_control = {
        "volume_mm3": horn.Volume(),
        "self_cut_mm3": sum(abs(s.Volume()) for s in horn.cut(horn.copy()).Solids()),
        "self_common_mm3": sum(abs(s.Volume()) for s in horn.intersect(horn.copy()).Solids()),
        "used_for_containment": False,
    }
    rows, negative = [], {}
    for name, spacer in sorted(spacers.items()):
        # Validate finite solid material, including the infinite-point test.
        _, validation = axial_ray_cover(spacer)
        distance = cover.distance(spacer)
        if not math.isfinite(distance) or distance < 0:
            raise ValueError("invalid cover distance")
        rows.append(
            {
                "a": name,
                "b": "PG3_XL430_horn",
                "status": "PROVEN_CLEAR" if distance > EPSILON_MM else "UNPROVEN",
                "continuous_distance_lower_bound_mm": distance,
                "partner_face_count": validation["source_face_count"],
                "partner_infinite_point_outside": validation["all_solids_infinite_point_outside"],
            }
        )
        centre = spacer.Center()
        dy, dz = 234.9 - centre.y, 164.6 - centre.z
        length = math.hypot(dy, dz)
        if not math.isfinite(length) or length <= EPSILON_MM:
            raise ValueError("cannot define inward spacer control")
        shift = (0, 0.2 * dy / length, 0.2 * dz / length)
        moved = spacer.translate(shift)
        negative[name] = {
            "displacement_mm": shift,
            "control": inspect_pairs(
                {"sweep": cover, "shifted_spacer": moved}, [("sweep", "shifted_spacer")]
            ),
            "actual_horn_distance_mm": moved.distance(horn),
        }
    negative_pass = len(negative) == 2 and all(
        n["control"]["pairs"][0]["status"] == "FAIL" and n["actual_horn_distance_mm"] <= EPSILON_MM
        for n in negative.values()
    )
    verify_axial_motion_contract()
    return {
        "axial_motion_contract": contract,
        "rotation_basis": "drive_group_is_Rz_about_construction_origin; to_arm_maps_to_fixed_world_X_axis",
        "envelope": envelope,
        "source_boolean_diagnostic": source_control,
        "pairs": rows,
        "negative_controls": negative,
        "negative_controls_detected": negative_pass,
        "accepted_clear_pairs": [
            [r["a"], r["b"]] for r in rows if negative_pass and r["status"] == "PROVEN_CLEAR"
        ],
        "physical_motor_interface_approved": False,
        "installation_approved": False,
    }


def run(checkpoint, motion_path, pivots_path, out):
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
    base = json.loads(motion_path.read_text())
    pivots = json.loads(pivots_path.read_text())
    for data, checker in (
        (base, "review_pg3_motion_clearance.py"),
        (pivots, "review_pg3_pivot_motion.py"),
    ):
        if data["assembly_sha256"] != digest(path) or data["checker_sha256"] != digest(
            Path(__file__).with_name(checker)
        ):
            raise ValueError("prior proof version mismatch")
        if any(digest(Path(n)) != h for n, h in data["dependencies"].items()):
            raise ValueError("prior proof dependency mismatch")
    if (
        pivots["base_motion_sha256"] != digest(motion_path)
        or not pivots["negative_controls_rejected"]
    ):
        raise ValueError("pivot evidence chain mismatch")
    groups = {n: group_for(n[4:]) if n.startswith("PG3_") else "fixed" for n in shapes}
    expected = {
        (a, b)
        for a, b in combinations(sorted(shapes), 2)
        if groups[a] != "fixed" or groups[b] != "fixed"
    }
    previous = {(r["a"], r["b"]): r for r in base["pairs"]}
    if (
        set(previous) != expected
        or len(previous) != len(base["pairs"])
        or groups != base["motion_groups"]
    ):
        raise ValueError("prior proof pair coverage mismatch")
    names = ("ARM_M06_ref27", "ARM_M06_ref28")
    report = inspect_horn_sweep(shapes["PG3_XL430_horn"], {n: shapes[n] for n in names})
    prior_accepted = {tuple(p) for p in pivots["accepted_clear_pairs"]}
    accepted = {tuple(p) for p in report["accepted_clear_pairs"]}
    if prior_accepted & accepted:
        raise ValueError("duplicate supplemental acceptance")
    combined = Counter(r["status"] for r in previous.values())
    for pair in prior_accepted | accepted:
        if pair not in previous or previous[pair]["status"] != "UNPROVEN":
            raise ValueError("supplemental pair was not unresolved in base")
        combined["UNPROVEN"] -= 1
        combined["PROVEN_CLEAR"] += 1
    deps = (
        "gripper_design/rotational_envelopes.py",
        "gripper_design/interface_envelopes.py",
        "gripper_design/pg2.py",
        "gripper_design/pg3.py",
        "scripts/assembly_io.py",
        "scripts/review_pg3.py",
        "scripts/review_pg3_motion_clearance.py",
        "uv.lock",
    )
    report.update(
        scope="two_complete_supplier_spacers_vs_horn_rotation_enclosure_fixed_upstream_arm_opening_25_to_135",
        assembly_sha256=digest(path),
        checker_sha256=digest(Path(__file__)),
        dependencies={n: digest(Path(n)) for n in deps},
        base_motion_sha256=digest(motion_path),
        prior_pivot_proof_sha256=digest(pivots_path),
        combined_motion_counts=dict(combined),
        stationary_pairs_not_reassessed=base["stationary_pairs_not_reassessed"],
        base_reports_modified=False,
    )
    if (
        sum(combined.values()) + base["stationary_pairs_not_reassessed"]
        != len(shapes) * (len(shapes) - 1) // 2
    ):
        raise ValueError("full pair accounting mismatch")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(
        {
            "accepted": report["accepted_clear_pairs"],
            "combined_counts": report["combined_motion_counts"],
        },
        flush=True,
    )
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--motion", type=Path, required=True)
    parser.add_argument("--pivots", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.motion, args.pivots, args.out))
