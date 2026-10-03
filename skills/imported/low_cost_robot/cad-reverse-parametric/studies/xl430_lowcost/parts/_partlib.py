"""Shared geometry helpers for the study parts (DRY).

These are study-specific conveniences built on cadquery; the truly generic primitives
live in cadre.parametric. Each part module imports from here instead of redefining the
same drill / blind-seat / repo-path logic.
"""
from __future__ import annotations
from pathlib import Path

import cadquery as cq

# Repo root from a parts/<file>.py: 0=parts 1=xl430_lowcost 2=studies
# 3=cad-reverse-parametric 4=skills 5=repo
REPO = Path(__file__).resolve().parents[5]
HW_STEP = REPO / "hardware/follower/step"
HW_STL = REPO / "hardware/follower/stl"

_PLANE = {"X": "YZ", "Y": "XZ", "Z": "XY"}


def drill(solid: cq.Workplane, centers_xyz, diameter: float, axis: str,
          length: float = 400.0) -> cq.Workplane:
    """Cut THROUGH cylindrical holes along a principal `axis` ('X'|'Y'|'Z') at the
    given absolute (x, y, z) centers. `length` is over-long to cut fully through."""
    tool = cq.Workplane(_PLANE[axis]).circle(diameter / 2).extrude(length, both=True)
    for c in centers_xyz:
        solid = solid.cut(tool.translate(tuple(c)))
    return solid


def blind_seat(solid: cq.Workplane, center, diameter: float, depth: float,
               face: float, axis: str, into: int = -1) -> cq.Workplane:
    """Cut a BLIND recess of `depth` into the outer face at coordinate `face` along
    `axis`. `into` is the sign of the cut direction (the body side): -1 cuts toward
    -axis (face on the +axis side, e.g. Y=42 wall), +1 cuts toward +axis (face on the
    -axis side, e.g. a Z=0 bottom face with the body above). `center` is a 3-tuple;
    its axis coordinate is ignored. The caller must ensure sufficient material
    behind the requested depth; this cutter cannot guarantee residual thickness."""
    cx, cy, cz = center
    plane = _PLANE[axis]
    # XZ has a -Y normal; `into` describes the world axis, not the plane normal.
    normal_sign = -1 if axis == "Y" else 1
    tool = cq.Workplane(plane).circle(diameter / 2).extrude(normal_sign * into * depth)
    # place the tool's workplane origin on the face
    off = {"X": (face, cy, cz), "Y": (cx, face, cz), "Z": (cx, cy, face)}[axis]
    return solid.cut(tool.translate(off))


def report_main(name: str, build, swap_build=None, samples: int = 8000,
                out=Path("outputs/parts")) -> dict:
    """Shared CLI body: export the stage-1 (orig) solid, optionally the XL430-swapped
    solid, then print the C-A1 mesh gap and C-A2 hole-family comparison vs the real
    part. `build()` returns the stage-1 model; `swap_build()` (or None for swap-not-
    applicable parts) returns the XL430 model."""
    import json
    from cadre import (parametric, compare, verdict, EquivalenceThresholds,
                       cylinder_faces, brep_available)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    import trimesh
    orig = build()
    files = {"orig": parametric.export(orig, out / f"{name}_orig")}
    result = {"part": name, "files": files, "swap_applicable": swap_build is not None}
    if swap_build is not None:
        files["xl430"] = parametric.export(swap_build(), out / f"{name}_xl430")
        # Honest swap-effect measurement: if the XL430 variant is geometrically
        # identical to stage-1, the part does not need reshaping for XL430 (it mounts
        # on the horn / is already wider than the body). Reported, never hidden.
        vo = trimesh.load(out / f"{name}_orig.stl", force="mesh").volume
        vx = trimesh.load(out / f"{name}_xl430.stl", force="mesh").volume
        result["swap_delta"] = {
            "volume_orig_mm3": round(float(vo), 2),
            "volume_xl430_mm3": round(float(vx), 2),
            "volume_delta_mm3": round(float(vx - vo), 2),
            "geometric_noop": abs(float(vx - vo)) < 1.0,
        }

    real_stl, real_step = HW_STL / f"{name}.stl", HW_STEP / f"{name}.step"
    if real_stl.exists():
        gap = compare(real_stl, out / f"{name}_orig.stl", samples)
        result["C_A1_gap_to_real"] = {
            "bbox_delta_mm": gap["bbox_delta_mm"],
            "surface_max_mm": gap["surface_distance"]["max_mm"],
            "surface_mean_mm": gap["surface_distance"]["mean_mm"],
            "volume_delta_pct": gap["volume_delta_pct"],
            "watertight": gap["watertight"],
            "equivalent": verdict(gap, EquivalenceThresholds())["equivalent"],
        }
    if brep_available() and real_step.exists():
        result["C_A2_families"] = {
            "real": cylinder_faces(real_step)["hole_families"],
            "recon": cylinder_faces(Path(out / f"{name}_orig.step"))["hole_families"],
        }
    print(json.dumps(result, indent=2))
    return result
