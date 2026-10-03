"""Reconcile the PG3 terminal BOM against a pinned saved STEP, not purchasing approval."""

import argparse
import hashlib
import json
from fnmatch import fnmatchcase
from pathlib import Path

import yaml

SCOPE = ["PG3_", "CAMERA_", "ARM_P06_"]
MOTOR_REPRESENTATIONS = {"PG3_XL430_fixed", "PG3_XL430_horn"}


def reconcile(spec, names):
    if len(set(names)) != len(names):
        raise ValueError("duplicate saved occurrence names")
    if spec["scope_prefixes"] != SCOPE:
        raise ValueError("terminal scope cannot silently change")
    target = {n for n in names if n.startswith(tuple(SCOPE))}
    if not target or not spec["items"]:
        raise ValueError("empty BOM or target")
    seen, ids, rows = set(), set(), []
    for item in spec["items"]:
        name, quantity = item["id"], item["quantity"]
        if name in ids or type(quantity) is not int or quantity <= 0:
            raise ValueError("duplicate item ID or invalid quantity")
        ids.add(name)
        matches = set()
        for pattern in item["patterns"]:
            selected = {n for n in names if fnmatchcase(n, pattern)}
            if not selected or matches & selected:
                raise ValueError(f"empty or duplicate selector: {pattern}")
            matches |= selected
        if not matches <= target or matches & seen:
            raise ValueError(f"out-of-scope or double-counted occurrence: {name}")
        mode = item.get("representation", "one_occurrence_per_item")
        if mode == "one_motor_fixed_and_horn":
            if matches != MOTOR_REPRESENTATIONS or quantity != 1:
                raise ValueError("motor display partition is the only two-to-one representation")
        elif mode != "one_occurrence_per_item" or len(matches) != quantity:
            raise ValueError(f"quantity or representation mismatch: {name}")
        seen |= matches
        rows.append({**item, "occurrences": sorted(matches)})
    if seen != target:
        raise ValueError(f"unlisted terminal occurrences: {sorted(target - seen)}")
    return {
        "status": "INVENTORY_MATCH_NOT_PURCHASING_APPROVAL",
        "scope": "terminal additions/replacements only; upstream assembly and motor internals excluded",
        "covered_occurrence_count": len(seen),
        "physical_item_count": sum(r["quantity"] for r in rows),
        "excluded_occurrences": sorted(set(names) - target),
        "items": rows,
        "dimension_or_fastener_qualification": False,
        "fabrication_approved": False,
        "installation_approved": False,
    }


def require_digest(path, expected):
    value = hashlib.sha256(path.read_bytes()).hexdigest()
    if value != expected:
        raise ValueError(f"input SHA mismatch: {path}")
    return value


def run(spec_path, checkpoint, out):
    from scripts.assembly_io import read_step

    if out.exists():
        raise FileExistsError(out)
    spec = yaml.safe_load(spec_path.read_text())
    manifest = json.loads((checkpoint / "review.json").read_text())
    assembly = checkpoint / "arm_camera_mid_CANDIDATE.step"
    source_sha = require_digest(assembly, spec["assembly_sha256"])
    require_digest(assembly, manifest["output_sha256"][assembly.name])
    rows = read_step(assembly)[2]
    result = reconcile(spec, [r.name for r in rows])
    result["assembly_sha256"] = source_sha
    result["evidence_sha256"] = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (
            spec_path,
            checkpoint / "review.json",
            Path(__file__),
            Path("scripts/assembly_io.py"),
        )
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print({k: result[k] for k in ("status", "covered_occurrence_count", "physical_item_count")})
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--spec", type=Path, default=Path("specs/pg3_candidate_bom.yaml"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.spec, args.checkpoint, args.out))
