"""A4 millimetre geometry for printable tag sheets."""

from dataclasses import dataclass
from math import isfinite

from beartype import beartype

REFERENCE_BAR_HEIGHT_MM = 1.0
REFERENCE_TICK_SPACING_MM = 10.0


@beartype
@dataclass(frozen=True, slots=True)
class PageSize:
    width_mm: float
    height_mm: float


A4 = PageSize(210.0, 297.0)


@beartype
@dataclass(frozen=True, slots=True)
class SheetSpec:
    page: PageSize = A4
    columns: int = 3
    rows: int = 4
    tag_size_mm: float = 40.0
    gap_mm: float = 10.0
    margin_mm: float = 12.0
    header_mm: float = 14.0
    ruler_height_mm: float = 18.0
    ruler_length_mm: float = 100.0
    first_tag_id: int = 0


@beartype
@dataclass(frozen=True, slots=True)
class TagSlot:
    tag_id: int
    row: int
    column: int
    x_mm: float
    y_mm: float
    size_mm: float


@beartype
@dataclass(frozen=True, slots=True)
class ReferenceBar:
    x_mm: float
    y_mm: float
    length_mm: float
    height_mm: float
    tick_spacing_mm: float


@beartype
@dataclass(frozen=True, slots=True)
class SheetPlan:
    spec: SheetSpec
    sheet_index: int
    sheet_count: int
    slots: tuple[TagSlot, ...]
    reference_bar: ReferenceBar

    @property
    def tag_ids(self) -> tuple[int, ...]:
        return tuple(slot.tag_id for slot in self.slots)


def _grid_size(spec: SheetSpec) -> tuple[float, float]:
    width = spec.columns * spec.tag_size_mm + (spec.columns - 1) * spec.gap_mm
    height = spec.rows * spec.tag_size_mm + (spec.rows - 1) * spec.gap_mm
    return width, height


@beartype
def _validate_dimensions(spec: SheetSpec) -> None:
    dimensions = (
        spec.page.width_mm, spec.page.height_mm, spec.tag_size_mm, spec.gap_mm,
        spec.margin_mm, spec.header_mm, spec.ruler_height_mm, spec.ruler_length_mm,
    )
    if not all(isfinite(value) for value in dimensions):
        raise ValueError("page and sheet dimensions must be finite")
    if min(spec.page.width_mm, spec.page.height_mm) <= 0:
        raise ValueError("page dimensions must be positive")
    if spec.columns < 1 or spec.rows < 1:
        raise ValueError("columns and rows must be positive")
    if spec.tag_size_mm <= 0:
        raise ValueError("tag size must be positive")
    if min(spec.gap_mm, spec.margin_mm, spec.header_mm, spec.ruler_height_mm) < 0:
        raise ValueError("gap, margins and bands must be nonnegative")
    if spec.ruler_length_mm <= 0:
        raise ValueError("reference bar length must be positive")


@beartype
def _validate_spec(spec: SheetSpec) -> None:
    _validate_dimensions(spec)
    grid_width, grid_height = _grid_size(spec)
    if grid_width + 2 * spec.margin_mm > spec.page.width_mm:
        raise ValueError("tag grid does not fit the page width")
    if spec.ruler_length_mm + 2 * spec.margin_mm > spec.page.width_mm:
        raise ValueError("reference bar does not fit the page width")
    block_height = spec.header_mm + grid_height + spec.ruler_height_mm
    if block_height + 2 * spec.margin_mm > spec.page.height_mm:
        raise ValueError("tag grid with header and reference bar does not fit the page height")


@beartype
def plan_sheet(spec: SheetSpec, sheet_index: int, sheet_count: int, first_tag_id: int) -> SheetPlan:
    _validate_spec(spec)
    if not 1 <= sheet_index <= sheet_count:
        raise ValueError("sheet index must be in 1..sheet_count")
    grid_width, grid_height = _grid_size(spec)
    block_height = spec.header_mm + grid_height + spec.ruler_height_mm
    top = (spec.page.height_mm - block_height) / 2
    left = (spec.page.width_mm - grid_width) / 2
    grid_top = top + spec.header_mm
    step = spec.tag_size_mm + spec.gap_mm
    next_id = first_tag_id + (sheet_index - 1) * spec.columns * spec.rows
    slots = []
    for row in range(spec.rows):
        for column in range(spec.columns):
            slots.append(
                TagSlot(next_id, row, column, left + column * step, grid_top + row * step,
                        spec.tag_size_mm)
            )
            next_id += 1
    bar_top = grid_top + grid_height + (spec.ruler_height_mm - REFERENCE_BAR_HEIGHT_MM) / 2
    bar = ReferenceBar(
        x_mm=(spec.page.width_mm - spec.ruler_length_mm) / 2,
        y_mm=bar_top,
        length_mm=spec.ruler_length_mm,
        height_mm=REFERENCE_BAR_HEIGHT_MM,
        tick_spacing_mm=REFERENCE_TICK_SPACING_MM,
    )
    return SheetPlan(spec, sheet_index, sheet_count, tuple(slots), bar)


@beartype
def plan_sheets(
    spec: SheetSpec, sheet_count: int = 2, first_tag_id: int | None = None
) -> tuple[SheetPlan, ...]:
    if sheet_count < 1:
        raise ValueError("sheet count must be positive")
    start = spec.first_tag_id if first_tag_id is None else first_tag_id
    if start < 0:
        raise ValueError("first tag id must be nonnegative")
    return tuple(plan_sheet(spec, index, sheet_count, start) for index in range(1, sheet_count + 1))
