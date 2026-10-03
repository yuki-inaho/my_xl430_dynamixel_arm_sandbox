"""Original-shape-preserving model for follower/elbow_to_wrist_extension.

This part is an organic/asymmetric connector from a historyless STEP. The safe CAD
contract is therefore: keep the original B-rep as the source of truth and do not replace
the upstream end with a simplified circular collar. Local rounding/reinforcement around
the four servo fastening holes may be considered later, but only after a change mask and
original-shape preservation gate are defined.

    uv run python studies/xl430_lowcost/parts/elbow_to_wrist_extension.py --out outputs/parts
"""
from __future__ import annotations
import sys
import argparse
from pathlib import Path

import cadquery as cq

from cadre import PartIntent
from cadre.geometry import Component
_PARTS_DIR = Path(__file__).resolve().parent
_STUDY_DIR = _PARTS_DIR.parent
for _p in (_STUDY_DIR, _PARTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import _partlib as P
import domain

INTENT = Path(__file__).resolve().parents[1] / "intent" / "elbow_to_wrist_extension.yaml"
_SERVOS = {"XL330-M288-T": domain.XL330, "XL430-W250-T": domain.XL430}


def make_extension(servo: Component, intent: PartIntent | None = None) -> cq.Workplane:
    """Return the original STEP geometry unchanged.

    `servo` is intentionally accepted for API compatibility with the rest of the study, but
    it does not drive geometry for this part. The earlier circular-collar reconstruction
    passed local min-wall/interference tests while destroying the original outline. Until a
    bounded local edit is specified, this part is a measured no-op across XL330/XL430.
    """
    return cq.importers.importStep(str(P.HW_STEP / "elbow_to_wrist_extension.step"))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("outputs/parts"))
    ap.add_argument("--samples", type=int, default=8000)
    a = ap.parse_args(argv)
    intent = PartIntent.load(INTENT)
    servo_name = {f.name: f for f in intent.features}["upstream_horn_mount"].servo
    P.report_main("elbow_to_wrist_extension",
                  lambda: make_extension(_SERVOS[servo_name], intent),
                  swap_build=lambda: make_extension(domain.XL430, intent),
                  samples=a.samples, out=a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
