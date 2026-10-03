"""Detect rendered AprilTags and preserve measured 2D-to-known-3D correspondences."""

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True)
class DetectionRunResult:
    output_directory: Path
    json_path: Path
    overlay_paths: tuple[Path, ...]


def _dictionary(dictionary_name: str):
    supported = {
        "DICT_APRILTAG_36h11": cv2.aruco.DICT_APRILTAG_36h11,
        "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
    }
    if dictionary_name not in supported:
        raise ValueError(f"unsupported dictionary: {dictionary_name}")
    return cv2.aruco.getPredefinedDictionary(supported[dictionary_name])


def validate_detection(
    ids: list[int],
    corners: list[NDArray[np.float64]],
    image_shape: tuple[int, int],
    expected_ids: set[int],
    *,
    minimum_tags: int = 2,
    boundary_margin_px: float = 2.0,
) -> tuple[bool, str]:
    if not ids:
        return False, "zero_detections"
    if len(ids) != len(set(ids)):
        return False, "duplicate_ids"
    if not set(ids).issubset(expected_ids):
        return False, "unexpected_ids"
    if len(ids) < minimum_tags or 4 * len(ids) < 8:
        return False, "insufficient_correspondences"
    height, width = image_shape
    for tag_corners in corners:
        points = np.asarray(tag_corners, dtype=np.float64)
        if (
            np.any(points[:, 0] <= boundary_margin_px)
            or np.any(points[:, 0] >= width - 1 - boundary_margin_px)
            or np.any(points[:, 1] <= boundary_margin_px)
            or np.any(points[:, 1] >= height - 1 - boundary_margin_px)
        ):
            return False, "corner_on_image_boundary"
    return True, "accepted"


def detect_frame(
    image_gray: ArrayLike,
    tag_corners_world_m: dict[str, list[list[float]]],
    *,
    dictionary_name: str = "DICT_APRILTAG_36h11",
) -> dict[str, Any]:
    image = np.asarray(image_gray, dtype=np.uint8)
    if image.ndim != 2:
        raise ValueError("detect_frame expects a grayscale image")
    parameters = cv2.aruco.DetectorParameters()
    parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_APRILTAG
    detector = cv2.aruco.ArucoDetector(_dictionary(dictionary_name), parameters)
    raw_corners, raw_ids, rejected = detector.detectMarkers(image)
    ids = [] if raw_ids is None else [int(value) for value in raw_ids.flatten()]
    corners = [np.asarray(value, dtype=np.float64).reshape(4, 2) for value in raw_corners]
    accepted, reason = validate_detection(
        ids,
        corners,
        image.shape,
        {int(value) for value in tag_corners_world_m},
    )

    tags = []
    for tag_id, image_corners in sorted(zip(ids, corners, strict=True), key=lambda item: item[0]):
        object_corners = tag_corners_world_m.get(str(tag_id))
        if object_corners is None:
            accepted, reason = False, "missing_object_points"
            continue
        area = abs(float(cv2.contourArea(image_corners.astype(np.float32))))
        perimeter = float(cv2.arcLength(image_corners.astype(np.float32), True))
        tags.append(
            {
                "id": tag_id,
                "image_corners_px": image_corners.tolist(),
                "object_corners_world_m": object_corners,
                "area_px2": area,
                "perimeter_px": perimeter,
                "minimum_border_margin_px": float(
                    min(
                        image_corners[:, 0].min(),
                        image.shape[1] - 1 - image_corners[:, 0].max(),
                        image_corners[:, 1].min(),
                        image.shape[0] - 1 - image_corners[:, 1].max(),
                    )
                ),
            }
        )
    return {
        "accepted": accepted,
        "reason": reason,
        "dictionary": dictionary_name,
        "tag_count": len(tags),
        "corner_count": 4 * len(tags),
        "rejected_candidate_count": len(rejected),
        "laplacian_variance": float(cv2.Laplacian(image, cv2.CV_64F).var()),
        "tags": tags,
    }


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_calibration_run(
    render_directory: str | Path,
    output_directory: str | Path,
) -> DetectionRunResult:
    render_directory = Path(render_directory)
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=False)
    truth_path = render_directory / "ground_truth.json"
    truth = json.loads(truth_path.read_text())
    frame_records = []
    overlay_paths = []
    for source_frame in truth["frames"]:
        image_path = render_directory / source_frame["rgb_file"]
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(image_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        detection = detect_frame(gray, truth["tag_corners_world_m"])
        actual_source_sha256 = _sha256(image_path)
        if actual_source_sha256 != source_frame["rgb_sha256"]:
            detection["accepted"] = False
            detection["reason"] = "source_rgb_sha_mismatch"
        elif source_frame.get("assessment", {}).get("accepted") is not True:
            detection["accepted"] = False
            reason = source_frame.get("assessment", {}).get("reason", "missing_assessment")
            detection["reason"] = f"renderer_rejected:{reason}"

        overlay = image.copy()
        if detection["tags"]:
            corners = [
                np.asarray(tag["image_corners_px"], dtype=np.float32).reshape(1, 4, 2)
                for tag in detection["tags"]
            ]
            ids = np.asarray([[tag["id"]] for tag in detection["tags"]], dtype=np.int32)
            cv2.aruco.drawDetectedMarkers(overlay, corners, ids)
        color = (0, 180, 0) if detection["accepted"] else (0, 0, 255)
        cv2.putText(
            overlay,
            detection["reason"],
            (12, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
            cv2.LINE_AA,
        )
        overlay_path = output_directory / f"overlay_{source_frame['index']:02d}.png"
        if not cv2.imwrite(str(overlay_path), overlay):
            raise OSError(f"failed to write {overlay_path}")
        overlay_paths.append(overlay_path)
        detection.update(
            {
                "frame_index": source_frame["index"],
                "source_rgb_file": source_frame["rgb_file"],
                "source_rgb_sha256": source_frame["rgb_sha256"],
                "actual_source_rgb_sha256": actual_source_sha256,
                "overlay_file": overlay_path.name,
                "overlay_sha256": _sha256(overlay_path),
            }
        )
        frame_records.append(detection)

    json_path = output_directory / "detections.json"
    payload = {
        "schema_version": 1,
        "source_ground_truth": str(truth_path),
        "source_ground_truth_sha256": _sha256(truth_path),
        "dictionary": "DICT_APRILTAG_36h11",
        "measurement_policy": "2d_corners_from_detector_not_ground_truth_projection",
        "frames": frame_records,
        "accepted_frame_count": sum(frame["accepted"] for frame in frame_records),
        "rejected_frames": [
            {"frame_index": frame["frame_index"], "reason": frame["reason"]}
            for frame in frame_records
            if not frame["accepted"]
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n")
    return DetectionRunResult(
        output_directory=output_directory,
        json_path=json_path,
        overlay_paths=tuple(overlay_paths),
    )
