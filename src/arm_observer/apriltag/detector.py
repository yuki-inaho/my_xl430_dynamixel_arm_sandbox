"""High-accuracy OpenCV detection of AprilTag 36h11 markers.

Accuracy-first defaults: no quad decimation, no pre-blur, tight polygonal
approximation and AprilTag corner refinement, at the cost of speed.
"""

from dataclasses import dataclass

import cv2.aruco as aruco
import numpy as np
from beartype import beartype


@beartype
@dataclass(frozen=True, slots=True)
class DetectorSettings:
    adaptive_thresh_win_min: int = 3
    adaptive_thresh_win_max: int = 53
    adaptive_thresh_win_step: int = 4
    adaptive_thresh_constant: float = 7.0
    min_marker_perimeter_rate: float = 0.01
    max_marker_perimeter_rate: float = 4.0
    polygonal_approx_accuracy_rate: float = 0.01
    min_corner_distance_rate: float = 0.05
    min_distance_to_border: int = 3
    april_tag_quad_decimate: float = 1.0
    april_tag_quad_sigma: float = 0.0
    corner_refinement_win_size: int = 5
    corner_refinement_max_iterations: int = 50
    corner_refinement_min_accuracy: float = 0.01


@beartype
@dataclass(frozen=True, slots=True)
class Detection:
    tag_id: int
    corners: tuple[tuple[float, float], ...]


@beartype
def build_detector(settings: DetectorSettings = DetectorSettings()) -> aruco.ArucoDetector:
    dictionary = aruco.getPredefinedDictionary(aruco.DICT_APRILTAG_36h11)
    params = aruco.DetectorParameters()
    params.adaptiveThreshWinSizeMin = settings.adaptive_thresh_win_min
    params.adaptiveThreshWinSizeMax = settings.adaptive_thresh_win_max
    params.adaptiveThreshWinSizeStep = settings.adaptive_thresh_win_step
    params.adaptiveThreshConstant = settings.adaptive_thresh_constant
    params.minMarkerPerimeterRate = settings.min_marker_perimeter_rate
    params.maxMarkerPerimeterRate = settings.max_marker_perimeter_rate
    params.polygonalApproxAccuracyRate = settings.polygonal_approx_accuracy_rate
    params.minCornerDistanceRate = settings.min_corner_distance_rate
    params.minDistanceToBorder = settings.min_distance_to_border
    params.aprilTagQuadDecimate = settings.april_tag_quad_decimate
    params.aprilTagQuadSigma = settings.april_tag_quad_sigma
    params.cornerRefinementMethod = aruco.CORNER_REFINE_APRILTAG
    params.cornerRefinementWinSize = settings.corner_refinement_win_size
    params.cornerRefinementMaxIterations = settings.corner_refinement_max_iterations
    params.cornerRefinementMinAccuracy = settings.corner_refinement_min_accuracy
    params.useAruco3Detection = False
    return aruco.ArucoDetector(dictionary, params)


@beartype
def detect_tags(
    image: np.ndarray, settings: DetectorSettings = DetectorSettings()
) -> tuple[Detection, ...]:
    corners, ids, _ = build_detector(settings).detectMarkers(image)
    if ids is None:
        return ()
    detections = []
    for tag_id, quad in zip(ids.flatten(), corners):
        points = tuple((float(point[0]), float(point[1])) for point in quad[0])
        detections.append(Detection(int(tag_id), points))
    return tuple(detections)
