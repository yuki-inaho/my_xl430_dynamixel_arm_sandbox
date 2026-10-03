"""Conservative continuous translation cover, not a sampled-motion certificate.

For a bounded solid S and segment D, S+D is covered by S and (boundary(S)+D):
any newly occupied point has a reverse trajectory crossing the original boundary.
Replacing EACH boundary face by its AABB and sweeping that box is conservative.
Overlaps in this cover can prevent proof but cannot establish physical collision.
This checks occupied volume, allowing zero-volume surface contact, not a positive
clearance margin or hand space. Rotation is not supported.
"""

import argparse
import json
from pathlib import Path

import cadquery as cq
import numpy as np

from gripper_design.pg2 import _solid_only, digest
from scripts.assembly_io import bounds, read_step
from scripts.review_pg3 import inspect_pairs
from scripts.verify_pg3_service_stages import camera_stages


def translation_cover(shape, offset):
    if not shape.isValid() or not _solid_only(shape):
        raise ValueError("valid solid-only moving material required")
    direction = np.asarray(offset, dtype=float)
    if direction.shape != (3,) or not np.isfinite(direction).all():
        raise ValueError("finite translation vector required")
    cover, zero_volume = {"original": shape}, []
    for i, face in enumerate(shape.Faces()):
        box = np.asarray(bounds(face))
        low = box[:3] + np.minimum(direction, 0)
        high = box[3:] + np.maximum(direction, 0)
        size = high - low
        if not np.isfinite(box).all() or np.any(size < 0):
            raise ValueError("invalid boundary cover bounds")
        if np.any(size == 0):
            # Exactly planar degenerate swept boxes contain zero 3D volume.
            # Do not discard small positive widths with a numerical cutoff.
            zero_volume.append({"face": i, "bounds_mm": [*low.tolist(), *high.tolist()]})
            continue
        cover[f"face_{i}"] = cq.Solid.makeBox(*size, tuple(low))
    return cover, zero_volume


def certify_pair(mover, obstacle, offset):
    cover, zero = translation_cover(mover, offset)
    result = inspect_pairs(cover | {"obstacle": obstacle}, [(n, "obstacle") for n in cover])
    rows = result["pairs"]
    upper_bound = sum(r.get("volume_mm3", r.get("conservative_intersection_mm3", 0)) for r in rows)
    clear = all(r["status"] == "PASS" for r in rows) and upper_bound <= 1e-4
    return {
        "status": "PROVEN_CLEAR" if clear else "UNPROVEN",
        "positive_clearance_required": False,
        "overlap_upper_bound_mm3": upper_bound if clear else None,
        "zero_volume_boundary_boxes": zero,
        "cover_checks": result,
    }


def run(assembly, out):
    if out.exists():
        raise FileExistsError(out)
    loaded = read_step(assembly)[2]
    shapes = {r.name: r.world for r in loaded}
    if len(shapes) != len(loaded):
        raise ValueError("ambiguous occurrence identity")
    cluster = camera_stages(shapes)["B_carrier_to_bracket_after_A"][0]
    arm = {n: s for n, s in shapes.items() if not n.startswith("CAMERA_")}
    result = {
        "assembly_sha256": digest(assembly),
        "checker_sha256": digest(Path(__file__)),
        "scope": "fixed_arm_mid_pose_translation_only_before_M3_no_hand_or_cable",
        "stages": {},
    }
    for name, movers, obstacles in (
        ("camera_cluster", cluster, arm),
        (
            "front_jaw_after_cluster",
            {"CAMERA_front_jaw": shapes["CAMERA_front_jaw"]},
            arm | cluster,
        ),
    ):
        far, near = [], []
        boxes = {n: bounds(s) for n, s in obstacles.items()}
        for a, mover in movers.items():
            swept = bounds(mover)
            swept[5] += 60
            for b, bb in boxes.items():
                if any(
                    swept[i + 3] < bb[i] - 1e-7 or bb[i + 3] < swept[i] - 1e-7 for i in range(3)
                ):
                    far.append([a, b])
                else:
                    near.append({"a": a, "b": b, **certify_pair(mover, obstacles[b], (0, 0, 60))})
        result["stages"][name] = {
            "movers": sorted(movers),
            "obstacles": sorted(obstacles),
            "start_offset_mm": [0, 0, 60],
            "end_offset_mm": [0, 0, 0],
            "far_pairs": far,
            "near_pairs": near,
            "continuous_translation_volume_clear": all(r["status"] == "PROVEN_CLEAR" for r in near),
        }
        assert len(far) + len(near) == len(movers) * len(obstacles)
        print(
            name, "far", len(far), "near", [(r["a"], r["b"], r["status"]) for r in near], flush=True
        )
    result["installation_approved"] = False
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    return 2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("assembly", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    raise SystemExit(run(args.assembly, args.out))
