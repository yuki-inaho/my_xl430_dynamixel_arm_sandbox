"""Static-fit and sweep checks for the printed HN11 M2 replacement.

Compares the regenerated rotor/cap against a saved arm pose.  It does not model
threads, bearing life, loads or tolerance stacks; those stay unqualified.
Pre-existing source overlaps are reported separately from new-design
interference.

The validator can target a different assembly than the reference that produced
the replacement part.  ``--assembly`` selects the checked arm and
``--reference-assembly`` the assembly whose occurrence transform maps the new
part into the checked arm (defaults to ``--assembly``).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_SurfaceType

_HERE = Path(__file__).resolve()
_STUDY = _HERE.parent
_CADRE_ROOT = _HERE.parents[2]
_REPO = _HERE.parents[4]
sys.path.insert(0, str(_STUDY))
sys.path.insert(0, str(_STUDY / "parts"))
sys.path.insert(0, str(_CADRE_ROOT / "studies" / "follower_geometry_revision" / "source"))

from assembly_io import read_step  # noqa: E402
import hn11_m2_idler as model  # noqa: E402

DEFAULT_ASSEMBLY = _REPO / "hardware" / "follower" / "step" / "arm.step"
DEFAULT_OUT = _CADRE_ROOT / "outputs" / "prototypes" / "hn11_m2_idler_fit"
VOLUME_TOL_MM3 = 1e-6
ROTOR_VOLUME_MM3 = 672.764
CAP_VOLUME_MM3 = 207.156
SCREW_VOLUMES_MM3 = (29.649, 39.291)
IDLER_VOLUME_TOL = 0.5
LINK_NAME_HINTS = ("connector", "Base", "P0")


def _bbox_close(a, b, tol=1e-4):
    for attr in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"):
        if abs(getattr(a, attr) - getattr(b, attr)) > tol:
            return False
    return True


def _place_to(shape, src_loc, tgt_row):
    order_a = tgt_row.loc * src_loc.inverse
    order_b = src_loc.inverse * tgt_row.loc
    for loc in (order_a, order_b):
        placed = shape.moved(loc)
        if _bbox_close(placed.BoundingBox(), tgt_row.world.BoundingBox()):
            return placed, loc
    raise RuntimeError(f"could not match placement for {tgt_row.path}")


def _axis_from_bounds(box):
    dims = [box.xlen, box.ylen, box.zlen]
    axis = dims.index(min(dims))
    direction = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)][axis]
    point = ((box.xmin + box.xmax) / 2.0, (box.ymin + box.ymax) / 2.0,
             (box.zmin + box.zmax) / 2.0)
    return cq.Vector(*point), cq.Vector(*direction)


def _bbox_expand(box, margin):
    return (box.xmin - margin, box.xmax + margin, box.ymin - margin,
            box.ymax + margin, box.zmin - margin, box.zmax + margin)


def _bbox_overlap_tuple(box, other):
    return (box.xmin <= other.xmax and other.xmin <= box.xmax
            and box.ymin <= other.ymax and other.ymin <= box.ymax
            and box.zmin <= other.zmax and other.zmin <= box.zmax)


def _find_by_volume(rows, volume, tol=IDLER_VOLUME_TOL):
    return [r for r in rows if abs(r.world.Volume() - volume) <= tol]


def _nearest_cap(cap_rows, rotor_row):
    center = rotor_row.world.BoundingBox().center
    return min(cap_rows, key=lambda r: (r.world.BoundingBox().center - center).Length)


def _instance_rows(rows, rotor_row, margin=14.0):
    box = rotor_row.world.BoundingBox()
    replaced = set()
    volumes = (ROTOR_VOLUME_MM3, CAP_VOLUME_MM3, *SCREW_VOLUMES_MM3)
    for row in rows:
        if not _bbox_overlap_tuple(box, row.world.BoundingBox()):
            continue
        if any(abs(row.world.Volume() - v) <= IDLER_VOLUME_TOL for v in volumes):
            replaced.add(row.index)
    return replaced


def _intersections(shape, rows, exclude=()):
    hits = []
    box = shape.BoundingBox()
    for row in rows:
        if row.index in exclude:
            continue
        if not _bbox_overlap_tuple(box, row.world.BoundingBox()):
            continue
        volume = float(shape.intersect(row.world).Volume())
        if volume > VOLUME_TOL_MM3:
            hits.append({"index": row.index, "path": row.path,
                         "intersection_mm3": round(volume, 6)})
    return hits


def _coaxial_features(shape, origin, direction, rmin=0.4, rmax=12.0, radial_max=14.0):
    """Cylindrical faces parallel to the joint axis, with radial offset and span."""
    rows = []
    d0 = (direction.x, direction.y, direction.z)

    def dot(a, b):
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    for face in shape.Faces():
        surface = BRepAdaptor_Surface(face.wrapped)
        if surface.GetType() != GeomAbs_SurfaceType.GeomAbs_Cylinder:
            continue
        cylinder = surface.Cylinder()
        radius = float(cylinder.Radius())
        if not rmin < radius < rmax:
            continue
        axis_dir = cylinder.Axis().Direction()
        d = (axis_dir.X(), axis_dir.Y(), axis_dir.Z())
        if abs(abs(dot(d, d0)) - 1.0) > 1e-4:
            continue
        point = cylinder.Axis().Location()
        q = (point.X() - origin.x, point.Y() - origin.y, point.Z() - origin.z)
        t = dot(q, d0)
        radial = (q[0] - t * d0[0], q[1] - t * d0[1], q[2] - t * d0[2])
        radial_offset = dot(radial, radial) ** 0.5
        if radial_offset > radial_max:
            continue
        box = face.BoundingBox()
        ts = [dot((corner[0] - origin.x, corner[1] - origin.y, corner[2] - origin.z), d0)
              for corner in ((box.xmin, box.ymin, box.zmin), (box.xmax, box.ymax, box.zmax))]
        ref = cq.Vector(0, 0, 1) if abs(d0[2]) < 0.9 else cq.Vector(1, 0, 0)
        e1 = direction.cross(ref).normalized()
        e2 = direction.cross(e1).normalized()
        radial_vec = cq.Vector(*radial)
        angle = math.degrees(math.atan2(radial_vec.dot(e2), radial_vec.dot(e1))) % 360.0
        rows.append({
            "diameter_mm": round(2.0 * radius, 4),
            "radial_mm": round(radial_offset, 4),
            "t_min_mm": round(min(ts), 4),
            "t_max_mm": round(max(ts), 4),
            "axis_pt": [point.X(), point.Y(), point.Z()],
            "angle_deg": round(angle, 4),
        })
    groups: dict[tuple, list[float]] = {}
    for row in rows:
        key = (row["diameter_mm"], row["radial_mm"], row["t_min_mm"], row["t_max_mm"])
        groups.setdefault(key, []).append(row["angle_deg"])
    features = []
    for (diameter, radial, t_min, t_max), angles in groups.items():
        clusters: list[list[float]] = []
        for angle in sorted(angles):
            for cluster in clusters:
                gap = abs(angle - cluster[0]) % 360.0
                if min(gap, 360.0 - gap) < 35.0:
                    cluster.append(angle)
                    break
            else:
                clusters.append([angle])
        features.append({
            "diameter_mm": diameter,
            "radial_mm": radial,
            "t_min_mm": t_min,
            "t_max_mm": t_max,
            "count": len(clusters),
            "angles_deg": [round(sum(c) / len(c), 1) for c in clusters],
        })
    return sorted(features, key=lambda f: (f["radial_mm"], f["diameter_mm"], f["t_min_mm"]))


def _rotate_in_place(shape, axis_pt, axis_dir, angle_deg):
    """Rotate about the line through ``axis_pt`` with direction ``axis_dir``.

    cadquery's ``Location(point, axis, angle)`` rotates about the axis through
    the origin and then translates by ``point``, so the pivot correction must be
    applied explicitly.  At 0 degrees the shape must not move.
    """
    rotation = cq.Location(cq.Vector(0, 0, 0), axis_dir, angle_deg)
    pivot = _xform_point(rotation, axis_pt)
    return shape.moved(rotation).moved(cq.Location(axis_pt - pivot))


def _is_link(row):
    name = row.name or ""
    return any(hint in name for hint in LINK_NAME_HINTS)


def _overlaps_with_margin(box, other, margin):
    return (box.xmin - margin <= other.xmax and other.xmin <= box.xmax + margin
            and box.ymin - margin <= other.ymax and other.ymin <= box.ymax + margin
            and box.zmin - margin <= other.zmax and other.zmin <= box.zmax + margin)


def _apply_locations(shape, locations):
    placed = shape
    for loc in locations:
        placed = placed.moved(loc)
    return placed


def _signed_axis(shape, axis_pt, axis_dir):
    """Orient the axis so it points from the outer face toward the counterbores."""
    features = _coaxial_features(shape, axis_pt, axis_dir, rmin=0.4, rmax=3.0,
                                 radial_max=9.0)
    counterbores = [f for f in features
                    if abs(f["diameter_mm"] - 4.5) < 0.2 and abs(f["radial_mm"] - 8.0) < 0.3]
    holes = [f for f in features
             if abs(f["diameter_mm"] - 2.0) < 0.2 and abs(f["radial_mm"] - 8.0) < 0.3]
    if counterbores and holes:
        t_cb = sum((f["t_min_mm"] + f["t_max_mm"]) / 2.0 for f in counterbores) / len(counterbores)
        t_hole = sum((f["t_min_mm"] + f["t_max_mm"]) / 2.0 for f in holes) / len(holes)
        if t_hole > t_cb:
            return axis_dir * -1.0
        return axis_dir
    # The replacement part has the 0-degree counterbores filled, so use its
    # blind insert seats instead: the seat opening is on the outer face.
    seats = [f for f in features
             if abs(f["diameter_mm"] - 2.5) < 0.1 and abs(f["radial_mm"] - 8.0) < 0.3
             and (f["t_max_mm"] - f["t_min_mm"]) > 2.5]
    if seats:
        t_mid = sum((f["t_min_mm"] + f["t_max_mm"]) / 2.0 for f in seats) / len(seats)
        if t_mid > 0.1:
            return axis_dir * -1.0
    return axis_dir


def _family_angle(shape, axis_pt, axis_dir, diameter, tolerance=0.15):
    """Angle of the first PCD16 family member with the given diameter."""
    features = _coaxial_features(shape, axis_pt, axis_dir,
                                 rmin=diameter / 2.0 - tolerance,
                                 rmax=diameter / 2.0 + tolerance,
                                 radial_max=9.0)
    families = [f for f in features if abs(f["radial_mm"] - 8.0) < 0.3]
    return families[0]["angles_deg"][0] if families else None


def _alignment_angle(shape, axis_pt, axis_dir):
    """Angle of the 45-degree Ø1.7 family, present on both source and replacement."""
    return _family_angle(shape, axis_pt, axis_dir, 1.7)


def _seat_angle(shape, axis_pt, axis_dir):
    """Angle of the replacement's 0-degree Ø2.5 insert-seat family."""
    return _family_angle(shape, axis_pt, axis_dir, 2.5)


def _xform_point(location, point):
    return cq.Vertex.makeVertex(*point.toTuple()).moved(location).Center()


def _geometric_locations(shape, tgt_row):
    """Axis/hole aligned placement for assemblies whose local frames differ.

    cadquery's ``Location(point, axis, angle)`` rotates about the axis through
    the origin and then translates by ``point``; the rotation must therefore be
    composed explicitly to pivot on the part axis.
    """
    src_pt, src_dir = _axis_from_bounds(shape.BoundingBox())
    src_dir = _signed_axis(shape, src_pt, src_dir)
    tgt_pt, tgt_dir = _axis_from_bounds(tgt_row.world.BoundingBox())
    tgt_dir = _signed_axis(tgt_row.world, tgt_pt, tgt_dir)
    locations = []
    cosine = max(-1.0, min(1.0, src_dir.dot(tgt_dir)))
    if cosine > 1.0 - 1e-6:
        pass
    elif cosine < -1.0 + 1e-6:
        helper = cq.Vector(1, 0, 0) if abs(src_dir.x) < 0.9 else cq.Vector(0, 1, 0)
        locations.append(cq.Location(cq.Vector(0, 0, 0),
                                     src_dir.cross(helper).normalized(), 180.0))
    else:
        axis = src_dir.cross(tgt_dir).normalized()
        locations.append(cq.Location(cq.Vector(0, 0, 0), axis,
                                     math.degrees(math.acos(cosine))))
    pivot = _xform_point(locations[0], src_pt) if locations else src_pt
    mid = _apply_locations(shape, locations)
    src_angle = _alignment_angle(mid, pivot, tgt_dir)
    tgt_angle = _alignment_angle(tgt_row.world, tgt_pt, tgt_dir)
    if src_angle is not None and tgt_angle is not None:
        delta = (tgt_angle - src_angle) % 90.0
        rotation = cq.Location(cq.Vector(0, 0, 0), tgt_dir, delta)
        rotated_pivot = _xform_point(rotation, pivot)
        locations.append(rotation)
        locations.append(cq.Location(pivot - rotated_pivot))
    locations.append(cq.Location(tgt_pt - pivot))
    placed = _apply_locations(shape, locations)
    if not _bbox_close(placed.BoundingBox(), tgt_row.world.BoundingBox(), tol=0.3):
        raise RuntimeError(f"geometric placement failed for {tgt_row.path}")
    return locations


def _instance_locations(shape, src_row, tgt_row):
    try:
        _, loc = _place_to(shape, src_row.loc, tgt_row)
        return [loc]
    except RuntimeError:
        return _geometric_locations(shape, tgt_row)


def validate(assembly_path: Path = DEFAULT_ASSEMBLY, sweep_step_deg: int = 5,
             reference_assembly: Path | None = None) -> dict:
    if sweep_step_deg <= 0 or 360 % sweep_step_deg:
        raise ValueError("sweep step must divide 360")
    _, _, rows = read_step(assembly_path)
    ref_path = Path(reference_assembly) if reference_assembly else Path(assembly_path)
    if ref_path == Path(assembly_path):
        ref_rows = rows
    else:
        _, _, ref_rows = read_step(ref_path)

    new_rotor = model.make_rotor()
    new_cap = model.make_cap()
    src_rotor_row = _find_by_volume(ref_rows, ROTOR_VOLUME_MM3)
    src_cap_row = _find_by_volume(ref_rows, CAP_VOLUME_MM3)
    rotor_rows = _find_by_volume(rows, ROTOR_VOLUME_MM3)
    cap_rows = _find_by_volume(rows, CAP_VOLUME_MM3)
    if not src_rotor_row or not src_cap_row or not rotor_rows or not cap_rows:
        raise RuntimeError("could not locate source idler occurrences by volume")

    report = {"assembly": str(assembly_path), "reference_assembly": str(ref_path),
              "instances": [], "status": "pass"}
    for tgt_row in rotor_rows:
        locations = _instance_locations(new_rotor, src_rotor_row[0], tgt_row)
        placed_rotor = _apply_locations(new_rotor, locations)
        cap_row = _nearest_cap(cap_rows, tgt_row)
        placed_cap = _apply_locations(new_cap, locations)
        cap_placement_matched = _bbox_close(
            placed_cap.BoundingBox(), cap_row.world.BoundingBox(), tol=0.3
        )
        replaced = _instance_rows(rows, tgt_row)
        retained = [r for r in rows if r.index not in replaced]
        rotor_hits = _intersections(placed_rotor, retained)
        cap_hits = _intersections(placed_cap, retained)
        src_rotor_hits = _intersections(tgt_row.world, retained)
        src_cap_hits = _intersections(cap_row.world, retained)

        def _delta(hits, source_hits):
            source = {h["index"]: h["intersection_mm3"] for h in source_hits}
            rows_out = []
            for hit in hits:
                delta = hit["intersection_mm3"] - source.get(hit["index"], 0.0)
                if delta > 1e-4:
                    rows_out.append({**hit, "source_mm3": source.get(hit["index"], 0.0),
                                     "new_interference_mm3": round(delta, 6)})
            return rows_out

        new_interference = _delta(rotor_hits, src_rotor_hits) + _delta(cap_hits, src_cap_hits)

        axis_point, axis_dir = _axis_from_bounds(tgt_row.world.BoundingBox())
        link_rows = [r for r in retained if _is_link(r)
                     and _overlaps_with_margin(tgt_row.world.BoundingBox(),
                                               r.world.BoundingBox(), 25.0)]
        link_features = []
        for link in link_rows:
            features = _coaxial_features(link.world, axis_point, axis_dir)
            if features:
                link_features.append({"path": link.path, "features": features})
        # Relative-motion checks.  Both plausible kinematic relations are
        # evaluated and always compared against the source part at the same
        # angle, so the source onset overlap is never reported as new
        # interference:
        #   (a) the link rotates while the rotor stays with the motor,
        #   (b) the rotor and cap rotate with the link while motor/base stay.
        sweep_new = 0.0
        for step in range(0, 360, sweep_step_deg):
            angle = float(step)
            for link in link_rows:
                moved = _rotate_in_place(link.world, axis_point, axis_dir, angle)
                new_volume = (float(placed_rotor.intersect(moved).Volume())
                              if _bbox_overlap_tuple(placed_rotor.BoundingBox(), moved.BoundingBox())
                              else 0.0)
                src_volume = (float(tgt_row.world.intersect(moved).Volume())
                              if _bbox_overlap_tuple(tgt_row.world.BoundingBox(), moved.BoundingBox())
                              else 0.0)
                sweep_new = max(sweep_new, new_volume - src_volume)
        static_obstacles = [r for r in retained if not _is_link(r)]
        # The rotor and cap are bodies of revolution about the joint axis, so
        # hypothesis (b) is sampled more coarsely than the link sweep.
        b_step = 30 if sweep_step_deg < 30 else sweep_step_deg
        for step in range(0, 360, b_step):
            angle = float(step)
            moved_rotor = _rotate_in_place(placed_rotor, axis_point, axis_dir, angle)
            moved_cap = _rotate_in_place(placed_cap, axis_point, axis_dir, angle)
            new_hits = (_intersections(moved_rotor, static_obstacles)
                        + _intersections(moved_cap, static_obstacles))
            src_hits = (_intersections(_rotate_in_place(tgt_row.world, axis_point, axis_dir, angle),
                                       static_obstacles)
                        + _intersections(_rotate_in_place(cap_row.world, axis_point, axis_dir, angle),
                                         static_obstacles))
            source = {h["index"]: h["intersection_mm3"] for h in src_hits}
            for hit in new_hits:
                delta = hit["intersection_mm3"] - source.get(hit["index"], 0.0)
                sweep_new = max(sweep_new, delta)
        sweep_max = max(0.0, sweep_new)
        shifted = placed_rotor.moved(
            cq.Location(cq.Vector(*[c * 2.0 for c in axis_dir.toTuple()]))
        )
        negative_hits = _intersections(shifted, retained)

        # Placement verification: face orientation and hole-family register.
        signed_dir = _signed_axis(tgt_row.world, axis_point, axis_dir)
        placed_seats = [f for f in _coaxial_features(placed_rotor, axis_point, signed_dir,
                                                     rmin=1.2, rmax=1.3, radial_max=9.0)
                        if abs(f["radial_mm"] - 8.0) < 0.3]
        target_counterbores = [f for f in _coaxial_features(tgt_row.world, axis_point, signed_dir,
                                                            rmin=2.2, rmax=2.3, radial_max=9.0)
                               if abs(f["radial_mm"] - 8.0) < 0.3]
        seat_mid = (sum((f["t_min_mm"] + f["t_max_mm"]) / 2.0 for f in placed_seats)
                    / len(placed_seats)) if placed_seats else None
        counterbore_mid = (sum((f["t_min_mm"] + f["t_max_mm"]) / 2.0 for f in target_counterbores)
                           / len(target_counterbores)) if target_counterbores else None
        face_alignment_ok = bool(seat_mid is not None and counterbore_mid is not None
                                 and seat_mid < 0.0 < counterbore_mid)
        placed_seat_angle = _seat_angle(placed_rotor, axis_point, signed_dir)
        target_counterbore_angle = _family_angle(tgt_row.world, axis_point, signed_dir, 4.5)
        register_residual_deg = (
            None if placed_seat_angle is None or target_counterbore_angle is None
            else round((placed_seat_angle - target_counterbore_angle) % 90.0, 3)
        )
        register_ok = register_residual_deg is not None and (
            min(register_residual_deg, 90.0 - register_residual_deg) < 2.0
        )

        # Idler-side screw pattern: Ø2.4 clearance holes near the rotor plane.
        screw_features = [feat for lf in link_features for feat in lf["features"]
                          if abs(feat["diameter_mm"] - 2.4) < 0.1
                          and abs(feat["radial_mm"] - 8.0) < 0.3
                          and feat["t_max_mm"] <= 1.0]
        screw_analysis = None
        if screw_features:
            span = max(f["t_max_mm"] - f["t_min_mm"] for f in screw_features)
            needed = span + 3.0  # link plate + insert length
            candidate = next((c for c in (5.0, 6.0, 7.0) if c >= needed - 1e-9), None)
            screw_analysis = {
                "link_plate_span_mm": round(span, 3),
                "required_length_mm": round(needed, 3),
                "candidate_length_mm": candidate,
                "engagement_mm": None if candidate is None else round(candidate - span, 3),
                "seat_depth_mm": 3.0,
                "seat_floor_mm": 0.5,
                "note": ("engagement is capped by the 3.0 mm seat depth; confirm screw "
                         "stock and the head seat before ordering"),
            }

        entry = {
            "rotor_row": tgt_row.index,
            "path": tgt_row.path,
            "placement_mode": "location" if len(locations) == 1 else "geometric",
            "cap_placement_matched": cap_placement_matched,
            "axis_point_mm": [round(v, 3) for v in axis_point.toTuple()],
            "axis_dir": [round(v, 3) for v in axis_dir.toTuple()],
            "rotor_intersections": rotor_hits,
            "cap_intersections": cap_hits,
            "source_rotor_intersections": src_rotor_hits,
            "source_cap_intersections": src_cap_hits,
            "new_interference": new_interference,
            "face_alignment_ok": face_alignment_ok,
            "register_residual_deg": register_residual_deg,
            "link_rows": [r.path for r in link_rows],
            "link_features": link_features,
            "idler_mount_status": ("idler_side_screw_pattern" if screw_features
                                   else "no_idler_side_screw_pattern"),
            "screw_analysis": screw_analysis,
            "link_sweep_max_mm3": round(sweep_max, 6),
            "negative_control_detected": bool(negative_hits),
        }
        if (new_interference or sweep_max > VOLUME_TOL_MM3 or not negative_hits
                or not face_alignment_ok or not register_ok):
            report["status"] = "fail"
        if (not cap_placement_matched or not link_rows or not screw_features):
            report["status"] = "incomplete"
        report["instances"].append(entry)
    report["scope"] = (
        "saved arm pose; sampled link sweep; source onset overlaps reported "
        "separately from new-design interference; no threads, no tolerance "
        "stack, no load or life analysis"
    )
    return report


def export(out: Path, report: dict) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    name = "hn11_m2_idler_fit_report.json"
    if "r3" in report["assembly"].lower():
        name = "hn11_m2_idler_fit_report_r3.json"
    path = out / name
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return {"fit_report": str(path.resolve())}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assembly", type=Path, default=DEFAULT_ASSEMBLY)
    parser.add_argument("--reference-assembly", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--sweep-step-deg", type=int, default=5)
    parser.add_argument("--fail-on-mismatch", action="store_true")
    args = parser.parse_args(argv)
    report = validate(args.assembly, args.sweep_step_deg, args.reference_assembly)
    report["artifacts"] = export(args.out, report)
    print(json.dumps({k: v for k, v in report.items() if k != "artifacts"},
                     indent=2, ensure_ascii=False))
    return 2 if args.fail_on_mismatch and report["status"] != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
