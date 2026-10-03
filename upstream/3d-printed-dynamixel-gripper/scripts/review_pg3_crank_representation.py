"""Validate a source-equivalent crank in three saved whole-arm assemblies.

Keeps frozen r4 intact. This candidate does not resolve camera, wiring or physical
acceptance and is not selected by the installation entrypoint.
"""

import argparse
import json
from pathlib import Path

import cadquery as cq

from gripper_design.pg2 import digest
from gripper_design.pg3 import PG3Model, to_arm
from gripper_design.pg3_crank_representation import SOURCE, build_candidate
from scripts.assembly_io import read_step
from scripts.review_pg3 import export_reimport, inspect_pairs
from scripts.review_pg3_crank_fasteners import inspect_bolt
from scripts.review_pg3_washer_contacts import controlled_containment


def run(checkpoint, out):
    out.mkdir(parents=True, exist_ok=False)
    model = PG3Model()  # Verify the immutable intake before using its part reference.
    original_path = model.source / "CAD/parts/07_crank.step"
    native_path = out / "crank_native_CANDIDATE.step"
    cq.exporters.export(build_candidate(), str(native_path))
    native = cq.importers.importStep(str(native_path)).val()
    original = cq.importers.importStep(str(original_path)).val()
    equality = controlled_containment(original, native, equal=True)
    if not equality["pass"]:
        raise ValueError("saved native candidate is not equivalent to donor part")
    manifest_path = checkpoint / "review.json"
    manifest = json.loads(manifest_path.read_text())
    report = {
        "scope": "crank representation candidate, full saved arm and all crank partners",
        "source_sha256": digest(SOURCE),
        "original_part_sha256": digest(original_path),
        "checkpoint_manifest_sha256": digest(manifest_path),
        "native_material_equivalence": equality,
        "replacement_occurrence": "PG3_crank",
        "other_occurrences_replaced": [],
        "installation_approved": False,
        "fabrication_approved": False,
        "default_candidate_changed": False,
        "poses": {},
    }
    for pose, angle in (("open", 25), ("mid", 90), ("closed", 135)):
        source = checkpoint / f"arm_camera_{pose}_CANDIDATE.step"
        if digest(source) != manifest["output_sha256"][source.name]:
            raise ValueError("frozen assembly SHA mismatch")
        rows = read_step(source)[2]
        shapes = {r.name: r.world for r in rows}
        if len(rows) != len(shapes) or "PG3_crank" not in shapes:
            raise ValueError("ambiguous or absent crank")
        shapes["PG3_crank"] = to_arm(native.rotate((0, 0, 0), (0, 0, 1), angle))
        path = out / source.name
        saved, signatures = export_reimport(shapes, path)
        host = saved["PG3_crank"]
        identity = controlled_containment(host, host.copy(), equal=True)
        if not identity["pass"]:
            raise ValueError("saved installed crank fails independent-copy identity")
        checks, negatives = {}, {}
        for i in range(4):
            name = f"PG3_horn_bolt_{i}"
            checks[name] = inspect_bolt(host, saved[name])
            for label, shift in (("axial", (-0.5, 0, 0)), ("lateral", (0, 0.3, 0))):
                negatives[f"{name}_{label}"] = inspect_bolt(host, saved[name].translate(shift))
        pairs = [("PG3_crank", name) for name in saved if name != "PG3_crank"]
        contacts = inspect_pairs(saved, pairs)
        report["poses"][pose] = {
            "input_assembly_sha256": digest(source),
            "output_assembly_sha256": digest(path),
            "occurrences": len(saved),
            "saved_geometry_signatures": signatures,
            "identity": identity,
            "bolt_checks": checks,
            "negative_controls": negatives,
            "all_four_nominal_contacts_bounded": all(
                r["nominal_contact_pass"] for r in checks.values()
            ),
            "negative_controls_rejected": all(
                r["status"] == "UNPROVEN" for r in negatives.values()
            ),
            "crank_partner_checks": contacts["pairs"],
            "crank_partner_controls": contacts["operand_controls"],
            "crank_partner_counts": contacts["counts"],
        }
        print(pose, report["poses"][pose]["crank_partner_counts"], flush=True)
    report["dependencies"] = {
        name: digest(Path(name))
        for name in (
            "gripper_design/pg3_crank_representation.py",
            "gripper_design/pg3.py",
            "gripper_design/pg2.py",
            "scripts/review_pg3_crank_representation.py",
            "scripts/review_pg3_crank_fasteners.py",
            "scripts/review_pg3_motor_partition.py",
            "scripts/review_pg3_pivot_stacks.py",
            "scripts/review_pg3_washer_contacts.py",
            "scripts/review_pg3.py",
            "scripts/assembly_io.py",
            "uv.lock",
        )
    }
    report["output_sha256"] = {p.name: digest(p) for p in out.glob("*.step")}
    (out / "review.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
