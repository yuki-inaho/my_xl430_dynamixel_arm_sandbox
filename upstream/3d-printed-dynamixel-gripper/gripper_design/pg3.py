"""PG3 C9 saved geometry, rigid motion and diagnostic R3 assembly placement.

Internal frame: X opening, Y up, Z forward (mm). Donor exports rotate it +90
degrees about X. Motor pose maps into R3 by Ry(90), then (-.2,234.9,164.6).
No donor code is imported; no implicit component classifications are allowed.
"""

import math
from pathlib import Path

import cadquery as cq
import numpy as np
from scipy.spatial import cKDTree

from camera_jig.build import CAMERA_ORIGIN, build_parts, donor_parts, envelope_hardware
from gripper_design.build import _source_rows
from gripper_design.pg2 import verify_intake
from scripts.assembly_io import bounds, read_step

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "references/pg3-c9/PG3_C92_J28"
GROUPS = {
    "frame": "fixed",
    "cap_U": "fixed",
    "cap_D": "fixed",
    "crank": "drive",
    "horn_spacer": "drive",
    "XL430_fixed": "fixed",
    "XL430_horn": "drive",
    "link_R": "link_R",
    "link_L": "link_L",
}
for side in ("R", "L"):
    for part in ("carriage", "finger", "pad"):
        GROUPS[f"{part}_{side}"] = side
    for part in ("bolt", "nut", "washer"):
        GROUPS[f"pivot_drive_{side}_{part}"] = "drive"
        GROUPS[f"pivot_carriage_{side}_{part}"] = side
        for y in (-14, 14):
            GROUPS[f"finger_{side}_{y}_{part}"] = side
for x in (-37.5, 37.5):
    for y in (-24.5, 24.5):
        for part in ("bolt", "nut", "washer"):
            GROUPS[f"cap_{x}_{y}_{part}"] = "fixed"
for i in range(4):
    GROUPS[f"horn_bolt_{i}"] = "drive"
for side in ("R", "L"):
    # Round retainers are constructed without spin in each saved donor pose.
    GROUPS[f"pivot_drive_{side}_washer"] = f"pin_{side}"
for x in (-11, 11):
    GROUPS[f"case_tapper_{x}"] = "fixed"


def group_for(name):
    if name not in GROUPS:
        raise ValueError(f"unknown PG3 occurrence: {name}")
    return GROUPS[name]


def position_mm(angle):
    if not math.isfinite(angle) or not 25 <= angle <= 135:
        raise ValueError("PG3 relative mechanism angle must be finite and within 25..135 deg")
    t = math.radians(angle)
    return 14 * math.cos(t) + math.sqrt(24**2 - (14 * math.sin(t)) ** 2)


def opening_mm(angle):
    return 2 * (position_mm(angle) - 10.5 - 1)


def group_transform(group, angle):
    x = position_mm(angle)
    t = math.radians(angle)
    pin = np.array([14 * math.cos(t), 14 * math.sin(t), 0.0])
    tform = np.eye(4)
    if group == "fixed":
        return tform
    if group in ("pin_R", "pin_L"):
        tform[:3, 3] = (1 if group == "pin_R" else -1) * (pin - np.array([0, 14, 0]))
        return tform
    if group in ("R", "L"):
        tform[0, 3] = (1 if group == "R" else -1) * (x - position_mm(90))
        return tform
    if group == "drive":
        delta = t - math.pi / 2
    elif group in ("link_R", "link_L"):
        delta = math.atan2(-pin[1], x - pin[0]) - math.atan2(-14, position_mm(90))
    else:
        raise ValueError(f"unknown rigid group: {group}")
    c, s = math.cos(delta), math.sin(delta)
    tform[:3, :3] = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    if group.startswith("link"):
        sign = 1 if group == "link_R" else -1
        tform[:3, 3] = sign * (pin - tform[:3, :3] @ np.array([0, 14, 0]))
    return tform


def to_arm(shape):
    return shape.rotate((0, 0, 0), (0, 1, 0), 90).translate((-0.2, 234.9, 164.6))


def shape_signature_difference(first, second):
    """Finite topology signature, not an exact Boolean-equivalence proof."""
    a = np.array([v.toTuple() for v in first.Vertices()])
    b = np.array([v.toTuple() for v in second.Vertices()])
    if len(a) == 0 or len(b) == 0:
        raise ValueError("shape has no vertices")
    distance = max(cKDTree(b).query(a)[0].max(), cKDTree(a).query(b)[0].max())
    return {
        "vertex_distance_mm": float(distance),
        "vertex_count_equal": len(a) == len(b),
        "face_count_equal": len(first.Faces()) == len(second.Faces()),
        "volume_error_mm3": abs(first.Volume() - second.Volume()),
        "area_error_mm2": abs(first.Area() - second.Area()),
    }


class PG3Model:
    def __init__(self, source=SOURCE):
        self.source = Path(source)
        self.receipt = verify_intake(self.source)
        rows = read_step(self.source / "CAD/C92_J28_mid.step")[2]
        if len(rows) != len(GROUPS) or {r.name for r in rows} != set(GROUPS):
            raise ValueError("PG3 occurrence inventory differs from reviewed C9")
        self.neutral = {r.name: r.world.rotate((0, 0, 0), (1, 0, 0), -90) for r in rows}

    def at(self, angle):
        result = {}
        for name, shape in self.neutral.items():
            transform = group_transform(group_for(name), angle)
            degrees = math.degrees(math.atan2(transform[1, 0], transform[0, 0]))
            result[name] = shape.rotate((0, 0, 0), (0, 0, 1), degrees).translate(
                tuple(transform[:3, 3])
            )
        return result

    def compare_saved(self, angle, pose):
        predicted = self.at(angle)
        rows = read_step(self.source / f"CAD/C92_J28_{pose}.step")[2]
        if len(rows) != len(GROUPS) or {r.name for r in rows} != set(GROUPS):
            raise ValueError("saved occurrence inventory mismatch")
        measured = {r.name: r.world.rotate((0, 0, 0), (1, 0, 0), -90) for r in rows}
        errors = {
            name: shape_signature_difference(predicted[name], measured[name]) for name in measured
        }
        gap = bounds(measured["pad_R"])[0] - bounds(measured["pad_L"])[3]
        return {
            "occurrence_count": len(rows),
            "angle_degrees": angle,
            "measured_opening_mm": gap,
            "analytic_opening_mm": opening_mm(angle),
            "maximum_vertex_distance_mm": max(e["vertex_distance_mm"] for e in errors.values()),
            "maximum_volume_error_mm3": max(e["volume_error_mm3"] for e in errors.values()),
            "signatures": errors,
            "comparison_scope": "vertex_area_volume_topology_not_exact_equivalence",
        }


def camera_assembly():
    shapes = {f"CAMERA_{n}": s for n, s in build_parts().items()}
    shapes.update({f"CAMERA_HW_{n}": s for n, s in envelope_hardware().items()})
    _, camera = donor_parts()
    n = cq.Vector(0, math.sqrt(3) / 2, -0.5)
    shapes["CAMERA_REFERENCE_UNCONFIRMED"] = camera.rotate((0, 0, 0), (1, 0, 0), 150).translate(
        tuple(cq.Vector(*CAMERA_ORIGIN) + n * 5)
    )
    return shapes


def motor_alignment(source=SOURCE):
    motor = cq.importers.importStep(
        str(Path(source) / "reference/C7/reference/XL430_from_supplied_arm.step")
    ).val()
    original = next(r.world for r in _source_rows() if r.name == "M06_ref00")
    placed = to_arm(motor)
    signature = shape_signature_difference(placed, original)
    self_cut = abs(placed.cut(placed.copy()).Volume())
    return {
        **signature,
        "self_difference_control_mm3": self_cut,
        "boolean_equivalence_status": "ERROR" if self_cut > 1e-4 else "NOT_TESTED",
        "transform": {
            "rotation_construction_to_arm": "Ry(+90deg)",
            "translation_mm": [-0.2, 234.9, 164.6],
        },
        "geometric_signature_matches": signature["vertex_distance_mm"] < 1e-6
        and signature["volume_error_mm3"] < 1e-4
        and signature["area_error_mm2"] < 1e-4,
        "boltability_approved": False,
    }


def arm_assembly(model, angle):
    # P06 also supports M06. Removing it would leave the new gripper unsupported.
    retained = {
        f"ARM_{r.name}": r.world
        for r in _source_rows()
        if r.name not in {"P07_moving_gripper_XL430", "M06_ref00"}
    }
    retained.update({f"PG3_{n}": to_arm(s) for n, s in model.at(angle).items()})
    retained.update(camera_assembly())
    return retained
