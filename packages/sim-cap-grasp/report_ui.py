"""Generate an offline report from this batch's actual saved evidence."""

import argparse
import csv
import html
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def build(root, name):
    index = read(root / "results" / name / "index.json")
    audit_path = root / "evidence" / f"independent-{name}.json"
    audit = read(audit_path) if audit_path.exists() else None
    media = root / "media" / f"random-{name}" / "manifest.json"
    records = read(media) if media.exists() else []
    by_id = {row["target_id"]: row for row in (audit or {}).get("trials", [])}
    escape = html.escape
    csv_dir = root / "evidence" / f"report-{name}"
    csv_dir.mkdir(parents=True, exist_ok=True)
    with (csv_dir / "trials.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["target_id", "x_m", "y_m", "status", "reason_codes", "run_dir"])
        for row in index["trials"]:
            writer.writerow(
                [
                    row["target_id"],
                    *row["target_m"][:2],
                    row["status"],
                    ";".join(row["reason_codes"]),
                    row["run_dir"],
                ]
            )
    selection = read(root / "results" / name / "selection.json")
    with (csv_dir / "proposals.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["proposal_index", "x_m", "y_m", "status", "reason"])
        for row in sorted(
            selection["selected_before_dynamics"] + selection["rejected"],
            key=lambda item: item["proposal_index"],
        ):
            writer.writerow(
                [row["proposal_index"], *row["target_m"][:2], row["status"], row.get("reason", "")]
            )
    rows = []
    dots = []
    for row in index["trials"]:
        detail = by_id.get(row["target_id"], {})
        diagnosis = detail.get("transfer_diagnostics_non_gating", {})
        lost = diagnosis.get("lower_first_both_finger_contacts_absent_s") is not None
        x, y = row["target_m"][:2]
        dots.append(
            f'<circle cx="{300 + x * 900:.2f}" cy="{300 - y * 900:.2f}" r="4" fill="{"#22805a" if row["status"] == "SUCCESS" else "#c23636"}"><title>{escape(row["target_id"])}</title></circle>'
        )
        run = escape(row["run_dir"])
        rows.append(
            f'<tr><td><a href="{run}/result.json">{escape(row["target_id"])}</a></td><td>{x * 1000:.1f}, {y * 1000:.1f}</td><td>{escape(row["status"])}</td><td>{escape(", ".join(row["reason_codes"]) or "—")}</td><td>{"あり" if lost else "なし / 未監査"}</td><td>{detail.get("audit_pass", "未監査")}</td></tr>'
        )
    clips = []
    for record in records:
        videos = "".join(
            f'<div><p>{escape(view)}</p><video controls preload="metadata" src="{escape(file)}"></video></div>'
            for view, file in record["videos"].items()
        )
        frames = "".join(
            f'<figure><a href="{escape(file)}"><img loading="lazy" alt="{escape(record["title"])} / {escape(phase)} / {escape(view)}" src="{escape(file)}"></a><figcaption>{escape(phase)} / {escape(view)}</figcaption></figure>'
            for phase, views in record["keyframes"].items()
            for view, file in views.items()
        )
        clips.append(
            f'<article><h3>{escape(record["title"])}</h3><p>{escape(record["trial"])} · {escape(record["status"])}</p><div class="views">{videos}</div><div class="frames">{frames}</div></article>'
        )
    interval = index.get("wilson_95_interval")
    confidence = (
        "未集計" if interval is None else f"{interval[0] * 100:.2f}–{interval[1] * 100:.2f}%"
    )
    transfer = (audit or {}).get("transfer_diagnostics_non_gating", {})
    losses = transfer.get("trials_with_any_lower_both_finger_contact_absence", "未監査")
    speed = transfer.get("cap_center_speed_before_box_contact_max_m_s")
    speed_text = "未監査" if speed is None else f"{speed:.3f} m/s"
    audit_status = "PASS" if audit and audit["audit_pass"] else "未監査 / FAIL"
    before_box = (
        sum(
            (d := row["transfer_diagnostics_non_gating"])[
                "lower_first_both_finger_contacts_absent_s"
            ]
            is not None
            and d["first_lower_release_box_contact_s"] is not None
            and d["lower_first_both_finger_contacts_absent_s"]
            < d["first_lower_release_box_contact_s"]
            for row in (audit or {}).get("trials", [])
        )
        if audit
        else "未監査"
    )
    history = []
    for path in sorted((root / "results").glob("qualification-*/index.json")):
        if path.parent.name == name:
            continue
        old = read(path)
        history.append(
            f'<li><a href="{escape(str(path.relative_to(root)))}">{escape(path.parent.name)}</a>: {escape(old["status"])}、成功 {old.get("successes", 0)}/{old["trial_count"]}、invalid {old.get("invalid_trials", "未集計")}。未完了分を別試行で置換していません。</li>'
        )
    body = f"""<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>ランダム把持 {escape(name)}</title><link rel="icon" href="data:,">
<style>body{{font:16px system-ui;background:#edf3f7;color:#17313f;margin:0;padding:24px}}main{{max-width:1180px;margin:auto}}article,section{{background:white;padding:22px;margin:20px 0;border-radius:12px}}h1{{line-height:1.4}}a{{color:#175c8b}}.views{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:15px}}video{{width:100%}}.frames{{display:flex;flex-wrap:wrap;gap:8px}}figure{{margin:0;width:160px}}figcaption{{font-size:12px}}.frames img{{width:160px;max-width:100%}}svg{{max-width:100%;height:auto}}.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;white-space:nowrap}}td,th{{text-align:left;padding:8px;border-bottom:1px solid #ddd}}input{{padding:10px;max-width:90%}}@media(max-width:700px){{body{{padding:12px}}.views{{grid-template-columns:1fr}}}}</style><main>
<h1>待機 → 把持 → 持上げ・保持 → 下置き → 待機復帰</h1>
<p>今回の batch: <strong>{escape(name)}</strong> / seed {index["generator_seed"]} / 状態 {escape(index["status"])}</p>
<section><h2>保存データからの集計</h2><p><strong>{index.get("successes", 0)} / {index["trial_count"]}</strong> 成功、unsafe {index.get("unsafe_trials", "未集計")}、invalid {index.get("invalid_trials", "未集計")}。Wilson 95%区間 {confidence}。独立監査 {audit_status}。</p>
<p>提案 {index["proposal_count"]}、棄却 {len(index["rejected"])}。実行前に選んだ候補全数を母数へ含めています。シミュレーション終了時の保存結果であり、実機の安全性を保証しません。</p>
<p>この区間は選択した新バッチの条件付き成功率を記述します。IKで棄却した範囲や実機への一般化、修正前バッチを含む無条件の成功率を示しません。</p>
<p><strong>下降中の連続保持は未確立。</strong> lower中に両指接触が失われた試行 {losses}、うち箱の初接触より前 {before_box}。最大箱接触前速度 {speed_text}。保持区間の合格と、穏やかな下置きは別です。固定pitch −50°、未校正proxy、MuJoCo真値の下降停止を使用。有限sampleの経路検査は連続衝突回避の証明ではありません。</p>
<p>受領した旧レポートの100試行rawは未納品です。このページは今回保存した新バッチを集計しています。</p>
<ul>{"".join(history)}</ul>
<p><a href="results/{escape(name)}/index.json">全結果</a> · <a href="results/{escape(name)}/selection.json">実行前の選択</a> · <a href="evidence/{escape(name)}-freeze.json">凍結条件</a>{f' · <a href="evidence/independent-{escape(name)}.json">全raw独立監査</a>' if audit else ""}</p></section>
<section><h2>採用配置 / XY（mm）</h2><svg viewBox="0 0 600 600" width="600" role="img" aria-label="採用配置のXY分布"><rect x="0" y="0" width="600" height="600" fill="#f2f6f8"/><path d="M0 300H600M300 0V600" stroke="#98aebd"/><text x="560" y="290">+X</text><text x="310" y="20">+Y</text><text x="8" y="590">0中心 / 端点 ±333 mm</text>{"".join(dots)}</svg><p><a href="evidence/report-{escape(name)}/trials.csv">試行CSV</a> · <a href="evidence/report-{escape(name)}/proposals.csv">提案・棄却CSV</a></p></section>
<section><h2>二視点の生状態再生</h2><p>保存qposからの描画です。描画中のqpos設定は物理試行ではありません。姿勢・視点は名目モデルに限ります。</p>{"".join(clips) or "<p>映像未生成。</p>"}</section>
<section><h2>全試行</h2><input id="search" placeholder="ID・成功失敗を検索" aria-label="試行検索"><div class="table"><table><thead><tr><th>ID</th><th>XY mm</th><th>結果</th><th>理由</th><th>下降接触消失</th><th>独立監査</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></section></main>
<script>document.getElementById('search').addEventListener('input',e=>{{for(const row of document.querySelectorAll('tbody tr'))row.hidden=!row.textContent.toLowerCase().includes(e.target.value.toLowerCase());}});</script></html>"""
    output = root / f"RANDOM_REPORT_{name}.html"
    output.write_text(body)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--name", default="qualification-001")
    args = parser.parse_args()
    print(build(args.root, args.name).name)


if __name__ == "__main__":
    main()
