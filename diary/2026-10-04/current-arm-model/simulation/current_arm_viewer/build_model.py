"""Build unchanged candidate geometry for a kinematic MuJoCo state viewer.

No serial access, collision certification, Boolean healing or physical dynamics.
All selected R3 occurrences, including sheet faces, are tessellated for display.
"""

import hashlib
import importlib.util
import json
import math
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import cadquery as cq
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/current-arm-mujoco-20261003"
MESH_DEFLECTION_MM = 0.12  # Display approximation, never a collision acceptance tolerance.
sys.path.insert(0, str(ROOT))
from gripper_design import camera_overhead_d405_r5 as camera
from scripts.assembly_io import read_step

C7_FILE = ROOT / "references/pg3-c9/PG3_C92_J28/reference/C7/source/design.py"
spec = importlib.util.spec_from_file_location("viewer_c7_donor", C7_FILE)
c7 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = c7
spec.loader.exec_module(c7)


def nums(a):
    return " ".join(f"{float(x):.12g}" for x in np.asarray(a).reshape(-1))


def mesh_export(filename, shapes, origin_mm):
    vertices, faces = [], []
    counts = []
    for name, shape in shapes:
        v, f = shape.tessellate(MESH_DEFLECTION_MM, 0.12)
        offset = len(vertices)
        vertices.extend((np.array(p.toTuple()) - origin_mm) / 1000 for p in v)
        faces.extend(tuple(i + offset for i in tri) for tri in f)
        counts.append(
            {"name": name, "vertices": len(v), "triangles": len(f), "solids": len(shape.Solids())}
        )
    if not faces or len(vertices) < 4:
        raise ValueError(f"Cannot represent mesh {filename}")
    with filename.open("w") as out:
        for p in vertices:
            out.write("v " + nums(p) + "\n")
        for tri in faces:
            out.write("f " + " ".join(str(i + 1) for i in tri) + "\n")
    return counts


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "meshes").mkdir(exist_ok=True)
    source = ROOT / "references/arm-r3/arm_XL430_R3.step"
    _, _, rows = read_step(source)
    meta = {
        p["name"]: p for p in json.loads((ROOT / "references/arm-r3/manifest.json").read_text())
    }
    joints = json.loads((ROOT / "references/arm-r3/joints.json").read_text())[:4]
    groups = defaultdict(list)
    for row in rows:
        unit = meta[row.name]["physical_unit"]
        if unit in {"M06", "P06_fixed_gripper_XL430", "P07_moving_gripper_XL430"}:
            continue
        groups[unit].append((row.name, row.world))
    root = ET.Element("mujoco", model="R3_C7_D405_candidate_state_viewer")
    ET.SubElement(root, "compiler", angle="radian", meshdir="meshes", autolimits="true")
    ET.SubElement(root, "option", gravity="0 0 0", timestep="0.01")
    vis = ET.SubElement(root, "visual")
    ET.SubElement(vis, "global", offwidth="1100", offheight="800")
    ET.SubElement(vis, "quality", shadowsize="2048", offsamples="4")
    ET.SubElement(
        vis, "headlight", ambient="0.35 0.35 0.35", diffuse="0.6 0.6 0.6", specular="0.12 0.12 0.12"
    )
    asset = ET.SubElement(root, "asset")
    ET.SubElement(
        asset,
        "texture",
        type="skybox",
        builtin="gradient",
        rgb1="0.9 0.94 0.96",
        rgb2="0.98 0.99 1",
        width="256",
        height="1536",
    )
    world = ET.SubElement(root, "worldbody")
    ET.SubElement(world, "light", pos="0.3 0.1 0.7", dir="-0.2 0 -1", diffuse="0.35 0.35 0.35")
    ET.SubElement(world, "light", pos="-0.4 0.3 0.4", dir="0.5 -0.2 -1", diffuse="0.25 0.25 0.25")
    ET.SubElement(
        world,
        "geom",
        name="table_display",
        type="plane",
        size="1 1 0.02",
        rgba="0.78 0.82 0.84 1",
        contype="0",
        conaffinity="0",
    )
    parents = [world]
    origins = [np.zeros(3)]
    for j, joint in enumerate(joints):
        origin = np.array(joint["centre_mm"])
        body = ET.SubElement(
            parents[-1], "body", name=f"arm_link_{j + 1}", pos=nums((origin - origins[-1]) / 1000)
        )
        # Placeholder inertial is required by the kinematic joint compiler;
        # no dynamics steps are performed and these are not measured values.
        ET.SubElement(body, "inertial", pos="0 0 0", mass="0.1", diaginertia="0.001 0.001 0.001")
        ET.SubElement(
            body,
            "joint",
            name=f"cad_j{j + 1}",
            type="hinge",
            axis=nums(joint["axis"]),
            limited="false",
        )
        parents.append(body)
        origins.append(origin)
    inventory = []

    def add_mesh(name, entries, body, origin, color, display_group=0):
        counts = mesh_export(OUT / "meshes" / f"{name}.obj", entries, np.array(origin))
        ET.SubElement(asset, "mesh", name=name, file=f"{name}.obj", inertia="shell")
        ET.SubElement(
            body,
            "geom",
            name=name,
            type="mesh",
            mesh=name,
            rgba=nums(color),
            group=str(display_group),
            contype="0",
            conaffinity="0",
            density="0",
        )
        inventory.append({"mesh": name, "entries": counts, "display_group": display_group})

    for unit, entries in groups.items():
        level = meta[entries[0][0]]["level"]
        color = (0.68, 0.71, 0.73, 1) if unit.startswith("M") else (0.92, 0.93, 0.90, 1)
        add_mesh(unit, entries, parents[level], origins[level], color)

    wrist = parents[4]
    grip_origin = np.array([-0.2, 164.9, 164.6])
    grip_base = ET.SubElement(
        wrist,
        "body",
        name="c7_fixed",
        pos=nums((grip_origin - origins[4]) / 1000),
        quat=nums([math.sqrt(0.5), -math.sqrt(0.5), 0, 0]),
    )
    c7_parts = c7.parts()
    grip_groups = defaultdict(list)
    for part in c7.assembled(90, d=c7_parts, motor=False):
        grip_groups[part.group].append((part.name, part.shape, part.kind))
    for group, items in grip_groups.items():
        local_origin = np.zeros(3)
        if group == "fixed":
            body = grip_base
        elif group == "drive":
            body = ET.SubElement(grip_base, "body", name="c7_drive")
            ET.SubElement(
                body, "inertial", pos="0 0 0", mass="0.01", diaginertia="0.00001 0.00001 0.00001"
            )
            ET.SubElement(
                body, "joint", name="gripper_delta", type="hinge", axis="0 0 1", limited="false"
            )
        elif group in ("R", "L"):
            body = ET.SubElement(grip_base, "body", name="c7_jaw_" + group)
            ET.SubElement(
                body, "inertial", pos="0 0 0", mass="0.01", diaginertia="0.00001 0.00001 0.00001"
            )
            ET.SubElement(
                body, "joint", name="slider_" + group, type="slide", axis="1 0 0", limited="false"
            )
        elif group in ("link_R", "link_L"):
            local_origin = np.array([0, 14 if group.endswith("R") else -14, 0])
            body = ET.SubElement(world, "body", name="c7_" + group, mocap="true")
        else:
            raise ValueError(f"Unknown C7 group {group}")
        by_kind = defaultdict(list)
        for name, shape, kind in items:
            by_kind[kind].append((name, shape))
        for kind, entries in by_kind.items():
            color = {
                "printed": (0.9, 0.92, 0.87, 1),
                "fastener": (0.43, 0.48, 0.52, 1),
                "pad": (0.10, 0.12, 0.13, 1),
            }[kind]
            add_mesh("c7_" + group + "_" + kind, entries, body, local_origin, color, 1)

    for variant, cam_spec, display_group in [
        ("r5_65", camera.Spec(), 2),
        ("compact_75", replace(camera.Spec(), pitch_deg=75, glass_center=(-0.2, 185, 250)), 3),
    ]:
        for name, shape in camera.build(cam_spec).items():
            color = (0.23, 0.28, 0.32, 1) if "BODY" in name else (0.84, 0.89, 0.90, 1)
            if any(x in name for x in ("BOLT", "TAP", "NUT", "SCREW", "WASHER")):
                color = (0.43, 0.48, 0.52, 1)
            add_mesh(variant + "_" + name, [(name, shape)], wrist, origins[4], color, display_group)
    tree = ET.ElementTree(root)
    ET.indent(tree)
    tree.write(OUT / "scene.xml", encoding="unicode")
    report = {
        "source_cad_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "c7_source_sha256": hashlib.sha256(C7_FILE.read_bytes()).hexdigest(),
        "cadquery": cq.__version__,
        "selected_arm_occurrences": sum(len(x) for x in groups.values()),
        "sheet_arm_occurrences": sum(not s.Solids() for es in groups.values() for _, s in es),
        "inventory": inventory,
        "configuration": "R3 bare arm + C7 + selectable nominal R5_65/compact75",
        "physical_match": "inferred; camera angle unresolved; no actual joint readout",
        "qpos_semantics": "4 CAD relative arm angles + gripper construction delta(theta-90) + two passive sliders",
        "kinematic_view_only": True,
        "collision_certified": False,
        "dynamic_values_are_placeholders": True,
        "no_hardware_access": True,
        "motor_internal_reference_parts_render_rigidly": True,
        "real_cables_absent": True,
        "mesh_tessellation_mm": MESH_DEFLECTION_MM,
    }
    (OUT / "model-provenance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "inventory"}, indent=2))


if __name__ == "__main__":
    build()
