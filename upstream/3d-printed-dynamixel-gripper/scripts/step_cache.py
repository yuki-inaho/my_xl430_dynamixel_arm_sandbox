"""Content-addressed disk cache for STEP assembly rows (test-suite speed).

``read_rows(path)`` returns the same rows as ``scripts.assembly_io.read_step(path)[2]``.
The cache is opt-in through ``CAD_STEP_CACHE_DIR`` (tests/conftest.py sets it to a
directory under ``.pytest_cache``); without it every call parses the STEP again.
Kept out of ``assembly_io`` so that module, which evidence runs snapshot as a
dependency, stays byte-identical.
"""

import hashlib
import importlib.metadata
import json
import os
from contextlib import contextmanager
from pathlib import Path

import cadquery as cq
from OCP.BinTools import BinTools, BinTools_FormatVersion
from OCP.gp import gp_Trsf
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS_Iterator, TopoDS_Shape

from scripts.assembly_io import Occurrence, read_step

CACHE_ENV = "CAD_STEP_CACHE_DIR"
_CACHE_FORMAT = 1


def read_rows(path):
    """Occurrences of a STEP assembly, like ``read_step(path)[2]``.

    When ``CAD_STEP_CACHE_DIR`` is set, rows are served from a content-addressed
    binary BREP cache instead of re-parsing the STEP. The key is the STEP file's
    SHA-256 plus the OCP/CadQuery versions and cache format, so any change to the
    file or the kernel re-parses. Cached rows carry the same index, path, name,
    color, location and unlocated shape (sub-shape sharing preserved); ``label``
    is None because no XCAF document exists. Triangulation is never cached, so a
    mesh added by one caller cannot leak into another caller's bounding boxes.
    """
    cache_dir = os.environ.get(CACHE_ENV)
    if not cache_dir:
        return read_step(path)[2]
    return _cached_rows(Path(path), Path(cache_dir))


def _cache_key(path):
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    versions = ":".join(
        [str(_CACHE_FORMAT)]
        + [importlib.metadata.version(p) for p in ("cadquery-ocp", "cadquery")]
    )
    return hashlib.sha256(f"{versions}:{digest}".encode()).hexdigest()[:32]


@contextmanager
def _exclusive(lock_path):
    """Serialize cache fills across pytest-xdist workers (POSIX); no-op elsewhere."""
    try:
        import fcntl
    except ImportError:  # pragma: no cover - non-POSIX
        yield
        return
    with open(lock_path, "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _trsf_values(loc):
    t = loc.wrapped.Transformation()
    return [t.Value(i, j) for i in range(1, 4) for j in range(1, 5)]


def _location(values):
    t = gp_Trsf()
    t.SetValues(*values)
    return cq.Location(TopLoc_Location(t))


def _write_cache(rows, brep, meta):
    compound = cq.Compound.makeCompound([r.shape for r in rows])
    tmp_brep, tmp_meta = brep.with_suffix(".brep.tmp"), meta.with_suffix(".json.tmp")
    if not BinTools.Write_s(
        compound.wrapped, str(tmp_brep), False, False, BinTools_FormatVersion.BinTools_FormatVersion_CURRENT
    ):
        raise OSError(f"cannot write {tmp_brep}")
    records = [
        {
            "index": r.index,
            "path": r.path,
            "name": r.name,
            "loc": _trsf_values(r.loc),
            "color": None if r.color is None else list(r.color.toTuple()),
        }
        for r in rows
    ]
    brep_sha = hashlib.sha256(tmp_brep.read_bytes()).hexdigest()
    tmp_meta.write_text(json.dumps({"format": _CACHE_FORMAT, "brep_sha256": brep_sha, "rows": records}))
    os.replace(tmp_brep, brep)  # BREP first: metadata marks the entry complete
    os.replace(tmp_meta, meta)


class CacheEntryInvalid(ValueError):
    """A cache entry is missing, truncated or altered; it is rebuilt from the STEP."""


def _load_cache(brep, meta):
    try:
        header = json.loads(meta.read_text())
        payload = brep.read_bytes()
    except (OSError, ValueError) as exc:
        raise CacheEntryInvalid(f"unreadable cache entry {meta.name}: {exc}") from exc
    if header.get("format") != _CACHE_FORMAT or hashlib.sha256(payload).hexdigest() != header.get(
        "brep_sha256"
    ):
        raise CacheEntryInvalid(f"cache entry {brep.name} does not match its recorded digest")
    records = header["rows"]
    compound = TopoDS_Shape()
    if not BinTools.Read_s(compound, str(brep)):
        raise OSError(f"cannot read {brep}")
    children = []
    it = TopoDS_Iterator(compound)
    while it.More():
        children.append(cq.Shape.cast(it.Value()))
        it.Next()
    if len(children) != len(records):
        raise ValueError(f"cache {brep.name}: {len(children)} shapes for {len(records)} rows")
    return [
        Occurrence(
            rec["index"],
            rec["path"],
            rec["name"],
            shape,
            _location(rec["loc"]),
            None,
            None if rec["color"] is None else cq.Color(*rec["color"]),
        )
        for rec, shape in zip(records, children)
    ]


def _cached_rows(path, cache_dir):
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(path)
    brep, meta = cache_dir / f"{key}.brep", cache_dir / f"{key}.json"
    if meta.exists():
        try:
            return _load_cache(brep, meta)
        except CacheEntryInvalid:
            pass  # rebuilt below from the STEP, the source of truth
    with _exclusive(cache_dir / f"{key}.lock"):
        try:  # another worker may have (re)filled it while we waited
            _load_cache(brep, meta)
        except CacheEntryInvalid:
            _write_cache(read_step(path)[2], brep, meta)
    # Always serve from the cache, so a cold fill and a warm hit return identical rows.
    return _load_cache(brep, meta)
