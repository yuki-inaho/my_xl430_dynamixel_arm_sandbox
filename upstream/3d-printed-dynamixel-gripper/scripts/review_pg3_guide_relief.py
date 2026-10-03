"""Audit the saved local frame relief and render four unoverlaid comparisons."""

import argparse
import json
from pathlib import Path

import cadquery as cq

from gripper_design.pg2 import digest
from gripper_design.pg3 import PG3Model, to_arm
from gripper_design.pg3_installation import frame_change_mask
from scripts.assembly_io import read_step
from scripts.render_cad import render

DEPENDENCIES = (
    "gripper_design/pg3_installation.py",
    "gripper_design/pg3.py",
    "gripper_design/pg2.py",
    "scripts/assembly_io.py",
    "scripts/render_cad.py",
    "uv.lock",
)


def control(shape):
    volume = shape.Volume()
    cut = sum(abs(s.Volume()) for s in shape.cut(shape.copy()).Solids())
    common = sum(abs(s.Volume()) for s in shape.intersect(shape.copy()).Solids())
    return {
        "volume_mm3": volume,
        "self_cut_mm3": cut,
        "self_common_mm3": common,
        "passed": shape.isValid()
        and len(shape.Solids()) == 1
        and volume > 0
        and cut < 1e-4
        and abs(common - volume) < 1e-4,
    }


def run(checkpoint, out):
    if out.exists():
        raise FileExistsError(out)
    manifest = json.loads((checkpoint / "review.json").read_text())

    def checked(relative):
        path = checkpoint / relative
        if digest(path) != manifest["output_sha256"][relative]:
            raise ValueError(f"checkpoint hash mismatch: {relative}")
        return path

    for name in DEPENDENCIES:
        frozen = checked("provenance/" + name.replace("/", "__"))
        if digest(Path(name)) != digest(frozen):
            raise ValueError(f"active dependency differs from checkpoint: {name}")
    model = PG3Model()
    original = model.neutral["frame"]
    part_path = checked("changed_parts_CANDIDATE/PG3_frame_guide_relief.step")
    updated = cq.importers.importStep(str(part_path)).val()
    controls = {"original": control(original), "updated": control(updated)}
    if not all(v["passed"] for v in controls.values()):
        raise ValueError("frame operand control failed")
    metrics = {
        "removed_volume_mm3": original.Volume() - updated.Volume(),
        "added_material_mm3": updated.cut(original).Volume(),
        "removed_outside_mask_mm3": original.cut(updated).cut(frame_change_mask()).Volume(),
    }
    if (
        abs(metrics["removed_volume_mm3"] - 11.04) > 1e-4
        or metrics["added_material_mm3"] > 1e-4
        or metrics["removed_outside_mask_mm3"] > 1e-4
    ):
        raise ValueError("local change invariant failed")
    poses = {}
    expected = to_arm(updated)
    for label in ("open", "mid", "closed"):
        assembly = checked(f"arm_camera_{label}_CANDIDATE.step")
        matches = [r.world for r in read_step(assembly)[2] if r.name == "PG3_frame"]
        if len(matches) != 1:
            raise ValueError("expected one installed frame")
        actual = matches[0]
        row = {
            "assembly_sha256": digest(assembly),
            "control": control(actual),
            "actual_minus_expected_mm3": actual.cut(expected).Volume(),
            "expected_minus_actual_mm3": expected.cut(actual).Volume(),
            "common_volume_mm3": actual.intersect(expected).Volume(),
        }
        if (
            not row["control"]["passed"]
            or row["actual_minus_expected_mm3"] > 1e-4
            or row["expected_minus_actual_mm3"] > 1e-4
            or abs(row["common_volume_mm3"] - expected.Volume()) > 1e-4
        ):
            raise ValueError(f"assembly did not install the saved candidate: {label}")
        poses[label] = row
    samples = []
    for angle in (25, 31.875, 38.75, 90, 135):
        for side in ("L", "R"):
            carriage = model.at(angle)["carriage_" + side]
            old_gap, new_gap = original.distance(carriage), updated.distance(carriage)
            samples.append(
                {"angle_deg": angle, "side": side, "old_gap_mm": old_gap, "new_gap_mm": new_gap}
            )
            if new_gap < 0.3 - 1e-6:
                raise ValueError("sampled candidate gap below design value")
    out.mkdir(parents=True)
    for side, x in (("L", -45), ("R", 45)):
        carriage = model.at(25)["carriage_" + side]
        for y in (-18.65, 18.65):
            for label, frame in (("before", original), ("after", updated)):
                render(
                    [(frame, (0.65, 0.68, 0.72)), (carriage, (0.16, 0.52, 0.68))],
                    out / f"{side}_{y}_{label}.png",
                    direction=(1 if side == "R" else -1, -1 if y > 0 else 1, 1.2),
                    size=(900, 700),
                    focus=(x, y, 22),
                    scale=4,
                )
    report = {
        "archive_sha256": model.receipt["archive_sha256"],
        "part_sha256": digest(part_path),
        "checker_sha256": digest(Path(__file__)),
        "dependencies": {p: digest(Path(p)) for p in DEPENDENCIES},
        "controls": controls,
        "metrics": metrics,
        "poses": poses,
        "gap_samples": samples,
        "view": "separate_before_after_oblique_views_no_overlay_left_right_front_rear_end_lands",
        "continuous_clearance": "not_evaluated_by_this_script",
        "end_stop_strength_verified": False,
        "physical_print_fit_verified": False,
        "installation_approved": False,
        "images_sha256": {p.name: digest(p) for p in out.glob("*.png")},
    }
    (out / "guide_relief.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"metrics": metrics, "gaps": samples}, indent=2), flush=True)
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
