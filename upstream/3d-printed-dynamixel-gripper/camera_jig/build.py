"""R3 P05 web clamp with a 28 mm UVC interface. All coordinates are millimetres.

The original link and the supplier camera spacer are unchanged. The link is
identified photographically, not measured on the user's physical printer output.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import cadquery as cq
from cadre.probes import cylinder_surface_sense
from OCP.BRepAdaptor import BRepAdaptor_Surface

from camera_jig.spec import SPEC
from scripts.assembly_io import bounds, read_step
from scripts.step_cache import read_rows

ROOT = Path(__file__).resolve().parents[1]
LINK = ROOT / SPEC.parent["step_path"]
ARM = ROOT / SPEC.assembly_source["step_path"]
DONOR = ROOT / SPEC.donor["step_path"]
LINK_SHA = SPEC.parent["sha256"]
DONOR_SHA = SPEC.donor["sha256"]
CX = SPEC.camera["origin_world_mm"][0]
CAMERA_ORIGIN = tuple(SPEC.camera["origin_world_mm"])
CAMERA_LOC = cq.Location(
    CAMERA_ORIGIN,
    tuple(SPEC.camera["carrier_rotation_axis"]),
    SPEC.camera["carrier_rotation_deg"],
)
EPS = 1e-5


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_source(path, expected):
    if sha(path) != expected:
        raise ValueError(f"Source hash mismatch: {path}")


def box(dx, dy, dz, x, y, z):
    return cq.Solid.makeBox(dx, dy, dz, cq.Vector(x, y, z))


def common_volume(a, b):
    for s in (a, b):
        if not s.isValid() or not s.Solids():
            raise ValueError("Boolean input must contain valid solids")
    common = a.intersect(b)
    volume = sum(s.Volume() for s in common.Solids())
    if not common.isValid() or not math.isfinite(volume) or volume < -EPS:
        raise ValueError("Invalid Boolean common; not a clearance pass")
    return max(0.0, volume)


def donor_parts():
    require_source(DONOR, DONOR_SHA)
    rows = read_rows(DONOR)
    if len(rows) != 34 or not rows[5].path.endswith("/NAUO6"):
        raise ValueError("Reference camera/spacer occurrence inventory changed")
    spacer, camera = rows[5].shape, rows[15].shape
    if any(abs(a - b) > EPS for a, b in zip(bounds(spacer), (-19, -19, 0, 19, 19, 2))):
        raise ValueError("Unexpected spacer frame")
    return spacer, camera


def drill_y(shape, diameter, x, z):
    bores = SPEC.clamp["clamp_bores"]
    return shape.cut(
        cq.Solid.makeCylinder(
            diameter / 2,
            bores["drill_length_mm"],
            (x, bores["drill_start_y_mm"], z),
            (0, 1, 0),
        )
    )


def build_parts(camera_pitch=None):
    require_source(LINK, LINK_SHA)
    camera_pitch = camera_pitch or SPEC.camera["mounting_pattern_mm"][0]
    saddle_spec = SPEC.clamp["saddle"]
    saddle = box(*saddle_spec["size_mm"], *saddle_spec["origin_mm"])
    stop_spec = SPEC.clamp["top_stop"]
    stop = box(*stop_spec["size_mm"], *stop_spec["origin_mm"])
    # The mast stays behind the camera seating plane; a shelf joins the clamp.
    mast_spec = SPEC.clamp["mast_local"]
    mast_local = box(*mast_spec["size_mm"], *mast_spec["origin_mm"])
    shelf_spec = SPEC.clamp["shelf"]
    shelf = box(*shelf_spec["size_mm"], *shelf_spec["origin_mm"])
    frame_x, frame_y, frame_z = SPEC.camera["carrier_outer_mm"]
    frame = (
        cq.Workplane("XY")
        .rect(frame_x, frame_y)
        .extrude(frame_z)
        .edges("|Z")
        .fillet(SPEC.camera["corner_fillet_mm"])
        .val()
    )
    opening_x, opening_y = SPEC.camera["carrier_opening_mm"]
    frame = frame.cut(box(opening_x, opening_y, frame_z + 2, -opening_x / 2, -opening_y / 2, -1))
    for x, y in itertools.product((-camera_pitch / 2, camera_pitch / 2), repeat=2):
        frame = frame.cut(
            cq.Solid.makeCylinder(
                SPEC.camera["mounting_hole_diameter_mm"] / 2,
                frame_z + 2,
                (x, y, -1),
            )
        )
    carrier_spec = SPEC.clamp["interchangeable_carrier"]
    carrier = frame.fuse(box(*carrier_spec["tab_size_mm"], *carrier_spec["tab_origin_local_mm"]))
    cable = SPEC.clamp["cable_strain_relief_reservations_local"]
    for origin in cable["ear_origins_local_mm"]:
        carrier = carrier.fuse(box(*cable["ear_size_mm"], *origin))
    for origin in cable["slot_origins_local_mm"]:
        carrier = carrier.cut(box(*cable["slot_size_mm"], *origin))
    for x, y in carrier_spec["attachment_hole_centres_local_mm"]:
        hole = cq.Solid.makeCylinder(
            carrier_spec["attachment_hole_diameter_mm"] / 2,
            9,
            (x, y, -5),
        )
        carrier = carrier.cut(hole)
        mast_local = mast_local.cut(hole)
        nut_pocket = (
            cq.Workplane("XY", origin=(x, y, 1.3))
            .polygon(6, 4 / math.cos(math.pi / 6))
            .extrude(1.7)
            .val()
        )
        carrier = carrier.cut(nut_pocket)
    saddle = saddle.fuse(stop, shelf, mast_local.moved(CAMERA_LOC)).clean()
    jaw_spec = SPEC.clamp["front_jaw"]
    jaw = box(*jaw_spec["size_mm"], *jaw_spec["origin_mm"])
    # Open-bottom reliefs straddle P05's motor cheeks without squeezing them.
    relief = SPEC.clamp["jaw_reliefs"]
    relief_x, relief_y, relief_z = relief["size_mm"]
    relief_y_origin, relief_z_origin = relief["origin_yz_mm"]
    for x in relief["center_x_mm"]:
        jaw = jaw.cut(
            box(relief_x, relief_y, relief_z, x - relief_x / 2, relief_y_origin, relief_z_origin)
        )
    bores = SPEC.clamp["clamp_bores"]
    for x in bores["center_x_mm"]:
        saddle = drill_y(saddle, bores["diameter_mm"], x, bores["center_z_mm"])
        jaw = drill_y(jaw, bores["diameter_mm"], x, bores["center_z_mm"])
    spacer, _ = donor_parts()
    return {
        "saddle": saddle,
        "front_jaw": jaw.clean(),
        "camera_carrier": carrier.clean().moved(CAMERA_LOC),
        "camera_spacer": spacer.translate((0, 0, 3)).moved(CAMERA_LOC),
    }


def camera_bores(shape):
    local = shape.moved(CAMERA_LOC.inverse)
    holes = []
    for face in local.Faces():
        if face.geomType() != "CYLINDER" or cylinder_surface_sense(face) != "concave":
            continue
        cylinder = BRepAdaptor_Surface(face.wrapped).Cylinder()
        d, p = cylinder.Axis().Direction(), cylinder.Location()
        if abs(d.Z()) < 1 - 1e-8 or not 0.5 < cylinder.Radius() < 2:
            continue
        bb = bounds(face)
        if bb[2] > EPS or bb[5] < 3 - EPS:
            continue
        xy = (p.X() - p.Z() * d.X() / d.Z(), p.Y() - p.Z() * d.Y() / d.Z())
        if (
            max(abs(value) for value in xy)
            > SPEC.camera["mounting_pattern_detection_window_half_mm"]
        ):
            continue
        if not any(math.dist(xy, h["xy_mm"]) < EPS for h in holes):
            holes.append({"xy_mm": xy, "diameter_mm": 2 * cylinder.Radius()})
    return holes


def validate_parts(parts):
    require_source(LINK, LINK_SHA)
    link = cq.importers.importStep(str(LINK)).val()
    holes = camera_bores(parts["camera_carrier"])
    target = list(itertools.product((-14.0, 14.0), repeat=2))
    error = None
    if len(holes) == 4:
        error = min(
            max(math.dist(a, b["xy_mm"]) for a, b in zip(target, order))
            for order in itertools.permutations(holes)
        )
    diam_error = max((abs(h["diameter_mm"] - 2.4) for h in holes), default=None)
    crossings = {name: common_volume(shape, link) for name, shape in parts.items()}
    overlaps = {
        f"{a}/{b}": common_volume(parts[a], parts[b]) for a, b in itertools.combinations(parts, 2)
    }
    contact_spec = SPEC.raw["contact_requirements"]
    probe = contact_spec["probe_depth_mm"]
    saddle_contact = common_volume(parts["saddle"].translate((0, probe, 0)), link) / probe
    jaw_contact = common_volume(parts["front_jaw"].translate((0, -probe, 0)), link) / probe
    saddle_local = parts["saddle"].moved(CAMERA_LOC.inverse)
    carrier_local = parts["camera_carrier"].moved(CAMERA_LOC.inverse)
    carrier_contact = common_volume(saddle_local, carrier_local.translate((0, 0, -probe))) / probe
    contact_areas = {
        "saddle_to_P05": saddle_contact,
        "front_jaw_to_P05": jaw_contact,
        "camera_carrier_to_saddle": carrier_contact,
    }
    contact_pass = (
        saddle_contact >= contact_spec["minimum_saddle_to_p05_area_mm2"]
        and jaw_contact >= contact_spec["minimum_front_jaw_to_p05_area_mm2"]
        and carrier_contact >= contact_spec["minimum_carrier_to_saddle_area_mm2"]
    )
    valid = all(s.isValid() and len(s.Solids()) == 1 and s.Volume() > 0 for s in parts.values())
    passed = (
        valid
        and error is not None
        and error < EPS
        and diam_error < EPS
        and max(crossings.values()) < EPS
        and max(overlaps.values()) < EPS
        and contact_pass
    )
    return {
        "geometry_pass": passed,
        "part_solids": {name: len(shape.Solids()) for name, shape in parts.items()},
        "camera_hole_count": len(holes),
        "camera_pattern_max_error_mm": error,
        "camera_diameter_error_mm": diam_error,
        "camera_bores": holes,
        "link_intersections_mm3": crossings,
        "candidate_intersections_mm3": overlaps,
        "contact_area_probe_mm2": contact_areas,
        "contact_area_pass": contact_pass,
        "physical_link_dimensions": "unknown",
        "motion_clearance": "not_checked",
        "clamp_retention_and_PLA_creep": "unknown",
        "tool_and_screw_selection": "candidate_only",
        "camera_model_matches_user_purchase": "unknown",
        "fabrication_approved": False,
    }


def validate_change_mask(parts):
    source_mutated = sha(LINK) != LINK_SHA
    link = cq.importers.importStep(str(LINK)).val()
    intersections = {name: common_volume(shape, link) for name, shape in parts.items()}
    allowed = set(SPEC.change_mask["allowed_new_parts"])
    unexpected = sorted(set(parts) - allowed)
    limit = SPEC.change_mask["maximum_source_intersection_mm3"]
    return {
        "pass": (
            not source_mutated
            and not unexpected
            and all(volume <= limit for volume in intersections.values())
        ),
        "source_mutated": source_mutated,
        "unexpected_parts": unexpected,
        "source_intersections_mm3": intersections,
        "maximum_source_intersection_mm3": limit,
    }


def envelope_hardware():
    """Threadless nominal envelopes, not selected purchasing specifications."""
    result = {}
    for i, (x, y) in enumerate(itertools.product((-14.0, 14.0), repeat=2)):
        shaft = cq.Solid.makeCylinder(1, 10, (x, y, -3.5))
        head = cq.Solid.makeCylinder(1.9, 1.6, (x, y, 6.5))
        nut = (
            cq.Workplane("XY", origin=(x, y, -1.6))
            .polygon(6, 4 / math.cos(math.pi / 6))
            .extrude(1.6)
            .val()
            .cut(cq.Solid.makeCylinder(1, 2, (x, y, -1.7)))
        )
        result[f"M2x10_{i}_ENVELOPE"] = shaft.fuse(head).moved(CAMERA_LOC)
        result[f"M2nut_{i}_ENVELOPE"] = nut.moved(CAMERA_LOC)
    for i, x in enumerate((CX - 28.5, CX + 28.5)):
        bolt = cq.Solid.makeCylinder(1.5, 16, (x, 130.9, 188.6), (0, 1, 0))
        bolt = bolt.fuse(cq.Solid.makeCylinder(2.75, 3, (x, 146.9, 188.6), (0, 1, 0)))
        nut = (
            cq.Workplane("XZ", origin=(x, 136.9, 188.6))
            .polygon(6, 5.5 / math.cos(math.pi / 6))
            .extrude(2.4)
            .val()
        )
        nut = drill_y(nut, 3, x, 188.6)
        result[f"M3x16_{i}_ENVELOPE"] = bolt
        result[f"M3nut_{i}_ENVELOPE"] = nut
    carrier_spec = SPEC.clamp["interchangeable_carrier"]
    for i, (x, y) in enumerate(carrier_spec["attachment_hole_centres_local_mm"]):
        shaft = cq.Solid.makeCylinder(1, 10, (x, y, -4), (0, 0, 1))
        head = cq.Solid.makeCylinder(1.9, 1.6, (x, y, -5.6))
        nut = (
            cq.Workplane("XY", origin=(x, y, 1.4))
            .polygon(6, 4 / math.cos(math.pi / 6))
            .extrude(1.6)
            .val()
            .cut(cq.Solid.makeCylinder(1, 2, (x, y, 1.3)))
        )
        result[f"M2x10_carrier_{i}_ENVELOPE"] = shaft.fuse(head).moved(CAMERA_LOC)
        result[f"M2nut_carrier_{i}_ENVELOPE"] = nut.moved(CAMERA_LOC)
    return result


def collision_rows(candidates, obstacles, *, non_solid_evidence=None):
    collisions, errors = [], []
    for name, shape in candidates.items():
        a = bounds(shape)
        for obstacle, solid in obstacles.items():
            b = bounds(solid)
            if any(a[i + 3] < b[i] - EPS or b[i + 3] < a[i] - EPS for i in range(3)):
                continue
            try:
                # A surface-only supplier model cannot supply an occupied volume.
                # Disjointness from its inflated enclosing box IS sufficient proof.
                if not solid.Solids() and solid.isValid():
                    enclosing = box(
                        *(b[i + 3] - b[i] + 2 * EPS for i in range(3)),
                        *(b[i] - EPS for i in range(3)),
                    )
                    distance = shape.distance(enclosing)
                    if not math.isfinite(distance) or distance <= EPS:
                        raise ValueError("Non-solid obstacle envelope not proven separated")
                    if non_solid_evidence is not None:
                        non_solid_evidence.append(
                            {
                                "jig": name,
                                "obstacle": obstacle,
                                "method": "distance to inflated enclosing box",
                                "distance_mm": distance,
                                "box_padding_mm": EPS,
                            }
                        )
                    continue
                volume = common_volume(shape, solid)
                if volume > EPS:
                    collisions.append({"jig": name, "obstacle": obstacle, "volume_mm3": volume})
            except Exception as exc:  # noqa: BLE001 - all kernel failures are recorded as failures
                errors.append({"jig": name, "obstacle": obstacle, "error": str(exc)})
    return collisions, errors


def export(out):
    out.mkdir(parents=True, exist_ok=False)
    parts = build_parts()
    for name, shape in parts.items():
        cq.exporters.export(shape, str(out / f"{name}_UNVALIDATED.step"))
        cq.exporters.export(
            shape, str(out / f"{name}_UNVALIDATED.stl"), tolerance=0.02, angularTolerance=0.1
        )
    reloaded = {n: cq.importers.importStep(str(out / f"{n}_UNVALIDATED.step")).val() for n in parts}
    result = validate_parts(reloaded)
    _, camera = donor_parts()
    n = cq.Vector(0, math.cos(math.pi / 6), -0.5)
    camera = camera.rotate((0, 0, 0), (1, 0, 0), 150).translate(
        tuple(cq.Vector(*CAMERA_ORIGIN) + n * 5)
    )
    hardware = envelope_hardware()
    assembly = cq.Assembly(name="R3_P05_CAMERA_JIG_UNVALIDATED")
    link = cq.importers.importStep(str(LINK)).val()
    assembly.add(link, name="P05_REFERENCE_UNCHANGED", color=cq.Color(0.74, 0.76, 0.78))
    for name, s in reloaded.items():
        assembly.add(s, name=name, color=cq.Color(0.13, 0.62, 0.7))
    assembly.add(
        camera, name="REFERENCE_UVC_CAMERA_NOT_PURCHASE_SPEC", color=cq.Color(0.18, 0.42, 0.2)
    )
    for name, s in hardware.items():
        assembly.add(s, name=name, color=cq.Color(0.5, 0.51, 0.53))
    assembly.save(str(out / "jig_on_P05_UNVALIDATED.step"))
    _, _, rows = read_step(ARM)
    full = cq.Assembly(name="R3_ARM_WITH_CAMERA_JIG_UNVALIDATED")
    for row in rows:
        full.add(row.world, name=f"source_{row.index}_{row.name}", color=row.color)
    for name, s in {**reloaded, **hardware, "reference_camera": camera}.items():
        full.add(s, name="JIG_" + name, color=cq.Color(0.13, 0.62, 0.7))
    full.save(str(out / "arm_with_jig_UNVALIDATED.step"))
    candidates = {**reloaded, **hardware, "reference_camera": camera}
    # Every source solid is an obstacle, including the link and future M05.
    non_solid_evidence = []
    collisions, errors = collision_rows(
        candidates,
        {f"{r.index}:{r.path}": r.world for r in rows},
        non_solid_evidence=non_solid_evidence,
    )
    internal, internal_errors = [], []
    for a, b in itertools.combinations(candidates, 2):
        hits, failures = collision_rows({a: candidates[a]}, {b: candidates[b]})
        internal.extend(hits)
        internal_errors.extend(failures)
    result.update(
        {
            "scope": "geometry candidate at R3 saved pose; not manufacturing approval",
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in (LINK, ARM, DONOR)},
            "code_sha256": sha(__file__),
            "lock_sha256": sha(ROOT / "uv.lock"),
            "source_leaf_count": len(rows),
            "static_source_collisions": collisions,
            "static_candidate_collisions": internal,
            "static_assembly_pass": not (collisions or internal or errors or internal_errors),
            "boolean_errors": errors + internal_errors,
            "non_solid_obstacle_evidence": non_solid_evidence,
            "camera_optical_axis_world": n.toTuple(),
            "output_sha256": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()},
        }
    )
    (out / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return (
        0
        if result["geometry_pass"] and not (collisions or internal or errors or internal_errors)
        else 2
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    raise SystemExit(export(args.out))


if __name__ == "__main__":
    main()
