"""Evidence-producing PG3 import/assembly review. Non-approved runs exit 2."""

import argparse
import importlib.metadata
import json
import math
import platform
import shutil
from collections import Counter
from itertools import combinations
from pathlib import Path

import cadquery as cq

from camera_jig.serviceability import tools
from gripper_design.pg2 import _solid_only, digest, import_archive
from gripper_design.pg3 import (
    SOURCE,
    PG3Model,
    arm_assembly,
    motor_alignment,
    shape_signature_difference,
)
from scripts.assembly_io import bounds, read_step
from scripts.render_cad import render
from simulation.pg3_scene import color, simulate, write_scene


def inspect_pairs(shapes, pairs):
    """Prove solid separation by distance, otherwise use controlled Booleans.

    A valid topology flag alone is insufficient for some supplied motor B-reps.
    Every Boolean operand must first pass difference-with-copy and self-common.
    Solid distance includes containment (distance zero), unlike a surface-only
    distance. A non-solid enclosing box is conservative, never its shell alone.
    """
    boxes = {n: bounds(s) for n, s in shapes.items()}
    controls = {}
    rows = []

    def control(name):
        if name not in controls:
            s = shapes[name]
            removed = sum(abs(v.Volume()) for v in s.cut(s.copy()).Solids())
            common = sum(abs(v.Volume()) for v in s.intersect(s.copy()).Solids())
            volume = sum(abs(v.Volume()) for v in s.Solids())
            controls[name] = {
                "self_cut_mm3": removed,
                "self_common_mm3": common,
                "volume_mm3": volume,
                "passed": s.isValid() and removed < 1e-4 and abs(common - volume) < 1e-4,
            }
        return controls[name]["passed"]

    for a, b in pairs:
        row = {"a": a, "b": b}
        aa, bb = boxes[a], boxes[b]
        if any(aa[i + 3] < bb[i] - 1e-7 or bb[i + 3] < aa[i] - 1e-7 for i in range(3)):
            row.update(status="PASS", reason="bbox_separated")
        else:
            try:
                if not shapes[a].isValid() or not shapes[b].isValid():
                    raise ValueError("invalid operand")
                solid_flags = [_solid_only(shapes[n]) for n in (a, b)]
                operands = []
                for n, bbx, is_solid in zip((a, b), (aa, bb), solid_flags):
                    operands.append(
                        shapes[n]
                        if is_solid
                        else cq.Solid.makeBox(
                            *(bbx[i + 3] - bbx[i] + 2e-5 for i in range(3)),
                            tuple(bbx[i] - 1e-5 for i in range(3)),
                        )
                    )
                distance = operands[0].distance(operands[1])
                if not math.isfinite(distance) or distance < 0:
                    raise ValueError("invalid distance result")
                row["distance_mm"] = distance
                if distance > 1e-5:
                    row.update(
                        status="PASS",
                        reason=(
                            "solid_distance_separated"
                            if all(solid_flags)
                            else "enclosing_box_distance_separated"
                        ),
                    )
                elif not all(solid_flags):
                    row.update(status="UNKNOWN", reason="non_solid_overlap")
                elif not control(a) or not control(b):
                    row.update(status="ERROR", reason="operand_self_boolean_control_failed")
                    # A conservative enclosure is a separate proof, not a repair
                    # of the operand. If its overlap is nonzero the error remains.
                    conservative, enclosed = [], []
                    for name, bbx in ((a, aa), (b, bb)):
                        if control(name):
                            conservative.append(shapes[name])
                        else:
                            enclosed.append(name)
                            conservative.append(
                                cq.Solid.makeBox(
                                    *(bbx[i + 3] - bbx[i] for i in range(3)), tuple(bbx[:3])
                                )
                            )
                    common = conservative[0].intersect(conservative[1])
                    volume = sum(abs(s.Volume()) for s in common.Solids())
                    if not common.isValid() or not math.isfinite(volume):
                        raise ValueError("invalid enclosure intersection")
                    row.update(enclosed_operands=enclosed, conservative_intersection_mm3=volume)
                    if volume <= 1e-4:
                        row.update(status="PASS", reason="conservative_enclosure_boolean_clear")
                else:
                    common = shapes[a].intersect(shapes[b])
                    volume = sum(abs(s.Volume()) for s in common.Solids())
                    if not math.isfinite(volume) or not common.isValid():
                        raise ValueError("invalid common result")
                    row.update(
                        status="FAIL" if volume > 1e-4 else "PASS",
                        reason="solid_intersection" if volume > 1e-4 else "boolean_clear",
                        volume_mm3=volume,
                    )
                    if volume > 1e-4:
                        row["intersection_bounds_mm"] = bounds(common)
            except Exception as exc:  # noqa: BLE001
                row.update(status="ERROR", reason="kernel_error", detail=str(exc))
        rows.append(row)
    return {
        "counts": dict(Counter(r["status"] for r in rows)),
        "pairs": rows,
        "operand_controls": controls,
        "contact_adjudication": "No overlap is automatically accepted as a thread or fit.",
    }


def export_reimport(shapes, path):
    assembly = cq.Assembly(name=path.stem)
    for name, shape in shapes.items():
        assembly.add(shape, name=name, color=cq.Color(*color(name)))
    assembly.save(str(path))
    rows = read_step(path)[2]
    if len(rows) != len(shapes) or {r.name for r in rows} != set(shapes):
        raise ValueError("saved inventory mismatch")
    reread = {r.name: r.world for r in rows}
    signatures = {n: shape_signature_difference(shapes[n], s) for n, s in reread.items()}
    if any(
        v["vertex_distance_mm"] > 1e-5
        or v["volume_error_mm3"] > 1e-3
        or not v["vertex_count_equal"]
        or not v["face_count_equal"]
        for v in signatures.values()
    ):
        raise ValueError("saved geometry signature mismatch")
    return reread, signatures


def review(source, out, rendering=True, simulation=True):
    out.mkdir(parents=True, exist_ok=False)
    provenance = out / "provenance"
    provenance.mkdir()
    for name in (
        "scripts/review_pg3.py",
        "scripts/assembly_io.py",
        "scripts/render_cad.py",
        "gripper_design/pg3.py",
        "gripper_design/pg2.py",
        "simulation/pg3_scene.py",
        "camera_jig/build.py",
        "camera_jig/serviceability.py",
        "specs/camera_mount.yaml",
    ):
        shutil.copy2(
            Path(__file__).resolve().parents[1] / name, provenance / name.replace("/", "__")
        )
    shutil.copy2(source.parent / "intake.json", provenance / "intake.json")
    model = PG3Model(source)
    report = {
        "variant": "PG3_C92_J28_C9",
        "archive_sha256": model.receipt["archive_sha256"],
        "motor_alignment": motor_alignment(source),
        "runtime": {
            "python": platform.python_version(),
            **{n: importlib.metadata.version(n) for n in ("cadquery", "cadquery-ocp", "mujoco")},
        },
        "poses": {},
        "replacement": {
            "removed": ["P07_moving_gripper_XL430", "M06_ref00"],
            "retained_support": "P06_fixed_gripper_XL430",
            "motor": "57 PG3 occurrences including split motor and horn",
        },
        "whole_arm_fit_approved": False,
        "fabrication_approved": False,
        "powered_operation_approved": False,
        "limitations": [
            "unchanged ARM-ARM pairs not requalified",
            "no whole-arm joint sweep",
            "no actual tool selection",
            "no cable/connector sweep",
            "camera model and optical pose unconfirmed",
            "strength/load not evaluated",
        ],
    }
    for angle, label in ((25, "open"), (90, "mid"), (135, "closed")):
        print(f"{label}: saved-pose comparison and whole-arm export", flush=True)
        original = model.compare_saved(angle, label)
        if any(
            e["vertex_distance_mm"] > 1e-6
            or e["volume_error_mm3"] > 1e-4
            or e["area_error_mm2"] > 1e-4
            or not e["vertex_count_equal"]
            or not e["face_count_equal"]
            for e in original["signatures"].values()
        ):
            (out / f"source_comparison_failed_{label}.json").write_text(
                json.dumps(original, indent=2)
            )
            raise ValueError("independent motion differs from saved source")
        assembled, signatures = export_reimport(
            arm_assembly(model, angle), out / f"arm_camera_{label}_UNVALIDATED.step"
        )
        pairs = [
            (a, b)
            for a, b in combinations(assembled, 2)
            if not (a.startswith("ARM_") and b.startswith("ARM_"))
        ]
        print(
            f"{label}: {len(assembled)} occurrences, {len(pairs)} changed-context pairs", flush=True
        )
        collision = inspect_pairs(assembled, pairs)
        (out / f"collisions_{label}.json").write_text(json.dumps(collision, indent=2) + "\n")
        report["poses"][label] = {
            "saved_source_comparison": original,
            "export_signatures": signatures,
            "occurrences": len(assembled),
            "pair_counts": collision["counts"],
        }
        (out / "review.partial.json").write_text(json.dumps(report, indent=2) + "\n")
        if rendering:
            colors = [(s, color(n)) for n, s in assembled.items()]
            render(colors, out / f"whole_arm_{label}.png", (1, 1, 1), size=(1000, 850))
            detail = [
                (s, color(n))
                for n, s in assembled.items()
                if not n.startswith("ARM_") or any(k in n for k in ("P05", "P06", "M05", "M06"))
            ]
            for name, direction in {
                "X": (1, 0, 0),
                "Y": (0, 1, 0),
                "Z": (0, 0, 1),
                "iso": (1, 1, 1),
            }.items():
                render(detail, out / f"terminal_{label}_{name}.png", direction, size=(1000, 800))
        if label == "mid":
            tool_shapes = {f"TOOL_{n}": s for n, s in tools().items()}
            service = inspect_pairs(
                assembled | tool_shapes, [(a, b) for a in tool_shapes for b in assembled]
            )
            (out / "camera_tools_mid.json").write_text(json.dumps(service, indent=2) + "\n")
            report["camera_tool_pair_counts"] = service["counts"]
    if simulation:
        path = write_scene(model, out / "simulation")
        sim = simulate(path)
        report["simulation"] = {k: v for k, v in sim.items() if k != "samples"}
    report["status"] = (
        "FAIL"
        if any(v["pair_counts"].get("FAIL", 0) for v in report["poses"].values())
        else "UNKNOWN"
    )
    report["output_sha256"] = {
        str(p.relative_to(out)): digest(p) for p in out.rglob("*") if p.is_file()
    }
    (out / "review.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "poses": {n: v["pair_counts"] for n, v in report["poses"].items()},
            },
            indent=2,
        )
    )
    return 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    intake = sub.add_parser("import")
    intake.add_argument("archive", type=Path)
    intake.add_argument("--out", type=Path, required=True)
    run = sub.add_parser("review")
    run.add_argument("--source", type=Path, default=SOURCE)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--no-render", action="store_true")
    run.add_argument("--no-simulation", action="store_true")
    args = parser.parse_args()
    if args.command == "import":
        receipt = import_archive(
            args.archive, args.out, archive_root="PG3_C92_J28", manifest_name="SHA256SUMS.txt"
        )
        print(json.dumps(receipt, indent=2))
        return 0
    return review(args.source, args.out, not args.no_render, not args.no_simulation)


if __name__ == "__main__":
    raise SystemExit(main())
