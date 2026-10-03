"""Save and inspect the ID5-only candidate. Exit 2: not installation approval."""

import argparse
import json
import shutil
from itertools import combinations
from pathlib import Path

from gripper_design.pg2 import digest
from gripper_design.pg3 import PG3Model
from gripper_design.pg3_id5 import assemble, inventory_contract
from scripts.render_cad import render
from scripts.review_pg3 import export_reimport, inspect_pairs
from simulation.pg3_scene import color


def run(out):
    out.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    provenance = out / "provenance"
    provenance.mkdir()
    inputs = [
        "gripper_design/pg3_id5.py",
        "gripper_design/pg3.py",
        "gripper_design/pg3_installation.py",
        "gripper_design/pg3_crank_representation.py",
        "gripper_design/build.py",
        "gripper_design/pg2.py",
        "scripts/review_pg3_id5.py",
        "scripts/review_pg3.py",
        "scripts/assembly_io.py",
        "scripts/render_cad.py",
        "camera_jig/build.py",
        "camera_jig/spec.py",
        "camera_jig/serviceability.py",
        "simulation/pg3_scene.py",
        "specs/project.yaml",
        "specs/architecture.yaml",
        "specs/camera_mount.yaml",
        "specs/pg3_installation.yaml",
        "uv.lock",
    ]
    for name in inputs:
        shutil.copy2(root / name, provenance / name.replace("/", "__"))
    model = PG3Model()
    report = {
        "status": "ID5_ONLY_CANDIDATE_NOT_INSTALLATION_APPROVAL",
        "source_archive_sha256": model.receipt["archive_sha256"],
        "arm_step_sha256": digest(root / "references/arm-r3/arm_XL430_R3.step"),
        "poses": {},
        "limits": [
            "physical-to-CAD correspondence has not been observed",
            "P05 is unchanged; cable relief and final camera design are still pending",
            "static changed-context screening is not continuous or force validation",
            "supplier internal overlaps and thread envelopes are not auto-approved",
        ],
        "fabrication_approved": False,
        "powered_operation_approved": False,
    }
    for pose, angle in (("open", 25), ("mid", 90), ("closed", 135)):
        source = assemble(model, angle)
        path = out / f"arm_camera_{pose}_ID5_CANDIDATE.step"
        shapes, signatures = export_reimport(source, path)
        contract = inventory_contract(shapes)
        pairs = [
            (a, b)
            for a, b in combinations(shapes, 2)
            if a.startswith(("PG3_", "CAMERA_")) or b.startswith(("PG3_", "CAMERA_"))
        ]
        checks = inspect_pairs(shapes, pairs)
        (out / f"contacts_{pose}.json").write_text(json.dumps(checks, indent=2) + "\n")
        report["poses"][pose] = {
            "angle_degrees": angle,
            "step_sha256": digest(path),
            "occurrence_count": len(shapes),
            "contract": contract,
            "roundtrip_signatures": signatures,
            "pair_count": len(pairs),
            "contacts": checks["counts"],
        }
        print(pose, len(shapes), checks["counts"], flush=True)
        (out / "review.json").write_text(json.dumps(report, indent=2) + "\n")
        if pose == "mid":
            full = [(s, color(n)) for n, s in shapes.items()]
            render(full, out / "whole_arm.png", (1, 1, 0.7))
            for axis, direction in (("X", (1, 0, 0)), ("Y", (0, 1, 0)), ("Z", (0, 0, 1))):
                render(full, out / f"terminal_{axis}.png", direction, focus=(0, 183, 175), scale=72)
    report["source_hashes"] = {name: digest(root / name) for name in inputs}
    report["outputs_sha256"] = {
        str(p.relative_to(out)): digest(p)
        for p in out.rglob("*")
        if p.is_file() and p.name != "review.json"
    }
    (out / "review.json").write_text(json.dumps(report, indent=2) + "\n")
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.out))
