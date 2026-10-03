"""Parametric reconstruction of follower/gripper_static_part (the gripper "static side").

Holds the joint5 gripper servo (XL330 -> XL430 swap target) and forms the fixed jaw.
Frame: X[-19.5,18.25] Y[-20,48.868] Z[0,29.5]. A HORN diamond (4x M2, axis Y) mounts
to the servo horn; BASE M2 holes (axis Z) fix the jaw. The swap grows the servo-body
clearance footprint while the horn/base hole patterns (the kinematic interface) stay.

    uv run python studies/xl430_lowcost/parts/gripper_static_part.py --out outputs/parts
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

INTENT = Path(__file__).resolve().parents[1] / "intent" / "gripper_static_part.yaml"
_SERVOS = {"XL330-M288-T": domain.XL330, "XL430-W250-T": domain.XL430}


def make_gripper_static(servo: Component, intent: PartIntent | None = None) -> cq.Workplane:
    intent = intent or PartIntent.load(INTENT)
    feat = {f.name: f for f in intent.features}
    horn = feat["horn_mount"].constraints
    base = feat["base_mount"].constraints
    cradle = feat["servo_cradle"].constraints
    clr = float(cradle["clearance_mm"])

    # Body block over the bbox; X/Y footprint grows with the servo body so the larger
    # XL430 clears (kept >= the real footprint). Z (jaw height) preserved.
    mw, mh, md = servo.envelope.as_tuple()
    foot_x = max(37.75, mw + 2 * clr + 8)
    body = (cq.Workplane("XY")
            .box(foot_x, 68.868, 29.5, centered=(True, False, False))
            .translate((0, -20.0, 0)))

    # HORN diamond: blind M2 into the +Y horn wall (face at Y=0, cutting +Y into body)
    for (hx, hz) in horn["diamond_centers_xz_mm"]:
        body = P.blind_seat(body, (hx, 0.0, hz), float(horn["hole_diameter_mm"]),
                            float(horn["blind_depth_mm"]), face=float(horn["face_y_mm"]),
                            axis="Y", into=+1)
    # BASE M2 through-holes (axis Z): two distinct-diameter families (phi2.30 x2,
    # phi2.34 x1) so the recon reproduces both, not a single merged phi2.3 family.
    body = P.drill(body, [tuple(c) for c in base["base_a_centers_mm"]],
                   float(base["base_a_diameter_mm"]), "Z")
    body = P.drill(body, [tuple(c) for c in base["base_b_centers_mm"]],
                   float(base["base_b_diameter_mm"]), "Z")
    return body


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("outputs/parts"))
    ap.add_argument("--samples", type=int, default=8000)
    a = ap.parse_args(argv)
    intent = PartIntent.load(INTENT)
    servo_name = {f.name: f for f in intent.features}["servo_cradle"].servo
    P.report_main("gripper_static_part",
                  lambda: make_gripper_static(_SERVOS[servo_name], intent),
                  swap_build=lambda: make_gripper_static(domain.XL430, intent),
                  samples=a.samples, out=a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
