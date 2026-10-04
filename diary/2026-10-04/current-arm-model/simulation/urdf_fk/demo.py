"""Export URDF, evaluate forward kinematics and save MuJoCo images."""

import argparse
import json
import math
import os
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")
import cv2
import mujoco
import numpy as np

from .model import (
    ROOT,
    SPEC,
    export_model,
    load_config,
    load_scene,
    numeric_vector,
    sha256,
    urdf_fk,
)


def checked_angles(model, angles):
    angles = numeric_vector(angles, 4)
    q = np.radians(angles)
    if np.any(q < model.jnt_range[:, 0]) or np.any(q > model.jnt_range[:, 1]):
        raise ValueError("Angles outside demonstration display ranges")
    return angles


def fk_state(model, angles):
    angles = checked_angles(model, angles)
    data = mujoco.MjData(model)
    data.qpos[:] = np.radians(angles)
    mujoco.mj_forward(model, data)
    forward = data.body("tool_link").xmat.reshape(3, 3) @ [0, 1, 0]
    return {
        "simulation_only": True,
        "hardware_targets": None,
        "angles_deg": angles.tolist(),
        "tool_m": data.site("tool_tip").xpos.tolist(),
        "forward_world": forward.tolist(),
        "pitch_deg": math.degrees(math.atan2(forward[2], math.hypot(forward[0], forward[1]))),
        "collision_certified": False,
        "calibrated_physical_pose": False,
    }


def camera_for(view="iso"):
    camera = mujoco.MjvCamera()
    camera.lookat[:] = [0, 0.065, 0.12]
    camera.distance = 0.58
    camera.azimuth, camera.elevation = {
        "iso": (135, -25),
        "side": (0, -10),
        "front": (90, -15),
        "top": (90, -85),
    }[view]
    return camera


def render_pose(model, angles, path, view="iso"):
    data = mujoco.MjData(model)
    data.qpos[:] = np.radians(checked_angles(model, angles))
    mujoco.mj_forward(model, data)
    with mujoco.Renderer(model, height=760, width=1060) as renderer:
        renderer.update_scene(data, camera=camera_for(view))
        rgb = renderer.render()
    if not cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)):
        raise OSError(f"Cannot save MuJoCo image: {path}")


def verify_kinematics(output, cfg):
    model, source = (
        load_scene(output),
        mujoco.MjModel.from_xml_path(str(ROOT / cfg["source_scene"])),
    )
    data, original = mujoco.MjData(model), mujoco.MjData(source)
    records = []
    meshes = json.loads((Path(output) / "model-manifest.json").read_text())["meshes"]
    for angles in cfg["validation"]["poses_deg"]:
        q = np.radians(angles)
        data.qpos[:] = q
        for name, value in zip(cfg["joint_names"], q):
            original.qpos[source.joint(name).qposadr[0]] = value
        mujoco.mj_forward(model, data)
        mujoco.mj_forward(source, original)
        independent = urdf_fk(Path(output) / "robot.urdf", q)
        errors = [np.max(np.abs(data.site("tool_tip").xpos - original.body("c7_fixed").xpos))]
        for body in cfg["body_names"]:
            errors.extend(
                [
                    np.max(np.abs(data.body(body).xpos - original.body(body).xpos)),
                    np.max(np.abs(data.body(body).xpos - independent[body][:3, 3])),
                    np.max(np.abs(data.body(body).xmat.reshape(3, 3) - independent[body][:3, :3])),
                ]
            )
        geometry_error = 0.0
        for entry in meshes:
            bounds = []
            for m, d in ((model, data), (source, original)):
                geom = m.geom(entry["name"])
                mid = m.geom_dataid[geom.id]
                start, count = m.mesh_vertadr[mid], m.mesh_vertnum[mid]
                world = (
                    m.mesh_vert[start : start + count] @ d.geom_xmat[geom.id].reshape(3, 3).T
                    + d.geom_xpos[geom.id]
                )
                bounds.append(np.stack((world.min(0), world.max(0))))
            geometry_error = max(geometry_error, float(np.max(np.abs(bounds[0] - bounds[1]))))
        records.append(
            {
                "angles_deg": angles,
                "max_transform_error": float(max(errors)),
                "max_world_mesh_bounds_error_m": geometry_error,
            }
        )
    worst = max(r["max_transform_error"] for r in records)
    geometry = max(r["max_world_mesh_bounds_error_m"] for r in records)
    if (
        worst > cfg["validation"]["fk_tolerance_m"]
        or geometry > cfg["validation"]["geometry_tolerance_m"]
    ):
        raise ValueError("Exported FK or meshes mismatch source")
    return {
        "pass": True,
        "poses": records,
        "max_transform_error": worst,
        "max_geometry_error_m": geometry,
        "source_scene_sha256": cfg["source_scene_sha256"],
    }


def run(output, cfg):
    output = Path(output)
    export_model(cfg, output)
    model = load_scene(output)
    poses = []
    for pose in cfg["poses"]:
        state = fk_state(model, pose["angles_deg"])
        state.update(name=pose["name"], label=pose["label"])
        independent = urdf_fk(output / "robot.urdf", np.radians(pose["angles_deg"]))["tool_link"]
        state["independent_fk_error_m"] = float(
            np.linalg.norm(independent[:3, 3] - state["tool_m"])
        )
        for view in ("iso", "side"):
            render_pose(model, pose["angles_deg"], output / f"{pose['name']}-{view}.png", view)
        poses.append(state)
    verification = verify_kinematics(output, cfg)
    (output / "verification.json").write_text(json.dumps(verification, indent=2) + "\n")
    result = {
        "simulation_only": True,
        "hardware_targets": None,
        "urdf_sha256": sha256(output / "robot.urdf"),
        "poses": poses,
        "verification": verification,
    }
    (output / "fk-results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--spec", type=Path, default=SPEC)
    args = parser.parse_args()
    run(args.output, load_config(args.spec))


if __name__ == "__main__":
    main()
