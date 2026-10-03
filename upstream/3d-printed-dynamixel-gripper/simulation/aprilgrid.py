"""Generate a dimensioned AprilTag board and its MuJoCo texture declaration."""

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

import cv2
import numpy as np

DICTIONARY_NAME = "DICT_APRILTAG_36h11"
DICTIONARY_SIZE = 587


@dataclass(frozen=True)
class AprilGridSpec:
    rows: int = 3
    columns: int = 4
    tag_ids: tuple[int, ...] = tuple(range(12))
    tag_size_mm: float = 30.0
    tag_spacing_mm: float = 10.0
    board_margin_mm: float = 10.0
    pixels_per_mm: int = 4
    tag_size_definition: str = "black_border_outer"
    dictionary: str = DICTIONARY_NAME


@dataclass(frozen=True)
class AprilGridResult:
    output_directory: Path
    png_path: Path
    json_path: Path
    mujoco_asset_path: Path
    board_width_mm: float
    board_height_mm: float


def validate_spec(spec: AprilGridSpec) -> None:
    if spec.rows <= 0 or spec.columns <= 0:
        raise ValueError("rows and columns must be positive")
    if len(spec.tag_ids) != spec.rows * spec.columns:
        raise ValueError("tag_ids count must equal rows * columns")
    if len(set(spec.tag_ids)) != len(spec.tag_ids):
        raise ValueError("tag IDs must be unique")
    if any(tag_id < 0 or tag_id >= DICTIONARY_SIZE for tag_id in spec.tag_ids):
        raise ValueError("tag ID is outside the tag36h11 dictionary range")
    if spec.dictionary != DICTIONARY_NAME:
        raise ValueError(f"dictionary must remain {DICTIONARY_NAME}")
    if spec.tag_size_definition != "black_border_outer":
        raise ValueError("tag_size_mm must measure the black border outer edge")
    if min(spec.tag_size_mm, spec.tag_spacing_mm, spec.board_margin_mm) <= 0.0:
        raise ValueError("physical dimensions must be positive")
    if spec.pixels_per_mm <= 0:
        raise ValueError("pixels_per_mm must be positive")
    for dimension_name, dimension in (
        ("tag_size_mm", spec.tag_size_mm),
        ("tag_spacing_mm", spec.tag_spacing_mm),
        ("board_margin_mm", spec.board_margin_mm),
    ):
        pixels = dimension * spec.pixels_per_mm
        if not np.isclose(pixels, round(pixels), atol=1e-9):
            raise ValueError(f"{dimension_name} must map to an integer pixel count")


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_aprilgrid(spec: AprilGridSpec, output_directory: Path) -> AprilGridResult:
    validate_spec(spec)
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=False)

    scale = spec.pixels_per_mm
    tag_pixels = round(spec.tag_size_mm * scale)
    spacing_pixels = round(spec.tag_spacing_mm * scale)
    margin_pixels = round(spec.board_margin_mm * scale)
    width_pixels = (
        2 * margin_pixels + spec.columns * tag_pixels + (spec.columns - 1) * spacing_pixels
    )
    height_pixels = 2 * margin_pixels + spec.rows * tag_pixels + (spec.rows - 1) * spacing_pixels
    board = np.full((height_pixels, width_pixels), 255, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)

    tags: list[dict[str, object]] = []
    for index, tag_id in enumerate(spec.tag_ids):
        row, column = divmod(index, spec.columns)
        x0 = margin_pixels + column * (tag_pixels + spacing_pixels)
        y0 = margin_pixels + row * (tag_pixels + spacing_pixels)
        x1 = x0 + tag_pixels
        y1 = y0 + tag_pixels
        marker = cv2.aruco.generateImageMarker(dictionary, tag_id, tag_pixels, borderBits=1)
        board[y0:y1, x0:x1] = marker

        object_x0 = x0 / scale
        object_y0 = y0 / scale
        object_x1 = x1 / scale
        object_y1 = y1 / scale
        tags.append(
            {
                "id": tag_id,
                "pixel_corners": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
                "object_corners_mm": [
                    [object_x0, object_y0, 0.0],
                    [object_x1, object_y0, 0.0],
                    [object_x1, object_y1, 0.0],
                    [object_x0, object_y1, 0.0],
                ],
            }
        )

    png_path = output_directory / "aprilgrid_tag36h11.png"
    if not cv2.imwrite(str(png_path), board):
        raise OSError(f"failed to write {png_path}")

    board_width_mm = width_pixels / scale
    board_height_mm = height_pixels / scale
    json_path = output_directory / "board.json"
    payload = {
        "schema_version": 1,
        "spec": asdict(spec),
        "board_width_mm": board_width_mm,
        "board_height_mm": board_height_mm,
        "image_width_px": width_pixels,
        "image_height_px": height_pixels,
        "pixel_pitch_mm": 1.0 / scale,
        "coordinate_frame": "board_x_right_y_down_z_out",
        "tag_size_excludes_quiet_zone": True,
        "tags": tags,
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n")

    mujoco_asset_path = output_directory / "mujoco_asset.xml"
    mujoco_asset_path.write_text(
        "\n".join(
            [
                '<mujoco model="aprilgrid_asset">',
                f"  <!-- {DICTIONARY_NAME}; tag_size_mm is the black-border outer size -->",
                "  <asset>",
                f'    <texture name="aprilgrid" type="2d" file="{png_path.name}"/>',
                '    <material name="aprilgrid" texture="aprilgrid" texuniform="true"',
                '              texrepeat="1 1" reflectance="0" specular="0" shininess="0"/>',
                "  </asset>",
                "</mujoco>",
                "",
            ]
        )
    )

    payload["files"] = {
        png_path.name: _sha256(png_path),
        mujoco_asset_path.name: _sha256(mujoco_asset_path),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n")
    return AprilGridResult(
        output_directory=output_directory,
        png_path=png_path,
        json_path=json_path,
        mujoco_asset_path=mujoco_asset_path,
        board_width_mm=board_width_mm,
        board_height_mm=board_height_mm,
    )
