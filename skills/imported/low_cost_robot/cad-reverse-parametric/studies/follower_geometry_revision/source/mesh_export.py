"""Closed STL export with an explicit, bounded repair for the source gripper.

The supplied gripper's STEP is valid, but its legacy cone trims tessellate with
missing faces in this kernel (the supplied legacy STL is also open). The only
fallback below re-cuts its eight analytic countersinks in a TEMPORARY mesh copy,
with 0.00001 mm radial relief. The delivered STEP and design B-rep are unchanged.
Every fallback is logged and fails if geometry change exceeds 0.01 mm^3.
"""

from pathlib import Path
import math
import cadquery as cq
import trimesh
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cone
from OCP.TopAbs import TopAbs_REVERSED


def _volume(shape):
    return float(sum(s.Volume() for s in shape.Solids()))


def export_closed_stl(shape: cq.Shape, path: Path, allow_gripper_repair: bool = False):
    shape.exportStl(
        str(path), tolerance=0.005, angularTolerance=0.1, relative=False, parallel=False
    )
    mesh = trimesh.load_mesh(path, process=True)
    metadata = dict(
        linear_deflection_mm=0.005,
        angular_deflection_rad=0.1,
        relative_deflection=False,
        temporary_copy_repaired=False,
    )
    if mesh.is_watertight and mesh.volume > 0:
        return metadata
    if not allow_gripper_repair:
        raise ValueError(f"STL is not closed: {path.name}")
    relief = 1e-5
    cutters = []
    for face in shape.Faces():
        surface = BRepAdaptor_Surface(face.wrapped)
        if (
            surface.GetType() != GeomAbs_Cone
            or face.wrapped.Orientation() != TopAbs_REVERSED
        ):
            continue
        cone = surface.Cone()
        if (
            abs(cone.RefRadius() - 1.4) > 1e-5
            or abs(cone.SemiAngle() - math.pi / 4) > 1e-6
        ):
            continue
        axis, centre = cone.Axis().Direction(), cone.Axis().Location()
        if abs(axis.Z()) < 1 - 1e-8:
            continue
        direction = cq.Vector(axis.X(), axis.Y(), axis.Z())
        start = cq.Vector(centre.X(), centre.Y(), centre.Z()) - direction * 0.5
        cutters.append(
            cq.Solid.makeCone(0.9 + relief, 1.9 + relief, 1, start, direction)
        )
    if len(cutters) != 8:
        raise ValueError("Unexpected gripper countersink layout; no automatic repair")
    temporary_copy = shape.cut(*cutters).clean()
    removed, added = (
        _volume(shape.cut(temporary_copy)),
        _volume(temporary_copy.cut(shape)),
    )
    if (
        not temporary_copy.isValid()
        or len(temporary_copy.Solids()) != 1
        or removed > 0.01
        or added > 1e-6
    ):
        raise ValueError("Mesh-only repair exceeded its geometric bounds")
    temporary_copy.exportStl(
        str(path), tolerance=0.005, angularTolerance=0.1, relative=False, parallel=False
    )
    mesh = trimesh.load_mesh(path, process=True)
    if not mesh.is_watertight or mesh.volume <= 0:
        raise ValueError("Mesh-only repair did not produce a closed STL")
    metadata.update(
        temporary_copy_repaired=True,
        source_step_unchanged=True,
        cone_count=len(cutters),
        radial_relief_mm=relief,
        temporary_copy_removed_volume_mm3=removed,
        temporary_copy_added_volume_mm3=added,
    )
    return metadata
