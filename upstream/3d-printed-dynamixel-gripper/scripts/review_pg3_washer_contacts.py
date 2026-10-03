"""Nominal shoulder/washer seating, kept separate from positive clearance."""

import argparse
import json
import math
from pathlib import Path

import cadquery as cq
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.TopAbs import TopAbs_OUT

from gripper_design.pg2 import _solid_only, digest
from scripts.assembly_io import bounds, read_step
from scripts.review_pg3_motion_clearance import verify_axial_motion_contract
from scripts.review_pg3_pivot_stacks import pick, planar_contact, profiles

LINEAR_TOL = 1e-6
VOLUME_TOL = 1e-4
AREA_TOL = 1e-5


class EvidenceError(ValueError):
    """A failed measurement cannot establish acceptance or a negative control."""


def finite_solid(shape):
    if not shape.isValid() or not _solid_only(shape) or len(shape.Solids()) != 1:
        raise ValueError("one valid solid required")
    classifier = BRepClass3d_SolidClassifier(shape.Solids()[0].wrapped)
    classifier.PerformInfinitePoint(1e-7)
    if classifier.State() != TopAbs_OUT or not math.isfinite(shape.Volume()) or shape.Volume() <= 0:
        raise ValueError("finite outward-oriented material required")


def controlled_containment(shape, cover, equal=False):
    controls = []
    for solid in (shape, cover):
        finite_solid(solid)
        cut, common = solid.cut(solid.copy()), solid.intersect(solid.copy())
        if not cut.isValid() or not common.isValid():
            raise EvidenceError("invalid containment self-control")
        controls.append({"self_cut_mm3": abs(cut.Volume()), "self_common_mm3": common.Volume()})
        if (
            not all(math.isfinite(v) for v in controls[-1].values())
            or abs(cut.Volume()) > VOLUME_TOL
            or abs(common.Volume() - solid.Volume()) > VOLUME_TOL
        ):
            raise EvidenceError("containment self-control failed")
    outside, inside = shape.cut(cover), shape.intersect(cover)
    missing = cover.cut(shape) if equal else None
    if not outside.isValid() or not inside.isValid() or (equal and not missing.isValid()):
        raise EvidenceError("invalid containment Boolean")
    values = [abs(outside.Volume()), abs(inside.Volume() - shape.Volume())]
    if equal:
        values.append(abs(missing.Volume()))
    if not all(math.isfinite(v) for v in values):
        raise EvidenceError("nonfinite containment volume")
    return {"pass": max(values) <= VOLUME_TOL, "residuals_mm3": values, "controls": controls}


def cylinder(profile):
    low, high = profile["span_x_mm"]
    return cq.Solid.makeCylinder(
        profile["radius_mm"], high - low, (low, *profile["axis_yz_mm"]), (1, 0, 0)
    )


def opposed_seat(first, second, coordinate, expected_area):
    try:
        contact = planar_contact(first, second, coordinate)
    except ValueError as exc:
        raise EvidenceError(str(exc)) from exc
    normals = []
    for ai in contact["first_faces"]:
        for bi in contact["second_faces"]:
            a, b = first.Faces()[ai], second.Faces()[bi]
            common = a.intersect(b)
            if not common.isValid() or not math.isfinite(common.Area()):
                raise EvidenceError("invalid seat common face")
            if common.Area() > AREA_TOL:
                # Planar normals are constant; face centres need not lie in the annulus.
                na, nb = a.normalAt(), b.normalAt()
                normals.append({"first_x": na.x, "second_x": nb.x, "dot": na.dot(nb)})
    contact.update(
        expected_area_mm2=expected_area,
        normals=normals,
        pass_contact=bool(normals)
        and expected_area > 0
        and abs(contact["common_area_mm2"] - expected_area) <= AREA_TOL
        and all(n["first_x"] > 1 - 1e-8 and n["second_x"] < -1 + 1e-8 for n in normals),
    )
    return contact


def inspect_washer_contact(host, bolt, washer, side, angle):
    contract = verify_axial_motion_contract()
    result = {
        "status": "UNPROVEN",
        "nominal_contact_pass": False,
        "installation_approved": False,
        "physical_free_motion_verified": False,
        "axial_motion_contract": contract,
    }
    try:
        if side not in ("L", "R") or not math.isfinite(angle) or not 25 <= angle <= 135:
            raise ValueError("explicit side and relative opening angle 25..135 required")
        for shape in (host, bolt, washer):
            finite_solid(shape)
        wp, bp, hp = profiles(washer), profiles(bolt), profiles(host)
        outer, bore = pick(wp, 3.5, "convex"), pick(wp, 1.1, "concave")
        centre = outer["axis_yz_mm"]
        shoulder = pick(hp, 2.5, "convex", centre)
        shoulder_bore = pick(hp, 1.15, "concave", centre)
        shank, head = pick(bp, 1, "convex"), pick(bp, 1.9, "convex")
        low, high = outer["span_x_mm"]
        expected_axis = (
            234.9 + (1 if side == "R" else -1) * 14 * math.sin(math.radians(angle)),
            164.6 - (1 if side == "R" else -1) * 14 * math.cos(math.radians(angle)),
        )
        axis_error = max(
            math.dist(row["axis_yz_mm"], expected_axis)
            for row in (outer, bore, shoulder, shoulder_bore, shank, head)
        )
        if (
            len(washer.Faces()) != 4
            or len(wp) != 2
            or axis_error > LINEAR_TOL
            or abs(high - low - 0.5) > LINEAR_TOL
            or max(abs(a - b) for a, b in zip(bore["span_x_mm"], (low, high))) > LINEAR_TOL
        ):
            raise ValueError("complete nominal annular washer or trajectory mismatch")
        annulus = cylinder(outer).cut(cylinder(bore))
        symmetry = controlled_containment(washer, annulus, equal=True)
        bolt_cover = cylinder(shank).fuse(cylinder(head))
        containment = controlled_containment(bolt, bolt_cover)
        seat = shank["span_x_mm"][1]
        shoulder_contact = opposed_seat(
            host,
            washer,
            low,
            math.pi * (shoulder["radius_mm"] ** 2 - shoulder_bore["radius_mm"] ** 2),
        )
        head_contact = opposed_seat(
            washer, bolt, high, math.pi * (head["radius_mm"] ** 2 - bore["radius_mm"] ** 2)
        )
        # The complete crank is behind the washer. The complete bolt lies in
        # a head ahead of it plus a shank within its proven full-span bore.
        host_gap = low - bounds(host)[3]
        head_gap = head["span_x_mm"][0] - high
        radial_gap = (
            bore["radius_mm"]
            - shank["radius_mm"]
            - math.dist(bore["axis_yz_mm"], shank["axis_yz_mm"])
        )
        seat_errors = [
            abs(low - shoulder["span_x_mm"][1]),
            abs(high - seat),
            abs(seat - head["span_x_mm"][0]),
        ]
        passed = (
            symmetry["pass"]
            and containment["pass"]
            and shoulder_contact["pass_contact"]
            and head_contact["pass_contact"]
            and host_gap >= -LINEAR_TOL
            and head_gap >= -LINEAR_TOL
            and radial_gap >= 0.1 - LINEAR_TOL
            and max(seat_errors) <= LINEAR_TOL
        )
        result.update(
            status="NOMINAL_CONTACT" if passed else "UNPROVEN",
            nominal_contact_pass=passed,
            washer_annulus_equivalence=symmetry,
            complete_bolt_containment=containment,
            shoulder_contact=shoulder_contact,
            head_contact=head_contact,
            host_to_washer_axial_gap_mm=host_gap,
            head_to_washer_axial_gap_mm=head_gap,
            shank_to_bore_radial_gap_mm=radial_gap,
            axis_trajectory_error_mm=axis_error,
            seat_errors_mm=seat_errors,
            washer_span_x_mm=[low, high],
            expected_axis_yz_mm=list(expected_axis),
            scope="nominal_geometry_all_opening_angles_fixed_upstream_arm",
            invariant_basis=(
                "verified annulus is invariant under spin about its own X axis; "
                "pin translation and drive rotation map its centre to the same signed "
                "R14 trajectory; whole-host bounds, bolt cover and opposed seating "
                "are preserved by the common rigid drive transform"
            ),
            tolerances={"linear_mm": LINEAR_TOL, "volume_mm3": VOLUME_TOL, "area_mm2": AREA_TOL},
            limits=[
                "nominal contact classification, not positive-clearance certificate",
                "numerical annulus equivalence within stated tolerances, not exact set identity",
                "actual washer bending, PLA compression/creep and screw preload unverified",
                "link clearance is separate; neither smooth shank nor nut proves threads",
            ],
        )
    except EvidenceError as exc:
        result.update(status="ERROR", reason=str(exc))
    except ValueError as exc:
        result["reason"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        result.update(status="ERROR", reason=f"kernel evaluation failed: {exc}")
    verify_axial_motion_contract()
    return result


def run(checkpoint, out):
    if out.exists():
        raise FileExistsError(out)
    manifest = json.loads((checkpoint / "review.json").read_text())
    report = {"poses": {}, "installation_approved": False, "clearance_ledger_modified": False}
    for pose, angle in (("open", 25), ("mid", 90), ("closed", 135)):
        path = checkpoint / f"arm_camera_{pose}_CANDIDATE.step"
        if digest(path) != manifest["output_sha256"][path.name]:
            raise ValueError("saved assembly SHA mismatch")
        rows = read_step(path)[2]
        shapes = {r.name: r.world for r in rows}
        if len(shapes) != len(rows):
            raise ValueError("ambiguous occurrence identity")
        checks, negative = {}, {}
        for side in ("L", "R"):
            host = shapes["PG3_crank"]
            washer = shapes[f"PG3_pivot_drive_{side}_washer"]
            bolt = shapes[f"PG3_pivot_drive_{side}_bolt"]
            checks[side] = inspect_washer_contact(host, bolt, washer, side, angle)
            fixtures = {
                "washer_into_shoulder": (host, bolt, washer.translate((-0.2, 0, 0))),
                "washer_axis_offset": (host, bolt, washer.translate((0, 0.2, 0))),
                "bolt_head_into_washer": (host, bolt.translate((-0.2, 0, 0)), washer),
            }
            for name, args in fixtures.items():
                negative[f"{side}_{name}"] = inspect_washer_contact(*args, side, angle)
        negative_ok = all(v["status"] == "UNPROVEN" for v in negative.values())
        report["poses"][pose] = {
            "assembly_sha256": digest(path),
            "angle_deg": angle,
            "sides": checks,
            "negative_controls": negative,
            "negative_controls_rejected": negative_ok,
            "nominal_contacts_accepted": negative_ok
            and all(v["nominal_contact_pass"] for v in checks.values()),
        }
        print(
            pose, {s: v["status"] for s, v in checks.items()}, "negative", negative_ok, flush=True
        )
    report["checker_sha256"] = digest(Path(__file__))
    report["dependencies"] = {
        n: digest(Path(n))
        for n in (
            "gripper_design/pg2.py",
            "gripper_design/pg3.py",
            "scripts/assembly_io.py",
            "scripts/review_pg3_motion_clearance.py",
            "scripts/review_pg3_pivot_stacks.py",
            "skills/cad-reverse-parametric/src/cadre/probes.py",
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
