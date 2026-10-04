"""Compare image-only estimates with held encoder deltas and export a portable report."""

import argparse
import hashlib
import html
import json
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np


def read_record(path):
    return json.loads((path/'pose.json').read_text())


def infer_signs(records, baseline):
    # Separate these observations from the validation set. This resolves only
    # relative sign convention, never absolute angles or a motor calibration.
    pairs = [('pose_06', 'pose_07'), ('pose_05', 'pose_06'), ('neutral', 'pose_01')]
    signs, evidence = [], []
    for axis, (first, second) in enumerate(pairs):
        a, b = records[first], records[second]
        ca = baseline if first == 'neutral' else np.array(a['after']['positions'])
        cb = np.array(b['after']['positions'])
        count_deg = (cb[axis]-ca[axis])*360/4096
        image_deg = (b['vision']['pose']['joint_angles_deg'][axis]
                     - a['vision']['pose']['joint_angles_deg'][axis])
        if abs(count_deg) < 1 or abs(image_deg) < .5:
            raise ValueError(f'Insufficient sign observation for axis {axis+1}')
        signs.append(int(np.sign(count_deg*image_deg)))
        evidence.append(dict(axis=axis+1, first=first, second=second,
                             encoder_delta_deg=count_deg, image_delta_deg=image_deg,
                             sign=signs[-1]))
    return np.array(signs), evidence, {n for pair in pairs for n in pair}


def evaluate(paths, neutral, baseline):
    records = {p.name: read_record(p) for p in paths}
    records['neutral'] = read_record(neutral)
    signs, sign_evidence, calibration_names = infer_signs(records, baseline)
    zero = np.array(records['neutral']['vision']['pose']['joint_angles_deg'])
    results: list[dict] = []  # JSON serialization boundary; each row validated above/below.
    for path in paths:
        r = records[path.name]
        actual = (np.array(r['after']['positions'])-baseline)*360/4096
        image = np.array(r['vision']['pose']['joint_angles_deg'])-zero
        frame_time = datetime.fromisoformat(r['vision']['metadata']['host_received_at']).timestamp()
        bracket = [datetime.fromisoformat(r[k]['at']).timestamp() for k in ('before', 'after')]
        if not bracket[0] <= frame_time <= bracket[1]:
            raise ValueError(f'{path}: frame is not bracketed by encoder samples')
        if r['vision']['status'] != 'tracking' or r['vision']['pose'] is None:
            raise ValueError(f'{path}: missing published estimate')
        results.append(dict(
            name=path.name, source=str(path), commanded_deg=r['ready']['delta_deg'],
            actual_encoder_delta_deg=actual.tolist(), image_delta_deg=image.tolist(),
            error_deg=(image[:3]-signs*actual[:3]).tolist(),
            sign_calibration_observation=path.name in calibration_names,
            bracket_seconds=bracket[1]-bracket[0],
            max_bracket_drift_counts=max(abs(a-b) for a, b in
                                         zip(r['before']['positions'], r['after']['positions'])),
            quality=r['vision']['quality'],
            color_depth_skew_ms=abs(r['vision']['metadata']['color_timestamp_ms']
                                    - r['vision']['metadata']['depth_timestamp_ms']),
        ))
    holdout = [r for r in results if not r['sign_calibration_observation']]
    errors = np.array([r['error_deg'] for r in holdout])
    summary = dict(
        captured_poses=len(results), sign_convention=signs.tolist(), sign_evidence=sign_evidence,
        holdout_poses=len(holdout), axes_evaluated=['ID1/base', 'ID2/shoulder', 'ID3/elbow'],
        holdout_mae_deg=np.mean(abs(errors), axis=0).tolist(),
        holdout_max_abs_error_deg=np.max(abs(errors), axis=0).tolist(),
        iou_range=[min(r['quality']['iou'] for r in results),
                   max(r['quality']['iou'] for r in results)],
        median_depth_residual_mm_range=[
            min(r['quality']['median_surface_residual_m'] for r in results)*1000,
            max(r['quality']['median_surface_residual_m'] for r in results)*1000],
        encoder_range_deg=np.ptp([r['actual_encoder_delta_deg'] for r in results], axis=0).tolist(),
        max_bracket_drift_counts=max(r['max_bracket_drift_counts'] for r in results),
        hardware_synchronized=False, absolute_calibration_verified=False,
        wrist_verified=False, wrist_reason='Only about 1.8 degree motion; +6 candidate stalled. '
                                          'Image estimate did not resolve that small change.',
        id5_verified=False, id5_reason='No moving downstream jaw geometry installed.',
        collision_status='No visible contact on reviewed paths; whole-range collision evidence '
                         'is unavailable. Wrist candidate is rejected.',
    )
    return results, summary


def report_html(rows, summary):
    images = []
    for r in rows:
        name = r['name']
        e = ', '.join(f'{v:+.2f}' for v in r['error_deg'])
        images.append(f'<article><h2>{name}</h2><p>指令 {r["commanded_deg"]}<br>'
                      f'相対角誤差（台座・肩・肘） {e}°<br>IoU {r["quality"]["iou"]:.3f}</p>'
                      f'<a href="captures/{name}/color.png"><img src="captures/{name}/color.png" '
                      f'alt="{name} 実画像"></a><img src="captures/{name}/overlay.jpg" '
                      f'alt="{name} CAD重畳"><img src="captures/{name}/depth-preview.png" '
                      f'alt="{name} 深度"><p>'
                      f'<a href="captures/{name}/observation.npz">RGB-D・K・mask</a> '
                      f'<a href="captures/{name}/pose.json">前後READ・推定・時刻</a></p></article>')
    return ('<!doctype html><html lang="ja"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>多姿勢 RGB-D 認識検証</title><style>'
            'body{font:16px system-ui;margin:24px;background:#f5f7f8;color:#17313d}'
            'main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));'
            'gap:20px}article{background:white;padding:16px}img{width:100%;height:auto}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere}h1{font-size:26px}</style>'
            '<h1>多姿勢のRGB-D認識検証 · 2026-10-04</h1>'
            '<p>20姿勢を画像確認しながら撮影。元の支持姿勢へ復帰し全5台トルクOFF、'
            '22:00頃にユーザーが電源OFFを報告。</p>'
            '<p>相対符号を決めた観測を評価集合から除外しています。絶対角の校正ではありません。'
            '肩の実変化は小さく、手首は未検証です。MuJoCo表示モデルの接触は無効のため、'
            '全可動域の非干渉を認定していません。</p>'
            '<p><a href="REVIEW.md">レビュー・性能・停止例</a> '
            '<a href="evaluation.json">全測定表JSON</a> '
            '<a href="performance.json">期間別性能</a></p>'
            '<p>台座・肩・肘の16姿勢相対MAE：1.15° / 0.43° / 0.37°。'
            '撮影701.97秒で19.80成功Hz、frame age p95 0.101秒。'
            '固定frame処理中央値40.76→29.23ms。性能は最終不在修正前の測定です。</p>'
            '<main><article><h2>開始時の支持姿勢</h2>'
            '<img src="captures/neutral/color.png" alt="撮影開始時の折り畳み姿勢"></article>'
            '<article><h2>復帰・全トルクOFF</h2>'
            '<img src="captures/neutral-final/color.png" alt="撮影終了後の支持姿勢"></article>'
            '<article><h2>発見した背景への誤追跡</h2>'
            '<img src="captures/arm-absent-negative/color.png" alt="アーム不在の失敗画像">'
            '<p>この画像では腕が写っていないのに背景への誤fitが生じました。'
            '台座の位置保持と深度判定により修正後はlost。元の誤推定も保存しています。'
            '</p></article><article><h2>台座位置変更後の表示</h2>'
            '<img src="moved-scene-after-fix-viewer.png" alt="位置変更されたアームをlost表示">'
            '<p>アームは見えていますが古い台座anchorに一致せずlost。再取得が必要です。'
            '</p></article></main>'
            '<details><summary>数値集計</summary><pre>'+html.escape(json.dumps(summary, indent=2))
            +'</pre></details><main>'+''.join(images)+'</main></html>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = sorted(args.dataset.glob('**/pose_*/pose.json'), key=lambda p: p.parent.name)
    paths = [p.parent for p in paths]
    if len(paths) != 20 or len({p.name for p in paths}) != 20:
        raise ValueError('Expected twenty distinct accepted poses across retained run segments')
    baseline = np.array(json.loads((args.dataset/'plan.json').read_text())['reference_counts'])
    rows, summary = evaluate(paths, args.dataset/'neutral', baseline)
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = []
    for path in [*paths, args.dataset/'neutral', args.dataset/'neutral-final']:
        target = args.output/'captures'/path.name
        shutil.copytree(path, target, dirs_exist_ok=True)
        manifest.extend(dict(path=str(p.relative_to(args.output)), bytes=p.stat().st_size,
                             sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                        for p in sorted(target.iterdir()) if p.is_file())
    (args.output/'evaluation.json').write_text(
        json.dumps(dict(summary=summary, poses=rows), indent=2))
    (args.output/'capture-manifest.json').write_text(json.dumps(manifest, indent=2))
    (args.output/'REPORT.html').write_text(report_html(rows, summary))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
