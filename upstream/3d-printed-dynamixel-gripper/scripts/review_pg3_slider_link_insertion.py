"""Sequential slider/link body insertion before caps, fingers and camera."""

import argparse
import json
from pathlib import Path

from gripper_design.pg2 import digest
from scripts.assembly_io import read_step
from scripts.review_pg3_mechanism_insertion import review_stage, split_stage
from scripts.verify_pg3_service_stages import mechanism_stages


def later_stages(shapes):
    tools = mechanism_stages(shapes, horn_l_key=True)
    present = dict(tools["G2_horn_drive"][0])
    stages = {}

    def add(name, moving_names, later_names=()):
        nonlocal present
        additions = set(moving_names) | set(later_names)
        if not additions <= set(shapes) or additions & set(present):
            raise ValueError("missing or previously installed addition")
        after = present | {n: shapes[n] for n in additions}
        movers, obstacles, later = split_stage(present, after, later_names)
        if set(movers) != set(moving_names):
            raise ValueError("declared mover inventory mismatch")
        stages[name] = (movers, obstacles, later)
        present = after

    for side in ("R", "L"):
        add(
            f"G3_{side}",
            [
                f"PG3_carriage_{side}",
                f"PG3_pivot_carriage_{side}_nut",
                f"PG3_finger_{side}_-14_nut",
                f"PG3_finger_{side}_14_nut",
            ],
        )
    for side in ("R", "L"):
        add(f"G4_{side}_link", [f"PG3_link_{side}"])
        add(
            f"G4_{side}_washers",
            [f"PG3_pivot_{kind}_{side}_washer" for kind in ("drive", "carriage")],
            [f"PG3_pivot_{kind}_{side}_bolt" for kind in ("drive", "carriage")],
        )
    expected = tools["G4_link_pivots"][0]
    if set(present) != set(expected) or any(present[n] is not expected[n] for n in present):
        raise ValueError("final body stage disagrees with reviewed tool-stage inventory")
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
    for name, (movers, obstacles, later) in later_stages(shapes).items():
        result = review_stage(movers, obstacles, (60, 0, 0))
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
        "saved mid fixed arm; sequential G3/G4 bodies along +X60 to0; no caps/fingers/camera"
    )
    report["limits"] = [
        "preloaded carriage nuts and temporary holding are assumptions, not verified operations",
        "intra-cluster pre-existing fit is not approved by mover-obstacle path clearance",
        "later-installed bolts need their own actual thread and insertion verification",
        "no hand, cable, force, printed fit or other arm pose approval",
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
    return 2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("checkpoint", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
