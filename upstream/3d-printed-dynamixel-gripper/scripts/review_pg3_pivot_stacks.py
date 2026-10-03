"""Measure nominal printed-shoulder pivot stacks from saved assembly B-rep."""

import argparse
import json
import math
from pathlib import Path

from cadre.probes import cylinder_surface_sense
from OCP.BRepAdaptor import BRepAdaptor_Surface

from gripper_design.pg2 import digest
from scripts.assembly_io import bounds, read_step


def profiles(shape):
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError("one valid solid required")
    result = []
    for i, face in enumerate(shape.Faces()):
        if face.geomType() != "CYLINDER":
            continue
        cylinder = BRepAdaptor_Surface(face.wrapped).Cylinder()
        if abs(cylinder.Axis().Direction().X()) < 1 - 1e-8:
            continue
        bb = bounds(face)
        result.append(
            {
                "face": i,
                "radius_mm": cylinder.Radius(),
                "sense": cylinder_surface_sense(face),
                "axis_yz_mm": list(cylinder.Location().Coord()[1:]),
                "span_x_mm": [bb[0], bb[3]],
            }
        )
    return result


def pick(rows, radius, sense, centre=None):
    found = [r for r in rows if abs(r["radius_mm"] - radius) < 1e-6 and r["sense"] == sense]
    if not found:
        raise ValueError(f"missing {sense} cylindrical interface R{radius}")
    if centre is not None:
        found.sort(key=lambda r: math.dist(r["axis_yz_mm"], centre))
        if (
            len(found) > 1
            and abs(
                math.dist(found[0]["axis_yz_mm"], centre)
                - math.dist(found[1]["axis_yz_mm"], centre)
            )
            < 1e-6
        ):
            raise ValueError("ambiguous pivot interface")
    elif len(found) != 1:
        raise ValueError("ambiguous fastener axis")
    return found[0]


def planar_contact(first, second, coordinate):
    def faces(shape):
        found = []
        for i, face in enumerate(shape.Faces()):
            bb = bounds(face)
            if face.geomType() != "PLANE" or max(abs(bb[k] - coordinate) for k in (0, 3)) > 1e-6:
                continue
            control = face.intersect(face.copy())
            if not control.isValid() or abs(control.Area() - face.Area()) > 1e-5:
                raise ValueError("unreliable planar contact control")
            found.append((i, face))
        return found

    a, b = faces(first), faces(second)
    area = 0.0
    for _, fa in a:
        for _, fb in b:
            common = fa.intersect(fb)
            if not common.isValid() or not math.isfinite(common.Area()):
                raise ValueError("invalid planar contact intersection")
            area += common.Area()
    return {
        "plane_x_mm": coordinate,
        "first_faces": [i for i, _ in a],
        "second_faces": [i for i, _ in b],
        "first_area_mm2": sum(f.Area() for _, f in a),
        "second_area_mm2": sum(f.Area() for _, f in b),
        "common_area_mm2": area,
    }


def inspect_pivots(shapes):
    result = {}
    for side in ("R", "L"):
        for kind in ("drive", "carriage"):
            prefix = f"PG3_pivot_{kind}_{side}"
            host_name = "PG3_crank" if kind == "drive" else f"PG3_carriage_{side}"
            names = {"host": host_name, "link": f"PG3_link_{side}"}
            names.update({n: f"{prefix}_{n}" for n in ("washer", "bolt", "nut")})
            p = {n: profiles(shapes[s]) for n, s in names.items()}
            shank = pick(p["bolt"], 1, "convex")
            centre = shank["axis_yz_mm"]
            head = pick(p["bolt"], 1.9, "convex", centre)
            shoulder = pick(p["host"], 2.5, "convex", centre)
            host_bore = pick(p["host"], 1.15, "concave", centre)
            link = pick(p["link"], 2.7, "concave", centre)
            washer = pick(p["washer"], 3.5, "convex", centre)
            washer_bore = pick(p["washer"], 1.1, "concave", centre)
            nut = pick(p["nut"], 1, "concave", centre)
            interfaces = {
                "shank": shank,
                "head": head,
                "shoulder": shoulder,
                "host_bore": host_bore,
                "link": link,
                "washer": washer,
                "washer_bore": washer_bore,
                "nut": nut,
            }
            axis_error = max(math.dist(r["axis_yz_mm"], centre) for r in interfaces.values())
            slo, shi = shoulder["span_x_mm"]
            llo, lhi = link["span_x_mm"]
            wlo, whi = washer["span_x_mm"]
            tip, seat = shank["span_x_mm"]
            nlo, nhi = nut["span_x_mm"]
            contacts = {
                "nut_host": planar_contact(shapes[host_name], shapes[names["nut"]], nhi),
                "washer_shoulder": planar_contact(shapes[host_name], shapes[names["washer"]], wlo),
                "head_washer": planar_contact(shapes[names["washer"]], shapes[names["bolt"]], seat),
            }
            expected = {
                "nut_host": contacts["nut_host"]["second_area_mm2"]
                - math.pi * (host_bore["radius_mm"] ** 2 - nut["radius_mm"] ** 2),
                "washer_shoulder": math.pi
                * (shoulder["radius_mm"] ** 2 - host_bore["radius_mm"] ** 2),
                "head_washer": math.pi * (head["radius_mm"] ** 2 - washer_bore["radius_mm"] ** 2),
            }
            contacts_pass = all(
                expected[n] > 0 and abs(v["common_area_mm2"] - expected[n]) < 1e-5
                for n, v in contacts.items()
            )
            row = {
                "occurrences": names,
                "interfaces": interfaces,
                "planar_contacts": contacts,
                "expected_nominal_contact_area_mm2": expected,
                "axis_error_mm": axis_error,
                "rear_axial_gap_mm": llo - slo,
                "front_axial_gap_mm": wlo - lhi,
                "radial_gap_mm": link["radius_mm"] - shoulder["radius_mm"] - axis_error,
                "retaining_overlap_mm": washer["radius_mm"] - link["radius_mm"] - axis_error,
                "washer_shoulder_seat_gap_mm": wlo - shi,
                "bolt_washer_seat_gap_mm": seat - whi,
                "nut_nominal_full_span_mm": nhi - nlo,
                "bolt_tip_beyond_nut_mm": nlo - tip,
                "nominal_engaged_span_mm": max(0, min(seat, nhi) - max(tip, nlo)),
                "washer_thickness_mm": whi - wlo,
                "screw_underhead_length_mm": seat - tip,
            }
            row["nominal_pivot_geometry_pass"] = (
                axis_error < 1e-6
                and contacts_pass
                and abs(head["span_x_mm"][0] - seat) < 1e-6
                and row["rear_axial_gap_mm"] >= 0.3 - 1e-6
                and row["front_axial_gap_mm"] >= 0.3 - 1e-6
                and row["radial_gap_mm"] >= 0.2 - 1e-6
                and row["retaining_overlap_mm"] >= 0.8 - 1e-6
                and abs(row["washer_shoulder_seat_gap_mm"]) < 1e-6
                and abs(row["bolt_washer_seat_gap_mm"]) < 1e-6
                and row["nominal_engaged_span_mm"] >= 1.6 - 1e-6
                and row["bolt_tip_beyond_nut_mm"] >= 0.4 - 1e-6
                and abs(row["washer_thickness_mm"] - 0.5) < 1e-6
            )
            result[prefix] = row
    return {
        "pivots": result,
        "nominal_pivot_geometry_pass": all(
            r["nominal_pivot_geometry_pass"] for r in result.values()
        ),
        "basis": "C9 nominal clearances remeasured from actual cylindrical interfaces",
        "limits": [
            "not whole-body collision or continuous mechanism motion proof",
            "smooth nut bores do not prove actual threads or thread runout",
            "print tolerance, washer bending, shoulder compression and creep unverified",
            "nominal planar intersections are not loaded or printed contact measurements",
        ],
        "actual_fastener_verified": False,
        "physical_free_motion_verified": False,
        "installation_approved": False,
    }


def run(assembly, out):
    if out.exists():
        raise FileExistsError(out)
    rows = read_step(assembly)[2]
    shapes = {r.name: r.world for r in rows}
    if len(shapes) != len(rows):
        raise ValueError("ambiguous occurrence identity")
    report = inspect_pivots(shapes)
    report.update(assembly_sha256=digest(assembly), checker_sha256=digest(Path(__file__)))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                n: {
                    k: r[k]
                    for k in (
                        "nominal_pivot_geometry_pass",
                        "rear_axial_gap_mm",
                        "front_axial_gap_mm",
                        "radial_gap_mm",
                        "bolt_tip_beyond_nut_mm",
                    )
                }
                for n, r in report["pivots"].items()
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
