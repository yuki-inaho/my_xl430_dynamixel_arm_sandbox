"""Build a portable gallery from existing reviewed RGB-D records without recapture."""
import argparse
import html
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()
    root = args.dataset
    plan = json.loads((root / "plan.json").read_text())
    records = []
    cards = []
    for name in ["neutral", *[p["name"] for p in plan["poses"]], "neutral-final"]:
        folder = root / name
        meta = json.loads((folder / "metadata.json").read_text())
        pose = json.loads((folder / "pose.json").read_text())
        required = ["color.png", "depth.png", "aligned_depth.png", "ir_left.png",
                    "ir_right.png", "depth_preview.png", "calibration.toml"]
        if not all((folder / file).is_file() for file in required):
            raise RuntimeError(f"Incomplete RGB-D record: {name}")
        if name.startswith("pose_") and not pose.get("accepted"):
            raise RuntimeError(f"Unreviewed image: {name}")
        record = dict(name=name, metadata=meta, pose=pose,
                      relative_directory=name, files=required)
        records.append(record)
        text = html.escape(json.dumps(pose.get("delta_deg", [])))
        counts = html.escape(json.dumps(pose.get("positions", pose.get("reference_counts"))))
        cards.append(f'<article><h2>{name}</h2><p>指令差分°: {text}<br>'
                     f'実count: {counts}<br>{html.escape(meta["captured_at"])}</p>'
                     f'<a href="{name}/color.png"><img src="{name}/color.png" alt="{name} RGB"></a>'
                     f'<img src="{name}/depth_preview.png" alt="{name} aligned depth">'
                     f'<p><a href="{name}/metadata.json">カメラパラメータ</a> · '
                     f'<a href="{name}/depth.png">生uint16深度</a> · '
                     f'<a href="{name}/aligned_depth.png">整列深度</a> · '
                     f'<a href="{name}/pose.json">実測値と時刻</a></p></article>')
    manifest = dict(schema_version=1, accepted_pose_count=20,
                    neutral_count=2, source_plan="plan.json", records=records,
                    capture_camera="D435 external 1280x720 profiles @30fps",
                    mounted_camera="D405 USB disconnected",
                    quality="Fixed focus; low-light grain. No denoising of source PNG.",
                    physical_calibration=False, hardware_synchronized=False)
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    page = '''<!doctype html><html lang="ja"><meta charset="utf-8">
<title>D405付きアーム RGB-D 20姿勢</title><style>
body{font-family:sans-serif;margin:24px;background:#edf1f4;color:#15252f}
main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}
article{background:white;padding:18px;border-radius:12px}img{width:100%}a{color:#125d85}
@media(max-width:800px){main{grid-template-columns:1fr}}</style>
<h1>D405付きアーム：待機姿勢＋20姿勢</h1>
<p>台座5方向 × 肘4段階。ID2/ID4/ID5は保持。角度は指令差分、精密なCAD角ではありません。</p>
<p>外部D435でRGB-D 1280×720、SDK profile 30fps。アームのD405はUSB未接続。</p>
<p>各姿勢2.5秒静止後、原画像を個別確認。固定焦点ですが低照度ノイズがあります。
RGB-Dとencoderは別取得で、取得前後のREAD時刻を保存。画像クリックで原寸表示。</p>
<p>手首−5°は追従未達で停止し、候補を変更。採用20姿勢に混ぜていません。
終了時は待機姿勢へ戻し、全5台Torque OFF、PWM/速度/加速度復元を実READで確認。</p>
<p><a href="SHOOTING_TABLE.md">撮影表</a> · <a href="manifest.json">全記録</a></p><main>'''
    (root / "index.html").write_text(page + "".join(cards) + "</main></html>")
    print(json.dumps(dict(dataset=str(root), reviewed_poses=20, neutrals=2)))


if __name__ == "__main__":
    main()
