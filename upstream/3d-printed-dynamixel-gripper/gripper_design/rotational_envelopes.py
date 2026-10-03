"""Rotation-invariant material enclosures with analytically bounded trimmed arcs."""

import math

import cadquery as cq
import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Curve

from gripper_design.interface_envelopes import axial_ray_cover
from scripts.assembly_io import bounds


def curve_radial_bound(edge, axis, centre):
    """Bound the trimmed edge, including extrema between topological vertices.

    For a circle, choose the point on the target axis level with its centre.
    Distance to that point bounds distance to the axis, even for a tilted circle.
    Its square is constant + A*cos(t) + B*sin(t); endpoints and the in-range
    maximum stationary parameter therefore bound the entire arc, not samples.
    """
    if axis not in (0, 1, 2) or np.shape(centre) != (2,) or not np.isfinite(centre).all():
        raise ValueError("Cartesian axis and finite transverse centre required")
    transverse = [i for i in range(3) if i != axis]
    target = np.asarray(centre)
    if edge.geomType() == "LINE" and edge.Vertices():
        return max(
            float(np.linalg.norm(np.asarray(v.toTuple())[transverse] - target))
            for v in edge.Vertices()
        )
    if edge.geomType() != "CIRCLE":
        raise ValueError("unsupported trimmed curve")
    curve = BRepAdaptor_Curve(edge.wrapped)
    circle = curve.Circle()
    origin = np.asarray(circle.Location().Coord())
    reference = origin.copy()
    reference[transverse] = target
    offset = origin - reference
    u = np.asarray(circle.Position().XDirection().Coord())
    v = np.asarray(circle.Position().YDirection().Coord())
    maximum = math.atan2(float(offset @ v), float(offset @ u))
    low, high = curve.FirstParameter(), curve.LastParameter()
    if not all(math.isfinite(t) for t in (low, high)) or low > high:
        raise ValueError("finite ordered curve interval required")
    maximum += 2 * math.pi * math.ceil((low - maximum) / (2 * math.pi))
    candidates = [low, high]
    if low <= maximum <= high:
        candidates.append(maximum)
    result = max(
        float(np.linalg.norm(np.asarray(curve.Value(t).Coord()) - reference)) for t in candidates
    )
    if not math.isfinite(result):
        raise ValueError("nonfinite curve bound")
    return result


def rotational_cover(shape, axis, centre, radius):
    """Enclose the entire finite solid in a cylinder invariant under axial rotation.

    Reuse the all-face material-cover argument, refining only planar edge bounds.
    No Boolean with the supplied shape is used to prove containment. A declared
    cylinder that fails to contain the boundary is rejected, never shrunk to fit.
    """
    if np.shape(centre) != (2,) or not np.isfinite([*centre, radius]).all() or radius <= 0:
        raise ValueError("finite centre and positive radius required")
    covers, proof = axial_ray_cover(shape, axis)
    transverse = [i for i in range(3) if i != axis]
    rows = []
    for row, face in zip(proof["all_boundary_faces"], shape.Faces(), strict=True):
        if row["kind"] == "cylinder":
            coarse = math.dist(row["centre_transverse_mm"], centre) + row["radius_mm"]
        else:
            bb = bounds(covers[row["name"]])
            coarse = math.hypot(
                *(max(abs(bb[i] - c), abs(bb[i + 3] - c)) for i, c in zip(transverse, centre))
            )
        result = {
            "face": row["face"],
            "surface_kind": face.geomType(),
            "coarse_radius_bound_mm": coarse,
        }
        required = coarse
        if (
            face.geomType() == "PLANE"
            and face.Edges()
            and all(e.geomType() in ("LINE", "CIRCLE") for e in face.Edges())
        ):
            edge_bounds = [curve_radial_bound(e, axis, centre) for e in face.Edges()]
            refined = max(edge_bounds) + proof["padding_mm"]
            required = min(required, refined)
            result.update(
                trimmed_edge_radius_bounds_mm=edge_bounds, refined_radius_bound_mm=refined
            )
        result["radius_upper_bound_mm"] = required
        if required > radius:
            raise ValueError(
                f"face {row['face']} exceeds declared rotation radius: {required} > {radius}"
            )
        rows.append(result)
    bb = bounds(shape)
    low, high = bb[axis] - proof["padding_mm"], bb[axis + 3] + proof["padding_mm"]
    origin, direction = [0.0, 0.0, 0.0], [0, 0, 0]
    origin[axis], direction[axis] = low, 1
    for i, value in zip(transverse, centre):
        origin[i] = value
    cover = cq.Solid.makeCylinder(radius, high - low, tuple(origin), tuple(direction))
    return cover, {
        "axis": axis,
        "centre_transverse_mm": list(centre),
        "radius_mm": radius,
        "axial_span_mm": [low, high],
        "source_face_count": len(shape.Faces()),
        "faces": rows,
        "maximum_required_radius_mm": max(r["radius_upper_bound_mm"] for r in rows),
        "all_solids_infinite_point_outside": proof["all_solids_infinite_point_outside"],
        "source_boolean_used_as_containment_proof": False,
        "shape_modified": False,
    }
