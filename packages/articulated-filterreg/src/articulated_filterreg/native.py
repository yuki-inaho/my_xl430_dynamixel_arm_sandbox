"""Validated adapters to the shared C++ numerical core.

``AF_BINDING=nanobind`` requires the nanobind extension. The explicit ``ctypes``
choice uses the separate C ABI. An unavailable extension never triggers a silent
binding change, and native resource ownership stays within this module.
"""
from __future__ import annotations

import ctypes as ct
import os
from pathlib import Path
from types import TracebackType

import numpy as np

BINDING = os.environ.get("AF_BINDING", "nanobind")

if BINDING == "nanobind":
    from . import _native
elif BINDING == "ctypes":
    _default_library = Path(__file__).resolve().parents[2] / "build/libaf_capi.so"
    _library_path = Path(os.environ.get("AF_CAPI_PATH", _default_library))
    _lib = ct.CDLL(str(_library_path))
    _double_array = np.ctypeslib.ndpointer(dtype=np.float64, flags="C_CONTIGUOUS")
    _int_array = np.ctypeslib.ndpointer(dtype=np.int32, flags="C_CONTIGUOUS")
    _lib.af_last_error.restype = ct.c_char_p
    _lib.af_create.argtypes = [_double_array, ct.c_int, ct.c_double, ct.c_int]
    _lib.af_create.restype = ct.c_void_p
    _lib.af_destroy.argtypes = [ct.c_void_p]
    _lib.af_destroy.restype = None
    _lib.af_evaluate.argtypes = [ct.c_void_p, _double_array, ct.c_int, _double_array]
    _lib.af_evaluate.restype = ct.c_int
    _lib.af_assemble.argtypes = [
        _double_array, _double_array, _double_array, _int_array, ct.c_int,
        _double_array, ct.c_int, ct.c_int, _double_array, _double_array,
    ]
    _lib.af_assemble.restype = ct.c_int
else:
    raise ValueError("AF_BINDING must be nanobind or ctypes")


def _error() -> RuntimeError:
    """Copy the native error before a later C ABI call can replace it."""
    return RuntimeError(_lib.af_last_error().decode("utf-8", "replace"))


def _cloud(value: np.ndarray, name: str) -> np.ndarray:
    cloud = np.ascontiguousarray(value, dtype=np.float64)
    if (cloud.ndim != 2 or cloud.shape[1] != 3 or len(cloud) == 0
            or not np.isfinite(cloud).all()):
        raise ValueError(f"{name} must be finite nonempty (n,3)")
    if len(cloud) > np.iinfo(np.int32).max:
        raise ValueError(f"{name} exceeds the C ABI row-count range")
    return cloud


class GaussianMoments:
    """Own a fixed-observation filter; use as a context manager when possible."""

    def __init__(self, observations: np.ndarray, sigma: float, mode: str = "lattice"):
        self._handle = None
        self._object = None
        target = _cloud(observations, "observations")
        if not np.isfinite(sigma) or sigma <= 0:
            raise ValueError("sigma must be positive")
        if mode not in ("lattice", "direct"):
            raise ValueError("mode must be lattice or direct")
        if BINDING == "nanobind":
            self._object = _native.MomentFilter(target, float(sigma), mode == "direct")
        else:
            self._handle = _lib.af_create(target, len(target), sigma, int(mode == "direct"))
            if not self._handle:
                raise _error()

    def evaluate(self, queries: np.ndarray) -> np.ndarray:
        """Return columns [mass, weighted x/y/z, weighted squared norm]."""
        points = _cloud(queries, "queries")
        if BINDING == "nanobind":
            if self._object is None:
                raise RuntimeError("filter is closed")
            return self._object.evaluate(points)
        if self._handle is None:
            raise RuntimeError("filter is closed")
        output = np.empty((len(points), 5), dtype=np.float64)
        if _lib.af_evaluate(self._handle, points, len(points), output):
            raise _error()
        return output

    def close(self) -> None:
        """Release the native owner; repeated calls are safe."""
        self._object = None
        if self._handle is not None:
            _lib.af_destroy(self._handle)
            self._handle = None

    def __enter__(self) -> GaussianMoments:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __del__(self):
        if getattr(self, "_handle", None) is not None:
            self.close()


def assemble_blocks(
    points: np.ndarray,
    targets: np.ndarray,
    weights: np.ndarray,
    body: np.ndarray,
    space_maps: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Reduce point residuals through fixed-size per-body similarity blocks.

    Validate body indices before narrowing to int32, so a large int64/uint64
    cannot wrap around to a valid but incorrect body index.
    """
    source = _cloud(points, "points")
    target = _cloud(targets, "targets")
    raw_body = np.asarray(body)
    weight = np.ascontiguousarray(weights, dtype=np.float64)
    maps = np.ascontiguousarray(space_maps, dtype=np.float64)

    if not np.issubdtype(raw_body.dtype, np.integer):
        raise ValueError("body indices must have an integer dtype")
    if (target.shape != source.shape or weight.shape != (len(source),)
            or raw_body.shape != (len(source),)):
        raise ValueError("point array sizes differ")
    if (maps.ndim != 3 or maps.shape[1] != 7 or maps.shape[0] == 0
            or maps.shape[2] == 0):
        raise ValueError("space_maps must be (bodies,7,d)")
    if (maps.shape[0] > np.iinfo(np.int32).max or maps.shape[2] > 128):
        raise ValueError("space_maps exceed native body or parameter limits")
    if (not np.isfinite(maps).all() or not np.isfinite(weight).all()
            or (weight < 0).any() or (raw_body < 0).any()
            or (raw_body >= len(maps)).any()):
        raise ValueError("invalid map, weight, or body value")
    body_index = np.ascontiguousarray(raw_body, dtype=np.int32)

    if BINDING == "nanobind":
        return _native.assemble_blocks(source, target, weight, body_index, list(maps))
    parameter_count = maps.shape[2]
    hessian = np.empty((parameter_count, parameter_count), dtype=np.float64)
    gradient = np.empty(parameter_count, dtype=np.float64)
    if _lib.af_assemble(
        source, target, weight, body_index, len(source), maps, len(maps),
        parameter_count, hessian, gradient,
    ):
        raise _error()
    return hessian, gradient
