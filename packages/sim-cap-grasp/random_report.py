"""Replay saved physics states as two-view evidence; never a new physics trial."""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys

os.environ.setdefault("MUJOCO_GL", "egl")
import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from build_scene import ROOT, save_json, sha

MEDIA = ROOT / "media"
FONT = "DejaVuSans.ttf"


def selections(name):
    index = json.loads((ROOT / "results" / name / "index.json").read_text())
    audit = json.loads((ROOT / "evidence" / f"independent-{name}.json").read_text())
    rows = index["trials"]
    outer = max(rows, key=lambda row: math.hypot(*row["target_m"][:2]))
    transfer = max(
        audit["trials"],
        key=lambda row: row["transfer_diagnostics_non_gating"][
            "cap_center_speed_before_box_contact_m_s"
        ],
    )
    return [
        ("representative", "事前に選ばれた最初の評価配置", rows[0]["run_dir"]),
        ("outer-boundary", "評価配置の最大半径側", outer["run_dir"]),
        (
            "transfer-limit",
            "下降時の接触消失の例（最大着地前速度）",
            transfer["trial"],
        ),
        ("negative", "負の対照：jawを閉じない", "results/review-random-fast-no-close"),
        (
            "historical-failure",
            "前バッチの実失敗：閉動作後に把持を成立できず早期停止",
            "results/qualification-001/qualification-001-t018",
        ),
    ]


def render(label, title, relative):
    directory = ROOT / relative
    result = json.loads((directory / "result.json").read_text())
    metadata = json.loads((directory / "metadata.json").read_text())
    with np.load(directory / "states.npz", allow_pickle=False) as archive:
        states = {key: archive[key] for key in archive.files}
    model = mujoco.MjModel.from_xml_path(str(directory / "scene.xml"))
    data = mujoco.MjData(model)
    renderer = mujoco.Renderer(model, 360, 640)
    option = mujoco.MjvOption()
    option.geomgroup[3:] = 0
    target = metadata["initial_cap_center_m"]
    camera = mujoco.MjvCamera()
    camera.lookat[:] = [target[0] * 0.35, target[1] * 0.35, 0.125]
    camera.distance = 0.50 + 0.35 * math.hypot(*target[:2])
    camera.azimuth = math.degrees(math.atan2(target[1], target[0])) + 45
    camera.elevation = -24
    output = MEDIA / label
    output.mkdir(parents=True, exist_ok=True)
    final = float(states["time"][-1])
    times = list(np.arange(0, final - 1e-6, 0.1)) + [final]
    font = ImageFont.truetype(FONT, 14)
    provenance = []
    for frame, time in enumerate(times):
        i = int(np.argmin(np.abs(states["time"] - time)))
        data.qpos[:] = states["qpos"][i]
        data.qvel[:] = states["qvel"][i]
        data.ctrl[:] = states["ctrl"][i]
        mujoco.mj_forward(model, data)
        for view, selected in [("external", camera), ("wrist", "wrist_d405")]:
            path = output / f"{view}-{frame:04d}.png"
            renderer.update_scene(data, camera=selected, scene_option=option)
            picture = Image.fromarray(renderer.render())
            draw = ImageDraw.Draw(picture)
            draw.rectangle((0, 0, 640, 44), fill="#142c3d")
            draw.text(
                (9, 4),
                f"{view.upper()} | t={states['time'][i]:.3f}s | {states['phase'][i]} | {result['status']}",
                font=font,
                fill="white",
            )
            draw.text(
                (9, 24),
                f"{label}  x={target[0] * 1000:.1f} y={target[1] * 1000:.1f} mm  (nominal simulation)",
                font=font,
                fill="#c8e9ef",
            )
            picture.save(path)
            provenance.append(
                {
                    "view": view,
                    "frame": frame,
                    "sample": i,
                    "simulation_time_s": float(states["time"][i]),
                    "phase": str(states["phase"][i]),
                    "file": str(path.relative_to(ROOT)),
                }
            )
        if frame % 50 == 0:
            print("RENDER", label, frame, "/", len(times), flush=True)
    renderer.close()
    videos = {}
    for view in ("external", "wrist"):
        video = output / f"{view}.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-framerate",
                "10",
                "-i",
                str(output / f"{view}-%04d.png"),
                "-c:v",
                "libx264",
                "-threads",
                "1",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "23",
                "-movflags",
                "+faststart",
                str(video),
            ],
            check=True,
        )
        videos[view] = str(video.relative_to(ROOT))
    keyframes = {}
    for name, phase, time in [
        ("standby", "settle", 0),
        ("approach", "approach", 5.4),
        ("closed", "close", 7.9),
        ("hold", "hold", 12.4),
        ("lower", "lower", 14.0),
        ("released", "release", 16.9),
        ("returned", "standby_final", 22.8),
    ]:
        available = [x for x in provenance if x["phase"] == phase and x["view"] == "external"]
        if available:
            entry = min(available, key=lambda row: abs(row["simulation_time_s"] - time))
            keyframes[name] = {
                view: str((output / f"{view}-{entry['frame']:04d}.png").relative_to(ROOT))
                for view in ("external", "wrist")
            }
    record = {
        "label": label,
        "title": title,
        "trial": relative,
        "status": result["status"],
        "videos": videos,
        "keyframes": keyframes,
        "source_states_sha256": sha(directory / "states.npz"),
        "source_scene_sha256": sha(directory / "scene.xml"),
        "frames_per_view": len(times),
        "render_fps": 10,
        "physics_timestep_s": model.opt.timestep,
        "simulation_duration_s": final,
        "external_camera": {
            "lookat": camera.lookat.tolist(),
            "distance": float(camera.distance),
            "azimuth": float(camera.azimuth),
            "elevation": float(camera.elevation),
        },
        "wrist_camera": "Source65deg nominal D405-equivalent; uncalibrated hardware optics",
        "provenance": "Raw mj_step state replay for visualization only; qpos writes here are rendering, not dynamics or evaluation",
    }
    save_json(output / "frame-provenance.json", {"metadata": record, "frames": provenance})
    print("RENDER COMPLETE", label, flush=True)
    return record


def main():
    global MEDIA
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-only", action="store_true")
    parser.add_argument("--html-only", action="store_true")
    parser.add_argument("--name", default="qualification-001")
    args = parser.parse_args()
    MEDIA = ROOT / "media" / f"random-{args.name}"
    MEDIA.mkdir(parents=True, exist_ok=True)
    if not args.html_only:
        if not shutil.which("ffmpeg"):
            raise RuntimeError(
                "Required ffmpeg encoder unavailable; do not substitute invented evidence"
            )
        records = []
        for label, title, relative in selections(args.name):
            records.append(render(label, title, relative))
            save_json(MEDIA / "manifest.json", records)
    if not args.render_only:
        import report_ui

        sys.argv = ["report_ui.py", "--name", args.name]
        report_ui.main()


if __name__ == "__main__":
    main()
