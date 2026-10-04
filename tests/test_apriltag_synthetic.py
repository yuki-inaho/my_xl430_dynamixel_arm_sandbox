"""Synthetic captures of tag sheets with known ground-truth corners."""

import numpy as np
import pytest

from arm_observer.apriltag.detector import detect_tags
from arm_observer.apriltag.families import TAG36H11
from arm_observer.apriltag.layout import SheetSpec, plan_sheets
from arm_observer.apriltag.synthetic import corner_rms_px, render_sheet_scene, render_tag_image


def test_all_ids_and_corner_rms_within_limit():
    plan = plan_sheets(SheetSpec())[0]
    scene = render_sheet_scene(plan, TAG36H11, blur_sigma=0.8, noise_sigma=2.0, seed=3)
    truth = {item.tag_id: item.corners_px for item in scene.truths}
    detections = detect_tags(scene.image)
    assert {detection.tag_id for detection in detections} == set(plan.tag_ids)
    errors = [corner_rms_px(detection, truth[detection.tag_id]) for detection in detections]
    assert max(errors) <= 0.5


def test_fractional_pixel_cells_have_continuous_black_border():
    plan = plan_sheets(SheetSpec())[0]
    scale = 5.3
    scene = render_sheet_scene(plan, TAG36H11, px_per_mm=scale, perspective=False)
    slot = plan.slots[0]
    left = round(slot.x_mm * scale)
    right = round((slot.x_mm + slot.size_mm) * scale)
    top = round(slot.y_mm * scale)
    # The black outer border must have no one-pixel white seams between cells.
    assert np.all(scene.image[top, left:right] == 0)
    assert {d.tag_id for d in detect_tags(scene.image)} == set(plan.tag_ids)


@pytest.mark.parametrize("rotations", [0, 1, 2, 3])
def test_rotation_invariance(rotations):
    image = render_tag_image(TAG36H11, 5, cell_px=12)
    rotated = np.pad(np.rot90(image, rotations), 40, constant_values=255)
    detections = detect_tags(np.ascontiguousarray(rotated))
    assert [detection.tag_id for detection in detections] == [5]


def test_blur_and_noise_robustness():
    plan = plan_sheets(SheetSpec())[0]
    scene = render_sheet_scene(
        plan, TAG36H11, perspective=True, blur_sigma=1.0, noise_sigma=2.0, seed=11
    )
    detections = detect_tags(scene.image)
    assert {detection.tag_id for detection in detections} == set(plan.tag_ids)
    truth = {item.tag_id: item.corners_px for item in scene.truths}
    errors = [corner_rms_px(detection, truth[detection.tag_id]) for detection in detections]
    assert max(errors) <= 0.75
