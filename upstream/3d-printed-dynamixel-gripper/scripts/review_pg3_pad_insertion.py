"""Two-segment pad insertion, without sliding the adhesive face along the jaw."""

import argparse
import json
import math
from itertools import pairwise
from pathlib import Path

from gripper_design.pg2 import digest
from scripts.assembly_io import read_step
from scripts.review_pg3_mechanism_insertion import review_stage
from scripts.verify_pg3_service_stages import mechanism_stages


def pad_stages(shapes):
    present = dict(mechanism_stages(shapes, horn_l_key=True)["G6_fingers"][0])
    stages = {}
    for side, sign in (("R", 1), ("L", -1)):
        name = f"PG3_pad_{side}"
        if name not in shapes or name in present:
            raise ValueError("missing or previously installed pad")
        movers = {name: shapes[name]}
        stages[f"G7_{side}_pad"] = (
            movers,
            dict(present),
            [(60, 0, sign * 3), (0, 0, sign * 3), (0, 0, 0)],
        )
        present.update(movers)
    expected = {n: s for n, s in shapes.items() if not n.startswith("CAMERA_")}
    if set(present) != set(expected) or any(present[n] is not expected[n] for n in present):
        raise ValueError("final pad stage disagrees with saved non-camera inventory")
    return stages


def review_path(movers, obstacles, waypoints):
    points = [tuple(float(v) for v in p) for p in waypoints]
    if (
        not movers
        or len(points) < 2
        or any(len(p) != 3 or not all(math.isfinite(v) for v in p) for p in points)
        or points[-1] != (0, 0, 0)
        or any(a == b for a, b in pairwise(points))
    ):
        raise ValueError("finite nonzero segments ending at saved pose required")
    segments = []
    for start, end in pairwise(points):
        # review_stage moves from endpoint+delta to endpoint, not from a global origin.
        placed = {n: s.translate(end) for n, s in movers.items()}
        delta = tuple(a - b for a, b in zip(start, end, strict=True))
        result = review_stage(placed, obstacles, delta)
        result["start_offset_from_saved_mm"] = list(start)
        result["end_offset_from_saved_mm"] = list(end)
        segments.append(result)
    return {
        "movers": sorted(movers),
        "obstacles": sorted(obstacles),
        "waypoints_from_saved_mm": [list(p) for p in points],
        "segments": segments,
        "continuous_path_volume_clear": all(
            r["continuous_translation_volume_clear"] for r in segments
        ),
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
    if len(shapes) != len(rows):
        raise ValueError("ambiguous occurrence identity")
    report = {"assembly_sha256": digest(path), "stages": {}, "installation_approved": False}
    for name, (movers, obstacles, waypoints) in pad_stages(shapes).items():
        report["stages"][name] = review_path(movers, obstacles, waypoints)
        print(name, "clear", report["stages"][name]["continuous_path_volume_clear"], flush=True)
    report["scope"] = (
        "fixed saved mid arm, pads after G6 before camera; approach with 3mm face gap then normal seating"
    )
    report["limits"] = [
        "28x20x1mm nominal pad includes adhesive thickness; no extra adhesive layer model",
        "material, adhesive, release liner, positioning and pressure tooling unverified",
        "bond strength, cure, PLA compatibility and gripping friction unverified",
        "no hand, cable, printed fit or other arm pose approval",
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
