"""Parametric reconstruction of follower/shoulder_rotation (the "rotation connector").

SWAP NOT APPLICABLE: this thin disc mounts on the joint1 base-rotation servo, which is
XL430-W250-T ALREADY (only joint3/4/5 swap in this migration). So we build stage-1
(equivalence-first) and emit NO XL430 variant — recorded explicitly, not silently.

Frame: X[-20,20] Y[-38.25,14.25] Z[19,29.9] (thin plate, ~10.9 thick). The horn screw
pattern (4x M2 at radius 8, axis Z) + phi10 horn bore (axis Z) is the XL430 horn
interface; M3 link holes (axis X) + phi21.5 side hub recess connect to the shoulder.

    uv run python studies/xl430_lowcost/parts/shoulder_rotation.py --out outputs/parts
"""
from __future__ import annotations
import sys
import argparse
from pathlib import Path

import cadquery as cq

from cadre import PartIntent
sys.path.insert(0, str(Path(__file__).resolve().parent))   # make _partlib importable
import _partlib as P

INTENT = Path(__file__).resolve().parents[1] / "intent" / "shoulder_rotation.yaml"
PLATE_T = 10.9            # Z thickness (preserved)
Z0 = 19.0                 # plate bottom (real Z[19,29.9])


def make_shoulder_rotation(intent: PartIntent | None = None) -> cq.Workplane:
    intent = intent or PartIntent.load(INTENT)
    feat = {f.name: f for f in intent.features}
    horn = feat["horn_mount"].constraints
    link = feat["link_mount"].constraints
    boss = feat["horn_boss_bore"].constraints
    hub = feat["hub_bore"].constraints

    # plate body spanning the measured bbox, thickness preserved
    body = (cq.Workplane("XY")
            .box(40.0, 52.5, PLATE_T, centered=(True, False, False))
            .translate((0, -38.25, Z0)))
    zc = Z0 + PLATE_T / 2.0

    # horn screw cross (4x M2 through, axis Z) at radius 8
    body = P.drill(body, [(x, y, zc) for (x, y) in horn["cross_centers_xy_mm"]],
                   float(horn["hole_diameter_mm"]), "Z")
    # phi10 horn shaft bore (through, axis Z) at origin
    cx, cy = boss["center_xy_mm"]
    body = P.drill(body, [(cx, cy, zc)], float(boss["diameter_mm"]), "Z")
    # phi21.5 hub face: the real part has a phi21.5 cylindrical face whose X-axis line
    # sits at (Y=0, Z=36.291), above the plate (a rounded top boss). Reproduce it with a
    # small lug at that height bored through along X, so the family lands at the exact
    # measured axis line (C-A2). The lug is intentionally small (does not claim to match
    # the organic outer shape -> C-A1 gap, expected).
    huby, hubz = hub["center_yz_mm"]
    r = float(hub["diameter_mm"]) / 2.0
    # BOX lug (not a cylinder — a cylindrical lug would add a spurious outer-diameter
    # family). Spans X across the plate, sized to host the phi21.5 bore, reaching down
    # into the plate (Z up to 29.9) to stay connected.
    lug = (cq.Workplane("XY")
           .box(40.0, 2 * (r + 2.0), 2 * (r + 2.0), centered=(True, True, True))
           .translate((0, huby, hubz)))
    body = body.union(lug)
    body = P.drill(body, [(0.0, huby, hubz)], float(hub["diameter_mm"]), "X")
    # M3 link holes (through, axis X) — drilled LAST so they also pierce the lug and are
    # not refilled by it (the lug overlaps the M3 at (0,8,25.3) in Y,Z).
    body = P.drill(body, [tuple(c) for c in link["mount_centers_mm"]],
                   float(link["hole_diameter_mm"]), "X")
    return body


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("outputs/parts"))
    ap.add_argument("--samples", type=int, default=8000)
    a = ap.parse_args(argv)
    intent = PartIntent.load(INTENT)
    # swap_build=None -> SWAP NOT APPLICABLE (joint1 is already XL430).
    P.report_main("shoulder_rotation", lambda: make_shoulder_rotation(intent),
                  swap_build=None, samples=a.samples, out=a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
