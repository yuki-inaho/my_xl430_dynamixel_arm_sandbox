"""High-accuracy OpenCV detection settings and marker detection."""

import cv2
import cv2.aruco as aruco
import numpy as np

from arm_observer.apriltag.detector import build_detector, detect_tags


def test_corner_refine_enabled():
    params = build_detector().getDetectorParameters()
    assert params.cornerRefinementMethod == aruco.CORNER_REFINE_APRILTAG
    assert params.cornerRefinementWinSize == 5
    assert params.cornerRefinementMaxIterations == 50
    assert params.cornerRefinementMinAccuracy == 0.01


def test_accuracy_first_settings():
    params = build_detector().getDetectorParameters()
    assert params.aprilTagQuadDecimate == 1.0
    assert params.aprilTagQuadSigma == 0.0
    assert params.polygonalApproxAccuracyRate == 0.01
    assert params.adaptiveThreshWinSizeMin == 3
    assert params.useAruco3Detection is False


def test_detect_single_opencv_marker():
    dictionary = aruco.getPredefinedDictionary(aruco.DICT_APRILTAG_36h11)
    marker = aruco.generateImageMarker(dictionary, 7, 8)
    canvas = np.full((400, 400), 255, dtype=np.uint8)
    canvas[72:328, 72:328] = cv2.resize(marker, (256, 256), interpolation=cv2.INTER_NEAREST)
    detections = detect_tags(canvas)
    assert [detection.tag_id for detection in detections] == [7]
    assert len(detections[0].corners) == 4
    assert detections[0].corners[0][0] < detections[0].corners[1][0]


def test_detect_blank_returns_empty():
    blank = np.full((200, 200), 255, dtype=np.uint8)
    assert detect_tags(blank) == ()
