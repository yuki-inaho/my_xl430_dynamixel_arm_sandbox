"""Parametric two-servo connector — the `make_connector(upstream, downstream)` API.

Mirrors the design-intent methodology: the SAME function reproduces the original
(XL430→XL330) and then performs the swap (XL430→XL430) by changing one argument.
Built from generic cadre primitives; the only domain input is the two Components.

HONESTY NOTE: this is an *interface primitive* (two assemblable servo cradles on a
beam), NOT a faithful stage-1 reconstruction of the organic Fusion bracket. `main`
quantifies the real gap to the original STL so the claim stays grounded — closing
that gap (a true equivalence-passing reconstruction) is on the backlog.

    uv run python studies/xl430_lowcost/connector.py --out outputs/connector
"""
from __future__ import annotations
import sys
import json
import argparse
from pathlib import Path

import cadquery as cq

from cadre import parametric, compare, verdict, EquivalenceThresholds
from cadre.geometry import Component
import domain

# Measured from follower/shoulder_to_elbow.step (brep bbox Y-extent / beam section).
JOINT_DISTANCE = 132.0
BEAM_W, BEAM_T = 20.0, 12.0
REAL_PART = Path(__file__).resolve().parents[4] / \
    "hardware/follower/stl/shoulder_to_elbow.stl"


def make_connector(upstream: Component, downstream: Component,
                   joint_distance: float = JOINT_DISTANCE,
                   wall: float = 4.0, clearance: float = 0.5) -> cq.Workplane:
    """A link beam carrying an upstream and a downstream servo cradle. Each cradle
    is open on +Z so the servo can be inserted; sized to its Component envelope so
    the connector adapts automatically when either servo spec changes."""
    up = parametric.clearance_pocket(upstream.envelope, clearance, wall, open_face="+Z")
    up = up.translate((0, joint_distance / 2, 0))
    down = parametric.clearance_pocket(downstream.envelope, clearance, wall, open_face="+Z")
    down = down.translate((0, -joint_distance / 2, 0))
    beam = cq.Workplane("XY").box(BEAM_W, joint_distance, BEAM_T)
    return beam.union(up).union(down)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("outputs/connector"))
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    stage1 = make_connector(domain.XL430, domain.XL330)   # equivalent-shape stage
    swapped = make_connector(domain.XL430, domain.XL430)  # parameter-swap stage
    f1 = parametric.export(stage1, a.out / "connector_XL430_to_XL330")
    f2 = parametric.export(swapped, a.out / "connector_XL430_to_XL430")

    out = {"connectors": {"XL430_to_XL330": f1, "XL430_to_XL430": f2}}

    # Parameter-swap evidence: same code, one Component changed.
    swap = compare(a.out / "connector_XL430_to_XL330.stl",
                   a.out / "connector_XL430_to_XL430.stl", samples=6000)
    out["parameter_swap_delta"] = {"bbox_delta_mm": swap["bbox_delta_mm"],
                                   "volume_delta_pct": swap["volume_delta_pct"]}

    # Honest gap to the real organic part (expected: NOT equivalent yet).
    if REAL_PART.exists():
        gap = compare(REAL_PART, a.out / "connector_XL430_to_XL330.stl", samples=6000)
        gap_verdict = verdict(gap, EquivalenceThresholds())
        out["gap_to_real_part"] = {
            "real": str(REAL_PART), "surface_max_mm": gap["surface_distance"]["max_mm"],
            "bbox_delta_mm": gap["bbox_delta_mm"], "equivalent": gap_verdict["equivalent"],
            "note": "interface primitive, not a faithful reconstruction — gap is expected",
        }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
