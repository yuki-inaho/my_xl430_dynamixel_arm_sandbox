"""Kinematic diagnostics from SHA-verified saved PG3 arm poses, headless only."""

import argparse
import json
from pathlib import Path

from gripper_design.pg2 import digest
from gripper_design.pg3 import PG3Model, shape_signature_difference, to_arm
from gripper_design.pg3_installation import SIDE_OPTICAL_PROXY_MM
from scripts.assembly_io import read_step
from simulation.pg3_scene import simulate, write_scene


def run(checkpoint, out):
    if out.exists():
        raise FileExistsError(out)
    manifest_path = checkpoint / "review.json"
    manifest = json.loads(manifest_path.read_text())
    saved, hashes = {}, {}
    for pose in ("open", "mid", "closed"):
        path = checkpoint / f"arm_camera_{pose}_CANDIDATE.step"
        sha = digest(path)
        if sha != manifest["output_sha256"][path.name]:
            raise ValueError("saved pose SHA mismatch")
        rows = read_step(path)[2]
        saved[pose] = {r.name: r.world for r in rows}
        if len(rows) != len(saved[pose]):
            raise ValueError("ambiguous occurrence inventory")
        hashes[path.name] = sha
    if any(set(s) != set(saved["mid"]) for s in saved.values()):
        raise ValueError("pose inventories differ")
    model = PG3Model()
    # Invert the explicit PG3 construction-to-arm transform for every PG3 part.
    model.neutral = {
        name: saved["mid"][f"PG3_{name}"]
        .translate((0.2, -234.9, -164.6))
        .rotate((0, 0, 0), (0, 1, 0), -90)
        for name in model.neutral
    }
    comparisons = {}
    for pose, angle in (("open", 25), ("mid", 90), ("closed", 135)):
        checks = {
            name: shape_signature_difference(to_arm(shape), saved[pose][f"PG3_{name}"])
            for name, shape in model.at(angle).items()
        }
        if any(
            r["vertex_distance_mm"] > 1e-5
            or r["volume_error_mm3"] > 1e-3
            or not r["vertex_count_equal"]
            or not r["face_count_equal"]
            for r in checks.values()
        ):
            raise ValueError("kinematic mapping differs from saved poses")
        comparisons[pose] = checks

    def assembly_factory(model, angle):
        if angle != 90:
            raise ValueError("scene construction requires saved mid pose")
        return saved["mid"]

    scene = write_scene(
        model,
        out,
        assembly_factory=assembly_factory,
        optical_proxy_mm=SIDE_OPTICAL_PROXY_MM,
        optical_normal=(0, 1, 0),
    )
    result = simulate(scene, virtual_candidates=False)
    provenance = {
        "input_pose_sha256": hashes,
        "manifest_sha256": digest(manifest_path),
        "pose_signature_comparisons": comparisons,
        "signature_comparison_is_exact_material_proof": False,
        "installation_approved": False,
        "scope": "kinematic closure and rendered visibility, not forces or physical camera",
        "dependencies": {
            name: digest(Path(name))
            for name in (
                "scripts/simulate_pg3_saved.py",
                "scripts/assembly_io.py",
                "simulation/pg3_scene.py",
                "gripper_design/pg3.py",
                "gripper_design/pg3_installation.py",
                "uv.lock",
            )
        },
        "outputs_sha256": {
            str(p.relative_to(out)): digest(p) for p in out.rglob("*") if p.is_file()
        },
    }
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(
        json.dumps(
            {k: result[k] for k in ("max_closure_residual_mm", "max_pad_gap_error_mm", "mode")}
        ),
        flush=True,
    )
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
