"""Export a fail-closed cable-routing CONCEPT on the unaccepted all-XL430 CAD.

Uses actual header occurrence transforms, not mixed-servo port positions.
Sweeps an assumed round bundle along tangent lines and circular bends.
No flexible-body dynamics, connector mating proof or electrical approval.
Sources: https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/
         https://www.jst-mfg.com/product/pdf/eng/eEH.pdf
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import cadquery as cq
import yaml

HERE = Path(__file__).resolve().parent
CADRE = HERE.parents[1]
sys.path.insert(0, str(CADRE / "studies/follower_geometry_revision/source"))
from assembly_io import read_step, bounds
from parts import emergency_center_bolt_idler as idler
from cadre import PartIntent

SOURCE_RUN = CADRE / "outputs/all_xl430_revision/unaccepted/current"
CONFIG = HERE / "intent/cable_routing.yaml"
DEFAULT_OUT = CADRE / "outputs/all_xl430_revision/unaccepted/cable_routing_20260922"


def port_frame(row, exit_height_mm):
    matrix = cq.Matrix(row.loc.wrapped.Transformation())
    origin = cq.Vector(0, 0, 0).transform(matrix)
    normal = (cq.Vector(0, 1, 0).transform(matrix) - origin).normalized()
    return cq.Vector(0, exit_height_mm, 0).transform(matrix), normal


def cable_envelope(edge, radius_mm):
    if not math.isfinite(radius_mm) or radius_mm <= 0:
        raise ValueError("bundle radius must be finite and positive")
    plane = cq.Plane(origin=edge.startPoint(), normal=edge.tangentAt(0))
    path = edge if isinstance(edge, cq.Wire) else cq.Wire.assembleEdges([edge])
    shape = cq.Workplane(plane).circle(radius_mm).sweep(path, isFrenet=True).val()
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError("invalid swept envelope; route must be revised")
    return shape


def rounded_path(points, radius):
    """Join straight legs with exact tangent circular arcs, never a tighter bend."""
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError("bend radius must be finite and positive")
    pts = []
    for point in points:
        if pts and (point - pts[-1]).Length < 1e-6:
            continue
        while len(pts) > 1:
            u, v = (pts[-1] - pts[-2]).normalized(), (point - pts[-1]).normalized()
            if u.dot(v) < 1 - 1e-10:
                break
            pts.pop()
        pts.append(point)
    if len(pts) < 2:
        raise ValueError("route needs at least two distinct points")
    cuts, corners = [0.0], [None]
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        u, v = (b - a).normalized(), (c - b).normalized()
        theta = math.acos(max(-1.0, min(1.0, u.dot(v))))
        if theta >= math.pi - 1e-6:
            raise ValueError("route reverses direction at a waypoint")
        cut = radius * math.tan(theta / 2)
        center = b + (v - u).normalized() * (radius / math.cos(theta / 2))
        middle = center + (b - center).normalized() * radius
        corners.append((b - u * cut, middle, b + v * cut))
        cuts.append(cut)
    cuts.append(0.0)
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        if (b - a).Length < cuts[i] + cuts[i + 1] + 1e-5:
            raise ValueError(f"leg {i} too short for radius {radius}; enlarge the loop")
    edges, cursor = [], pts[0]
    for first, middle, last in corners[1:]:
        edges.append(cq.Edge.makeLine(cursor, first))
        edges.append(cq.Edge.makeThreePointArc(first, middle, last))
        cursor = last
    edges.append(cq.Edge.makeLine(cursor, pts[-1]))
    return cq.Wire.assembleEdges(edges)


def curve_metrics(edge, minimum_radius_mm, samples=501):
    curvatures = edge.curvatures([i / (samples - 1) for i in range(samples)])
    maximum = max(curvatures)
    radius = 1 / maximum if maximum > 1e-10 else None
    return {"length_mm": edge.Length(), "curvature_samples": samples,
            "minimum_sampled_radius_mm": radius,
            "bend_radius_target_mm": minimum_radius_mm,
            "bend_radius_pass": radius is None or radius >= minimum_radius_mm - 1e-6}


def intersections(shape, obstacles):
    hits = []
    bb = bounds(shape)
    for name, other in obstacles.items():
        if not other.Solids():
            continue
        ob = bounds(other)
        if not all(bb[i] <= ob[i + 3] and ob[i] <= bb[i + 3] for i in range(3)):
            continue
        volume = sum(s.Volume() for s in shape.intersect(other).Solids())
        if volume > 1e-5:
            hits.append({"name": name, "volume_mm3": volume})
    return hits


def straight_driver_envelopes(head_face, outward, *, drive_af_mm, shaft_length_mm,
                              handle_diameter_mm, handle_length_mm, withdrawal_mm,
                              shaft_margin_mm, hand_radial_margin_mm):
    """Conservative straight-driver approach, rotation and withdrawal volumes.

    The origin is the exposed head face. The socket interior is deliberately
    outside this check; a matching AF value does not prove drive engagement.
    Cylinders include every rotation and an outward translation up to withdrawal.
    They do not model an L-key, a ratchet or a real human hand.
    """
    sizes = (drive_af_mm, shaft_length_mm, handle_diameter_mm, handle_length_mm)
    margins = (withdrawal_mm, shaft_margin_mm, hand_radial_margin_mm)
    if any(not math.isfinite(v) or v <= 0 for v in sizes):
        raise ValueError("tool sizes must be finite and positive")
    if any(not math.isfinite(v) or v < 0 for v in margins) or outward.Length < 1e-9:
        raise ValueError("invalid tool direction or margin")
    axis = outward.normalized()
    return {
        "shaft_with_margin": cq.Solid.makeCylinder(
            drive_af_mm / math.sqrt(3) + shaft_margin_mm,
            shaft_length_mm + withdrawal_mm, head_face, axis),
        "handle_and_hand": cq.Solid.makeCylinder(
            handle_diameter_mm / 2 + hand_radial_margin_mm,
            handle_length_mm + withdrawal_mm, head_face + axis * shaft_length_mm, axis),
    }


def sampled_insertion(part, obstacles, outward, travel_mm, step_mm):
    """Probe insertion backwards from the seated part; samples are not a sweep."""
    if any(not math.isfinite(v) or v <= 0 for v in (travel_mm, step_mm)) or outward.Length < 1e-9:
        raise ValueError("invalid insertion path")
    axis, count = outward.normalized(), math.ceil(travel_mm / step_mm)
    collisions = []
    for i in range(count + 1):
        offset = travel_mm * i / count
        hits = intersections(part.translate(axis * offset), obstacles)
        if hits:
            collisions.append({"offset_mm": offset, "intersections": hits})
    return {"sampled_clear": not collisions, "samples": count + 1,
            "outward_direction": axis.toTuple(), "travel_mm": travel_mm,
            "sample_spacing_mm": travel_mm / count, "colliding_samples": collisions,
            "scope": "sampled straight insertion at saved pose, not continuous or alternate-path proof"}


def load_source(run):
    source = run / "CAD/arm_all_XL430_static_UNACCEPTED.step"
    previous = json.loads((run / "reports/validation.json").read_text())
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != previous["candidate_sha256"]["CAD/arm_all_XL430_static_UNACCEPTED.step"]:
        raise ValueError("source CAD no longer matches the existing rejection report")
    manifest_path = run / "replacement_manifest.json"
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != previous["candidate_sha256"]["replacement_manifest.json"]:
        raise ValueError("source occurrence manifest has changed")
    _, _, rows = read_step(source)
    names = {row.name: row for row in rows}
    if len(names) != len(rows):
        raise ValueError("ambiguous source occurrence names")
    manifest = json.loads(manifest_path.read_text())
    if set(names) != {item["name"] for item in manifest}:
        raise ValueError("source occurrences do not match the manifest")
    return source, digest, previous, names, manifest


def build(out=DEFAULT_OUT, run=SOURCE_RUN, config=CONFIG):
    settings = yaml.safe_load(config.read_text())
    source, digest, previous, names, manifest = load_source(run)
    assembly = cq.Assembly(name="ALL_XL430_CABLE_CONCEPT_UNACCEPTED")
    shoulder = "/Robot Arm v14/XL-430_new v1:2/"
    removed = {item["name"] for item in manifest if item["logical_path"].startswith(shoulder)
               and any(t in item["logical_path"] for t in ("IDLER_DUMMY", "IDLER_CAP", "IDLER_SCREW"))}
    if len(removed) != 4:
        raise ValueError("shoulder idler replacement scope has changed")
    obstacles = {}
    for name, row in names.items():
        if name not in removed:
            obstacles[name] = row.world
            assembly.add(row.world, name=name, color=row.color)

    # Same shoulder datum as the validated local prototype; keep all other parts.
    original_idler = names["KEEP_067_DC11_A01_IDLER_DUMMY_1"]
    bb = bounds(original_idler.world)
    placement = cq.Location(cq.Vector(bb[0], (bb[1]+bb[4])/2, (bb[2]+bb[5])/2))
    intent = PartIntent.load(idler.INTENT)
    features = {f.name: f.constraints for f in intent.features}
    length = features["support_flange"]["thickness_mm"] + features["rotating_pilot"]["extension_from_flange_mm"]
    additions = {
        "emergency_printed_idler": idler.make_emergency_idler(intent).val().moved(placement),
        "reference_wide_washer": idler.make_reference_washer(intent).val().translate((length, 0, 0)).moved(placement),
        "reference_M3x12_bolt": idler.make_reference_bolt(intent).val().moved(placement),
    }
    addition_hits = {name: intersections(shape, obstacles) for name, shape in additions.items()}
    insertion_results = {}
    # The retained link is intentionally present. If the flange cannot pass it,
    # report the necessary precedence rather than hiding the link from the scan.
    for name, shape in additions.items():
        insertion_results[name] = sampled_insertion(shape, obstacles, cq.Vector(1, 0, 0),
                                                    **settings["insertion_probe"])
        insertion_results[name]["already_added_accessories"] = list(additions)[:list(additions).index(name)]
        print(json.dumps({"insertion": name,
                          "colliding_samples": len(insertion_results[name]["colliding_samples"])}), flush=True)
        obstacles[name] = shape
        assembly.add(shape, name=name, color=cq.Color(0.95, 0.45, 0.1))

    routes, cable_shapes, used_ports = [], {}, set()
    for spec in settings["routes"]:
        if "start_port" in spec:
            start, direction = port_frame(names[spec["start_port"]], settings["wire_exit_local_y_mm"])
        else:
            start, direction = cq.Vector(spec["start_xyz_mm"]), cq.Vector(spec["start_direction"])
        end, end_out = port_frame(names[spec["end_port"]], settings["wire_exit_local_y_mm"])
        ports = [spec[k] for k in ("start_port", "end_port") if k in spec]
        if used_ports.intersection(ports):
            raise ValueError("one physical port was assigned to multiple routes")
        used_ports.update(ports)
        lead = settings["port_straight_control_length_mm"]
        points = [start, start + direction * lead,
                  *(cq.Vector(p) for p in spec["waypoints_mm"]), end + end_out * lead, end]
        edge = rounded_path(points, settings["minimum_bend_radius_mm"])
        shape = cable_envelope(edge, settings["bundle_diameter_mm"] / 2)
        metrics = curve_metrics(edge, settings["minimum_bend_radius_mm"])
        hits = intersections(shape, obstacles)
        cable_hits = intersections(shape, cable_shapes)
        record = {"name": spec["name"], "ports": ports,
                  "start_mm": start.toTuple(), "end_mm": end.toTuple(),
                  **metrics, "solid_intersections": hits, "cable_intersections": cable_hits,
                  "scope": "saved pose only; no connector exclusion; no dynamic cable model"}
        routes.append(record)
        cable_shapes[spec["name"]] = shape
        assembly.add(shape, name="CONCEPT_" + spec["name"], color=cq.Color(*spec["color"]))
        print(json.dumps({"route": spec["name"], "length_mm": round(edge.Length(), 1),
                          "bend_radius_mm": metrics["minimum_sampled_radius_mm"],
                          "collisions": len(hits), "cable_collisions": len(cable_hits)}), flush=True)

    # Insertion direction markers end at the wire-exit datum, not at an invented
    # surface point. These lines are annotations, NOT verified mating plug CAD.
    for name in sorted(used_ports):
        start, _ = port_frame(names[name], 6)
        end, _ = port_frame(names[name], settings["wire_exit_local_y_mm"])
        assembly.add(cq.Edge.makeLine(start, end), name="PORT_DATUM_" + name, color=cq.Color(1, 0.9, 0.3))

    bolt = additions["reference_M3x12_bolt"]
    head = cq.Vector(bounds(bolt)[3], (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2)
    tool_zones = straight_driver_envelopes(head, cq.Vector(1, 0, 0), **settings["center_bolt_tool"])
    tool_results = {
        name: {"solid_intersections": intersections(zone, obstacles),
               "cable_intersections": intersections(zone, cable_shapes)}
        for name, zone in tool_zones.items()
    }
    tool_clear = all(not item["solid_intersections"] and not item["cable_intersections"]
                     for item in tool_results.values())
    print(json.dumps({"center_bolt_tool_corridor_clear": tool_clear,
                      "results": tool_results}), flush=True)

    out.mkdir(parents=True, exist_ok=True)
    output_step = out / "arm_all_xl430_cable_concept_UNACCEPTED.step"
    assembly.export(str(output_step))
    for name, zone in tool_zones.items():
        assembly.add(zone, name="TOOL_ENVELOPE_" + name, color=cq.Color(1, 0.3, 0.1, 0.25))
    tool_step = out / "arm_all_xl430_tool_access_UNACCEPTED.step"
    assembly.export(str(tool_step))
    report = {
        "status": "unaccepted_concept", "manufacturing_release": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_step": str(source), "source_sha256": digest,
        "historical_source_external_collision_count": previous["static_interference"]["external_collision_count"],
        "historical_source_report_not_a_new_scan": True,
        "retained_occurrences": len(names) - len(removed), "removed_names": sorted(removed),
        "accessory_intersections": addition_hits,
        "sampled_accessory_insertion": insertion_results,
        "settings": settings, "routes": routes,
        "center_bolt_tool_access": {
            "status": "provisional_clear" if tool_clear else "blocked",
            "head_face_mm": head.toTuple(), "approach_direction": [-1, 0, 0],
            "outward_direction": [1, 0, 0], "envelopes": tool_results,
            "scope": "assumed straight driver, saved pose; margins included; no obstacle exclusions",
            "not_verified": ["actual tool dimensions", "socket fit and drive engagement depth",
                             "actual thread and tightening torque", "other arm fasteners",
                             "component insertion sequence and counter-holding tool"],
        },
        "pending": ["all-XL430 mechanical fit", "actual harness diameter and manufacturer bend limit",
                    "real mating plugs and insertion/tool corridors", "table and base clearance",
                    "joint limits and flexible cable swept motion", "strain-relief fixtures and connector pull",
                    "power distribution, fuses, voltage drop and connector current ratings",
                    "actual center-thread engagement and printed idler friction"],
        "step": str(output_step), "step_sha256": hashlib.sha256(output_step.read_bytes()).hexdigest(),
        "tool_step": str(tool_step), "tool_step_sha256": hashlib.sha256(tool_step.read_bytes()).hexdigest(),
    }
    (out / "cable_review.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--fail-on-blocking", action="store_true")
    args = parser.parse_args()
    report = build(out=args.out)
    print(json.dumps({"status": report["status"], "step": report["step"]}))
    raise SystemExit(2 if args.fail_on_blocking else 0)
