"""Diagnostic framing sweep for an unpurchased ID5-mounted camera."""

from __future__ import annotations

import argparse
import json
import math
from itertools import product
from pathlib import Path
from types import SimpleNamespace

from gripper_design.pg3 import PG3Model
from gripper_design.pg3_id5 import assemble


def corners(box) -> list[tuple[float, float, float]]:
    return list(product((box.xmin, box.xmax), (box.ymin, box.ymax), (box.zmin, box.zmax)))


def segment_hits_box(start, end, box) -> bool:
    """Conservative segment/AABB test; a hit is not a proven B-rep occlusion."""
    near, far = 0.0, 1.0
    for index, bounds in enumerate(
        ((box.xmin, box.xmax), (box.ymin, box.ymax), (box.zmin, box.zmax))
    ):
        delta = end[index] - start[index]
        if abs(delta) < 1e-9:
            if not bounds[0] <= start[index] <= bounds[1]:
                return False
            continue
        entry, exit_ = sorted(
            ((bounds[0] - start[index]) / delta, (bounds[1] - start[index]) / delta)
        )
        near, far = max(near, entry), min(far, exit_)
        if near > far:
            return False
    return near < 1 - 1e-6 and far > 1e-6


def cube_fits_between_pads(left_pad, right_pad, center_x: float, edge_mm: float) -> bool:
    half = edge_mm / 2
    return center_x - half >= left_pad.xmax and center_x + half <= right_pad.xmin


def camera_axes(origin, target):
    vector = [b - a for a, b in zip(origin, target)]
    length = math.sqrt(sum(value**2 for value in vector))
    forward = tuple(value / length for value in vector)
    if forward[1] <= 0 or forward[2] >= 0:
        raise ValueError("camera must face forward and downward toward the grasp zone")
    # The scan stays in the assembly YZ plane, so camera-right is world +X.
    right = (1.0, 0.0, 0.0)
    up = (0.0, -forward[2], forward[1])
    return forward, right, up


def frame_bounds(origin, target, box, fov_y_deg=50.0, aspect=4 / 3):
    forward, right, up = camera_axes(origin, target)
    tan_y = math.tan(math.radians(fov_y_deg) / 2)
    tan_x = tan_y * aspect
    projected = []
    for corner in corners(box):
        vector = [b - a for a, b in zip(origin, corner)]
        depth = sum(a * b for a, b in zip(vector, forward))
        if depth <= 0:
            return None
        projected.append(
            (
                sum(a * b for a, b in zip(vector, right)) / (depth * tan_x),
                sum(a * b for a, b in zip(vector, up)) / (depth * tan_y),
            )
        )
    return [
        round(min(x for x, _ in projected), 4),
        round(min(y for _, y in projected), 4),
        round(max(x for x, _ in projected), 4),
        round(max(y for _, y in projected), 4),
    ]


def write_proxy_preview(report: dict, out: Path, origin=(-0.2, 178.0, 226.0)) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch, Rectangle

    candidate = next(
        row for row in report["candidates"] if tuple(row["camera_proxy_origin_world_mm"]) == origin
    )
    figure, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    palette = {"pad_L": "#087e8b", "pad_R": "#d1495b", "diagnostic_cube": "#587b36"}
    for ax, pose in zip(axes, candidate["poses"]):
        ax.add_patch(Rectangle((-1, -1), 2, 2, fill=False, edgecolor="black"))
        cube = next(
            (
                f"cube_{edge}_diagnostic"
                for edge in (20, 10)
                if pose["targets"][f"cube_{edge}_diagnostic"]["fits_nominal_pad_gap"]
            ),
            None,
        )
        for name in ("pad_L", "pad_R", cube):
            if name is None:
                continue
            color = palette["diagnostic_cube" if name.startswith("cube") else name]
            xmin, ymin, xmax, ymax = pose["targets"][name]["projected_bounds_normalized"]
            ax.add_patch(
                Rectangle(
                    (xmin, ymin),
                    xmax - xmin,
                    ymax - ymin,
                    facecolor=color,
                    edgecolor=color,
                    alpha=0.25,
                )
            )
        ax.set(
            xlim=(-1, 1),
            ylim=(-1, 1),
            title=f"PG3 {pose['angle_deg']} deg / gap {pose['pad_gap_mm']:.1f} mm",
        )
        ax.set_aspect("equal")
        ax.grid(alpha=0.15)
    figure.suptitle("Assumed 50 deg vertical FOV / box projection only", fontsize=11, y=0.95)
    figure.legend(
        [Patch(facecolor=color, edgecolor=color, alpha=0.4) for color in palette.values()],
        ["Left pad", "Right pad", "Diagnostic cube when gap permits"],
        loc="lower center",
        ncol=3,
        frameon=False,
    )
    figure.tight_layout(rect=(0, 0.08, 1, 0.87))
    figure.savefig(out / "vision_proxy_three_poses.png", dpi=160)
    plt.close(figure)


def diagnostic_scan(out: Path) -> dict:
    if out.exists():
        raise FileExistsError(out)
    model = PG3Model()
    assemblies = {angle: assemble(model, angle) for angle in (25, 90, 135)}
    target = (-0.2, 214.6, 164.6)
    candidates = []
    for y, z in product((170.0, 174.0, 178.0, 180.0), (220.0, 226.0, 232.0, 238.0)):
        origin = (-0.2, y, z)
        forward, _, _ = camera_axes(origin, target)
        pose_rows = []
        all_framed = True
        potential_frame_blockers = 0
        for angle, assembly in assemblies.items():
            frame = assembly["PG3_frame"].BoundingBox()
            left_pad = assembly["PG3_pad_L"].BoundingBox()
            right_pad = assembly["PG3_pad_R"].BoundingBox()
            pad_gap = right_pad.xmin - left_pad.xmax
            targets = {}
            for side in ("L", "R"):
                box = assembly[f"PG3_pad_{side}"].BoundingBox()
                projected = frame_bounds(origin, target, box)
                framed = projected is not None and max(abs(v) for v in projected) <= 1
                blockers = sum(segment_hits_box(origin, corner, frame) for corner in corners(box))
                all_framed &= framed
                potential_frame_blockers += blockers
                targets[f"pad_{side}"] = {
                    "projected_bounds_normalized": projected,
                    "all_bbox_corners_in_assumed_fov": framed,
                    "frame_aabb_hit_corner_rays": blockers,
                }
            for edge in (10.0, 20.0, 30.0):
                half = edge / 2
                cube = SimpleNamespace(
                    xmin=target[0] - half,
                    xmax=target[0] + half,
                    ymin=target[1] - half,
                    ymax=target[1] + half,
                    zmin=target[2] - half,
                    zmax=target[2] + half,
                )
                projected = frame_bounds(origin, target, cube)
                targets[f"cube_{int(edge)}_diagnostic"] = {
                    "projected_bounds_normalized": projected,
                    "all_bbox_corners_in_assumed_fov": (
                        projected is not None and max(abs(v) for v in projected) <= 1
                    ),
                    "fits_nominal_pad_gap": cube_fits_between_pads(
                        left_pad, right_pad, target[0], edge
                    ),
                    "size_is_user_requirement": False,
                }
            pose_rows.append(
                {"angle_deg": angle, "pad_gap_mm": round(pad_gap, 3), "targets": targets}
            )
        candidates.append(
            {
                "camera_proxy_origin_world_mm": origin,
                "target_world_mm": target,
                "down_angle_from_horizontal_deg": round(
                    math.degrees(math.atan2(-forward[2], forward[1])), 2
                ),
                "all_pad_bbox_corners_in_assumed_fov": all_framed,
                "potential_frame_aabb_hit_corner_rays": potential_frame_blockers,
                "poses": pose_rows,
            }
        )
    result = {
        "scope": "diagnostic_proxy_fov_and_aabb_only_not_actual_visibility_or_camera_mount_geometry",
        "assumed_vertical_fov_deg": 50.0,
        "assumed_aspect": 4 / 3,
        "camera_model_confirmed": False,
        "camera_body_mount_cable_occlusion_checked": False,
        "candidates": candidates,
    }
    out.mkdir(parents=True)
    (out / "vision_proxy_scan.json").write_text(json.dumps(result, indent=2) + "\n")
    write_proxy_preview(result, out)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = diagnostic_scan(args.out)
    print(
        json.dumps(
            [
                {
                    "origin": row["camera_proxy_origin_world_mm"],
                    "down_angle_deg": row["down_angle_from_horizontal_deg"],
                    "pads_in_fov": row["all_pad_bbox_corners_in_assumed_fov"],
                    "frame_aabb_hit_corner_rays": row["potential_frame_aabb_hit_corner_rays"],
                }
                for row in report["candidates"]
            ],
            indent=2,
        )
    )
