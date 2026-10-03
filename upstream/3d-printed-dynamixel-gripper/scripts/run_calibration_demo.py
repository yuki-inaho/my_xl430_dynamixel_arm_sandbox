"""Run the deterministic CAD + MuJoCo + AprilTag synthetic validation pipeline."""

import argparse
import json
import math
import os
import shutil
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

import cv2
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from camera_jig.build import envelope_hardware
from gripper_design.build import _source_rows, build_terminal_pose
from scripts.render_cad import render
from simulation.aprilgrid import AprilGridSpec, generate_aprilgrid
from simulation.calibrate import calibrate_run
from simulation.detect_aprilgrid import detect_calibration_run
from simulation.integration import write_integration_report
from simulation.mujoco_scene import render_calibration_run

MANIFEST_INPUTS = (
    "pyproject.toml",
    "uv.lock",
    "specs/architecture.yaml",
    "specs/camera_mount.yaml",
    "specs/interfaces_all_xl430.yaml",
    "specs/jaw_fastener_ledger.yaml",
    "specs/parallel_jaw.yaml",
    "specs/simulation_calibration.yaml",
    "scripts/run_calibration_demo.py",
    "simulation/aprilgrid.py",
    "simulation/calibrate.py",
    "simulation/detect_aprilgrid.py",
    "simulation/frames.py",
    "simulation/integration.py",
    "simulation/mujoco_scene.py",
    "gripper_design/build.py",
    "gripper_design/fastener_ledger.py",
    "gripper_design/parallel_jaw.py",
    "camera_jig/build.py",
    "camera_jig/spec.py",
    "scripts/assembly_io.py",
    "scripts/render_cad.py",
    "simulation/assets/calibration_scene.xml",
    "references/arm-r3/arm_XL430_R3.step",
    "references/arm-r3/P05_wrist_XL430.step",
    "references/arm-r3/joints.json",
    "references/robonine/RB9.01.062.000 Gripper.STEP",
)


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _files(output_directory: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": str(path.relative_to(output_directory)),
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(output_directory.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    ]


def _cad_shapes():
    pose = build_terminal_pose(theta_rad=0.0)
    shapes = []
    for row in _source_rows():
        if row.name.startswith(("P05_", "M05_", "M06_")):
            shapes.append((row.world, (0.72, 0.74, 0.78, 0.72)))
    shapes.extend((shape, (0.12, 0.62, 0.70, 1.0)) for shape in pose.camera_shapes.values())
    shapes.extend((shape, (0.86, 0.45, 0.10, 1.0)) for shape in pose.jaw_shapes.values())
    shapes.extend((shape, (0.42, 0.44, 0.48, 1.0)) for shape in envelope_hardware().values())
    return shapes


def run_demo(config_path: str | Path, output_directory: str | Path) -> Path:
    config_path = Path(config_path)
    output_directory = Path(output_directory)
    config = yaml.safe_load(config_path.read_text())
    backend = config["renderer"]["backend"]
    if os.environ.get("MUJOCO_GL") != backend:
        raise RuntimeError(f"MUJOCO_GL must explicitly equal configured backend {backend}")
    output_directory.mkdir(parents=True, exist_ok=False)
    shutil.copy2(config_path, output_directory / "simulation_calibration.yaml")

    board_values = dict(config["board"])
    board_values["tag_ids"] = tuple(board_values["tag_ids"])
    board = generate_aprilgrid(AprilGridSpec(**board_values), output_directory / "board")
    rendered = render_calibration_run(
        board_directory=board.output_directory,
        output_directory=output_directory / "rendered",
        width=int(config["renderer"]["width_px"]),
        height=int(config["renderer"]["height_px"]),
        fovy_degrees=float(config["renderer"]["fovy_degrees"]),
    )
    detections = detect_calibration_run(
        rendered.output_directory,
        output_directory / "detections",
    )
    calibration = calibrate_run(
        detections.json_path,
        rendered.truth_path,
        output_directory / "calibration",
    )
    integration_report = write_integration_report(output_directory / "integration")

    cad_directory = output_directory / "cad_views"
    cad_directory.mkdir()
    shapes = _cad_shapes()
    cad_view_paths = []
    size = (
        int(config["cad_views"]["width_px"]),
        int(config["cad_views"]["height_px"]),
    )
    for name, direction in config["cad_views"]["directions"].items():
        path = cad_directory / f"terminal_{name}.png"
        render(shapes, path, direction=direction, size=size)
        cad_view_paths.append(path)

    detection_payload = json.loads(detections.json_path.read_text())
    calibration_payload = json.loads(calibration.json_path.read_text())
    integration_payload = json.loads(integration_report.read_text())
    manifest = {
        "schema_version": 1,
        "config_source": str(config_path),
        "config_source_sha256": _sha256(config_path),
        "inputs": [
            {
                "path": relative_path,
                "sha256": _sha256(ROOT / relative_path),
                "size_bytes": (ROOT / relative_path).stat().st_size,
            }
            for relative_path in MANIFEST_INPUTS
        ],
        "render_backend": backend,
        "rendered_frame_count": len(rendered.frame_paths),
        "accepted_detection_frame_count": detection_payload["accepted_frame_count"],
        "rejected_frames": detection_payload["rejected_frames"],
        "cad_views": [str(path.relative_to(output_directory)) for path in cad_view_paths],
        "synthetic_validation_passed": calibration_payload["synthetic_validation_passed"],
        "p05_camera_invariant": integration_payload["p05_invariant"],
        "real_camera_calibration_approved": False,
        "fabrication_approved": False,
        "powered_operation_approved": False,
        "artifacts": _files(output_directory),
    }
    manifest_path = output_directory / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest_path


def verify_run(output_directory: str | Path) -> dict[str, Any]:
    output_directory = Path(output_directory)
    manifest_path = output_directory / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    sources = [item["path"] for item in manifest["inputs"]]
    artifacts = [item["path"] for item in manifest["artifacts"]]
    if len(sources) != len(set(sources)) or set(sources) != set(MANIFEST_INPUTS):
        raise ValueError("incomplete or duplicate input evidence")
    required = {
        "rendered/ground_truth.json",
        "detections/detections.json",
        "calibration/calibration_report.json",
        "integration/integration_report.json",
        "integration/camera_parentage.xml",
        "board/board.json",
    }
    if (
        len(artifacts) != len(set(artifacts))
        or not required <= set(artifacts)
        or set(artifacts) != {item["path"] for item in _files(output_directory)}
    ):
        raise ValueError("incomplete or duplicate artifact evidence")
    for relative in artifacts:
        path = (output_directory / relative).resolve()
        if not path.is_relative_to(output_directory.resolve()):
            raise ValueError("artifact path escapes run directory")
    for source in manifest["inputs"]:
        path = ROOT / source["path"]
        if not path.is_file() or _sha256(path) != source["sha256"]:
            raise ValueError(f"input SHA mismatch: {source['path']}")
    for artifact in manifest["artifacts"]:
        path = output_directory / artifact["path"]
        if not path.is_file() or _sha256(path) != artifact["sha256"]:
            raise ValueError(f"artifact SHA mismatch: {artifact['path']}")
    image_paths = [
        output_directory / artifact["path"]
        for artifact in manifest["artifacts"]
        if artifact["path"].endswith(".png")
    ]
    for path in image_paths:
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if image is None or float(image.std()) < 1.0:
            raise ValueError(f"blank image: {path}")
    if manifest["rejected_frames"]:
        raise ValueError("canonical E2E run contains rejected frames")
    if not manifest["synthetic_validation_passed"]:
        raise ValueError("synthetic calibration gates failed")
    truth = json.loads((output_directory / "rendered/ground_truth.json").read_text())
    detections = json.loads((output_directory / "detections/detections.json").read_text())
    calibration = json.loads((output_directory / "calibration/calibration_report.json").read_text())
    frames = truth["frames"]
    accepted = [f for f in detections["frames"] if f["accepted"]]
    if (
        len(frames) < 12
        or len(frames) != manifest["rendered_frame_count"]
        or len(accepted) != manifest["accepted_detection_frame_count"]
        or len(accepted) != len(frames)
        or len({f["rgb_sha256"] for f in frames}) != len(frames)
        or any(not f["assessment"]["accepted"] for f in frames)
        or any(f["tag_count"] < 2 or f["corner_count"] < 8 for f in accepted)
    ):
        raise ValueError("manifest counts/quality do not match actual frames")
    if any(f"rendered/{f['rgb_file']}" not in artifacts for f in frames):
        raise ValueError("missing rendered image evidence")
    limits = {
        "reprojection_rms_px": 0.5,
        "fx_relative_error": 0.01,
        "fy_relative_error": 0.01,
        "cx_absolute_error_px": 2.0,
        "cy_absolute_error_px": 2.0,
        "maximum_rotation_error_deg": 0.5,
        "maximum_translation_error_mm": 2.0,
    }
    if (
        not calibration["synthetic_validation_passed"]
        or calibration["failed_gates"]
        or any(
            not math.isfinite(calibration["metrics"][k])
            or not 0 <= calibration["metrics"][k] <= limit
            for k, limit in limits.items()
        )
    ):
        raise ValueError("calibration report does not meet numerical gates")
    if len(manifest["cad_views"]) != 4 or not set(manifest["cad_views"]) <= set(artifacts):
        raise ValueError("missing CAD view evidence")
    return {
        "artifact_count": len(manifest["artifacts"]),
        "rendered_frame_count": manifest["rendered_frame_count"],
        "accepted_detection_frame_count": manifest["accepted_detection_frame_count"],
        "cad_view_count": len(manifest["cad_views"]),
        "synthetic_validation_passed": manifest["synthetic_validation_passed"],
        "png_count": len(image_paths),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        print(json.dumps(verify_run(args.out), indent=2))
        return 0
    manifest = run_demo(args.config, args.out)
    print(json.dumps(verify_run(manifest.parent), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
