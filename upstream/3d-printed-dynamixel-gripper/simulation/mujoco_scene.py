"""Headless MuJoCo scene generation for P05-fixed AprilGrid calibration."""

import json
import os
import shutil
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

import cv2
import mujoco
import numpy as np
from numpy.typing import ArrayLike, NDArray

from simulation.frames import camera_intrinsics_from_fovy, mujoco_camera_pose, project_world_points

FloatArray = NDArray[np.float64]
ASSET_TEMPLATE = Path(__file__).with_name("assets") / "calibration_scene.xml"


@dataclass(frozen=True)
class CameraView:
    name: str
    position_world_m: tuple[float, float, float]
    target_world_m: tuple[float, float, float]

    def __post_init__(self) -> None:
        eye = np.asarray(self.position_world_m, dtype=np.float64)
        target = np.asarray(self.target_world_m, dtype=np.float64)
        if eye.shape != (3,) or target.shape != (3,):
            raise ValueError("camera position and target must be 3-vectors")
        if np.linalg.norm(eye - target) < 1e-9:
            raise ValueError("camera eye and target must differ")


@dataclass(frozen=True)
class FrameAssessment:
    accepted: bool
    reason: str
    sha256: str
    visible_corner_count: int


@dataclass(frozen=True)
class RenderResult:
    output_directory: Path
    scene_path: Path
    truth_path: Path
    frame_paths: tuple[Path, ...]


def default_camera_views() -> tuple[CameraView, ...]:
    views_by_height = (
        (0.30, ((-0.10, -0.06), (0.10, -0.05), (-0.07, 0.09), (0.08, 0.08))),
        (0.38, ((-0.13, -0.06), (0.12, -0.08), (-0.09, 0.11), (0.11, 0.10))),
        (0.46, ((-0.15, -0.07), (0.14, -0.09), (-0.11, 0.13), (0.13, 0.12))),
    )
    return tuple(
        CameraView(
            name=f"p05_pose_{index:02d}",
            position_world_m=(x, y, z),
            target_world_m=(0.0, 0.0, 0.0),
        )
        for index, (z, (x, y)) in enumerate(
            item for z, offsets in views_by_height for item in ((z, offset) for offset in offsets)
        )
    )


def _camera_axes(view: CameraView) -> tuple[FloatArray, FloatArray, FloatArray]:
    eye = np.asarray(view.position_world_m, dtype=np.float64)
    target = np.asarray(view.target_world_m, dtype=np.float64)
    forward = (target - eye) / np.linalg.norm(target - eye)
    world_up = np.array([0.0, 1.0, 0.0])
    z_axis = -forward
    x_axis = np.cross(world_up, z_axis)
    if np.linalg.norm(x_axis) < 1e-8:
        world_up = np.array([1.0, 0.0, 0.0])
        x_axis = np.cross(world_up, z_axis)
    x_axis /= np.linalg.norm(x_axis)
    y_axis = np.cross(z_axis, x_axis)
    y_axis /= np.linalg.norm(y_axis)
    return x_axis, y_axis, z_axis


def _numbers(values: ArrayLike) -> str:
    return " ".join(f"{float(value):.12g}" for value in np.asarray(values).reshape(-1))


def _sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assess_frame(
    image_rgb: NDArray[np.uint8],
    projected_board_corners: ArrayLike,
    board_front_facing: bool,
    prior_hashes: set[str],
) -> FrameAssessment:
    image = np.asarray(image_rgb)
    digest = _sha256_bytes(image.tobytes())
    corners = np.asarray(projected_board_corners, dtype=np.float64)
    height, width = image.shape[:2]
    visible = (
        (corners[:, 0] >= 0)
        & (corners[:, 0] < width)
        & (corners[:, 1] >= 0)
        & (corners[:, 1] < height)
    )
    visible_count = int(np.count_nonzero(visible))
    if float(np.std(image)) < 1.0:
        return FrameAssessment(False, "black_image", digest, visible_count)
    if digest in prior_hashes:
        return FrameAssessment(False, "duplicate_frame", digest, visible_count)
    if not board_front_facing:
        return FrameAssessment(False, "board_backside", digest, visible_count)
    if visible_count != 4:
        return FrameAssessment(False, "board_outside_image", digest, visible_count)
    return FrameAssessment(True, "accepted", digest, visible_count)


def _scene_xml(
    texture_filename: str,
    board_mesh_filename: str,
    board_width_m: float,
    board_height_m: float,
    views: tuple[CameraView, ...],
    fovy_degrees: float,
) -> ET.ElementTree:
    tree = ET.parse(ASSET_TEMPLATE)
    root = tree.getroot()
    asset = root.find("asset")
    worldbody = root.find("worldbody")
    if asset is None or worldbody is None:
        raise ValueError("scene template must contain asset and worldbody")
    ET.SubElement(asset, "texture", name="aprilgrid", type="2d", file=texture_filename)
    ET.SubElement(
        asset,
        "mesh",
        name="aprilgrid_board_mesh",
        file=board_mesh_filename,
        inertia="shell",
    )
    ET.SubElement(
        asset,
        "material",
        name="aprilgrid",
        texture="aprilgrid",
        texrepeat="1 1",
        texuniform="false",
        reflectance="0",
        specular="0",
        shininess="0",
    )
    ET.SubElement(
        worldbody,
        "geom",
        name="aprilgrid_board",
        type="mesh",
        mesh="aprilgrid_board_mesh",
        pos="0 0 0",
        material="aprilgrid",
        contype="0",
        conaffinity="0",
    )
    for view in views:
        x_axis, y_axis, _ = _camera_axes(view)
        body = ET.SubElement(
            worldbody,
            "body",
            name=f"P05_{view.name}",
            pos=_numbers(view.position_world_m),
        )
        ET.SubElement(
            body,
            "camera",
            name=view.name,
            pos="0 0 0",
            xyaxes=f"{_numbers(x_axis)} {_numbers(y_axis)}",
            fovy=f"{fovy_degrees:.12g}",
        )
    return tree


def _write_board_mesh(path: Path, width_m: float, height_m: float) -> None:
    half_width = width_m / 2.0
    half_height = height_m / 2.0
    path.write_text(
        "\n".join(
            [
                f"v {-half_width:.12g} {-half_height:.12g} 0",
                f"v {half_width:.12g} {-half_height:.12g} 0",
                f"v {half_width:.12g} {half_height:.12g} 0",
                f"v {-half_width:.12g} {half_height:.12g} 0",
                "vt 0 0",
                "vt 1 0",
                "vt 1 1",
                "vt 0 1",
                "f 1/1 2/2 3/3",
                "f 1/1 3/3 4/4",
                "",
            ]
        )
    )


def _board_world_geometry(
    board_payload: dict[str, object],
) -> tuple[FloatArray, dict[int, FloatArray]]:
    width_m = float(board_payload["board_width_mm"]) / 1000.0
    height_m = float(board_payload["board_height_mm"]) / 1000.0
    board_corners = np.array(
        [
            [-width_m / 2, height_m / 2, 0.0],
            [width_m / 2, height_m / 2, 0.0],
            [width_m / 2, -height_m / 2, 0.0],
            [-width_m / 2, -height_m / 2, 0.0],
        ]
    )
    tag_corners: dict[int, FloatArray] = {}
    for tag in board_payload["tags"]:
        corners_mm = np.asarray(tag["object_corners_mm"], dtype=np.float64)
        world = np.column_stack(
            [
                corners_mm[:, 0] / 1000.0 - width_m / 2,
                height_m / 2 - corners_mm[:, 1] / 1000.0,
                np.zeros(4),
            ]
        )
        tag_corners[int(tag["id"])] = world
    return board_corners, tag_corners


def render_calibration_run(
    *,
    board_directory: str | Path,
    output_directory: str | Path,
    width: int = 640,
    height: int = 480,
    fovy_degrees: float = 50.0,
    views: tuple[CameraView, ...] | None = None,
) -> RenderResult:
    render_backend = os.environ.get("MUJOCO_GL")
    if render_backend not in {"egl", "osmesa"}:
        raise RuntimeError("MUJOCO_GL must be explicitly set to egl or osmesa")
    board_directory = Path(board_directory)
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=False)
    board_payload = json.loads((board_directory / "board.json").read_text())
    source_texture = board_directory / "aprilgrid_tag36h11.png"
    texture_path = output_directory / source_texture.name
    shutil.copy2(source_texture, texture_path)
    selected_views = views or default_camera_views()
    board_width_m = float(board_payload["board_width_mm"]) / 1000.0
    board_height_m = float(board_payload["board_height_mm"]) / 1000.0
    board_mesh_path = output_directory / "aprilgrid_board.obj"
    _write_board_mesh(board_mesh_path, board_width_m, board_height_m)
    tree = _scene_xml(
        texture_path.name,
        board_mesh_path.name,
        board_width_m,
        board_height_m,
        selected_views,
        fovy_degrees,
    )
    scene_path = output_directory / "calibration_scene.xml"
    tree.write(scene_path, encoding="unicode", xml_declaration=True)

    model = mujoco.MjModel.from_xml_path(str(scene_path))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    renderer = mujoco.Renderer(model, height=height, width=width)
    intrinsics = camera_intrinsics_from_fovy(
        width=width,
        height=height,
        fovy_degrees=fovy_degrees,
    )
    board_corners, tag_corners = _board_world_geometry(board_payload)
    prior_hashes: set[str] = set()
    frame_paths: list[Path] = []
    frame_records: list[dict[str, object]] = []
    try:
        for index, view in enumerate(selected_views):
            camera_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, view.name)
            renderer.update_scene(data, camera=view.name)
            image_rgb = renderer.render().copy()
            rotation_world_from_mujoco_camera = data.cam_xmat[camera_id].reshape(3, 3).copy()
            position_world = data.cam_xpos[camera_id].copy()
            pose = mujoco_camera_pose(position_world, rotation_world_from_mujoco_camera)
            projected_board, _ = project_world_points(
                board_corners,
                intrinsics.matrix,
                pose.camera_from_world,
            )
            board_front_facing = bool(position_world[2] > 0.0)
            assessment = assess_frame(
                image_rgb,
                projected_board,
                board_front_facing,
                prior_hashes,
            )
            prior_hashes.add(assessment.sha256)
            frame_path = output_directory / f"frame_{index:02d}.png"
            if not cv2.imwrite(str(frame_path), cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)):
                raise OSError(f"failed to write {frame_path}")
            frame_paths.append(frame_path)
            frame_records.append(
                {
                    "index": index,
                    "camera_name": view.name,
                    "rgb_file": frame_path.name,
                    "rgb_sha256": _sha256_file(frame_path),
                    "raw_rgb_sha256": assessment.sha256,
                    "camera_matrix": intrinsics.matrix.tolist(),
                    "world_from_camera": pose.world_from_camera.tolist(),
                    "camera_from_world": pose.camera_from_world.tolist(),
                    "position_world_m": position_world.tolist(),
                    "projected_board_corners_px": projected_board.tolist(),
                    "board_visible_corner_count": assessment.visible_corner_count,
                    "assessment": asdict(assessment),
                }
            )
    finally:
        renderer.close()

    truth_path = output_directory / "ground_truth.json"
    truth_payload = {
        "schema_version": 1,
        "render_backend": render_backend,
        "mujoco_version": mujoco.__version__,
        "camera_parent": "P05_fixed_eye_in_hand",
        "camera_roll_dependency": "none_J5_roll_independent",
        "image_width_px": width,
        "image_height_px": height,
        "fovy_degrees": fovy_degrees,
        "camera_matrix": intrinsics.matrix.tolist(),
        "board_source_json": str(board_directory / "board.json"),
        "board_source_sha256": _sha256_file(board_directory / "board.json"),
        "board_corners_world_m": board_corners.tolist(),
        "tag_corners_world_m": {
            str(tag_id): corners.tolist() for tag_id, corners in tag_corners.items()
        },
        "frames": frame_records,
    }
    truth_path.write_text(json.dumps(truth_payload, indent=2) + "\n")
    return RenderResult(
        output_directory=output_directory,
        scene_path=scene_path,
        truth_path=truth_path,
        frame_paths=tuple(frame_paths),
    )
