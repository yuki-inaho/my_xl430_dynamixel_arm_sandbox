"""Sample declared rigid insertion paths, with conservative swept-AABB broad phase."""

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from gripper_design.pg2 import digest
from scripts.assembly_io import bounds, read_step
from scripts.review_pg3 import inspect_pairs
from scripts.verify_pg3_service_stages import camera_stages


def sample_translation(movers, obstacles, start, step_mm=1):
    start = np.asarray(start, dtype=float)
    if (
        start.shape != (3,)
        or not np.isfinite(start).all()
        or not math.isfinite(step_mm)
        or step_mm <= 0
    ):
        raise ValueError("finite start and positive sampling step required")
    if not movers or not obstacles or set(movers) & set(obstacles):
        raise ValueError("nonempty disjoint occurrence inventories required")
    boxes = {n: bounds(s) for n, s in obstacles.items()}
    near, separated = [], []
    for a, shape in movers.items():
        bb = np.asarray(bounds(shape))
        swept = np.r_[bb[:3] + np.minimum(start, 0), bb[3:] + np.maximum(start, 0)]
        for b, other in boxes.items():
            if any(
                swept[i + 3] < other[i] - 1e-7 or other[i + 3] < swept[i] - 1e-7 for i in range(3)
            ):
                separated.append([a, b])
            else:
                near.append((a, b))
    count = max(1, math.ceil(float(np.linalg.norm(start)) / step_mm))
    samples = []
    for t in np.linspace(1, 0, count + 1):
        offset = start * t
        shapes = {n: s.translate(tuple(offset)) for n, s in movers.items()} | obstacles
        checked = inspect_pairs(shapes, near)
        samples.append(
            {
                "offset_mm": offset.tolist(),
                "counts": checked["counts"],
                "unresolved_or_failed": [r for r in checked["pairs"] if r["status"] != "PASS"],
            }
        )
    return {
        "movers": sorted(movers),
        "obstacles": sorted(obstacles),
        "start_offset_mm": start.tolist(),
        "end_offset_mm": [0, 0, 0],
        "sample_step_max_mm": float(np.linalg.norm(start)) / count,
        "continuously_separated_by_swept_aabb": separated,
        "sampled_pairs": near,
        "samples": samples,
        "sampled_path_clear": all(not s["unresolved_or_failed"] for s in samples),
        "continuous_near_pair_proof": False,
        "hand_clearance_verified": False,
    }


def run(assembly, out):
    if out.exists():
        raise FileExistsError(out)
    rows = read_step(assembly)[2]
    shapes = {r.name: r.world for r in rows}
    if len(rows) != len(shapes):
        raise ValueError("ambiguous occurrence identity")
    cluster = camera_stages(shapes)["B_carrier_to_bracket_after_A"][0]
    arm = {n: s for n, s in shapes.items() if not n.startswith("CAMERA_")}
    result = {
        "assembly_sha256": digest(assembly),
        "checker_sha256": digest(Path(__file__)),
        "powered_motion": False,
        "installation_approved": False,
        "stages": {},
    }
    for name, moving, fixed in (
        ("camera_cluster_lower_from_above_before_M3", cluster, arm),
        (
            "front_jaw_lower_after_camera_cluster_before_M3",
            {"CAMERA_front_jaw": shapes["CAMERA_front_jaw"]},
            arm | cluster,
        ),
    ):
        result["stages"][name] = sample_translation(moving, fixed, (0, 0, 60))
        r = result["stages"][name]
        print(
            name,
            "clear",
            r["sampled_path_clear"],
            "near pairs",
            len(r["sampled_pairs"]),
            "failures",
            dict(Counter(x["status"] for s in r["samples"] for x in s["unresolved_or_failed"])),
            flush=True,
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    return 2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("assembly", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    raise SystemExit(run(args.assembly, args.out))
