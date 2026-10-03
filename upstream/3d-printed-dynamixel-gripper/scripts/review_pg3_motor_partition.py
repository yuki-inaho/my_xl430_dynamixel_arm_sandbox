"""Check the displayed fixed/horn partition without trusting whole-solid Booleans."""

import argparse
import json
import math
from pathlib import Path

import cadquery as cq

from gripper_design.interface_envelopes import axial_ray_cover
from gripper_design.pg2 import digest
from gripper_design.rotational_envelopes import rotational_cover
from scripts.assembly_io import bounds, read_step
from scripts.review_pg3_motion_clearance import EPSILON_MM, verify_axial_motion_contract

VOLUME_TOL = 1e-4
PADDING = 1e-7


def area(shape):
    value = shape.Area()
    if not shape.isValid() or not math.isfinite(value) or value < 0:
        raise ValueError("invalid or nonfinite face area")
    return value


def face_control(shape):
    value = area(shape)
    cut = area(shape.cut(shape.copy()))
    common = area(shape.intersect(shape.copy()))
    if cut != 0 or abs(common - value) > PADDING:
        raise ValueError("face self-control failed")
    return {"area_mm2": value, "self_cut_area_mm2": cut, "self_common_area_mm2": common}


def partition_face(face, plane):
    """Explicit face partition with controls, conservation and two-way residuals.

    The box covers the complete radial/forward extent; no radial region is cut
    away. Zero-area shared edges lie on the partition and add no material volume.
    """
    bb = bounds(face)
    clip = cq.Solid.makeBox(
        bb[3] + 1 - plane,
        bb[4] - bb[1] + 2,
        bb[5] - bb[2] + 2,
        (plane, bb[1] - 1, bb[2] - 1),
    )
    source_control = face_control(face)
    front, back = face.intersect(clip), face.cut(clip)
    controls = {"front": face_control(front), "back": face_control(back)}
    if not front.Faces() or area(front) <= 0:
        raise ValueError("missing forward boundary")
    union = front.fuse(back) if back.Faces() else front
    controls["union"] = face_control(union)
    residual = [area(face.cut(union)), area(union.cut(face)), area(front.intersect(back))]
    conservation = abs(area(front) + area(back) - area(face))
    if any(v != 0 for v in residual) or conservation > PADDING:
        raise ValueError("face partition loses, adds or double-counts boundary")
    front_min = bounds(front)[0]
    back_max = bounds(back)[3] if back.Faces() else plane
    if front_min < plane - PADDING or back_max > plane + PADDING:
        raise ValueError("face partition is on the wrong side")
    return front, {
        "source_control": source_control,
        "piece_controls": controls,
        "residual_areas_mm2": residual,
        "conservation_error_mm2": conservation,
        "front_min_x_mm": front_min,
        "back_max_x_mm": back_max,
        "cut_plane_x_mm": plane,
    }


def radial_distance(face, axis):
    value = face.distance(axis)
    if not math.isfinite(value) or value < 0:
        raise ValueError("invalid boundary-axis distance")
    return value


def inspect_partition(fixed, horn, centre=(234.9, 164.6), radius=10.3):
    result = {
        "status": "UNPROVEN",
        "nominal_partition_pass": False,
        "physical_motor_interface_approved": False,
        "installation_approved": False,
    }
    try:
        _, envelope = rotational_cover(horn, 0, centre, radius)
        _, validation = axial_ray_cover(fixed)
        plane = bounds(horn)[0]
        bb = bounds(fixed)
        axis = cq.Edge.makeLine((bb[0] - 1, *centre), (bb[3] + 1, *centre))
        effective_plane, checks = plane, []
        for index, face in enumerate(fixed.Faces()):
            fb = bounds(face)
            row = {"face": index, "kind": face.geomType(), "bbox_mm": fb}
            if fb[3] <= plane + PADDING:
                effective_plane = max(effective_plane, fb[3])
                row.update(method="entire_face_behind_plane", excluded_forward=False)
            else:
                distance = radial_distance(face, axis)
                row.update(method="whole_face_radial_distance", axis_distance_mm=distance)
                if distance - PADDING <= radius + EPSILON_MM and fb[0] < plane - PADDING:
                    front, split = partition_face(face, plane)
                    distance = radial_distance(front, axis)
                    effective_plane = max(effective_plane, split["back_max_x_mm"])
                    row.update(method="controlled_forward_face_partition", partition=split)
                row["forward_radial_gap_lower_bound_mm"] = distance - PADDING - radius
                row["excluded_forward"] = distance - PADDING > radius + EPSILON_MM
            checks.append(row)
        # Below this plane, count the ENTIRE horn cylinder slab as possible
        # intersection. Boundary padding is not discarded as zero thickness.
        effective_plane += PADDING
        low, high = envelope["axial_span_mm"]
        thickness = max(0, min(high, effective_plane) - low)
        slab_volume = math.pi * radius**2 * thickness
        forward_proven = all(
            r["method"] == "entire_face_behind_plane" or r["excluded_forward"] for r in checks
        )
        passed = forward_proven and math.isfinite(slab_volume) and slab_volume <= VOLUME_TOL
        result.update(
            status="BOUNDED_PARTITION_CONTACT" if passed else "UNPROVEN",
            nominal_partition_pass=passed,
            horn_envelope=envelope,
            fixed_source_face_count=len(fixed.Faces()),
            fixed_infinite_point_outside=validation["all_solids_infinite_point_outside"],
            all_boundary_faces=checks,
            effective_plane_x_mm=effective_plane,
            possible_contact_slab_thickness_mm=thickness,
            contact_volume_upper_bound_mm3=slab_volume if forward_proven else None,
            forward_region_proven_empty=forward_proven,
            volume_tolerance_mm3=VOLUME_TOL,
            padding_mm=PADDING,
            positive_clearance_proven=False,
            basis="every positive-X ray from finite material exits an accounted boundary face",
            scope="nominal displayed partition under any rotation about the declared fixed X axis",
            whole_solid_boolean_used=False,
        )
    except Exception as exc:  # noqa: BLE001
        result.update(status="ERROR", reason=str(exc))
    return result


def run(checkpoint, out):
    if out.exists():
        raise FileExistsError(out)
    contract = verify_axial_motion_contract()
    manifest = json.loads((checkpoint / "review.json").read_text())
    report = {"poses": {}, "motion_contract": contract, "installation_approved": False}
    for pose in ("open", "mid", "closed"):
        path = checkpoint / f"arm_camera_{pose}_CANDIDATE.step"
        if digest(path) != manifest["output_sha256"][path.name]:
            raise ValueError("saved input SHA mismatch")
        rows = read_step(path)[2]
        shapes = {r.name: r.world for r in rows}
        if len(shapes) != len(rows):
            raise ValueError("ambiguous occurrences")
        fixed, horn = shapes["PG3_XL430_fixed"], shapes["PG3_XL430_horn"]
        check = inspect_partition(fixed, horn)
        intrusion = cq.Solid.makeBox(1, 1, 1, (17, 234.4, 164.1))
        extra = cq.Compound.makeCompound([*fixed.Solids(), intrusion])
        negative = {
            "horn_behind_partition_0p2mm": inspect_partition(fixed, horn.translate((-0.2, 0, 0))),
            "additional_fixed_material_in_sweep": inspect_partition(extra, horn),
        }
        negative_ok = all(n["status"] == "UNPROVEN" for n in negative.values())
        report["poses"][pose] = {
            "assembly_sha256": digest(path),
            "check": check,
            "negative_controls": negative,
            "negative_controls_rejected": negative_ok,
            "bounded_partition_accepted": check["nominal_partition_pass"] and negative_ok,
        }
        print(pose, check["status"], "negative", negative_ok, flush=True)
    verify_axial_motion_contract()
    report["checker_sha256"] = digest(Path(__file__))
    report["dependencies"] = {
        n: digest(Path(n))
        for n in (
            "gripper_design/interface_envelopes.py",
            "gripper_design/rotational_envelopes.py",
            "gripper_design/pg2.py",
            "gripper_design/pg3.py",
            "scripts/assembly_io.py",
            "scripts/review_pg3_motion_clearance.py",
            "uv.lock",
        )
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
