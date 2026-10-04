"""Millimetre geometry for A4 tag sheets."""

import pytest

from arm_observer.apriltag.layout import A4, SheetSpec, plan_sheets


def test_sheet_pair_ids():
    plans = plan_sheets(SheetSpec())
    assert len(plans) == 2
    assert tuple(slot.tag_id for slot in plans[0].slots) == tuple(range(12))
    assert tuple(slot.tag_id for slot in plans[1].slots) == tuple(range(12, 24))
    assert [plan.sheet_index for plan in plans] == [1, 2]
    assert all(plan.sheet_count == 2 for plan in plans)


def test_tag_geometry_exact_mm():
    plan = plan_sheets(SheetSpec())[0]
    assert len(plan.slots) == 12
    assert all(slot.size_mm == pytest.approx(40.0, abs=1e-9) for slot in plan.slots)
    columns = sorted({slot.column for slot in plan.slots})
    rows = sorted({slot.row for slot in plan.slots})
    assert columns == [0, 1, 2]
    assert rows == [0, 1, 2, 3]
    by_cell = {(slot.row, slot.column): slot for slot in plan.slots}
    assert by_cell[(0, 1)].x_mm - by_cell[(0, 0)].x_mm == pytest.approx(50.0, abs=1e-9)
    assert by_cell[(1, 0)].y_mm - by_cell[(0, 0)].y_mm == pytest.approx(50.0, abs=1e-9)


def test_no_overlap_and_within_margins():
    spec = SheetSpec()
    for plan in plan_sheets(spec):
        rectangles = [(slot.x_mm, slot.y_mm, slot.size_mm) for slot in plan.slots]
        for x, y, size in rectangles:
            assert x >= spec.margin_mm
            assert y >= spec.margin_mm
            assert x + size <= spec.page.width_mm - spec.margin_mm
            assert y + size <= spec.page.height_mm - spec.margin_mm
        for first, second in zip(rectangles, rectangles[1:]):
            separated = (
                first[0] + first[2] <= second[0] + 1e-9
                or second[0] + second[2] <= first[0] + 1e-9
                or first[1] + first[2] <= second[1] + 1e-9
                or second[1] + second[2] <= first[1] + 1e-9
            )
            assert separated


def test_reference_bar_length_and_position():
    plan = plan_sheets(SheetSpec())[0]
    bar = plan.reference_bar
    assert bar.length_mm == pytest.approx(100.0, abs=1e-9)
    assert bar.x_mm >= 0
    assert bar.x_mm + bar.length_mm <= A4.width_mm
    grid_bottom = max(slot.y_mm + slot.size_mm for slot in plan.slots)
    assert bar.y_mm > grid_bottom


def test_oversize_rejected():
    with pytest.raises(ValueError):
        plan_sheets(SheetSpec(tag_size_mm=80.0))


def test_invalid_parameters_rejected():
    with pytest.raises(ValueError):
        plan_sheets(SheetSpec(columns=0))
    with pytest.raises(ValueError):
        plan_sheets(SheetSpec(rows=-1))
    with pytest.raises(ValueError):
        plan_sheets(SheetSpec(gap_mm=-1.0))
