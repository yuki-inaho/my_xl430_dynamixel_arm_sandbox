"""AprilTag sheet generation and detection."""

from arm_observer.apriltag.detector import Detection, DetectorSettings, build_detector, detect_tags
from arm_observer.apriltag.drawing import Drawing, build_sheet_drawing
from arm_observer.apriltag.families import TAG36H11, TagFamily
from arm_observer.apriltag.layout import (
    A4,
    PageSize,
    ReferenceBar,
    SheetPlan,
    SheetSpec,
    TagSlot,
    plan_sheet,
    plan_sheets,
)
from arm_observer.apriltag.pdf import sheet_filename, write_sheet_pdf
from arm_observer.apriltag.synthetic import (
    SceneTruth,
    SyntheticScene,
    corner_rms_px,
    render_sheet_scene,
    render_tag_image,
)

__all__ = [
    "A4",
    "Detection",
    "DetectorSettings",
    "Drawing",
    "PageSize",
    "ReferenceBar",
    "SceneTruth",
    "SheetPlan",
    "SheetSpec",
    "SyntheticScene",
    "TAG36H11",
    "TagFamily",
    "TagSlot",
    "build_detector",
    "build_sheet_drawing",
    "corner_rms_px",
    "detect_tags",
    "plan_sheet",
    "plan_sheets",
    "render_sheet_scene",
    "render_tag_image",
    "sheet_filename",
    "write_sheet_pdf",
]
