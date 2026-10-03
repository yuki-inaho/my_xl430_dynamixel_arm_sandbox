"""Measure pad silhouette occlusion at identical optics; not contact-face visibility."""

import argparse
import json
from pathlib import Path

import numpy as np

from gripper_design.pg2 import digest
from scripts.review_pg3_camera_range import mesh_assets
from simulation.pg3_scene import mujoco, set_pose


def visibility(renderer, model, data, target, camera="camera_proxy"):
    gid = model.geom(target).id

    def mask(option=None):
        renderer.enable_segmentation_rendering()
        renderer.update_scene(data, camera=camera, scene_option=option)
        seg = renderer.render().copy()
        return (seg[:, :, 0] == gid) & (seg[:, :, 1] == mujoco.mjtObj.mjOBJ_GEOM)

    actual = mask()
    original_groups = model.geom_group.copy()
    option = mujoco.MjvOption()
    option.geomgroup[:] = 0
    option.geomgroup[0] = 1
    try:
        model.geom_group[:] = 5
        model.geom_group[gid] = 0
        unobstructed = mask(option)
    finally:
        model.geom_group[:] = original_groups
    visible, reference = int(actual.sum()), int(unobstructed.sum())
    if np.any(actual & ~unobstructed):
        raise ValueError("segmentation reference failed subset control")
    return {
        "visible_pixels": visible,
        "unobstructed_silhouette_pixels": reference,
        "visible_fraction": visible / reference if reference else None,
        "scope": "whole_pad_silhouette_not_grasp_contact_face_or_object_visibility",
    }


def run(scene, out):
    if out.exists():
        raise FileExistsError(out)
    model = mujoco.MjModel.from_xml_path(str(scene))
    model.vis.quality.offsamples = 0
    data = mujoco.MjData(model)
    renderer = mujoco.Renderer(model, 480, 640)
    samples = []
    try:
        for angle in (25, 90, 135):
            for roll in (-30, 0, 30):
                set_pose(model, data, angle, roll)
                samples.append(
                    {
                        "opening_degrees": angle,
                        "roll_degrees": roll,
                        "pads": {
                            s: visibility(renderer, model, data, f"PG3_pad_{s}") for s in ("R", "L")
                        },
                    }
                )
    finally:
        renderer.close()
    result = {
        "scene_sha256": digest(scene),
        "mesh_assets_sha256": mesh_assets(scene),
        "checker_sha256": digest(Path(__file__)),
        "samples": samples,
        "optics_confirmed": False,
        "useful_imaging_approved": False,
        "acceptance_threshold": None,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    for sample in samples:
        print(
            sample["opening_degrees"],
            sample["roll_degrees"],
            {k: v["visible_fraction"] for k, v in sample["pads"].items()},
            flush=True,
        )
    return 2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("scene", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    raise SystemExit(run(args.scene, args.out))
