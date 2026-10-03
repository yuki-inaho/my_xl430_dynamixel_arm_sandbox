"""Package the accepted mixed-servo follower revision for OrcaSlicer.

The geometry revision is intentionally separate from the older XL430-only
study.  The shared slicer implementation is reused, but this file owns the
seven-part allow-list and the revision-specific exclusion record.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parent
SHARED_DIR = STUDY_DIR.parent / "xl430_lowcost"
sys.path.insert(0, str(SHARED_DIR))

from prepare_print_package import (  # noqa: E402
    _copy_pair,
    _slice,
)

DEFAULT_PARTS = (
    "base_idler_clearance",
    "elbow_to_wrist_extension_round",
    "elbow_to_wrist_standoff",
    "shoulder_rotation_unchanged",
    "shoulder_to_elbow_unchanged",
    "gripper_static_unchanged",
    "gripper_moving_unchanged",
)

EXCLUDED_DESIGNS = {
    "elbow_to_wrist_xl430": (
        "2026-09-18 geometry review blocked this model: the outside rounded "
        "profile was incorrectly treated as a bore, so it is not promoted here."
    ),
}


def _write_readme(output_dir: Path, manifest: dict) -> None:
    lines = [
        "# フォロワーアーム幾何改訂 印刷パッケージ",
        "",
        "2026-09-19の混在サーボ構成向け幾何改訂から、検査済みSTEP/STLを",
        "Creality K1C用に整理し、OrcaSlicerでスライスしたパッケージです。",
        "",
        "## 先に確認すること",
        "",
        "- 7部品のSTEP再読込、単一ソリッド、閉じたSTLを検査済みです。",
        "- 基準姿勢での部品間干渉と取付穴軸を検査済みです。",
        "- Dynamixelへの組付け、ねじ、強度、耐久性、全角度の干渉は未検証です。",
        "- 実機の嵌合試験片、物理印刷結果、組立確認済み部品は含みません。",
        "- この改訂は全関節XL430化ではなく、XL430 2台とXL330系4台の混在構成です。",
        "",
        "## 内容",
        "",
        "| 場所 | 内容 |",
        "|---|---|",
        "| `STEP/` | 検査済み7部品のSTEP |",
        "| `STL/` | OrcaSlicerへ渡した7部品のSTL |",
        "| `GCODE/follower_revision_parts_PLA_plate_N.gcode` | プレートごとのG-code |",
        "| `GCODE/gcode_validation.json` | Orca結果・部品数・警告・G-code検査 |",
        "| `validation/manifest.json` | 入力ハッシュ、寸法、除外理由 |",
        "| `slicer/profiles/` | 使用プロファイルのスナップショット |",
        "",
        "## スライス設定",
        "",
        "- プリンタ: Creality K1C / 0.4 mm nozzle",
        "- レイヤー: 0.20 mm Standard",
        "- フィラメント: CR-PLA @K1C",
        "- 壁: 3周",
        "- サポート: 有効",
        "- `M191`: なし（チャンバー温度待ちを無効化）",
        "",
        "## 未収録",
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
    orca: Path,
    support_enabled: bool = True,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(output_dir / "GCODE", ignore_errors=True)
    shutil.rmtree(output_dir / "slicer", ignore_errors=True)
    parts = [_copy_pair(source_dir, output_dir, name) for name in DEFAULT_PARTS]
    gcode_report = _slice(
        output_dir,
        list(DEFAULT_PARTS),
        orca,
        machine_profile=None,
        process_profile=None,
        filament_profile=None,
        wall_loops=3,
        support_enabled=support_enabled,
        gcode_prefix="follower_revision_parts_PLA",
        allow_multiple_plates=True,
    )

    manifest = {
        "schema": "follower-geometry-print-package/v1",
        "source_dir": str(source_dir),
        "revision": "follower_geometry_revision_20260919",
        "printer": {
            "model": "Creality K1C",
            "nozzle_mm": 0.4,
            "layer_height_mm": 0.20,
            "material": "PLA",
            "wall_loops": 3,
            "support_enabled": support_enabled,
        },
        "parts": parts,
        "excluded_designs": dict(EXCLUDED_DESIGNS),
        "gcode": gcode_report,
    }
    validation_dir = output_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    (validation_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_readme(output_dir, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=STUDY_DIR.parent.parent
        / "outputs/follower_geometry_revision/CAD/parts",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STUDY_DIR.parent.parent / "outputs/follower_print_package",
    )
    parser.add_argument(
        "--orca",
        type=Path,
        default=Path.home() / "Applications/OrcaSlicer.AppImage",
    )
    args = parser.parse_args(argv)
    try:
        manifest = prepare(args.source_dir, args.output_dir, args.orca)
    except (FileNotFoundError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
