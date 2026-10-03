"""Parametric two-part ID5 case-top camera mount candidate.

Coordinates are in the saved arm assembly frame. The camera outline, screws,
strength and actual optical center remain unverified; this is not a print release.
"""

from __future__ import annotations

import math
from itertools import product
from pathlib import Path

import cadquery as cq
import yaml
from cadre.probes import cylinder_surface_sense
from OCP.BRepAdaptor import BRepAdaptor_Surface

from camera_jig.id5_corner_anchor import EXPECTED_CENTERS_XY_MM, EXPECTED_TOP_Z_MM

SPEC_PATH = Path(__file__).resolve().parents[1] / "specs/camera_mount_id5_corner.yaml"


def _config() -> dict:
    with SPEC_PATH.open(encoding="utf-8") as stream:
        spec = yaml.safe_load(stream)
    return spec["mount"]["candidate_geometry"] | {"optical": spec["view_validation"]}


def _cylinder(start: cq.Vector, end: cq.Vector, radius_mm: float) -> cq.Solid:
    direction = end - start
    return cq.Solid.makeCylinder(radius_mm, direction.Length, start, direction.normalized())


def _axial_hole_centers(shape: cq.Shape, diameter_mm: float, axis_index: int) -> set[tuple]:
    centers = set()
    for face in shape.Faces():
        if face.geomType() != "CYLINDER" or cylinder_surface_sense(face) != "concave":
            continue
        cylinder = BRepAdaptor_Surface(face.wrapped).Cylinder()
        if abs(cylinder.Radius() * 2 - diameter_mm) > 0.01:
            continue
        axis = cylinder.Axis().Direction()
        if abs((axis.X(), axis.Y(), axis.Z())[axis_index]) < 0.999:
            continue
        point = cylinder.Location()
        coords = (point.X(), point.Y(), point.Z())
        centers.add(tuple(round(coords[index], 3) for index in range(3) if index != axis_index))
    return centers


def build_candidate(*, anchor_shift_x_mm=0.0, camera_pitch_mm=28.0) -> dict:
    """Create separate case base and replaceable angled camera carrier solids."""
    config = _config()
    base_x, base_y, base_thickness = config["base_size_mm"]
    center_x, center_y = config["base_center_world_xy_mm"]
    top_z = EXPECTED_TOP_Z_MM
    base = cq.Solid.makeBox(
        base_x,
        base_y,
        base_thickness,
        cq.Vector(center_x - base_x / 2, center_y - base_y / 2, top_z),
    )

    optical = config["optical"]
    optical_origin = cq.Vector(*optical["diagnostic_proxy_origin_world_mm"])
    direction = cq.Vector(*optical["diagnostic_proxy_look_at_world_mm"]) - optical_origin
    optical_axis = direction.normalized()
    plane = cq.Plane(origin=optical_origin, xDir=(1, 0, 0), normal=optical_axis)

    crossbar_x, crossbar_y, crossbar_thickness = config["carrier_crossbar_size_local_mm"]
    crossbar_center_y = config["carrier_crossbar_center_local_y_mm"]
    crossbar_local = cq.Solid.makeBox(
        crossbar_x,
        crossbar_y,
        crossbar_thickness,
        cq.Vector(-crossbar_x / 2, crossbar_center_y - crossbar_y / 2, -crossbar_thickness),
    )
    crossbar = crossbar_local.moved(plane.location)
    support_start = cq.Vector(*config["side_support_start_world_mm"])
    side_x = config["side_support_offset_x_mm"]
    support_radius = config["side_support_radius_mm"]
    end_z = config["side_support_end_local_z_mm"]
    supports = []
    for sign in (-1, 1):
        outer_start = cq.Vector(support_start.x + sign * side_x, support_start.y, support_start.z)
        outer_end = plane.toWorldCoords((sign * side_x, crossbar_center_y, end_z))
        inner_end = plane.toWorldCoords((sign * (crossbar_x / 2 - 3), crossbar_center_y, end_z))
        supports.extend(
            (
                _cylinder(support_start, outer_start, support_radius),
                _cylinder(outer_start, outer_end, support_radius),
                _cylinder(outer_end, inner_end, support_radius),
            )
        )
    base = base.fuse(*supports, crossbar).clean()

    for hole_x, hole_y in EXPECTED_CENTERS_XY_MM:
        drill = cq.Solid.makeCylinder(
            config["case_attachment_clearance_diameter_mm"] / 2,
            base_thickness + 2,
            cq.Vector(hole_x + anchor_shift_x_mm, hole_y, top_z - 1),
            cq.Vector(0, 0, 1),
        )
        base = base.cut(drill)

    carrier_x, carrier_y, carrier_thickness = config["carrier_outer_mm"]
    carrier_local = cq.Solid.makeBox(
        carrier_x,
        carrier_y,
        carrier_thickness,
        cq.Vector(-carrier_x / 2, -carrier_y / 2, 0),
    )
    opening_x, opening_y = config["carrier_center_opening_mm"]
    opening = cq.Solid.makeBox(
        opening_x,
        opening_y,
        carrier_thickness + 2,
        cq.Vector(-opening_x / 2, -opening_y / 2, -1),
    )
    carrier_local = carrier_local.cut(opening)
    for hole_x, hole_y in product((-camera_pitch_mm / 2, camera_pitch_mm / 2), repeat=2):
        drill = cq.Solid.makeCylinder(
            config["carrier_hole_diameter_mm"] / 2,
            carrier_thickness + 2,
            cq.Vector(hole_x, hole_y, -1),
            cq.Vector(0, 0, 1),
        )
        carrier_local = carrier_local.cut(drill)

    for hole_x, hole_y in config["carrier_attachment_centers_local_mm"]:
        drill = cq.Solid.makeCylinder(
            config["carrier_attachment_clearance_diameter_mm"] / 2,
            carrier_thickness + crossbar_thickness + 2,
            cq.Vector(hole_x, hole_y, -crossbar_thickness - 1),
            cq.Vector(0, 0, 1),
        )
        carrier_local = carrier_local.cut(drill)
        base = base.cut(drill.moved(plane.location))

    return {
        "base": base.clean(),
        "camera_carrier": carrier_local.clean().moved(plane.location),
        "carrier_location": plane.location,
        "optical_origin": optical_origin.toTuple(),
        "optical_axis": optical_axis.toTuple(),
    }


def validate_candidate(candidate: dict) -> dict:
    """Measure the produced solids, independently of caller's parameter values."""
    config = _config()
    base = candidate["base"]
    carrier = candidate["camera_carrier"]
    if not base.isValid() or not carrier.isValid() or base.Volume() <= 0 or carrier.Volume() <= 0:
        raise ValueError("invalid mount solids")
    if len(base.Solids()) != 1 or len(carrier.Solids()) != 1:
        raise ValueError("mount parts must each contain one solid")

    case_centers = _axial_hole_centers(base, config["case_attachment_clearance_diameter_mm"], 2)
    if case_centers != set(EXPECTED_CENTERS_XY_MM):
        raise ValueError(f"case anchor hole centers mismatch: {sorted(case_centers)}")

    local_carrier = carrier.moved(candidate["carrier_location"].inverse)
    camera_centers = _axial_hole_centers(local_carrier, config["carrier_hole_diameter_mm"], 2)
    pitch = 28.0
    expected_camera_centers = set(product((-pitch / 2, pitch / 2), repeat=2))
    if camera_centers != expected_camera_centers:
        raise ValueError(f"camera pattern mismatch: {sorted(camera_centers)}")

    optical_axis = candidate["optical_axis"]
    if not math.isclose(
        math.sqrt(sum(component**2 for component in optical_axis)), 1, abs_tol=1e-6
    ):
        raise ValueError("optical axis is not a unit vector")
    if optical_axis[1] <= 0 or optical_axis[2] >= 0:
        raise ValueError("optical axis does not look forward and down")
    return {
        "case_anchor_pass": True,
        "camera_pattern_pass": True,
        "case_centers_world_xy_mm": sorted(case_centers),
        "camera_centers_local_xy_mm": sorted(camera_centers),
        "base_volume_mm3": base.Volume(),
        "carrier_volume_mm3": carrier.Volume(),
    }
