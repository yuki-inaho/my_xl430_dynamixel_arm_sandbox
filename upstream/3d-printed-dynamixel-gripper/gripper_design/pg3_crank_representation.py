"""Source-equivalent crank candidate with deferred face unification.

Reuses the supplied construction and dimensions, changing only when clean() is
called. Used by the installation candidate, not a fabrication release.
Saved-artifact validation is required; an in-memory Boolean alone is insufficient.
"""

import hashlib
import importlib.util
import sys
import uuid
from functools import reduce
from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "references/pg3-c9/PG3_C92_J28/reference/C7/source/design.py"
)
SOURCE_SHA256 = "c20f0dd65fa1338ba3d42c9424990937bd161b491b5a937e429a84ccf4bb25d0"


def build_candidate(source=SOURCE):
    source = Path(source)
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("source SHA differs from reviewed construction")
    name = f"_pg3_crank_representation_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        # Same CSG order and tools. Suppress only intermediate same-domain cleanup.
        module.cut = lambda shape, *tools: reduce(lambda a, b: a.cut(b), tools, shape)
        module.fuse = lambda *shapes: shapes[0].fuse(*shapes[1:])
        shape = module.crank(module.P).clean()
    finally:
        del sys.modules[name]
    if not shape.isValid() or len(shape.Solids()) != 1 or shape.Volume() <= 0:
        raise ValueError("invalid crank candidate")
    return shape
