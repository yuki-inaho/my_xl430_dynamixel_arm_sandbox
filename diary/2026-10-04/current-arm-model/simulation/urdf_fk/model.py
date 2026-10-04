"""Export the selected serial kinematic tree with unchanged meshes to URDF.

Supports this explicit, unrotated four-hinge MJCF tree. Rejects unsupported
frames rather than approximating them. All inertias remain display placeholders.
"""

import hashlib
import json
import math
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "specs/urdf_fk_r3.json"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def numeric_vector(value, size):
    try:
        if len(value) != size or any(
            isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, float, np.number))
            for v in value
        ):
            raise ValueError("Finite numeric vector required")
        result = np.asarray(value, dtype=float)
    except (TypeError, OverflowError) as exc:
        raise ValueError("Finite numeric vector required") from exc
    if result.shape != (size,) or not np.isfinite(result).all():
        raise ValueError("Finite numeric vector required")
    return result.copy()


def numbers(value):
    return " ".join(f"{float(v):.15g}" for v in np.asarray(value).reshape(-1))


def load_config(path=SPEC):
    cfg = json.loads(Path(path).read_text())
    if cfg.get("simulation_only") is not True or cfg.get("hardware_targets") is not None:
        raise ValueError("Offline simulation specification required")
    bounds = np.array([numeric_vector(row, 2) for row in cfg["demo_ranges_deg"]])
    if bounds.shape != (4, 2) or not np.all(bounds[:, 0] < bounds[:, 1]):
        raise ValueError("Four ordered ranges required")
    seed = numeric_vector(cfg["seed_deg"], 4)
    if np.any(seed < bounds[:, 0]) or np.any(seed > bounds[:, 1]):
        raise ValueError("Seed outside demonstration ranges")
    for pose in cfg["poses"]:
        angles = numeric_vector(pose["angles_deg"], 4)
        if np.any(angles < bounds[:, 0]) or np.any(angles > bounds[:, 1]):
            raise ValueError("Example pose outside display ranges")
    return cfg


def checked_inputs(cfg, root):
    for path_key, hash_key in (
        ("source_scene", "source_scene_sha256"),
        ("source_provenance", "source_provenance_sha256"),
        ("cad_file", "cad_sha256"),
        ("joints_file", "joints_sha256"),
    ):
        if sha256(root / cfg[path_key]) != cfg[hash_key]:
            raise ValueError(f"Source hash mismatch: {path_key}")
    provenance = json.loads((root / cfg["source_provenance"]).read_text())
    if provenance["source_cad_sha256"] != cfg["cad_sha256"]:
        raise ValueError("CAD provenance hash mismatch")
    scene = ET.parse(root / cfg["source_scene"]).getroot()
    if scene.find("actuator") is not None:
        raise ValueError("Source must not contain actuators")
    world = scene.find("worldbody")
    chain = [world]
    joints = json.loads((root / cfg["joints_file"]).read_text())[:4]
    centers = [np.zeros(3)]
    for body_name, joint_name, record in zip(cfg["body_names"], cfg["joint_names"], joints):
        body = chain[-1].find(f"body[@name='{body_name}']")
        if body is None:
            raise ValueError("Source serial tree mismatch")
        orientation_fields = set(body.attrib) & {"euler", "axisangle", "xyaxes", "zaxis"}
        quat = np.fromstring(body.get("quat", "1 0 0 0"), sep=" ")
        if orientation_fields or not np.array_equal(quat, [1, 0, 0, 0]):
            raise ValueError("Rotated body frames are unsupported; explicit conversion required")
        joint = body.find("joint")
        if (
            len(body.findall("joint")) != 1
            or joint.get("name") != joint_name
            or joint.get("type") != "hinge"
            or joint.get("pos", "0 0 0") != "0 0 0"
        ):
            raise ValueError("Only one origin-centered hinge per selected body is supported")
        center = np.array(record["centre_mm"], dtype=float) / 1000
        if not np.allclose(
            np.fromstring(body.get("pos"), sep=" "), center - centers[-1], atol=1e-12, rtol=0
        ):
            raise ValueError("Source joint origin does not match saved CAD axes")
        if not np.array_equal(np.fromstring(joint.get("axis"), sep=" "), record["axis"]):
            raise ValueError("Source joint axis does not match saved CAD axes")
        chain.append(body)
        centers.append(center)
    return scene, chain, provenance


def add_inertial(link, source=None):
    """Positive compile-only placeholder, never an identified physical inertia."""
    element = ET.SubElement(link, "inertial")
    ET.SubElement(element, "origin", xyz="0 0 0", rpy="0 0 0")
    ET.SubElement(element, "mass", value="0.1" if source is None else source.get("mass"))
    diagonal = [0.001] * 3 if source is None else np.fromstring(source.get("diaginertia"), sep=" ")
    ET.SubElement(
        element,
        "inertia",
        ixx=str(diagonal[0]),
        iyy=str(diagonal[1]),
        izz=str(diagonal[2]),
        ixy="0",
        ixz="0",
        iyz="0",
    )


def write_xml(root, path):
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def export_model(cfg, output, root=ROOT):
    root, output = Path(root), Path(output)
    if output.exists():
        raise FileExistsError(f"Unique output required: {output}")
    if output.resolve().is_relative_to((root / "references").resolve()):
        raise ValueError("References are immutable")
    source, chain, provenance = checked_inputs(cfg, root)
    inventory = {
        item["mesh"]: item
        for item in provenance["inventory"]
    }
    # Fixed fixtures use their source parent frame, without adding a degree of freedom.
    fixed_visuals = cfg.get("fixed_visuals", [])
    extras = {
        (item["body"], name): item["group"]
        for item in fixed_visuals
        for name in item["mesh_names"]
    }
    if len(extras) != sum(len(item["mesh_names"]) for item in fixed_visuals):
        raise ValueError("Duplicate fixed visual selection")
    selected_extras = set()
    assets = {a.get("name"): a for a in source.findall("asset/mesh")}
    robot = ET.Element("robot", name=cfg.get("model_name", "current_R3_bare_kinematic"))
    robot.append(
        ET.Comment(
            "Simulation only. Demo joint limits and inertias are not hardware specifications."
        )
    )
    ext = ET.SubElement(robot, "mujoco")
    ET.SubElement(
        ext,
        "compiler",
        angle="radian",
        meshdir="meshes",
        strippath="true",
        discardvisual="false",
        fusestatic="false",
        inertiafromgeom="false",
    )
    ET.SubElement(ext, "option", gravity="0 0 0")
    links, meshes = [], []
    for level, body in enumerate(chain):
        name = "base_link" if level == 0 else body.get("name")
        link = ET.SubElement(robot, "link", name=name)
        add_inertial(link, body.find("inertial") if level else None)
        links.append(name)
        for geom in body.findall("geom"):
            if geom.get("type") != "mesh":
                continue
            mesh_name = geom.get("mesh")
            group = int(geom.get("group", "0"))
            extra_key = (body.get("name"), mesh_name)
            is_extra = extra_key in extras and group == extras[extra_key]
            if group != cfg["visual_group"] and not is_extra:
                continue
            if mesh_name not in inventory:
                raise ValueError(f"Unaccounted source visual: {mesh_name}")
            if inventory[mesh_name]["display_group"] != group:
                raise ValueError("Source visual group/provenance mismatch")
            if is_extra:
                selected_extras.add(extra_key)
            # This input has identity geom poses. Reject extensions until explicitly supported.
            if set(geom.attrib) & {"pos", "quat", "euler", "axisangle"}:
                raise ValueError("Non-identity geom frames require explicit conversion")
            asset = assets[mesh_name]
            if set(asset.attrib) & {"refpos", "refquat", "scale"}:
                raise ValueError("Non-identity source mesh transform requires explicit conversion")
            mesh_source = root / cfg["source_scene"]
            mesh_source = (
                mesh_source.parent / source.find("compiler").get("meshdir") / asset.get("file")
            )
            file = f"meshes/{mesh_name}.obj"
            visual = ET.SubElement(link, "visual", name=geom.get("name"))
            ET.SubElement(visual, "origin", xyz="0 0 0", rpy="0 0 0")
            ET.SubElement(ET.SubElement(visual, "geometry"), "mesh", filename=file, scale="1 1 1")
            material = ET.SubElement(visual, "material", name="material_" + mesh_name)
            ET.SubElement(material, "color", rgba=geom.get("rgba"))
            meshes.append(
                {
                    "name": geom.get("name"),
                    "file": file,
                    "source": str(mesh_source.relative_to(root)),
                    "source_sha256": sha256(mesh_source),
                    "sha256": sha256(mesh_source),
                    "link": name,
                    "occurrences": len(inventory[mesh_name]["entries"]),
                    "sheets": sum(e["solids"] == 0 for e in inventory[mesh_name]["entries"]),
                }
            )
    if selected_extras != set(extras):
        raise ValueError("Fixed visual missing or attached to a different source body")
    if len(meshes) != cfg["expected_meshes"] or len({e["name"] for e in meshes}) != len(meshes):
        raise ValueError("Source visual inventory mismatch")
    if sum(e["occurrences"] for e in meshes) != cfg["expected_occurrences"]:
        raise ValueError("Source occurrence inventory mismatch")
    for index, body in enumerate(chain[1:]):
        joint = ET.SubElement(robot, "joint", name=cfg["joint_names"][index], type="revolute")
        ET.SubElement(joint, "parent", link=links[index])
        ET.SubElement(joint, "child", link=links[index + 1])
        ET.SubElement(joint, "origin", xyz=body.get("pos"), rpy="0 0 0")
        ET.SubElement(joint, "axis", xyz=body.find("joint").get("axis"))
        lo, hi = np.radians(cfg["demo_ranges_deg"][index])
        ET.SubElement(joint, "limit", lower=str(lo), upper=str(hi), effort="1", velocity="0.1")
    ET.SubElement(robot, "link", name="tool_link")
    fixed = ET.SubElement(robot, "joint", name="tool_fixed", type="fixed")
    ET.SubElement(fixed, "parent", link=cfg["tool_body"])
    ET.SubElement(fixed, "child", link="tool_link")
    ET.SubElement(fixed, "origin", xyz=numbers(cfg["tool_offset_m"]), rpy="0 0 0")
    output.mkdir(parents=True)
    (output / "meshes").mkdir()
    for entry in meshes:
        shutil.copyfile(root / entry["source"], output / entry["file"])
    write_xml(robot, output / "robot.urdf")
    # The scene below is generated by compiling the actual exported URDF.
    imported = mujoco.MjModel.from_xml_path(str(output / "robot.urdf"))
    if imported.nq != 4 or imported.nu or imported.nmesh != len(meshes):
        raise ValueError("Compiled URDF inventory mismatch")
    mujoco.mj_saveLastXML(str(output / "imported.xml"), imported)
    scene = ET.parse(output / "imported.xml").getroot()
    scene.find("compiler").set("meshdir", "meshes")
    world = scene.find("worldbody")
    tool = world.find(".//body[@name='tool_link']")
    if tool is None:
        raise ValueError("URDF importer discarded tool frame")
    ET.SubElement(
        tool, "site", name="tool_tip", type="sphere", size="0.0035", rgba="0.1 0.75 0.45 1"
    )
    # The axis center can be inside the motor mesh; a separate line exposes its direction.
    ET.SubElement(
        tool,
        "site",
        name="tool_direction",
        type="capsule",
        fromto="0 0 0 0 0.045 0",
        size="0.0018",
        rgba="0.1 0.75 0.45 1",
    )
    ET.SubElement(
        tool,
        "site",
        name="tool_direction_end",
        type="sphere",
        pos="0 0.045 0",
        size="0.003",
        rgba="0.1 0.75 0.45 1",
    )
    ET.SubElement(
        world,
        "geom",
        name="table",
        type="plane",
        size="0.6 0.6 0.02",
        rgba="0.78 0.82 0.84 1",
        contype="0",
        conaffinity="0",
    )
    ET.SubElement(world, "light", pos="0.3 -0.2 0.6", dir="-0.2 0.4 -1", diffuse="0.6 0.6 0.6")
    visual = ET.SubElement(scene, "visual")
    ET.SubElement(visual, "global", offwidth="1200", offheight="900")
    ET.SubElement(visual, "headlight", ambient="0.45 0.45 0.45", diffuse="0.7 0.7 0.7")
    write_xml(scene, output / "scene.xml")
    manifest = {
        "configuration": cfg["configuration"],
        "source_cad_sha256": cfg["cad_sha256"],
        "source_scene_sha256": cfg["source_scene_sha256"],
        "mujoco_version": mujoco.__version__,
        "simulation_only": True,
        "hardware_targets": None,
        "collision_certified": False,
        "dynamic_values_are_placeholders": True,
        "effort_velocity_are_placeholders": True,
        "selected_occurrences": sum(e["occurrences"] for e in meshes),
        "sheet_occurrences": sum(e["sheets"] for e in meshes),
        "tool_definition": cfg["tool_definition"],
        "meshes": meshes,
        "fixed_visuals": fixed_visuals,
        "excluded": cfg.get("excluded", ["M06/P06/P07", "C7 mechanism", "D405 holders"]),
        "files": {
            p.name: sha256(p)
            for p in (output / "robot.urdf", output / "scene.xml", output / "imported.xml")
        },
        "spec": cfg,
    }
    (output / "model-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )
    return manifest


def load_scene(output):
    output = Path(output)
    manifest = json.loads((output / "model-manifest.json").read_text())
    for file, expected in manifest["files"].items():
        if sha256(output / file) != expected:
            raise ValueError(f"Artifact hash mismatch: {file}")
    for entry in manifest["meshes"]:
        if sha256(output / entry["file"]) != entry["sha256"]:
            raise ValueError("Mesh hash mismatch")
    model = mujoco.MjModel.from_xml_path(str(output / "scene.xml"))
    if model.nq != 4 or model.nv != 4 or model.nu:
        raise ValueError("Offline scalar four-axis model required")
    return model


def axis_rotation(axis, angle):
    axis = numeric_vector(axis, 3)
    norm = np.linalg.norm(axis)
    if norm == 0:
        raise ValueError("Zero joint axis")
    x, y, z = axis / norm
    skew = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    return np.eye(3) + math.sin(angle) * skew + (1 - math.cos(angle)) * (skew @ skew)


def urdf_fk(path, qpos):
    """Independent XML/NumPy FK, without MuJoCo transforms or Jacobians."""
    qpos = numeric_vector(qpos, 4)
    robot = ET.parse(path).getroot()
    transforms = {"base_link": np.eye(4)}
    index = 0
    for joint in robot.findall("joint"):
        parent, child = joint.find("parent").get("link"), joint.find("child").get("link")
        origin = joint.find("origin")
        local = np.eye(4)
        local[:3, 3] = np.fromstring(origin.get("xyz", "0 0 0"), sep=" ")
        r, p, y = np.fromstring(origin.get("rpy", "0 0 0"), sep=" ")
        local[:3, :3] = (
            axis_rotation([0, 0, 1], y) @ axis_rotation([0, 1, 0], p) @ axis_rotation([1, 0, 0], r)
        )
        if joint.get("type") == "revolute":
            local[:3, :3] = local[:3, :3] @ axis_rotation(
                np.fromstring(joint.find("axis").get("xyz"), sep=" "), qpos[index]
            )
            index += 1
        elif joint.get("type") != "fixed":
            raise ValueError("Unsupported independent FK joint type")
        transforms[child] = transforms[parent] @ local
    if index != 4:
        raise ValueError("Four revolute joints required")
    return transforms
