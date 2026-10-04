"""Actual-size A4 PDF output for tag sheet plans."""

import re

import pytest
from reportlab.lib.pagesizes import A4 as A4_POINTS

from arm_observer.apriltag.families import TAG36H11
from arm_observer.apriltag.layout import SheetSpec, plan_sheets
from arm_observer.apriltag.pdf import sheet_filename, write_sheet_pdf


def test_pdf_header_and_mediabox(tmp_path):
    plan = plan_sheets(SheetSpec())[0]
    path = write_sheet_pdf(plan, TAG36H11, tmp_path / "sheet.pdf")
    data = path.read_bytes()
    assert data.startswith(b"%PDF-")
    match = re.search(
        rb"MediaBox\s*\[\s*0(?:\.0+)?\s+0(?:\.0+)?\s+(\d+\.\d+)\s+(\d+\.\d+)\s*\]", data
    )
    assert match is not None, "A4 MediaBox not found in PDF"
    width_points, height_points = (float(value) for value in match.groups())
    assert width_points == pytest.approx(A4_POINTS[0], abs=1.0)
    assert height_points == pytest.approx(A4_POINTS[1], abs=1.0)
    assert data.count(b"MediaBox") == 1


def test_sheet_filename():
    first, second = plan_sheets(SheetSpec())
    assert sheet_filename(first, TAG36H11) == "apriltag_36h11_a4_sheet_1_ids_000-011.pdf"
    assert sheet_filename(second, TAG36H11) == "apriltag_36h11_a4_sheet_2_ids_012-023.pdf"
