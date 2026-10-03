"""Attribute pad silhouette occlusion to saved scene geometry, not object ROI."""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from gripper_design.pg2 import digest
from scripts.review_pg3_camera_range import mesh_assets
from scripts.review_pg3_occlusion import visibility
from simulation.pg3_scene import mujoco, set_pose


def attribute_pixels(reference, segmentation, target_id, geom_names, geom_type):
    reference, segmentation = np.asarray(reference), np.asarray(segmentation)
    if (
        reference.ndim != 2
        or reference.dtype != np.bool_
        or segmentation.shape != (*reference.shape, 2)
        or not np.issubdtype(segmentation.dtype, np.integer)
        or target_id not in geom_names
    ):
        raise ValueError(
            "boolean reference, matching integer segmentation and known target required"
        )
    actual = (segmentation[:, :, 0] == target_id) & (segmentation[:, :, 1] == geom_type)
    if np.any(actual & ~reference):
        raise ValueError("actual target pixels outside reference")
    hidden = reference & ~actual
    ids, counts = np.unique(segmentation[hidden], axis=0, return_counts=True)
    occluders, unknown = [], []
    for (gid, kind), count in zip(ids, counts, strict=True):
        row = {"geom_id": int(gid), "object_type": int(kind), "pixels": int(count)}
        if kind == geom_type and gid in geom_names:
            row["name"] = geom_names[gid]
            occluders.append(row)
        else:
            row["reason"] = "background_or_non_geom_or_unknown_id"
            unknown.append(row)
    total, visible = int(reference.sum()), int(actual.sum())
    blocked, unclassified = sum(r["pixels"] for r in occluders), sum(r["pixels"] for r in unknown)
    if visible + blocked + unclassified != total:
        raise ValueError("pixel conservation failure")
    return {
        "reference_pixels": total,
        "visible_pixels": visible,
        "visible_fraction": visible / total if total else None,
        "occluded_pixels": blocked,
        "unclassified_pixels": unclassified,
        "occluders": sorted(occluders, key=lambda r: (-r["pixels"], r["geom_id"])),
        "unclassified": unknown,
    }


def masks(renderer, model, data, gid):
    renderer.enable_segmentation_rendering()
    renderer.update_scene(data, camera="camera_proxy")
    actual = renderer.render().copy()
    original = model.geom_group.copy()
    option = mujoco.MjvOption()
    option.geomgroup[:] = 0
    option.geomgroup[0] = 1
    try:
        model.geom_group[:] = 5
        model.geom_group[gid] = 0
        renderer.update_scene(data, camera="camera_proxy", scene_option=option)
        solo = renderer.render().copy()
    finally:
        model.geom_group[:] = original
    reference = (solo[:, :, 0] == gid) & (solo[:, :, 1] == mujoco.mjtObj.mjOBJ_GEOM)
    return reference, actual


def run(checkpoint, out):
    scene = checkpoint / "simulation/scene.xml"
    manifest = json.loads((checkpoint / "review.json").read_text())["output_sha256"]
    assets = mesh_assets(scene)
    inputs = {"simulation/scene.xml": digest(scene)} | {
        f"simulation/{p}": h for p, h in assets.items()
    }
    if any(manifest.get(p) != h for p, h in inputs.items()):
        raise ValueError("frozen scene/mesh SHA mismatch")
    out.mkdir(parents=True, exist_ok=False)
    model = mujoco.MjModel.from_xml_path(str(scene))
    model.vis.quality.offsamples = 0
    data = mujoco.MjData(model)
    renderer = mujoco.Renderer(model, 480, 640)
    geom_type = int(mujoco.mjtObj.mjOBJ_GEOM)
    names = {i: model.geom(i).name or f"unnamed_geom_{i}" for i in range(model.ngeom)}
    samples, files = [], []
    try:
        for angle in (25, 90, 135):
            for roll in (-30, 0, 30):
                set_pose(model, data, angle, roll)
                pads = {}
                for side in ("R", "L"):
                    target = f"PG3_pad_{side}"
                    gid = model.geom(target).id
                    ref, actual = masks(renderer, model, data, gid)
                    result = attribute_pixels(ref, actual, gid, names, geom_type)
                    baseline = visibility(renderer, model, data, target)
                    if (
                        result["reference_pixels"] != baseline["unobstructed_silhouette_pixels"]
                        or result["visible_pixels"] != baseline["visible_pixels"]
                    ):
                        raise ValueError("existing visibility cross-check failed")
                    result["existing_visibility_crosscheck"] = True
                    pads[side] = result
                    classified = np.zeros((*ref.shape, 3), dtype=np.uint8)
                    classified[ref] = (235, 180, 35)
                    for row in result["occluders"]:
                        mask = (
                            ref
                            & (actual[:, :, 0] == row["geom_id"])
                            & (actual[:, :, 1] == geom_type)
                        )
                        classified[mask] = (220, 65, 55)
                    classified[ref & (actual[:, :, 0] == gid) & (actual[:, :, 1] == geom_type)] = (
                        45,
                        195,
                        115,
                    )
                    path = out / f"mask_a{angle}_r{roll}_{side}.png"
                    Image.fromarray(classified).save(path)
                    files.append(path)
                renderer.disable_segmentation_rendering()
                renderer.update_scene(data, camera="camera_proxy")
                path = out / f"rgb_a{angle}_r{roll}.png"
                Image.fromarray(renderer.render().copy()).save(path)
                files.append(path)
                samples.append({"opening_degrees": angle, "roll_degrees": roll, "pads": pads})
                print(angle, roll, {s: p["occluders"] for s, p in pads.items()}, flush=True)
    finally:
        renderer.close()
    report = {
        "input_sha256": inputs,
        "samples": samples,
        "mask_colors": {
            "visible": [45, 195, 115],
            "occluded_by_known_geom": [220, 65, 55],
            "unclassified": [235, 180, 35],
            "outside_reference": [0, 0, 0],
        },
        "render_size": [640, 480],
        "segmentation_msaa_samples": 0,
        "all_reference_masks_nonempty": all(
            p["reference_pixels"] > 0 for s in samples for p in s["pads"].values()
        ),
        "all_pixels_classified": all(
            p["unclassified_pixels"] == 0 for s in samples for p in s["pads"].values()
        ),
        "scope": "nine sampled poses; whole-pad silhouettes, not contact faces or grasped-object ROI",
        "camera_or_mount_moved": False,
        "optics_confirmed": False,
        "useful_imaging_approved": False,
        "installation_approved": False,
        "output_sha256": {p.name: digest(p) for p in files},
        "dependencies": {
            p: digest(Path(p))
            for p in (
                "scripts/review_pg3_occluders.py",
                "scripts/review_pg3_occlusion.py",
                "scripts/review_pg3_camera_range.py",
                "simulation/pg3_scene.py",
                "uv.lock",
            )
        },
    }
    (out / "review.json").write_text(json.dumps(report, indent=2) + "\n")
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
