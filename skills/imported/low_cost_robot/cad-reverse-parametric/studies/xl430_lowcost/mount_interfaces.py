"""Read actual horn/link interfaces in each motor's local XYZ frame.

This survey covers four-hole horn/idler interfaces, not case fasteners, thread
engagement, bearing preload, structural capacity or assembly approval.
The +Z motor axis is explicit; shapes are transformed, not inferred from names.
Dimensions identify surveyed features, not approved replacement dimensions.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common

from cable_routing import load_source
from assembly_io import bounds
from cadre.probes import cylinder_surface_sense

TOL = 1e-5  # Existing CAD length tolerance; not an FDM manufacturing tolerance.


def _solid(shape):
    if not shape.isValid() or not shape.Solids() or any(s.Volume() <= 0 for s in shape.Solids()):
        raise ValueError("interface needs valid outward-oriented solid geometry")


def extract_bores(shape, *, seat_z, diameter, radial_window, rim_search_mm=.25):
    """Concave Z bores near a surveyed seat, keeping unrounded axes and spans.

    rim_search_mm admits a small entry chamfer. It is a feature-search window,
    never a seat-alignment tolerance. A cylinder is not proof of a screw thread.
    """
    _solid(shape)
    holes = []
    for index, face in enumerate(shape.Faces()):
        if face.geomType() != "CYLINDER":
            continue
        surface = BRepAdaptor_Surface(face.wrapped)
        cylinder = surface.Cylinder()
        d = cylinder.Axis().Direction()
        if abs(d.Z()) < 1 - 1e-10 or abs(2 * cylinder.Radius() - diameter) > TOL:
            continue
        p = cylinder.Location()
        if cylinder_surface_sense(face) != "concave":
            continue
        # Intersect the axis line with z=0; its stored location is not a rim.
        xy = [p.X() - p.Z() * d.X() / d.Z(), p.Y() - p.Z() * d.Y() / d.Z()]
        if not radial_window[0] <= math.hypot(*xy) <= radial_window[1]:
            continue
        bb = bounds(face)
        span = [bb[2], bb[5]]
        if seat_z < span[0] - rim_search_mm or seat_z > span[1] + rim_search_mm:
            continue
        previous = next((h for h in holes if math.dist(xy, h["xy_mm"]) <= TOL), None)
        if previous is None:
            holes.append({"xy_mm": xy, "diameter_mm": 2 * cylinder.Radius(),
                          "z_range_mm": span, "faces": [index]})
        else:
            previous["faces"].append(index)
            previous["z_range_mm"] = [min(previous["z_range_mm"][0], span[0]),
                                      max(previous["z_range_mm"][1], span[1])]
    return sorted(holes, key=lambda h: tuple(h["xy_mm"]))


def match_pattern(motor_holes, link_holes):
    """Minimax bijection for a small, explicit four-hole mounting pattern."""
    if len(motor_holes) != 4 or len(link_holes) != 4:
        raise ValueError("four unique holes required on each side")
    for holes in (motor_holes, link_holes):
        pts = [h["xy_mm"] for h in holes]
        if any(len(p) != 2 or not all(math.isfinite(x) for x in p) for p in pts):
            raise ValueError("finite XY coordinates required")
        if any(math.dist(a, b) <= TOL for a, b in itertools.combinations(pts, 2)):
            raise ValueError("duplicate hole axis in pattern")
    candidates = []
    for order in itertools.permutations(range(4)):
        distances = [math.dist(motor_holes[i]["xy_mm"], link_holes[j]["xy_mm"])
                     for i, j in enumerate(order)]
        candidates.append((max(distances), sum(distances), order, distances))
    maximum, _, order, distances = min(candidates)
    return {"max_offset_mm": maximum,
            "pairs": [{"motor_index": i, "link_index": j, "offset_mm": distances[i]}
                      for i, j in enumerate(order)]}


def _seat_faces(shape, z):
    return [(i, f) for i, f in enumerate(shape.Faces()) if f.geomType() == "PLANE"
            and abs(abs(f.normalAt().z) - 1) < 1e-10 and abs(f.Center().z - z) <= TOL]


def _common_area(a, b):
    op = BRepAlgoAPI_Common(a.wrapped, b.wrapped)
    op.Build()
    if not op.IsDone() or op.Shape().IsNull():
        raise RuntimeError("seat contact boolean did not complete")
    shape = cq.Shape.cast(op.Shape())
    area = sum(f.Area() for f in shape.Faces())
    if not shape.isValid() or not math.isfinite(area) or area < 0:
        raise RuntimeError("invalid seat contact boolean")
    return area


def inspect_interface(motor, link, *, motor_z, link_z, side,
                      motor_diameter, link_diameter, radial_window):
    _solid(motor)
    _solid(link)
    if side not in (-1, 1) or not all(math.isfinite(v) for v in (motor_z, link_z)):
        raise ValueError("finite seat coordinates and side +/-1 required")
    a = extract_bores(motor, seat_z=motor_z, diameter=motor_diameter, radial_window=radial_window)
    b = extract_bores(link, seat_z=link_z, diameter=link_diameter, radial_window=radial_window)
    motor_planes, link_planes = _seat_faces(motor, motor_z), _seat_faces(link, link_z)
    facing_a = [(i, f) for i, f in motor_planes if f.normalAt().z * side > 0]
    facing_b = [(i, f) for i, f in link_planes if f.normalAt().z * side < 0]
    opposing = bool(facing_a and facing_b)
    actual_motor_z = sum(f.Center().z for _, f in motor_planes) / len(motor_planes) if motor_planes else None
    actual_link_z = sum(f.Center().z for _, f in link_planes) / len(link_planes) if link_planes else None
    offset = actual_link_z - actual_motor_z if actual_motor_z is not None and actual_link_z is not None else None
    area = 0.
    if offset is not None and abs(offset) <= TOL and opposing:
        area = sum(_common_area(f, g) for _, f in facing_a for _, g in facing_b)
    pattern = match_pattern(a, b) if len(a) == len(b) == 4 else None
    known = bool(pattern is not None and motor_planes and link_planes)
    reasons = []
    if not known:
        reasons.append("missing_or_ambiguous_four_hole_pattern_or_seat")
    if offset is not None and abs(offset) > TOL:
        reasons.append("axial_seat_offset")
    if pattern is not None and pattern["max_offset_mm"] > TOL:
        reasons.append("in_plane_hole_offset")
    if motor_planes and link_planes and not opposing:
        reasons.append("nonopposing_seat_normals")
    if known and abs(offset) <= TOL and opposing and area <= 0:
        reasons.append("no_trimmed_face_contact")
    status = "unknown" if not known else ("fail" if reasons else "pass")
    def planes(rows):
        return [{"face": i, "center_mm": f.Center().toTuple(), "normal": f.normalAt().toTuple(),
                 "area_mm2": f.Area()} for i, f in rows]
    return {"geometry_status": status, "reasons": reasons, "motor_holes": a, "link_holes": b,
            "pattern": pattern, "seat_offset_mm": offset, "opposing_normals": opposing,
            "actual_motor_seat_z_mm": actual_motor_z, "actual_link_seat_z_mm": actual_link_z,
            "motor_seat_faces": planes(motor_planes), "link_seat_faces": planes(link_planes),
            "contact_area_mm2": area, "engineering_approved": False,
            "thread_engagement_status": "unknown", "case_fastening_status": "not_checked",
            "strength_status": "unknown"}


# Actual surveyed inner seats in each motor's local frame. Script J tags are NOT
# physical servo IDs. Missing idler entries intentionally describe one-sided links.
INTERFACES = (
    ("base", "KEEP_000_DC11_A01_DUMMY_1", "KEEP_007_DC11_A01_IDLER_DUMMY_1",
     "KEEP_059_rotation_connector_1", 2.4, 19., None),
    ("shoulder", "KEEP_060_DC11_A01_DUMMY_1", "KEEP_067_DC11_A01_IDLER_DUMMY_1",
     "KEEP_058_connector_1", 2.4, 19., -19.),
    ("elbow", "J4_XL430_00_DC11_A01_DUMMY_1", "J4_XL430_07_DC11_A01_IDLER_DUMMY_1",
     "KEEP_160_connector_1", 1.8, 6.5, -22.5),
    ("extension", "J6_XL430_00_DC11_A01_DUMMY_1", "J6_XL430_07_DC11_A01_IDLER_DUMMY_1",
     "KEEP_057_shoulder_rotation_1", 2., 7., -22.5),
    ("wrist", "J3_XL430_00_DC11_A01_DUMMY_1", "J3_XL430_07_DC11_A01_IDLER_DUMMY_1",
     "KEEP_117_static_side_1", 2.3, 6.5, None),
    ("gripper", "J5_GRIPPER_XL430_00_DC11_A01_DUMMY_1", "J5_GRIPPER_XL430_07_DC11_A01_IDLER_DUMMY_1",
     "KEEP_116_moving_side_1", 1.8, 7., -22.5),
)


def inspect_run(run):
    import cadre.probes
    source, digest, _, names, _ = load_source(run)
    if {n for n in names if n.endswith("_DC11_A01_DUMMY_1")} != {r[1] for r in INTERFACES}:
        raise ValueError("motor inventory differs from the six surveyed occurrences")
    records = []
    for role, body_name, idler_name, link_name, diameter, front, back in INTERFACES:
        body = names[body_name]
        link = names[link_name].world.moved(body.loc.inverse)
        for label, z, sign in (("output", front, 1), ("idler", back, -1)):
            if z is None:
                continue
            motor = body.shape if sign == 1 else names[idler_name].world.moved(body.loc.inverse)
            result = inspect_interface(motor, link, motor_z=19. * sign, link_z=z, side=sign,
                                       motor_diameter=2., link_diameter=diameter,
                                       radial_window=(5., 9.))
            records.append({"role": role, "interface": label, "motor": body_name,
                            "mating_occurrence": body_name if sign == 1 else idler_name,
                            "link": link_name, "original_xl430": role in ("base", "shoulder"),
                            "motor_local_to_world": body.loc.toTuple(), **result})
    return {"source": str(source), "source_sha256": digest,
            "manifest_sha256": hashlib.sha256((run / "replacement_manifest.json").read_bytes()).hexdigest(),
            "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "probe_sha256": hashlib.sha256(Path(cadre.probes.__file__).read_bytes()).hexdigest(),
            "status": "unaccepted_interface_survey", "engineering_approved": False,
            "scope": "six output and four idler four-hole interfaces; no case/threads/strength approval",
            "length_tolerance_mm": TOL, "interfaces": records,
            "summary": {s: sum(r["geometry_status"] == s for r in records) for s in ("pass", "fail", "unknown")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = inspect_run(args.run)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"]))
    return 2 if report["summary"]["fail"] or report["summary"]["unknown"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
