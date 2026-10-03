"""Connect the provisional CAD camera carrier frame to MuJoCo conventions."""

import json
import xml.etree.ElementTree as ET
from hashlib import sha256
from pathlib import Path

import numpy as np
import yaml
from numpy.typing import ArrayLike, NDArray

from simulation.frames import (
    MUJOCO_CAMERA_FROM_OPENCV_CAMERA,
    homogeneous_transform,
    mujoco_camera_pose,
)

FloatArray = NDArray[np.float64]
ROOT = Path(__file__).resolve().parents[1]
CAMERA_SPEC = ROOT / "specs" / "camera_mount.yaml"
ARCHITECTURE_SPEC = ROOT / "specs" / "architecture.yaml"


def _rotation_x(degrees: float) -> FloatArray:
    radians = np.deg2rad(degrees)
    cosine, sine = np.cos(radians), np.sin(radians)
    return np.array(
        [[1.0, 0.0, 0.0], [0.0, cosine, -sine], [0.0, sine, cosine]],
        dtype=np.float64,
    )


def _rotation_about_axis(axis: ArrayLike, degrees: float) -> FloatArray:
    vector = np.asarray(axis, dtype=np.float64)
    vector /= np.linalg.norm(vector)
    radians = np.deg2rad(degrees)
    skew = np.array(
        [
            [0.0, -vector[2], vector[1]],
            [vector[2], 0.0, -vector[0]],
            [-vector[1], vector[0], 0.0],
        ]
    )
    return (
        np.eye(3) * np.cos(radians)
        + (1.0 - np.cos(radians)) * np.outer(vector, vector)
        + np.sin(radians) * skew
    )


def _validate_pose(pose: ArrayLike) -> FloatArray:
    transform = np.asarray(pose, dtype=np.float64)
    if transform.shape != (4, 4):
        raise ValueError("camera pose must have shape (4, 4)")
    if not np.isfinite(transform).all() or not np.allclose(transform[3], [0, 0, 0, 1]):
        raise ValueError("camera pose must be a finite homogeneous transform")
    rotation = transform[:3, :3]
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-9):
        raise ValueError("camera pose rotation must be orthonormal")
    if not np.isclose(np.linalg.det(rotation), 1.0, atol=1e-9):
        raise ValueError("camera pose must be right-handed")
    return transform


def candidate_camera_pose_from_spec() -> FloatArray:
    """Return world_from_OpenCV-camera for the mechanical carrier proxy."""
    camera_spec = yaml.safe_load(CAMERA_SPEC.read_text())
    architecture = yaml.safe_load(ARCHITECTURE_SPEC.read_text())
    candidate = camera_spec["camera"]["mechanical_camera_frame_candidate"]
    if candidate["status"] != "carrier_normal_proxy_not_exact_optical_frame":
        raise ValueError("camera frame status must remain a mechanical proxy")
    if camera_spec["camera"]["optical_frame"] is not None:
        raise ValueError("exact optical frame must not be fabricated from the proxy")
    relationship = architecture["camera"]["kinematic_relationship"]
    if relationship["follows_cad_joint_J5_output_rotation"] is not False:
        raise ValueError("P05 camera must remain independent of J5 output roll")
    rotation_spec = candidate["rotation_world_from_opencv_camera"]
    if rotation_spec["construction"] != "rotation_about_world_x":
        raise ValueError("unsupported mechanical camera frame construction")
    return homogeneous_transform(
        _rotation_x(float(rotation_spec["degrees"])),
        np.asarray(candidate["origin_world_mm"], dtype=np.float64) / 1000.0,
    )


def p05_fixed_camera_pose(
    world_from_camera: ArrayLike,
    *,
    j5_roll_degrees: float,
) -> FloatArray:
    """Measure the fixed camera after changing the actual MuJoCo J5 joint."""
    import mujoco

    if not np.isfinite(j5_roll_degrees):
        raise ValueError("joint angle must be finite")
    model = build_camera_rig(world_from_camera)
    data = mujoco.MjData(model)
    data.qpos[model.joint("J5").qposadr[0]] = np.deg2rad(j5_roll_degrees)
    mujoco.mj_forward(model, data)
    camera_id = model.camera("p05_camera").id
    return mujoco_camera_pose(
        data.cam_xpos[camera_id], data.cam_xmat[camera_id].reshape(3, 3)
    ).world_from_camera


def build_camera_rig(reference_from_camera: ArrayLike, *, world_from_reference=None):
    """Compile a kinematic proxy, not a mass/contact model of the complete arm.

    P05 uses the R3 reference axes at the saved pose. The fixed camera is a
    sibling of J5_output. The deliberately wrong horn camera is its child.
    """
    import mujoco

    candidate = mujoco_pose_from_opencv_pose(reference_from_camera)
    parent = _validate_pose(np.eye(4) if world_from_reference is None else world_from_reference)
    architecture = yaml.safe_load(ARCHITECTURE_SPEC.read_text())
    joint = next(j for j in architecture["namespaces"]["cad"]["joints"] if j["cad_joint"] == "J5")
    centre = np.asarray(joint["centre_mm"], dtype=float) / 1000

    def numbers(values):
        return " ".join(format(float(v), ".17g") for v in np.asarray(values).ravel())

    def quaternion(rotation):
        quat = np.empty(4)
        mujoco.mju_mat2Quat(quat, np.asarray(rotation, dtype=float).ravel())
        return numbers(quat)

    root = ET.Element("mujoco", model="CAD_camera_parentage_proxy")
    ET.SubElement(root, "compiler", angle="radian")
    body = ET.SubElement(
        ET.SubElement(root, "worldbody"),
        "body",
        name="P05",
        pos=numbers(parent[:3, 3]),
        quat=quaternion(parent[:3, :3]),
    )
    ET.SubElement(
        body,
        "camera",
        name="p05_camera",
        pos=numbers(candidate[:3, 3]),
        quat=quaternion(candidate[:3, :3]),
    )
    output = ET.SubElement(body, "body", name="J5_output", pos=numbers(centre))
    ET.SubElement(output, "inertial", pos="0 0 0", mass="0.001", diaginertia="1e-6 1e-6 1e-6")
    ET.SubElement(
        output, "joint", name="J5", type="hinge", axis=numbers(joint["axis"]), limited="false"
    )
    ET.SubElement(
        output,
        "camera",
        name="horn_negative",
        pos=numbers(candidate[:3, 3] - centre),
        quat=quaternion(candidate[:3, :3]),
    )
    return mujoco.MjModel.from_xml_string(ET.tostring(root, encoding="unicode"))


def horn_following_camera_pose(
    world_from_camera_at_zero: ArrayLike,
    *,
    j5_roll_degrees: float,
) -> FloatArray:
    """Rejected comparison: rotate the camera with the J5 output horn."""
    architecture = yaml.safe_load(ARCHITECTURE_SPEC.read_text())
    j5 = next(
        joint for joint in architecture["namespaces"]["cad"]["joints"] if joint["cad_joint"] == "J5"
    )
    centre = np.asarray(j5["centre_mm"], dtype=np.float64) / 1000.0
    rotation = _rotation_about_axis(j5["axis"], j5_roll_degrees)
    around_centre = np.eye(4)
    around_centre[:3, :3] = rotation
    around_centre[:3, 3] = centre - rotation @ centre
    return around_centre @ _validate_pose(world_from_camera_at_zero)


def mujoco_pose_from_opencv_pose(world_from_opencv_camera: ArrayLike) -> FloatArray:
    """Convert world_from_OpenCV-camera to world_from_MuJoCo-camera."""
    opencv_pose = _validate_pose(world_from_opencv_camera)
    opencv_camera_from_mujoco_camera = homogeneous_transform(
        MUJOCO_CAMERA_FROM_OPENCV_CAMERA,
        np.zeros(3),
    )
    result = opencv_pose @ opencv_camera_from_mujoco_camera
    return _validate_pose(result)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def write_integration_report(
    output_directory: str | Path,
    *,
    roll_angles_degrees: tuple[float, ...] = (-90.0, 0.0, 90.0),
) -> Path:
    import mujoco

    if len(set(roll_angles_degrees)) < 2 or not np.isfinite(roll_angles_degrees).all():
        raise ValueError("at least two distinct finite roll angles required")
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=False)
    candidate = candidate_camera_pose_from_spec()
    model = build_camera_rig(candidate)
    xml_path = output_directory / "camera_parentage.xml"
    mujoco.mj_saveLastXML(str(xml_path), model)
    fixed = [
        p05_fixed_camera_pose(candidate, j5_roll_degrees=angle) for angle in roll_angles_degrees
    ]
    horn = []
    data = mujoco.MjData(model)
    for angle in roll_angles_degrees:
        data.qpos[model.joint("J5").qposadr[0]] = np.deg2rad(angle)
        mujoco.mj_forward(model, data)
        camera_id = model.camera("horn_negative").id
        pose = mujoco_camera_pose(data.cam_xpos[camera_id], data.cam_xmat[camera_id].reshape(3, 3))
        horn.append(pose.world_from_camera)
    payload = {
        "schema_version": 1,
        "verification_method": "MuJoCo_mj_forward_actual_J5_qpos_and_cam_xpos_xmat",
        "model_xml": xml_path.name,
        "model_sha256": _sha256(xml_path),
        "fixture_inertia_is_not_physical": True,
        "full_arm_dynamics_validated": False,
        "aprilgrid_render_scene_uses_this_rig": False,
        "scope": "CAD_mechanical_camera_frame_proxy_to_MuJoCo_not_real_optical_calibration",
        "camera_mount_spec": str(CAMERA_SPEC),
        "camera_mount_spec_sha256": _sha256(CAMERA_SPEC),
        "architecture_spec": str(ARCHITECTURE_SPEC),
        "architecture_spec_sha256": _sha256(ARCHITECTURE_SPEC),
        "exact_optical_frame_confirmed": False,
        "physical_ID_to_CAD_J5_mapping_confirmed": False,
        "roll_angles_degrees": list(roll_angles_degrees),
        "p05_fixed_world_from_opencv_camera": [pose.tolist() for pose in fixed],
        "p05_fixed_world_from_mujoco_camera": [
            mujoco_pose_from_opencv_pose(pose).tolist() for pose in fixed
        ],
        "rejected_horn_following_world_from_opencv_camera": [pose.tolist() for pose in horn],
        "p05_invariant": all(np.allclose(fixed[0], pose, atol=1e-12) for pose in fixed[1:]),
        "horn_negative_changes": all(
            not np.allclose(horn[0], pose, atol=1e-12) for pose in horn[1:]
        ),
        "fabrication_approved": False,
        "real_camera_calibration_approved": False,
    }
    report_path = output_directory / "integration_report.json"
    report_path.write_text(json.dumps(payload, indent=2) + "\n")
    return report_path
