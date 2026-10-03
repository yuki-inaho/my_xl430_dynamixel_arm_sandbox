"""Staged loading on the saved removable bench support."""

import argparse
import json
import sys
from pathlib import Path

import cadquery as cq

from gripper_design.pg2 import digest
from gripper_design.pg3_bench_support import to_world
from scripts.assembly_io import read_step
from scripts.review_pg3_bench_support import linkage
from scripts.review_pg3_drive_screw_exchange import axial_bolt_path_bound
from scripts.review_pg3_mechanism_insertion import review_stage
from scripts.review_pg3_nut_loading import review_loaded_nut
from scripts.review_pg3_washer_contacts import finite_solid


def validate_stages(stages, parts, support):
    installed = {"JIG": support}
    if len(stages) != len(parts) or len(parts) != 17:
        raise ValueError("17 individual loading stages required")
    for stage in stages:
        movers, obstacles = stage["movers"], stage["obstacles"]
        if (
            len(movers) != 1
            or not set(movers) <= set(parts)
            or set(movers) & set(installed)
            or any(shape is not parts[n] for n, shape in movers.items())
        ):
            raise ValueError("each saved part must be loaded once without relocation")
        if set(obstacles) != set(installed) or any(
            shape is not installed[n] for n, shape in obstacles.items()
        ):
            raise ValueError("all already installed material must remain stationary")
        installed.update(movers)
        if set(stage["not_yet_installed"]) != set(parts) - set(installed):
            raise ValueError("explicit future inventory mismatch")
    if set(installed) != {"JIG", *parts}:
        raise ValueError("incomplete final bench inventory")


def loading_stages(shapes, support):
    finite_solid(support)
    parts, _ = linkage(shapes)
    pivots = [f"PG3_pivot_{kind}_{side}" for kind in ("drive", "carriage") for side in ("R", "L")]
    order = [
        *(f"{p}_nut" for p in pivots),
        "PG3_crank",
        "PG3_carriage_R",
        "PG3_carriage_L",
        "PG3_link_R",
        "PG3_link_L",
        *(f"{p}_{item}" for p in pivots for item in ("washer", "bolt")),
    ]
    installed, stages = {"JIG": support}, []
    for name in order:
        stages.append(
            {
                "name": name,
                "movers": {name: parts[name]},
                "obstacles": dict(installed),
                "not_yet_installed": sorted(set(parts) - set(installed) - {name}),
            }
        )
        installed[name] = parts[name]
    validate_stages(stages, parts, support)
    return stages


def supplement_stage(stage, raw):
    movers, obstacles = stage["movers"], stage["obstacles"]
    if len(movers) != 1:
        raise ValueError("one moving part required")
    a, mover = next(iter(movers.items()))
    entries = [(tuple(p), 0.0) for p in raw["far_pairs"]]
    entries.extend(
        ((r["a"], r["b"]), r["selected_volume_upper_bound_mm3"]) for r in raw["near_pairs"]
    )
    expected = {(a, b) for b in obstacles}
    if len(entries) != len(expected) or {k for k, _ in entries} != expected:
        raise ValueError("complete pair coverage required before supplementation")
    if raw["start_offset_mm"] != [60, 0, 0] or raw["end_offset_mm"] != [0, 0, 0]:
        raise ValueError("supplement supports source +X60mm to seated motion only")
    selected = {k[1]: v for k, v in entries}
    nut_paths, bolt_paths = {}, {}
    no_penetration = not raw["actual_penetration_samples"]
    for b, obstacle in obstacles.items():
        if selected[b] <= 1e-4:
            continue
        try:
            if a.endswith("_bolt"):
                proof = axial_bolt_path_bound(mover, obstacle, 60)
                bolt_paths[b] = proof
                if proof["status"] == "BOUNDED_TRANSLATION":
                    selected[b] = min(selected[b], proof["continuous_volume_upper_bound_mm3"])
            elif b.endswith("_nut"):
                # Translating both operands by -tX preserves their intersection
                # volume: host+tX against nut equals host against nut-tX.
                proof = review_loaded_nut({b: obstacle}, {a: mover}, (-60, 0, 0))
                nut_paths[b] = proof
                no_penetration &= not proof["actual_penetration_samples"]
                if proof["supplemented_continuous_translation_volume_clear"]:
                    selected[b] = min(
                        selected[b], proof["hex_enclosure"]["summed_overlap_upper_bound_mm3"]
                    )
        except Exception as exc:  # noqa: BLE001 - An unproved bound cannot lower the result.
            target = bolt_paths if a.endswith("_bolt") else nut_paths
            target[b] = {"status": "ERROR", "reason": f"{type(exc).__name__}: {exc}"}
    total = sum(selected.values())
    return {
        "inverse_nut_paths": nut_paths,
        "axial_bolt_paths": bolt_paths,
        "selected_pair_upper_bounds_mm3": selected,
        "summed_upper_bound_mm3": total,
        "nominal_material_path_clear": total <= 1e-4 and no_penetration,
        "physical_retention_proven": False,
        "basis": "whole-pair relative translation; existing complete hex and bolt material enclosures; raw evidence retained",
    }


def run(checkpoint, support_dir, out):
    if out.exists():
        raise FileExistsError(out)
    path = checkpoint / "arm_camera_mid_CANDIDATE.step"
    manifest = json.loads((checkpoint / "review.json").read_text())
    jig_report = json.loads((support_dir / "review.json").read_text())
    jig_path = support_dir / "bench_support_CANDIDATE.step"
    if (
        digest(path) != manifest["output_sha256"][path.name]
        or digest(path) != jig_report["assembly_sha256"]
        or digest(jig_path) != jig_report["output_sha256"][jig_path.name]
    ):
        raise ValueError("saved assembly/support provenance mismatch")
    rows = read_step(path)[2]
    shapes = {r.name: r.world for r in rows}
    if len(shapes) != len(rows):
        raise ValueError("ambiguous occurrence identity")
    support = to_world(cq.importers.importStep(str(jig_path)).val(), jig_report["frame"])
    stages = loading_stages(shapes, support)
    report = {
        "assembly_sha256": digest(path),
        "support_step_sha256": digest(jig_path),
        "support_review_sha256": digest(support_dir / "review.json"),
        "stages": [],
        "installation_approved": False,
        "fabrication_approved": False,
    }
    for index, stage in enumerate(stages, 1):
        print("stage", index, stage["name"], flush=True)
        proof = review_stage(stage["movers"], stage["obstacles"], (60, 0, 0))
        proof["supplemental"] = supplement_stage(stage, proof)
        proof.update(
            index=index,
            part=stage["name"],
            not_yet_installed=stage["not_yet_installed"],
        )
        report["stages"].append(proof)
    report["pair_count"] = sum(s["pair_count"] for s in report["stages"])
    if report["pair_count"] != 153:
        raise ValueError("complete 17-stage Cartesian coverage required")
    report["nominal_material_paths_pass"] = all(
        s["supplemental"]["nominal_material_path_clear"] for s in report["stages"]
    )
    report["limits"] = [
        "parts are placed individually at saved-mid orientations; nuts need manual angular alignment",
        "horizontal bench gravity is a handling assumption, not simulated stability or retention",
        "hands and transient locating devices are absent; nut lateral slip and host positioning remain unverified",
        "smooth bolt translation does not prove threading, rotation, tool engagement or tightening",
        "no arm/frame/camera on bench; separately held spacer and whole-cluster arm insertion belong to subsequent stages",
        "final geometry, printed tolerances, real fasteners, cable egress, optics and strength gates remain open",
    ]
    root, dependencies = Path.cwd().resolve(), set()
    for module in list(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename:
            absolute = Path(filename).resolve()
            if absolute.is_relative_to(root) and absolute.suffix == ".py":
                relative = absolute.relative_to(root)
                if relative.parts[0] in {"scripts", "gripper_design", "camera_jig"}:
                    dependencies.add(relative.as_posix())
    report["dependencies"] = {p: digest(Path(p)) for p in sorted(dependencies | {"uv.lock"})}
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print("nominal material paths", report["nominal_material_paths_pass"], flush=True)
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("support", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.support, args.out))
