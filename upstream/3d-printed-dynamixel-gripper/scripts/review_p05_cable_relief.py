"""Compare a local P05 cable-window candidate against a saved ID5 assembly."""

import argparse
import json
import shutil
from itertools import combinations
from pathlib import Path

import cadquery as cq

from gripper_design.p05_cable_relief import (
    candidate,
    change_mask,
    diagnostic_wires,
    original,
    protected,
)
from gripper_design.pg2 import digest
from gripper_design.pg3 import shape_signature_difference
from gripper_design.pg3_id5 import inventory_contract
from scripts.assembly_io import read_step
from scripts.render_cad import render
from scripts.review_pg3 import export_reimport, inspect_pairs


def run(assembly, out):
    out.mkdir(parents=True, exist_ok=False)
    rows = read_step(assembly)[2]
    shapes = {r.name: r.world for r in rows}
    if len(rows) != len(shapes):
        raise ValueError("duplicate assembly names")
    inventory_contract(shapes)
    old = original()
    sig = shape_signature_difference(old, shapes["ARM_P05_wrist_XL430"])
    if sig["vertex_distance_mm"] > 1e-6 or sig["volume_error_mm3"] > 1e-4:
        raise ValueError("saved P05 differs from the unchanged source")
    new = candidate()
    cq.exporters.export(new, str(out / "P05_side_windows_CANDIDATE.step"))
    cq.exporters.export(new, str(out / "P05_side_windows_CANDIDATE.stl"), tolerance=0.02)
    new = cq.importers.importStep(str(out / "P05_side_windows_CANDIDATE.step")).val()
    removed = old.cut(new)
    shapes["ARM_P05_wrist_XL430"] = new
    saved, signatures = export_reimport(shapes, out / "ID5_mid_P05_windows_CANDIDATE.step")
    wires = diagnostic_wires()
    context = inspect_pairs(
        saved | wires,
        [("ARM_P05_wrist_XL430", n) for n in saved if n != "ARM_P05_wrist_XL430"]
        + [(w, n) for w in wires for n in saved]
        + list(combinations(wires, 2)),
    )
    (out / "contacts.json").write_text(json.dumps(context, indent=2) + "\n")
    root = Path(__file__).resolve().parents[1]
    source_files = [
        "gripper_design/p05_cable_relief.py",
        "gripper_design/pg3_id5.py",
        "scripts/review_p05_cable_relief.py",
        "scripts/probe_pg3_wire_routes.py",
        "scripts/review_pg3.py",
        "scripts/assembly_io.py",
        "uv.lock",
    ]
    provenance = out / "provenance"
    provenance.mkdir()
    for name in source_files:
        shutil.copy2(root / name, provenance / name.replace("/", "__"))
    checks = {
        n: {
            "old_P05_overlap_mm3": old.intersect(w).Volume(),
            "new_P05_overlap_mm3": new.intersect(w).Volume(),
            "sidewall_distance_mm": new.distance(w),
        }
        for n, w in wires.items()
    }
    report = {
        "assembly_sha256": digest(assembly),
        "source_P05_signature": sig,
        "source_hashes": {n: digest(root / n) for n in source_files},
        "old_volume_mm3": old.Volume(),
        "new_volume_mm3": new.Volume(),
        "removed_volume_mm3": removed.Volume(),
        "added_material_mm3": new.cut(old).Volume(),
        "change_outside_mask_mm3": removed.cut(change_mask()).Volume(),
        "protected_region_loss_mm3": removed.intersect(protected()).Volume(),
        "valid_single_solid": new.isValid() and len(new.Solids()) == 1,
        "wires": checks,
        "context_counts": context["counts"],
        "roundtrip_signatures": signatures,
        "limits": [
            "OD1.9 and bend centreline radius1.2 are unqualified assumptions",
            "sidewall clearance is not plug insertion or complete cable routing",
            "rear-cover clearance uses an assumed wire route; the motor is not modified",
            "support strength, actual contact footprint and PLA creep unverified",
        ],
        "wiring_approved": False,
        "fabrication_approved": False,
    }
    view = [(new, (0.62, 0.65, 0.7))] + [(w, (0.9, 0.15, 0.1)) for w in wires.values()]
    render(view, out / "P05_windows.png", (1, 1, 0.6), focus=(0, 150, 176), scale=32)
    render(view, out / "P05_windows_X.png", (1, 0, 0), focus=(0, 150, 176), scale=32)
    report["outputs_sha256"] = {
        str(p.relative_to(out)): digest(p)
        for p in out.rglob("*")
        if p.is_file() and p.name != "review.json"
    }
    (out / "review.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in {"roundtrip_signatures", "outputs_sha256", "source_hashes"}
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
