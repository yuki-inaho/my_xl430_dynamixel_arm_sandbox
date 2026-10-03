"""Estimate synthetic intrinsics/extrinsics and compare them with MuJoCo truth."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray


class CalibrationDatasetError(ValueError):
    pass


def reprojection_rms_px(residuals: NDArray) -> float:
    """RMS Euclidean pixel distance per corner, not per coordinate component."""
    residuals = np.asarray(residuals, dtype=float)
    if residuals.ndim != 2 or residuals.shape[1] != 2 or len(residuals) == 0:
        raise CalibrationDatasetError("residuals must be nonempty Nx2")
    if not np.isfinite(residuals).all():
        raise CalibrationDatasetError("residuals must be finite")
    return float(np.sqrt(np.mean(np.sum(np.square(residuals), axis=1))))


@dataclass(frozen=True)
class CalibrationResult:
    output_directory: Path
    json_path: Path
    markdown_path: Path


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rotation_error_degrees(estimated: NDArray, truth: NDArray) -> float:
    delta = estimated @ truth.T
    cosine = np.clip((np.trace(delta) - 1.0) / 2.0, -1.0, 1.0)
    return float(np.degrees(np.arccos(cosine)))


def validate_pose_diversity(
    rvecs: Sequence[NDArray],
    tvecs: Sequence[NDArray],
    *,
    minimum_normal_spread_degrees: float = 10.0,
    minimum_distance_span_m: float = 0.08,
) -> dict[str, float | int]:
    if len(rvecs) < 12 or len(tvecs) != len(rvecs):
        raise CalibrationDatasetError("pose diversity requires at least 12 matched poses")
    normals = []
    distances = []
    for rotation_vector, translation_vector in zip(rvecs, tvecs, strict=True):
        rotation, _ = cv2.Rodrigues(np.asarray(rotation_vector, dtype=np.float64))
        normals.append(rotation @ np.array([0.0, 0.0, 1.0]))
        distances.append(float(np.linalg.norm(translation_vector)))
    normal_spread = max(
        float(np.degrees(np.arccos(np.clip(np.dot(first, second), -1.0, 1.0))))
        for index, first in enumerate(normals)
        for second in normals[index + 1 :]
    )
    distance_span = max(distances) - min(distances)
    sorted_distances = sorted(distances)
    distance_clusters = 1
    cluster_anchor = sorted_distances[0]
    for distance in sorted_distances[1:]:
        if distance - cluster_anchor >= 0.04:
            distance_clusters += 1
            cluster_anchor = distance
    if (
        normal_spread < minimum_normal_spread_degrees
        or distance_span < minimum_distance_span_m
        or distance_clusters < 3
    ):
        raise CalibrationDatasetError(
            "insufficient pose diversity: need >=10 deg normal spread and three distances"
        )
    return {
        "normal_spread_degrees": normal_spread,
        "distance_span_m": distance_span,
        "distance_cluster_count": distance_clusters,
    }


def calibrate_run(
    detections_json: str | Path,
    ground_truth_json: str | Path,
    output_directory: str | Path,
    *,
    object_scale: float = 1.0,
) -> CalibrationResult:
    detections_json = Path(detections_json)
    ground_truth_json = Path(ground_truth_json)
    output_directory = Path(output_directory)
    if object_scale <= 0.0:
        raise CalibrationDatasetError("object_scale must be positive")
    detections = json.loads(detections_json.read_text())
    truth = json.loads(ground_truth_json.read_text())
    accepted = [frame for frame in detections["frames"] if frame["accepted"]]
    if len(accepted) < 12:
        raise CalibrationDatasetError("calibration requires at least 12 accepted frames")

    truth_by_index = {frame["index"]: frame for frame in truth["frames"]}
    object_points = []
    image_points = []
    for frame in accepted:
        object_points.append(
            np.concatenate(
                [
                    np.asarray(tag["object_corners_world_m"], dtype=np.float32)
                    for tag in frame["tags"]
                ]
            )
            * object_scale
        )
        image_points.append(
            np.concatenate(
                [np.asarray(tag["image_corners_px"], dtype=np.float32) for tag in frame["tags"]]
            )
        )

    flags = (
        cv2.CALIB_ZERO_TANGENT_DIST
        | cv2.CALIB_FIX_K1
        | cv2.CALIB_FIX_K2
        | cv2.CALIB_FIX_K3
        | cv2.CALIB_FIX_K4
        | cv2.CALIB_FIX_K5
        | cv2.CALIB_FIX_K6
    )
    (
        reprojection_rms,
        camera_matrix,
        distortion,
        calibration_rvecs,
        calibration_tvecs,
        std_intrinsics,
        std_extrinsics,
        per_view_errors,
    ) = cv2.calibrateCameraExtended(
        object_points,
        image_points,
        (int(truth["image_width_px"]), int(truth["image_height_px"])),
        None,
        np.zeros((8, 1), dtype=np.float64),
        flags=flags,
    )
    diversity = validate_pose_diversity(calibration_rvecs, calibration_tvecs)

    truth_camera_matrix = np.asarray(truth["camera_matrix"], dtype=np.float64)
    fx_relative_error = abs(camera_matrix[0, 0] / truth_camera_matrix[0, 0] - 1.0)
    fy_relative_error = abs(camera_matrix[1, 1] / truth_camera_matrix[1, 1] - 1.0)
    cx_absolute_error = abs(camera_matrix[0, 2] - truth_camera_matrix[0, 2])
    cy_absolute_error = abs(camera_matrix[1, 2] - truth_camera_matrix[1, 2])

    frame_reports = []
    for object_set, image_set, detection_frame in zip(
        object_points, image_points, accepted, strict=True
    ):
        solved, rotation_vector, translation_vector = cv2.solvePnP(
            object_set,
            image_set,
            camera_matrix,
            distortion,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not solved:
            raise CalibrationDatasetError(f"PnP failed for frame {detection_frame['frame_index']}")
        estimated_rotation, _ = cv2.Rodrigues(rotation_vector)
        true_transform = np.asarray(
            truth_by_index[detection_frame["frame_index"]]["camera_from_world"],
            dtype=np.float64,
        )
        rotation_error = _rotation_error_degrees(
            estimated_rotation,
            true_transform[:3, :3],
        )
        translation_error = float(
            np.linalg.norm(translation_vector.reshape(3) - true_transform[:3, 3]) * 1000.0
        )
        projected, _ = cv2.projectPoints(
            object_set,
            rotation_vector,
            translation_vector,
            camera_matrix,
            distortion,
        )
        residual = projected.reshape(-1, 2) - image_set
        frame_reports.append(
            {
                "frame_index": detection_frame["frame_index"],
                "tag_count": detection_frame["tag_count"],
                "corner_count": detection_frame["corner_count"],
                "rotation_error_deg": rotation_error,
                "translation_error_mm": translation_error,
                "reprojection_rms_px": reprojection_rms_px(residual),
                "estimated_rvec": rotation_vector.reshape(3).tolist(),
                "estimated_tvec_m": translation_vector.reshape(3).tolist(),
            }
        )

    metrics = {
        "reprojection_rms_px": float(reprojection_rms),
        "fx_relative_error": float(fx_relative_error),
        "fy_relative_error": float(fy_relative_error),
        "cx_absolute_error_px": float(cx_absolute_error),
        "cy_absolute_error_px": float(cy_absolute_error),
        "maximum_rotation_error_deg": max(frame["rotation_error_deg"] for frame in frame_reports),
        "maximum_translation_error_mm": max(
            frame["translation_error_mm"] for frame in frame_reports
        ),
    }
    gates = {
        "accepted_frame_count": len(accepted) >= 12,
        "reprojection_rms": metrics["reprojection_rms_px"] <= 0.5,
        "fx_relative_error": metrics["fx_relative_error"] <= 0.01,
        "fy_relative_error": metrics["fy_relative_error"] <= 0.01,
        "cx_absolute_error": metrics["cx_absolute_error_px"] <= 2.0,
        "cy_absolute_error": metrics["cy_absolute_error_px"] <= 2.0,
        "rotation_error": metrics["maximum_rotation_error_deg"] <= 0.5,
        "translation_error": metrics["maximum_translation_error_mm"] <= 2.0,
    }
    failed_gates = [name for name, passed in gates.items() if not passed]
    output_directory.mkdir(parents=True, exist_ok=False)
    json_path = output_directory / "calibration_report.json"
    payload = {
        "schema_version": 1,
        "detection_source": str(detections_json),
        "detection_source_sha256": _sha256(detections_json),
        "ground_truth_source": str(ground_truth_json),
        "ground_truth_source_sha256": _sha256(ground_truth_json),
        "accepted_frame_count": len(accepted),
        "object_scale": object_scale,
        "calibration_model": "pinhole_zero_distortion_synthetic",
        "estimated_camera_matrix": camera_matrix.tolist(),
        "truth_camera_matrix": truth_camera_matrix.tolist(),
        "estimated_distortion": distortion.reshape(-1).tolist(),
        "std_deviation_intrinsics": std_intrinsics.reshape(-1).tolist(),
        "std_deviation_extrinsics": std_extrinsics.reshape(-1).tolist(),
        "per_view_errors_px": per_view_errors.reshape(-1).tolist(),
        "pose_diversity": diversity,
        "metrics": metrics,
        "gates": gates,
        "failed_gates": failed_gates,
        "synthetic_validation_passed": not failed_gates,
        "real_camera_calibration_approved": False,
        "frames": frame_reports,
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n")
    markdown_path = output_directory / "calibration_report.md"
    markdown_path.write_text(
        "\n".join(
            [
                "# Synthetic calibration report",
                "",
                f"- Result: {'PASS' if not failed_gates else 'FAIL'}",
                f"- Accepted frames: {len(accepted)}",
                f"- Reprojection RMS: {metrics['reprojection_rms_px']:.6f} px",
                f"- fx/fy relative error: {metrics['fx_relative_error']:.6%} / {metrics['fy_relative_error']:.6%}",
                f"- cx/cy absolute error: {metrics['cx_absolute_error_px']:.6f} / {metrics['cy_absolute_error_px']:.6f} px",
                f"- Maximum pose error: {metrics['maximum_rotation_error_deg']:.6f} deg / {metrics['maximum_translation_error_mm']:.6f} mm",
                f"- Failed gates: {', '.join(failed_gates) if failed_gates else 'none'}",
                "- Real camera calibration approved: no",
                "",
            ]
        )
    )
    return CalibrationResult(output_directory, json_path, markdown_path)
