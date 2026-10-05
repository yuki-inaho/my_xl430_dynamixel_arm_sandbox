"""Generate state-derived two-view evidence, plots, and offline Japanese HTML."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess

os.environ.setdefault("MUJOCO_GL", "egl")
import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from build_scene import ROOT, save_json, sha

MEDIA = ROOT / "media"
FONT = "DejaVuSans.ttf"


def render_trial(name, label):
    trial = ROOT / "results" / name
    s = np.load(trial / "states.npz")
    model = mujoco.MjModel.from_xml_path(str(trial / "scene.xml"))
    data = mujoco.MjData(model)
    renderer = mujoco.Renderer(model, 360, 640)
    opt = mujoco.MjvOption()
    opt.geomgroup[3:] = 0
    camera = mujoco.MjvCamera()
    camera.lookat[:] = [0, 0.14, 0.12]
    camera.distance = 0.43
    camera.azimuth = 135
    camera.elevation = -20
    out = MEDIA / label
    out.mkdir(parents=True, exist_ok=True)
    frames = []
    for number, t in enumerate(np.arange(0, float(s["time"][-1]) + 0.0001, 0.1)):
        i = int(np.argmin(np.abs(s["time"] - t)))
        data.qpos[:] = s["qpos"][i]
        data.qvel[:] = s["qvel"][i]
        data.ctrl[:] = s["ctrl"][i]
        mujoco.mj_forward(model, data)
        for view, cam in [("external", camera), ("wrist", "wrist_d405")]:
            target = out / f"{view}-{number:04d}.png"
            renderer.update_scene(data, camera=cam, scene_option=opt)
            im = Image.fromarray(renderer.render())
            draw = ImageDraw.Draw(im)
            draw.rectangle((0, 0, 640, 29), fill="#182733")
            draw.text(
                (10, 6),
                f"{view.upper()}  t={s['time'][i]:.3f}s  {s['phase'][i]}  {label}",
                font=ImageFont.truetype(FONT, 15),
                fill="white",
            )
            im.save(target)
            frames.append(
                {
                    "view": view,
                    "frame": number,
                    "sample": i,
                    "simulation_time": float(s["time"][i]),
                    "phase": str(s["phase"][i]),
                    "file": str(target.relative_to(ROOT)),
                }
            )
        if number % 25 == 0:
            print(f"Rendering {label}: frame{number}, physics t={t:.1f}s", flush=True)
    renderer.close()
    save_json(
        out / "frame-provenance.json",
        {
            "source": str(trial.relative_to(ROOT) / "states.npz"),
            "physics_dt_s": model.opt.timestep,
            "render_fps": 10,
            "frames": frames,
        },
    )
    videos = []
    if shutil.which("ffmpeg"):
        for view in ("external", "wrist"):
            dest = out / f"{view}.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-framerate",
                    "10",
                    "-i",
                    str(out / f"{view}-%04d.png"),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-crf",
                    "23",
                    "-movflags",
                    "+faststart",
                    str(dest),
                ],
                check=True,
            )
            videos.append(str(dest.relative_to(ROOT)))
    keys = {}
    for stage, t in [
        ("approach", 2.9),
        ("grasp", 6.4),
        ("lift", 8.0),
        ("hold", 10.0),
        ("release", 12.7),
    ]:
        number = round(t * 10)
        if number < len(frames) // 2:
            keys[stage] = [
                str((out / f"{view}-{number:04d}.png").relative_to(ROOT))
                for view in ("external", "wrist")
            ]
    return {
        "trial": name,
        "label": label,
        "frames_per_view": len(frames) // 2,
        "videos": videos,
        "keyframes": keys,
    }


def plot(nominal_name):
    s = np.load(ROOT / "results" / nominal_name / "states.npz")
    t = s["time"]
    az = np.clip(np.abs(s["cap_axis"][:, 2]), 0, 1)
    clearance = (s["cap_position"][:, 2] - 0.0075 * az - 0.014 * np.sqrt(1 - az * az) - 0.05) * 1000
    rel = np.einsum("nji,nj->ni", s["grip_rotation"], s["cap_position"] - s["grip_position"])
    start = np.where(s["phase"] == "hold")[0][0]
    drift = np.linalg.norm(rel - rel[start], axis=1) * 1000
    error = np.linalg.norm(s["grip_position"] - s["target_position"], axis=1) * 1000
    datasets = [
        ("Cap bottom above INITIAL support (mm)", [clearance], 20, (0, 45)),
        (
            "Left / right force-bearing normal contact (N)",
            [s["left_force"], s["right_force"]],
            None,
            (0, 1.0),
        ),
    ]
    datasets += [
        ("Grip-frame center drift from hold start (mm)", [drift], 5, (0, 8)),
        ("Actual grip site to commanded target (mm)", [error], 2, (0, 3)),
    ]
    im = Image.new("RGB", (1400, 880), "white")
    draw = ImageDraw.Draw(im)
    font = ImageFont.truetype(FONT, 20)
    small = ImageFont.truetype(FONT, 16)
    for panel, (title, series, threshold, yrange) in enumerate(datasets):
        ox = 30 + (panel % 2) * 700
        oy = 20 + (panel // 2) * 430
        left, top, right, bottom = ox + 55, oy + 55, ox + 640, oy + 365
        draw.text((ox + 10, oy), title, font=font, fill="#162733")

        def x(v, left=left, right=right):
            return left + (v / 13) * (right - left)

        def y(v, bottom=bottom, top=top, yrange=yrange):
            return bottom - (np.clip(v, *yrange) - yrange[0]) / (yrange[1] - yrange[0]) * (
                bottom - top
            )

        draw.rectangle((x(9), top, x(11), bottom), fill="#e2f2e8")
        for grid in np.linspace(*yrange, 6):
            draw.line((left, y(grid), right, y(grid)), fill="#dbe1e5")
            draw.text((ox, y(grid) - 8), f"{grid:.1f}", font=small, fill="#59636b")
        for tx in (0, 3, 6, 9, 11, 13):
            draw.text((x(tx) - 8, bottom + 8), str(tx), font=small, fill="#59636b")
        if threshold is not None:
            for xx in range(left, right, 14):
                draw.line((xx, y(threshold), xx + 7, y(threshold)), fill="#b82d3a", width=2)
        for index, values in enumerate(series):
            ids = np.arange(0, len(t), 5)
            draw.line(
                [(x(float(t[i])), y(float(values[i]))) for i in ids],
                fill=("#157a8c", "#ce7937")[index],
                width=2,
            )
        draw.text(
            (left, bottom + 35),
            "Time (s)     shaded = evaluated 2-second hold",
            font=small,
            fill="#59636b",
        )
    im.save(MEDIA / "timeseries.png")


def proxy_closeups(nominal_name):
    trial = ROOT / "results" / nominal_name
    states = np.load(trial / "states.npz")
    index = int(np.argmin(abs(states["time"] - 10.0)))
    model = mujoco.MjModel.from_xml_path(str(trial / "scene.xml"))
    data = mujoco.MjData(model)
    data.qpos[:] = states["qpos"][index]
    mujoco.mj_forward(model, data)
    for name in ("cap_geom", "cap_mark", "box", "table"):
        model.geom_group[model.geom(name).id] = 2
    renderer = mujoco.Renderer(model, 540, 960)
    for label, group in [("source", 0), ("proxy", 3)]:
        opt = mujoco.MjvOption()
        opt.geomgroup[:] = 0
        opt.geomgroup[group] = opt.geomgroup[2] = 1
        renderer.update_scene(data, camera="wrist_d405", scene_option=opt)
        Image.fromarray(renderer.render()).save(MEDIA / f"grasp-{label}-closeup.png")
    renderer.close()
    save_json(
        MEDIA / "closeup-provenance.json",
        {
            "trial": "results/" + nominal_name,
            "sample": index,
            "time_s": float(states["time"][index]),
            "scene_sha256": sha(trial / "scene.xml"),
            "states_sha256": sha(trial / "states.npz"),
        },
    )


def main(skip_render=False, nominal_name="review-repeat", negative_name="review-no-close"):
    MEDIA.mkdir(exist_ok=True)
    if not skip_render:
        media = [render_trial(nominal_name, "nominal"), render_trial(negative_name, "negative")]
        save_json(MEDIA / "manifest.json", media)
    media = json.loads((MEDIA / "manifest.json").read_text())
    if [x["trial"] for x in media] != [nominal_name, negative_name]:
        raise ValueError("Media manifest refers to different trials; regenerate images")
    plot(nominal_name)
    proxy_closeups(nominal_name)
    study = json.loads((ROOT / "study-results.json").read_text())
    nominal = json.loads(
        (ROOT / "results" / nominal_name / "independent-evaluation.json").read_text()
    )
    metrics = nominal["metrics"]
    audit_name = "raw-audit-" + nominal_name + ".json"
    audit = json.loads((ROOT / audit_name).read_text())
    all_trials = []
    for path in sorted((ROOT / "results").glob("*/result.json")):
        result = json.loads(path.read_text())
        metadata = json.loads((path.parent / "metadata.json").read_text())
        all_trials.append(
            {
                "name": path.parent.name,
                "status": result["status"],
                "reason_codes": result["reason_codes"],
                "friction": metadata["friction"],
                "mass_g": metadata["cap_mass_kg"] * 1000,
                "timestep_ms": metadata.get("timestep_s", 0.001) * 1000,
                "metrics": result["metrics"],
                "result_path": str(path.relative_to(ROOT)),
            }
        )
    summary = {
        "status": nominal["status"],
        "scope": "nominal simulation only",
        "hardware_success": "not_tested",
        "scene_registration": "nominal",
        "calibration_verified": False,
        "metrics": metrics,
        "evaluation_contract": json.loads((ROOT / "evaluation_contract.json").read_text()),
        "deterministic_repeat": study["deterministic_repeat"],
        "independent_raw_audit_pass": audit["pass"],
        "trials": all_trials,
        "media": media,
        "delivery_validation": "see review-verification.json",
    }
    save_json(ROOT / "result.json", summary)
    cards = [
        ("連続保持", f"{metrics['hold_duration_s']:.3f} s", "基準 2.0 s以上"),
        (
            "底面の最小離隔",
            f"{metrics['hold_bottom_clearance_min_m'] * 1000:.3f} mm",
            "初期支持面から 20 mm以上",
        ),
        ("左右同時接触", f"{metrics['hold_bilateral_fraction'] * 100:.2f}%", "基準 80%以上"),
        (
            "手先内の最大漂移",
            f"{metrics['hold_grip_frame_drift_max_m'] * 1000:.3f} mm",
            "基準 5 mm以下",
        ),
    ]
    card_html = "".join(
        f"<article><small>{a}</small><strong>{b}</strong><span>{c}</span></article>"
        for a, b, c in cards
    )
    rows = "".join(
        f'<tr><td><a href="{x["result_path"]}">{x["name"]}</a></td><td class="{x["status"].lower()}">{x["status"]}</td><td>{x["friction"]}</td><td>{x["mass_g"]:.2f}</td><td>{x["timestep_ms"]:.1f}</td><td>{", ".join(x["reason_codes"]) or "全条件達成"}</td></tr>'
        for x in all_trials
    )
    stage_html = "".join(
        f'<h3>{name} · {t:.1f}秒</h3><div class="views"><figure><img src="{media[0]["keyframes"][name][0]}" alt="{name} 外部視点"><figcaption>外部視点</figcaption></figure><figure><img src="{media[0]["keyframes"][name][1]}" alt="{name} D405相当視点"><figcaption>D405相当の手首視点</figcaption></figure></div>'
        for name, t in [
            ("approach", 2.9),
            ("grasp", 6.4),
            ("lift", 8.0),
            ("hold", 10.0),
            ("release", 12.7),
        ]
    )
    negative_video = "".join(
        f'<video controls preload="metadata" src="{v}"></video>' for v in media[1]["videos"]
    )
    nominal_video = "".join(
        f'<video controls preload="metadata" src="{v}"></video>' for v in media[0]["videos"]
    )
    page = f"""<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>R3アームのキャップ把持シミュレーション検証</title>
<style>body{{font:16px/1.7 system-ui,sans-serif;margin:0;color:#243341;background:#f4f6f7}}main{{max-width:1150px;margin:auto;padding:42px 24px 80px}}h1{{font-size:32px;line-height:1.4;color:#152630}}h2{{margin-top:50px}}h3{{margin-top:28px}}a{{color:#146783}}.lead{{font-size:19px}}.tag{{color:#167147;font-weight:700}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:30px 0}}article{{background:white;padding:18px;border-radius:10px}}article strong{{display:block;font-size:27px;color:#156a49}}article small,article span{{display:block;font-size:13px}}.views{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}figure{{margin:0}}img,video{{width:100%;height:auto;background:#dce3e5}}figcaption{{font-size:14px;color:#566774}}.views video{{min-width:0}}table{{border-collapse:collapse;width:100%;background:white;font-size:14px}}td,th{{padding:10px;border:1px solid #d9dfe3;text-align:left}}th{{background:#263e4d;color:white}}.success{{color:#167147;font-weight:700}}.failure{{color:#9b4141}}pre{{white-space:pre-wrap;background:white;padding:18px;overflow:auto}}.note{{color:#795427}}.scroll{{overflow:auto}}footer{{margin-top:45px;font-size:13px;color:#596b75}}@media(max-width:750px){{.cards{{grid-template-columns:1fr 1fr}}.views{{grid-template-columns:1fr}}h1{{font-size:26px}}}}</style>
<main><p class="tag">SUCCESS · 名目物理シミュレーション</p><h1>R3アームによるキャップ把持と持ち上げの検証</h1>
<p class="lead">4軸アームと1軸jawが、自由物体のキャップへ接近し、左右のsofttipだけで持ち上げて2秒保持した。元の固定条件を数値判定し、同じseedで全状態が完全一致する再実行を確認した。</p>
<p class="note">実機の成功や校正済みの現実再現を意味しない。カメラとbaseの外部校正、servo位相、65/75度の現物版、softtip物性、cap寸法・質量は未確定。今回の成功は、明示した名目シーンと接触モデル内の結果である。</p>
<div class="cards">{card_html}</div><p>評価区間 9.000–11.000秒。接近誤差 {metrics["approach_position_error_m"] * 1000:.5f} mm。保持中の支持接触0、名目試行の全期間で禁止接触0、関節境界違反0、数値警告0。cap底面は傾斜を含む円筒の最下点から計算した。</p>
<h2>物理状態から描画した二視点動画</h2><p>動画は1 ms刻みの実mj_stepログから10 fpsで描画。映像用のpose再生は描画だけに使用し、把持判定は13,001点の生状態・接触forceによる。D405相当カメラは65度holder候補の光学中心・視線に配置した名目視点である。</p><div class="views">{nominal_video}</div>
{stage_html}
<h2>時系列と独立検証</h2><img src="media/timeseries.png" alt="底面離隔、左右接触力、grip frame漂移、接近誤差の時系列"><p>漂移グラフの表示範囲は0–8 mmで、把持前・解放後の範囲外の値は上端に切り詰めている。評価する保持区間の値はすべて表示範囲内で、生ログの数値は変更していない。</p><p>同seedの9系列はbit単位で完全一致。独立監査は実装の判定器をimportせず、生qposからFKと全保持指標を再計算し、9状態の接触力も別のmj_forwardで照合した。<a href="raw-audit-nominal-repeat.json">独立監査JSON</a> · <a href="study-results.json">比較試験と再現性JSON</a> · <a href="result.json">全結果JSON</a></p>
<h2>負の対照と成功域</h2><p>同一の最終経路でjawを開いたまま持ち上げると、capは支持面に残り、NO_GRIP / INSUFFICIENT_LIFTとなった。摩擦・質量の低高条件と、半分の時間刻みも実行した。</p><div class="views">{negative_video}</div>
<div class="scroll"><table><thead><tr><th>試行</th><th>判定</th><th>摩擦μ</th><th>質量 g</th><th>刻み ms</th><th>理由</th></tr></thead><tbody>{rows}</tbody></table></div>
<p>mass-lowは2秒の保持条件自体を達成した後、予定した2.5秒保持の終盤に滑り、異常停止したため全試行FAILUREとした。低摩擦の成功は主張しない。半刻み試験は底面最小36.436 mm、左右99.65%、漂移1.427 mmでSUCCESS。</p>
<h2>失敗からの修正</h2><ol><li>粗いmotor外接箱とframeの凸分解膨張が作る偽接触を、原CADのcase・horn・rail寸法で修正。禁止pairや閾値を削って回避していない。</li><li>外部Pythonの明示的な速度feedbackによる振動を、同じgain・力上限のMuJoCo implicit position servoへ移して解消。</li><li>nominal001–006では先端の傾斜面から滑り、幾何offsetや閉じ代では改善しなかった。MuJoCo 3.13の公式説明に従い、Newton/ellipticで接線と法線のconstraint impedance比を1から10へ変更した。摩擦μ0.7、cap1.5g、gain、力上限、判定契約は据え置き。NoSlip後処理は使用していない。</li></ol>
<p><a href="https://mujoco.readthedocs.io/en/3.13.0/modeling.html#preventing-slip">MuJoCo 3.13 Preventing slip</a>。接触のsoftnessとimpratioは未測定の名目数値モデルであり、実材料を校正した結果ではない。半刻みでも成功したが、保持中の漂移量は約0.76→1.43 mmと変化し、数値依存が残る。</p>
<h2>観測資料とモデルの範囲</h2><p>公開版には合成画像だけを含む。実写、会話、元archiveはローカル保存。下記観測推定は元成果物の記録であり、本パッケージから実写解析を再実行したという意味ではない。</p>
<p>独立depth解析はbox高さ49.35 mm、cap上面64.13 mm、baseからcapまで約177 mmを支持した。名目box50 mm、cap中心[0,180,57.5] mmをIK前に固定した。baseの+Y方向登録は仮定である。元画像の非ゼロRGB歪みは保持し、raw pixel/depthをbase座標として流用していない。</p>
<p>元R3 visual meshを変更せず、4つのarm jointとC7の非線形閉リンクを再利用した。C7は5つの機構座標にrank4の閉路拘束を持ち、独立jawは1自由度。6つの左右非対称scanfit外形を搭載し、未確認の内部coreは追加していない。capは重力下のfreejointで、weld・mocap・外力吊上げ・実行中のqpos書換はない。</p>
<div class="views"><figure><img src="media/grasp-source-closeup.png" alt="保持状態の原visual形状"><figcaption>10秒保持状態の原visual形状</figcaption></figure><figure><img src="media/grasp-proxy-closeup.png" alt="同じ保持状態の接触proxy"><figcaption>同一状態の接触proxy。開口と左右分離を保っている。</figcaption></figure></div><p>proxy誤差はmodel/proxy_report.jsonに保存。頂点サンプリング値は厳密なHausdorff上限ではなく、微小な穴やねじ頭の詳細は近似される。frameの0.5 mm機構隙間を元CADのrail面で復元し、motor全外接箱による偽接触をcaseとhornに分けて解消した。</p>
<p>腕の力上限1.0 Nm、jaw0.08 Nm。ROBOTISの瞬間stall値を連続定格と扱っていない。観測されていないケーブル全長、材質の真の変形、実機servo校正、製作・搭載安全性は今回未検証。</p>
<h2>実行と再生</h2><pre>uv sync --frozen\nMUJOCO_GL=egl uv run --no-sync python run.py --seed 0 --output results/replayed-nominal\nuv run --no-sync python evaluate.py results/replayed-nominal\nMUJOCO_GL=egl uv run --no-sync python report.py</pre><p>Python 3.12、MuJoCo 3.13.0、numpy 2.5.3、scipy 1.18.1、Pillow 12.3.0。依存の全解決結果はuv.lock。モデル・source入力・ログ・画像・動画をarchive内に同梱し、別のsource checkoutを要求しない。既存trialは上書きせず、新しいoutput名を使用する。</p>
<h2>今回のコードレビュー</h2><p>入力不足を外部checkoutから補わず、sourceとcacheのhashを検証する。隠れたcap支持・不正CLI値・中断を拒否/失敗記録する。今回の実動力学再実行と元trace比較は <a href="review-verification.json">検証JSON</a>。禁止接触0は宣言したpolicy内の結果であり、隣接body全体等の除外や未モデル化ケーブルを含む全実機可動域の安全保証ではない。</p>
<footer>オフラインシミュレーション専用。実機・camera・serialへの接続や通電は実行していない。判定基準・仮定はevaluation_contract.json / assumptions.json、失敗もresults内のraw logに保存。保存済みcontactは可逆gzip、評価器は直接読める。</footer></main></html>"""
    page = page.replace('href="raw-audit-nominal-repeat.json"', f'href="{audit_name}"')
    page = page.replace(
        "同seedの9系列はbit単位で完全一致。",
        "改善版はこのPC内の同seed再実行で9系列がbit単位で完全一致。元の別環境の軌跡とは一致せず、保持漂移0.759→1.385mmなどの差がある。再IKの微小丸め差が観測されたが因果は未隔離。",
    )
    page = page.replace("半刻み試験は底面最小", "元成果物の半刻み試験は底面最小")
    if nominal["status"] != "SUCCESS" or not audit["pass"]:
        raise ValueError("Cannot publish a success report for a failed or unaudited trial")
    (ROOT / "REPORT.html").write_text(page)
    print(
        "Report generated: REPORT.html, result.json, two-view MP4/PNG sequences and plots",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-render", action="store_true")
    main(parser.parse_args().skip_render)
