"""Synthetic captures of tag sheets with known ground-truth corners."""

from dataclasses import dataclass
from math import isfinite

import cv2
import numpy as np
from beartype import beartype

from arm_observer.apriltag.detector import Detection
from arm_observer.apriltag.families import TagFamily
from arm_observer.apriltag.layout import SheetPlan

DEFAULT_PX_PER_MM = 6.0
QUIET_CELLS = 1


@beartype
@dataclass(frozen=True, slots=True)
class SceneTruth:
    tag_id: int
    corners_px: tuple[tuple[float, float], ...]


@beartype
@dataclass(frozen=True, slots=True)
class SyntheticScene:
    image: np.ndarray
    truths: tuple[SceneTruth, ...]
    px_per_mm: float


@beartype
def render_tag_image(
    family: TagFamily, tag_id: int, cell_px: int, quiet_cells: int = QUIET_CELLS
) -> np.ndarray:
    if cell_px <= 0 or quiet_cells < 0:
        raise ValueError("cell_px must be positive and quiet_cells nonnegative")
    modules = family.tag_modules(tag_id)
    side = family.module_side + 2 * quiet_cells
    image = np.full((side * cell_px, side * cell_px), 255, dtype=np.uint8)
    for row, line in enumerate(modules):
        for column, black in enumerate(line):
            if black:
                top = (row + quiet_cells) * cell_px
                left = (column + quiet_cells) * cell_px
                image[top : top + cell_px, left : left + cell_px] = 0
    return image


@beartype
def _sheet_plane(plan: SheetPlan, family: TagFamily, px_per_mm: float) -> np.ndarray:
    page = plan.spec.page
    height = int(round(page.height_mm * px_per_mm))
    width = int(round(page.width_mm * px_per_mm))
    plane = np.full((height, width), 255, dtype=np.uint8)
    cell_mm = plan.spec.tag_size_mm / family.module_side
    for slot in plan.slots:
        for row, line in enumerate(family.tag_modules(slot.tag_id)):
            for column, black in enumerate(line):
                if black:
                    top = int(round((slot.y_mm + row * cell_mm) * px_per_mm))
                    left = int(round((slot.x_mm + column * cell_mm) * px_per_mm))
                    bottom = int(round((slot.y_mm + (row + 1) * cell_mm) * px_per_mm))
                    right = int(round((slot.x_mm + (column + 1) * cell_mm) * px_per_mm))
                    plane[top:bottom, left:right] = 0
    return plane


def _default_perspective(width: int, height: int) -> tuple[np.ndarray, np.ndarray]:
    source = np.array([[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float32)
    destination = np.array(
        [
            [0.07 * width, 0.05 * height],
            [0.94 * width, 0.09 * height],
            [0.97 * width, 0.95 * height],
            [0.03 * width, 0.91 * height],
        ],
        dtype=np.float32,
    )
    return source, destination


@beartype
def _warp(plane: np.ndarray, perspective: bool) -> tuple[np.ndarray, np.ndarray]:
    height, width = plane.shape
    if not perspective:
        return plane.copy(), np.eye(3, dtype=np.float64)
    source, destination = _default_perspective(width, height)
    matrix = cv2.getPerspectiveTransform(source, destination)
    warped = cv2.warpPerspective(
        plane, matrix, (width, height), flags=cv2.INTER_LINEAR, borderValue=255
    )
    return warped, matrix


@beartype
def _truth(plan: SheetPlan, px_per_mm: float, matrix: np.ndarray) -> tuple[SceneTruth, ...]:
    truths = []
    for slot in plan.slots:
        corners = np.array(
            [
                [slot.x_mm, slot.y_mm],
                [slot.x_mm + slot.size_mm, slot.y_mm],
                [slot.x_mm + slot.size_mm, slot.y_mm + slot.size_mm],
                [slot.x_mm, slot.y_mm + slot.size_mm],
            ],
            dtype=np.float64,
        ) * px_per_mm
        transformed = cv2.perspectiveTransform(
            corners.reshape(-1, 1, 2), matrix
        ).reshape(-1, 2)
        truths.append(
            SceneTruth(slot.tag_id, tuple((float(x), float(y)) for x, y in transformed))
        )
    return tuple(truths)


@beartype
def _degrade(image: np.ndarray, blur_sigma: float, noise_sigma: float, seed: int) -> np.ndarray:
    result = image.astype(np.float32)
    if blur_sigma > 0:
        result = cv2.GaussianBlur(result, (0, 0), blur_sigma)
    if noise_sigma > 0:
        result = result + np.random.default_rng(seed).normal(0.0, noise_sigma, result.shape)
    return np.clip(result, 0, 255).astype(np.uint8)


@beartype
def render_sheet_scene(
    plan: SheetPlan,
    family: TagFamily,
    *,
    px_per_mm: float = DEFAULT_PX_PER_MM,
    perspective: bool = True,
    blur_sigma: float = 0.0,
    noise_sigma: float = 0.0,
    seed: int = 0,
) -> SyntheticScene:
    if not isfinite(px_per_mm) or px_per_mm <= 0:
        raise ValueError("px_per_mm must be finite and positive")
    if not all(isfinite(value) and value >= 0 for value in (blur_sigma, noise_sigma)):
        raise ValueError("blur_sigma and noise_sigma must be finite and nonnegative")
    plane = _sheet_plane(plan, family, px_per_mm)
    warped, matrix = _warp(plane, perspective)
    image = _degrade(warped, blur_sigma, noise_sigma, seed)
    return SyntheticScene(image, _truth(plan, px_per_mm, matrix), px_per_mm)


@beartype
def corner_rms_px(detection: Detection, truth: tuple[tuple[float, float], ...]) -> float:
    detected = np.asarray(detection.corners, dtype=np.float64)
    expected = np.asarray(truth, dtype=np.float64)
    if detected.shape != expected.shape:
        raise ValueError("detection and truth must have the same corner shape")
    errors = [
        float(np.sqrt(np.mean(np.sum((detected - np.roll(expected, shift, axis=0)) ** 2, axis=1))))
        for shift in range(len(expected))
    ]
    return min(errors)
