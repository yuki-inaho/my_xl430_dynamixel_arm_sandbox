"""Guarded local edits on an existing B-rep, without shape reconstruction."""
from __future__ import annotations

import math

import cadquery as cq


def _volume(shape: cq.Shape) -> float:
    if shape.wrapped.IsNull() or not shape.isValid():
        raise RuntimeError("Invalid Boolean result")
    values = [float(s.Volume(tol=1e-12)) for s in shape.Solids()]
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise RuntimeError("Invalid solid volume")
    return sum(values)


def _require_same_material(a: cq.Shape, b: cq.Shape, tolerance_mm3: float) -> None:
    va, vb = _volume(a), _volume(b)
    if min(va, vb) <= 0:
        raise RuntimeError("Material comparison requires positive-volume inputs")
    if _volume(a.cut(b)) + _volume(b.cut(a)) > tolerance_mm3:
        raise RuntimeError("Material differences exceed tolerance")
    # Some coincident-face failures produce empty CUT and COMMON together.
    # Empty differences alone therefore cannot establish material preservation.
    for common in (a.intersect(b), b.intersect(a)):
        vc = _volume(common)
        if max(abs(vc-va), abs(vc-vb)) > tolerance_mm3:
            raise RuntimeError("Common material does not preserve both inputs")


def extend_prismatic_section(
    shape: cq.Shape, *, axis: int, coordinate: float, delta: float,
    guard_half_width: float = 0.25, tolerance_mm3: float = 1e-7,
) -> cq.Shape:
    """Move one chunk outward and bridge it with the exact source section.

    Positive delta moves the positive-axis chunk; negative delta moves the
    negative-axis chunk. The opposite chunk is stationary. A zero delta returns
    a copy. The material within the guard slab must equal a constant-section
    prism, to the stated numerical volume tolerance. This rejects a cut across
    a transverse bore or a varying profile instead of silently stretching it.

    This is an axis-aligned *extension*, not scaling or contraction. Callers must
    separately authorize the moving region and check all relocated interfaces,
    assembly clearance, manufacturing tolerances and structural requirements.
    """
    if type(axis) is not int or axis not in (0, 1, 2):
        raise ValueError("axis must be 0, 1 or 2")
    if not all(math.isfinite(v) for v in (coordinate, delta, guard_half_width, tolerance_mm3)):
        raise ValueError("dimensions must be finite")
    if guard_half_width <= 0 or tolerance_mm3 <= 0:
        raise ValueError("guard and numerical tolerance must be positive")
    if shape.wrapped.IsNull() or not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError("input must be one valid solid")
    original_volume = _volume(shape)
    if original_volume <= 0:
        raise ValueError("input solid has no volume")
    # Self-cut can trivially return empty even when independently copied
    # geometry produces invalid Booleans. Such input cannot support this oracle.
    try:
        replica = shape.copy()
        _require_same_material(shape, replica, tolerance_mm3)
    except RuntimeError as exc:
        raise RuntimeError(f"Boolean identity preflight failed: {exc}") from exc
    box = shape.BoundingBox()
    low = [box.xmin, box.ymin, box.zmin]
    high = [box.xmax, box.ymax, box.zmax]
    if not low[axis] < coordinate-guard_half_width < coordinate+guard_half_width < high[axis]:
        raise ValueError("cut and guard must lie inside the solid bounds")
    if delta == 0:
        return shape.copy()

    def vector(amount):
        values = [0., 0., 0.]
        values[axis] = amount
        return cq.Vector(*values)

    def slab(start, end):
        origin = [v-1 for v in low]
        lengths = [b-a+2 for a, b in zip(low, high)]
        origin[axis], lengths[axis] = start, end-start
        return cq.Solid.makeBox(*lengths, cq.Vector(*origin))

    # Size the plane from the input bounds; its centre need not be world zero.
    centre = [(a+b)/2 for a, b in zip(low, high)]
    centre[axis] = coordinate
    span = max(b-a for a, b in zip(low, high))+2
    plane = cq.Face.makePlane(span, span, centre, vector(1))
    section = shape.intersect(plane)
    _volume(section)  # Check kernel validity even though a section has zero volume.
    faces = section.Faces()
    if not faces:
        raise ValueError("cut has no material section")

    def prism(start, length):
        pieces = [cq.Solid.extrudeLinear(f.outerWire(), f.innerWires(), vector(length))
                  .translate(vector(start)) for f in faces]
        result = cq.Compound.makeCompound(pieces)
        _volume(result)
        return result

    actual_guard = shape.intersect(slab(coordinate-guard_half_width, coordinate+guard_half_width))
    expected_guard = prism(-guard_half_width, 2*guard_half_width)
    actual_volume, prism_volume = _volume(actual_guard), _volume(expected_guard)
    if abs(actual_volume-prism_volume) > tolerance_mm3:
        raise ValueError("section is not prismatic: guard volumes differ")
    common_volume = _volume(actual_guard.intersect(expected_guard))
    if common_volume > min(actual_volume, prism_volume) + tolerance_mm3:
        raise RuntimeError("Inconsistent guard intersection volume")
    # Inclusion-exclusion avoids tangent zero-thickness slivers in two cuts.
    guard_error = actual_volume + prism_volume - 2*common_volume
    if guard_error < -tolerance_mm3:
        raise RuntimeError("Negative guard symmetric difference")
    if guard_error > tolerance_mm3:
        raise ValueError(f"section is not prismatic: symmetric difference {guard_error:.12g} mm3")

    negative = shape.intersect(slab(low[axis]-1, coordinate))
    positive = shape.intersect(slab(coordinate, high[axis]+1))
    if min(_volume(negative), _volume(positive)) <= 0:
        raise ValueError("cut must produce two material chunks")
    fixed, moving = (positive, negative) if delta < 0 else (negative, positive)
    moved = moving.translate(vector(delta))
    bridge = prism(0, delta)
    def cap(face, position):
        return (face.geomType() == "PLANE"
                and abs(abs(face.normalAt().toTuple()[axis])-1) < 1e-9
                and abs(face.Center().toTuple()[axis]-position) < 1e-7)

    # Join the existing faces at the two cut planes. A global fuse/clean can
    # re-trim unrelated imported faces, making later preservation Booleans fail.
    retained = [f for f in fixed.Faces() if not cap(f, coordinate)]
    retained += [f for f in moved.Faces() if not cap(f, coordinate+delta)]
    retained += [f for f in bridge.Faces()
                 if not cap(f, coordinate) and not cap(f, coordinate+delta)]
    result = cq.Solid.makeSolid(cq.Shell.makeShell(retained))
    _volume(result)
    if len(result.Solids()) != 1:
        raise ValueError("extension produced a disconnected solid")
    expected_bridge_volume = sum(f.Area() for f in faces)*abs(delta)
    if abs(_volume(bridge)-expected_bridge_volume) > tolerance_mm3:
        raise RuntimeError("bridge volume does not match section area times distance")
    # Imported trimmed surfaces can have non-additive mass integrals even after
    # a no-op split/rejoin. Verify the actual material of each region instead.
    regions = [
        (negative.translate(vector(min(delta, 0))), low[axis]+min(delta, 0)-1,
         coordinate+min(delta, 0)),
        (bridge, min(coordinate, coordinate+delta), max(coordinate, coordinate+delta)),
        (positive.translate(vector(max(delta, 0))), coordinate+max(delta, 0),
         high[axis]+max(delta, 0)+1),
    ]
    for expected, start, end in regions:
        actual = result.intersect(slab(start, end))
        try:
            _require_same_material(actual, expected, tolerance_mm3)
        except RuntimeError as exc:
            raise RuntimeError(f"Region [{start}, {end}] preservation failed: {exc}") from exc
    return result
