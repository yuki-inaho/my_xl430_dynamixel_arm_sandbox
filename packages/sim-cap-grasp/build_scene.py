"""Offline conversion of preserved R3/C7 evidence to contact dynamics.

No hardware imports. Original visual vertices are copied without alteration.
The C7 drive, two rods and two sliders form exact planar closed loops.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import xml.etree.ElementTree as ET
from itertools import combinations
from pathlib import Path

import coacd
import mujoco
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "source_inputs"
MODEL = ROOT / "model"
X90 = math.sqrt(0.024**2 - 0.014**2)
ARM_LIMITS = np.deg2rad([[-180, 180], [-40, 40], [-180, 180], [-138, 128]])


def nums(values):
    return " ".join(f"{float(v):.12g}" for v in np.asarray(values).reshape(-1))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def clip_convex(hull, axis, coordinate, keep_above):
    """Exact convex halfspace clip through source edges; no implicit mesh repair."""
    vertices = np.asarray(hull.vertices)
    signed = (vertices[:, axis] - coordinate) * (1 if keep_above else -1)
    keep = signed >= -1e-12
    if keep.all():
        return hull
    edges = hull.edges_unique
    crossing = edges[(signed[edges[:, 0]] * signed[edges[:, 1]]) < 0]
    points = [vertices[keep]]
    if len(crossing):
        a, b = crossing[:, 0], crossing[:, 1]
        u = signed[a] / (signed[a] - signed[b])
        points.append(vertices[a] + u[:, None] * (vertices[b] - vertices[a]))
    vertices = np.concatenate(points)
    if len(vertices) < 4 or np.ptp(vertices, axis=0).min() < 1e-8:
        return None
    return trimesh.convex.convex_hull(vertices)


def prepare_inputs():
    """Use only preserved, hash-verified inputs; never repair from another checkout."""
    hashes = json.loads((INPUT / "hashes.json").read_text())
    required = {"viewer/scene.xml"} | {
        f"scanfit/{part}_{side}.stl" for side in ("L", "R") for part in ("cot", "foam", "band")
    }
    if required - hashes.keys():
        raise ValueError("Incomplete input manifest")
    actual = {
        str(p.relative_to(INPUT))
        for p in INPUT.rglob("*")
        if p.is_file() and p.name != "hashes.json"
    }
    if actual != hashes.keys():
        raise ValueError("Missing or unmanifested source input")
    for name, digest in hashes.items():
        if sha(INPUT / name) != digest:
            raise ValueError(f"Source input hash mismatch: {name}")


def closure(theta):
    x = 0.014 * math.cos(theta) + math.sqrt(0.024**2 - (0.014 * math.sin(theta)) ** 2)
    phi = math.atan2(-0.014 * math.sin(theta), x - 0.014 * math.cos(theta))
    return x, phi - math.atan2(-0.014, X90)


def place_reset(model, data, arm, theta_deg=50):
    """Only caller-approved RESET or OFFLINE FK/IK; never call during dynamics."""
    for i, value in enumerate(arm, 1):
        data.qpos[model.joint(f"cad_j{i}").qposadr[0]] = value
    theta = math.radians(theta_deg)
    x, delta = closure(theta)
    data.qpos[model.joint("gripper_delta").qposadr[0]] = theta - math.pi / 2
    for side, sign in (("R", 1), ("L", -1)):
        data.qpos[model.joint(f"slider_{side}").qposadr[0]] = sign * (x - X90)
        data.qpos[model.joint(f"rod_{side}").qposadr[0]] = delta - (theta - math.pi / 2)
    mujoco.mj_forward(model, data)


def decompose_mesh(name, file, scale=1.0):
    """Cached deterministic CoACD parts; motor outer boxes conservatively bound cases."""
    cache = (
        MODEL / "decomposition" / (name + "_v2" if name in {"M05", "c7_fixed_printed"} else name)
    )
    report_file = cache / "report.json"
    if report_file.exists():
        parts = sorted(cache.glob("part_*.obj"))
        report = json.loads(report_file.read_text())
        if (
            report.get("source_sha256") != sha(file)
            or report.get("source_scale_to_m") != scale
            or not parts
            or report.get("parts") != len(parts)
        ):
            raise ValueError(f"Stale or incomplete decomposition cache: {name}")
        manifest = json.loads((MODEL / "cache_hashes.json").read_text())
        for part in parts:
            if manifest.get(str(part.relative_to(MODEL))) != sha(part):
                raise ValueError(f"Decomposition part hash mismatch: {part.name}")
        return parts, report
    cache.mkdir(parents=True, exist_ok=True)
    mesh = trimesh.load_mesh(file, process=True)
    mesh.apply_scale(scale)
    source_vertices = np.asarray(mesh.vertices)
    motor = name.startswith("M") and name[1:].isdigit()
    if name == "M05":
        # Source-vertex-verified case and two output-axis protrusions. The old
        # whole AABB filled empty corners and falsely hit the moving carriage.
        main = trimesh.creation.box(
            extents=[0.0285, 0.034, 0.0465],
            transform=trimesh.transformations.translation_matrix([0, 0.060, 0.012]),
        )
        hulls = [main]
        for lo, hi in ((0.040, 0.043), (0.077, 0.0809)):
            transform = trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0])
            transform[:3, 3] = [0, (lo + hi) / 2, 0]
            hulls.append(
                trimesh.creation.cylinder(
                    radius=0.01025 / math.cos(math.pi / 64),
                    height=hi - lo,
                    sections=64,
                    transform=transform,
                )
            )
        v = source_vertices
        inside = (
            (v[:, 1] >= 0.043 - 1e-9)
            & (v[:, 1] <= 0.077 + 1e-9)
            & (np.abs(v[:, 0]) <= 0.01425 + 1e-9)
            & (v[:, 2] >= -0.01125 - 1e-9)
            & (v[:, 2] <= 0.03525 + 1e-9)
        )
        protrusion = (
            (np.hypot(v[:, 0], v[:, 2]) <= 0.01025 + 1e-9)
            & (v[:, 1] >= 0.040 - 1e-9)
            & (v[:, 1] <= 0.0809 + 1e-9)
        )
        if not np.all(inside | protrusion):
            raise ValueError("Motor proxy does not cover all original vertices")
        method = "Source-verified maincase box + two Y-axis horn cylinders; all source vertices covered, cylinder64 conservatively circumscribed"
    elif name == "c7_fixed_printed":
        old = MODEL / "decomposition" / name
        oldfiles = sorted(old.glob("part_*.obj"))
        if oldfiles:
            oldreport = json.loads((old / "report.json").read_text())
            manifest = json.loads((MODEL / "cache_hashes.json").read_text())
            if (
                oldreport["source_sha256"] != sha(file)
                or oldreport["source_scale_to_m"] != scale
                or oldreport["parts"] != len(oldfiles)
                or any(manifest.get(str(p.relative_to(MODEL))) != sha(p) for p in oldfiles)
            ):
                raise ValueError("Stale original C7 decomposition")
            raw = [trimesh.load_mesh(p, process=True) for p in oldfiles]
        else:
            coacd.set_log_level("warn")
            result = coacd.run_coacd(
                coacd.Mesh(np.asarray(mesh.vertices), np.asarray(mesh.faces)),
                threshold=0.02,
                preprocess_resolution=35,
                resolution=1500,
                mcts_nodes=15,
                mcts_iterations=50,
                decimate=True,
                max_ch_vertex=48,
                seed=0,
            )
            raw = [trimesh.Trimesh(v, f, process=True) for v, f in result]
        hulls = []
        for h in raw:
            for axis, lo, hi in ((0, -0.046, 0.046), (1, -0.028, 0.028), (2, 0.017, 0.0241)):
                h = clip_convex(h, axis, lo, True)
                if h is None:
                    break
                h = clip_convex(h, axis, hi, False)
                if h is None:
                    break
            if h is not None and len(h.vertices) >= 4 and np.ptp(h.vertices, axis=0).min() > 1e-8:
                hulls.append(h.convex_hull)
        for sign in (-1, 1):
            hulls.append(
                trimesh.creation.box(
                    extents=[0.092, 0.009, 0.003],
                    transform=trimesh.transformations.translation_matrix(
                        [0, sign * 0.0235, 0.0256]
                    ),
                )
            )
        method = "Base CoACD clipped to exact CAD source slabs; two independent cap-rail boxes at |Y|19..28mm,Z24.1..27.1mm preserve measured 0.5mm rod gap. Screw bores occupied."
    elif motor:
        hulls = [
            trimesh.creation.box(
                extents=mesh.extents,
                transform=trimesh.transformations.translation_matrix(mesh.bounds.mean(axis=0)),
            )
        ]
        method = "conservative case bounding box; minor horn/holes occupied"
    elif "fastener" in name:
        hulls = [
            part.convex_hull
            for part in mesh.split(only_watertight=False, repair=False)
            if len(part.vertices) >= 4 and np.ptp(part.vertices, axis=0).min() > 1e-8
        ]
        method = "separate connected fasteners; convex hull per screw/washer, no inter-part bridge"
    elif name.startswith("cot_") or any(
        word in name for word in ("WASHER", "TAP", "BOLT", "NUT", "SCREW", "USB", "D405_BODY")
    ):
        hulls = [mesh.convex_hull]
        method = "convex outer envelope; small fastener bores/internal cavities not represented"
    else:
        print(f"Decomposing {name}: {len(mesh.faces)} faces", flush=True)
        coacd.set_log_level("warn")
        result = coacd.run_coacd(
            coacd.Mesh(np.asarray(mesh.vertices), np.asarray(mesh.faces)),
            threshold=0.02,
            preprocess_mode="auto",
            preprocess_resolution=35,
            resolution=1500,
            mcts_nodes=15,
            mcts_iterations=50,
            mcts_max_depth=3,
            merge=True,
            decimate=True,
            max_ch_vertex=48,
            seed=0,
        )
        hulls = [trimesh.Trimesh(v, f, process=True) for v, f in result]
        method = "CoACD concavity0.02 normalized; seed0; max48vertices/part"
    files = []
    for i, hull in enumerate(hulls):
        dest = cache / f"part_{i:03d}.obj"
        hull.export(dest)
        files.append(dest)
    # Directed vertex-to-source vertex is a reproducible conservative sample
    # diagnostic, not a certified Hausdorff bound. Source triangles remain supplied.
    from scipy.spatial import cKDTree

    d = cKDTree(source_vertices).query(np.concatenate([h.vertices for h in hulls]))[0]
    report = {
        "source_sha256": sha(file),
        "source_scale_to_m": scale,
        "method": method,
        "parts": len(hulls),
        "source_bounds_m": mesh.bounds.tolist(),
        "proxy_directory": str(cache.relative_to(MODEL)),
        "source_watertight": bool(mesh.is_watertight),
        "proxy_vertex_to_source_vertex_max_m": float(np.max(d)),
        "proxy_vertex_to_source_vertex_p95_m": float(np.quantile(d, 0.95)),
        "error_limitations": "Vertex sampling diagnostic, not certified surface error. Source visual/contact proxy comparison images supplied; mounting bores/minor features may be filled, large gaps decomposed.",
    }
    save_json(report_file, report)
    manifest_file = MODEL / "cache_hashes.json"
    manifest = json.loads(manifest_file.read_text()) if manifest_file.exists() else {}
    manifest.update({str(p.relative_to(MODEL)): sha(p) for p in files})
    save_json(manifest_file, manifest)
    return files, report


def build():
    prepare_inputs()
    MODEL.mkdir(exist_ok=True)
    (MODEL / "meshes").mkdir(exist_ok=True)
    assumptions = json.loads((ROOT / "assumptions.json").read_text())
    src = INPUT / "viewer"
    tree = ET.parse(src / "scene.xml")
    root = tree.getroot()
    root.set("model", "R3_C7_scanfit_D405_nominal_contact_dynamics")
    root.find("option").attrib.update(
        gravity="0 0 -9.81",
        timestep="0.001",
        integrator="implicitfast",
        solver="Newton",
        iterations="100",
        tolerance="1e-10",
        cone="elliptic",
        impratio="10",
    )
    ET.SubElement(root.find("option"), "flag", autoreset="disable", filterparent="disable")
    root.find("visual/global").attrib.update(offwidth="960", offheight="720")
    world = root.find("worldbody")
    asset = root.find("asset")
    for child in list(asset):
        if child.tag == "mesh" and child.get("name", "").startswith("compact_75"):
            asset.remove(child)
    for parent in root.iter():
        for child in list(parent):
            if child.tag == "geom" and child.get("name", "").startswith("compact_75"):
                parent.remove(child)
    for mesh in asset.findall("mesh"):
        shutil.copyfile(src / "meshes" / mesh.get("file"), MODEL / "meshes" / mesh.get("file"))
    world.remove(world.find("geom[@name='table_display']"))
    ET.SubElement(
        world,
        "geom",
        name="table",
        type="plane",
        size="0.65 0.65 0.01",
        rgba="0.28 0.34 0.38 1",
        contype="0",
        conaffinity="0",
    )
    box = assumptions["nominal"]["box"]
    ET.SubElement(
        world,
        "geom",
        name="box",
        type="box",
        pos=nums(box["center_m"]),
        size=nums(box["halfsize_m"]),
        rgba="0.14 0.15 0.18 1",
        contype="0",
        conaffinity="0",
    )
    bodies = {b.get("name"): b for b in world.iter("body")}
    # Nominal lumped inertias use bounded positive mass and geometric extents;
    # no zero/placeholder inertia is inherited from the display model.
    lumped = {
        "arm_link_1": (0.080, [0, -0.01, 0.035], [0.035, 0.045, 0.030]),
        "arm_link_2": (0.090, [0, 0.009, 0.072], [0.044, 0.045, 0.115]),
        "arm_link_3": (0.085, [0, 0.057, 0], [0.046, 0.12, 0.032]),
        "arm_link_4": (0.16, [0, 0.065, 0.054], [0.075, 0.12, 0.14]),
        "c7_fixed": (0.018, [0, 0, 0.021], [0.092, 0.056, 0.011]),
        "c7_drive": (0.009, [0, 0, 0.024], [0.037, 0.020, 0.011]),
        "c7_jaw_R": (0.025, [0.022, 0, 0.047], [0.028, 0.044, 0.072]),
        "c7_jaw_L": (0.025, [-0.025, 0, 0.047], [0.028, 0.044, 0.072]),
    }
    for name, (mass, center, extents) in lumped.items():
        b = bodies[name]
        old = b.find("inertial")
        if old is not None:
            b.remove(old)
        x, y, z = extents
        inertia = mass / 12 * np.array([y * y + z * z, x * x + z * z, x * x + y * y])
        ET.SubElement(b, "inertial", mass=str(mass), pos=nums(center), diaginertia=nums(inertia))
    for i in range(1, 5):
        j = bodies[f"arm_link_{i}"].find("joint")
        j.attrib.update(
            limited="true", range=nums(ARM_LIMITS[i - 1]), damping="0.01", armature="0.0001"
        )
    drive = bodies["c7_drive"]
    drive.find("joint").attrib.update(
        limited="true", range=nums(np.deg2rad([-65, 45])), damping="0.001", armature="0.00001"
    )
    equalities = ET.SubElement(root, "equality")
    for side, sign in (("R", 1), ("L", -1)):
        rod = bodies[f"c7_link_{side}"]
        world.remove(rod)
        rod.attrib.pop("mocap")
        rod.set("pos", nums([0, sign * 0.014, 0]))
        ET.SubElement(
            rod, "joint", name=f"rod_{side}", type="hinge", axis="0 0 1", damping="0.00001"
        )
        ET.SubElement(
            rod,
            "inertial",
            mass="0.002",
            pos=nums([sign * X90 / 2, -sign * 0.007, 0.028]),
            diaginertia="1.1e-7 1.1e-7 2e-7",
        )
        drive.append(rod)
        ET.SubElement(
            equalities,
            "connect",
            name=f"closure_{side}",
            body1=f"c7_link_{side}",
            body2=f"c7_jaw_{side}",
            anchor=nums([sign * X90, -sign * 0.014, 0.0279]),
            solref="0.003 1",
            solimp="0.99 0.9999 0.001",
        )
        bodies[f"c7_jaw_{side}"].find("joint").attrib.update(
            limited="true", range="-0.019 0.019", damping="0.015"
        )
    # Grip datum anchored to unchanged reference frame, not the object.
    ET.SubElement(
        bodies["c7_fixed"],
        "site",
        name="grip",
        pos="-0.0035 -0.002 0.080",
        size="0.001",
        rgba="1 0.2 0.1 1",
        group="4",
    )
    # Camera optical center from holder candidate; conventional OpenGL -Z viewing.
    ET.SubElement(
        bodies["arm_link_4"],
        "camera",
        name="wrist_d405",
        pos="0 0.0921 0.0924",
        xyaxes="1 0 0 0 0.906307787 0.422618262",
        fovy="57.8",
    )
    ET.SubElement(
        world,
        "camera",
        name="external",
        pos="0.38 0.48 0.31",
        xyaxes="-0.756 0.655 0 -0.314 -0.363 0.878",
        fovy="48",
    )
    cap = assumptions["nominal"]["cap"]
    capbody = ET.SubElement(world, "body", name="cap", pos=nums(cap["initial_center_m"]))
    ET.SubElement(capbody, "freejoint", name="cap_free")
    ET.SubElement(
        capbody,
        "geom",
        name="cap_geom",
        type="cylinder",
        size=nums([cap["radius_m"], cap["height_m"] / 2]),
        mass=str(cap["mass_kg"]),
        rgba="0.96 0.98 1 1",
        contype="0",
        conaffinity="0",
        condim="4",
    )
    # Label dot makes orientation visible while contributing no support/contact.
    ET.SubElement(
        capbody,
        "geom",
        name="cap_mark",
        type="sphere",
        pos="0.006 0 0.0076",
        size="0.0015",
        mass="0",
        contype="0",
        conaffinity="0",
        rgba="0.1 0.3 0.6 1",
    )
    actuators = ET.SubElement(root, "actuator")
    for i in range(1, 5):
        ET.SubElement(
            actuators,
            "position",
            name=f"arm_motor_{i}",
            joint=f"cad_j{i}",
            kp="60",
            kv="2",
            gear="1",
            ctrllimited="true",
            ctrlrange=nums(ARM_LIMITS[i - 1]),
            forcelimited="true",
            forcerange="-1 1",
        )
    ET.SubElement(
        actuators,
        "position",
        name="jaw_motor",
        joint="gripper_delta",
        gear="1",
        kp="0.12",
        kv="0.003",
        ctrllimited="true",
        ctrlrange=nums(np.deg2rad([-65, 45])),
        forcelimited="true",
        forcerange="-0.08 0.08",
    )
    # Source visual geometry is kept exactly. Physical proxies are hidden group3.
    proxy_groups = []
    reports = {}
    for parent in list(world.iter()):
        for g in list(parent.findall("geom")):
            name = g.get("name", "")
            if g.get("type") != "mesh":
                continue
            body_name = parent.get("name", "world")
            category = (
                "holder"
                if name.startswith("r5_")
                else "mechanism"
                if name.startswith("c7")
                else "arm"
            )
            # The inherited thin C7 display pads are supplanted by observed six add-ons.
            if name in ("c7_L_pad", "c7_R_pad"):
                parent.remove(g)
                continue
            g.set("group", "0")
            files, reports[name] = decompose_mesh(name, src / "meshes" / f"{name}.obj")
            for index, f in enumerate(files):
                proxy_name = f"col_{name}_{index}"
                ET.SubElement(
                    asset,
                    "mesh",
                    name=proxy_name,
                    file=str(f.relative_to(MODEL / "meshes"))
                    if f.is_relative_to(MODEL / "meshes")
                    else "../" + str(f.relative_to(MODEL)),
                    inertia="shell",
                )
                ET.SubElement(
                    parent,
                    "geom",
                    name=proxy_name,
                    type="mesh",
                    mesh=proxy_name,
                    density="0",
                    contype="0",
                    conaffinity="0",
                    group="3",
                    rgba="0.95 0.3 0.1 0.35",
                )
                proxy_groups.append(
                    {"name": proxy_name, "body": body_name, "category": category, "source": name}
                )
    for side in ("L", "R"):
        b = bodies[f"c7_jaw_{side}"]
        for part in ("cot", "foam", "band"):
            name = f"{part}_{side}"
            file = INPUT / "scanfit" / f"{name}.stl"
            shutil.copyfile(file, MODEL / "meshes" / file.name)
            ET.SubElement(
                asset, "mesh", name=name, file=file.name, scale="0.001 0.001 0.001", inertia="shell"
            )
            color = {
                "cot": "0.26 0.65 0.92 1",
                "foam": "0.10 0.12 0.13 1",
                "band": "0.95 0.42 0.08 1",
            }[part]
            ET.SubElement(
                b,
                "geom",
                name=name,
                type="mesh",
                mesh=name,
                density="0",
                contype="0",
                conaffinity="0",
                rgba=color,
            )
            files, reports[name] = decompose_mesh(name, file, 0.001)
            for index, f in enumerate(files):
                proxy_name = f"col_{name}_{index}"
                ET.SubElement(
                    asset,
                    "mesh",
                    name=proxy_name,
                    file="../" + str(f.relative_to(MODEL)),
                    inertia="shell",
                )
                ET.SubElement(
                    b,
                    "geom",
                    name=proxy_name,
                    type="mesh",
                    mesh=proxy_name,
                    density="0",
                    contype="0",
                    conaffinity="0",
                    group="3",
                    rgba="0.3 0.8 0.3 0.4",
                )
                proxy_groups.append(
                    {
                        "name": proxy_name,
                        "body": f"c7_jaw_{side}",
                        "category": "softtip" if part == "cot" else "addon",
                        "side": side,
                        "source": name,
                    }
                )
    env = [
        {"name": "cap_geom", "body": "cap", "category": "cap"},
        {"name": "box", "body": "world", "category": "support"},
        {"name": "table", "body": "world", "category": "support"},
    ]
    geoms = proxy_groups + env
    contacts = ET.SubElement(root, "contact")
    # Complete collision policy is expressed as a small group matrix. Bitmasks
    # permit MuJoCo BVH broadphase, instead of an O(n^2) explicit-pair list.
    groups = {}
    for geom in geoms:
        key = (geom["body"], geom["category"])
        if key not in groups:
            groups[key] = {**geom, "id": len(groups), "mask": 0}
        geom["group_id"] = groups[key]["id"]
    classes = []
    for a, b in combinations(groups.values(), 2):
        category_set = {a["category"], b["category"]}
        same_rigid = a["body"] == b["body"]
        arm_indices = [
            int(x["body"][-1])
            for x in (a, b)
            if x["category"] == "arm" and x["body"].startswith("arm_link_")
        ]
        adjacent_arm = len(arm_indices) == 2 and abs(arm_indices[0] - arm_indices[1]) <= 1
        # Frame, drive and rods have intentional hinge/slider fastening interfaces.
        mounting_body_pairs = {
            frozenset(("c7_fixed", "c7_drive")),
            frozenset(("c7_drive", "c7_link_R")),
            frozenset(("c7_drive", "c7_link_L")),
            frozenset(("c7_link_R", "c7_jaw_R")),
            frozenset(("c7_link_L", "c7_jaw_L")),
            frozenset(("c7_fixed", "c7_jaw_R")),
            frozenset(("c7_fixed", "c7_jaw_L")),
        }
        internal_mechanism = (
            category_set == {"mechanism"}
            and frozenset((a["body"], b["body"])) in mounting_body_pairs
        )
        horn_mount = any(
            x["body"] == "arm_link_4" and x["category"] == "arm" for x in (a, b)
        ) and any(x["body"] == "c7_drive" for x in (a, b))
        wrist_mount = a["body"] in {"arm_link_4", "c7_fixed"} and b["body"] in {
            "arm_link_4",
            "c7_fixed",
        }
        base_mount = any(x["body"] == "world" and x["category"] == "arm" for x in (a, b)) and any(
            x["body"] == "arm_link_1" for x in (a, b)
        )
        fixed_support = a["body"] == b["body"] == "world"
        if (
            same_rigid
            or adjacent_arm
            or internal_mechanism
            or horn_mount
            or wrist_mount
            or base_mount
            or fixed_support
        ):
            rule = "intentional_rigid_or_adjacent_joint_mount"
            enabled = False
        elif category_set == {"cap", "support"}:
            rule, enabled = "support_allowed_outside_hold", True
        elif category_set == {"cap", "softtip"}:
            rule, enabled = "left_right_grip", True
        else:
            rule, enabled = "forbidden", True
        classes.append({"group1": a["id"], "group2": b["id"], "class": rule, "enabled": enabled})
        if enabled:
            a["mask"] |= 1 << b["id"]
            b["mask"] |= 1 << a["id"]
    assert len(groups) < 31
    elements = {g.get("name"): g for g in world.iter("geom")}
    for geom in geoms:
        group = groups[(geom["body"], geom["category"])]
        elements[geom["name"]].attrib.update(
            contype=str(1 << group["id"]),
            conaffinity=str(group["mask"]),
            condim="4",
            friction="0.7 0.001 0.0001",
            solref="0.006 1",
            solimp="0.95 0.99 0.001",
        )
        if geom["category"] == "softtip":
            ET.SubElement(
                contacts,
                "pair",
                geom1=geom["name"],
                geom2="cap_geom",
                condim="4",
                friction="0.7 0.7 0.001 0.0001 0.0001",
                solref="0.01 1",
                solimp="0.90 0.98 0.001",
            )
    ET.indent(tree)
    tree.write(MODEL / "scene.xml", encoding="unicode")
    save_json(
        MODEL / "collision_pairs.json",
        {
            "geoms": geoms,
            "groups": list(groups.values()),
            "group_pairs": classes,
            "same_group": "disabled: same rigid part/category",
            "coverage": "Every physical geom belongs to exactly one group; symmetric matrix classifies all distinct-group pairs. Visual source meshes are replaced by their collocated physical proxies, not silently omitted.",
        },
    )
    save_json(MODEL / "proxy_report.json", reports)
    save_json(
        MODEL / "inertias.json",
        {
            "status": "unmeasured nominal lumped rectangular inertias",
            "body_mass_center_extents": lumped,
        },
    )
    model = mujoco.MjModel.from_xml_path(str(MODEL / "scene.xml"))
    data = mujoco.MjData(model)
    place_reset(model, data, [0, 0, 0, 0], 90)
    audit = {
        "mujoco_version": mujoco.__version__,
        "nq": model.nq,
        "nv": model.nv,
        "nu": model.nu,
        "neq": model.neq,
        "nmocap": model.nmocap,
        "ngeom": model.ngeom,
        "npair": model.npair,
        "gravity": model.opt.gravity.tolist(),
        "timestep": model.opt.timestep,
        "independent_arm_dof": 4,
        "independent_jaw_dof": 1,
        "closure": "5 planar jaw coordinates - two planar rod-to-slider point constraints (rank4) =1 DOF",
        "free_cap": True,
        "cap_weld": False,
        "runtime_pose_writes": False,
        "scene_xml_sha256": sha(MODEL / "scene.xml"),
        "builder_sha256": sha(Path(__file__)),
        "mesh_assets_sha256": {
            a.get("file"): sha(MODEL / "meshes" / a.get("file")) for a in root.findall("asset/mesh")
        },
        "scanfit_components": [f"{p}_{s}" for s in ("L", "R") for p in ("cot", "foam", "band")],
    }
    save_json(MODEL / "audit.json", audit)
    print(json.dumps(audit, indent=2))
    return model


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    build()
