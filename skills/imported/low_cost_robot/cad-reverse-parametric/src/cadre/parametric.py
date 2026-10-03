"""Generic parametric primitives, driven by `Envelope` + hole patterns.

Domain-agnostic building blocks for reconstructing an interface part. The same
functions emit any size of block/pocket/plate; the *study* layer decides which
`Envelope` and which hole pattern to feed in.
"""
from __future__ import annotations
from pathlib import Path

import cadquery as cq

from .geometry import Envelope

Point2D = tuple[float, float]


def envelope_proxy(env: Envelope, clearance: float = 0.0) -> cq.Workplane:
    """Solid block of the component envelope (for interference checks)."""
    w, h, d = env.as_tuple()
    return cq.Workplane("XY").box(w + 2 * clearance, d + 2 * clearance,
                                  h + 2 * clearance)


def _access_window(env: Envelope, clearance: float, face: str) -> cq.Workplane:
    """A box that, when cut, opens the cavity through `face` ('+Z','-X',...).
    Cross-section = cavity; elongated outward along the face axis."""
    w, h, d = env.as_tuple()                       # envelope_proxy maps to box(w,d,h)
    sx, sy, sz = w + 2 * clearance, d + 2 * clearance, h + 2 * clearance
    axis, sign, big = face[-1].upper(), (1 if face[0] == "+" else -1), 1000.0
    off = [0.0, 0.0, 0.0]
    if axis == "X":
        sx, off[0] = big, sign * big / 2
    elif axis == "Y":
        sy, off[1] = big, sign * big / 2
    else:
        sz, off[2] = big, sign * big / 2
    return cq.Workplane("XY").box(sx, sy, sz).translate(tuple(off))


def clearance_pocket(env: Envelope, clearance: float = 0.5, wall: float = 3.0,
                     open_face: str | None = None) -> cq.Workplane:
    """Holder block with the (clearanced) component body subtracted. `open_face`
    (e.g. '+Z') removes that wall so the component can be inserted — without it the
    cavity is fully enclosed (an interference proxy, not an assemblable holder)."""
    w, h, d = env.as_tuple()
    outer = cq.Workplane("XY").box(w + 2 * (clearance + wall),
                                   d + 2 * (clearance + wall),
                                   h + 2 * clearance + wall)
    pocket = outer.cut(envelope_proxy(env, clearance))
    if open_face:
        pocket = pocket.cut(_access_window(env, clearance, open_face))
    return pocket


def adapter_plate(hole_centers: list[Point2D], hole_diameter: float,
                  plate_w: float, plate_h: float,
                  thickness: float = 3.0) -> cq.Workplane:
    """Flat plate carrying an arbitrary, re-pitchable hole pattern."""
    p = cq.Workplane("XY").box(plate_w, plate_h, thickness,
                               centered=(True, True, False))
    if hole_centers:
        p = (p.faces(">Z").workplane()
             .pushPoints(list(hole_centers))
             .circle(hole_diameter / 2).cutThruAll())
    return p


def export(model: cq.Workplane, stem: Path, formats=("step", "stl")) -> list[str]:
    written = []
    for fmt in formats:
        out = f"{stem}.{fmt}"
        cq.exporters.export(model, out)
        written.append(out)
    return written
