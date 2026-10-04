"""Local FK viewer. No telemetry bridge, motor SDK or serial input."""

import argparse
import copy
import json
import logging
import mimetypes
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")
import cv2
import mujoco
import numpy as np

from .demo import camera_for, checked_angles, fk_state
from .model import ROOT, load_scene, numeric_vector

LOGGER = logging.getLogger(__name__)


def advance_display(current, target, max_step_deg):
    current, target = numeric_vector(current, 4), numeric_vector(target, 4)
    step = numeric_vector([max_step_deg], 1)[0]
    if step <= 0 or step > 0.5:
        raise ValueError("Display step must be 0..0.5 degrees")
    delta = target - current
    peak = float(np.max(np.abs(delta)))
    return (current + delta * min(1.0, step / peak)).tolist() if peak else current.tolist()


class Preview:
    def __init__(self, output, start_renderer=True):
        self.output = Path(output)
        self.manifest = json.loads((self.output / "model-manifest.json").read_text())
        self.cfg = self.manifest["spec"]
        self.model = load_scene(output)
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.jpg = None
        self.state = {
            **fk_state(self.model, self.cfg["seed_deg"]),
            "target_angles_deg": self.cfg["seed_deg"],
            "view": "iso",
            "paused": False,
            "frame_seq": 0,
            "error": None,
            "model": self.cfg["configuration"],
            "fixed_visuals": self.manifest.get("fixed_visuals", []),
            "source_cad_sha256": self.manifest["source_cad_sha256"],
            "display_ranges_deg": self.cfg["demo_ranges_deg"],
            "presets": self.cfg["poses"],
        }
        if start_renderer:
            self.thread = threading.Thread(target=self.render_loop, daemon=True)
            self.thread.start()

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.state)

    def update(self, payload):
        if (
            not isinstance(payload, dict)
            or not payload
            or set(payload) - {"angles_deg", "view", "paused"}
        ):
            raise ValueError("Only angles_deg, view, paused are supported")
        checked = {}
        if "angles_deg" in payload:
            checked["target_angles_deg"] = checked_angles(
                self.model, payload["angles_deg"]
            ).tolist()
        if "view" in payload:
            if payload["view"] not in {"iso", "side", "front", "top"}:
                raise ValueError("Unknown view")
            checked["view"] = payload["view"]
        if "paused" in payload:
            if type(payload["paused"]) is not bool:
                raise ValueError("Boolean paused required")
            checked["paused"] = payload["paused"]
        with self.lock:
            if checked.get("paused") is True:
                # Stop consumes the target; resume cannot unexpectedly restart an old transition.
                checked["target_angles_deg"] = self.state["angles_deg"].copy()
            self.state.update(checked)
        return self.snapshot()

    def render_loop(self):
        renderer = None
        try:
            renderer = mujoco.Renderer(self.model, height=760, width=1060)
            data = mujoco.MjData(self.model)
            fps = self.cfg["display"]["fps"]
            while not self.stop.is_set():
                start = time.monotonic()
                with self.lock:
                    if not self.state["paused"]:
                        angles = advance_display(
                            self.state["angles_deg"],
                            self.state["target_angles_deg"],
                            self.cfg["display"]["max_frame_step_deg"],
                        )
                        self.state.update(fk_state(self.model, angles))
                    state = copy.deepcopy(self.state)
                data.qpos[:] = np.radians(state["angles_deg"])
                mujoco.mj_forward(self.model, data)
                renderer.update_scene(data, camera=camera_for(state["view"]))
                rgb = renderer.render()
                ok, jpeg = cv2.imencode(
                    ".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88]
                )
                if not ok:
                    raise OSError("MuJoCo frame encoding failed")
                with self.lock:
                    self.jpg = jpeg.tobytes()
                    self.state["frame_seq"] += 1
                self.stop.wait(max(0, 1 / fps - (time.monotonic() - start)))
        except Exception as exc:
            LOGGER.exception("MuJoCo renderer stopped")
            with self.lock:
                self.state["error"] = str(exc)
        finally:
            if renderer is not None:
                renderer.close()


def handler_for(viewer):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send_bytes(self, status, data, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/favicon.ico":
                self.send_bytes(204, b"", "image/x-icon")
            elif path == "/":
                self.send_bytes(
                    200,
                    Path(__file__).with_name("index.html").read_bytes(),
                    "text/html; charset=utf-8",
                )
            elif path == "/api/state":
                self.send_bytes(
                    200, json.dumps(viewer.snapshot(), allow_nan=False).encode(), "application/json"
                )
            elif path == "/frame.jpg":
                with viewer.lock:
                    image = viewer.jpg
                self.send_bytes(
                    200 if image else 503,
                    image or b"Frame not ready",
                    "image/jpeg" if image else "text/plain",
                )
            elif path == "/spec":
                self.send_response(302)
                self.send_header("Location", "/docs/CURRENT_ARM_SPEC.html")
                self.send_header("Content-Length", "0")
                self.end_headers()
            elif (
                path.startswith(
                    (
                        "/docs/",
                        "/outputs/urdf-fk-r3-20261004-r2/",
                        "/outputs/arm-current-audit-20261003/",
                        "/references/arm-r3/",
                        "/simulation/urdf_fk/",
                        "/skills/urdf-mujoco-fk/",
                        "/temp/photo-version-check_20261003/",
                    )
                )
                or path == "/specs/urdf_fk_r3.json"
            ):
                requested = (ROOT / path.lstrip("/")).resolve()
                allowed = requested.is_relative_to(ROOT) and (
                    "/" + requested.relative_to(ROOT).as_posix() == path
                )
                if allowed and requested.is_file():
                    mime = mimetypes.guess_type(requested.name)[0] or "application/octet-stream"
                    self.send_bytes(200, requested.read_bytes(), mime)
                else:
                    self.send_bytes(404, b"Not found", "text/plain")
            elif path == "/current-arm-spec.css":
                self.send_bytes(200, (ROOT / "docs/current-arm-spec.css").read_bytes(), "text/css")
            elif path.startswith("/images/current-arm-20261004/"):
                name = path.rsplit("/", 1)[1]
                p = ROOT / "docs/images/current-arm-20261004" / name
                if name in {x.name for x in p.parent.glob("*")} and p.is_file():
                    mime = "image/png" if p.suffix == ".png" else "image/jpeg"
                    self.send_bytes(200, p.read_bytes(), mime)
                else:
                    self.send_bytes(404, b"Not found", "text/plain")
            else:
                self.send_bytes(404, b"Not found", "text/plain")

        def do_POST(self):
            if self.path != "/api/state":
                self.send_bytes(404, b"Not found", "text/plain")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 16384:
                    raise ValueError("Invalid request length")
                result = viewer.update(json.loads(self.rfile.read(length)))
                self.send_bytes(
                    200, json.dumps(result, allow_nan=False).encode(), "application/json"
                )
            except (ValueError, TypeError, KeyError) as exc:
                self.send_bytes(400, json.dumps({"error": str(exc)}).encode(), "application/json")

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18104)
    args = parser.parse_args()
    viewer = Preview(args.output)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(viewer))
    print(f"FK simulation: http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        viewer.stop.set()
        viewer.thread.join(timeout=5)


if __name__ == "__main__":
    main()
