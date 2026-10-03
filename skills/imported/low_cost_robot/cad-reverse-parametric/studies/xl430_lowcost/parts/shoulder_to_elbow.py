"""Parametric reconstruction of follower/shoulder_to_elbow (the "XL430 to XL330 new
connector"). Intent-driven, equivalent-shape-first, then a one-argument XL430 swap.

Frame (matches the real STEP, `cadre.cli inspect`):
  - long axis = Y; bbox Y[-13,119] = 132 (joint_distance, preserved on swap)
  - upstream servo cradle straddles the X=+/-19 walls; servo OUTPUT AXIS = X
  - downstream mount boss at Y ~100-116 carries 2x M2 holes along +X

HONESTY (same stance as connector.py): the real bracket is an organic Fusion solid.
This is an *interface reconstruction* that reproduces the measured HOLE FAMILIES
(diameters, axis lines, absolute centers) — the C-A2 / C-B6..C-B8 invariants — on a
manufacturable beam+cradle body. It is NOT expected to pass the C-A1 mesh-equivalence
gate (organic outer surface differs); `main` prints the C-A1 gap honestly and runs
C-A2 (family match) as the real acceptance gate.

Generic geometry comes from cadre.parametric / cadquery; the only domain inputs are
the two `Component`s (domain.XL430 / domain.XL330) and the measured coordinates,
which are read from the intent YAML so the script and the YAML cannot drift.

    uv run python studies/xl430_lowcost/parts/shoulder_to_elbow.py --out outputs/parts
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
import domain

_HERE = Path(__file__).resolve()
_STUDY = _HERE.parents[1]                       # studies/xl430_lowcost
# parents: 0=parts 1=xl430_lowcost 2=studies 3=cad-reverse-parametric 4=skills 5=repo
_REPO = _HERE.parents[5]                         # repo root
INTENT = _STUDY / "intent" / "shoulder_to_elbow.yaml"
REAL_STL = _REPO / "hardware/follower/stl/shoulder_to_elbow.stl"
REAL_STEP = _REPO / "hardware/follower/step/shoulder_to_elbow.step"

# Servo selectable by name from the intent; resolves to a domain Component.
_SERVOS = {"XL330-M288-T": domain.XL330, "XL430-W250-T": domain.XL430}


def _drill_x(solid: cq.Workplane, centers_xyz, diameter: float,
             length: float = 200.0) -> cq.Workplane:
    """Cut cylindrical holes whose axis is global X, at absolute (x,y,z) centers.
    `length` is over-long so the cut is fully through the local material."""
    tool = (cq.Workplane("YZ").circle(diameter / 2)
            .extrude(length, both=True))         # axis along X, centered at origin
    for (x, y, z) in centers_xyz:
        solid = solid.cut(tool.translate((x, y, z)))
    return solid


def _counterbore_x(solid: cq.Workplane, wx: float, wall_t: float, diameter: float,
                   depth: float) -> cq.Workplane:
    """Cut a shallow counterbore (seat) of `depth` into EACH cradle wall, axis along
    X, from that wall's OUTER face inward. Used for the servo-case seat (phi26): it
    must NOT be a through-cut, or it would swallow the coaxial phi10 passage and the
    surrounding M2 ring.

    The walls are centred at x=+/-`wx` with thickness `wall_t`, so the +x wall spans
    [wx-wall_t/2, wx+wall_t/2] (outer face = wx+wall_t/2) and the -x wall spans
    [-wx-wall_t/2, -wx+wall_t/2] (outer face = -wx-wall_t/2). The seat is placed at
    the ACTUAL outer face of each wall (not the nominal +/-wx line), so the residual
    floor on both walls is exactly wall_t - depth (CF-1 manufacturability, C-B4)."""
    r = diameter / 2
    eps = 0.01
    # +x wall: outer face at x = wx + wall_t/2; cut a depth-deep seat opening inward.
    plus_outer = wx + wall_t / 2.0
    plus = (cq.Workplane("YZ").circle(r).extrude(depth)         # x in [0, depth]
            .translate((plus_outer + eps - depth, 0, 0)))       # seat: [outer-depth, outer]
    # -x wall: outer face at x = -(wx + wall_t/2); seat opens inward (+x).
    minus_outer = -(wx + wall_t / 2.0)
    minus = (cq.Workplane("YZ").circle(r).extrude(depth)
             .translate((minus_outer - eps, 0, 0)))             # seat: [outer, outer+depth]
    return solid.cut(plus).cut(minus)


def make_shoulder_to_elbow(upstream: Component, downstream: Component,
                           intent: PartIntent | None = None) -> cq.Workplane:
    """Beam (Y) + upstream servo cradle (open +Z, servo axis X) + downstream mount
    boss, then the measured hole families bored along X. `upstream`/`downstream`
    drive the cradle envelopes; swapping `downstream` performs the XL430 swap while
    all preserved coordinates (joint_distance, hole centers) stay fixed."""
    intent = intent or PartIntent.load(INTENT)
    feat = {f.name: f for f in intent.features}
    beam = feat["link_beam"].constraints
    up_c = feat["upstream_servo_mount"].constraints
    dn_c = feat["downstream_servo_mount"].constraints
    body_bore = feat["motor_body_bore"].constraints
    horn_bore = feat["horn_idler_bore"].constraints

    jd = float(beam["joint_distance_mm"])        # 132, preserved
    bw, bt = float(beam["beam_w_mm"]), float(beam["beam_t_mm"])
    wx = float(up_c["wall_x_mm"])                # +/-19 cradle walls (servo axis X)
    wall_t = float(up_c["wall_mm"])              # wall thickness along X

    # --- spine beam along Y, spanning Y[-13,119] ---
    body = (cq.Workplane("XY")
            .box(bw, jd, bt, centered=(True, False, True))
            .translate((0, -13.0, 0)))           # so Y runs [-13, 119]

    # --- upstream servo cradle: TWO solid end-walls at x=+/-19 joined by the spine,
    # leaving the servo cavity between them (open +Z by construction). The walls are
    # solid plates so the phi10 passage, phi26 case seat and the M2 cross ring all
    # land in real material (a clearance_pocket would remove that wall material).
    # The cradle holds the UPSTREAM servo (joint2 = XL430, fixed), so its size is
    # driven by `upstream` and does NOT change on the downstream swap. ---
    # Wall must comfortably contain the phi26 case seat (dia 26) without touching its
    # edge (a tangent seat creates degenerate faces -> non-watertight mesh).
    seat_dia = float(body_bore["diameter_mm"])               # 26
    wall_h = seat_dia + 6.0                                   # 32: seat clears the edge
    wall_yspan = seat_dia + 6.0
    for sx in (+1, -1):
        # extrude() always grows +X from the YZ plane by wall_t, so to CENTRE the
        # wall on x = sx*wx we translate its start to sx*wx - wall_t/2 (NOT
        # sx*wx - sx*wall_t/2, which mis-centred the -X wall at -13.5 instead of -19
        # and left its phi26 seat outside the wall -> asymmetric/absent floor, CF-1).
        wall = (cq.Workplane("YZ")
                .rect(wall_yspan, wall_h)
                .extrude(wall_t)
                .translate((sx * wx - wall_t / 2, 0, 0)))
        body = body.union(wall)

    # --- downstream mount TAB at Y ~80-119 carrying the 2x M2 holes (drilled along X).
    # From the real part: the tail is a flat tab X[-14.8,14.8], Z[2,13] (upper half),
    # holes at x=-14.75 z=7.7. The downstream servo (joint3) bolts onto the -X face and
    # its body extends further -X (away from the bracket). The swap (XL330 -> XL430)
    # grows the tab Y/Z footprint so the larger XL430 frame face is fully supported;
    # the body keepout on -X must stay clear (checks.envelope_clearance). The tab top
    # (z up to ~13) overlaps the spine beam, keeping it connected. ---
    dn_centers = [tuple(c) for c in dn_c["mount_centers_mm"]]
    ys = [c[1] for c in dn_centers]
    zs = [c[2] for c in dn_centers]
    x_face = dn_centers[0][0]                      # -14.75 mount plane (tab -X face)
    dn_w, dn_h, dn_d = downstream.envelope.as_tuple()
    tab_t = abs(x_face) * 2.0                       # tab spans x[-14.75, +14.75] (~29.5)
    pad = 6.0
    tab_yspan = (max(ys) - min(ys)) + max(dn_w, dn_d) + pad   # grows with servo frame
    tab_zspan = (13.0 - 2.0) + pad                  # upper-Z tab band (real Z[2,13])
    y_c = (min(ys) + max(ys)) / 2.0
    z_c = 13.0 - tab_zspan / 2.0                     # top-aligned to z=13 (meets beam)
    tab = (cq.Workplane("XY")
           .box(tab_t, tab_yspan, tab_zspan, centered=(True, True, True))
           .translate((0, y_c, z_c)))
    body = body.union(tab)

    # --- holes / seats along X (C-A2 / C-B7 / C-B8 invariants) ---
    # phi10 horn/idler passage: THROUGH both walls (one axis line).
    body = _drill_x(body, [(0.0, 0.0, 0.0)], float(horn_bore["diameter_mm"]))
    # phi26 servo-case seat: shallow COUNTERBORE on each outer wall face (NOT through,
    # so it does not swallow the phi10 passage or the M2 ring). C-B7 seat depth ~3mm.
    # CF-1 manufacturability (C-B4): residual floor = wall_t - seat_depth. The wall
    # was 4.0 -> floor 1.0mm (< 2.5mm). intent wall_mm is now 5.5 -> floor 5.5-3.0 =
    # 2.5mm >= C-B4 2.5mm. wall_t is read from intent so this is intent-driven.
    body = _counterbore_x(body, wx, wall_t, float(body_bore["diameter_mm"]), depth=3.0)
    # upstream M2 cross ring at radius 8 (y,z) -> through both walls in one X pass.
    up_centers = [(wx, yy, zz) for (yy, zz) in up_c["cross_centers_yz_mm"]]
    body = _drill_x(body, up_centers, float(up_c["hole_diameter_mm"]))
    # downstream M2 holes along X at the boss.
    body = _drill_x(body, dn_centers, float(dn_c["hole_diameter_mm"]))
    return body


def _families(step_path: Path) -> list[dict]:
    r = cylinder_faces(step_path)
    return r.get("hole_families", [])


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("outputs/parts"))
    ap.add_argument("--samples", type=int, default=8000)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    intent = PartIntent.load(INTENT)
    dn_servo_name = {f.name: f for f in intent.features}["downstream_servo_mount"].servo
    downstream = _SERVOS[dn_servo_name]          # original spec: XL330
    upstream = domain.XL430

    orig = make_shoulder_to_elbow(upstream, downstream, intent)
    f_orig = parametric.export(orig, a.out / "shoulder_to_elbow_orig")

    swapped = make_shoulder_to_elbow(upstream, domain.XL430, intent)
    f_swap = parametric.export(swapped, a.out / "shoulder_to_elbow_xl430")

    out = {"orig": f_orig, "xl430": f_swap,
           "spec": {"upstream": upstream.name, "downstream_orig": downstream.name,
                    "downstream_swap": domain.XL430.name}}

    # C-A1: honest mesh gap to the real organic part (expected NOT equivalent).
    if REAL_STL.exists():
        gap = compare(REAL_STL, a.out / "shoulder_to_elbow_orig.stl", a.samples)
        out["C_A1_gap_to_real"] = {
            "bbox_delta_mm": gap["bbox_delta_mm"],
            "surface_max_mm": gap["surface_distance"]["max_mm"],
            "surface_mean_mm": gap["surface_distance"]["mean_mm"],
            "volume_delta_pct": gap["volume_delta_pct"],
            "equivalent": verdict(gap, EquivalenceThresholds())["equivalent"],
            "note": "interface reconstruction; organic outer surface differs -> C-A1 gap is expected & quantified",
        }
    # C-A2: hole-family match (the real acceptance gate) — real vs reconstructed.
    if brep_available() and REAL_STEP.exists():
        out["C_A2_families"] = {
            "real": _families(REAL_STEP),
            "recon_orig": _families(Path(a.out / "shoulder_to_elbow_orig.step")),
        }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
