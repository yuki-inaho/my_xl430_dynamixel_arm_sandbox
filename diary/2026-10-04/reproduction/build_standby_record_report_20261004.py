"""Build a local illustrated record from saved artifacts only. No robot access."""
import argparse
import base64
import hashlib
import html
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def href(path, output):
    return quote(os.path.relpath(path, output), safe="/")


def figure(path, title, caption):
    mime = "image/png" if path.suffix == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode()
    return (f'<figure><button class="image" aria-label="{html.escape(title)}を拡大">'
            f'<img loading="lazy" src="data:{mime};base64,{encoded}" '
            f'alt="{html.escape(title)}"></button><figcaption><strong>{html.escape(title)}'
            f'</strong><span>{html.escape(caption)}</span></figcaption></figure>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--simulation-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--session-clean", type=Path, required=True)
    args = parser.parse_args()
    root = args.workspace / "reports/robot-completion-20261004"
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    assets = out / "screenshots"
    assets.mkdir(exist_ok=True)
    sim = args.simulation_root / "outputs/robot-vision-observation-20261004"
    for p in sorted(sim.rglob("*")):
        if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
            target = assets / p.relative_to(sim)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)

    first = rows(root / "standby-stage-actual/events.jsonl")
    second = rows(root / "standby-stage-resumed/events.jsonl")
    post = rows(root / "standby-off-post-read.jsonl")
    frames = [r["frame"] for r in post if "frame" in r]
    last = {m["motor_id"]: m for m in frames[-1]["motors"]}
    reached = {r["stage"]: r for r in second if r["kind"] == "reached"}
    all_events = first + second
    writes = [r for r in all_events if r["kind"] == "write"]
    baseline = next(r["baseline"] for r in first if r["kind"] == "plan")
    spans = {mid: max(f["motors"][mid-1]["position_counts"] for f in frames) -
                  min(f["motors"][mid-1]["position_counts"] for f in frames)
             for mid in range(1, 6)}
    checks = {
        "all_200_post_frames": len(frames) == 200,
        "all_post_torque_off": all(m["torque_enabled"] is False
            for f in frames for m in f["motors"]),
        "all_post_healthy": all(not m["hardware_error"] and not m["device_alert"]
            and not m["faults"] for f in frames for m in f["motors"]),
        "post_span_at_most_one": max(spans.values()) <= 1,
        "post_closed": post[-1]["summary"]["port_closed"] is True,
        "write_ids_only_2_3_4": {r["motor_id"] for r in writes} == {2, 3, 4},
        "write_register_names_only_allowed": all(r["name"] in
            ("goal", "torque", "pwm", "velocity", "acceleration") for r in writes),
        "forward_and_return_stages_recorded": set(reached) >= {"elbow60", "elbow72",
            "wrist10", "wrist30", "return_wrist", "return_elbow60",
            "return_elbow30", "return_fold"},
        "actual_elbow_opened_over_700_counts": reached["elbow72"]["positions"][2] -
            baseline[2] > 700,
        "actual_wrist_down_over_250_counts": baseline[3] -
            reached["wrist30"]["positions"][3] > 250,
        "return_near_original_baseline": all(abs(last[mid]["position_counts"] -
            baseline[mid-1]) <= 20 for mid in range(1, 6)),
        "released_final_event": second[-1]["kind"] == "released_supported",
        "first_deadline_failure_preserved": any(r["kind"] == "stop" and
            "deadline" in r["reason"] for r in first),
    }
    summary = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "saved-artifact audit; no hardware access",
        "checks": checks, "all_checks_pass": all(checks.values()),
        "baseline_counts": baseline,
        "standby_counts_observed_130106": [2064, 3115, 1969, 1721, 2059],
        "post_off_counts": [last[mid]["position_counts"] for mid in range(1, 6)],
        "post_spans": spans, "post_summary": post[-1]["summary"],
        "power_off": {"user_report": "電源きりました", "recorded_at_local": "2026-10-04T13:06",
            "exact_switch_time": None, "supply_measurement": None,
            "camera_frames": ["power-off-0001.jpg", "power-off-0002.jpg", "power-off-0003.jpg"],
            "visual_review": "元の畳み姿勢付近を保持。原画像をVLMで確認。",
            "support_load_path_verified": False},
        "absolute_calibration_verified": False,
        "collision_certification": "UNKNOWN; original Boolean controls ERROR",
        "quality": {"python_tests": 291, "ruff": "PASS", "ty": "PASS",
            "max_complexity": 10, "skill_validation": "PASS"},
        "execution_code_hash_captured_before_run": False,
        "current_source_sha256": digest(args.workspace / "src/arm_observer/standby_motion.py"),
        "code_scope_note": "signal/logging stop improvements were tested offline after motion",
    }
    (out / "RECORD.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    manifest = []
    for p in sorted(root.rglob("*")):
        if out in p.parents:
            continue
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".mkv"):
            manifest.append({"path": str(p.relative_to(args.workspace)),
                "href": href(p, out), "bytes": p.stat().st_size, "sha256": digest(p)})
    for p in sorted(assets.rglob("*")):
        if p.is_file():
            manifest.append({"path": str(p.relative_to(out)), "href": href(p, out),
                             "bytes": p.stat().st_size, "sha256": digest(p),
                             "kind": "copied MuJoCo/Playwright screenshot"})
    (out / "ASSETS.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    camera = root / "standby-camera"
    gallery = [
        (camera/"frame-0019.jpg", "開始時の畳み姿勢", "肩・肘・手首をこの位置で保持。ID1/5には書き込まない。"),
        (camera/"frame-0043.jpg", "最初の肘30°段階", "実機の肘が開いた。肩の位置を保持しながら、前方へ動いたことを確認。"),
        (camera/"frame-0100.jpg", "2段階目・最初の停止", "実機は前方へ動いたが、負荷下がり36countが残りdeadlineで停止。脱力しなかった。"),
        (camera/"resumed-0039.jpg", "限定補正後の再開", "閾値を緩めず1回最大30countのgoal補正。元baselineと復元設定は保持。"),
        (camera/"resumed-0052.jpg", "前腕を前向きに", "肘の実変化を確認。世界角は外観による概略で、精密測定ではない。"),
        (camera/"resumed-0065.jpg", "手首の小さい下向き動作", "先に小さい段階で、下げる方向へ動くことを観察。"),
        (camera/"resumed-0098.jpg", "スタンバイ候補に到達", "前腕は概ね前方、ID5支持部は下向き。実READ2064/3115/1969/1721/2059。"),
        (camera/"resumed-0180.jpg", "元姿勢へ復帰", "手首を戻し、肘を段階的に畳んだ。空中のスタンバイでは脱力しない。"),
        (camera/"release-0048.jpg", "全TorqueOFF後", "10秒200frameの独立READで全台OFF、最大span1count。大きな落下なし。"),
        (camera/"power-off-0003.jpg", "ユーザーの電源OFF報告後", "13:06の電源OFF申告後に撮影。畳み姿勢付近を保つ。電源電圧の測定はしていない。"),
    ]
    photographs = "".join(figure(*entry) for entry in gallery)
    screenshots = "".join(figure(assets/name, title, caption) for name,title,caption in [
        ("standby-stage30-preview.png", "MuJoCo：初段の候補", "専用headless Playwrightで確認。画像基準の概略CAD入力。"),
        ("standby-world-down30.png", "MuJoCo：前方・下向きの候補", "爪・カメラホルダー未装着を反映。実角ライブ校正と重力安定の検証は未完了。"),
        ("phase-derived-manual-pose.png", "MuJoCo：現在姿勢の仮定", "画像から作った観測仮説。未知の誤差を正確な校正値にはしていない。"),
    ])
    state_rows = "".join(f"<tr><td>ID{mid}</td><td>{role}</td><td>{baseline[mid-1]}</td>"
        f"<td>{summary['standby_counts_observed_130106'][mid-1]}</td>"
        f"<td>{last[mid]['position_counts']}</td><td>{spans[mid]}</td></tr>"
        for mid,role in enumerate(["台座・中立近傍","肩・現在近傍保持","肘・前方へ開く",
                                   "手首・下向き","未装着爪・中立維持"],1))
    inventory = "".join(f'<li><a href="{item["href"]}">{html.escape(item["path"])}</a>'
        f' <small>{item["bytes"]:,} bytes</small></li>' for item in manifest)
    links = [
        (root/"standby-stage-actual/events.jsonl", "第一実行ログ（停止を含む）"),
        (root/"standby-stage-resumed/events.jsonl", "再開・復帰・脱力ログ"),
        (root/"standby-off-post-read.jsonl", "独立事後READ（200frame）"),
        (root/"standby-stage-resumed/SELF_REVIEW_5.md", "今回の自己レビュー5回"),
        (args.workspace/"temp/workdoc_Oct04-2026_robot_completion.md", "継続作業書"),
        (args.workspace/"skills/robot-park-pose-definition/SKILL.md", "更新した汎用スキル"),
        (args.session_clean, "会話 *_clean.json（書き出し時点まで）"),
        (out/"RECORD.json", "独立集計・判定JSON"),
        (out/"ASSETS.json", "全保存画像・動画のSHA256一覧"),
    ]
    link_html = "".join(f'<li><a href="{href(p,out)}">{html.escape(title)}</a></li>' for p,title in links)
    page = f"""<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>実機スタンバイ・停止記録 2026-10-04</title>
<link rel="icon" href="data:,">
<style>
:root{{color-scheme:light;font-family:system-ui,"Noto Sans JP",sans-serif;color:#20333e;background:#eef3f5}}
body{{margin:0}}header{{background:#173c48;color:white;padding:40px max(22px,calc((100vw - 1120px)/2))}}
h1{{font-size:clamp(24px,3vw,36px);margin:12px 0}}h2{{font-size:24px}}p,li{{line-height:1.8}}
main{{max-width:1120px;margin:auto;padding:24px}}section{{margin:24px 0;background:white;padding:24px;border-radius:12px}}
.pill{{display:inline-block;background:#d9ede6;color:#1a5844;padding:7px 12px;border-radius:20px;font-size:13px}}
.note{{background:#fff5df;border-left:4px solid #c18422;padding:12px 16px}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}}
figure{{margin:0;min-width:0;border:1px solid #dce5e9;border-radius:8px;overflow:hidden;background:#f5f8fa}}
.image{{display:block;border:0;padding:0;width:100%;cursor:zoom-in;background:none}}img{{display:block;width:100%;height:auto}}
figcaption{{padding:14px;line-height:1.65}}figcaption strong,figcaption span{{display:block}}figcaption span{{font-size:14px;margin-top:6px}}
.scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse;white-space:nowrap}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #dce5e9}}
a{{color:#096e89;overflow-wrap:anywhere}}small{{color:#647b85}}details{{margin:16px 0}}summary{{cursor:pointer;font-weight:650}}
dialog{{border:0;padding:12px;max-width:96vw;width:1400px;background:white}}dialog::backdrop{{background:#000b}}
dialog button{{padding:8px 15px;float:right;margin-bottom:10px}}dialog img{{clear:both}}footer{{padding:20px 0;color:#617881}}
@media(max-width:720px){{main{{padding:12px}}section{{padding:16px}}.grid{{grid-template-columns:1fr}}}}
</style>
<header><span class="pill">実機作業はユーザー指示で一時停止 · 電源OFF報告あり</span>
<h1>スタンバイへ実際に動かし、元姿勢へ戻した記録</h1>
<p>2026年10月4日 / 裸の全XL430・R3系アーム / 画像・実READ・停止を含む原ログ</p></header>
<main><section><h2>結果</h2><p>肩を現在位置近傍で保持し、肘を段階的に前方へ開き、
手首を下向きに動かした。USBカメラで動いたことを確認した。その後元の安定姿勢へ戻し、
全モーターのTorqueOFFとRAM設定の復元をREAD照合した。</p>
<p>脱力後10秒・200frameでは欠測0、約20Hz、各関節の変化は最大1count。
ユーザーは13:06に「電源きりました」と報告。報告後のカメラ画像でも元姿勢付近を保っていた。</p>
<p class="note">スタンバイの向きは外観による概略確認。絶対CAD角の校正、自己干渉全域、
クッションの荷重経路は未確定。既存MuJoCoは描画・運動学の確認用で、実角ライブ校正や重力安定の証明は未完了。</p></section>
<section><h2>実機画像で追う一連の動き</h2><p>画像をクリックすると拡大できます。選択した原画像はHTMLに埋め込んでいます。</p>
<div class="grid">{photographs}</div></section>
<section><h2>読取り値</h2><p>数値はencoder count。世界角と同じ意味ではありません。電源OFF後には新しいモーターREADをしていません。</p>
<div class="scroll"><table><thead><tr><th>ID</th><th>役割</th><th>開始</th><th>スタンバイ</th><th>脱力後最終</th><th>10秒span</th></tr></thead>
<tbody>{state_rows}</tbody></table></div></section>
<section><h2>停止と修正を残す</h2><p>最初のelbow60は36countの負荷下がりが残り、
18秒のdeadlineで停止した。脱力せず、現在位置付近を保持した。判定閾値を緩めず、
1回最大30countのgoal補正と元の基準・復元設定を維持する再開処理を追加した。</p>
<p>空中で自動TorqueOFFしない。ID1/5は書込みなし。ID2/3/4の限定RAM経路は旧ID3単軸経路とは別。
実機後のレビューで、follow中の停止信号とログ障害時の保持処理を修正し、offlineで検証した。</p>
<p>最終品質確認：Python291件PASS、ruff/ty PASS、最大複雑度10、スキル形式PASS。
保存原ログから独立に集計した13項目は {sum(checks.values())}/13 PASS。</p></section>
<section><h2>MuJoCo / Playwrightの保存画面</h2><div class="grid">{screenshots}</div></section>
<section><h2>更新スキルと記録の再現</h2><p>robot-park-pose-definitionへ、概略の視覚確認と
精密校正の区別、近位関節の保持、段階レビュー、脱力しない停止、限定補正、基準を維持する再開、
電源OFFと支持の別記録を追記した。今回固有のcountは汎用の既定値にしていない。</p>
<ul>{link_html}</ul><details><summary>保存されている画像・動画の全一覧（{len(manifest)}件）</summary>
<p>主な画像は上に埋め込み、連続撮影の全frameと旧比較画面は原ファイルへのリンクを残した。
試行段階の仮表示も含む一覧であり、各画像を合格証拠とは扱わない。</p><ul>{inventory}</ul></details>
</section><footer>生成 {summary['created_at']}。ローカル保存のみ。commit・pushは実行していない。
会話JSONは書き出し時点までの現分岐。祖先会話の再構成と最終応答の収録は主張しない。</footer>
</main><dialog id="zoom"><button id="close">閉じる</button><img alt="拡大画像"></dialog>
<script>const d=document.querySelector('#zoom');document.querySelectorAll('.image').forEach(b=>b.onclick=()=>{{
d.querySelector('img').src=b.querySelector('img').src;d.showModal()}});document.querySelector('#close').onclick=()=>d.close();
d.onclick=e=>{{if(e.target===d)d.close()}};</script></html>"""
    (out / "REPORT.html").write_text(page, encoding="utf-8")
    print(json.dumps({"html": str(out / "REPORT.html"), "embedded_images": 13,
        "inventory_items": len(manifest), "checks_pass": all(checks.values()),
        "html_bytes": len(page.encode())}, ensure_ascii=False))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
