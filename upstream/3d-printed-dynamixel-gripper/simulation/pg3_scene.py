"""Saved PG3 meshes with slider-crank joints and closed-loop site constraints.

Kinematic diagnostic only: gravity, contacts and force qualification are disabled.
The camera intrinsics/optical origin and body inertias are explicitly assumed.
"""

import json
import math
import os
import xml.etree.ElementTree as ET
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")
import mujoco
import numpy as np
from PIL import Image

from camera_jig.build import CAMERA_ORIGIN
from gripper_design.pg3 import arm_assembly, group_for, opening_mm, position_mm


def values(seq):
    return " ".join(f"{float(v):.12g}" for v in seq)


def color(name):
    if "CAMERA" in name:
        return (0.20, 0.58, 0.66, 1)
    if "pad" in name:
        return (0.16, 0.18, 0.19, 1)
    if "finger" in name and not any(k in name for k in ("bolt", "nut", "washer")):
        return (0.90, 0.45, 0.20, 1)
    if "link" in name:
        return (0.25, 0.65, 0.36, 1)
    if name.startswith("ARM"):
        return (0.60, 0.64, 0.68, 1)
    return (0.76, 0.77, 0.79, 1)


def write_scene(
    pg3, out, *, assembly_factory=arm_assembly, optical_proxy_mm=None, optical_normal=None
):
    whole = assembly_factory(pg3, 90)
    expected = {f"PG3_{name}" for name in pg3.neutral}
    if {name for name in whole if name.startswith("PG3_")} != expected:
        raise ValueError("PG3 occurrence inventory differs from the kinematic model")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    meshdir = out / "meshes"
    meshdir.mkdir()
    root = ET.Element("mujoco", model="PG3_C9_camera_kinematic_diagnostic")
    ET.SubElement(root, "compiler", angle="radian", meshdir="meshes")
    ET.SubElement(root, "option", gravity="0 0 0", timestep="0.002")
    visual = ET.SubElement(root, "visual")
    ET.SubElement(visual, "global", offwidth="960", offheight="720")
    # Integer segmentation IDs must not be mixed at multisampled mesh edges.
    ET.SubElement(visual, "quality", offsamples="0")
    ET.SubElement(visual, "map", znear="0.001", zfar="10")
    default = ET.SubElement(root, "default")
    ET.SubElement(default, "geom", contype="0", conaffinity="0", density="0")
    asset = ET.SubElement(root, "asset")
    world = ET.SubElement(root, "worldbody")
    ET.SubElement(world, "light", pos="0.3 0.1 0.8", dir="-0.2 0.1 -1")
    ET.SubElement(world, "light", pos="-0.4 0.4 0.5", dir="0.2 -0.2 -1")
    roll_origin = np.array([-0.0002, 0.1649, 0.1646])
    roll = ET.SubElement(world, "body", name="J5_roll_diagnostic", pos=values(roll_origin))
    ET.SubElement(roll, "inertial", pos="0 0 0", mass=".01", diaginertia="1e-5 1e-5 1e-5")
    ET.SubElement(roll, "joint", name="wrist_roll", type="hinge", axis="0 1 0")
    base = ET.SubElement(
        roll,
        "body",
        name="PG3_M06",
        pos="0 .0700 0",
        quat=values((math.sqrt(0.5), 0, math.sqrt(0.5), 0)),
    )
    bodies = {"fixed": base}

    def body(parent, name, **attrs):
        b = ET.SubElement(parent, "body", name=name, **attrs)
        ET.SubElement(b, "inertial", pos="0 0 0", mass="0.01", diaginertia="1e-5 1e-5 1e-5")
        return b

    bodies["drive"] = body(base, "drive")
    ET.SubElement(
        bodies["drive"],
        "joint",
        name="crank",
        type="hinge",
        axis="0 0 1",
        limited="true",
        range=values(np.radians([-65, 45])),
    )
    x0 = position_mm(90) / 1000
    equality = ET.SubElement(root, "equality")
    for side, sign in (("R", 1), ("L", -1)):
        bodies[side] = body(base, f"slider_{side}")
        ET.SubElement(bodies[side], "joint", name=f"slide_{side}", type="slide", axis="1 0 0")
        bodies[f"link_{side}"] = body(
            bodies["drive"], f"link_{side}", pos=values((0, sign * 0.014, 0))
        )
        ET.SubElement(
            bodies[f"link_{side}"], "joint", name=f"link_joint_{side}", type="hinge", axis="0 0 1"
        )
        ET.SubElement(
            bodies[f"link_{side}"],
            "site",
            name=f"endpoint_{side}",
            pos=values((sign * x0, -sign * 0.014, 0.028)),
            size=".0003",
            rgba="0 0 0 0",
        )
        ET.SubElement(
            bodies[side],
            "site",
            name=f"carriage_pin_{side}",
            pos=values((sign * x0, 0, 0.028)),
            size=".0003",
            rgba="0 0 0 0",
        )
        ET.SubElement(
            bodies[side],
            "site",
            name=f"pad_inner_{side}",
            pos=values((sign * (x0 - 0.0115), 0, 0.0497)),
            size=".0003",
            rgba="0 0 0 0",
        )
        ET.SubElement(
            equality,
            "connect",
            name=f"closure_{side}",
            site1=f"endpoint_{side}",
            site2=f"carriage_pin_{side}",
        )

    inventory = {}

    def mesh(name, shape, parent, offset=(0, 0, 0)):
        vertices, faces = shape.tessellate(0.12, 0.15)
        xyz = np.array([v.toTuple() for v in vertices]) / 1000 - offset
        if not len(faces):
            raise ValueError(f"non-renderable occurrence: {name}")
        path = meshdir / f"{name}.obj"
        path.write_text(
            "\n".join(
                [
                    *("v " + values(v) for v in xyz),
                    *("f " + " ".join(str(i + 1) for i in f) for f in faces),
                ]
            )
            + "\n"
        )
        ET.SubElement(asset, "mesh", name=name, file=path.name)
        ET.SubElement(parent, "geom", name=name, type="mesh", mesh=name, rgba=values(color(name)))
        inventory[name] = {"vertices": len(vertices), "triangles": len(faces)}

    for name in pg3.neutral:
        # Use the installed mid-pose material, including local part replacements.
        shape = (
            whole[f"PG3_{name}"].translate((0.2, -234.9, -164.6)).rotate((0, 0, 0), (0, 1, 0), -90)
        )
        group = group_for(name)
        if group.startswith("pin_"):
            group = "drive"  # Axisymmetric washer: seam rotation does not alter the geometry.
        offset = (
            (0, (0.014 if group == "link_R" else -0.014), 0)
            if group.startswith("link_")
            else (0, 0, 0)
        )
        mesh(f"PG3_{name}", shape, bodies[group], np.array(offset))
    for name, shape in whole.items():
        if not name.startswith("PG3_"):
            if name.startswith(("ARM_M06_", "ARM_P06_")):
                mesh(name, shape, roll, roll_origin)
            else:
                mesh(name, shape, world)

    target = np.array([0.025, 0.2349, 0.1646])
    # Keep the sensor outside the reference housing; real lens pose remains unmeasured.
    normal = np.array([0, math.sqrt(3) / 2, -0.5])
    camera_shape = whole["CAMERA_REFERENCE_UNCONFIRMED"]
    verts = np.array([v.toTuple() for v in camera_shape.Vertices()]) / 1000
    origin = np.array(CAMERA_ORIGIN) / 1000
    optical = origin + normal * (np.max((verts - origin) @ normal) + 0.002)
    if optical_proxy_mm is not None:
        if optical_normal is None:
            raise ValueError("explicit optical origin requires an explicit direction")
        optical = np.asarray(optical_proxy_mm, dtype=float) / 1000
        normal = np.asarray(optical_normal, dtype=float)
        if not np.isclose(np.linalg.norm(normal), 1):
            raise ValueError("optical direction must be a unit vector")
    sensor = ET.SubElement(world, "body", name="P05_camera_fixed", pos=values(optical))
    # Camera looks along local -Z. Optical frame x=world X, y=z cross x.
    z = -normal
    x = np.array([1.0, 0, 0])
    ET.SubElement(
        sensor, "camera", name="camera_proxy", xyaxes=values(np.r_[x, np.cross(z, x)]), fovy="50"
    )
    for name, pos in (("whole_arm", [0.50, 0.60, 0.42]), ("terminal", [0.36, 0.41, 0.33])):
        focus = np.array([0, 0.14, 0.12]) if name == "whole_arm" else target
        z = np.array(pos) - focus
        z /= np.linalg.norm(z)
        x = np.cross([0, 0, 1], z)
        x /= np.linalg.norm(x)
        ET.SubElement(
            world,
            "camera",
            name=name,
            pos=values(pos),
            xyaxes=values(np.r_[x, np.cross(z, x)]),
            fovy="45",
        )
    path = out / "scene.xml"
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="unicode")
    (out / "assumptions.json").write_text(
        json.dumps(
            {
                "inventory": inventory,
                "simulation": "analytic_joint_trajectory_plus_mj_forward_not_force_dynamics",
                "collision": "disabled_visual_meshes_BRep_evidence_is_separate",
                "inertias": "positive_dummy_inertias_not_identified",
                "gravity": 0,
                "camera_parent": "fixed_P05_R3_saved_pose",
                "camera_fovy_deg_assumed": 50,
                "camera_origin_m_assumed": optical.tolist(),
                "camera_optical_pose_verified": False,
                "full_arm_joint_sweep": "not_tested",
                "wrist_roll": "J5_Y_axis_diagnostic_plus_minus30_not_admitted_physical_range",
                "roll_visual_limitation": "M05 supplier horn not split; original motor stays static",
                "powered_operation_approved": False,
            },
            indent=2,
        )
        + "\n"
    )
    return path


def set_pose(model, data, angle, wrist_roll_degrees=0):
    x = position_mm(angle)
    t = math.radians(angle)
    delta = t - math.pi / 2
    phi = math.atan2(-14 * math.sin(t), x - 14 * math.cos(t))
    phi0 = math.atan2(-14, position_mm(90))
    q = {
        "wrist_roll": math.radians(wrist_roll_degrees),
        "crank": delta,
        "slide_R": (x - position_mm(90)) / 1000,
        "slide_L": -(x - position_mm(90)) / 1000,
        "link_joint_R": phi - phi0 - delta,
        "link_joint_L": phi - phi0 - delta,
    }
    for name, val in q.items():
        data.qpos[model.joint(name).qposadr[0]] = val
    mujoco.mj_forward(model, data)
    residual = (
        max(
            np.linalg.norm(data.site(f"endpoint_{s}").xpos - data.site(f"carriage_pin_{s}").xpos)
            for s in ("R", "L")
        )
        * 1000
    )
    gap = np.linalg.norm(data.site("pad_inner_R").xpos - data.site("pad_inner_L").xpos) * 1000
    return {
        "angle_degrees": angle,
        "closure_residual_mm": float(residual),
        "measured_pad_gap_mm": float(gap),
        "analytic_pad_gap_mm": opening_mm(angle),
    }


def segmentation_bounds(segmentation, geom_id):
    y, x = np.nonzero(
        (segmentation[:, :, 0] == geom_id) & (segmentation[:, :, 1] == mujoco.mjtObj.mjOBJ_GEOM)
    )
    if not len(x):
        return None
    return [int(x.min()), int(y.min()), int(x.max()), int(y.max())]


def simulate(path, *, virtual_candidates=True):
    path = Path(path)
    model = mujoco.MjModel.from_xml_path(str(path.resolve()))
    # Integer segmentation IDs must not be blended by multisample antialiasing.
    model.vis.quality.offsamples = 0
    data = mujoco.MjData(model)
    rows = [set_pose(model, data, float(a)) for a in np.linspace(25, 135, 221)]
    render = mujoco.Renderer(model, height=480, width=640)
    frames = []
    visibility = []
    viewpoint_candidates = []
    roll_samples = []
    try:
        for angle, label in ((25, "open"), (90, "mid"), (135, "closed")):
            set_pose(model, data, angle)
            for camera in ("whole_arm", "terminal", "camera_proxy"):
                render.update_scene(data, camera=camera)
                rgb = render.render().copy()
                Image.fromarray(rgb).save(path.parent / f"{camera}_{label}.png")
                if camera == "camera_proxy":
                    render.enable_segmentation_rendering()
                    render.update_scene(data, camera=camera)
                    seg = render.render().copy()
                    render.disable_segmentation_rendering()
                    pixels = {
                        s: int(
                            np.count_nonzero(
                                (seg[:, :, 0] == model.geom(f"PG3_pad_{s}").id)
                                & (seg[:, :, 1] == mujoco.mjtObj.mjOBJ_GEOM)
                            )
                        )
                        for s in ("R", "L")
                    }
                    visibility.append(
                        {
                            "pose": label,
                            "pad_pixels": pixels,
                            "rgb_std": float(rgb.std()),
                            "optics": "assumed_not_actual",
                            "image_size_px": [rgb.shape[1], rgb.shape[0]],
                            "pad_bounds_px": {
                                s: segmentation_bounds(seg, model.geom(f"PG3_pad_{s}").id)
                                for s in ("R", "L")
                            },
                        }
                    )
        for angle in np.r_[np.linspace(25, 135, 24), np.linspace(135, 25, 24)]:
            set_pose(model, data, float(angle))
            render.update_scene(data, camera="terminal")
            frames.append(Image.fromarray(render.render().copy()))
        frames[0].save(
            path.parent / "opening_cycle.gif",
            save_all=True,
            append_images=frames[1:],
            duration=80,
            loop=0,
        )
        for roll_degrees in (-30, 0, 30):
            result = set_pose(model, data, 90, roll_degrees)
            roll_samples.append(
                {
                    **result,
                    "wrist_roll_degrees": roll_degrees,
                    "camera_world_position_m": data.camera("camera_proxy").xpos.tolist(),
                    "camera_world_rotation": data.camera("camera_proxy").xmat.tolist(),
                    "pad_R_world_position_m": data.site("pad_inner_R").xpos.tolist(),
                }
            )
            for view in ("terminal", "camera_proxy"):
                render.update_scene(data, camera=view)
                Image.fromarray(render.render().copy()).save(
                    path.parent / f"{view}_roll{roll_degrees}.png"
                )
        camera = model.camera("camera_proxy")
        camera_id = camera.id
        parent_position = model.body("P05_camera_fixed").pos.copy()
        target = np.array([0.0495, 0.2349, 0.1646])
        for x in (0.05, 0.08, 0.11, 0.14) if virtual_candidates else ():
            position = np.array([x, 0.139, 0.228])
            z = position - target
            z /= np.linalg.norm(z)
            right = np.cross([0, 0, 1], z)
            right /= np.linalg.norm(right)
            rotation = np.column_stack((right, np.cross(z, right), z))
            quat = np.empty(4)
            mujoco.mju_mat2Quat(quat, rotation.ravel())
            model.cam_pos[camera_id] = position - parent_position
            model.cam_quat[camera_id] = quat
            candidate = {
                "world_position_mm": (position * 1000).tolist(),
                "target_mm": (target * 1000).tolist(),
                "poses": {},
                "mechanical_mount_designed": False,
                "scope": "virtual_sensor_only_existing_camera_hardware_not_relocated",
            }
            for angle, label in ((25, "open"), (90, "mid"), (135, "closed")):
                set_pose(model, data, angle)
                render.update_scene(data, camera="camera_proxy")
                Image.fromarray(render.render().copy()).save(
                    path.parent / f"virtual_camera_x{int(x * 1000)}_{label}.png"
                )
                render.enable_segmentation_rendering()
                render.update_scene(data, camera="camera_proxy")
                seg = render.render().copy()
                render.disable_segmentation_rendering()
                candidate["poses"][label] = {
                    s: int(
                        np.count_nonzero(
                            (seg[:, :, 0] == model.geom(f"PG3_pad_{s}").id)
                            & (seg[:, :, 1] == mujoco.mjtObj.mjOBJ_GEOM)
                        )
                    )
                    for s in ("R", "L")
                }
            viewpoint_candidates.append(candidate)
    finally:
        render.close()
    report = {
        "mode": "kinematic_mj_forward_not_mj_step_or_physical_contact",
        "dof_count": model.nv,
        "closed_loop_constraint_count": model.neq,
        "samples": rows,
        "visibility": visibility,
        "virtual_viewpoint_candidates": viewpoint_candidates,
        "wrist_roll_samples": roll_samples,
        "max_closure_residual_mm": max(r["closure_residual_mm"] for r in rows),
        "max_pad_gap_error_mm": max(
            abs(r["measured_pad_gap_mm"] - r["analytic_pad_gap_mm"]) for r in rows
        ),
        "frame_difference_mean": float(
            np.abs(np.asarray(frames[0], dtype=float) - np.asarray(frames[23], dtype=float)).mean()
        ),
        "force_and_strength_validated": False,
        "camera_calibrated": False,
    }
    (path.parent / "simulation.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
