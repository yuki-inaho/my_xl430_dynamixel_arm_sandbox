"""Conservative continuous PG3 opening clearance with the upstream arm fixed.

Distance between occupied sets is Lipschitz with the sum of their maximum point
speeds. A midpoint distance exceeding that bound times the half interval proves
separation throughout the interval. Failure to prove is not proof of collision.
"""

import argparse
import json
import math
from collections import Counter
from functools import lru_cache
from itertools import combinations
from pathlib import Path

import cadquery as cq
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

from gripper_design.pg2 import _solid_only, digest
from gripper_design.pg3 import GROUPS, group_for, group_transform, to_arm
from scripts.assembly_io import bounds, read_step

EPSILON_MM = 1e-5
MIN_SPAN_RAD = math.radians(0.5)
KINEMATICS_PATH = Path(__file__).resolve().parents[1] / "gripper_design/pg3.py"
REVIEWED_PLANAR_SHA256 = "ac2da0e35e6665c5526ed03f02f1881c4edd8c69c1679c58add1810814b1b775"


class DistanceTo:
    """Exact minimum B-rep distance from many placements to one fixed shape.

    Same computation as ``cq.Shape.distance`` (BRepExtrema_DistShapeShape, default
    flags, multithreaded), but the fixed shape is loaded once, so its sub-shape
    maps and bounding volumes are not rebuilt for every sample of a motion sweep.
    """

    def __init__(self, fixed):
        self._calc = BRepExtrema_DistShapeShape()
        self._calc.SetMultiThread(True)
        self._calc.LoadS1(fixed.wrapped)

    def __call__(self, moving):
        self._calc.LoadS2(moving.wrapped)
        self._calc.Perform()
        if not self._calc.IsDone():
            raise ValueError("B-rep distance computation failed")
        return self._calc.Value()


def verify_axial_motion_contract(source=KINEMATICS_PATH):
    """Bind the all-angle planar-motion proof to the reviewed formulas and placement.

    All group_transform branches use only Rz and XY translation. to_arm maps
    construction Z to world X minus .2 mm. Therefore every point's world X is
    invariant, not just the sampled vertex positions. Any source change requires
    re-review; updating this digest without rechecking the formulas is invalid.
    """
    if digest(source) != REVIEWED_PLANAR_SHA256:
        raise ValueError("unreviewed PG3 kinematics: re-prove axial invariance before scanning")
    return {
        "kinematics_sha256": REVIEWED_PLANAR_SHA256,
        "world_axis": "X",
        "proof": "construction_Rz_and_XY_translation_then_Ry90_and_fixed_translation",
        "scope": "all_material_points_all_opening_angles_25_to_135_fixed_upstream_arm",
    }


def axial_gap_certificate(first_bounds, second_bounds):
    """Requires verify_axial_motion_contract before use as a motion certificate."""
    for bb in (first_bounds, second_bounds):
        if (
            len(bb) != 6
            or not all(math.isfinite(v) for v in bb)
            or any(bb[i] > bb[i + 3] for i in range(3))
        ):
            raise ValueError("finite ordered 3D bounds required")
    gap = max(first_bounds[0] - second_bounds[3], second_bounds[0] - first_bounds[3])
    if gap > EPSILON_MM:
        return {
            "status": "PROVEN_CLEAR",
            "method": "invariant_world_X_projection",
            "checks": 0,
            "certified_intervals": 1,
            "continuous_distance_lower_bound_mm": gap,
        }
    return None


def point_speed_bound(neutral, group):
    """Maximum material-point speed in mm per mechanism radian, 25..135deg.

    r=14,l=24. Slider |x'| <= r+r^2/(2*sqrt(l^2-r^2)). Link angle derivative
    |beta'| <= r/sqrt(l^2-r^2); its moving pin speed is r. An AABB encloses all
    points, including curved extrema not represented by topological vertices.
    """
    if group == "fixed":
        return 0.0
    if group in ("R", "L"):
        return 14 + 196 / (2 * math.sqrt(380))
    if group in ("pin_R", "pin_L"):
        return 14.0
    bb = bounds(neutral)
    x = max(abs(bb[0]), abs(bb[3]))
    if group == "drive":
        return math.hypot(x, max(abs(bb[1]), abs(bb[4])))
    if group in ("link_R", "link_L"):
        pivot_y = 14 if group == "link_R" else -14
        radius = math.hypot(x, max(abs(bb[1] - pivot_y), abs(bb[4] - pivot_y)))
        return 14 + 14 / math.sqrt(380) * radius
    raise ValueError(f"unknown motion group: {group}")


def certify_interval(distance_at, speed_bound, low, high, *, min_span=MIN_SPAN_RAD, max_checks=256):
    if (
        not all(math.isfinite(v) for v in (speed_bound, low, high, min_span))
        or speed_bound < 0
        or low >= high
        or min_span <= 0
        or not isinstance(max_checks, int)
        or max_checks < 1
    ):
        raise ValueError("finite nonnegative speed, ordered interval and positive budgets required")
    todo = [(low, high)]
    count, certified = 0, 0
    minimum = math.inf
    while todo:
        a, b = todo.pop()
        if count >= max_checks:
            reason = "evaluation_budget"
            break
        d = distance_at((a + b) / 2)
        if not math.isfinite(d) or d < 0:
            raise ValueError("invalid distance")
        count += 1
        minimum = min(minimum, d)
        if d > speed_bound * (b - a) / 2 + EPSILON_MM:
            certified += 1
            continue
        if d <= EPSILON_MM:
            reason = "midpoint_positive_separation_not_established"
            break
        if b - a <= min_span:
            reason = "subdivision_limit"
            break
        middle = (a + b) / 2
        # The midpoint alone already proves |t - middle| < (d - EPSILON_MM) / speed_bound
        # clear (same Lipschitz bound), so only the two uncovered remainders are
        # subdivided instead of both full halves. speed_bound > 0 here: with zero
        # speed, d > EPSILON_MM certified above and d <= EPSILON_MM stopped. The
        # radius gives up one more EPSILON_MM so float rounding of middle +/- radius
        # cannot open an unchecked sliver; radius < (b - a) / 2 keeps both remainders.
        radius = max(0.0, (d - 2 * EPSILON_MM) / speed_bound)
        todo.extend(((middle + radius, b), (a, middle - radius)))
    else:
        return {
            "status": "PROVEN_CLEAR",
            "checks": count,
            "certified_intervals": certified,
            "minimum_evaluated_distance_lower_bound_mm": minimum,
        }
    return {
        "status": "UNPROVEN",
        "reason": reason,
        "checks": count,
        "certified_intervals": certified,
        "unresolved_interval_rad": [a, b],
        "minimum_evaluated_distance_lower_bound_mm": minimum,
    }


def run(checkpoint, out):
    if out.exists():
        raise FileExistsError(out)
    axial_contract = verify_axial_motion_contract()
    path = checkpoint / "arm_camera_mid_CANDIDATE.step"
    manifest = json.loads((checkpoint / "review.json").read_text())
    if digest(path) != manifest["output_sha256"][path.name]:
        raise ValueError("checkpoint hash mismatch")
    loaded = read_step(path)[2]
    shapes = {r.name: r.world for r in loaded}
    if len(shapes) != len(loaded):
        raise ValueError("ambiguous occurrence identity")
    if {n[4:] for n in shapes if n.startswith("PG3_")} != set(GROUPS):
        raise ValueError("PG3 inventory mismatch")
    groups = {n: group_for(n[4:]) if n.startswith("PG3_") else "fixed" for n in shapes}
    neutral = {
        n: s.translate((0.2, -234.9, -164.6)).rotate((0, 0, 0), (0, 1, 0), -90)
        for n, s in shapes.items()
        if groups[n] != "fixed"
    }
    speeds = {n: point_speed_bound(neutral[n], groups[n]) if n in neutral else 0.0 for n in shapes}
    invalid = {n for n, s in shapes.items() if not s.isValid()}
    non_solids = {n for n, s in shapes.items() if not _solid_only(s)}
    axial_bounds = {n: bounds(s) for n, s in shapes.items()}
    for name in non_solids:
        # Keep the same enclosure margin used by at(), including surface-only parts.
        bb = axial_bounds[name]
        axial_bounds[name] = [v - 1e-5 if i < 3 else v + 1e-5 for i, v in enumerate(bb)]

    @lru_cache(maxsize=4096)
    def at(name, radians):
        shape = shapes[name]
        if groups[name] != "fixed":
            t = group_transform(groups[name], math.degrees(radians))
            angle = math.degrees(math.atan2(t[1, 0], t[0, 0]))
            shape = to_arm(
                neutral[name].rotate((0, 0, 0), (0, 0, 1), angle).translate(tuple(t[:3, 3]))
            )
        bb = bounds(shape)
        if name in non_solids:
            shape = cq.Solid.makeBox(
                *(bb[i + 3] - bb[i] + 2e-5 for i in range(3)), tuple(bb[i] - 1e-5 for i in range(3))
            )
            bb = bounds(shape)
        return shape, bb

    rows = []
    stationary = 0
    low, high = math.radians(25), math.radians(135)
    for a, b in combinations(sorted(shapes), 2):
        if groups[a] == groups[b] == "fixed":
            stationary += 1
            continue
        row = {"a": a, "b": b, "point_speed_bound_sum_mm_per_rad": speeds[a] + speeds[b]}
        if a in invalid or b in invalid:
            row.update(status="ERROR", reason="invalid_source_shape")
        elif groups[a] == groups[b]:
            row.update(
                status="RIGID_RELATION_UNCHANGED", reason="static_contact_acceptance_not_implied"
            )
        else:
            speed = speeds[a] + speeds[b]

            def distance_at(t, a=a, b=b, speed=speed):
                aa, ab = at(a, t)
                ba, bb = at(b, t)
                gap = math.sqrt(
                    sum(max(ab[i] - bb[i + 3], bb[i] - ab[i + 3], 0) ** 2 for i in range(3))
                )
                if gap > speed * (high - low) / 2 + EPSILON_MM:
                    return gap
                return aa.distance(ba)

            try:
                axial = axial_gap_certificate(axial_bounds[a], axial_bounds[b])
                if axial is not None:
                    row.update(axial)
                else:
                    row.update(method="point_speed_lipschitz")
                    row.update(certify_interval(distance_at, speed, low, high))
            except Exception as exc:  # noqa: BLE001
                row.update(status="ERROR", reason="distance_evaluation_failed", detail=str(exc))
        rows.append(row)
        if len(rows) % 500 == 0:
            print(len(rows), dict(Counter(r["status"] for r in rows)), flush=True)
    assert len(rows) + stationary == len(shapes) * (len(shapes) - 1) // 2
    # Do not publish a certificate if the source contract changed during the run.
    verify_axial_motion_contract()
    report = {
        "scope": "continuous_gripper_opening_25_to_135_degrees_fixed_upstream_arm_no_cables",
        "assembly_sha256": digest(path),
        "checker_sha256": digest(Path(__file__)),
        "dependencies": {
            p: digest(Path(p))
            for p in ("scripts/assembly_io.py", "gripper_design/pg2.py", "gripper_design/pg3.py")
        },
        "kinematics_source": "gripper_design.pg3.group_transform_applied_to_saved_mid_geometry",
        "axial_motion_contract": axial_contract,
        "distance_epsilon_mm": EPSILON_MM,
        "min_subdivision_degrees": 0.5,
        "max_checks_per_pair": 256,
        "occurrence_count": len(shapes),
        "non_solid_AABB_enclosures": sorted(non_solids),
        "stationary_pairs_not_reassessed": stationary,
        "motion_groups": groups,
        "point_speed_bounds_mm_per_rad": speeds,
        "counts": dict(Counter(r["status"] for r in rows)),
        "pairs": rows,
        "continuous_all_contacts_accepted": False,
        "installation_approved": False,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(report["counts"], flush=True)
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
