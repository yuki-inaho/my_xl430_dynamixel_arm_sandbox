"""Screen explicit prewired M05 routes; assumed wires are not installation approval."""

import argparse
import json
import math
import shutil
from collections import Counter
from itertools import combinations
from pathlib import Path

import cadquery as cq

from gripper_design.pg2 import digest
from scripts.assembly_io import bounds, read_step
from scripts.probe_pg3_connector_access import corridors
from scripts.render_cad import render
from scripts.review_pg3 import inspect_pairs


def quarter_route(start, diameter, radius, end_y, axis, sign, end_coordinate):
    """Round wire: -Y straight, tangent circular bend, transverse straight.

    No fan-out, twist, elastic squeeze, helix, or spline-curvature approximation.
    Radius is centreline radius, not a manufacturer-approved bend allowance.
    """
    if (
        axis not in (0, 2)
        or sign not in (-1, 1)
        or len(start) != 3
        or not all(math.isfinite(v) for v in (*start, diameter, radius, end_y, end_coordinate))
        or diameter <= 0
        or radius <= diameter / 2
    ):
        raise ValueError("finite positive dimensions and transverse bend required")
    a = list(start)
    a[1] = end_y + radius
    mid = a.copy()
    mid[1] -= radius / math.sqrt(2)
    mid[axis] += sign * radius * (1 - 1 / math.sqrt(2))
    b = a.copy()
    b[1] = end_y
    b[axis] += sign * radius
    end = b.copy()
    end[axis] = end_coordinate
    if start[1] <= a[1] or sign * (end_coordinate - b[axis]) <= 0:
        raise ValueError("bend leaves no positive inlet or outlet straight")
    path = cq.Wire.assembleEdges(
        [
            cq.Edge.makeLine(tuple(start), tuple(a)),
            cq.Edge.makeThreePointArc(tuple(a), tuple(mid), tuple(b)),
            cq.Edge.makeLine(tuple(b), tuple(end)),
        ]
    )
    wire = (
        cq.Workplane(cq.Plane(origin=tuple(start), normal=(0, -1, 0)))
        .circle(diameter / 2)
        .sweep(path, isFrenet=True)
        .val()
    )
    if not wire.isValid() or len(wire.Solids()) != 1:
        raise ValueError("invalid swept wire")
    return wire, {
        "start_mm": list(start),
        "bend_start_mm": a,
        "bend_end_mm": b,
        "end_mm": end,
        "diameter_mm_assumed": diameter,
        "minimum_centreline_radius_mm": radius,
        "start_tangent": [0, -1, 0],
        "actual_wire_or_bend_allowance_verified": False,
    }


def terminal_centres(header):
    bb = bounds(header)
    tip = bb[4]
    centres = []
    for face in header.Faces():
        f = bounds(face)
        if face.geomType() != "PLANE" or abs(f[1] - tip) > 1e-5 or abs(f[4] - tip) > 1e-5:
            continue
        if abs(face.Area() - 0.64**2) > 1e-5:
            raise ValueError("unexpected terminal end face")
        centres.append([(f[i] + f[i + 3]) / 2 for i in range(3)])
    centres.sort(key=lambda p: p[2])
    if len(centres) != 3 or any(
        abs(centres[i + 1][2] - centres[i][2] - 2.5) > 1e-5 for i in range(2)
    ):
        raise ValueError("expected three 2.5 mm pitch terminal ends")
    return centres, tip - 3.2


def run(assembly, out, side_exit=False):
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out / "checker.py.txt")
    rows = read_step(assembly)[2]
    shapes = {r.name: r.world for r in rows}
    if len(shapes) != len(rows):
        raise ValueError("ambiguous occurrence names")
    corridors(shapes)  # Fixed-case-plane pose and header dimension guard.
    terminals = {}
    for port in (3, 4):
        points, pcb = terminal_centres(shapes[f"ARM_M05_ref{port:02d}"])
        terminals[port] = {"pin_ends_mm": points, "pcb_plane_y_mm": pcb}
    routes, assumptions, groups = {}, {}, {}
    directions = (
        ("left", 0, -1, -28),
        ("right", 0, 1, 28),
        ("down", 2, -1, 145),
        ("up", 2, 1, 208),
    )
    if side_exit:
        directions = (("side_outward", 0, 1, 16),)
    for radius in (1.2,) if side_exit else (2.0, 4.0, 6.0):
        for label, axis, sign, target in directions:
            group = f"R{radius:g}_{label}"
            groups[group] = []
            for port, item in terminals.items():
                for index, point in enumerate(item["pin_ends_mm"]):
                    # 8.1 catalog mated height +0.6 projection allowance is an
                    # explicit diagnostic estimate, not measured wire exit.
                    start = [point[0], item["pcb_plane_y_mm"] - 8.7, point[2]]
                    name = f"WIRE_{group}_port{port}_{index}"
                    outward = 1 if port == 3 else -1
                    wire, info = quarter_route(
                        start,
                        1.9,
                        radius,
                        150.6 if side_exit else 146.15,
                        axis,
                        outward if side_exit else sign,
                        (16 if port == 3 else -16.4) if side_exit else target,
                    )
                    routes[name], assumptions[name] = wire, info
                    groups[group].append(name)
    checks = inspect_pairs(
        shapes | routes,
        [(a, b) for a in routes for b in shapes]
        + [(a, b) for names in groups.values() for a, b in combinations(names, 2)],
    )
    summary = {}
    for group, names in groups.items():
        selected = [r for r in checks["pairs"] if r["a"] in names]
        summary[group] = {
            "counts": dict(Counter(r["status"] for r in selected)),
            "nonpass": [r for r in selected if r["status"] != "PASS"],
            "route_approved": False,
        }
    report = {
        "assembly_sha256": digest(assembly),
        "routing_mode": "side_outlet_first_leg" if side_exit else "rejected_straight_rear_exit",
        "checker_sha256": digest(Path(__file__)),
        "connector_guard_sha256": digest(Path(__file__).with_name("probe_pg3_connector_access.py")),
        "catalog_sha256": digest(Path("references/jst-eh/eEH.pdf")),
        "terminals": terminals,
        "assumptions": assumptions,
        "groups": summary,
        "checks": checks,
        "limits": [
            "1.9mm round insulation and 8.7mm PCB-to-wire-exit are diagnostic assumptions",
            "no fan-out, plug insertion, hand or cable-to-E148 route proof",
            "fixed saved arm pose, no wrist or whole-arm cable sweep",
            "a failed candidate is not proof that every prewired route is impossible",
            "side mode stops outside motor; no subsequent routing or allowed bend-radius proof",
        ],
        "wiring_approved": False,
        "physical_assembly_verified": False,
    }
    (out / "routes.json").write_text(json.dumps(report, indent=2) + "\n")
    selected_group = "R1.2_side_outward" if side_exit else "R4_down"
    selected_names = groups[selected_group]
    selected = {n: routes[n] for n in selected_names}
    assembly_cad = cq.Assembly(name="DIAGNOSTIC_UNACCEPTED_WIRE_ROUTE")
    for name in ("ARM_P05_wrist_XL430", "ARM_M05_ref00", "CAMERA_saddle", "CAMERA_front_jaw"):
        assembly_cad.add(shapes[name], name=name, color=cq.Color(0.6, 0.65, 0.7))
    for name, shape in selected.items():
        assembly_cad.add(shape, name=name, color=cq.Color(1, 0.2, 0.1))
    assembly_cad.save(str(out / f"{selected_group}_DIAGNOSTIC.step"))
    view = [
        (shapes[n], (0.6, 0.65, 0.7, 0.35))
        for n in ("ARM_P05_wrist_XL430", "ARM_M05_ref00", "CAMERA_saddle", "CAMERA_front_jaw")
    ] + [(s, (1, 0.2, 0.1)) for s in selected.values()]
    render(
        view, out / f"{selected_group}_DIAGNOSTIC.png", (1, -1, 0.5), focus=(0, 147, 178), scale=28
    )
    print(json.dumps({g: v["counts"] for g, v in summary.items()}, indent=2))
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assembly", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--side-exit", action="store_true", help="Screen only first lateral exit leg"
    )
    args = parser.parse_args()
    raise SystemExit(run(args.assembly, args.out, args.side_exit))
