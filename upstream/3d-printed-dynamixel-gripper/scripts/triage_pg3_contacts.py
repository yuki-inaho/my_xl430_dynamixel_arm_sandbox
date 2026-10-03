"""Source-bound triage of unresolved contacts; never converts errors into clearance."""

import argparse
import json
from collections import Counter
from pathlib import Path

from gripper_design.build import _source_rows
from gripper_design.pg2 import digest
from gripper_design.pg3 import PG3Model, shape_signature_difference, to_arm
from scripts.assembly_io import bounds, read_step


def source_signature(actual, original):
    if original is None:
        return {"status": "NO_UNCHANGED_SOURCE_CLAIM"}
    difference = shape_signature_difference(actual, original)
    matched = (
        difference["vertex_count_equal"]
        and difference["face_count_equal"]
        and difference["vertex_distance_mm"] < 1e-5
        and difference["volume_error_mm3"] < 1e-3
        and difference["area_error_mm2"] < 1e-3
    )
    return {
        "status": "SIGNATURE_MATCH" if matched else "SOURCE_MISMATCH",
        "scope": "vertices_topology_area_volume_not_exact_material_equivalence",
        **difference,
    }


def category(a, b):
    pair = {a, b}
    internal = {f"ARM_M06_ref{i:02d}" for i in range(2, 35)}
    if "PG3_XL430_fixed" in pair and pair & internal:
        return "supplier_internal_vs_partitioned_motor"
    if all(n.startswith("PG3_") for n in pair):
        return "inherited_pg3_joint_requires_local_contact_proof"
    if "ARM_P06_PG3_support" in pair:
        return "modified_support_vs_mating_motor"
    if any(n.startswith("ARM_P06_horn_bolt_") for n in pair):
        return "new_horn_screw_vs_mating_thread"
    if any(n.startswith("ARM_P06_case_tapper_") for n in pair):
        return "new_case_tapper_vs_mating_pilot"
    if "CAMERA_REFERENCE_UNCONFIRMED" in pair:
        return "reference_camera_vs_mount_or_screw"
    return "UNCLASSIFIED_REQUIRES_REVIEW"


def run(checkpoint, out):
    if out.exists():
        raise FileExistsError(out)
    review = json.loads((checkpoint / "review.json").read_text())
    model = PG3Model()
    arm = {f"ARM_{r.name}": r.world for r in _source_rows()}
    result = {
        "purpose": "triage_not_contact_approval",
        "checker_sha256": digest(Path(__file__)),
        "archive_sha256": model.receipt["archive_sha256"],
        "review_sha256": digest(checkpoint / "review.json"),
        "supplier_partition_source": "references/pg3-c9/PG3_C92_J28/reference/C7/source/design.py:187",
        "poses": {},
        "whole_arm_fit_approved": False,
    }
    for label, angle in (("open", 25), ("mid", 90), ("closed", 135)):
        assembly = checkpoint / f"arm_camera_{label}_CANDIDATE.step"
        raw_path = checkpoint / f"collisions_{label}.json"
        for path in (assembly, raw_path):
            if digest(path) != review["output_sha256"][path.name]:
                raise ValueError(f"checkpoint hash mismatch: {path}")
        original = arm | {f"PG3_{n}": to_arm(s) for n, s in model.at(angle).items()}
        loaded = read_step(assembly)[2]
        actual = {r.name: r.world for r in loaded}
        if len(actual) != len(loaded):
            raise ValueError("ambiguous occurrence identity")
        unresolved = [r for r in json.loads(raw_path.read_text())["pairs"] if r["status"] != "PASS"]
        names = {r[k] for r in unresolved for k in ("a", "b")}
        evidence = {
            n: {
                "bbox_mm": bounds(actual[n]),
                "source_signature": source_signature(actual[n], original.get(n)),
            }
            for n in sorted(names)
        }
        rows = []
        for row in unresolved:
            kind = category(row["a"], row["b"])
            inherited = kind.startswith(("supplier_internal", "inherited_pg3"))
            matched = all(
                evidence[row[k]]["source_signature"]["status"] == "SIGNATURE_MATCH"
                for k in ("a", "b")
            )
            rows.append(
                {
                    "raw": row,
                    "category": kind,
                    "inherited_signature_supported": inherited and matched,
                    "contact_approved": False,
                    "required_next_evidence": (
                        "source material/partition and bounded intended contact; signature match alone is insufficient"
                        if inherited and matched
                        else "actual mating surfaces, bounded contact volume, and off-interface intrusion negative control"
                    ),
                }
            )
        result["poses"][label] = {
            "assembly_sha256": digest(assembly),
            "raw_report_sha256": digest(raw_path),
            "category_counts": dict(Counter(r["category"] for r in rows)),
            "retained_raw_status_counts": dict(Counter(r["raw"]["status"] for r in rows)),
            "occurrences": evidence,
            "contacts": rows,
        }
        print(label, result["poses"][label]["category_counts"], flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    return 2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("checkpoint", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
