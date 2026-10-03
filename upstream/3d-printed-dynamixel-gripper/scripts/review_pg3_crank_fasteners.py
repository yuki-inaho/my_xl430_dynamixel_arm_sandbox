"""Nominal crank mounting contact; physical fasteners remain unapproved."""

import argparse
import json
import math
from pathlib import Path

import cadquery as cq
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_OUT

from gripper_design.pg2 import digest
from gripper_design.pg3 import group_for
from scripts.assembly_io import bounds, read_step
from scripts.review_pg3_motion_clearance import EPSILON_MM, verify_axial_motion_contract
from scripts.review_pg3_motor_partition import PADDING, VOLUME_TOL, partition_face, radial_distance
from scripts.review_pg3_pivot_stacks import pick, profiles
from scripts.review_pg3_washer_contacts import (
    EvidenceError,
    controlled_containment,
    cylinder,
    finite_solid,
    opposed_seat,
)


def inspect_cylinder_region(host, profile):
    """A connected cylinder core is empty if no boundary enters and one point is OUT.

    Account for EVERY host face; partition only its axial span, never its radial
    coverage. Boundary end slabs remain possible material and consume the volume
    budget. Point classification is not a sampled collision test: the all-face
    exclusion is what makes one point determine the connected core's occupancy.
    """
    finite_solid(host)
    low, high = profile["span_x_mm"]
    centre, radius = profile["axis_yz_mm"], profile["radius_mm"] + 2 * PADDING
    if not all(math.isfinite(v) for v in (low, high, radius, *centre)) or high <= low:
        raise ValueError("finite nonempty cylinder required")
    core_low, core_high = low, high
    axis = cq.Edge.makeLine((low - 1, *centre), (high + 1, *centre))
    rows = []
    for index, original in enumerate(host.Faces()):
        bb = bounds(original)
        row = {"face": index, "bbox_mm": bb}
        if bb[3] <= low + PADDING:
            core_low = max(core_low, bb[3])
            row.update(method="outside_axial_span", clear=True)
        elif bb[0] >= high - PADDING:
            core_high = min(core_high, bb[0])
            row.update(method="outside_axial_span", clear=True)
        else:
            whole_distance = radial_distance(original, axis)
            if whole_distance - PADDING > radius + EPSILON_MM:
                row.update(
                    method="whole_face_radial_distance", axis_distance_mm=whole_distance, clear=True
                )
                rows.append(row)
                continue
            face = original
            splits = []
            if bb[0] < low:
                try:
                    face, proof = partition_face(face, low)
                except Exception as exc:
                    raise EvidenceError(f"face {index} low split: {exc}") from exc
                core_low = max(core_low, proof["back_max_x_mm"])
                splits.append({"end": "low", **proof})
            if bounds(face)[3] > high:
                reflected = face.rotate((0, 0, 0), (0, 1, 0), 180)
                try:
                    reflected, proof = partition_face(reflected, -high)
                except Exception as exc:
                    raise EvidenceError(f"face {index} high split: {exc}") from exc
                face = reflected.rotate((0, 0, 0), (0, 1, 0), -180)
                core_high = min(core_high, -proof["back_max_x_mm"])
                splits.append({"end": "high_reflected", **proof})
            distance = radial_distance(face, axis)
            row.update(
                method="all_axial_face_material",
                partitions=splits,
                axis_distance_mm=distance,
                clear=distance - PADDING > radius + EPSILON_MM,
            )
        rows.append(row)
    core_low += PADDING
    core_high -= PADDING
    classifier = BRepClass3d_SolidClassifier(host.Solids()[0].wrapped)
    classifier.Perform(gp_Pnt((core_low + core_high) / 2, *centre), PADDING)
    outside = classifier.State() == TopAbs_OUT
    empty = core_high > core_low and all(r["clear"] for r in rows) and outside
    slab = math.pi * radius**2 * max(0, high - low - max(0, core_high - core_low))
    return {
        "status": "BOUNDED_REGION" if empty and slab <= VOLUME_TOL else "UNPROVEN",
        "nominal_partition_pass": empty and slab <= VOLUME_TOL,
        "all_boundary_faces": rows,
        "core_span_x_mm": [core_low, core_high],
        "core_anchor_outside": outside,
        "contact_volume_upper_bound_mm3": slab if empty else None,
        "enclosing_radius_mm": radius,
    }


def inspect_bolt(host, bolt):
    result = {
        "status": "UNPROVEN",
        "nominal_contact_pass": False,
        "actual_threads_verified": False,
        "installation_approved": False,
        "positive_clearance_proven": False,
    }
    try:
        finite_solid(host)
        finite_solid(bolt)
        rows = profiles(bolt)
        shank, head = pick(rows, 1, "convex"), pick(rows, 1.9, "convex")
        centre = shank["axis_yz_mm"]
        bore = pick(profiles(host), 1.15, "concave", centre)
        axis_error = max(math.dist(r["axis_yz_mm"], centre) for r in (head, bore))
        parts = {"shank": cylinder(shank), "head": cylinder(head)}
        cover = parts["shank"].fuse(parts["head"])
        containment = controlled_containment(bolt, cover)
        # No lost screw material may consume an unrecorded extra volume budget.
        enclosed = containment["pass"] and containment["residuals_mm3"][0] == 0
        try:
            checks = {
                name: inspect_cylinder_region(host, p)
                for name, p in (("shank", shank), ("head", head))
            }
        except Exception as exc:
            raise EvidenceError(f"boundary evaluation failed: {exc}") from exc
        seat = head["span_x_mm"][0]
        contact = opposed_seat(host, bolt, seat, math.pi * (1.9**2 - 1.15**2))
        volume = sum(r.get("contact_volume_upper_bound_mm3") or 0 for r in checks.values())
        all_bounded = all(r["nominal_partition_pass"] for r in checks.values())
        passed = (
            enclosed
            and axis_error < 1e-6
            and abs(shank["span_x_mm"][1] - seat) < 1e-6
            and abs(bore["span_x_mm"][1] - seat) < 1e-6
            and contact["pass_contact"]
            and all_bounded
            and volume <= VOLUME_TOL
        )
        result.update(
            status="BOUNDED_NOMINAL_CONTACT" if passed else "UNPROVEN",
            nominal_contact_pass=passed,
            complete_screw_containment=containment,
            boundary_checks=checks,
            host_face_count=len(host.Faces()),
            contact=contact,
            axis_error_mm=axis_error,
            summed_contact_volume_upper_bound_mm3=volume if all_bounded else None,
            volume_tolerance_mm3=VOLUME_TOL,
            scope="complete nominal screw versus complete crank; not physical thread or PLA strength",
        )
    except EvidenceError as exc:
        result.update(status="ERROR", reason=str(exc))
    except ValueError as exc:
        result["reason"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        result.update(status="ERROR", reason=str(exc))
    return result


def run(checkpoint, out):
    if out.exists():
        raise FileExistsError(out)
    contract = verify_axial_motion_contract()
    manifest = json.loads((checkpoint / "review.json").read_text())
    names = [f"PG3_horn_bolt_{i}" for i in range(4)]
    if any(group_for(n.removeprefix("PG3_")) != "drive" for n in ["PG3_crank", *names]):
        raise ValueError("not the reviewed common rigid drive group")
    report = {"poses": {}, "motion_contract": contract, "installation_approved": False}
    for pose in ("open", "mid", "closed"):
        path = checkpoint / f"arm_camera_{pose}_CANDIDATE.step"
        if digest(path) != manifest["output_sha256"][path.name]:
            raise ValueError("saved assembly SHA mismatch")
        rows = read_step(path)[2]
        shapes = {r.name: r.world for r in rows}
        if len(rows) != len(shapes):
            raise ValueError("ambiguous occurrences")
        checks, negatives = {}, {}
        for name in names:
            checks[name] = inspect_bolt(shapes["PG3_crank"], shapes[name])
            for label, shift in (("axial", (-0.5, 0, 0)), ("lateral", (0, 0.3, 0))):
                negatives[f"{name}_{label}"] = inspect_bolt(
                    shapes["PG3_crank"], shapes[name].translate(shift)
                )
            print(pose, name, checks[name]["status"], flush=True)
        negative_ok = all(r["status"] == "UNPROVEN" for r in negatives.values())
        report["poses"][pose] = {
            "assembly_sha256": digest(path),
            "checks": checks,
            "negative_controls": negatives,
            "negative_controls_rejected": negative_ok,
            "accepted": negative_ok and all(r["nominal_contact_pass"] for r in checks.values()),
        }
    verify_axial_motion_contract()
    report["checker_sha256"] = digest(Path(__file__))
    report["dependencies"] = {
        n: digest(Path(n))
        for n in (
            "gripper_design/pg2.py",
            "gripper_design/pg3.py",
            "gripper_design/interface_envelopes.py",
            "gripper_design/rotational_envelopes.py",
            "scripts/assembly_io.py",
            "scripts/review_pg3_motor_partition.py",
            "scripts/review_pg3_motion_clearance.py",
            "scripts/review_pg3_washer_contacts.py",
            "scripts/review_pg3_pivot_stacks.py",
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
