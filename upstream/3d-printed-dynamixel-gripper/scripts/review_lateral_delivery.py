"""Read-only supplemental review of the supplied lateral-camera study.

The donor's checks are reproduced, not promoted to independent engineering
approval. Added probes test omissions with explicit, assumed tool envelopes.
All generated evidence stays outside the immutable extracted delivery.
"""

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import cadquery as cq
import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    def convert(obj):
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        raise TypeError(type(obj).__name__)

    path.write_text(json.dumps(value, indent=2, allow_nan=False, default=convert) + "\n")


def cylinder(point, axis, radius, length):
    return cq.Solid.makeCylinder(radius, length, cq.Vector(*point), cq.Vector(*axis))


def common_volume(a, b):
    common = a.intersect(b)
    if common.Solids() and not common.isValid():
        raise ValueError("Invalid common")
    value = sum(s.Volume() for s in common.Solids())
    if not np.isfinite(value) or value < -1e-7:
        raise ValueError("Invalid volume")
    return max(0.0, value)


def run(repo, out, render_views):
    out.mkdir(parents=True, exist_ok=False)
    toolkit = repo / "skills/cad-reverse-parametric"
    study_dir = toolkit / "studies/gripper_camera_lateral"
    source = study_dir / "source"
    artifact = toolkit / "outputs/gripper_camera_lateral/unaccepted/20260922-r1"
    sys.path.insert(0, str(source))
    import design
    import review
    import study
    from render_cad import render
    from vision import check_vision

    study.verify_export_binding(artifact)
    d = design.build()
    closed = review.reload_items(artifact / "CAD/full_arm_0deg.step", d.items)
    opened = review.reload_items(artifact / "CAD/full_arm_50deg.step", d.at_opening(50))
    hand_items = d.in_hand(closed)
    hand = {i.key: i.world for i in hand_items}
    result = {
        "scope": "Supplemental review; no fabrication or operation approval",
        "complete": False,
        "environment": {"python": platform.python_version(), "cadquery": cq.__version__},
        "source": str(repo),
        "study_code_sha256": {p.name: digest(p) for p in source.glob("*.py")},
        "cad_sha256": {
            str(p.relative_to(artifact)): digest(p) for p in (artifact / "CAD").rglob("*.step")
        },
        "review_script_sha256": digest(Path(__file__)),
        "export_hash_binding": "passed",
        "interfaces": review.check_interfaces(d, closed),
        "continuous_new_mount_bound": review.continuous_mount_bound(d, closed),
    }
    units = sorted({i.unit for i in closed if "XL,XC-330" in i.unit or "XL-430" in i.unit})
    result["motor_units"] = units
    result["non_solid_occurrences"] = [
        {
            "key": i.key,
            "path": i.original_path,
            "faces": len(i.shape.Faces()),
            "bbox_H_mm": design.bounds(hand[i.key]),
        }
        for i in closed
        if not i.shape.Solids()
    ]
    print("Input bound; scanning serialized closed/open solid geometry", flush=True)
    for name, items in (("closed", closed), ("open", opened)):
        result[f"{name}_scan"] = review.scan(items)
        write_json(out / "audit.json", result)
        print(name, result[f"{name}_scan"]["external_count"], flush=True)

    print("Recomputing sampled jaw motion and camera visibility", flush=True)
    result["jaw_motion"] = review.motion_scan(d, closed)
    result["vision"] = check_vision(d, items_override=hand_items)
    write_json(out / "audit.json", result)

    # A deliberately detached carrier has unchanged infinite hole axes.
    fwd = design.camera_basis(d.config)[2]
    gap = -10.0
    change = d.hand_world * cq.Location(tuple(gap * fwd)) * d.hand_world.inverse
    detached = [
        design.Item(
            i.key,
            i.original_path,
            i.shape,
            change * i.loc if i.key == "uvc28_camera_carrier" else i.loc,
            i.unit,
            i.role,
            i.color,
        )
        for i in closed
    ]
    shifted_carrier = hand["uvc28_camera_carrier"].translate(tuple(gap * fwd))
    result["detached_carrier_negative_control"] = {
        "translation_along_optical_axis_mm": gap,
        "original_bridge_carrier_distance_mm": hand["wrist_camera_bridge"].distance(
            hand["uvc28_camera_carrier"]
        ),
        "modified_bridge_carrier_distance_mm": hand["wrist_camera_bridge"].distance(
            shifted_carrier
        ),
        "donor_interface_checker_passed": review.check_interfaces(d, detached)["passed"],
        "scope": "Interface checker only; not a bypass of every top-level gate",
    }
    assert result["detached_carrier_negative_control"]["modified_bridge_carrier_distance_mm"] > 1
    box = cq.Solid.makeBox(10, 10, 10)
    a = design.Item("a", "a", box, cq.Location(), "a", "camera_mount", (1, 0, 0))
    b = design.Item(
        "b", "b", box.Shells()[0], cq.Location((5, 0, 0)), "b", "camera_mount", (0, 1, 0)
    )
    result["shell_obstacle_negative_control"] = review.scan([a, b])

    # Each probe includes the inserted driver shaft and a cylindrical grip. The
    # envelopes are assumptions, not a purchased-tool specification or L-key sweep.
    targets = []
    for u in (-14.0, 14.0):
        for v in (-14.0, 14.0):
            targets.append((f"camera_M2_{u:g}_{v:g}", u, v, 8.6))
    for u in (-12.0, 12.0):
        targets.append((f"carrier_M3_{u:g}", u, -24.0, 3.0))
    tools = {}
    result["tool_assumptions"] = {
        "shaft_diameter_mm": 6,
        "shaft_length_mm": 60,
        "handle_diameter_mm": 20,
        "handle_length_mm": 30,
        "axis": "outward along optical forward",
        "stand_off_from_seat_mm": 2,
        "scope": "Seated straight driver envelope; no actual tool, fingers or insertion sweep",
    }
    for name, u, v, w in targets:
        base = design.camera_point(d.config, u, v, w + 2)
        shaft = cylinder(base, fwd, 3, 60)
        grip = cylinder(base + 60 * fwd, fwd, 10, 30)
        tools[name] = (shaft, grip)
    result["tool_access"] = []
    for name, (shaft, grip) in tools.items():
        hits = []
        for item in hand_items:
            if not item.shape.Solids():
                continue
            for component, envelope in (("shaft", shaft), ("handle", grip)):
                b1, b2 = np.array(design.bounds(envelope)), np.array(design.bounds(item.world))
                if np.any(np.minimum(b1[3:], b2[3:]) - np.maximum(b1[:3], b2[:3]) <= 1e-5):
                    continue
                v = common_volume(envelope, item.world)
                if v > 1e-4:
                    hits.append(
                        {
                            "key": item.key,
                            "path": item.original_path,
                            "role": item.role,
                            "component": component,
                            "volume_mm3": v,
                        }
                    )
        # Bench stage only retains the three new mount parts and camera proxies.
        bench_hits = [h for h in hits if h["role"] in ("camera_mount", "camera_proxy")]
        result["tool_access"].append(
            {"target": name, "installed_hits": hits, "bench_hits": bench_hits}
        )

    # Inventory bbox overlaps with omitted surfaces; these are unresolved
    # envelopes, never proof of real solid interference.
    omitted = []
    for i in hand_items:
        if i.shape.Solids():
            continue
        b = np.array(design.bounds(i.world))
        for name in list(d.parts) + list(d.proxies):
            q = np.array(design.bounds(hand[name]))
            overlap = np.minimum(b[3:], q[3:]) - np.maximum(b[:3], q[:3])
            if np.all(overlap > 1e-5):
                omitted.append(
                    {
                        "surface_key": i.key,
                        "path": i.original_path,
                        "new_part": name,
                        "bbox_overlap_mm": overlap.tolist(),
                    }
                )
    result["new_part_vs_omitted_surface_bbox_overlap"] = omitted
    result["camera_lever_arm_from_flange_center_mm"] = float(
        np.linalg.norm(design.camera_optical_center(d.config) - design.MOUNT_CENTER)
    )
    result["new_parts"] = review.check_parts(artifact, d)
    result["complete"] = True
    write_json(out / "audit.json", result)
    if render_views:
        # Render actual reimported STEP in a fixed hand coordinate frame.
        selected = [
            i
            for i in hand_items
            if i.role != "upstream"
            or "/XL,XC-330 v1:6/" in i.original_path
            or "/XL,XC-330 v1:8/" in i.original_path
        ]
        shapes = [(i.world, i.color) for i in selected if i.shape.Solids()]
        for name, direction in (
            ("X", (1, 0, 0)),
            ("Y", (0, 1, 0)),
            ("Z", (0, 0, 1)),
            ("iso", (1, -1, 1)),
        ):
            render(shapes, out / f"hand_{name}.png", direction=direction)
        render(
            shapes + [(s, (1, 0.1, 0.1, 0.4)) for pair in tools.values() for s in pair],
            out / "tool_envelopes.png",
            direction=(1, -1, 1),
        )
    print(
        json.dumps(
            {
                "output": str(out),
                "motors": len(units),
                "non_solids": len(result["non_solid_occurrences"]),
                "detached_carrier": result["detached_carrier_negative_control"],
                "tool_hits": {x["target"]: len(x["installed_hits"]) for x in result["tool_access"]},
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    run(args.repo.resolve(), args.out.resolve(), args.render)


if __name__ == "__main__":
    main()
