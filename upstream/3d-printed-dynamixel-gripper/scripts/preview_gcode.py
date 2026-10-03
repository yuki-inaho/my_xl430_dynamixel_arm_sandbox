"""Render actual linear relative-extrusion toolpaths, without executing G-code."""

import argparse
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from mpl_toolkits.mplot3d.art3d import Line3DCollection


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("gcode", type=Path)
    p.add_argument("out", type=Path)
    args = p.parse_args()
    pos = np.zeros(3)
    segments, colors, first = [], [], []
    role = "Custom"
    relative_e, absolute_xyz = False, True
    palette = {"saddle.stl": "#128996", "front_jaw.stl": "#b9562a", "camera_spacer.stl": "#558032"}
    obj = "saddle.stl"
    for line in args.gcode.read_text().splitlines():
        if line.startswith(";TYPE:"):
            role = line[6:]
        found = re.match(r"; printing object (\S+) id:", line)
        if found:
            obj = found[1]
        words = line.split(";", 1)[0].split()
        if not words:
            continue
        cmd = words[0]
        if cmd in ("G90", "G91"):
            absolute_xyz = cmd == "G90"
        if cmd in ("M82", "M83"):
            relative_e = cmd == "M83"
        if cmd not in ("G0", "G1"):
            continue
        if not absolute_xyz or not relative_e:
            raise ValueError("Preview supports only absolute XYZ + relative E")
        vals = {s[0]: float(s[1:]) for s in words[1:] if s[0] in "XYZEF"}
        target = np.array([vals.get(a, pos[i]) for i, a in enumerate("XYZ")])
        if (
            vals.get("E", 0) > 0
            and np.linalg.norm(target[:2] - pos[:2]) > 0.001
            and role != "Custom"
        ):
            pair = [pos.copy(), target.copy()]
            color = "#999ca2" if "Support" in role else palette.get(obj, "#444444")
            segments.append(pair)
            colors.append(color)
            if target[2] < 0.21:
                first.append(pair)
        pos = target
    if not segments or not first:
        raise ValueError("No extrusion toolpaths")
    seg = np.array(segments)
    fig = plt.figure(figsize=(15, 7))
    ax = fig.add_subplot(121)
    ax.add_collection(LineCollection(np.array(first)[:, :, :2], linewidths=0.4, colors="#128996"))
    ax.set(
        xlim=(0, 220),
        ylim=(0, 220),
        xlabel="X (mm)",
        ylabel="Y (mm)",
        title="First layer - one 220 x 220 mm plate",
    )
    ax.set_aspect("equal")
    ax.grid(alpha=0.15)
    ax3 = fig.add_subplot(122, projection="3d")
    ax3.add_collection3d(Line3DCollection(seg, colors=colors, linewidths=0.2, alpha=0.75))
    b0, b1 = seg.min(axis=(0, 1)), seg.max(axis=(0, 1))
    ax3.set(
        xlim=(b0[0], b1[0]),
        ylim=(b0[1], b1[1]),
        zlim=(0, b1[2]),
        xlabel="X",
        ylabel="Y",
        zlabel="Z",
        title="Extrusion paths (gray: supports)",
    )
    ax3.set_box_aspect((b1[0] - b0[0], b1[1] - b0[1], b1[2]))
    ax3.view_init(elev=25, azim=-50)
    fig.tight_layout()
    fig.savefig(args.out, dpi=160)
    print(
        {
            "extruding_segments": len(segments),
            "first_layer_segments": len(first),
            "bounds_mm": [b0.tolist(), b1.tolist()],
        }
    )


if __name__ == "__main__":
    main()
