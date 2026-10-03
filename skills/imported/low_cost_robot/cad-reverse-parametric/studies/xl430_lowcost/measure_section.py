"""WP-4 / CF-5: measure seat depth & through-ness of the reconstructed XL430 STEP
parts with cadquery (the *numerical* primary method; chili3d is a visual aux only).

Method:
  - phi26 servo-case seat (shoulder, axis X): on each cradle WALL solid, march along
    X on a clean seat radius (r=11, between the M2 ring r=8 and the phi26 edge r=13)
    and split the wall thickness into the seat void (pocket depth) and the residual
    floor (material). Floor must be >= C-B4 2.5mm on BOTH walls (CF-1).
  - phi18.12 pocket (elbow PROTOTYPE only, axis Y): check its face extent AND
    material at the entry and behind the floor. This pocket does not exist in
    the original STEP; the source's round tops are convex outer profiles.
  - phi2.3 base mount (elbow, axis Z): confirm a through void from Z=0 to Z=top.

    cd skills/cad-reverse-parametric
    PYTHONPATH=studies/xl430_lowcost uv run python studies/xl430_lowcost/measure_section.py
"""
from __future__ import annotations
import argparse
from pathlib import Path

import numpy as np
import cadquery as cq
from cadquery import Vector
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder

_HERE = Path(__file__).resolve()
_SKILL = _HERE.parents[2]
OUT = _SKILL / "outputs" / "parts"


def _solids(step_path: Path):
    return cq.importers.importStep(str(step_path)).solids().vals()


def measure_shoulder_seat():
    solids = _solids(OUT / "shoulder_to_elbow_xl430.step")
    print("== shoulder_to_elbow_xl430 : phi26 servo-case seat (blind, axis X) ==")
    for s in solids:
        bb = s.BoundingBox()
        thick = bb.xmax - bb.xmin
        if abs(bb.xmin) < 10 or thick > 7:      # skip the central beam/tab solid
            continue
        side = "+X" if bb.xmin > 0 else "-X"
        xs = np.arange(bb.xmin - 0.3, bb.xmax + 0.3, 0.02)
        mat = [x for x in xs if s.isInside(Vector(float(x), 0.0, 11.0), tolerance=1e-4)]
        void = [x for x in xs if bb.xmin <= x <= bb.xmax
                and not s.isInside(Vector(float(x), 0.0, 11.0), tolerance=1e-4)]
        floor = (max(mat) - min(mat)) if mat else 0.0
        depth = (max(void) - min(void)) if void else 0.0
        ok = "PASS (>=2.5)" if floor >= 2.5 - 1e-6 else "FAIL (<2.5)"
        print(f"   {side} wall x[{bb.xmin:.2f},{bb.xmax:.2f}] thick={thick:.2f}: "
              f"seat_depth(r=11)={depth:.2f}mm  floor={floor:.2f}mm  C-B4 {ok}")


def measure_elbow_seats(step_path: Path | None = None) -> bool:
    s = max(_solids(step_path or OUT / "elbow_to_wrist_xl430.step"), key=lambda x: x.Volume())
    bb = s.BoundingBox()
    print("== elbow_to_wrist PROTOTYPE: pocket opening/floor; not source-equivalence or fit approval ==")
    pocket_ok = False
    for f in s.Faces():
        surf = BRepAdaptor_Surface(f.wrapped)
        if surf.GetType() == GeomAbs_Cylinder and 8.5 < surf.Cylinder().Radius() < 9.6:
            fb = f.BoundingBox()
            entry_open = not s.isInside(Vector(11.0, 41.9, 18.94))
            floor_present = s.isInside(Vector(11.0, 37.9, 18.94))
            pocket_ok = (abs(fb.ymin - 38.0) < 0.01 and abs(fb.ymax - 42.0) < 0.01
                         and entry_open and floor_present)
            print(f"   prototype pocket: cyl-face Y[{fb.ymin:.2f},{fb.ymax:.2f}] "
                  f"entry_open={entry_open} floor_present={floor_present} "
                  f"-> {'PASS' if pocket_ok else 'FAIL'}")
            break
    # base mount phi2.3 through along Z at (x=3, y=3.1).
    zs = np.arange(bb.zmin - 0.5, bb.zmax + 0.5, 0.05)
    through = all(not s.isInside(Vector(3.0, 3.1, float(z)), tolerance=1e-4)
                  for z in zs if bb.zmin < z < bb.zmax)
    print(f"   base-mount phi2.3 @x=3,y=3.1: {'THROUGH' if through else 'NOT through'} "
          "(sampled full axial path)")
    return pocket_ok and through


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--elbow-step", type=Path,
                        help="explicit diagnostic STEP; defaults to the old outputs/parts artifact")
    args = parser.parse_args()
    measure_shoulder_seat()
    raise SystemExit(0 if measure_elbow_seats(args.elbow_step) else 2)
