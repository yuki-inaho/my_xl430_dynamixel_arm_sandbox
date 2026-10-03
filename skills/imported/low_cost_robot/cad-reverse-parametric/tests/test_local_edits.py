"""B-rep extension must preserve chunks, never stretch a transverse bore."""
import cadquery as cq
import pytest
from pathlib import Path

from cadre.local_edits import extend_prismatic_section


def volume(shape):
    return sum(s.Volume() for s in shape.Solids())


def difference(a, b):
    return volume(a.cut(b)) + volume(b.cut(a))


def clip(shape, axis, low, high):
    origin, size = [-100.] * 3, [200.] * 3
    origin[axis], size[axis] = low, high-low
    return shape.intersect(cq.Solid.makeBox(*size, cq.Vector(*origin)))


@pytest.mark.parametrize("axis", [0, 1, 2])
@pytest.mark.parametrize("delta", [-4.25, 4.25])
def test_extension_preserves_both_chunks_all_axes_and_directions(axis, delta):
    source = cq.Workplane("XY").box(20, 16, 12).val()
    changed = extend_prismatic_section(source, axis=axis, coordinate=0., delta=delta)
    direction = [0., 0., 0.]
    direction[axis] = delta
    if delta < 0:
        fixed = clip(source, axis, 0, 100)
        fixed_actual = clip(changed, axis, 0, 100)
        moved = clip(source, axis, -100, 0).translate(direction)
        moved_actual = clip(changed, axis, -100, delta)
    else:
        fixed = clip(source, axis, -100, 0)
        fixed_actual = clip(changed, axis, -100, 0)
        moved = clip(source, axis, 0, 100).translate(direction)
        moved_actual = clip(changed, axis, delta, 100)
    assert changed.isValid() and len(changed.Solids()) == 1
    assert difference(fixed, fixed_actual) < 1e-7
    assert difference(moved, moved_actual) < 1e-7
    assert volume(changed)-volume(source) == pytest.approx(
        [16*12, 20*12, 20*16][axis] * abs(delta), abs=1e-7)


def test_zero_extension_is_identity():
    source = cq.Workplane("XY").box(10, 8, 6).val()
    assert difference(source, extend_prismatic_section(source, axis=0, coordinate=0, delta=0)) < 1e-7


def test_empty_common_cannot_make_identity_preflight_pass(monkeypatch):
    source = cq.Workplane("XY").box(10, 8, 6).val()
    monkeypatch.setattr(cq.Shape, "intersect", lambda *a, **kw: cq.Compound.makeCompound([]))
    with pytest.raises(RuntimeError, match="Boolean identity preflight failed"):
        extend_prismatic_section(source, axis=0, coordinate=0, delta=0)


def test_transverse_bore_cannot_be_stretched_into_a_slot():
    source = cq.Workplane("XY").box(20, 16, 12).val()
    source = source.cut(cq.Solid.makeCylinder(2, 20, cq.Vector(0, 0, -10)))
    with pytest.raises(ValueError, match="prismatic"):
        extend_prismatic_section(source, axis=0, coordinate=0, delta=4)


def test_curved_outline_at_section_is_not_approximated():
    source = cq.Solid.makeSphere(10, angleDegrees1=-90)
    with pytest.raises(ValueError, match="prismatic"):
        extend_prismatic_section(source, axis=0, coordinate=0, delta=4)


def test_constant_axial_bore_keeps_its_radius():
    source = cq.Solid.makeCylinder(5, 10).cut(cq.Solid.makeCylinder(2, 10))
    changed = extend_prismatic_section(source, axis=2, coordinate=5, delta=3)
    expected = cq.Solid.makeCylinder(5, 13).cut(cq.Solid.makeCylinder(2, 13))
    assert difference(changed, expected) < 1e-7


def test_equal_guard_volume_does_not_hide_a_slanted_profile():
    wire = cq.Workplane("YZ").rect(8, 6).val()
    source = cq.Solid.extrudeLinear(wire, [], cq.Vector(20, 4, 0)).translate((-10, -2, 0))
    with pytest.raises(ValueError, match="prismatic"):
        extend_prismatic_section(source, axis=0, coordinate=0, delta=4)


@pytest.mark.parametrize("parameters", [
    {"axis": -1}, {"axis": 3}, {"axis": True},
    {"coordinate": 10.}, {"coordinate": -10.}, {"coordinate": 100.},
    {"coordinate": float("nan")}, {"delta": float("inf")},
    {"guard_half_width": 0.}, {"guard_half_width": -1.},
    {"guard_half_width": float("nan")}, {"tolerance_mm3": 0.},
])
def test_invalid_parameters_cannot_pass(parameters):
    args = {"axis":0, "coordinate":0., "delta":1.}
    args.update(parameters)
    with pytest.raises(ValueError):
        extend_prismatic_section(cq.Workplane("XY").box(20, 16, 12).val(), **args)


def test_non_solid_and_disconnected_input_are_rejected():
    box = cq.Workplane("XY").box(10, 8, 6).val()
    for source in [box.Faces()[0], cq.Compound.makeCompound([box, box.translate((20, 0, 0))])]:
        with pytest.raises(ValueError, match="solid"):
            extend_prismatic_section(source, axis=0, coordinate=0, delta=1)


def test_kernel_exception_propagates(monkeypatch):
    source = cq.Workplane("XY").box(10, 8, 6).val()
    def broken(*args, **kwargs):
        raise RuntimeError("kernel failed")
    monkeypatch.setattr(cq.Shape, "intersect", broken)
    with pytest.raises(RuntimeError, match="kernel failed"):
        extend_prismatic_section(source, axis=0, coordinate=0, delta=1)


def test_imported_source_with_failed_identity_preflight_is_not_modified(monkeypatch):
    path = Path(__file__).resolve().parents[3] / "hardware/follower/step/gripper_static_part.step"
    source = cq.importers.importStep(str(path)).val()
    assert source.isValid()
    def forbidden(*args, **kwargs):
        pytest.fail("must reject unreliable source before constructing a bridge")
    monkeypatch.setattr(cq.Solid, "extrudeLinear", forbidden)
    with pytest.raises(RuntimeError, match="Boolean identity preflight failed"):
        extend_prismatic_section(source, axis=1, coordinate=-11.35, delta=-4.25)
