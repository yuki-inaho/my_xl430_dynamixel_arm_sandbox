"""Parametric reconstruction of follower/gripper_moving_part (the gripper "moving side").

The moving jaw rides on the joint5 servo HORN (not the body) — impact tier "indirect".
So the XL330 -> XL430 swap scope here is LIMITED to the horn/idler seat following the
XL430 horn: the phi16 horn-boss seat + phi1.8 tap pattern stay, and the phi31 outer
body-clearance recess grows for the larger XL430 body. There is no motor-body cradle to
resize. Frame: X[-5,16] Y[-8,56] Z[0,35.5]; all interfaces along axis Z.

    uv run python studies/xl430_lowcost/parts/gripper_moving_part.py --out outputs/parts
"""
from __future__ import annotations
import sys
import argparse
from pathlib import Path

import cadquery as cq

from cadre import PartIntent
from cadre.geometry import Component
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _partlib as P
import domain

INTENT = Path(__file__).resolve().parents[1] / "intent" / "gripper_moving_part.yaml"
_SERVOS = {"XL330-M288-T": domain.XL330, "XL430-W250-T": domain.XL430}
PRINT_EDGE_RELIEF_MM = 0.2


def make_gripper_moving(
    servo: Component,
    intent: PartIntent | None = None,
    print_edge_relief_mm: float = 0.0,
) -> cq.Workplane:
    intent = intent or PartIntent.load(INTENT)
    feat = {f.name: f for f in intent.features}
    tap = feat["horn_idler_mount"].constraints
    boss = feat["horn_boss_bore"].constraints
    recess = feat["body_clearance_recess"].constraints

    # jaw body over the bbox (Z preserved). Y footprint grows slightly with the servo
    # body so the larger XL430 clears behind the recess (kinematic Z interface stays).
    mw, mh, md = servo.envelope.as_tuple()
    foot_y = max(63.999, mh + 16)
    relief = max(0.0, float(print_edge_relief_mm))
    # Print-only repair: the real/open recess has two exact tangencies where the phi16
    # boss seat touches the +X and -Y outer walls. That is acceptable as source
    # geometry, but exported STL becomes non-manifold. Add material only outside those
    # two walls for print artifacts; do not change the functional holes/seats.
    body = (cq.Workplane("XY")
            .box(21.0 + relief, foot_y + relief, 35.5, centered=(False, False, False))
            .translate((-5.0, -8.0 - relief, 0)))

    # phi31 outer body-clearance recess (blind from Z=0, into +Z); grows on swap if the
    # servo body is larger (here phi31 already clears XL330/XL430 horn region; recorded).
    rcx, rcy = recess["center_xy_mm"]
    body = P.blind_seat(body, (rcx, rcy, 0.0), float(recess["diameter_mm"]),
                        float(recess["blind_depth_mm"]), face=0.0, axis="Z", into=+1)
    # phi16 horn-boss seat (blind from Z=0, into +Z)
    bcx, bcy = boss["center_xy_mm"]
    body = P.blind_seat(body, (bcx, bcy, 0.0), float(boss["diameter_mm"]),
                        float(boss["blind_depth_mm"]), face=0.0, axis="Z", into=+1)
    # 4x phi1.8 tap diamond (blind from Z=0, into +Z) on the horn boss
    for (tx, ty) in tap["diamond_centers_xy_mm"]:
        body = P.blind_seat(body, (tx, ty, 0.0), float(tap["hole_diameter_mm"]),
                            float(tap["blind_depth_mm"]), face=0.0, axis="Z", into=+1)
    return body


def make_gripper_moving_printable(
    servo: Component,
    intent: PartIntent | None = None,
    edge_relief_mm: float = PRINT_EDGE_RELIEF_MM,
) -> cq.Workplane:
    """Return a print-only manifold variant with unchanged functional holes/seats."""
    return make_gripper_moving(servo, intent, print_edge_relief_mm=edge_relief_mm)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("outputs/parts"))
    ap.add_argument("--samples", type=int, default=8000)
    a = ap.parse_args(argv)
    intent = PartIntent.load(INTENT)
    servo_name = {f.name: f for f in intent.features}["horn_idler_mount"].servo
    P.report_main("gripper_moving_part",
                  lambda: make_gripper_moving(_SERVOS[servo_name], intent),
                  swap_build=lambda: make_gripper_moving(domain.XL430, intent),
                  samples=a.samples, out=a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
