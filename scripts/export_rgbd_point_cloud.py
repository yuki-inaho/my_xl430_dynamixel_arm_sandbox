"""Export an aligned RGB-D capture through the existing RGB-D utility to PLY/HTML."""

import argparse
import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
import open3d as o3d
import plotly.graph_objects as go


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--rgbd-project", type=Path, required=True)
    parser.add_argument(
        "--max-depth",
        type=float,
        default=2.5,
        help="Display clipping in metres; PLY retains all valid depth",
    )
    parser.add_argument("--max-display-points", type=int, default=30000)
    args = parser.parse_args()
    if args.max_depth <= 0 or args.max_display_points < 1:
        parser.error("Display limits must be positive")
    metadata = json.loads((args.capture / "metadata.json").read_text())
    if metadata["alignment_target"] != "color":
        raise ValueError("Expected depth already aligned to RGB")
    intr = metadata["intrinsics"]["color"]
    if any(intr["coeffs"]):
        raise ValueError("Nonzero distortion needs an SDK deprojection adapter")
    rgb = cv2.imread(str(args.capture / "color.png"))
    depth = cv2.imread(str(args.capture / "aligned_depth.png"), cv2.IMREAD_UNCHANGED)
    if rgb is None or depth is None or depth.dtype != np.uint16:
        raise ValueError("Missing RGB/uint16 depth")
    if rgb.shape[:2] != depth.shape or depth.shape != (intr["height"], intr["width"]):
        raise ValueError("Image and intrinsics dimensions differ")
    spec = importlib.util.spec_from_file_location(
        "reused_rgbd_points", args.rgbd_project / "scripts/rgbd/point_clouds.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Existing RGB-D utility module could not be loaded")
    utility = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(utility)
    K = np.array([[intr["fx"], 0, intr["ppx"]], [0, intr["fy"], intr["ppy"]], [0, 0, 1]])
    result = utility.generate_colorized_depth_point_from_rgb_d_images(
        cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB), depth, K, metadata["depth_scale_m_per_count"]
    )
    points, colors = result["points"], result["colors"]
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)
    if not o3d.io.write_point_cloud(str(args.capture / "point-cloud.ply"), pcd):
        raise RuntimeError("PLY write failed")
    mask = np.isfinite(points).all(axis=1) & (points[:, 2] <= args.max_depth)
    displayed, shades = points[mask], colors[mask]
    if not len(displayed):
        raise ValueError("No points inside display range")
    stride = max(1, (len(displayed) + args.max_display_points - 1) // args.max_display_points)
    displayed, shades = displayed[::stride], shades[::stride]
    rgb_strings = [f"rgb({c[0]},{c[1]},{c[2]})" for c in np.clip(shades * 255, 0, 255).astype(int)]
    fig = go.Figure(
        go.Scatter3d(
            x=displayed[:, 0],
            y=displayed[:, 1],
            z=displayed[:, 2],
            mode="markers",
            marker=dict(size=2, color=rgb_strings),
        )
    )
    device_name = metadata["device"].get("name", "RGB-D camera")
    fig.update_layout(
        title=f"{device_name}実撮影の色付き点群 · {metadata['captured_at']}",
        template="plotly_dark",
        height=760,
        scene=dict(
            aspectmode="data",
            xaxis_title="右 X [m]",
            yaxis_title="下 Y [m]",
            zaxis_title="前 Z [m]",
            camera=dict(up=dict(x=0, y=-1, z=0), eye=dict(x=0.15, y=-0.1, z=-1.8)),
        ),
    )
    fig.write_html(str(args.capture / "point-cloud.html"), include_plotlyjs=True)
    info = dict(
        capture=str(args.capture.resolve()),
        ply_point_count=len(points),
        displayed_point_count=len(displayed),
        display_max_depth_m=args.max_depth,
        display_stride=stride,
        coordinate_frame="RGB optical: right/down/forward; metres",
        axis_transform="none",
        depth_scale_m_per_count=metadata["depth_scale_m_per_count"],
    )
    (args.capture / "point-cloud.json").write_text(json.dumps(info, ensure_ascii=False, indent=2))
    print(json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main()
