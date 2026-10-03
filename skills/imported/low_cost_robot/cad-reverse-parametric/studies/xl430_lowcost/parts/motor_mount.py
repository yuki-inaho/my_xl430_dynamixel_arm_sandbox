"""Building block: a parametric Dynamixel motor-mount, driven by a Component.

Demonstrates the swap mechanism concretely. The SAME code emits an XL330 or an
XL430 mount — only the injected `Component` (envelope + screw) changes. The hole
pattern is the DXL X-series cross recovered by brep_probe from the originals.

This is a reusable *interface primitive*, not a 1:1 reproduction of the organic
bracket. Stage-1 reconstruction composes blocks like this, then the equivalence
gate (cadre.cli equiv) measures the gap to the original.

    uv run python studies/xl430_lowcost/parts/motor_mount.py --out outputs/parts
"""
from __future__ import annotations
import sys
import json
import argparse
from pathlib import Path

import cadquery as cq

from cadre import Envelope, parametric
from cadre.geometry import Component
import domain

# DXL X-series face screw cross, recovered from the originals (±8 mm, M2).
DXL_CROSS = [(0.0, 8.0), (0.0, -8.0), (8.0, 0.0), (-8.0, 0.0)]
# Catalog clearance-hole diameter per mount screw spec.
_SCREW_DIA = {"M2": 2.4, "M2.5": 2.9, "M3": 3.4}


def motor_mount(servo: Component, wall: float = 4.0, clearance: float = 0.5,
                back_plate: float = 4.0) -> cq.Workplane:
    """A cradle that wraps the servo body with `wall`, plus a screw-faced back."""
    body = servo.envelope
    screw = servo.meta.get("mount_screw", "M2")
    dia = _SCREW_DIA.get(screw, 2.4)
    # Cradle = clearance pocket around the body.
    cradle = parametric.clearance_pocket(body, clearance=clearance, wall=wall)
    # Back plate carrying the DXL cross hole pattern, sized to the body face.
    plate_w = body.w + 2 * (clearance + wall)
    plate_h = body.h + 2 * clearance
    plate = parametric.adapter_plate(DXL_CROSS, dia, plate_w, plate_h, back_plate)
    plate = plate.translate((0, -(body.d / 2 + clearance + wall + back_plate / 2), 0))
    return cradle.union(plate)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("outputs/parts"))
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    written = {}
    for servo in (domain.XL330, domain.XL430):
        tag = servo.name.replace("-", "_").replace(".", "")
        model = motor_mount(servo)
        files = parametric.export(model, a.out / f"mount_{tag}")
        written[servo.name] = files
    print(json.dumps({"parts": written}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
