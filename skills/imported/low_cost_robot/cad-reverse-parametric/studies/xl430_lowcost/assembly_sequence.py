"""Fail-closed staged translation diagnostics; sampled paths are not approval.

The CLI preserves the original arm and writes a separately labelled candidate.
Supplier motor internals are one purchased subassembly. Only the listed original
idler/cap/center-screw occurrences are replaced. The rest of the arm is retained
in the export but explicitly NOT covered by the local assembly sequence.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path

import cadquery as cq
import yaml

from cable_routing import CADRE, SOURCE_RUN, load_source, bounds
from parts.external_center_support import make_parts, make_insertion_sweeps

CONFIG = Path(__file__).with_name("intent") / "assembly_sequence.yaml"
DEFAULT_OUT = CADRE / "outputs/assembly_resolution/sequence"
VOLUME_TOLERANCE_MM3 = 1e-4


def _vector(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("path offset must have three coordinates")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError("path coordinates must be finite numbers")
    return [float(v) for v in value]


def sample_offsets(waypoints, max_step_mm):
    if (isinstance(max_step_mm, bool) or not isinstance(max_step_mm, (int, float))
            or not math.isfinite(max_step_mm) or max_step_mm <= 0):
        raise ValueError("path step must be finite and positive")
    if not isinstance(waypoints, list) or len(waypoints) < 2:
        raise ValueError("path needs at least two waypoints")
    points = [_vector(p) for p in waypoints]
    if points[-1] != [0., 0., 0.]:
        raise ValueError("path must end at the saved pose")
    result = [points[0]]
    for a, b in zip(points, points[1:]):
        length = math.dist(a, b)
        if length == 0:
            raise ValueError("path has a zero-length segment")
        count = math.ceil(length/max_step_mm)
        if len(result)+count > 100000:
            raise ValueError("path exceeds the diagnostic sample resource limit")
        result.extend([[a[j]+(b[j]-a[j])*i/count for j in range(3)] for i in range(1, count+1)])
    return result


def _names(values, label):
    if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values):
        raise ValueError(f"{label} must be a list of names")
    if len(set(values)) != len(values):
        raise ValueError(f"duplicate {label}")
    return set(values)


def _intersection_volume(a, b):
    solids = a.intersect(b).Solids()
    if any(not s.isValid() for s in solids):
        raise ValueError("invalid boolean intersection solid")
    volumes = [s.Volume() for s in solids]
    if any(not math.isfinite(v) or v < 0 for v in volumes):
        raise ValueError("invalid boolean intersection volume")
    return sum(volumes)


def _hits(part, obstacles, boxes):
    box = bounds(part)
    result = []
    for name, obstacle in obstacles.items():
        other = boxes[name]
        if not all(box[i] <= other[i+3]+1e-5 and other[i] <= box[i+3]+1e-5 for i in range(3)):
            continue
        volume = _intersection_volume(part, obstacle)
        if volume > VOLUME_TOLERANCE_MM3:
            result.append({"obstacle": name, "volume_mm3": volume})
    return result


def validate_sequence(parts, plan, progress=None):
    allowed = {"required_parts", "initially_installed", "initial_fixture_reason", "stages"}
    if not isinstance(plan, dict) or set(plan) != allowed:
        raise ValueError("sequence has missing or unsupported fields")
    required = _names(plan["required_parts"], "required inventory")
    if required != set(parts):
        raise ValueError("required inventory must match the complete supplied part catalog")
    initial = _names(plan["initially_installed"], "initial inventory")
    if not initial <= required or not isinstance(plan["initial_fixture_reason"], str) or not plan["initial_fixture_reason"].strip():
        raise ValueError("initial inventory needs known parts and an explicit fixture reason")
    if not isinstance(plan["stages"], list):
        raise ValueError("stages must be a list")
    installed, ids, paths = set(initial), set(), []
    for stage in plan["stages"]:
        if not isinstance(stage, dict) or set(stage) != {"id", "moving", "requires", "offsets_mm", "max_step_mm"}:
            raise ValueError("stage has missing or unsupported fields; obstacle exclusions are forbidden")
        key, moving = stage["id"], stage["moving"]
        if not isinstance(key, str) or not key or key in ids:
            raise ValueError("stage ids must be unique nonempty strings")
        if not isinstance(moving, str) or moving not in required-installed:
            raise ValueError("moving part is unknown or already installed")
        if not _names(stage["requires"], "stage requirements") <= installed:
            raise ValueError("stage prerequisite is not installed")
        paths.append(sample_offsets(stage["offsets_mm"], stage["max_step_mm"]))
        ids.add(key)
        installed.add(moving)
    if installed != required:
        raise ValueError(f"final inventory missing: {sorted(required-installed)}")
    for name, shape in parts.items():
        if not isinstance(shape, cq.Shape) or not shape.Solids() or not shape.isValid():
            raise ValueError(f"part {name} must contain valid solids; surface references are not obstacles")
    boxes = {name: bounds(shape) for name, shape in parts.items()}
    installed = set(initial)
    initial_hits = []
    for a, b in combinations(sorted(initial), 2):
        initial_hits.extend({"part": a, **hit} for hit in _hits(parts[a], {b: parts[b]}, boxes))
    reports = []
    for stage, offsets in zip(plan["stages"], paths):
        if progress:
            progress(stage["id"])
        obstacles = {n: parts[n] for n in sorted(installed)}
        collisions = []
        for offset in offsets:
            collisions.extend({"offset_mm": offset, **hit} for hit in
                              _hits(parts[stage["moving"]].translate(offset), obstacles, boxes))
        reports.append({"id": stage["id"], "moving": stage["moving"],
                        "obstacles": sorted(obstacles), "sample_count": len(offsets),
                        "offsets_mm": offsets, "max_step_mm": stage["max_step_mm"],
                        "collisions": collisions, "sampled_clear": not collisions})
        installed.add(stage["moving"])
    return {"sampled_clear": not initial_hits and all(s["sampled_clear"] for s in reports),
            "continuous_path_verified": False, "engineering_approved": False,
            "volume_tolerance_mm3": VOLUME_TOLERANCE_MM3,
            "initial_collisions": initial_hits, "stages": reports,
            "installed_final": sorted(installed),
            "scope": "all supplied local units only; nominal final poses after failed stages remain hypothetical"}


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def continuous_accessory_checks(parts, plan, candidate):
    nominal, _ = make_parts(candidate)
    installed = set(plan["initially_installed"])
    boxes = {name: bounds(shape) for name, shape in parts.items()}
    reports = []
    for stage in plan["stages"]:
        moving, offsets = stage["moving"], stage["offsets_mm"]
        supported = (moving in nominal and len(offsets) == 2 and offsets[-1] == [0,0,0]
                     and offsets[0][0] > 0 and offsets[0][1:] == [0,0])
        record = {"id": stage["id"], "moving": moving, "supported": supported,
                  "continuous_clear": None, "obstacles": sorted(installed)}
        if supported:
            a, b = nominal[moving], parts[moving]
            difference = sum(s.Volume() for shape in (a.cut(b), b.cut(a)) for s in shape.Solids())
            if not math.isfinite(difference) or difference > VOLUME_TOLERANCE_MM3:
                raise ValueError("actual part differs from the sweep definition")
            sweep = make_insertion_sweeps(candidate, offsets[0][0])[moving]
            if not sweep.isValid() or not sweep.Solids():
                raise ValueError("invalid translation sweep")
            hits = _hits(sweep, {n:parts[n] for n in sorted(installed)}, boxes)
            record.update({"continuous_clear": not hits, "collisions": hits,
                           "method": "exact axial extrusion union",
                           "travel_mm": offsets[0][0]})
        else:
            record["reason"] = "No continuous proof for this shape or path; sampled results are separate."
        reports.append(record)
        installed.add(moving)
    return reports


def replacement_inventory(config, manifest):
    motor_rows = [r for r in manifest if r["logical_path"].startswith(config["source_motor_path"])]
    motor_names = {r["name"] for r in motor_rows}
    expected = {r["name"] for r in motor_rows if any(token in r["logical_path"]
                for token in ("/DC11_A01_IDLER_DUMMY:", "/DC11_A01_IDLER_CAP_DUMMY:", "/DC11_A01_IDLER_SCREW:"))}
    removed = _names(config["removed_source_parts"], "replaced source parts")
    if len(expected) != 4 or removed != expected:
        raise ValueError("replacement inventory must be exactly the original idler, cap and two center-screw leaves")
    return motor_names, removed


def _contact_area(a, b, x):
    def faces(shape):
        return [f for f in shape.Faces() if f.geomType() == "PLANE"
                and abs(f.normalAt().x) > .999 and abs(f.Center().x-x) < 1e-6]
    return sum(fa.intersect(fb).Area() for fa in faces(a) for fb in faces(b))


def run(config_path, out):
    config = yaml.safe_load(config_path.read_text())
    source, digest, previous, names, manifest = load_source(SOURCE_RUN)
    if digest != config["source_sha256"]:
        raise ValueError("sequence source hash differs from configured source")
    motor_names, removed = replacement_inventory(config, manifest)
    if not motor_names <= set(names) or config["source_link"] not in names:
        raise ValueError("replacement exclusions or source link do not resolve")
    included_motor = sorted(n for n in motor_names-removed if names[n].world.Solids())
    if not included_motor:
        raise ValueError("motor subassembly is empty")
    motor = cq.Compound.makeCompound([names[n].world for n in included_motor])
    accessories, stack = make_parts(config["candidate"])
    stack["motor_tube_contact_area_mm2"] = _contact_area(
        motor, accessories["tube"], config["candidate"]["motor_seat_x_mm"])
    parts = {"link": names[config["source_link"]].world, "motor": motor, **accessories}
    result = validate_sequence(parts, config["sequence"], lambda name: print(f"Checking {name}", flush=True))
    result["continuous_stage_checks"] = continuous_accessory_checks(parts, config["sequence"], config["candidate"])
    local_source = motor_names | {config["source_link"]}
    result.update({"created_at": datetime.now(timezone.utc).isoformat(),
        "status": "UNACCEPTED", "config": str(config_path.resolve()),
        "source": str(source), "source_sha256": digest, "config_sha256": _hash(config_path),
        "script_sha256": _hash(Path(__file__)),
        "candidate_generator_sha256": _hash(Path(__file__).with_name("parts")/"external_center_support.py"),
        "local_source_occurrences": sorted(local_source), "replaced_source_occurrences": sorted(removed),
        "unplanned_source_occurrences": sorted(set(names)-local_source),
        "unresolved_acceptance": config["unresolved_acceptance"], "nominal_stack": stack,
        "baseline_external_intersections_not_resolved": previous["static_interference"]["external_collision_count"],
        "baseline_report_only_not_a_new_full_scan": True,
        "whole_arm_sequence_complete": False})
    out.mkdir(parents=True, exist_ok=True)
    (out/"sequence_report.json").write_text(json.dumps(result, indent=2)+"\n")
    assembly = cq.Assembly(name="all_XL430_external_support_UNACCEPTED")
    for name, row in names.items():
        if name not in removed:
            assembly.add(row.world, name=name, color=row.color)
    for name, shape in accessories.items():
        assembly.add(shape, name=f"candidate_{name}_UNVALIDATED",
                     color=cq.Color(.9, .45, .1) if name == "guide" else cq.Color(.4, .65, .7))
    target = out/"arm_external_support_UNACCEPTED.step"
    assembly.save(str(target))
    result["output_sha256"] = {target.name: _hash(target)}
    result["output_occurrence_count"] = len(names)-len(removed)+len(accessories)
    (out/"sequence_report.json").write_text(json.dumps(result, indent=2)+"\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--fail-on-blocking", action="store_true")
    args = parser.parse_args()
    result = run(args.config, args.out)
    print(json.dumps({k:result[k] for k in ("status", "sampled_clear", "engineering_approved", "whole_arm_sequence_complete")}))
    return 2 if args.fail_on_blocking and not result["engineering_approved"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
