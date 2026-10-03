"""Audit PG3 evidence without converting diagnostic FAIL into release PASS."""

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

from gripper_design.pg2 import digest


def check_manifest(run, manifest):
    if not manifest:
        raise ValueError("empty evidence manifest")
    for name, expected in manifest.items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe evidence path")
        if digest(run / relative) != expected:
            raise ValueError(f"artifact changed: {name}")


def audit(run):
    report = json.loads((run / "review.json").read_text())
    check_manifest(run, report["output_sha256"])
    actual_files = {
        str(p.relative_to(run)) for p in run.rglob("*") if p.is_file() and p != run / "review.json"
    }
    if actual_files != set(report["output_sha256"]):
        raise ValueError("incomplete evidence manifest")
    root = Path(__file__).resolve().parents[1]
    spec = yaml.safe_load((run / "provenance/specs__camera_mount.yaml").read_text())
    inputs = {}
    for key in ("parent", "assembly_source", "donor_reference"):
        entry = spec[key]
        actual = digest(root / entry["step_path"])
        if actual != entry["sha256"]:
            raise ValueError(f"reference input changed: {key}")
        inputs[entry["step_path"]] = actual
    for code in (run / "provenance").glob("*.py"):
        original = root / code.name.replace("__", "/")
        if digest(original) != digest(code):
            raise ValueError(f"active generator differs from run snapshot: {code.name}")
    pairs = {}
    for pose in ("open", "mid", "closed"):
        coll = json.loads((run / f"collisions_{pose}.json").read_text())
        actual = dict(Counter(r["status"] for r in coll["pairs"]))
        if actual != report["poses"][pose]["pair_counts"] or len(coll["pairs"]) != 19773:
            raise ValueError("pair inventory or summary mismatch")
        pairs[pose] = actual
    sim = json.loads((run / "simulation/simulation.json").read_text())
    if (
        len(sim["samples"]) != 221
        or sim["dof_count"] != 6
        or sim["closed_loop_constraint_count"] != 2
    ):
        raise ValueError("simulation inventory mismatch")
    if sim["max_closure_residual_mm"] > 1e-7 or sim["max_pad_gap_error_mm"] > 1e-7:
        raise ValueError("kinematic mismatch")
    rolls = sim["wrist_roll_samples"]
    for field in ("camera_world_position_m", "camera_world_rotation"):
        if not np.allclose([r[field] for r in rolls], rolls[0][field], atol=1e-12, rtol=0):
            raise ValueError("P05 camera incorrectly follows wrist roll")
    if np.allclose(rolls[0]["pad_R_world_position_m"], rolls[-1]["pad_R_world_position_m"]):
        raise ValueError("downstream pad does not move with roll")
    pngs = list(run.rglob("*.png"))
    for path in pngs:
        if np.asarray(Image.open(path).convert("RGB")).std() < 2:
            raise ValueError(f"blank image: {path}")
    frames = Image.open(run / "simulation/opening_cycle.gif").n_frames
    if frames < 40 or sim["frame_difference_mean"] < 1:
        raise ValueError("opening animation is static")
    return {
        "evidence_audit": "PASS",
        "engineering_status": report["status"],
        "report_sha256": digest(run / "review.json"),
        "verified_artifacts": len(report["output_sha256"]),
        "verified_reference_inputs": inputs,
        "png_count": len(pngs),
        "gif_frames": frames,
        "pair_counts": pairs,
        "whole_arm_fit_approved": False,
        "fabrication_approved": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    result = audit(args.run)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
