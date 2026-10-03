"""Reproduce saved-face identity failure across isolated CadQuery environments.

Diagnostic only: no healing, tolerance override, CAD export or acceptance.
The only project dependency is the read-only STEP occurrence reader.
"""

import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path

from scripts.assembly_io import bounds, read_step


def identity_measurement(shape, dimension):
    measure = "Area" if dimension == 2 else "Volume"
    source = getattr(shape, measure)()
    common = shape.intersect(shape.copy())
    cut = shape.cut(shape.copy())
    values = [source, getattr(common, measure)(), getattr(cut, measure)()]
    if not all(math.isfinite(v) for v in values):
        raise ValueError("nonfinite diagnostic measurement")
    return {
        "source": values[0],
        "self_common": values[1],
        "self_cut": values[2],
        "dimension": dimension,
        "source_valid": shape.isValid(),
        "common_valid": common.isValid(),
        "cut_valid": cut.isValid(),
        "bbox_mm": bounds(shape),
    }


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(checkpoint, out):
    if out.exists():
        raise FileExistsError(out)
    manifest_path = checkpoint / "review.json"
    manifest = json.loads(manifest_path.read_text())
    result = {
        "scope": "independent-copy identity diagnostic, not clearance",
        "versions": {
            name: importlib.metadata.version(name) for name in ("cadquery", "cadquery-ocp")
        },
        "checker_sha256": digest(Path(__file__)),
        "reader_sha256": digest(Path(__file__).with_name("assembly_io.py")),
        "manifest_sha256": digest(manifest_path),
        "geometry_modified": False,
        "installation_approved": False,
        "poses": {},
    }
    for pose in ("open", "mid", "closed"):
        path = checkpoint / f"arm_camera_{pose}_CANDIDATE.step"
        sha = digest(path)
        if sha != manifest["output_sha256"][path.name]:
            raise ValueError("saved assembly hash mismatch")
        matches = [r.world for r in read_step(path)[2] if r.name == "PG3_crank"]
        if len(matches) != 1:
            raise ValueError("one crank occurrence required")
        host = matches[0]
        face = host.Faces()[5]
        if face.geomType() != "CYLINDER":
            raise ValueError("diagnostic face identity changed")
        row = {
            "assembly_sha256": sha,
            "world_solid": identity_measurement(host, 3),
            "world_face5": identity_measurement(face, 2),
            "translated_face5": identity_measurement(face.translate((-20.3, -234.9, -164.6)), 2),
            "common_translation_mm": [-20.3, -234.9, -164.6],
        }
        result["poses"][pose] = row
        print(pose, row["world_face5"], flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
