"""Exact solid decomposition audit, preserving raw collision reports and unknowns."""

import argparse
import json
from collections import Counter
from pathlib import Path

from gripper_design.pg2 import _solid_only, digest
from scripts.assembly_io import read_step
from scripts.review_pg3 import inspect_pairs


def inspect_components(first, second):
    if not _solid_only(first) or not _solid_only(second):
        return {"status": "UNKNOWN", "reason": "non_solid_material_not_dropped"}
    shapes = {f"a_{i}": s for i, s in enumerate(first.Solids())}
    shapes.update({f"b_{i}": s for i, s in enumerate(second.Solids())})
    aa = [n for n in shapes if n.startswith("a_")]
    bb = [n for n in shapes if n.startswith("b_")]
    if not aa or not bb:
        raise ValueError("empty material inventory")
    result = inspect_pairs(shapes, [(a, b) for a in aa for b in bb])
    rows = result["pairs"]
    # Components may overlap internally. The sum is an upper bound on the
    # union intersection, not a reason to double-count it as physical collision.
    upper_bound = sum(
        r.get("volume_mm3", r.get("conservative_intersection_mm3", 0.0)) for r in rows
    )
    if any(r["status"] == "FAIL" for r in rows):
        status, reason = "FAIL", "at_least_one_proven_component_penetration"
    elif all(r["status"] == "PASS" for r in rows) and upper_bound <= 1e-4:
        status, reason = "PASS", "all_material_components_clear_with_global_bound"
    else:
        status, reason = "UNKNOWN", "component_evidence_insufficient"
    return {
        "status": status,
        "reason": reason,
        "component_counts": [len(aa), len(bb)],
        "intersection_upper_bound_mm3": upper_bound if status == "PASS" else None,
        "checks": result,
        "healing_or_geometry_changes": False,
    }


def run(checkpoint, out):
    if out.exists():
        raise FileExistsError(out)
    original = json.loads((checkpoint / "review.json").read_text())
    result = {
        "checker_sha256": digest(Path(__file__)),
        "base_checker_sha256": digest(Path(__file__).with_name("review_pg3.py")),
        "poses": {},
        "installation_approved": False,
    }
    for label in ("open", "mid", "closed"):
        assembly = checkpoint / f"arm_camera_{label}_CANDIDATE.step"
        report = checkpoint / f"collisions_{label}.json"
        for path in (assembly, report):
            if digest(path) != original["output_sha256"][path.name]:
                raise ValueError(f"checkpoint hash mismatch: {path}")
        loaded = read_step(assembly)[2]
        shapes = {r.name: r.world for r in loaded}
        if len(shapes) != len(loaded):
            raise ValueError("ambiguous occurrence identity")
        raw = json.loads(report.read_text())
        rows = [
            {"raw": r, "decomposition": inspect_components(shapes[r["a"]], shapes[r["b"]])}
            for r in raw["pairs"]
            if r["status"] != "PASS"
        ]
        result["poses"][label] = {
            "assembly_sha256": digest(assembly),
            "raw_report_sha256": digest(report),
            "counts": dict(Counter(r["decomposition"]["status"] for r in rows)),
            "rows": rows,
        }
        print(label, result["poses"][label]["counts"], flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    return 2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("checkpoint", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
