"""Actual-size A4 PDF output for tag sheet plans."""

from pathlib import Path

from beartype import beartype
from reportlab.lib.units import mm as POINTS_PER_MM
from reportlab.pdfgen.canvas import Canvas

from arm_observer.apriltag.drawing import Drawing, LineOp, RectOp, TextOp, build_sheet_drawing
from arm_observer.apriltag.families import TagFamily
from arm_observer.apriltag.layout import SheetPlan

BLACK = (0.0, 0.0, 0.0)
WHITE = (1.0, 1.0, 1.0)
TEXT_FONT = "Helvetica"


@beartype
def sheet_filename(plan: SheetPlan, family: TagFamily) -> str:
    short_name = family.name.removeprefix("tag")
    first, last = min(plan.tag_ids), max(plan.tag_ids)
    return (
        f"apriltag_{short_name}_a4_sheet_{plan.sheet_index}_ids_{first:03d}-{last:03d}.pdf"
    )


@beartype
def _draw_rect(canvas: Canvas, op: RectOp) -> None:
    canvas.setFillColorRGB(*(BLACK if op.fill == "black" else WHITE))
    canvas.rect(
        op.x_mm * POINTS_PER_MM,
        op.y_mm * POINTS_PER_MM,
        op.width_mm * POINTS_PER_MM,
        op.height_mm * POINTS_PER_MM,
        stroke=0,
        fill=1,
    )


@beartype
def _draw_line(canvas: Canvas, op: LineOp) -> None:
    canvas.setStrokeColorRGB(*BLACK)
    canvas.setLineWidth(op.width_mm * POINTS_PER_MM)
    canvas.line(
        op.x1_mm * POINTS_PER_MM,
        op.y1_mm * POINTS_PER_MM,
        op.x2_mm * POINTS_PER_MM,
        op.y2_mm * POINTS_PER_MM,
    )


@beartype
def _draw_text(canvas: Canvas, op: TextOp) -> None:
    canvas.setFillColorRGB(*BLACK)
    canvas.setFont(TEXT_FONT, op.size_pt)
    position = (op.x_mm * POINTS_PER_MM, op.y_mm * POINTS_PER_MM)
    if op.anchor == "center":
        canvas.drawCentredString(*position, op.text)
    elif op.anchor == "right":
        canvas.drawRightString(*position, op.text)
    else:
        canvas.drawString(*position, op.text)


@beartype
def _write_drawing(canvas: Canvas, drawing: Drawing) -> None:
    for op in drawing.ops:
        if isinstance(op, RectOp):
            _draw_rect(canvas, op)
        elif isinstance(op, LineOp):
            _draw_line(canvas, op)
        else:
            _draw_text(canvas, op)


@beartype
def write_sheet_pdf(plan: SheetPlan, family: TagFamily, path: Path) -> Path:
    drawing = build_sheet_drawing(plan, family)
    path.parent.mkdir(parents=True, exist_ok=True)
    page = plan.spec.page
    canvas = Canvas(
        str(path),
        pagesize=(page.width_mm * POINTS_PER_MM, page.height_mm * POINTS_PER_MM),
        pageCompression=1,
    )
    _write_drawing(canvas, drawing)
    canvas.showPage()
    canvas.save()
    return path
