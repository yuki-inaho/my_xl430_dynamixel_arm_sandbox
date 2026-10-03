"""Export and challenge the actual locally revised PG3/camera assembly.

No device communication. Exit 2 while physical and engineering acceptance is
incomplete, even if individual geometry checks pass. Never overwrites a run.
"""

import argparse
import json
import shutil
from itertools import combinations
from pathlib import Path

import cadquery as cq
import trimesh

from gripper_design.build import _source_rows
from gripper_design.pg2 import digest
from gripper_design.pg3 import PG3Model, to_arm
from gripper_design.pg3_crank_representation import SOURCE as CRANK_SOURCE
from gripper_design.pg3_crank_representation import build_candidate as build_crank
from gripper_design.pg3_installation import (
    SIDE_OPTICAL_PROXY_MM,
    camera_tools,
    case_attachment_report,
    frame_candidate,
    frame_change_mask,
    horn_attachment_report,
    installed_assembly,
    original_support,
    side_camera_assembly,
    side_camera_parts,
    support_candidate,
    support_change_mask,
)
from scripts.render_cad import render
from scripts.review_pg3 import export_reimport, inspect_pairs
from scripts.review_pg3_camera_range import run as camera_range
from scripts.review_pg3_washer_contacts import controlled_containment
from scripts.verify_pg3_service_stages import assembly_stages
from simulation.pg3_scene import color, simulate, write_scene


def changed(name):
    return not name.startswith("ARM_") or name.startswith("ARM_P06_")


def run(out, *, simulation=True, rendering=True):
    out.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    provenance = out / "provenance"
    provenance.mkdir()
    for name in (
        "gripper_design/pg3_installation.py",
        "gripper_design/pg3_crank_representation.py",
        "gripper_design/pg3.py",
        "scripts/review_pg3.py",
        "scripts/review_pg3_installation.py",
        "scripts/review_pg3_camera_range.py",
        "scripts/review_pg3_washer_contacts.py",
        "scripts/verify_pg3_service_stages.py",
        "scripts/assembly_io.py",
        "scripts/render_cad.py",
        "gripper_design/build.py",
        "gripper_design/pg2.py",
        "camera_jig/spec.py",
        "camera_jig/build.py",
        "camera_jig/serviceability.py",
        "simulation/pg3_scene.py",
        "specs/pg3_installation.yaml",
        "specs/camera_mount.yaml",
        "uv.lock",
    ):
        shutil.copy2(root / name, provenance / name.replace("/", "__"))
    model = PG3Model()
    parts = {
        "P06_PG3_support": support_candidate(),
        "PG3_frame_guide_relief": frame_candidate(model.neutral["frame"]),
        "PG3_crank_representation": build_crank(),
        **side_camera_parts(),
    }
    partdir = out / "changed_parts_CANDIDATE"
    partdir.mkdir()
    meshes = {}
    for name, shape in parts.items():
        path = partdir / name
        cq.exporters.export(shape, str(path.with_suffix(".step")))
        cq.exporters.export(
            shape, str(path.with_suffix(".stl")), tolerance=0.02, angularTolerance=0.1
        )
        reread = cq.importers.importStep(str(path.with_suffix(".step"))).val()
        mesh = trimesh.load_mesh(path.with_suffix(".stl"), process=True)
        meshes[name] = {
            "valid": reread.isValid(),
            "solid_count": len(reread.Solids()),
            "volume_mm3": reread.Volume(),
            "watertight": bool(mesh.is_watertight),
            "winding_consistent": bool(mesh.is_winding_consistent),
            "mesh_components": len(mesh.split()),
            "coordinate_frame": "PG3_construction" if name.startswith("PG3_") else "R3_arm_world",
            "print_orientation": "design_frame_not_slicer_release",
        }
    # Original copies are reference-only; the replacement map selects the revised frame.
    shutil.copytree(model.source / "CAD/parts", out / "PG3_original_parts_STEP")
    shutil.copytree(model.source / "STL", out / "PG3_original_print_STL")
    crank_original_path = model.source / "CAD/parts/07_crank.step"
    crank_saved = cq.importers.importStep(str(partdir / "PG3_crank_representation.step")).val()
    crank_equivalence = controlled_containment(
        cq.importers.importStep(str(crank_original_path)).val(), crank_saved, equal=True
    )
    if not crank_equivalence["pass"]:
        raise ValueError("saved crank material differs from original manufacturing part")
    old, new = original_support(), parts["P06_PG3_support"]
    original_frame = model.neutral["frame"]
    updated_frame = parts["PG3_frame_guide_relief"]
    frame = to_arm(updated_frame)
    report = {
        "status": "INCOMPLETE_NOT_INSTALLATION_APPROVAL",
        "archive_sha256": model.receipt["archive_sha256"],
        "original_copies_reference_only": True,
        "crank_representation": {
            "method": "supplied_CSG_with_deferred_intermediate_clean",
            "source_sha256": digest(CRANK_SOURCE),
            "original_native_part_sha256": digest(crank_original_path),
            "saved_native_material_equivalence": crank_equivalence,
            "dimensions_changed": False,
        },
        "part_replacements": [
            {
                "assembly_occurrence": "PG3_frame",
                "original_step": "PG3_original_parts_STEP/01_frame.step",
                "original_stl": "PG3_original_print_STL/unchanged_C7/01_frame.stl",
                "candidate_step": "changed_parts_CANDIDATE/PG3_frame_guide_relief.step",
                "candidate_stl": "changed_parts_CANDIDATE/PG3_frame_guide_relief.stl",
                "candidate_coordinate_frame": "PG3_construction",
                "assembly_placement": "Ry(+90deg) then translation(-0.2,234.9,164.6)mm",
            },
            {
                "assembly_occurrence": "PG3_crank",
                "original_step": "PG3_original_parts_STEP/07_crank.step",
                "original_stl": "PG3_original_print_STL/unchanged_C7/07_crank.stl",
                "candidate_step": "changed_parts_CANDIDATE/PG3_crank_representation.step",
                "candidate_stl": "changed_parts_CANDIDATE/PG3_crank_representation.stl",
                "candidate_coordinate_frame": "PG3_construction_zero_angle",
                "assembly_placement": "Rz(relative opening angle) then Ry(+90deg), T(-0.2,234.9,164.6)mm",
            },
        ],
        "frame_relief": {
            "original_volume_mm3": original_frame.Volume(),
            "candidate_volume_mm3": updated_frame.Volume(),
            "removed_volume_mm3": original_frame.Volume() - updated_frame.Volume(),
            "added_material_mm3": updated_frame.cut(original_frame).Volume(),
            "change_outside_mask_mm3": original_frame.cut(updated_frame)
            .cut(frame_change_mask())
            .Volume(),
            "retained_end_land_size_mm": [2.0, 3.2, 4.6],
            "end_stop_strength_verified": False,
        },
        "support": {
            "old_frame_intersection_mm3": old.intersect(to_arm(original_frame)).Volume(),
            "new_frame_intersection_mm3": new.intersect(frame).Volume(),
            "frame_distance_mm": new.distance(frame),
            "change_outside_mask_mm3": old.cut(new).cut(support_change_mask()).Volume(),
        },
        "case_attachment": case_attachment_report(
            next(r.world for r in _source_rows() if r.name == "M06_ref00")
        ),
        "horn_attachment": horn_attachment_report(
            next(r.world for r in _source_rows() if r.name == "M05_ref00"), new
        ),
        "meshes": meshes,
        "poses": {},
        "whole_arm_fit_approved": False,
        "fabrication_approved": False,
        "physical_assembly_verified": False,
        "powered_operation_approved": False,
        "limitations": [
            "actual camera and optics unconfirmed",
            "load/PLA creep unverified",
            "cable/connector sweep pending",
            "whole-arm joint sweep pending",
            "unresolved BRep contact controls retained, not waived",
        ],
    }

    def save(name, data):
        (out / name).write_text(json.dumps(data, indent=2) + "\n")

    for angle, label in ((25, "open"), (90, "mid"), (135, "closed")):
        print(f"{label}: export/reimport and all changed-context pairs", flush=True)
        shapes, signatures = export_reimport(
            installed_assembly(model, angle), out / f"arm_camera_{label}_CANDIDATE.step"
        )
        pairs = [(a, b) for a, b in combinations(shapes, 2) if changed(a) or changed(b)]
        collisions = inspect_pairs(shapes, pairs)
        save(f"collisions_{label}.json", collisions)
        report["poses"][label] = {
            "counts": collisions["counts"],
            "pair_count": len(pairs),
            "occurrences": len(shapes),
            "signatures": signatures,
        }
        save("review.partial.json", report)
        if rendering:
            render(
                [(s, color(n)) for n, s in shapes.items()],
                out / f"whole_{label}.png",
                (1, 1, 1),
                size=(1000, 850),
            )
            detail = [
                (s, color(n))
                for n, s in shapes.items()
                if changed(n) or any(k in n for k in ("P05", "M05", "M06"))
            ]
            for axis, direction in {
                "X": (1, 0, 0),
                "Y": (0, 1, 0),
                "Z": (0, 0, 1),
                "iso": (1, 1, 1),
            }.items():
                render(detail, out / f"terminal_{label}_{axis}.png", direction, size=(1000, 800))
        if label == "mid":
            tt = {f"TOOL_{n}": s for n, s in camera_tools().items()}
            all_tools = inspect_pairs(shapes | tt, [(a, b) for a in tt for b in shapes])
            save("tools_fully_assembled.json", all_tools)
            bench = side_camera_assembly()
            m2 = {n: s for n, s in tt.items() if n.startswith("TOOL_M2")}
            # Keep the rejected coarse bench sequence as a diagnostic, then
            # evaluate the explicitly ordered A/B/C and D/E assembly stages.
            stages = {
                "diagnostic_camera_all_M2_after_bench_assembly": inspect_pairs(
                    bench | m2, [(a, b) for a in m2 for b in bench]
                ),
            }
            for stage, (obstacles, subset) in assembly_stages(shapes).items():
                stages[stage] = inspect_pairs(
                    obstacles | subset, [(a, b) for a in subset for b in obstacles]
                )
            save("tools_required_stages.json", stages)
            report["tools_required_stages"] = {k: v["counts"] for k, v in stages.items()}
    if simulation:
        path = write_scene(
            model,
            out / "simulation",
            assembly_factory=installed_assembly,
            optical_proxy_mm=SIDE_OPTICAL_PROXY_MM,
            optical_normal=(0, 1, 0),
        )
        result = simulate(path, virtual_candidates=False)
        report["simulation"] = {k: v for k, v in result.items() if k != "samples"}
        camera_range(path, out / "camera_range", angles=(25, 90, 135), rolls=(-30, 0, 30))
        cr = json.loads((out / "camera_range/camera_range.json").read_text())
        report["camera_range"] = {k: v for k, v in cr.items() if k != "samples"}
    report["output_sha256"] = {
        str(p.relative_to(out)): digest(p) for p in out.rglob("*") if p.is_file()
    }
    save("review.json", report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "support": report["support"],
                "poses": {k: v["counts"] for k, v in report["poses"].items()},
                "stages": report.get("tools_required_stages"),
            },
            indent=2,
        ),
        flush=True,
    )
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--no-simulation", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run(args.out, rendering=not args.no_render, simulation=not args.no_simulation))
