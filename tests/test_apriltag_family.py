"""36h11 module patterns must match the OpenCV dictionary bit-for-bit."""

import cv2.aruco as aruco
import pytest

from arm_observer.apriltag.families import TAG36H11


def _opencv_modules(tag_id: int) -> tuple[tuple[bool, ...], ...]:
    dictionary = aruco.getPredefinedDictionary(aruco.DICT_APRILTAG_36h11)
    marker = aruco.generateImageMarker(dictionary, tag_id, 8)
    return tuple(tuple(bool(value) for value in row == 0) for row in marker)


@pytest.mark.parametrize("tag_id", range(24))
def test_tag_modules_match_opencv(tag_id):
    assert TAG36H11.tag_modules(tag_id) == _opencv_modules(tag_id)


def test_shape_and_outer_border():
    for tag_id in range(24):
        modules = TAG36H11.tag_modules(tag_id)
        assert len(modules) == 8
        assert all(len(row) == 8 for row in modules)
        assert all(modules[0]) and all(modules[7])
        assert all(row[0] for row in modules) and all(row[7] for row in modules)


def test_tag_id_out_of_range_rejected():
    with pytest.raises(ValueError):
        TAG36H11.tag_modules(24)
    with pytest.raises(ValueError):
        TAG36H11.tag_modules(-1)
