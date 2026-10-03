"""Functional / characterization checks for test-driven CAD refactoring.

These are the assertions that pin *behaviour* (not just looks): axis alignment,
hole-pattern match, envelope clearance. Use them as characterization tests on the
original, keep them green through the equivalent-shape reconstruction, then carry
the function-level ones across the parameter swap.

Pure geometry (numpy) + optional mesh containment (trimesh). Domain-agnostic.
"""
from __future__ import annotations
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    value: float | None = None
    detail: str = ""


def _unit(v) -> np.ndarray:
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n else v


def axes_collinear(point_a, dir_a, point_b, dir_b,
                   max_angle_deg: float = 0.5, max_dist_mm: float = 0.1) -> CheckResult:
    """Do two axis lines coincide (parallel within angle AND close within dist)?

    Used e.g. to assert the servo output axis and the idler axis are the same line.
    """
    ua, ub = _unit(dir_a), _unit(dir_b)
    cosang = abs(float(np.clip(np.dot(ua, ub), -1, 1)))
    angle = np.degrees(np.arccos(cosang))
    pa, pb = np.asarray(point_a, float), np.asarray(point_b, float)
    cross = np.cross(ua, ub)
    ncross = np.linalg.norm(cross)
    if ncross < 1e-9:                       # parallel → point-to-line distance
        dist = float(np.linalg.norm(np.cross(pb - pa, ua)))
    else:                                   # skew → common-perpendicular distance
        dist = float(abs(np.dot(pb - pa, cross / ncross)))
    ok = angle <= max_angle_deg and dist <= max_dist_mm
    return CheckResult("axes_collinear", ok, round(dist, 4),
                       f"angle={angle:.3f}deg dist={dist:.4f}mm")


def hole_pattern_match(centers_a, centers_b, tol_mm: float = 0.15) -> CheckResult:
    """Greedy nearest-neighbour match between two hole-center sets (same frame)."""
    A = [np.asarray(c, float) for c in centers_a]
    B = [np.asarray(c, float) for c in centers_b]
    if len(A) != len(B):
        return CheckResult("hole_pattern_match", False, None,
                           f"count mismatch {len(A)} vs {len(B)}")
    remaining = list(B)
    worst = 0.0
    for a in A:
        if not remaining:
            break
        dists = [float(np.linalg.norm(a - b)) for b in remaining]
        j = int(np.argmin(dists))
        worst = max(worst, dists[j])
        remaining.pop(j)
    ok = worst <= tol_mm
    return CheckResult("hole_pattern_match", ok, round(worst, 4),
                       f"max nearest-neighbour {worst:.4f}mm (tol {tol_mm})")


def envelope_clearance(model_mesh, keepout_mesh, samples: int = 5000) -> CheckResult:
    """No part material inside the servo keepout: sample keepout, none may be
    inside the model. Both args are trimesh.Trimesh (watertight)."""
    pts = keepout_mesh.sample(samples)
    try:
        inside = model_mesh.contains(pts)
        n_in = int(np.count_nonzero(inside))
    except Exception as e:                  # non-watertight → cannot decide
        return CheckResult("envelope_clearance", False, None, f"contains() failed: {e!r}")
    ok = n_in == 0
    return CheckResult("envelope_clearance", ok, float(n_in),
                       f"{n_in}/{samples} keepout samples inside the part")
