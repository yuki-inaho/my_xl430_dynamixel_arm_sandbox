"""Compare bench-fastened linkage insertion with in-situ pivot assembly."""

import argparse
import json
from pathlib import Path

from gripper_design.pg2 import digest
from scripts.assembly_io import read_step
from scripts.review_pg3 import inspect_pairs
from scripts.review_pg3_mechanism_insertion import review_stage, split_stage
from scripts.verify_pg3_service_stages import mechanism_stages


def bench_cluster(shapes):
    canonical = mechanism_stages(shapes, horn_l_key=True)
    before = canonical["G1_frame_case"][0]
    expected_before = {
        n
        for n in shapes
        if n.startswith(("ARM_", "PG3_case_tapper"))
        or (n.startswith("PG3_cap_") and n.endswith("_nut"))
        or n in {"PG3_XL430_fixed", "PG3_XL430_horn", "PG3_frame"}
    }
    if set(before) != expected_before:
        raise ValueError("complete G1 obstacle inventory required")
    late = {f"PG3_finger_{s}_{p}_nut" for s in ("R", "L") for p in ("-14", "14")}
    full = canonical["G4_link_pivots"][0]
    if not late <= set(full):
        raise ValueError("all late-loaded finger nuts must be accounted for")
    after = {n: s for n, s in full.items() if n not in late}
    horn = {f"PG3_horn_bolt_{i}" for i in range(4)}
    movers, obstacles, later = split_stage(before, after, horn)
    expected = {"PG3_crank", "PG3_horn_spacer"}
    for side in ("R", "L"):
        expected.update({f"PG3_carriage_{side}", f"PG3_link_{side}"})
        expected.update(
            f"PG3_pivot_{kind}_{side}_{p}"
            for kind in ("drive", "carriage")
            for p in ("bolt", "washer", "nut")
        )
    if set(movers) != expected or any(s is not shapes[n] for n, s in after.items()):
        raise ValueError("complete saved linkage and spacer geometry required")
    bench_tools = canonical["G4_link_pivots"][1]
    horn_tools = canonical["G2_horn_drive"][1]
    for tools, names in (
        (bench_tools, {n for n in expected if n.endswith("_bolt")}),
        (horn_tools, horn),
    ):
        if set(tools) != {f"{prefix}_{n}" for prefix in ("TOOL", "WITHDRAWAL") for n in names}:
            raise ValueError("every final screw needs access and withdrawal envelopes")
    return {
        "movers": movers,
        "obstacles": obstacles,
        "horn_bolts": {n: shapes[n] for n in later},
        "installed": after,
        "bench_tools": bench_tools,
        "horn_tools": horn_tools,
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
    prepared = bench_cluster(shapes)
    report = {"assembly_sha256": digest(path), "installation_approved": False}
    report["cluster_insertion"] = review_stage(
        prepared["movers"],
        prepared["obstacles"],
        (60, 0, 0),
        boss_pair=("PG3_horn_spacer", "PG3_XL430_horn"),
    )
    report["tools"] = {}
    for label, bodies, tools in (
        ("bench_pivots", prepared["movers"], prepared["bench_tools"]),
        ("horn_after_cluster", prepared["installed"], prepared["horn_tools"]),
    ):
        proof = inspect_pairs(bodies | tools, [(a, b) for a in tools for b in bodies])
        proof.update(present_occurrences=sorted(bodies), tool_occurrences=sorted(tools))
        report["tools"][label] = proof
        print(label, proof["counts"], flush=True)
    report["nominal_paths_and_tool_envelopes_pass"] = (
        report["cluster_insertion"]["continuous_translation_volume_clear"]
        and not report["cluster_insertion"]["actual_penetration_samples"]
        and all(set(p["counts"]) == {"PASS"} for p in report["tools"].values())
    )
    report["horn_bolts_installed_after_insertion"] = sorted(prepared["horn_bolts"])
    report["scope"] = (
        "saved mid; 17-part bench-fastened articulated linkage plus held separate spacer; full G1 arm/frame stays fixed; horn screws installed last"
    )
    report["limits"] = [
        "linkage is articulated, not a rigid body; maintaining its saved pose during handling is unverified",
        "the separate horn spacer also requires support; it is not assumed captured",
        "finger nuts are loaded later using separately reviewed access, not carried loose in this cluster",
        "G1 cap nuts remain conservative stationary obstacles; actual cap nut loading/holding is separate",
        "bench pivot screw/nut loading, retention, actual threads and tightening are not certified by tool envelopes",
        "horn screw insertion and actual bit/socket engagement are separate from above-head tool access",
        "pre-existing intra-cluster contacts and whole-arm/other-pose motion are not accepted by this insertion test",
        "hand/fixture, cable, printed fit, strength and installation gates remain open",
    ]
    report["checker_sha256"] = digest(Path(__file__))
    report["dependencies"] = {
        p: digest(Path(p))
        for p in (
            "scripts/review_pg3_mechanism_insertion.py",
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
    print("nominal candidate", report["nominal_paths_and_tool_envelopes_pass"], flush=True)
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
