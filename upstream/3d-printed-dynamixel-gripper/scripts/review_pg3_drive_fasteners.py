"""Bound PG3 mounting-screw contact to actual receiver bores and inspect seats."""

import argparse
import json
import math
from pathlib import Path

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface

from gripper_design.interface_envelopes import axial_boss_cover, bounded_contact
from gripper_design.pg2 import _solid_only, digest
from gripper_design.pg3_installation import _outer_planar_seat
from scripts.assembly_io import bounds, read_step
from scripts.review_pg3_pivot_stacks import pick, planar_contact, profiles


def all_profiles(shape):
    if not shape.isValid() or not _solid_only(shape):
        raise ValueError("valid solid-only receiver required")
    return [
        {**row, "solid_index": i}
        for i, solid in enumerate(shape.Solids())
        for row in profiles(solid)
    ]


def countersink_contact(frame, screw, centre):
    def cones(shape):
        result = []
        for index, face in enumerate(shape.Faces()):
            if face.geomType() != "CONE":
                continue
            cone = BRepAdaptor_Surface(face.wrapped).Cone()
            if abs(cone.Axis().Direction().X()) < 1 - 1e-8:
                continue
            apex = cone.Apex().Coord()
            result.append((math.dist(apex[1:], centre), index, face, cone))
        if not result:
            raise ValueError("missing actual countersink cone")
        result.sort(key=lambda r: r[0])
        if len(result) > 1 and abs(result[0][0] - result[1][0]) < 1e-6:
            raise ValueError("ambiguous countersink cone")
        return result[0]

    _, fi, ff, fc = cones(frame)
    _, si, sf, sc = cones(screw)
    for face in (ff, sf):
        common = face.intersect(face.copy())
        if not common.isValid() or abs(common.Area() - face.Area()) > 1e-5:
            raise ValueError("countersink face self-control failed")
    common = ff.intersect(sf)
    if not common.isValid() or not math.isfinite(common.Area()):
        raise ValueError("invalid countersink common face")
    apex_error = math.dist(fc.Apex().Coord(), sc.Apex().Coord())
    angle = abs(fc.SemiAngle())
    spans = [bounds(face) for face in (ff, sf)]
    low, high = max(b[0] for b in spans), min(b[3] for b in spans)
    radii = sorted(abs(x - fc.Apex().X()) * math.tan(angle) for x in (low, high))
    area = math.pi * (radii[1] ** 2 - radii[0] ** 2) / math.sin(angle) if high > low else 0
    vertices = common.Vertices()
    normal_dot = None
    if common.Area() > 0 and vertices:
        point = vertices[0].Center()
        normal_dot = ff.normalAt(point).dot(sf.normalAt(point))
    passed = (
        apex_error < 1e-6
        and abs(angle - abs(sc.SemiAngle())) < 1e-8
        and area > 0
        and abs(common.Area() - area) < 1e-5
        and normal_dot is not None
        and normal_dot < -1 + 1e-8
    )
    return {
        "frame_face": fi,
        "screw_face": si,
        "apex_error_mm": apex_error,
        "half_angle_radians": angle,
        "expected_overlapping_frustum_area_mm2": area,
        "contact_area_mm2": common.Area(),
        "contact_normal_dot": normal_dot,
        "nominal_seating_pass": passed,
        "PLA_bearing_strength_verified": False,
    }


def inspect_receivers(shapes):
    horn, case = shapes["PG3_XL430_horn"], shapes["PG3_XL430_fixed"]
    hp = [
        r for r in all_profiles(horn) if r["sense"] == "concave" and abs(r["radius_mm"] - 1) < 1e-6
    ]
    cp = [
        r
        for r in all_profiles(case)
        if r["sense"] == "concave" and abs(r["radius_mm"] - 1.05) < 1e-6
    ]
    if len(hp) != 4 or len(cp) != 2:
        raise ValueError("expected four horn bores and two front case pilots")
    horn_seat = _outer_planar_seat(horn, 0, 1, [r["axis_yz_mm"] for r in hp])
    case_seat = _outer_planar_seat(case, 0, 1, [r["axis_yz_mm"] for r in cp])
    horn_cover, cover_evidence = axial_boss_cover(
        horn, 0, horn_seat["coordinate_mm"], (234.9, 164.6), 4
    )
    bb = bounds(case)
    case_cover = {
        "all_case_material_AABB": cq.Solid.makeBox(
            *(bb[i + 3] - bb[i] for i in range(3)), tuple(bb[:3])
        )
    }
    result = {}
    for name in [
        *(f"PG3_horn_bolt_{i}" for i in range(4)),
        "PG3_case_tapper_-11",
        "PG3_case_tapper_11",
    ]:
        is_horn = "horn_bolt" in name
        radius = 1 if is_horn else 1.3
        fastener = shapes[name]
        shank = pick(profiles(fastener), radius, "convex")
        centre = shank["axis_yz_mm"]
        bore = pick(hp if is_horn else cp, 1 if is_horn else 1.05, "concave", centre)
        plane = (horn_seat if is_horn else case_seat)["coordinate_mm"]
        bottom, bore_top = bore["span_x_mm"]
        tip, shank_top = shank["span_x_mm"]
        maximum_depth = 3.5 if is_horn else 4
        limit = max(bottom, plane - maximum_depth)
        axis_error = math.dist(centre, bore["axis_yz_mm"])
        row = {
            "receiver": "PG3_XL430_horn" if is_horn else "PG3_XL430_fixed",
            "actual_bore": bore,
            "actual_shank": shank,
            "seat_x_mm": plane,
            "axis_error_mm": axis_error,
            "insertion_from_seat_mm": plane - tip,
            "supplier_max_depth_mm": maximum_depth,
            "tip_to_depth_limit_mm": tip - limit,
            "overlap_with_cylindrical_bore_span_mm": max(
                0, min(shank_top, bore_top) - max(tip, bottom)
            ),
            "actual_thread_engagement_verified": False,
            "thread_strength_verified": False,
        }
        # Receiver-derived region stays put when a negative-control screw moves.
        y, z = bore["axis_yz_mm"]
        region = cq.Solid.makeCylinder(radius, plane - limit, (limit, y, z), (1, 0, 0))
        try:
            row.update(bounded_contact(fastener, region, horn_cover if is_horn else case_cover))
            if is_horn:
                head = pick(profiles(fastener), 1.9, "convex")
                contact = planar_contact(shapes["PG3_crank"], fastener, head["span_x_mm"][0])
                expected = math.pi * (1.9**2 - 1.15**2)
                row["head_crank_contact"] = contact
                seated = abs(contact["common_area_mm2"] - expected) < 1e-5
            else:
                row["countersink"] = countersink_contact(shapes["PG3_frame"], fastener, centre)
                seated = row["countersink"]["nominal_seating_pass"]
            row["nominal_receiver_geometry_pass"] = (
                axis_error < 1e-6
                and 0 < plane - tip <= maximum_depth
                and tip - limit >= 0.5 - 1e-6
                and row["outside_allowed_region_clear"]
                and seated
            )
        except ValueError as exc:
            row.update(nominal_receiver_geometry_pass=False, verification_error=str(exc))
        result[name] = row
    return {
        "fasteners": result,
        "horn_boundary_cover": cover_evidence,
        "case_material_solid_count": len(case.Solids()),
        "nominal_receiver_geometry_pass": all(
            r["nominal_receiver_geometry_pass"] for r in result.values()
        ),
        "basis": "actual bores/seats plus supplier depth ceilings; no minimum strength inferred",
        "source_drawing": "references/robotis-xl430-new-20180324/XL-430_new.pdf",
        "drawing_sha256": digest(Path("references/robotis-xl430-new-20180324/XL-430_new.pdf")),
        "actual_fasteners_verified": False,
        "installation_approved": False,
    }


def run(assembly, out):
    if out.exists():
        raise FileExistsError(out)
    rows = read_step(assembly)[2]
    shapes = {r.name: r.world for r in rows}
    if len(rows) != len(shapes):
        raise ValueError("ambiguous occurrences")
    report = inspect_receivers(shapes)
    report.update(assembly_sha256=digest(assembly), checker_sha256=digest(Path(__file__)))
    report["dependency_sha256"] = {
        p: digest(Path(p))
        for p in (
            "gripper_design/interface_envelopes.py",
            "gripper_design/pg3_installation.py",
            "scripts/review_pg3_pivot_stacks.py",
            "scripts/review_pg3_components.py",
            "scripts/review_pg3.py",
        )
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                n: {
                    k: r[k]
                    for k in (
                        "nominal_receiver_geometry_pass",
                        "insertion_from_seat_mm",
                        "tip_to_depth_limit_mm",
                    )
                }
                for n, r in report["fasteners"].items()
            },
            indent=2,
        )
    )
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assembly", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.assembly, args.out))
