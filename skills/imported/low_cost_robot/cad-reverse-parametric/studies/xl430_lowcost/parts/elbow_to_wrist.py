"""Experimental interface model for follower/elbow_to_wrist.

This is NOT an equivalent reconstruction or a validated XL430 replacement. The
source's phi18.124 cylindrical faces are convex rounded outside profiles on two
tabs, not a blind horn-boss seat. The legacy prototype below retains that pocket
as an explicit design hypothesis for diagnosis, not as measured source geometry.
Hole-family agreement alone missed both that mistake and the missing second tab.

The CLI enforces source equivalence before exporting a normal XL430 candidate.
--export-prototype can emit a clearly named diagnostic XL430 model after failure,
but does not change the failed status or exit code. Original STEP/STL are untouched.

    uv run python studies/xl430_lowcost/parts/elbow_to_wrist.py --out outputs/parts
"""
from __future__ import annotations
import sys
import json
import argparse
from pathlib import Path

import cadquery as cq

from cadre import (parametric, compare, verdict, EquivalenceThresholds,
                   PartIntent, cylinder_faces, brep_available)
from cadre.geometry import Component

_HERE = Path(__file__).resolve()
_STUDY = _HERE.parents[1]                        # studies/xl430_lowcost
if str(_STUDY) not in sys.path:
    sys.path.insert(0, str(_STUDY))
import domain
from parts import _partlib as P
# parents: 0=parts 1=xl430_lowcost 2=studies 3=cad-reverse-parametric 4=skills 5=repo
_REPO = _HERE.parents[5]                          # repo root
INTENT = _STUDY / "intent" / "elbow_to_wrist.yaml"
REAL_STL = _REPO / "hardware/follower/stl/elbow_to_wrist.stl"
REAL_STEP = _REPO / "hardware/follower/step/elbow_to_wrist.step"

_SERVOS = {"XL330-M288-T": domain.XL330, "XL430-W250-T": domain.XL430}

# Invariants of the original frame, preserved across the swap.
FACE_Y = 42.0                # horn interface plane (motor output axis = Y)
BASE_Z = 0.0                 # base plate plane
END_WALL_T = 9.0             # Y=42 end wall thickness (>= 4mm seat + 2.5mm residual,
                             # and >= 6mm tap + 2.5mm residual margin holds with 9)
BASE_T = 3.0                 # base plate thickness (matches real Z[0,3] slab)


def _drill(solid: cq.Workplane, centers_xyz, diameter: float, axis: str,
           length: float = 200.0) -> cq.Workplane:
    """Cut THROUGH cylindrical holes along a principal `axis` ('X'|'Y'|'Z') at
    absolute (x,y,z) centers."""
    plane = {"X": "YZ", "Y": "XZ", "Z": "XY"}[axis]
    tool = cq.Workplane(plane).circle(diameter / 2).extrude(length, both=True)
    for c in centers_xyz:
        solid = solid.cut(tool.translate(tuple(c)))
    return solid


def _blind_seat_y(solid: cq.Workplane, center_xz, diameter: float, depth: float,
                  face_y: float) -> cq.Workplane:
    """Cut a BLIND recess of `depth` into the +Y end face at `face_y`, axis along Y,
    cutting in the -Y direction (inward). Stays blind so it never pierces the cradle."""
    x, z = center_xz
    return P.blind_seat(solid, (x, face_y, z), diameter, depth,
                        face=face_y, axis="Y", into=-1)


def make_elbow_to_wrist(motor: Component, intent: PartIntent | None = None
                        ) -> cq.Workplane:
    """Build the unvalidated prototype, not an accepted source reconstruction.

    Base plate (Z=0) + motor cradle (open +Z, motor axis Y) + horn end wall (Y=42)
    carrying the boss seat & tap diamond, then the measured hole families. `motor`
    drives the cradle envelope; XL330 -> XL430 grows the cradle while every preserved
    coordinate (base/horn planes, hole centers) stays fixed."""
    intent = intent or PartIntent.load(INTENT)
    feat = {f.name: f for f in intent.features}
    cradle_c = feat["motor_cradle"].constraints
    base_c = feat["base_mount"].constraints
    horn_c = feat["horn_mount"].constraints
    boss_c = feat["prototype_boss_pocket"].constraints

    clr = float(cradle_c["clearance_mm"])
    wall = float(cradle_c["wall_mm"])
    mw, mh, md = motor.envelope.as_tuple()        # XL330 20x34x26 / XL430 28.5x46.5x34

    # --- footprint sized to the motor cradle: X = body width + walls, Y = axial
    # (base->horn) span fixed at 42, Z = base + body height + open top. ---
    foot_x = max(22.0, mw + 2 * (clr + wall))
    foot_y = FACE_Y                                # preserved axial span
    # full-height end pillars rise to clear the motor body in Z
    pillar_z = max(28.0, md + 2 * clr + wall)

    # base plate (Z=0..BASE_T), full footprint, centered in X over [0,foot_x]
    body = (cq.Workplane("XY")
            .box(foot_x, foot_y, BASE_T, centered=(False, False, False)))

    # two side rails along Y (at X=0 and X=foot_x-wall) rising in Z -> the cradle
    for x0 in (0.0, foot_x - wall):
        rail = (cq.Workplane("XY")
                .box(wall, foot_y, pillar_z, centered=(False, False, False))
                .translate((x0, 0, 0)))
        body = body.union(rail)

    # horn END WALL at Y=42: a thick slab Y[face-END_WALL_T, face], full X/Z section
    end_wall = (cq.Workplane("XY")
                .box(foot_x, END_WALL_T, pillar_z, centered=(False, False, False))
                .translate((0, FACE_Y - END_WALL_T, 0)))
    body = body.union(end_wall)

    # --- BASE mounts: 4x M2 clearance THROUGH along Z (entry Z=0) ---
    base_centers = [tuple(c) for c in base_c["mount_centers_mm"]]
    body = _drill(body, base_centers, float(base_c["hole_diameter_mm"]), "Z")

    # --- HORN end (Y=42 face): blind boss seat + blind tap diamond (axis Y) ---
    bx, bz = boss_c["center_xz_mm"]
    body = _blind_seat_y(body, (bx, bz), float(boss_c["diameter_mm"]),
                         float(boss_c["blind_depth_mm"]), FACE_Y)
    for (hx, hz) in horn_c["diamond_centers_xz_mm"]:
        body = _blind_seat_y(body, (hx, hz), float(horn_c["hole_diameter_mm"]),
                             float(horn_c["blind_depth_mm"]), FACE_Y)
    return body


def _families(step_path: Path) -> list[dict]:
    return cylinder_faces(step_path).get("hole_families", [])


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("outputs/parts"))
    ap.add_argument("--samples", type=int, default=8000)
    ap.add_argument("--export-prototype", action="store_true",
                    help="export a diagnostic XL430 prototype even if equivalence fails; exit stays 2")
    a = ap.parse_args(argv)
    if a.samples <= 0:
        ap.error("--samples must be positive")
    a.out.mkdir(parents=True, exist_ok=True)

    out = {"status": "blocked_missing_reference", "swap_exported": False,
           "note": "Experimental interface model; hole families do not prove source equivalence or assembly fit."}
    if not REAL_STL.is_file() or not REAL_STEP.is_file():
        out["missing_references"] = [str(p) for p in (REAL_STL, REAL_STEP) if not p.is_file()]
        (a.out / "elbow_to_wrist_review.json").write_text(json.dumps(out, indent=2) + "\n")
        print(json.dumps(out, indent=2))
        return 2

    intent = PartIntent.load(INTENT)
    motor_name = {f.name: f for f in intent.features}["motor_cradle"].servo
    motor = _SERVOS[motor_name]                   # original spec: XL330

    orig = make_elbow_to_wrist(motor, intent)
    f_orig = parametric.export(orig, a.out / "elbow_to_wrist_orig_prototype")
    out.update({"orig": f_orig,
                "spec": {"motor_orig": motor.name, "motor_swap": domain.XL430.name}})

    if REAL_STL.exists():
        gap = compare(REAL_STL, a.out / "elbow_to_wrist_orig_prototype.stl", a.samples)
        out["C_A1_gap_to_real"] = {
            "bbox_delta_mm": gap["bbox_delta_mm"],
            "surface_max_mm": gap["surface_distance"]["max_mm"],
            "surface_mean_mm": gap["surface_distance"]["mean_mm"],
            "volume_delta_pct": gap["volume_delta_pct"],
            "watertight": gap["watertight"],
            "equivalent": verdict(gap, EquivalenceThresholds())["equivalent"],
            "note": "Non-equivalence blocks the swap; C-A2 is diagnostic only.",
        }
    if brep_available() and REAL_STEP.exists():
        out["C_A2_families"] = {
            "real": _families(REAL_STEP),
            "recon_orig": _families(a.out / "elbow_to_wrist_orig_prototype.step"),
        }
        out["cylinder_evidence"] = {
            "real": cylinder_faces(REAL_STEP),
            "recon_orig": cylinder_faces(a.out / "elbow_to_wrist_orig_prototype.step"),
        }
    equivalent = out["C_A1_gap_to_real"]["equivalent"]
    out["status"] = "passed_equivalence" if equivalent else "blocked_non_equivalent"
    if equivalent or a.export_prototype:
        stem = "elbow_to_wrist_xl430" if equivalent else "elbow_to_wrist_xl430_prototype"
        out["xl430"] = parametric.export(make_elbow_to_wrist(domain.XL430, intent), a.out / stem)
        out["swap_exported"] = True
    (a.out / "elbow_to_wrist_review.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0 if equivalent else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
