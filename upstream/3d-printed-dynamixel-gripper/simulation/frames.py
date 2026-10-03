"""Explicit MuJoCo, CAD-world, and OpenCV camera-frame transforms."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]

# MuJoCo cameras look along local -Z with +Y up. OpenCV cameras look along
# +Z with +Y down. This proper rotation maps OpenCV camera coordinates into
# the MuJoCo camera frame and is its own inverse.
MUJOCO_CAMERA_FROM_OPENCV_CAMERA: FloatArray = np.diag([1.0, -1.0, -1.0])


@dataclass(frozen=True)
class CameraPose:
    """Both transform directions, named as destination_from_source."""

    world_from_camera: FloatArray
    camera_from_world: FloatArray


@dataclass(frozen=True)
class CameraIntrinsics:
    width: int
    height: int
    fovy_degrees: float
    fx: float
    fy: float
    cx: float
    cy: float
    matrix: FloatArray


def _rotation_matrix(value: ArrayLike) -> FloatArray:
    rotation = np.asarray(value, dtype=np.float64)
    if rotation.shape != (3, 3):
        raise ValueError("rotation must have shape (3, 3)")
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-9):
        raise ValueError("rotation must be orthonormal")
    if not np.isclose(np.linalg.det(rotation), 1.0, atol=1e-9):
        raise ValueError("rotation must be right-handed")
    return rotation


def homogeneous_transform(rotation: ArrayLike, translation: ArrayLike) -> FloatArray:
    rotation_array = _rotation_matrix(rotation)
    translation_array = np.asarray(translation, dtype=np.float64)
    if translation_array.shape != (3,):
        raise ValueError("translation must have shape (3,)")
    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = rotation_array
    transform[:3, 3] = translation_array
    return transform


def invert_transform(destination_from_source: ArrayLike) -> FloatArray:
    transform = np.asarray(destination_from_source, dtype=np.float64)
    if transform.shape != (4, 4):
        raise ValueError("transform must have shape (4, 4)")
    rotation = _rotation_matrix(transform[:3, :3])
    inverse = np.eye(4, dtype=np.float64)
    inverse[:3, :3] = rotation.T
    inverse[:3, 3] = -(rotation.T @ transform[:3, 3])
    return inverse


def mujoco_camera_pose(
    position_world: ArrayLike,
    rotation_world_from_mujoco_camera: ArrayLike,
) -> CameraPose:
    """Convert a MuJoCo camera pose to explicit OpenCV-camera transforms."""
    world_from_mujoco_camera = homogeneous_transform(
        rotation_world_from_mujoco_camera,
        position_world,
    )
    mujoco_camera_from_opencv_camera = homogeneous_transform(
        MUJOCO_CAMERA_FROM_OPENCV_CAMERA,
        np.zeros(3),
    )
    world_from_camera = world_from_mujoco_camera @ mujoco_camera_from_opencv_camera
    return CameraPose(
        world_from_camera=world_from_camera,
        camera_from_world=invert_transform(world_from_camera),
    )


def camera_intrinsics_from_fovy(
    *, width: int, height: int, fovy_degrees: float
) -> CameraIntrinsics:
    """Derive an OpenCV K matrix from MuJoCo vertical field of view."""
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")
    if not 0.0 < fovy_degrees < 180.0:
        raise ValueError("fovy must be between 0 and 180 degrees")
    focal = 0.5 * height / np.tan(np.deg2rad(0.5 * fovy_degrees))
    cx = 0.5 * width
    cy = 0.5 * height
    matrix = np.array(
        [[focal, 0.0, cx], [0.0, focal, cy], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    return CameraIntrinsics(
        width=width,
        height=height,
        fovy_degrees=float(fovy_degrees),
        fx=float(focal),
        fy=float(focal),
        cx=cx,
        cy=cy,
        matrix=matrix,
    )


def project_world_points(
    points_world: ArrayLike,
    camera_matrix: ArrayLike,
    camera_from_world: ArrayLike,
) -> tuple[FloatArray, FloatArray]:
    points = np.asarray(points_world, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("points_world must have shape (N, 3)")
    intrinsics = np.asarray(camera_matrix, dtype=np.float64)
    if intrinsics.shape != (3, 3):
        raise ValueError("camera_matrix must have shape (3, 3)")
    transform = np.asarray(camera_from_world, dtype=np.float64)
    if transform.shape != (4, 4):
        raise ValueError("camera_from_world must have shape (4, 4)")

    homogeneous_points = np.column_stack([points, np.ones(len(points))])
    points_camera = (transform @ homogeneous_points.T).T[:, :3]
    depth = points_camera[:, 2]
    if np.any(depth <= 0.0):
        raise ValueError("all points must have positive OpenCV camera depth")
    image_homogeneous = (intrinsics @ points_camera.T).T
    pixels = image_homogeneous[:, :2] / image_homogeneous[:, 2, None]
    return pixels, depth
