"""Independent geometry/serialization/collision checks on the exported STEP."""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import TYPE_CHECKING

import cadquery as cq
import numpy as np
import trimesh
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.TopAbs import TopAbs_REVERSED

from assembly_io import bounds, read_step

if TYPE_CHECKING:
    from rebuild import Build

EPS_VOLUME = 1e-4
EPS_LENGTH = 1e-5


def volume(shape):
    return float(sum(s.Volume() for s in shape.Solids()))


def overlap(a, b):
    return volume(a.intersect(b))


def bore_centres(shape, axis, radius):
    """Projected concave-cylinder axes; radius alone never defines a bore."""
    result = []
    for face in shape.Faces():
        surface = BRepAdaptor_Surface(face.wrapped)
        if (
            surface.GetType() != GeomAbs_Cylinder
            or face.wrapped.Orientation() != TopAbs_REVERSED
        ):
            continue
        cylinder = surface.Cylinder()
        direction = cylinder.Axis().Direction()
        if abs([direction.X(), direction.Y(), direction.Z()][axis]) < 1 - 1e-8:
            continue
        if abs(cylinder.Radius() - radius) > 1e-5:
            continue
        loc = cylinder.Axis().Location()
        pair = np.delete([loc.X(), loc.Y(), loc.Z()], axis)
        if not any(np.linalg.norm(pair - old) < 1e-6 for old in result):
            result.append(pair)
    return np.array(result)


def nearest_error(reference, candidates):
    if len(reference) == 0 or len(candidates) == 0:
        return float("inf")
    return float(
        np.linalg.norm(reference[:, None, :] - candidates[None, :, :], axis=-1)
        .min(axis=1)
        .max()
    )


def extension_rims(shape):
    """Distance from each countersink mouth to the actual exported outer wire."""
    from rebuild import HOLES_YZ

    results = []
    for sign in (-1, 1):
        outer_wires = []
        for face in shape.Faces():
            surface = BRepAdaptor_Surface(face.wrapped)
            if surface.GetType() != GeomAbs_Plane:
                continue
            plane = surface.Plane()
            if (
                abs(plane.Axis().Direction().X()) > 1 - 1e-8
                and abs(plane.Location().X() - sign * 17.5) < 1e-6
            ):
                outer_wires.append(face.outerWire())
        if not outer_wires:
            raise ValueError("Missing outer ear face")
        for y, z in HOLES_YZ:
            mouth = cq.Wire.makeCircle(
                2.9, cq.Vector(sign * 17.5, y, z), cq.Vector(1, 0, 0)
            )
            distance = min(mouth.distance(wire) for wire in outer_wires)
            entry_empty = all(
                not shape.isInside(cq.Vector(sign * x, y, z))
                for x in (14.501, 15, 15.501, 16.5, 17.499)
            )
            results.append(
                dict(
                    side=sign,
                    centre_yz_mm=[y, z],
                    outer_rim_mm=distance,
                    through_ear_verified=entry_empty,
                )
            )
    return results


def physical_unit(path):
    """Identify each supplier motor subassembly, including the nested gripper motor.

    Reference-solid overlaps INSIDE one supplier motor are recorded, not silently
    claimed to be collision-free. All other pairs are physical assembly conflicts.
    """
    segments = path.split("/")
    for i, segment in enumerate(segments):
        if segment.startswith(("XL,XC-330 v1:", "XL-430_new v1:")):
            return "/".join(segments[: i + 1])
    return path


def scan_collisions(rows, original_paths):
    solids = {i: row.world for i, row in rows.items() if row.shape.Solids()}
    boxes = {i: np.array(bounds(shape)) for i, shape in solids.items()}
    candidates = [
        (i, j)
        for i, j in itertools.combinations(solids, 2)
        if np.all(
            np.minimum(boxes[i][3:], boxes[j][3:])
            - np.maximum(boxes[i][:3], boxes[j][:3])
            > 1e-5
        )
    ]
    hits = []
    for i, j in candidates:
        common = overlap(solids[i], solids[j])
        if common > EPS_VOLUME:
            hits.append(
                dict(
                    i=i,
                    j=j,
                    volume_mm3=common,
                    path_i=original_paths[i],
                    path_j=original_paths[j],
                    supplier_internal=physical_unit(original_paths[i])
                    == physical_unit(original_paths[j]),
                )
            )
    return dict(
        solid_occurrences=len(solids),
        total_pairs=len(solids) * (len(solids) - 1) // 2,
        boolean_candidate_pairs=len(candidates),
        intersections=hits,
    )


def validate_release(build: Build, out: Path):
    parts = {}
    for name, model in build.parts.items():
        path = out / f"CAD/parts/{name}"
        step = cq.importers.importStep(str(path.with_suffix(".step"))).val()
        mesh = trimesh.load_mesh(str(path.with_suffix(".stl")), process=True)
        parts[name] = dict(
            valid_brep=step.isValid(),
            solids=len(step.Solids()),
            volume_mm3=volume(step),
            exact_bounds_mm=bounds(step),
            stl_watertight=bool(mesh.is_watertight),
            stl_positive_volume=bool(mesh.volume > 0),
            stl_volume_mm3=float(mesh.volume),
        )
    extension = cq.importers.importStep(
        str(out / "CAD/parts/elbow_to_wrist_extension_round.step")
    ).val()
    rims = extension_rims(extension)
    preservation = {}
    for key, name in {
        "extension": "elbow_to_wrist_extension_round",
        "base": "base_idler_clearance",
        "wrist": "elbow_to_wrist_standoff",
    }.items():
        old, new, mask = (
            build.local_sources[key],
            build.parts[name],
            build.local_masks[key],
        )
        removed, added = old.cut(new), new.cut(old)
        preservation[key] = dict(
            removed_mm3=volume(removed),
            added_mm3=volume(added),
            removed_outside_mask_mm3=volume(removed.cut(mask))
            if removed.Solids()
            else 0.0,
            added_outside_mask_mm3=volume(added.cut(mask)) if added.Solids() else 0.0,
        )
    _, _, loaded = read_step(out / "CAD/follower_geometry_checked.step")
    reloaded = {int(row.name[:3]): row for row in loaded}
    original = {row.index: row for row in build.original}
    paths = {row.index: row.path for row in build.original}
    if set(reloaded) != set(original):
        raise ValueError("STEP round-trip changed occurrence identity/count")
    total_solids = sum(len(row.shape.Solids()) for row in loaded)
    original_solids = sum(len(row.shape.Solids()) for row in build.original)
    target = reloaded[build.target_index].world

    def row_ending(suffix):
        rows = [r for r in build.original if r.path.endswith(suffix)]
        if len(rows) != 1:
            raise ValueError(f"Nonunique datum owner: {suffix}")
        return reloaded[rows[0].index].world

    mates = []
    for name, a, aa, ar, b, ba, br, expected in [
        (
            "extension_upstream_horn",
            target,
            0,
            0.9,
            row_ending("/XL,XC-330 v1:7/DC15_A01_HORN_DUMMY:1"),
            0,
            0.8,
            4,
        ),
        (
            "extension_downstream_case",
            target,
            0,
            1.1,
            row_ending("/XL,XC-330 v1:8/DC15_A01_CASE_B_DUMMY:1"),
            0,
            1.0,
            2,
        ),
        (
            "wrist_body_mount",
            reloaded[build.wrist_index].world,
            2,
            1.15,
            row_ending("/XL,XC-330 v1:6/DC15_A01_CASE_B_DUMMY:1"),
            2,
            1.0,
            4,
        ),
        (
            "gripper_to_wrist_horn",
            row_ending("/gripper v9:1/static side:1"),
            2,
            1.15,
            row_ending("/XL,XC-330 v1:6/DC15_A01_HORN_DUMMY:1"),
            2,
            0.8,
            4,
        ),
        (
            "base_body_mount",
            reloaded[build.base_index].world,
            2,
            1.5,
            row_ending("/XL-430_new v1:1/DC11_A01_DUMMY:1"),
            2,
            1.25,
            4,
        ),
    ]:
        source_points, destination_points = (
            bore_centres(a, aa, ar),
            bore_centres(b, ba, br),
        )
        error = nearest_error(source_points, destination_points)
        mates.append(
            dict(
                name=name,
                axis_count=len(source_points),
                expected_axis_count=expected,
                max_projected_axis_error_mm=error,
                passed=len(source_points) == expected and error < EPS_LENGTH,
            )
        )

    print("Checking original and reloaded assembly intersections...", flush=True)
    baseline = scan_collisions(original, paths)
    revised = scan_collisions(reloaded, paths)
    before = {(x["i"], x["j"]): x for x in baseline["intersections"]}
    after = {(x["i"], x["j"]): x for x in revised["intersections"]}
    new_hits = [v for key, v in after.items() if key not in before]
    increased = [
        dict(**v, delta_mm3=v["volume_mm3"] - before[key]["volume_mm3"])
        for key, v in after.items()
        if key in before and v["volume_mm3"] - before[key]["volume_mm3"] > 0.01
    ]
    resolved = [v for key, v in before.items() if key not in after]
    physical_hits = [v for v in revised["intersections"] if not v["supplier_internal"]]
    collision_report = dict(
        volume_tolerance_mm3=EPS_VOLUME,
        baseline=baseline,
        revised=revised,
        new_intersections=new_hits,
        increased_intersections=increased,
        resolved_intersections=resolved,
        physical_assembly_intersections=physical_hits,
    )
    (out / "reports/assembly_collisions.json").write_text(
        json.dumps(collision_report, indent=2)
    )
    source_base_bounds = np.array(bounds(build.original[build.base_index].world))
    new_base_bounds = np.array(bounds(reloaded[build.base_index].world))
    base_fixed = (
        float(np.max(np.abs(source_base_bounds - new_base_bounds))) < EPS_LENGTH
    )
    checks = dict(
        all_seven_print_parts_valid_single_solids=all(
            p["valid_brep"] and p["solids"] == 1 for p in parts.values()
        ),
        all_seven_print_meshes_closed=all(
            p["stl_watertight"] and p["stl_positive_volume"] for p in parts.values()
        ),
        extension_original_material_preserved=preservation["extension"]["removed_mm3"]
        < EPS_VOLUME,
        wrist_floor_original_material_preserved=preservation["wrist"]["removed_mm3"]
        < EPS_VOLUME,
        only_declared_local_masks_changed=all(
            p["removed_outside_mask_mm3"] < EPS_VOLUME
            and p["added_outside_mask_mm3"] < EPS_VOLUME
            for p in preservation.values()
        ),
        extension_eight_mouth_rims_at_least_2_5=all(
            r["outer_rim_mm"] >= 2.5 - EPS_LENGTH and r["through_ear_verified"]
            for r in rims
        ),
        checked_five_mating_patterns_aligned=all(m["passed"] for m in mates),
        assembly_count_preserved_no_overlay=total_solids == original_solids == 117
        and len(loaded) == len(original) == 161,
        base_not_translated=base_fixed,
        no_new_or_increased_overlap=not new_hits and not increased,
        no_inter_unit_or_print_part_interference=not physical_hits,
    )
    return dict(
        status="GEOMETRY_PASS_REFERENCE_POSE"
        if all(checks.values())
        else "GEOMETRY_FAIL",
        geometry_checks_passed=all(checks.values()),
        checks=checks,
        print_parts=parts,
        preservation=preservation,
        extension_rims=rims,
        mating_checks=mates,
        original_solid_count=original_solids,
        reloaded_solid_count=total_solids,
        reloaded_leaf_count=len(loaded),
        collision_summary=dict(
            broadphase_total_pairs=revised["total_pairs"],
            detailed_boolean_pairs=revised["boolean_candidate_pairs"],
            source_physical_conflicts=sum(
                not x["supplier_internal"] for x in baseline["intersections"]
            ),
            revised_physical_conflicts=len(physical_hits),
            resolved_count=len(resolved),
            retained_supplier_internal_overlaps=sum(
                x["supplier_internal"] for x in revised["intersections"]
            ),
        ),
        scope="Local printable-part and reference-pose geometry revision; two XL430 + four XL330-series motor instances retained",
        not_verified=[
            "Full XL430 conversion",
            "All-angle or continuous swept-volume collision clearance",
            "Strength, fatigue, payload, holding torque, thermal limits",
            "Fastener length/thread engagement/preload",
            "Printer process tolerance and real-component fit",
            "All remaining legacy hole-family tolerances",
        ],
        manufacturing_notes=[
            "Extension external Y span grows from 90.100 to 93.076 mm; hole datums unchanged",
            "Wrist stand-offs add 3.25 mm to the fastening stack, with 1.5 mm annular wall",
            "Extension-to-downstream-case nominal side gap is 0.25 mm each; clamp/spacer stack requires physical review",
            "Original gripper optional third body-hole axis offset approximately 0.212 mm is retained, not certified",
            "Supplier motor reference solids overlap internally; these models were not rebuilt",
            "Moving-gripper STL uses a temporary 0.00001 mm analytic-cone relief to repair legacy tessellation; STEP remains unchanged; see mesh_export.json",
        ],
    )
