"""Identify the ID5 case-top frame holes without treating case screws as anchors."""

from __future__ import annotations

import math

import cadquery as cq
from cadre.probes import cylinder_surface_sense
from OCP.Bnd import Bnd_Box
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib

TOP_HOLE_DIAMETER_MM = 2.1
TOP_HOLE_MAX_DEPTH_MM = 4.0
EXPECTED_CENTERS_XY_MM = ((-8.2, 158.9), (-8.2, 170.9), (7.8, 158.9), (7.8, 170.9))
EXPECTED_TOP_Z_MM = 199.85


def _exact_z_range(shape: cq.Shape) -> tuple[float, float]:
    """B-rep bounds that ignore any mesh a renderer left on a shared shape.

    ``Shape.BoundingBox()`` uses stored triangulation when present, so the same
    cached occurrence measured differently after an unrelated test rendered it.
    """
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped, box, False, False)
    _, _, zmin, _, _, zmax = box.Get()
    return zmin, zmax


def inspect_case_top_holes(motor_case: cq.Shape) -> dict:
    """Read trimmed, concave axial faces at the case top in assembly coordinates."""
    top_z = _exact_z_range(motor_case)[1]
    holes = []
    for face in motor_case.Faces():
        if face.geomType() != "CYLINDER" or cylinder_surface_sense(face) != "concave":
            continue
        cylinder = BRepAdaptor_Surface(face.wrapped).Cylinder()
        if not math.isclose(cylinder.Radius() * 2, TOP_HOLE_DIAMETER_MM, abs_tol=0.01):
            continue
        axis = cylinder.Axis().Direction()
        face_zmin, face_zmax = _exact_z_range(face)
        if abs(axis.Z()) < 0.999 or face_zmax < top_z - 0.3:
            continue
        depth = top_z - face_zmin
        if not 0 < depth <= TOP_HOLE_MAX_DEPTH_MM + 0.01:
            continue
        point = cylinder.Location()
        holes.append((point.X(), point.Y(), depth))
    if len(holes) != 4:
        raise ValueError(f"Expected four case-top frame holes, found {len(holes)}")
    return {
        "centers_xy_mm": sorted((round(x, 4), round(y, 4)) for x, y, _ in holes),
        "diameter_mm": TOP_HOLE_DIAMETER_MM,
        "surface_z_mm": round(top_z, 4),
        "trimmed_depths_mm": sorted(round(depth, 4) for _, _, depth in holes),
    }


def validate_id5_case_anchor(motor_case: cq.Shape, tolerance_mm: float = 0.02) -> dict:
    """Reject a different occurrence or a translated mounting pattern."""
    report = inspect_case_top_holes(motor_case)
    if abs(report["surface_z_mm"] - EXPECTED_TOP_Z_MM) > tolerance_mm:
        raise ValueError("ID5 case-top surface is at the wrong assembly datum")
    if any(
        math.dist(actual, expected) > tolerance_mm
        for actual, expected in zip(report["centers_xy_mm"], EXPECTED_CENTERS_XY_MM)
    ):
        raise ValueError("ID5 case-top hole centers do not match the assembly datum")
    return report
