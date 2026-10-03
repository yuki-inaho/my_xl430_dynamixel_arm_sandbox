"""Headless pose-grid framing and occlusion evidence; assumed optics, not calibration."""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image

from gripper_design.pg2 import digest
from simulation.pg3_scene import mujoco, segmentation_bounds, set_pose


def projected_bounds(model, data, name, width=640, height=480):
    gid = model.geom(name).id
    mid = model.geom_dataid[gid]
    vertices = model.mesh_vert[
        model.mesh_vertadr[mid] : model.mesh_vertadr[mid] + model.mesh_vertnum[mid]
    ]
    world = vertices @ data.geom_xmat[gid].reshape(3, 3).T + data.geom_xpos[gid]
    camera = data.camera("camera_proxy")
    local = (world - camera.xpos) @ camera.xmat.reshape(3, 3)
    if np.any(-local[:, 2] <= 1e-6):
        return None
    f = height / 2 / np.tan(np.deg2rad(model.cam_fovy[camera.id]) / 2)
    x = (width - 1) / 2 + f * local[:, 0] / -local[:, 2]
    y = (height - 1) / 2 - f * local[:, 1] / -local[:, 2]
    return [float(x.min()), float(y.min()), float(x.max()), float(y.max())]


def run(scene, out, *, angles=range(25, 136, 5), rolls=range(-30, 31, 5)):
    out.mkdir(parents=True, exist_ok=False)
    model = mujoco.MjModel.from_xml_path(str(scene))
    # Explicit no-MSAA segmentation pass prevents mixed integer IDs at edges.
    old_msaa = model.vis.quality.offsamples
    model.vis.quality.offsamples = 0
    data = mujoco.MjData(model)
    renderer = mujoco.Renderer(model, 480, 640)
    samples = []
    try:
        for angle in angles:
            for roll in rolls:
                set_pose(model, data, angle, roll)
                renderer.enable_segmentation_rendering()
                renderer.update_scene(data, camera="camera_proxy")
                seg = renderer.render().copy()
                pads = {}
                for side in ("R", "L"):
                    name = f"PG3_pad_{side}"
                    bounds = projected_bounds(model, data, name)
                    pixels = int(
                        np.count_nonzero(
                            (seg[:, :, 0] == model.geom(name).id)
                            & (seg[:, :, 1] == mujoco.mjtObj.mjOBJ_GEOM)
                        )
                    )
                    margin = (
                        None
                        if bounds is None
                        else min(bounds[0], bounds[1], 639 - bounds[2], 479 - bounds[3])
                    )
                    pads[side] = {
                        "projected_bounds_px": bounds,
                        "margin_px": margin,
                        "visible_pixels": pixels,
                        "visible_bounds_px": segmentation_bounds(seg, model.geom(name).id),
                        "framing_pass": margin is not None and margin >= 20,
                        "not_fully_occluded": pixels > 0,
                    }
                samples.append({"opening_degrees": angle, "roll_degrees": roll, "pads": pads})
                if angle in (25, 90, 135) and roll in (-30, 0, 30):
                    renderer.disable_segmentation_rendering()
                    renderer.update_scene(data, camera="camera_proxy")
                    Image.fromarray(renderer.render()).save(out / f"camera_a{angle}_r{roll}.png")
    finally:
        renderer.close()
    ok = all(
        p["framing_pass"] and p["not_fully_occluded"] for s in samples for p in s["pads"].values()
    )
    report = {
        "scene_sha256": digest(scene),
        "mesh_assets_sha256": mesh_assets(scene),
        "source_msaa_samples": int(old_msaa),
        "segmentation_msaa_samples": 0,
        "scope": "sampled_proxy_optics_not_actual_camera_acceptance",
        "framing_margin_requirement_px": 20,
        "sample_count": len(samples),
        "framing_and_nonzero_visibility_pass": ok,
        "samples": samples,
        "optical_calibration_verified": False,
        "continuous_motion_proof": False,
    }
    (out / "camera_range.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "samples"}, indent=2), flush=True)
    return 0 if ok else 2


def mesh_assets(scene):
    tree = ET.parse(scene)
    compiler = tree.find("compiler")
    directory = "" if compiler is None else compiler.get("meshdir", "")
    result = {}
    for mesh in tree.findall("asset/mesh"):
        name = mesh.get("file")
        if name is not None:
            path = (scene.parent / directory / name).resolve()
            if not path.is_relative_to(scene.parent.resolve()):
                raise ValueError("mesh asset is outside the scene evidence directory")
            result[str(path.relative_to(scene.parent.resolve()))] = digest(path)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.scene, args.out))
