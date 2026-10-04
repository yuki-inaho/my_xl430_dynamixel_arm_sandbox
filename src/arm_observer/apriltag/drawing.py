"""Vector drawing primitives for a tag sheet in millimetre coordinates.

Layout math is done top-down (matching page reading order); PDF output uses a
bottom-left origin, so every y coordinate is flipped exactly once here.
"""

from dataclasses import dataclass
from typing import Literal

from beartype import beartype

from arm_observer.apriltag.families import TagFamily
from arm_observer.apriltag.layout import SheetPlan, TagSlot

Fill = Literal["black", "white"]
Anchor = Literal["left", "center", "right"]

LABEL_FONT_SIZE_PT = 6.5
HEADER_FONT_SIZE_PT = 11.0
SUBHEADER_FONT_SIZE_PT = 8.0
FOOTER_FONT_SIZE_PT = 7.0
LABEL_GAP_MM = 3.0
HEADER_BASELINES_MM = (5.5, 11.0)
TICK_HEIGHT_MM = 2.5
TICK_LINE_WIDTH_MM = 0.3


@beartype
@dataclass(frozen=True, slots=True)
class RectOp:
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    fill: Fill


@beartype
@dataclass(frozen=True, slots=True)
class LineOp:
    x1_mm: float
    y1_mm: float
    x2_mm: float
    y2_mm: float
    width_mm: float


@beartype
@dataclass(frozen=True, slots=True)
class TextOp:
    x_mm: float
    y_mm: float
    text: str
    size_pt: float
    anchor: Anchor


@beartype
@dataclass(frozen=True, slots=True)
class Drawing:
    page_width_mm: float
    page_height_mm: float
    ops: tuple[RectOp | LineOp | TextOp, ...]

    @property
    def rects(self) -> tuple[RectOp, ...]:
        return tuple(op for op in self.ops if isinstance(op, RectOp))

    @property
    def lines(self) -> tuple[LineOp, ...]:
        return tuple(op for op in self.ops if isinstance(op, LineOp))

    @property
    def texts(self) -> tuple[TextOp, ...]:
        return tuple(op for op in self.ops if isinstance(op, TextOp))


def _flip(page_height_mm: float, y_top_mm: float, height_mm: float) -> float:
    return page_height_mm - y_top_mm - height_mm


@beartype
def _header_ops(plan: SheetPlan, family: TagFamily) -> list[TextOp]:
    spec = plan.spec
    grid_top = min(slot.y_mm for slot in plan.slots)
    top = grid_top - spec.header_mm
    first, last = min(plan.tag_ids), max(plan.tag_ids)
    center_x = spec.page.width_mm / 2
    title = f"AprilTag {family.name} - A4 tag sheet {plan.sheet_index}/{plan.sheet_count}"
    subtitle = (
        f"tag {spec.tag_size_mm:g} mm | gap {spec.gap_mm:g} mm | IDs {first}-{last} | "
        "PRINT AT 100% (ACTUAL SIZE)"
    )
    return [
        TextOp(center_x, _flip(spec.page.height_mm, top + HEADER_BASELINES_MM[0], 0.0),
               title, HEADER_FONT_SIZE_PT, "center"),
        TextOp(center_x, _flip(spec.page.height_mm, top + HEADER_BASELINES_MM[1], 0.0),
               subtitle, SUBHEADER_FONT_SIZE_PT, "center"),
    ]


@beartype
def _tag_ops(slot: TagSlot, family: TagFamily, page_height_mm: float) -> list[RectOp]:
    cell = slot.size_mm / family.module_side
    ops = []
    for row, line in enumerate(family.tag_modules(slot.tag_id)):
        for column, black in enumerate(line):
            if black:
                ops.append(
                    RectOp(
                        slot.x_mm + column * cell,
                        _flip(page_height_mm, slot.y_mm + row * cell, cell),
                        cell,
                        cell,
                        "black",
                    )
                )
    return ops


@beartype
def _label_ops(slot: TagSlot, page_height_mm: float) -> list[TextOp]:
    baseline = slot.y_mm + slot.size_mm + LABEL_GAP_MM
    return [
        TextOp(
            slot.x_mm + slot.size_mm / 2,
            _flip(page_height_mm, baseline, 0.0),
            f"ID {slot.tag_id}",
            LABEL_FONT_SIZE_PT,
            "center",
        )
    ]


@beartype
def _reference_ops(plan: SheetPlan, page_height_mm: float) -> list[RectOp | LineOp | TextOp]:
    bar = plan.reference_bar
    page_width = plan.spec.page.width_mm
    ops: list[RectOp | LineOp | TextOp] = [
        RectOp(bar.x_mm, _flip(page_height_mm, bar.y_mm, bar.height_mm), bar.length_mm,
               bar.height_mm, "black")
    ]
    tick_count = int(round(bar.length_mm / bar.tick_spacing_mm))
    tick_y1 = _flip(page_height_mm, bar.y_mm - TICK_HEIGHT_MM, 0.0)
    tick_y2 = _flip(page_height_mm, bar.y_mm, 0.0)
    for index in range(tick_count + 1):
        x = bar.x_mm + index * bar.tick_spacing_mm
        ops.append(LineOp(x, tick_y1, x, tick_y2, TICK_LINE_WIDTH_MM))
    label_y = _flip(page_height_mm, bar.y_mm - TICK_HEIGHT_MM - 1.0, 0.0)
    ops.append(TextOp(bar.x_mm, label_y, "0", FOOTER_FONT_SIZE_PT, "left"))
    ops.append(
        TextOp(bar.x_mm + bar.length_mm, label_y, f"{bar.length_mm:g} mm", FOOTER_FONT_SIZE_PT,
               "right")
    )
    ops.append(
        TextOp(
            page_width / 2,
            _flip(page_height_mm, bar.y_mm + bar.height_mm + 4.0, 0.0),
            "Measure the 100 mm reference bar; if it is not exactly 100 mm, disable printer "
            "scaling.",
            FOOTER_FONT_SIZE_PT,
            "center",
        )
    )
    return ops


@beartype
def build_sheet_drawing(plan: SheetPlan, family: TagFamily) -> Drawing:
    page = plan.spec.page
    ops: list[RectOp | LineOp | TextOp] = list(_header_ops(plan, family))
    for slot in plan.slots:
        ops.extend(_tag_ops(slot, family, page.height_mm))
        ops.extend(_label_ops(slot, page.height_mm))
    ops.extend(_reference_ops(plan, page.height_mm))
    return Drawing(page.width_mm, page.height_mm, tuple(ops))
