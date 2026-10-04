"""Build a portable evidence gallery from actual camera receipts and motion journals."""

import html
import json
import shutil
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "diary/2026-10-04/gripper-mounted-review"
DATA = Path.home() / "data/xl430-arm/2026-10-04/gripper-open-close"


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def copy_capture(camera, source):
    source = Path(source)
    target = REPORT / "captures" / camera / source.name
    shutil.copytree(source, target, dirs_exist_ok=True)
    return target.relative_to(REPORT)


def depth_roi(relative, camera, *, changed_view=False):
    path = REPORT / relative
    metadata = json.loads((path / "metadata.json").read_text())
    depth = cv2.imread(str(path / "aligned_depth.png"), cv2.IMREAD_UNCHANGED)
    if depth.dtype != np.uint16 or depth.shape != (720, 1280):
        raise ValueError("Expected untouched 1280x720 Z16 aligned depth")
    rect = (600, 105, 785, 305) if camera == "d435" else (545, 295, 895, 685)
    x0, y0, x1, y1 = rect
    roi = depth[y0:y1, x0:x1]
    valid = roi[roi > 0].astype(float) * metadata["depth_scale_m_per_count"]
    scale = metadata["depth_scale_m_per_count"]
    near = cv2.applyColorMap(
        np.clip(depth.astype(float) * scale / 0.2 * 255, 0, 255).astype(np.uint8),
        cv2.COLORMAP_TURBO,
    )
    near[depth == 0] = 0
    cv2.imwrite(str(path / "depth_near_0_200mm.png"), near)
    if changed_view:
        return dict(rect_xyxy=None, note="Camera moved; original target ROI is not applicable")
    return dict(
        rect_xyxy=rect,
        rectangle_not_segmentation=True,
        nonzero_fraction=float(np.count_nonzero(roi) / roi.size),
        p10_p50_p90_m=np.quantile(valid, [0.1, 0.5, 0.9]).tolist() if valid.size else None,
        depth_scale_m_per_count=scale,
        note="Foreground/background mixed; not metrology or exact tip distance",
    )


def journals():
    summaries = []
    for name in (
        "open-close-run",
        "open-close-retry",
        "open-close-photo-output",
        "open-close-final",
        "open-close-return",
    ):
        events = [
            json.loads(line) for line in (REPORT / name / "motion.jsonl").read_text().splitlines()
        ]
        samples = [e for e in events if e["kind"] == "sample"]
        motors = [[m for m in e["motors"] if m["motor_id"] == 5][0] for e in samples]
        start = events[0]["start"]["positions"]
        writes = [e for e in events if e["kind"] == "write"]
        status = (
            "closed/returned/released"
            if name == "open-close-return"
            else "candidate stopped; see actual positions"
        )
        summaries.append(
            dict(
                run=name,
                status=status,
                id5_min_max_counts=[
                    min(m["position_counts"] for m in motors),
                    max(m["position_counts"] for m in motors),
                ],
                max_abs_pwm=max(abs(m["pwm_raw"]) for m in motors),
                max_abs_load=max(abs(m["load_raw"]) for m in motors),
                other_axis_max_change=max(
                    abs(m["position_counts"] - start[m["motor_id"] - 1])
                    for e in samples
                    for m in e["motors"]
                    if m["motor_id"] != 5
                ),
                write_ids=sorted({e["motor_id"] for e in writes}),
                final_release=next(e for e in reversed(events) if e["kind"] == "released"),
            )
        )
    return summaries


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    mounting = Path.home() / "Downloads/ChatGPT 画像 2026年10月4日 23_03_07.jpg"
    shutil.copy2(mounting, REPORT / "photos/motor-mount.jpg")
    pre405 = Path.home() / "data/xl430-arm/2026-10-04/gripper-mounted-review/d405"
    shutil.copytree(pre405, REPORT / "d405", dirs_exist_ok=True)
    rows = []
    sources = []
    labels = {
        "closed": "初期閉",
        "open10": "小開",
        "open20": "中開",
        "open-observed": "観測最大開",
        "reclosed": "再閉・指サック接触",
    }
    for state, label in labels.items():
        receipt = json.loads((DATA / f"states/{state}.json").read_text())
        counts = [
            next(m for m in v["before"]["motors"] if m["motor_id"] == 5)["position_counts"]
            for v in receipt["captures"].values()
        ]
        sources.append(
            (
                f"{label} — 実測ID5 {counts} count",
                {k: v["path"] for k, v in receipt["captures"].items()},
                state,
            )
        )
    sources.extend(
        [
            (
                "初回停止・ID5 OFF 2105 count",
                json.loads((REPORT / "first-stop-captures.json").read_text()),
                "first-stop",
            ),
            (
                "再試行停止・ID5 OFF（後続READ 2109 count）",
                json.loads((REPORT / "retry-stop-captures.json").read_text()),
                "retry-stop",
            ),
        ]
    )
    end_view = REPORT / "end-view-captures.json"
    if end_view.exists():
        sources.append(
            (
                "ユーザーのカメラ微調整後・現在の閉状態（ID5 OFF）",
                json.loads(end_view.read_text())["captures"],
                "end-view",
            )
        )
    depth = {}
    for title, captures, state in sources:
        cells = []
        depth[state] = {}
        for camera, source in captures.items():
            relative = copy_capture(camera, source)
            depth[state][camera] = depth_roi(relative, camera, changed_view=state == "end-view")
            cells.append(
                f'<article><h3>{camera.upper()}</h3><a href="{relative}/color.png">'
                f'<img src="{relative}/color.png" alt="{html.escape(title)} {camera} RGB"></a>'
                f'<p><a href="{relative}/metadata.json">実時刻・K・歪み・深度scale</a> / '
                f'<a href="{relative}/aligned_depth.png">Z16深度</a></p>'
                f'<img src="{relative}/depth_near_0_200mm.png" alt="0–200 mm depth visualization">'
                "<p>深度表示0–200 mm、200 mm超は同じ端色。黒は欠損。</p></article>"
            )
        rows.append(
            f'<section><h2>{title}</h2><div class="grid">' + "".join(cells) + "</div></section>"
        )
    lighting = REPORT / "lights-dim-reference.json"
    if lighting.exists():
        captures = json.loads(lighting.read_text())["captures"]
        cells = []
        for camera, receipt in captures.items():
            relative = receipt["relative"]
            cells.append(
                f'<article><h3>{camera.upper()}</h3><img src="{relative}/color.png" '
                f'alt="消灯報告後の参考視野 {camera}"><p>'
                f'<a href="{relative}/metadata.json">撮影時刻・パラメータ</a> / '
                f'<a href="{relative}/aligned_depth.png">原深度</a></p></article>'
            )
        rows.append(
            "<section><h2>消灯報告後の参考視野 — 23:47:43/44</h2>"
            "<p>追加motor指令なし。D435は指先上端が画面外・暗所ノイズが増加。"
            "D405は指先が見えるが逆光。開閉の証拠は変更前の5状態を使う。"
            '旧矩形ROI・camera poseを新視点の測定には使わない。</p><div class="grid">'
            + "".join(cells)
            + "</div></section>"
        )
    summaries = journals()
    write_json(REPORT / "motion-summary.json", summaries)
    write_json(REPORT / "depth-roi-review.json", depth)
    shutil.copytree(DATA / "states", REPORT / "states", dirs_exist_ok=True)
    table = "".join(
        f"<tr><td>{r['run']}</td><td>{r['id5_min_max_counts']}</td>"
        f"<td>{r['max_abs_pwm']}</td><td>{r['max_abs_load']}</td>"
        f"<td>{r['other_axis_max_change']}</td></tr>"
        for r in summaries
    )
    page = """<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ID5 グリッパ実機確認</title>
<style>body{font-family:system-ui,sans-serif;background:#f3f5f7;color:#182433;margin:0;padding:20px;
max-width:1320px;margin:auto;overflow-wrap:anywhere}h1{font-size:28px}
section,article{min-width:0}section{margin:28px 0}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}img{width:100%;height:auto}
article{background:white;padding:12px}a{overflow-wrap:anywhere;color:#1356a2}p{line-height:1.7}
.warning{padding:18px;background:#fff1d8;border-left:5px solid #a36509}pre{white-space:pre-wrap;
overflow-wrap:anywhere}.table-scroll{max-width:100%;overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:8px;
border:1px solid #ccd2da}@media(max-width:680px){.grid{grid-template-columns:1fr}body{padding:12px}}
</style><h1>ID5 グリッパの実機確認 — 2026-10-04</h1>
<p class="warning"><strong>実機の開→閉と二眼撮影を確認。</strong>閉2067、小開2173、中開2281、
観測開2486（閉基準から約36.83°）、再閉2091 count。再閉では指サック接触を画像確認。
40°指令の厳密到達は未達で、初期closed countへも24count残差があります。
指令値を達成角度と呼びません。最終全台OFF、ID5 RAM復元済み。</p>
<p>D435俯瞰・D405ハンドアイともRGB/depth/IR 1280×720、設定30fps。
同時使用時の取得は約17–19Hz、二眼は逐次host時刻で取得しhardware同期ではありません。
D435は暗所ノイズあり、D405は逆光で黒い部材が暗いもののsofttip・間隔は識別可能。
近接の深度欠損率は<a href="depth-roi-review.json">矩形ROI記録</a>を参照。</p>
<p>開閉撮影後にユーザーがカメラを微調整。末尾の現在状態だけ新しい視点。
旧viewにfitした外部camera pose/seedは次回自動流用しません。</p>
<p><a href="../../../docs/GRIPPER_ID5_CONSTRAINTS.md">ID5制約仕様</a> /
<a href="../workdocs/workdoc_Oct04-2026_gripper_open_close.md">作業書</a> /
<a href="motion-summary.json">独立集計</a> /
<a href="final-closed-read/FINAL_PLACEHOLDER">最終READ</a> /
<a href="../diverse-recognition/REPORT.html">先行20姿勢認識レビュー</a></p>
<h2>実測停止ログ</h2><div class="table-scroll"><table><tr><th>Run</th>
<th>ID5 count範囲</th><th>max PWM raw</th>
<th>max推定Load raw</th><th>他軸変化count</th></tr>TABLE_PLACEHOLDER</table></div>
<p>PWM150→250では初動停滞。写真pairをユーザー確認後、写真実測のPWM35.03%相当310で開動作を観測。
開20°は14count残差、開40°は35count残差で停止。閉位置の画像確認まで監督して実行。
推定Loadは力の測定値ではありません。
全WRITEはID5だけ。両runともOFFと元PWM885/PA0/PV0のREAD一致を確認。
最終独立READでは全5台OFF、他軸の差1–2countで15count guard内、ID5 2091 stable、error0。</p>
ROWS_PLACEHOLDER
<section><h2>提供資料とモデルの範囲</h2>
<p>写真pairはユーザーの明示確認で181.41°閉、239.50°開（差58.09°）。
したがって正countが開く方向。掲載順だけで確定した初稿の根拠は訂正しました。
機械限界／比例した開口幅ではありません。
取付写真は駆動軸面の配置の根拠であり、クランク位相の確定には使いません。</p>
<img src="photos/motor-mount.jpg" alt="ユーザー提供のモーター取り付け向き">
<p>scanfit ZIP SHA256 76d72f6a7af0d9bfab11a3c1ad6e02c246b6aeb5d0d0eff5a7f4f0761a8d7238。
CRCと96件のMANIFEST一致。softtip外形6部品、STEP/STL mm Zup、GLB m Yup。
C92 donorのframe/cap hash一致は現物爪C9の証明ではありません。
指サックは中実の外形占有モデルで弾性・中空・圧縮を表現しません。</p>
<p><a href="independent-step-check.json">STEP再import6件</a> /
<a href="independent-mesh-check.json">STL/GLB独立検査</a> /
<a href="scanfit/results/report_ja.md">元fitレポート</a> /
<a href="input-manifest.json">入力manifest</a></p>
<p>cot p95約0.91/0.96mm、foam p95約1.95/2.79mm、右foam最大約4.38mm。
ねじの4点XY fit residual約0.12mmは同じfit点の残差であり独立精度ではありません。
現行arm perceptionモデルは爪を含まないため今回のgripper形状・開閉認識の検証には未対応。
</p></section></html>"""
    final = next((REPORT / "final-closed-read").glob("*.md")).name
    page = (
        page.replace("FINAL_PLACEHOLDER", final)
        .replace("TABLE_PLACEHOLDER", table)
        .replace("ROWS_PLACEHOLDER", "".join(rows))
    )
    (REPORT / "REPORT.html").write_text(page)
    print(
        json.dumps(
            dict(
                report=str(REPORT / "REPORT.html"),
                states=len(sources),
                lighting_reference_pairs=int(lighting.exists()),
                camera_captures=(len(sources) + int(lighting.exists())) * 2,
            )
        )
    )


if __name__ == "__main__":
    main()
