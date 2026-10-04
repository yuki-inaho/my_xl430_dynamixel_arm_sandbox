"""RGB-D capture and browser preview using an existing RealSense camera implementation."""

import argparse
import importlib.util
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pyrealsense2 as rs_module

# The SDK exports its enums from a binary extension without Python type stubs.
rs: Any = rs_module


def save_frame(camera, frame, args, output, *, received_at=None):
    output.mkdir(parents=True, exist_ok=False)
    images = {
        "color": frame.color,
        "depth": frame.depth,
        "aligned_depth": frame.aligned_depth,
        "ir_left": frame.ir_left,
        "ir_right": frame.ir_right,
    }
    for name, data in images.items():
        if data is None or not data.size or not cv2.imwrite(str(output / f"{name}.png"), data):
            raise RuntimeError(f"Invalid or unsaved {name}")
    profile = camera._rs_profile
    depth_scale = profile.get_device().first_depth_sensor().get_depth_scale()
    intrinsics = {}
    for name, stream in [("color", rs.stream.color), ("depth", rs.stream.depth)]:
        intr = profile.get_stream(stream).as_video_stream_profile().get_intrinsics()
        intrinsics[name] = dict(
            width=intr.width,
            height=intr.height,
            fx=intr.fx,
            fy=intr.fy,
            ppx=intr.ppx,
            ppy=intr.ppy,
            model=str(intr.model),
            coeffs=list(intr.coeffs),
        )
    ext = profile.get_stream(rs.stream.depth).get_extrinsics_to(profile.get_stream(rs.stream.color))
    metadata = dict(
        captured_at=datetime.now().astimezone().isoformat(),
        host_frame_received_at=received_at,
        device=camera.get_device_info(),
        requested_serial=args.serial,
        depth_scale_m_per_count=depth_scale,
        intrinsics=intrinsics,
        depth_to_color=dict(
            rotation_sdk_column_major=list(ext.rotation), translation_m=list(ext.translation)
        ),
        alignment_target="color",
        color_storage="BGR encoded by OpenCV to PNG",
        frameset_timestamp_ms=frame.timestamp,
        frameset_frame_number=frame.frame_index,
        per_stream_timestamps=None,
        fps=args.fps,
        robot_observation=None,
        streams=[
            dict(
                stream=str(p.stream_type()),
                index=p.stream_index(),
                fps=p.fps(),
                width=p.as_video_stream_profile().width(),
                height=p.as_video_stream_profile().height(),
            )
            for p in profile.get_streams()
            if p.is_video_stream_profile()
        ],
        shapes={name: list(data.shape) for name, data in images.items()},
        depth_dtype=str(frame.depth.dtype),
        aligned_depth_valid_fraction=float(
            np.count_nonzero(frame.aligned_depth) / frame.aligned_depth.size
        ),
    )
    (output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    camera.export_calibration(str(output / "calibration.toml"))
    depth_m = frame.aligned_depth.astype(np.float32) * depth_scale
    preview = cv2.applyColorMap(
        np.clip(depth_m * 255 / 2, 0, 255).astype(np.uint8), cv2.COLORMAP_TURBO
    )
    preview[frame.aligned_depth == 0] = 0
    cv2.imwrite(str(output / "depth_preview.png"), preview)
    return metadata


PAGE = """<!doctype html><html lang="ja"><meta charset="utf-8"><title>RealSense RGB-Dライブ</title>
<style>
body{font-family:sans-serif;margin:24px;background:#17212b;color:#edf3f7}
main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
img{width:100%}button,a{font-size:18px;color:inherit}
button{background:#286080;padding:12px;border:0}pre{white-space:pre-wrap}
</style>
<h1>RealSense RGB-Dライブ</h1><p>RGBと整列深度。深度の黒色は欠損、色は0〜2mの表示です。</p>
<main>
<section><h2>RGB</h2><img id="color" src="/color.mjpeg"></section>
<section><h2>深度</h2><img id="depth" src="/depth.mjpeg"></section>
</main>
<p><button onclick="capture()">現在のRGB-Dを保存</button></p>
<pre id="status"></pre><pre id="saved"></pre>
<script>
async function refresh(){
try{const s=await(await fetch('/status.json')).json();
document.getElementById('status').textContent=JSON.stringify(s,null,2)
}catch(e){document.getElementById('status').textContent=String(e)}}
async function capture(){const r=await fetch('/capture',{method:'POST'});
document.getElementById('saved').textContent=await r.text()}
setInterval(refresh,1000);refresh();
</script></html>"""


def serve(camera, args):
    import signal
    from collections import deque
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
    from threading import Condition, Event, Lock, Thread

    args.output.mkdir(parents=True, exist_ok=True)
    lock = Lock()
    condition = Condition(lock)
    state: dict[str, Any] = {}
    arrival_times = deque(maxlen=61)
    scale = camera._rs_profile.get_device().first_depth_sensor().get_depth_scale()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(args.output), **kw)

        def respond(self, content, mime, code=200):
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/color.mjpeg", "/depth.mjpeg"):
                self.stream_images(path.replace(".mjpeg", ".jpg"))
                return
            with lock:
                ready = "frame" in state
                if path in ("/color.jpg", "/depth.jpg") and ready:
                    content = state[path]
                elif path == "/status.json":
                    content = json.dumps(
                        dict(
                            serial=args.serial,
                            fps=args.fps,
                            size=state.get("size"),
                            acquisition_rate_hz=state.get("acquisition_rate_hz"),
                            frameset_frame_number=state.get("index"),
                            received_at=state.get("received_at"),
                            age_seconds=time.monotonic() - state.get("at", time.monotonic()),
                            depth_valid_fraction=state.get("valid"),
                            robot_observation=None,
                        )
                    ).encode()
                else:
                    content = None
            if path == "/":
                self.respond(PAGE.encode(), "text/html; charset=utf-8")
            elif content is not None:
                self.respond(
                    content, "application/json" if path.endswith(".json") else "image/jpeg"
                )
            elif path in ("/color.jpg", "/depth.jpg"):
                self.respond(b"Waiting for camera frame", "text/plain", 503)
            else:
                super().do_GET()

        def stream_images(self, image_key):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            last_index = None
            try:
                while True:
                    with condition:
                        ready = condition.wait_for(
                            lambda: (
                                state.get("closing")
                                or (image_key in state and state.get("index") != last_index)
                            ),
                            timeout=5,
                        )
                        if not ready or state.get("closing"):
                            return
                        jpeg, last_index = state[image_key], state["index"]
                    self.wfile.write(
                        b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                        + str(len(jpeg)).encode()
                        + b"\r\n\r\n"
                        + jpeg
                        + b"\r\n"
                    )
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return

        def do_POST(self):
            if self.path != "/capture":
                self.respond(b"Not found", "text/plain", 404)
                return
            length = int(self.headers.get("Content-Length", 0))
            request = json.loads(self.rfile.read(length)) if length else {}
            not_before = request.get("not_before_unix_s", 0)
            with condition:
                condition.wait_for(lambda: state.get("received_unix_s", 0) >= not_before, timeout=2)
                frame = state.get("frame")
                age = time.monotonic() - state.get("at", 0)
                received_at = state.get("received_at")
                fresh_enough = state.get("received_unix_s", 0) >= not_before
            if frame is None or age > 2 or not fresh_enough:
                self.respond(b"No fresh frame", "text/plain", 503)
                return
            output = args.output / datetime.now().astimezone().strftime("capture-%Y%m%d-%H%M%S-%f")
            try:
                metadata = save_frame(camera, frame, args, output, received_at=received_at)
                self.respond(
                    json.dumps(dict(path=str(output), metadata=metadata)).encode(),
                    "application/json",
                )
            except Exception as error:
                self.respond(str(error).encode(), "text/plain", 500)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", args.serve_port), Handler)
    server.daemon_threads = True
    Thread(target=server.serve_forever, daemon=True).start()
    # Do not unwind Python/native SDK image processing on a signal. Finish the
    # current frame, then close HTTP and the camera through their normal finally.
    stop = Event()
    previous = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    for s in previous:
        signal.signal(s, lambda *_: stop.set())
    print(f"Live camera: http://127.0.0.1:{args.serve_port}", flush=True)
    try:
        while not stop.is_set():
            frame = camera.grab()
            received = datetime.now().astimezone()
            depth_m = frame.aligned_depth.astype(np.float32) * scale
            depth = cv2.applyColorMap(
                np.clip(depth_m * 255 / 2, 0, 255).astype(np.uint8), cv2.COLORMAP_TURBO
            )
            depth[frame.aligned_depth == 0] = 0
            rgb_ok, rgb_jpg = cv2.imencode(".jpg", frame.color, [cv2.IMWRITE_JPEG_QUALITY, 85])
            depth_ok, depth_jpg = cv2.imencode(".jpg", depth, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not rgb_ok or not depth_ok:
                raise RuntimeError("Preview encoding failed")
            with condition:
                arrival_times.append(time.monotonic())
                rate = (
                    ((len(arrival_times) - 1) / (arrival_times[-1] - arrival_times[0]))
                    if len(arrival_times) > 1
                    else None
                )
                state.update(
                    frame=frame,
                    index=frame.frame_index,
                    at=arrival_times[-1],
                    size=[frame.color.shape[1], frame.color.shape[0]],
                    acquisition_rate_hz=rate,
                    received_at=received.isoformat(),
                    received_unix_s=received.timestamp(),
                    valid=float(np.count_nonzero(frame.aligned_depth) / frame.aligned_depth.size),
                )
                state["/color.jpg"] = rgb_jpg.tobytes()
                state["/depth.jpg"] = depth_jpg.tobytes()
                condition.notify_all()
    finally:
        with condition:
            state["closing"] = True
            condition.notify_all()
        server.shutdown()
        server.server_close()
        for s, handler in previous.items():
            signal.signal(s, handler)


def start_camera(camera, profiles):
    """Reuse acquisition, but configure only options the selected sensor supports."""
    camera._rs_profile = camera._pipeline.start(camera._config)
    camera._is_started = True  # close must stop the pipeline even if option setup fails
    camera._device = camera._rs_profile.get_device()
    sensor = camera._device.first_depth_sensor()
    settings = (
        (rs.option.visual_preset, profiles[camera._profile]),
        (rs.option.laser_power, camera._laser_power),
        (rs.option.emitter_enabled, 1),
    )
    for option, value in settings:
        if sensor.supports(option):
            sensor.set_option(option, value)
    camera._emitter_enabled = sensor.supports(rs.option.emitter_enabled)
    camera._emitter_alternate = False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--warmup", type=float, default=3.0)
    parser.add_argument("--serve-port", type=int, help="Serve a live browser preview on localhost")
    args = parser.parse_args()
    # Load only the existing camera module, independently of this workspace's scripts.
    sys.path.insert(0, str(args.capture_project.resolve()))
    spec = importlib.util.spec_from_file_location(
        "reused_realsense_device", args.capture_project / "scripts/realsense_device.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Existing camera module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    camera = module.RealSenseDevice(args.width, args.height, args.fps)
    try:
        camera.open()
        camera._config.enable_device(args.serial)
        start_camera(camera, module.PROFILE_MAP)
        if args.serve_port:
            serve(camera, args)
            return
        until = time.monotonic() + args.warmup
        while True:
            frame = camera.grab()
            received_at = datetime.now().astimezone().isoformat()
            if time.monotonic() >= until:
                break
        print(
            json.dumps(
                save_frame(camera, frame, args, args.output, received_at=received_at),
                ensure_ascii=False,
            )
        )
    finally:
        camera.close(hardware_reset=False)


if __name__ == "__main__":
    main()
