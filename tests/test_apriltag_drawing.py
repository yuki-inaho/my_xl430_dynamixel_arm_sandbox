"""Vector drawing content for a tag sheet plan."""

import pytest

from arm_observer.apriltag.drawing import RectOp, build_sheet_drawing
from arm_observer.apriltag.families import TAG36H11
from arm_observer.apriltag.layout import SheetSpec, plan_sheets


def _drawing():
    plan = plan_sheets(SheetSpec())[0]
    return plan, build_sheet_drawing(plan, TAG36H11)


def test_black_rects_match_modules():
    plan, drawing = _drawing()
    cell = plan.spec.tag_size_mm / TAG36H11.module_side
    page_height = plan.spec.page.height_mm
    module_rects = [
        op
        for op in drawing.rects
        if isinstance(op, RectOp)
        and op.fill == "black"
        and op.width_mm == pytest.approx(cell, abs=1e-9)
        and op.height_mm == pytest.approx(cell, abs=1e-9)
    ]
    inverse: dict[int, set[tuple[int, int]]] = {slot.tag_id: set() for slot in plan.slots}
    for op in module_rects:
        top = page_height - op.y_mm - op.height_mm
        for slot in plan.slots:
            inside = (
                slot.x_mm - 1e-9 <= op.x_mm
                and op.x_mm + op.width_mm <= slot.x_mm + slot.size_mm + 1e-9
                and slot.y_mm - 1e-9 <= top
                and top + op.height_mm <= slot.y_mm + slot.size_mm + 1e-9
            )
            if inside:
                row = round((top - slot.y_mm) / cell)
                column = round((op.x_mm - slot.x_mm) / cell)
                inverse[slot.tag_id].add((row, column))
                break
        else:
            pytest.fail(f"module rect outside every tag slot: {op}")
    for slot in plan.slots:
        modules = TAG36H11.tag_modules(slot.tag_id)
        expected = {
            (row, column)
            for row, line in enumerate(modules)
            for column, black in enumerate(line)
            if black
        }
        assert inverse[slot.tag_id] == expected


def test_reference_bar_rect():
    plan, drawing = _drawing()
    bars = [
        op
        for op in drawing.rects
        if isinstance(op, RectOp)
        and op.width_mm == pytest.approx(100.0, abs=1e-9)
        and op.height_mm == pytest.approx(1.0, abs=1e-9)
    ]
    assert len(bars) == 1
    assert bars[0].x_mm == pytest.approx(plan.reference_bar.x_mm, abs=1e-9)


def test_header_and_footer_texts():
    _, drawing = _drawing()
    texts = [op.text for op in drawing.texts]
    assert any("PRINT AT 100% (ACTUAL SIZE)" in text for text in texts)
    assert any("sheet 1/2" in text for text in texts)
    assert any("IDs 0-11" in text for text in texts)
    assert any("100 mm reference bar" in text for text in texts)


def test_drawing_is_deterministic():
    plan = plan_sheets(SheetSpec())[0]
    assert build_sheet_drawing(plan, TAG36H11) == build_sheet_drawing(plan, TAG36H11)
