"""Headless waypoint views from the same saved CAD and insertion plan."""

import argparse
import json
from pathlib import Path

from gripper_design.pg2 import digest
from scripts.assembly_io import read_step
from scripts.render_cad import render
from scripts.review_pg3_pad_insertion import pad_stages


def color(name):
    if name.startswith("PG3_finger_") and not name.endswith(("_bolt", "_nut", "_washer")):
        return (0.9, 0.3, 0.1)
    if name.startswith("PG3_pad_"):
        return (0.1, 0.12, 0.14)
    return (0.65, 0.68, 0.71)


def run(checkpoint, out):
    path = checkpoint / "arm_camera_mid_CANDIDATE.step"
    expected = json.loads((checkpoint / "review.json").read_text())["output_sha256"][path.name]
    if digest(path) != expected:
        raise ValueError("saved input SHA mismatch")
    rows = read_step(path)[2]
    shapes = {r.name: r.world for r in rows}
    if len(shapes) != len(rows):
        raise ValueError("ambiguous occurrence identity")
    stages = pad_stages(shapes)
    out.mkdir(parents=True, exist_ok=False)
    manifest = {
        "assembly_sha256": expected,
        "scope": "fixed mid; cropped -Y view of pad installation before camera; visual aid only",
        "legend": {"moving_pad": "green", "installed_pad": "dark", "fingers": "orange"},
        "focus_mm": [58, 234.9, 164.6],
        "view_direction": [0, -1, 0],
        "parallel_scale_mm": 62,
        "frames": [],
        "installation_approved": False,
        "source_sha256": {
            p: digest(Path(p))
            for p in (
                "scripts/render_pg3_pad_insertion.py",
                "scripts/render_cad.py",
                "scripts/review_pg3_pad_insertion.py",
                "scripts/assembly_io.py",
                "scripts/verify_pg3_service_stages.py",
                "uv.lock",
            )
        },
    }
    for name, (movers, obstacles, waypoints) in stages.items():
        for i, point in enumerate(waypoints):
            filename = f"{name}_{i}.png"
            bodies = [(s, color(n)) for n, s in obstacles.items()]
            bodies += [(s.translate(point), (0.05, 0.7, 0.25)) for s in movers.values()]
            render(
                bodies,
                out / filename,
                direction=(0, -1, 0),
                focus=(58, 234.9, 164.6),
                scale=62,
                size=(1280, 900),
            )
            manifest["frames"].append(
                {
                    "file": filename,
                    "offset_from_saved_mm": point,
                    "movers": sorted(movers),
                    "obstacles": sorted(obstacles),
                    "sha256": digest(out / filename),
                }
            )
            print(filename, flush=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.checkpoint, args.out)
