"""Organize validated CAD artifacts and optionally produce printer G-code.

The input directory is expected to contain the STEP/STL pair selected by the
CAD/mesh gates.  This command deliberately has an explicit allow-list: a file
that merely exists under an old generated-output directory is not promoted to
an accepted print artifact.

Example::

    rtk uv run python studies/xl430_lowcost/prepare_print_package.py \
        --source-dir outputs/print \
        --output-dir outputs/xl430_print_package \
        --slice \
        --orca ~/Applications/OrcaSlicer.AppImage
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable

import numpy as np
import trimesh


DEFAULT_PARTS = (
    "shoulder_rotation_orig",
    "shoulder_to_elbow_xl430",
    "elbow_to_wrist_extension_xl430",
    "gripper_static_part_xl430",
    "gripper_moving_part_xl430_print",
)

EXCLUDED_DESIGNS = {
    "elbow_to_wrist_xl430": (
        "2026-09-18 geometry review blocked this model: an outside rounded "
        "profile was interpreted as a bore, so the existing generated mesh is stale."
    ),
}

_OBJECT_RE = re.compile(r"^EXCLUDE_OBJECT_DEFINE NAME=(\S+)", re.MULTILINE)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _edge_anomalies(mesh: trimesh.Trimesh) -> int:
    _, counts = np.unique(mesh.edges_sorted, axis=0, return_counts=True)
    return int(np.count_nonzero(counts != 2))


def mesh_report(path: Path) -> dict:
    """Return the slicer-facing topology and size checks for one STL."""
    mesh = trimesh.load(path, force="mesh")
    return {
        "file": str(path),
        "sha256": _sha256(path),
        "watertight": bool(mesh.is_watertight),
        "is_volume": bool(mesh.is_volume),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "nonmanifold_or_boundary_edges": _edge_anomalies(mesh),
        "triangles": int(len(mesh.faces)),
        "bbox_mm": [round(float(value), 3) for value in mesh.bounding_box.extents],
        "min_z_mm": round(float(mesh.bounds[0][2]), 3),
        "max_z_mm": round(float(mesh.bounds[1][2]), 3),
        "volume_mm3": round(float(mesh.volume), 3) if mesh.is_volume else None,
    }


def _print_ready(report: dict) -> bool:
    return bool(
        report["watertight"]
        and report["is_volume"]
        and report["winding_consistent"]
        and report["nonmanifold_or_boundary_edges"] == 0
    )


def _copy_pair(source_dir: Path, output_dir: Path, name: str) -> dict:
    step_src = source_dir / f"{name}.step"
    stl_src = source_dir / f"{name}.stl"
    missing = [str(path) for path in (step_src, stl_src) if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"missing STEP/STL pair for {name}: {', '.join(missing)}"
        )

    step_dst = output_dir / "STEP" / step_src.name
    stl_dst = output_dir / "STL" / stl_src.name
    step_dst.parent.mkdir(parents=True, exist_ok=True)
    stl_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(step_src, step_dst)
    shutil.copy2(stl_src, stl_dst)
    report = mesh_report(stl_dst)
    if not _print_ready(report):
        raise ValueError(f"STL failed print-readiness gate: {stl_src}")
    return {
        "name": name,
        "step": str(step_dst.relative_to(output_dir)),
        "stl": str(stl_dst.relative_to(output_dir)),
        "mesh": report,
    }


def _find_profile(root: Path, relative: str) -> Path:
    path = root / "resources" / "profiles" / relative
    if not path.is_file():
        raise FileNotFoundError(f"OrcaSlicer profile not found: {path}")
    return path


def _write_profile(src: Path, dst: Path, updates: dict[str, object]) -> Path:
    data = json.loads(src.read_text(encoding="utf-8"))
    data.update(updates)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return dst


def _resolve_orca(app: Path, extraction_dir: Path) -> Path:
    if app.name.endswith(".AppImage"):
        result = subprocess.run(
            [str(app), "--appimage-extract"],
            cwd=extraction_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"AppImage extraction failed: {result.stderr[-1000:]}")
        app_run = extraction_dir / "squashfs-root" / "AppRun"
        if not app_run.is_file():
            raise FileNotFoundError(f"AppRun missing after extraction: {app_run}")
        return app_run
    if not app.is_file():
        raise FileNotFoundError(f"OrcaSlicer executable not found: {app}")
    return app


def _validate_gcode(gcode: Path, result_json: Path, names: Iterable[str]) -> dict:
    text = gcode.read_text(encoding="utf-8", errors="replace")
    result = json.loads(result_json.read_text(encoding="utf-8"))
    expected = list(names)
    object_lines = _OBJECT_RE.findall(text)
    warning_messages = [
        plate.get("warning_message", "")
        for plate in result.get("sliced_plates", [])
        if plate.get("warning_message")
    ]
    object_hits = {
        name: [line for line in object_lines if f"{name}.stl" in line]
        for name in expected
    }
    report = {
        "gcode": str(gcode),
        "result": result,
        "expected_objects": expected,
        "object_definition_lines": object_lines,
        "object_hits": object_hits,
        "warning_messages": warning_messages,
        "m191_count": len(re.findall(r"^M191\b", text, re.IGNORECASE | re.MULTILINE)),
        "has_start_print": "START_PRINT" in text,
        "has_end_print": "END_PRINT" in text,
        "layer_count": _first_comment_value(text, r"total layer number: (.+)"),
        "estimated_time": _first_comment_value(
            text, r"estimated printing time \(normal mode\) = (.+)"
        ),
        "filament_used_cm3": _first_comment_value(
            text, r"filament used \[cm3\] = (.+)"
        ),
    }
    report["passed"] = bool(
        result.get("return_code") == 0
        and str(result.get("error_string", "")).lower() == "success."
        and len(object_lines) == len(expected)
        and all(object_hits.values())
        and not warning_messages
        and report["m191_count"] == 0
        and report["has_start_print"]
        and report["has_end_print"]
    )
    return report


def _first_comment_value(text: str, pattern: str) -> str | None:
    match = re.search(rf"^; {pattern}$", text, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else None


def _slice(
    output_dir: Path,
    names: list[str],
    orca: Path,
    machine_profile: Path | None,
    process_profile: Path | None,
    filament_profile: Path | None,
    wall_loops: int,
    support_enabled: bool,
    gcode_prefix: str = "xl430_arm_parts_PLA",
    allow_multiple_plates: bool = False,
) -> dict:
    if shutil.which("xvfb-run") is None:
        raise RuntimeError("xvfb-run is required for headless OrcaSlicer execution")

    profiles_dir = output_dir / "slicer" / "profiles"
    profile_root = profiles_dir / "source"
    with tempfile.TemporaryDirectory(prefix="cadre-orca-") as tmp:
        extraction_dir = Path(tmp) / "orca"
        extraction_dir.mkdir()
        app_run = _resolve_orca(orca, extraction_dir)
        root = app_run.parent
        profile_machine = machine_profile or _find_profile(
            root, "Creality/machine/Creality K1C 0.4 nozzle.json"
        )
        profile_process = process_profile or _find_profile(
            root, "Creality/process/0.20mm Standard @Creality K1C 0.4 nozzle.json"
        )
        profile_filament = filament_profile or _find_profile(
            root, "Creality/filament/CR-PLA @K1C-all.json"
        )
        machine_dst = profile_root / "machine.json"
        process_dst = _write_profile(
            profile_process,
            profiles_dir / "process_020_k1c.json",
            {
                "wall_loops": str(wall_loops),
                "enable_support": "1" if support_enabled else "0",
            },
        )
        filament_dst = _write_profile(
            profile_filament,
            profiles_dir / "filament_pla_k1c.json",
            # The K1C profile otherwise emits M191/35 C, which is not a safe
            # assumption for a printer without a chamber-temperature macro.
            {"chamber_temperature": "0"},
        )
        machine_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(profile_machine, machine_dst)
        (profiles_dir / "source_manifest.json").write_text(
            json.dumps(
                {
                    "machine_source": str(profile_machine),
                    "process_source": str(profile_process),
                    "filament_source": str(profile_filament),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        slice_input = output_dir / "STL"
        temp_output = Path(tmp) / "slice-output"
        temp_output.mkdir()
        command = [
            "xvfb-run",
            "-a",
            str(app_run),
            "--load-settings",
            f"{machine_dst};{process_dst}",
            "--load-filaments",
            str(filament_dst),
            "--arrange",
            "1",
            "--slice",
            "0",
            "--outputdir",
            str(temp_output),
            *[str(slice_input / f"{name}.stl") for name in names],
        ]
        log_path = output_dir / "slicer" / "orcaslicer.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        log_path.write_text(
            "COMMAND:\n"
            + " ".join(command)
            + "\n\nSTDOUT:\n"
            + result.stdout
            + "\nSTDERR:\n"
            + result.stderr,
            encoding="utf-8",
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"OrcaSlicer failed ({result.returncode}); see {log_path}"
            )

        result_src = temp_output / "result.json"
        gcode_sources = sorted(temp_output.glob("plate_*.gcode"))
        if not gcode_sources or not result_src.is_file():
            raise FileNotFoundError(
                "OrcaSlicer did not produce plate_N.gcode/result.json"
            )
        gcode_dir = output_dir / "GCODE"
        gcode_dir.mkdir(parents=True, exist_ok=True)
        result_dst = gcode_dir / "orcaslicer_result.json"
        shutil.copy2(result_src, result_dst)
        if not allow_multiple_plates and len(gcode_sources) != 1:
            raise RuntimeError(
                f"OrcaSlicer produced {len(gcode_sources)} plates; "
                "rerun with multi-plate packaging enabled"
            )

        if len(gcode_sources) == 1:
            gcode_dst = gcode_dir / f"{gcode_prefix}.gcode"
            shutil.copy2(gcode_sources[0], gcode_dst)
            report = _validate_gcode(gcode_dst, result_dst, names)
        else:
            plate_reports = []
            seen_names = []
            for gcode_src in gcode_sources:
                plate_index = gcode_src.stem.removeprefix("plate_")
                gcode_dst = gcode_dir / f"{gcode_prefix}_plate_{plate_index}.gcode"
                shutil.copy2(gcode_src, gcode_dst)
                text = gcode_src.read_text(encoding="utf-8", errors="replace")
                plate_names = [name for name in names if f"{name}.stl" in text]
                if not plate_names:
                    raise RuntimeError(f"no expected part found in {gcode_src.name}")
                seen_names.extend(plate_names)
                plate_report = _validate_gcode(gcode_dst, result_dst, plate_names)
                plate_report["plate_index"] = int(plate_index)
                plate_reports.append(plate_report)
            report = {
                "gcode": [
                    str(
                        gcode_dir
                        / f"{gcode_prefix}_plate_{source.stem.removeprefix('plate_')}.gcode"
                    )
                    for source in gcode_sources
                ],
                "result": json.loads(result_dst.read_text(encoding="utf-8")),
                "expected_objects": list(names),
                "plates": plate_reports,
                "plate_count": len(plate_reports),
                "passed": sorted(seen_names) == sorted(names)
                and all(plate["passed"] for plate in plate_reports),
            }
        (gcode_dir / "gcode_validation.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        if not report["passed"]:
            raise RuntimeError(
                f"G-code validation failed; see {gcode_dir / 'gcode_validation.json'}"
            )
        return report


def _write_readme(output_dir: Path, manifest: dict) -> None:
    lines = [
        "# XL430 arm parts print package",
        "",
        "このディレクトリは、CAD検査を通過したSTEP/STLと、Creality K1C向けに",
        "OrcaSlicerで生成したG-codeを分離して保存した印刷パッケージです。",
        "",
        "## 先に確認すること",
        "",
        "- このG-codeは形状のメッシュ検査とスライサー出力検査を通過したものです。",
        "- Dynamixel本体への組付け、ねじ、可動域、干渉、強度、耐久性は未検証です。",
        "- まず一部品または薄い端部を少量印刷し、実機との嵌合を確認してください。",
        "- 実機の嵌合試験片、物理印刷結果、組立確認済みの部品はこのパッケージに含まれていません。",
        "- `elbow_to_wrist_xl430` は設計レビューで未承認のため、このパッケージには含めていません。",
        "",
        "## 内容",
        "",
        "| 場所 | 内容 |",
        "|---|---|",
        "| `STEP/` | 採用した部品のSTEP |",
        "| `STL/` | OrcaSlicerへ渡したSTL |",
        "| `GCODE/xl430_arm_parts_PLA.gcode` | 1プレートに全採用部品を配置したG-code |",
        "| `GCODE/gcode_validation.json` | 部品数、M191、開始/終了マクロ、Orca結果の検証 |",
        "| `validation/manifest.json` | 入力ハッシュ、寸法、mesh判定、除外理由 |",
        "| `slicer/profiles/` | スライスに使ったプロファイルのスナップショット |",
        "",
        "## 設定",
        "",
        "- プリンタ: Creality K1C / 0.4 mm nozzle",
        "- レイヤー: 0.20 mm Standard",
        "- フィラメント: CR-PLA @K1C",
        "- 壁: 3周",
        f"- サポート: {'有効' if manifest['printer']['support_enabled'] else '無効'}（OrcaSlicerプロファイルで固定）",
        "- チャンバー待ち: 0。出力G-codeに`M191`がないことを検証済み",
        "",
        "## 未収録の成果物",
        "",
        "| 名前 | 理由 |",
        "|---|---|",
        *[
            f"| `{name}` | {reason} |"
            for name, reason in manifest["excluded_designs"].items()
        ],
        "",
    ]
    (output_dir / "README_ja.md").write_text("\n".join(lines), encoding="utf-8")


def prepare(
    source_dir: Path,
    output_dir: Path,
    names: Iterable[str] = DEFAULT_PARTS,
    slice_enabled: bool = False,
    orca: Path | None = None,
    machine_profile: Path | None = None,
    process_profile: Path | None = None,
    filament_profile: Path | None = None,
    wall_loops: int = 3,
    support_enabled: bool = False,
) -> dict:
    names = list(names)
    unknown = sorted(set(names) - set(DEFAULT_PARTS))
    if unknown:
        raise ValueError(f"part is not in the print allow-list: {', '.join(unknown)}")
    output_dir.mkdir(parents=True, exist_ok=True)
    parts = [_copy_pair(source_dir, output_dir, name) for name in names]
    manifest = {
        "schema": "xl430-print-package/v1",
        "source_dir": str(source_dir),
        "printer": {
            "model": "Creality K1C",
            "nozzle_mm": 0.4,
            "layer_height_mm": 0.20,
            "material": "PLA",
            "wall_loops": wall_loops,
            "support_enabled": support_enabled,
        },
        "parts": parts,
        "excluded_designs": dict(EXCLUDED_DESIGNS),
        "gcode": None,
    }
    validation_dir = output_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    source_report = source_dir / "print_readiness_report.json"
    if source_report.is_file():
        shutil.copy2(source_report, validation_dir / source_report.name)

    if slice_enabled:
        if orca is None:
            raise ValueError("--orca is required with --slice")
        manifest["gcode"] = _slice(
            output_dir,
            names,
            orca,
            machine_profile,
            process_profile,
            filament_profile,
            wall_loops,
            support_enabled,
        )
    manifest_path = validation_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _write_readme(output_dir, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--part", action="append", dest="parts")
    parser.add_argument("--slice", action="store_true")
    parser.add_argument(
        "--orca", type=Path, default=Path.home() / "Applications/OrcaSlicer.AppImage"
    )
    parser.add_argument("--machine-profile", type=Path)
    parser.add_argument("--process-profile", type=Path)
    parser.add_argument("--filament-profile", type=Path)
    parser.add_argument("--wall-loops", type=int, default=3)
    parser.add_argument("--enable-support", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = prepare(
            args.source_dir,
            args.output_dir,
            args.parts or DEFAULT_PARTS,
            args.slice,
            args.orca,
            args.machine_profile,
            args.process_profile,
            args.filament_profile,
            args.wall_loops,
            args.enable_support,
        )
    except (FileNotFoundError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
