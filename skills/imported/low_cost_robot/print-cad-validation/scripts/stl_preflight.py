#!/usr/bin/env python3
"""Generic STL printability preflight.

Reports mesh watertightness, volume validity, winding consistency, bbox, triangle count,
and boundary/non-manifold edge examples. This script does not repair meshes; use it to
decide whether CAD-side or slicer-side repair is required.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def edge_anomalies(mesh: trimesh.Trimesh, limit: int = 8) -> tuple[int, list[dict]]:
    unique, counts = np.unique(mesh.edges_sorted, axis=0, return_counts=True)
    bad = unique[counts != 2]
    bad_counts = counts[counts != 2]
    examples = []
    for edge, count in zip(bad[:limit], bad_counts[:limit]):
        pts = mesh.vertices[edge]
        examples.append(
            {
                "occurrences": int(count),
                "points": pts.round(6).tolist(),
                "midpoint": pts.mean(axis=0).round(6).tolist(),
                "length": round(float(np.linalg.norm(pts[0] - pts[1])), 6),
            }
        )
    return int(len(bad)), examples


def inspect_stl(path: Path) -> dict:
    mesh = trimesh.load(path, force="mesh")
    bad_edges, examples = edge_anomalies(mesh)
    passed = bool(mesh.is_watertight and mesh.is_volume and bad_edges == 0)
    return {
        "file": str(path),
        "passed": passed,
        "watertight": bool(mesh.is_watertight),
        "is_volume": bool(mesh.is_volume),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "triangles": int(len(mesh.faces)),
        "vertices": int(len(mesh.vertices)),
        "bbox": [round(float(x), 3) for x in mesh.bounding_box.extents],
        "volume": round(float(mesh.volume), 3) if mesh.is_volume else None,
        "nonmanifold_or_boundary_edges": bad_edges,
        "edge_anomaly_examples": examples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stl", type=Path, nargs="+")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on-error", action="store_true")
    args = parser.parse_args()

    results = [inspect_stl(path) for path in args.stl]
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for result in results:
            status = "PASS" if result["passed"] else "FAIL"
            print(
                f"{status} {result['file']} watertight={result['watertight']} "
                f"is_volume={result['is_volume']} bad_edges={result['nonmanifold_or_boundary_edges']} "
                f"bbox={result['bbox']}"
            )
    return 2 if args.fail_on_error and not all(item["passed"] for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
