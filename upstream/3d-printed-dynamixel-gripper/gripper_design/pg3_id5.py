"""ID5-only layout candidate; no added motor, roll joint or fabrication approval."""

import cadquery as cq

from gripper_design.build import _source_rows
from gripper_design.pg3 import GROUPS
from gripper_design.pg3_crank_representation import build_candidate as build_crank
from gripper_design.pg3_installation import frame_candidate, side_camera_assembly

ORIGIN_MM = (-0.2, 164.9, 164.6)
LOCATION = cq.Location(ORIGIN_MM, (1, 0, 0), -90)


def to_id5(shape):
    return shape.rotate((0, 0, 0), (1, 0, 0), -90).translate(ORIGIN_MM)


def removed_source_names():
    return {
        r.name
        for r in _source_rows()
        if r.name.startswith("M06_")
        or r.name in {"M05_ref00", "P06_fixed_gripper_XL430", "P07_moving_gripper_XL430"}
    }


def inventory_contract(shapes):
    rows = _source_rows()
    removed = removed_source_names()
    retained = {f"ARM_{r.name}" for r in rows if r.name not in removed}
    expected_pg3 = {f"PG3_{n}" for n in GROUPS}
    actual = set(shapes)
    if {n for n in actual if n.startswith("ARM_")} != retained:
        raise ValueError("ARM inventory differs from ID5-only source-preserving contract")
    if {n for n in actual if n.startswith("PG3_")} != expected_pg3:
        raise ValueError("PG3 inventory differs from single split-motor mechanism")
    if any(not n.startswith(("ARM_", "PG3_", "CAMERA_")) for n in actual):
        raise ValueError("unclassified assembly inventory")
    return {
        "physical_motor_count_by_design": 5,
        "additional_terminal_motor_count": 0,
        "jaw_physical_id_requirement": 5,
        "observed_physical_mapping_verified": False,
        "candidate_CAD_motor_location": "M05",
        "retained_source_occurrences": sorted(retained),
        "removed_source_occurrences": sorted(removed),
        "motor_display_split": ["PG3_XL430_fixed", "PG3_XL430_horn"],
        "source_M05_ref00_replaced_not_added": True,
        "installation_approved": False,
    }


def assemble(model, angle):
    removed = removed_source_names()
    shapes = {f"ARM_{r.name}": r.world for r in _source_rows() if r.name not in removed}
    mechanism = model.at(angle)
    mechanism["frame"] = frame_candidate(model.neutral["frame"])
    mechanism["crank"] = build_crank().rotate((0, 0, 0), (0, 0, 1), angle)
    shapes.update({f"PG3_{n}": to_id5(s) for n, s in mechanism.items()})
    shapes.update(side_camera_assembly())
    inventory_contract(shapes)
    return shapes
