"""Generic geometric-equivalence checker between two solids (mesh or STEP).

Backs the "equivalent-shape-first" workflow: rebuild a part parametrically, then
prove it matches the original before changing any parameter. No domain terms.
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass

import numpy as np
import trimesh


@dataclass(frozen=True)
class EquivalenceThresholds:
    max_bbox_mm: float = 0.5
    max_surface_mm: float = 0.5
    max_volume_pct: float = 2.0


def _load(path: Path) -> trimesh.Trimesh:
    return trimesh.load(path, force="mesh")


def surface_distance(a: trimesh.Trimesh, b: trimesh.Trimesh, samples: int = 20000) -> dict:
    pa, pb = a.sample(samples), b.sample(samples)
    _, da, _ = b.nearest.on_surface(pa)
    _, db, _ = a.nearest.on_surface(pb)
    both = np.concatenate([da, db])
    return {
        "mean_mm": round(float(both.mean()), 4),
        "rms_mm": round(float(np.sqrt((both ** 2).mean())), 4),
        "max_mm": round(float(both.max()), 4),
        "p95_mm": round(float(np.percentile(both, 95)), 4),
    }


def compare(original: Path, candidate: Path, samples: int = 20000) -> dict:
    a, b = _load(original), _load(candidate)
    ea, eb = sorted(a.bounding_box.extents, reverse=True), \
        sorted(b.bounding_box.extents, reverse=True)
    # Guard non-watertight meshes: no valid volume -> None (never NaN in JSON).
    va = float(a.volume) if a.is_volume else None
    vb = float(b.volume) if b.is_volume else None
    vol_pct = (round(100 * (vb - va) / va, 3)
               if (va not in (None, 0) and vb is not None) else None)
    return {
        "original": str(original), "candidate": str(candidate),
        "bbox_original_mm": [round(x, 3) for x in ea],
        "bbox_candidate_mm": [round(x, 3) for x in eb],
        "bbox_delta_mm": [round(float(x - y), 4) for x, y in zip(ea, eb)],
        "volume_original_mm3": round(va, 2) if va is not None else None,
        "volume_candidate_mm3": round(vb, 2) if vb is not None else None,
        "volume_delta_pct": vol_pct,
        "watertight": {"original": bool(a.is_watertight),
                       "candidate": bool(b.is_watertight)},
        "surface_distance": surface_distance(a, b, samples),
    }


def verdict(cmp: dict, th: EquivalenceThresholds = EquivalenceThresholds()) -> dict:
    checks = {
        "bbox": max(abs(x) for x in cmp["bbox_delta_mm"]) <= th.max_bbox_mm,
        "surface_max": cmp["surface_distance"]["max_mm"] <= th.max_surface_mm,
        "volume": (cmp["volume_delta_pct"] is not None
                   and abs(cmp["volume_delta_pct"]) <= th.max_volume_pct),
    }
    return {"checks": checks, "equivalent": all(checks.values())}
