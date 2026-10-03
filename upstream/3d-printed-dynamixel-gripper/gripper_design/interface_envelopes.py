"""Conservative covers from analytic boundary faces, without healing donor CAD."""

import math

import cadquery as cq
import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.TopAbs import TopAbs_OUT

from gripper_design.pg2 import _solid_only
from scripts.assembly_io import bounds
from scripts.review_pg3_components import inspect_components


def axial_ray_cover(shape, axis=0):
    """Cover material, not just its surface, with negative-axis boundary rays.

    Every material point has a positive-axis ray that exits through some face.
    Extend each entire face projection back to the solid's global axial minimum.
    The union therefore covers the material even for cavities/concave outlines.
    Disks bound axial cylinders and planar circular/linear contours; other faces
    use full B-rep AABBs. No input face or interior material is dropped.
    """
    if axis not in (0, 1, 2) or not shape.isValid() or not _solid_only(shape):
        raise ValueError("valid finite solid material and Cartesian axis required")
    for solid in shape.Solids():
        classifier = BRepClass3d_SolidClassifier(solid.wrapped)
        classifier.PerformInfinitePoint(1e-7)
        if (
            classifier.State() != TopAbs_OUT
            or not math.isfinite(solid.Volume())
            or solid.Volume() <= 0
        ):
            raise ValueError("finite bounded positive-volume solid required")
    source = bounds(shape)
    if not np.isfinite(source).all() or min(source[i + 3] - source[i] for i in range(3)) <= 0:
        raise ValueError("finite nondegenerate solid bounds required")
    transverse = [i for i in range(3) if i != axis]
    padding = 1e-7
    low = source[axis] - padding
    direction = [0, 0, 0]
    direction[axis] = 1
    pieces, rows = {}, []
    for index, face in enumerate(shape.Faces()):
        bb = bounds(face)
        surface = BRepAdaptor_Surface(face.wrapped)
        centre, radius = None, None
        if face.geomType() == "CYLINDER":
            cylinder = surface.Cylinder()
            vector = np.asarray(cylinder.Axis().Direction().Coord())
            if abs(vector[axis]) > 1 - 1e-10:
                origin = np.asarray(cylinder.Location().Coord())
                middle = (bb[axis] + bb[axis + 3]) / 2
                centre3 = origin + vector * ((middle - origin[axis]) / vector[axis])
                centre = centre3[transverse]
                tilt = np.linalg.norm(vector[transverse])
                # Axial position of a surface point also includes its radius's
                # axial projection. Include that term when bounding tilted axes.
                drift = ((bb[axis + 3] - bb[axis]) / 2 + cylinder.Radius() * tilt) / abs(
                    vector[axis]
                )
                radius = cylinder.Radius() + drift * tilt
        elif face.geomType() == "PLANE":
            edges = face.Edges()
            circles = [e for e in edges if e.geomType() == "CIRCLE"]
            if circles and all(e.geomType() in ("CIRCLE", "LINE") for e in edges):
                circle = BRepAdaptor_Curve(circles[0].wrapped).Circle()
                centre = np.asarray(circle.Location().Coord())[transverse]
                values = []
                for edge in edges:
                    if edge.geomType() == "CIRCLE":
                        circle = BRepAdaptor_Curve(edge.wrapped).Circle()
                        values.append(
                            np.linalg.norm(
                                np.asarray(circle.Location().Coord())[transverse] - centre
                            )
                            + circle.Radius()
                        )
                    else:
                        values.extend(
                            np.linalg.norm(np.asarray(v.toTuple())[transverse] - centre)
                            for v in edge.Vertices()
                        )
                        if not edge.Vertices():
                            raise ValueError("empty line boundary")
                radius = max(values)
        high = bb[axis + 3] + padding
        row = {"face": index, "surface_kind": face.geomType(), "face_bounds_mm": bb}
        if radius is not None:
            radius = float(radius) + padding
            origin = [0.0, 0.0, 0.0]
            origin[axis] = low
            for i, value in zip(transverse, centre):
                origin[i] = float(value)
            piece = cq.Solid.makeCylinder(radius, high - low, tuple(origin), tuple(direction))
            row.update(kind="cylinder", radius_mm=radius, centre_transverse_mm=list(centre))
        else:
            minimum = [v - padding for v in bb[:3]]
            maximum = [v + padding for v in bb[3:]]
            minimum[axis] = low
            piece = cq.Solid.makeBox(*(b - a for a, b in zip(minimum, maximum)), tuple(minimum))
            row.update(kind="box")
        if not piece.isValid() or len(piece.Solids()) != 1 or piece.Volume() <= 0:
            raise ValueError("invalid ray cover")
        name = f"face_{index}"
        pieces[name] = piece
        row.update(name=name, axial_span_mm=[low, high])
        rows.append(row)
    return pieces, {
        "axis": axis,
        "padding_mm": padding,
        "source_face_count": len(shape.Faces()),
        "all_solids_infinite_point_outside": True,
        "all_boundary_faces": rows,
        "shape_modified": False,
    }


def axial_boss_cover(shape, axis, seat, centre, radius):
    """Cover a case behind a plane plus a coaxial circular protrusion.

    For any material above the plane, the positive-axis ray must exit through
    an above-plane boundary. Bounding every such face radially bounds that
    material too. Unsupported surfaces fail closed. The body below the plane
    is covered by the source AABB. Touching is allowed; this is not a fit margin.
    ``centre`` contains the two coordinates perpendicular to the positive axis.
    """
    if axis not in (0, 1, 2) or not shape.isValid() or not _solid_only(shape):
        raise ValueError("valid solid material and Cartesian axis required")
    if len(centre) != 2 or not np.isfinite([seat, radius, *centre]).all() or radius <= 0:
        raise ValueError("finite positive envelope dimensions required")
    transverse = [i for i in range(3) if i != axis]
    target = np.asarray(centre)
    epsilon = 1e-7

    def radial(point):
        return float(np.linalg.norm(np.asarray(point)[transverse] - target))

    def aligned(direction):
        if abs(direction.Coord()[axis]) < 1 - 1e-10:
            raise ValueError("non-axial analytic surface")

    faces, case_max, radial_max = [], [], radius
    for index, face in enumerate(shape.Faces()):
        bb = bounds(face)
        if bb[axis + 3] <= seat + epsilon:
            case_max.append(bb[axis + 3])
            faces.append({"face": index, "region": "case", "bbox_mm": bb})
            continue
        surface = BRepAdaptor_Surface(face.wrapped)
        kind = face.geomType()
        if kind == "CYLINDER":
            cylinder = surface.Cylinder()
            aligned(cylinder.Axis().Direction())
            maximum = radial(cylinder.Location().Coord()) + cylinder.Radius()
        elif kind == "CONE":
            cone = surface.Cone()
            aligned(cone.Axis().Direction())
            apex = cone.Apex().Coord()
            maximum = radial(apex) + max(abs(bb[k] - apex[axis]) for k in (axis, axis + 3)) * abs(
                math.tan(cone.SemiAngle())
            )
        elif kind == "PLANE":
            aligned(surface.Plane().Axis().Direction())
            values = []
            for edge in face.Edges():
                curve = BRepAdaptor_Curve(edge.wrapped)
                if edge.geomType() == "CIRCLE":
                    circle = curve.Circle()
                    aligned(circle.Axis().Direction())
                    values.append(radial(circle.Location().Coord()) + circle.Radius())
                elif edge.geomType() == "LINE" and edge.Vertices():
                    values.extend(radial(v.toTuple()) for v in edge.Vertices())
                else:
                    raise ValueError("unsupported cap boundary")
            if not values:
                raise ValueError("empty cap boundary")
            maximum = max(values)
        else:
            raise ValueError(f"unsupported protruding surface: {kind}")
        if not math.isfinite(maximum) or maximum > radius + epsilon:
            raise ValueError("boundary extends beyond declared boss radius")
        radial_max = max(radial_max, maximum)
        faces.append(
            {
                "face": index,
                "region": "boss",
                "kind": kind,
                "radial_upper_bound_mm": maximum,
                "bbox_mm": bb,
            }
        )
    if not case_max or not any(f["region"] == "boss" for f in faces):
        raise ValueError("both body and protrusion must be present")
    box = bounds(shape)
    plane = max(case_max)
    high = box[3:]
    high[axis] = plane
    dimensions = [high[i] - box[i] for i in range(3)]
    if min(dimensions) <= 0 or box[axis + 3] <= plane:
        raise ValueError("degenerate envelope")
    base = [0.0, 0.0, 0.0]
    base[axis] = plane
    for i, value in zip(transverse, centre):
        base[i] = value
    direction = [0, 0, 0]
    direction[axis] = 1
    cover = {
        "case": cq.Solid.makeBox(*dimensions, tuple(box[:3])),
        "boss": cq.Solid.makeCylinder(
            radial_max, box[axis + 3] - plane, tuple(base), tuple(direction)
        ),
    }
    return cover, {
        "all_boundary_faces": faces,
        "source_face_count": len(shape.Faces()),
        "case_plane_mm": plane,
        "boss_radius_mm": radial_max,
        "axis": axis,
        "centre_transverse_mm": list(centre),
        "shape_modified": False,
    }


def bounded_contact(fastener, allowed_region, cover):
    """Prove any possible overlap is confined to an explicitly allowed region.

    The caller must establish the region from actual mating geometry. This does
    not itself approve a thread form, fit, allowable torque or material strength.
    """
    for s in (fastener, allowed_region):
        if not s.isValid() or not _solid_only(s):
            raise ValueError("valid solids required")
        if (
            abs(s.cut(s.copy()).Volume()) > 1e-4
            or abs(s.intersect(s.copy()).Volume() - s.Volume()) > 1e-4
        ):
            raise ValueError("unreliable allowed-region Boolean")
    inside = fastener.intersect(allowed_region)
    outside = fastener.cut(allowed_region)
    if (
        not inside.isValid()
        or not outside.isValid()
        or inside.Volume() <= 0
        or outside.Volume() <= 0
    ):
        raise ValueError("both engaged and external fastener material required")
    if abs(inside.Volume() + outside.Volume() - fastener.Volume()) > 1e-4:
        raise ValueError("contact region does not partition fastener material")
    check = inspect_components(cq.Compound.makeCompound(list(cover.values())), outside)
    return {
        "outside_allowed_region_clear": check["status"] == "PASS",
        "outside_region_check": check,
        "engaged_envelope_volume_mm3": inside.Volume(),
        "outside_envelope_volume_mm3": outside.Volume(),
        "actual_thread_approved": False,
        "physical_fastener_verified": False,
    }
