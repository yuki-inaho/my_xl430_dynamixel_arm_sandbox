"""Export and audit the unapproved ID5 case-top camera mount candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import cadquery as cq
import trimesh

from camera_jig.build import collision_rows, common_volume
from camera_jig.id5_corner import SPEC_PATH, build_candidate, validate_candidate
from camera_jig.id5_corner_anchor import validate_id5_case_anchor
from camera_jig.id5_corner_vision import corners
from gripper_design.pg3 import PG3Model
from gripper_design.pg3_id5 import assemble
from scripts.assembly_io import read_step

ROOT = Path(__file__).resolve().parents[1]
MID_STEP = ROOT / "outputs/pg3-id5-p05-windows-r2/ID5_mid_P05_windows_CANDIDATE.step"
MID_REVIEW = ROOT / "outputs/pg3-id5-p05-windows-r2/review.json"
ARM_STEP = ROOT / "references/arm-r3/arm_XL430_R3.step"
DONOR_MID = ROOT / "references/pg3-c9/PG3_C92_J28/CAD/C92_J28_mid.step"
POSES = {"open": 25, "mid": 90, "closed": 135}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bbox(shape: cq.Shape) -> list[float]:
    box = shape.BoundingBox()
    return [box.xmin, box.ymin, box.zmin, box.xmax, box.ymax, box.zmax]


def _reload_part(shape: cq.Shape, name: str, out: Path) -> tuple[cq.Shape, dict]:
    step = out / f"{name}_CANDIDATE.step"
    stl = out / f"{name}_CANDIDATE.stl"
    cq.exporters.export(shape, str(step))
    cq.exporters.export(shape, str(stl), tolerance=0.02, angularTolerance=0.1)
    reloaded = cq.importers.importStep(str(step)).val()
    if not reloaded.isValid() or len(reloaded.Solids()) != 1:
        raise ValueError(f"STEP roundtrip is not one valid solid: {name}")
    volume_error = abs(shape.Volume() - reloaded.Volume())
    bbox_error = max(abs(a - b) for a, b in zip(_bbox(shape), _bbox(reloaded)))
    if volume_error > 0.01 or bbox_error > 0.01:
        raise ValueError(f"STEP roundtrip geometry changed: {name}")
    mesh = trimesh.load_mesh(stl, force="mesh")
    return reloaded, {
        "step": step.name,
        "step_sha256": _sha256(step),
        "stl": stl.name,
        "stl_sha256": _sha256(stl),
        "source_volume_mm3": shape.Volume(),
        "reloaded_volume_mm3": reloaded.Volume(),
        "roundtrip_volume_error_mm3": volume_error,
        "roundtrip_bbox_error_mm": bbox_error,
        "stl_watertight": bool(mesh.is_watertight),
        "stl_winding_consistent": bool(mesh.is_winding_consistent),
        "stl_body_count": int(mesh.body_count),
        "stl_mesh_volume_mm3": float(mesh.volume),
    }


def _pose_shapes(model: PG3Model, angle: int, p05_windows: cq.Shape) -> dict[str, cq.Shape]:
    shapes = assemble(model, angle)
    shapes = {name: shape for name, shape in shapes.items() if not name.startswith("CAMERA_")}
    if "ARM_P05_wrist_XL430" not in shapes:
        raise ValueError("P05 occurrence missing from ID5 arm candidate")
    shapes["ARM_P05_wrist_XL430"] = p05_windows
    return shapes


def mount_ray_hits(
    origin: tuple[float, float, float],
    target_box,
    parts: dict[str, cq.Shape],
    ray_radius_mm: float = 0.1,
) -> list[dict]:
    """B-rep occlusion probes from the provisional lens point to target box corners."""
    start = cq.Vector(*origin)
    hits = []
    for index, point in enumerate(corners(target_box)):
        vector = cq.Vector(*point) - start
        length = vector.Length
        direction = vector.normalized()
        ray = cq.Solid.makeCylinder(
            ray_radius_mm, length - 0.2, start + direction * 0.1, direction
        )
        for name, part in parts.items():
            volume = common_volume(ray, part)
            if volume > 1e-4:
                hits.append({"corner": index, "mount_part": name, "ray_volume_mm3": volume})
    return hits


def export_candidate(out: Path) -> dict:
    """Produce candidate-only artifacts; no fabrication or physical fit approval."""
    if out.exists():
        raise FileExistsError(out)
    candidate = build_candidate()
    geometry = validate_candidate(candidate)
    if common_volume(candidate["base"], candidate["camera_carrier"]) > 1e-4:
        raise ValueError("camera mount parts intersect one another")
    out.mkdir(parents=True)

    reloaded = {}
    part_reports = {}
    for name in ("base", "camera_carrier"):
        reloaded[name], part_reports[name] = _reload_part(candidate[name], name, out)
    validate_candidate({**candidate, **reloaded})
    if any(
        not row["stl_watertight"] or not row["stl_winding_consistent"]
        for row in part_reports.values()
    ):
        raise ValueError("STL export is not watertight and consistently wound")

    mid_rows = read_step(MID_STEP)[2]
    mid_shapes = {row.name: row.world for row in mid_rows if not row.name.startswith("CAMERA_")}
    if len(mid_shapes) != len(mid_rows) - 21:
        raise ValueError("saved mid occurrence inventory or old camera count changed")
    p05_windows = mid_shapes["ARM_P05_wrist_XL430"]
    model = PG3Model()
    pose_reports = {}
    for pose_name, angle in POSES.items():
        shapes = mid_shapes if pose_name == "mid" else _pose_shapes(model, angle, p05_windows)
        case_report = validate_id5_case_anchor(shapes["PG3_XL430_fixed"])
        hits, errors = collision_rows(reloaded, shapes)
        if hits or errors:
            raise ValueError(
                f"mount/arm interference in {pose_name}: {hits}; kernel errors: {errors}"
            )
        mount_occlusion = {
            side: mount_ray_hits(
                candidate["optical_origin"], shapes[f"PG3_pad_{side}"].BoundingBox(), reloaded
            )
            for side in ("L", "R")
        }
        if any(mount_occlusion.values()):
            raise ValueError(f"candidate mount blocks diagnostic pad rays in {pose_name}: {mount_occlusion}")
        full = cq.Assembly(name=f"ID5_CAMERA_{pose_name.upper()}_UNVALIDATED")
        for name, shape in shapes.items():
            full.add(shape, name=name)
        full.add(
            reloaded["base"], name="ID5_CAMERA_CASE_BASE_CANDIDATE", color=cq.Color(0.1, 0.6, 0.65)
        )
        full.add(
            reloaded["camera_carrier"],
            name="ID5_CAMERA_28MM_CARRIER_CANDIDATE",
            color=cq.Color(0.85, 0.45, 0.12),
        )
        output_step = out / f"ID5_{pose_name}_camera_mount_CANDIDATE.step"
        full.save(str(output_step))
        pose_reports[pose_name] = {
            "pg3_angle_deg": angle,
            "retained_occurrences_without_old_P05_camera": len(shapes),
            "case_top_holes": case_report,
            "mount_vs_arm_collisions": hits,
            "mount_vs_arm_boolean_errors": errors,
            "diagnostic_mount_ray_hits_to_pad_bbox_corners": mount_occlusion,
            "output_step": output_step.name,
            "output_step_sha256": _sha256(output_step),
        }

    baseline = json.loads(MID_REVIEW.read_text(encoding="utf-8"))
    report = {
        "scope": "CAD-only, provisional ID5 case-top camera mount; not a physical fit or print approval",
        "inputs_sha256": {
            "spec": _sha256(SPEC_PATH),
            "source_arm": _sha256(ARM_STEP),
            "pg3_donor_mid": _sha256(DONOR_MID),
            "saved_mid_candidate": _sha256(MID_STEP),
            "saved_mid_review": _sha256(MID_REVIEW),
        },
        "mount_geometry": geometry,
        "mount_parts_common_volume_mm3": common_volume(
            reloaded["base"], reloaded["camera_carrier"]
        ),
        "parts": part_reports,
        "poses": pose_reports,
        "prior_arm_review": {
            "path": str(MID_REVIEW.relative_to(ROOT)),
            "status": "unresolved; new mount checks do not erase previous ERROR/UNKNOWN",
            "summary": baseline.get("summary"),
        },
        "camera_model_confirmed": False,
        "physical_id_mapping_verified": False,
        "fasteners_and_tool_confirmed": False,
        "cable_route_confirmed": False,
        "structural_strength_confirmed": False,
        "fabrication_approved": False,
        "gcode_allowed": False,
        "powered_operation_approved": False,
    }
    for part in part_reports.values():
        if not math.isfinite(part["stl_mesh_volume_mm3"]):
            raise ValueError("non-finite STL mesh volume")
    (out / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = export_candidate(args.out)
    print(json.dumps({"parts": result["parts"], "poses": result["poses"]}, indent=2))
