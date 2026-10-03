"""Check explicit assembly stages against a saved PG3 assembly, retaining all stage parts."""

import argparse
import json
import math
from pathlib import Path

import cadquery as cq

from gripper_design.pg2 import digest
from gripper_design.pg3 import GROUPS
from gripper_design.pg3_installation import camera_tools, support_tools
from scripts.assembly_io import bounds, read_step
from scripts.review_pg3 import inspect_pairs
from scripts.review_pg3_pivot_stacks import pick, profiles


def driver_envelope(head, shaft_radius=1.5, withdrawal=0):
    """Nominal +X straight tool and grip reservation, not an engaged bit model.

    Extending each axial cylinder by withdrawal exactly covers positive-X
    translation of their union. Rotation about X does not change this envelope.
    """
    if shaft_radius <= 0 or withdrawal < 0:
        raise ValueError("positive shaft and nonnegative withdrawal required")
    x, y, z = head
    segments = ((shaft_radius, 0.05, 75), (10, 75.05, 30), (40, 70.05, 100))
    solids = [
        cq.Solid.makeCylinder(r, length + withdrawal, (x + offset, y, z), (1, 0, 0))
        for r, offset, length in segments
    ]
    return solids[0].fuse(*solids[1:])


def horn_l_key_envelope(head, withdrawal=0):
    """Candidate 1.5 AF, 50/14 mm L-key access/turning reservation.

    PB 210.1,5 supplies the nominal AF and inner arm lengths. The lower
    35 mm straight section and grip placement remain explicit envelope-fit
    conditions to confirm on the actual key. No socket engagement is modeled.
    """
    if withdrawal < 0:
        raise ValueError("nonnegative withdrawal required")
    x, y, z = head
    segments = ((1.5 / math.sqrt(3), 0.05, 50), (15, 35, 16), (40, 35, 100))
    solids = [
        cq.Solid.makeCylinder(r, length + withdrawal, (x + offset, y, z), (1, 0, 0))
        for r, offset, length in segments
    ]
    return solids[0].fuse(*solids[1:])


def mechanism_stages(shapes, horn_l_key=False):
    expected = {f"PG3_{name}" for name in GROUPS}
    actual = {name for name in shapes if name.startswith("PG3_")}
    if actual != expected:
        raise ValueError("PG3 occurrence inventory mismatch")
    present = {n for n in shapes if n.startswith("ARM_")}
    present.update({"PG3_XL430_fixed", "PG3_XL430_horn"})
    stages = {}

    def matching(prefix, suffix):
        return sorted(n for n in expected if n.startswith(prefix) and n.endswith(suffix))

    def add(stage, added, bolts):
        additions = set(added) | set(bolts)
        if additions & present:
            raise ValueError("a PG3 component was installed twice")
        present.update(additions)
        tools = {}
        for name in bolts:
            radius = 1.3 if "case_tapper" in name else 1
            cylinder = pick(profiles(shapes[name]), radius, "convex")
            y, z = cylinder["axis_yz_mm"]
            head = (bounds(shapes[name])[3], y, z)
            envelope = (
                horn_l_key_envelope if horn_l_key and "horn_bolt" in name else driver_envelope
            )
            tools[f"TOOL_{name}"] = envelope(head)
            tools[f"WITHDRAWAL_{name}"] = envelope(head, withdrawal=100)
        stages[stage] = ({n: shapes[n] for n in sorted(present)}, tools)

    add(
        "G1_frame_case",
        ["PG3_frame", *matching("PG3_cap_", "_nut")],
        matching("PG3_case_tapper", ""),
    )
    add(
        "G2_horn_drive",
        ["PG3_horn_spacer", "PG3_crank", *matching("PG3_pivot_drive_", "_nut")],
        matching("PG3_horn_bolt_", ""),
    )
    present.update(
        {
            "PG3_carriage_R",
            "PG3_carriage_L",
            *matching("PG3_pivot_carriage_", "_nut"),
            *matching("PG3_finger_", "_nut"),
        }
    )
    add(
        "G4_link_pivots",
        ["PG3_link_R", "PG3_link_L", *matching("PG3_pivot_", "_washer")],
        matching("PG3_pivot_", "_bolt"),
    )
    add(
        "G5_caps",
        ["PG3_cap_U", "PG3_cap_D", *matching("PG3_cap_", "_washer")],
        matching("PG3_cap_", "_bolt"),
    )
    add(
        "G6_fingers",
        ["PG3_finger_R", "PG3_finger_L", *matching("PG3_finger_", "_washer")],
        matching("PG3_finger_", "_bolt"),
    )
    present.update({"PG3_pad_R", "PG3_pad_L"})
    if present != {n for n in shapes if not n.startswith("CAMERA_")}:
        raise ValueError("final pre-camera inventory mismatch")
    return stages


def camera_stages(shapes):
    tools = {f"TOOL_{n}": s for n, s in camera_tools().items()}
    first = ["CAMERA_camera_carrier", "CAMERA_camera_spacer", "CAMERA_REFERENCE_UNCONFIRMED"]
    for i in range(4):
        first.extend([f"CAMERA_HW_M2x10_{i}_ENVELOPE", f"CAMERA_HW_M2nut_{i}_ENVELOPE"])
    first.extend(f"CAMERA_HW_M2nut_carrier_{i}_ENVELOPE" for i in range(2))
    second = [*first, "CAMERA_saddle", *[f"CAMERA_HW_M2x10_carrier_{i}_ENVELOPE" for i in range(2)]]
    expected = (
        set(second)
        | {"CAMERA_front_jaw"}
        | {f"CAMERA_HW_{kind}_{i}_ENVELOPE" for kind in ("M3x16", "M3nut") for i in range(2)}
    )
    actual = {n for n in shapes if n.startswith("CAMERA_")}
    if actual != expected:
        raise ValueError(
            f"camera occurrence inventory changed: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
    return {
        "A_camera_to_carrier_before_bracket": (
            {n: shapes[n] for n in first},
            {n: s for n, s in tools.items() if n.startswith("TOOL_M2_")},
        ),
        "B_carrier_to_bracket_after_A": (
            {n: shapes[n] for n in second},
            {n: s for n, s in tools.items() if n.startswith("TOOL_M2C_")},
        ),
        "C_clamp_to_arm_after_B": (
            shapes,
            {n: s for n, s in tools.items() if n.startswith("TOOL_M3_")},
        ),
    }


def assembly_stages(shapes):
    stages = camera_stages(shapes)
    support = {f"TOOL_{n}": s for n, s in support_tools().items()}
    before = {
        n: s
        for n, s in shapes.items()
        if n.startswith("ARM_") and not n.startswith(("ARM_M06_", "ARM_P06_case_"))
    }
    stages["D_horn_before_M06"] = (
        before,
        {n: s for n, s in support.items() if n.startswith("TOOL_HORN_")},
    )
    stages["E_case_on_arm"] = (
        shapes,
        {n: s for n, s in support.items() if n.startswith("TOOL_CASE_")},
    )
    return stages


def verify(path, include_mechanism=False, horn_l_key=False):
    if horn_l_key and not include_mechanism:
        raise ValueError("L-key candidate requires mechanism stages")
    rows = read_step(path)[2]
    shapes = {r.name: r.world for r in rows}
    if len(rows) != len(shapes):
        raise ValueError("ambiguous occurrence names")
    stages = assembly_stages(shapes)
    if include_mechanism:
        stages.update(mechanism_stages(shapes, horn_l_key))
    result = {}
    for name, (obstacles, tools) in stages.items():
        check = inspect_pairs(obstacles | tools, [(a, b) for a in tools for b in obstacles])
        result[name] = {
            "present_occurrences": sorted(obstacles),
            "tool_names": sorted(tools),
            **check,
        }
    passed = all(set(v["counts"]) == {"PASS"} for v in result.values())
    return {
        "assembly_sha256": digest(path),
        "checker_sha256": digest(Path(__file__)),
        "tool_code_sha256": digest(
            Path(__file__).resolve().parents[1] / "gripper_design/pg3_installation.py"
        ),
        "stages": result,
        "nominal_tool_stages_pass": passed,
        "mechanism_stages_included": include_mechanism,
        "horn_l_key_candidate": {
            "enabled": horn_l_key,
            "candidate": "PB 210.1,5",
            "source": "https://www.pbswisstools.com/en/tools/quality-hand-tools/precisionbits/product/pb-210",
            "published_AF_long_inner_short_inner_mm": [1.5, 50, 14],
            "required_minimum_straight_shank_mm": 35,
            "reserved_turning_radius_mm": 15,
            "grip_reservation_radius_length_mm": [40, 100],
            "actual_tool_fits_envelope_verified": False,
            "actual_socket_and_required_torque_verified": False,
        },
        "mechanism_tool_assumptions": {
            "shaft_diameter_mm": 3,
            "shaft_length_mm": 75,
            "handle_diameter_mm": 20,
            "handle_length_mm": 30,
            "grip_reservation_diameter_mm": 80,
            "grip_reservation_length_mm": 100,
            "positive_X_withdrawal_mm": 100,
            "bit_engagement_and_actual_human_fit_verified": False,
            "scope": "above_head_outer_access_and_continuous_straight_withdrawal_only",
        }
        if include_mechanism
        else None,
        "required_order": [
            "camera captive nuts, camera/spacer onto carrier (A)",
            "carrier/camera onto saddle via two accessible M2 screws (B)",
            "P06 onto M05 horn before M06 installation (D)",
            "M06 onto P06 with bottom case screws (E)",
            "PG3 frame/case G1, spacer/crank/horn G2, bare carriages, links/pivots G4, caps G5, fingers G6, pads",
            "camera saddle plus front jaw onto P05 (C)",
        ],
        "service_order": "release clamp C, undo B, service camera screws A; do not drive A in assembled state",
        "insertion_and_hand_clearance_verified": False,
        "actual_tools_measured": False,
        "physical_assembly_verified": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("assembly", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument(
        "--mechanism",
        action="store_true",
        help="Include PG3 staged shaft/handle/grip and withdrawal",
    )
    p.add_argument(
        "--horn-l-key",
        action="store_true",
        help="Use separately documented 1.5 AF L-key envelope at horn",
    )
    args = p.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    result = verify(args.assembly, args.mechanism, args.horn_l_key)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v["counts"] for k, v in result["stages"].items()}, indent=2))
    raise SystemExit(0 if result["nominal_tool_stages_pass"] else 2)
