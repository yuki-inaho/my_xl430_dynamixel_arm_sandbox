"""Generic, file-driven probes. Domain-agnostic: nothing about servos here.

Three tiers, increasing cost / increasing fidelity:
  1. step_text  - parse STEP as ISO-10303 text (no CAD kernel)
  2. stl_mesh   - mesh stats via trimesh
  3. brep       - B-rep faces / cylinders via CadQuery+OCP (optional dependency)

A `KeywordPolicy` (category -> regex) is *injected*, so the same probe serves
any domain. The XL430 study supplies a Dynamixel policy; nothing is hard-coded.
"""
from __future__ import annotations
import re
import math
from pathlib import Path
from dataclasses import dataclass

from .geometry import classify_screw, DEFAULT_SCREW_BANDS

# ---------------------------------------------------------------- tier 1: text

# ISO 10303-21 permits whitespace between tokens; tolerate it for portability
# across STEP exporters (Fusion is tight, others are not).
_PRODUCT = re.compile(r"PRODUCT\s*\(\s*'([^']*)'")
_CYL_RADIUS = re.compile(
    r"CYLINDRICAL_SURFACE\s*\(\s*'[^']*'\s*,\s*#?\d+\s*,\s*([0-9.eE+-]+)\s*\)")


@dataclass(frozen=True)
class KeywordPolicy:
    """Maps a category label to a regex; injected into text probing/classification."""
    patterns: dict[str, str]

    def compiled(self) -> dict[str, re.Pattern]:
        return {k: re.compile(v, re.I) for k, v in self.patterns.items()}


def step_text_probe(path: Path, policy: KeywordPolicy | None = None) -> dict:
    text = Path(path).read_text(errors="replace")
    products = sorted(set(_PRODUCT.findall(text)))
    radii: dict[float, int] = {}
    for r in _CYL_RADIUS.findall(text):
        v = round(float(r), 3)
        radii[v] = radii.get(v, 0) + 1
    keywords = {}
    if policy:
        keywords = {k: len(rx.findall(text)) for k, rx in policy.compiled().items()}
    return {
        "file": str(path),
        "name": Path(path).stem,
        "products": products,
        "keywords": keywords,
        "counts": {
            "advanced_face": text.count("ADVANCED_FACE"),
            "cylindrical_surface": text.count("CYLINDRICAL_SURFACE"),
            "closed_shell": text.count("CLOSED_SHELL"),
            "circle": len(re.findall(r"\bCIRCLE\(", text)),
        },
        "cylinder_radii": sorted(radii.items()),
    }


# ---------------------------------------------------------------- tier 2: mesh

def stl_geometry_probe(path: Path) -> dict:
    import trimesh
    mesh = trimesh.load(path, force="mesh")
    ext = mesh.bounding_box.extents
    return {
        "file": str(path),
        "name": Path(path).stem,
        "bbox_mm": [round(float(x), 3) for x in ext],
        "volume_mm3": round(float(mesh.volume), 2) if mesh.is_volume else None,
        "area_mm2": round(float(mesh.area), 2),
        "triangles": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "centroid_mm": [round(float(x), 3) for x in mesh.centroid],
    }


# ---------------------------------------------------------------- tier 3: brep

def brep_available() -> bool:
    try:
        import cadquery  # noqa: F401
        from OCP.BRepAdaptor import BRepAdaptor_Surface  # noqa: F401
        return True
    except Exception:
        return False


def _round3(v) -> list[float]:
    return [round(float(x), 3) for x in v]


def _round6(v) -> list[float]:
    return [round(float(x), 6) for x in v]


def _canonical_dir(d, tol: float = 1e-6) -> tuple[float, ...]:
    """B-rep cylinder axis sign is arbitrary; canonicalize so ±dir compare equal."""
    dd = list(d)
    for x in dd:
        if abs(x) > tol:
            if x < 0:
                dd = [-c for c in dd]
            break
    return tuple(round(c, 3) for c in dd)


def _perp_foot(pt, u) -> tuple[float, ...]:
    """Component of pt perpendicular to unit axis u — identifies the axis *line*
    independent of where along it a (possibly split) face sits."""
    dot = sum(p * c for p, c in zip(pt, u))
    return tuple(round(p - dot * c, 1) for p, c in zip(pt, u))


def group_cylinder_holes(cylinders: list[dict],
                         screw_bands=DEFAULT_SCREW_BANDS) -> list[dict]:
    """Group raw cylindrical *faces* into distinct *axis lines*, then into families
    by (radius, canonical axis direction).

    Reports the only invariant we can extract reliably:
      - `axes`  : distinct axis lines (radius + direction + perpendicular foot),
                  collapsing the arbitrary B-rep sign and any face splitting.
      - `faces` : raw cylindrical-face tally (transparency).

    This legacy grouping includes convex outside profiles as well as concave
    bores. Neither face counts nor axis-line counts establish a physical hole
    count, blind/through status, or thread function. Inspect surface sense and
    axial extents, then confirm openings/material on the solid.
    """
    axes: dict[tuple, dict] = {}
    for c in cylinders:
        u = _canonical_dir(c["axis_dir"])
        foot = _perp_foot(c["axis_pt"], u)
        key = (c["radius"], u, foot)
        # center = canonical foot of the axis line (frame-stable: independent of
        # which wall / split face we hit), so two probes of the same pattern match.
        a = axes.setdefault(key, {"radius": c["radius"], "axis_dir": list(u),
                                  "center": list(foot), "faces": 0})
        a["faces"] += 1
    families: dict[tuple, list] = {}
    for a in axes.values():
        families.setdefault((a["radius"], tuple(a["axis_dir"])), []).append(a)
    return [
        {"radius": r, "diameter": round(2 * r, 3),
         "screw": classify_screw(2 * r, screw_bands), "axis_dir": list(u),
         "axes": len(group), "faces": sum(a["faces"] for a in group),
         "centers": [a["center"] for a in group]}
        for (r, u), group in sorted(families.items(), key=lambda kv: -len(kv[1]))
    ]


def _open_solids(path: Path):
    import cadquery as cq
    return cq.importers.importStep(str(path)).solids().vals()


def _bbox_minmax(solids) -> dict:
    bb = solids[0].BoundingBox()                 # bbox over ALL solids (wp.val() = first only)
    for s in solids[1:]:
        bb.add(s.BoundingBox())
    return {"xmin": round(bb.xmin, 3), "xmax": round(bb.xmax, 3),
            "ymin": round(bb.ymin, 3), "ymax": round(bb.ymax, 3),
            "zmin": round(bb.zmin, 3), "zmax": round(bb.zmax, 3),
            "xlen": round(bb.xlen, 3), "ylen": round(bb.ylen, 3), "zlen": round(bb.zlen, 3)}


def cylinder_surface_sense(face) -> str:
    """Classify a cylindrical face using its oriented material normal.

    Assumes an outward-oriented solid. A topology orientation flag alone is
    insufficient because the surface parameterization can have either handedness.
    This says nothing about a feature's mounting or threaded function.
    """
    import cadquery as cq
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    surface = BRepAdaptor_Surface(face.wrapped)
    if surface.GetType() != GeomAbs_Cylinder:
        raise ValueError("cylinder_surface_sense requires a cylindrical face")
    uv = ((surface.FirstUParameter() + surface.LastUParameter()) / 2,
          (surface.FirstVParameter() + surface.LastVParameter()) / 2)
    if not all(math.isfinite(v) for v in uv):
        return "unknown"
    cylinder = surface.Cylinder()
    p, d = cylinder.Location(), cylinder.Axis().Direction()
    sample = surface.Value(*uv)
    point = cq.Vector(sample.X(), sample.Y(), sample.Z())
    axis = cq.Vector(d.X(), d.Y(), d.Z())
    delta = point - cq.Vector(p.X(), p.Y(), p.Z())
    radial = delta - axis.multiply(delta.dot(axis))
    if radial.Length <= 0:
        return "unknown"
    dot = face.normalAt(point).dot(radial.normalized())
    if not math.isfinite(dot):
        return "unknown"
    if dot > 1 - 1e-7:
        return "convex"
    if dot < -1 + 1e-7:
        return "concave"
    return "unknown"


def _raw_cylinders(solids, screw_bands) -> tuple[list[dict], int, int]:
    """Per-face cylinders with ABSOLUTE axis points (placement-truth, not collapsed)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    cylinders, planes, faces = [], 0, 0
    for solid in solids:
        for face in solid.Faces():
            faces += 1
            ad = BRepAdaptor_Surface(face.wrapped)
            t = ad.GetType()
            if t == GeomAbs_Plane:
                planes += 1
            elif t == GeomAbs_Cylinder:
                cyl = ad.Cylinder(); loc = cyl.Axis().Location(); d = cyl.Axis().Direction()
                r = float(cyl.Radius())
                sense = cylinder_surface_sense(face)
                direction = (d.X(), d.Y(), d.Z())
                if next((value for value in direction if abs(value) > 1e-6), 1) < 0:
                    direction = tuple(-value for value in direction)
                mid_u = (ad.FirstUParameter() + ad.LastUParameter()) / 2
                axial = []
                for v in (ad.FirstVParameter(), ad.LastVParameter()):
                    p = ad.Value(mid_u, v)
                    axial.append(sum(a * b for a, b in zip(
                        (p.X(), p.Y(), p.Z()), direction)))
                cylinders.append({
                    "radius": round(r, 3), "diameter": round(2 * r, 3),
                    "axis_dir": _round3((d.X(), d.Y(), d.Z())),
                    "axis_pt": _round3((loc.X(), loc.Y(), loc.Z())),
                    "screw": classify_screw(2 * r, screw_bands),
                    "surface_sense": sense,
                    "axial_range_mm": _round3(sorted(axial)),
                    "angular_span_deg": round(math.degrees(
                        ad.LastUParameter() - ad.FirstUParameter()), 3),
                })
    return cylinders, faces, planes


def _family_views(cylinders, screw_bands) -> dict:
    return {
        # Kept for existing consumers; it is not a list of verified holes.
        "hole_families": group_cylinder_holes(cylinders, screw_bands),
        "hole_families_semantics": "legacy_all_cylindrical_surfaces",
        "bore_families": group_cylinder_holes(
            [c for c in cylinders if c["surface_sense"] == "concave"], screw_bands),
        "outer_cylinder_families": group_cylinder_holes(
            [c for c in cylinders if c["surface_sense"] == "convex"], screw_bands),
    }


def brep_probe(path: Path, screw_bands=DEFAULT_SCREW_BANDS) -> dict:
    if not brep_available():
        return {"file": str(path), "name": Path(path).stem, "available": False}
    solids = _open_solids(path)
    if not solids:                       # surface-only STEP — degrade, don't crash
        return {"file": str(path), "name": Path(path).stem, "available": True,
                "solids": 0, "faces": 0, "planes": 0, "cylindrical_faces": 0,
                "bbox_mm": None, **_family_views([], screw_bands)}
    cylinders, faces, planes = _raw_cylinders(solids, screw_bands)
    bb = _bbox_minmax(solids)
    return {
        "file": str(path), "name": Path(path).stem, "available": True,
        "solids": len(solids), "faces": faces, "planes": planes,
        "cylindrical_faces": len(cylinders),
        "bbox_mm": [bb["xlen"], bb["ylen"], bb["zlen"]],
        **_family_views(cylinders, screw_bands),
    }


def cylinder_faces(path: Path, screw_bands=DEFAULT_SCREW_BANDS) -> dict:
    """Inspect cylindrical face sense, axial spans, and grouped axis lines.

    axis_pt is a reference point on the unbounded cylinder axis, not a face
    center. axial_range_mm locates the trimmed face along the canonical unit
    axis relative to the global origin; angular_span_deg exposes partial arcs.
    Legacy hole_families includes both inside and outside surfaces.
    """
    if not brep_available():
        return {"file": str(path), "name": Path(path).stem, "available": False}
    solids = _open_solids(path)
    if not solids:
        return {"file": str(path), "name": Path(path).stem, "available": True,
                "solids": 0, "bbox": None, "cylinders": [],
                **_family_views([], screw_bands)}
    cylinders, faces, planes = _raw_cylinders(solids, screw_bands)
    return {
        "file": str(path), "name": Path(path).stem, "available": True,
        "solids": len(solids), "faces": faces, "planes": planes,
        "bbox": _bbox_minmax(solids),
        "cylinders": sorted(cylinders, key=lambda c: (c["diameter"], c["axis_pt"])),
        **_family_views(cylinders, screw_bands),
    }


def _curve_type_name(curve_type) -> str:
    from OCP.GeomAbs import (
        GeomAbs_Line, GeomAbs_Circle, GeomAbs_Ellipse, GeomAbs_BSplineCurve,
        GeomAbs_BezierCurve,
    )
    return {
        GeomAbs_Line: "line",
        GeomAbs_Circle: "circle",
        GeomAbs_Ellipse: "ellipse",
        GeomAbs_BSplineCurve: "bspline",
        GeomAbs_BezierCurve: "bezier",
    }.get(curve_type, str(int(curve_type)))


def _surface_type_name(surface_type) -> str:
    from OCP.GeomAbs import (
        GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere,
        GeomAbs_Torus, GeomAbs_BSplineSurface, GeomAbs_BezierSurface,
    )
    return {
        GeomAbs_Plane: "plane",
        GeomAbs_Cylinder: "cylinder",
        GeomAbs_Cone: "cone",
        GeomAbs_Sphere: "sphere",
        GeomAbs_Torus: "torus",
        GeomAbs_BSplineSurface: "bspline_surface",
        GeomAbs_BezierSurface: "bezier_surface",
    }.get(surface_type, str(int(surface_type)))


def edge_records(path: Path, indexes: list[int] | None = None,
                 include_faces: bool = True) -> dict:
    """List STEP B-rep edges with stable-enough topology metadata.

    Use this after a viewer or measurement tool reports selected edge indexes,
    lengths, or endpoints. Edge indexes are kernel traversal indexes, so they are
    best treated as a bridge to confirm against length/coordinate evidence rather
    than as a persistent cross-export identifier.
    """
    if not brep_available():
        return {"file": str(path), "name": Path(path).stem, "available": False}
    import cadquery as cq
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Cylinder
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp, TopExp_Explorer
    from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
    from OCP.TopoDS import TopoDS

    wanted = set(indexes) if indexes is not None else None
    shape = cq.importers.importStep(str(path)).val().wrapped
    face_map = None
    if include_faces:
        face_map = TopTools_IndexedDataMapOfShapeListOfShape()
        TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, face_map)

    records = []
    exp = TopExp_Explorer(shape, TopAbs_EDGE)
    idx = 0
    while exp.More():
        edge = TopoDS.Edge_s(exp.Current())
        if wanted is None or idx in wanted:
            curve = BRepAdaptor_Curve(edge)
            props = GProp_GProps()
            BRepGProp.LinearProperties_s(edge, props)
            first, last = curve.FirstParameter(), curve.LastParameter()
            rec = {
                "index": idx,
                "length": round(float(props.Mass()), 9),
                "curve_type": _curve_type_name(curve.GetType()),
                "start": _round6((curve.Value(first).X(), curve.Value(first).Y(),
                                  curve.Value(first).Z())),
                "end": _round6((curve.Value(last).X(), curve.Value(last).Y(),
                                curve.Value(last).Z())),
            }
            if curve.GetType() == GeomAbs_Circle:
                circle = curve.Circle()
                loc = circle.Location()
                rec["circle"] = {
                    "radius": round(float(circle.Radius()), 6),
                    "center": _round6((loc.X(), loc.Y(), loc.Z())),
                }
            if include_faces and face_map is not None and face_map.Contains(edge):
                faces = []
                for face_shape in face_map.FindFromKey(edge):
                    surface = BRepAdaptor_Surface(TopoDS.Face_s(face_shape))
                    item = {"surface_type": _surface_type_name(surface.GetType())}
                    if surface.GetType() == GeomAbs_Cylinder:
                        cyl = surface.Cylinder()
                        loc = cyl.Axis().Location()
                        direction = cyl.Axis().Direction()
                        item["cylinder"] = {
                            "radius": round(float(cyl.Radius()), 6),
                            "axis_pt": _round6((loc.X(), loc.Y(), loc.Z())),
                            "axis_dir": _round6((direction.X(), direction.Y(),
                                                 direction.Z())),
                        }
                    faces.append(item)
                rec["adjacent_faces"] = faces
            records.append(rec)
        idx += 1
        exp.Next()

    return {
        "file": str(path),
        "name": Path(path).stem,
        "available": True,
        "edge_count": idx,
        "edges": records,
    }


def match_edge_lengths(path: Path, lengths: list[float], tolerance: float = 0.05,
                       limit: int = 5, include_faces: bool = True) -> dict:
    """Find nearest B-rep edges for measured lengths.

    This is useful when an external viewer reports selected edge lengths but its
    edge indexes do not directly correspond to the standalone STEP's traversal
    order. Always combine matches with coordinates and curve/surface type.
    """
    rec = edge_records(path, include_faces=include_faces)
    if not rec.get("available"):
        return rec
    edges = rec["edges"]
    queries = []
    for q in lengths:
        ranked = sorted(edges, key=lambda e: abs(float(e["length"]) - q))[:limit]
        queries.append({
            "length": q,
            "tolerance": tolerance,
            "matches": [
                {**m, "delta": round(abs(float(m["length"]) - q), 9),
                 "within_tolerance": abs(float(m["length"]) - q) <= tolerance}
                for m in ranked
            ],
        })
    return {
        "file": rec["file"],
        "name": rec["name"],
        "available": True,
        "edge_count": rec["edge_count"],
        "queries": queries,
    }
