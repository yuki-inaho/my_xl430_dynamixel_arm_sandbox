"""Local MuJoCo rendering server. Kinematics only; no motor/serial code.

Optional input is the readonly observer's existing v2 JSONL, never a command.
Verified calibration is required to render that telemetry as CAD joint angles.
"""

import argparse
import json
import math
import os
import sys
import threading
import time
from dataclasses import asdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import direction_observation
import live_input

os.environ.setdefault("MUJOCO_GL", "egl")
import cv2
import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "outputs/current-arm-mujoco-20261003"
STATIC = Path(__file__).with_name("index.html")
OBSERVATION_DIR = MODEL_DIR / "direction-observations"
# Display intervals only; they do not certify collision-free hardware motion.
# The elbow must include the folded physical pose, which is outside +/-60 degrees.
RANGES = live_input.RANGES


def write_exclusive(target, data):
    """Create target exclusively; a failed write never leaves a partial evidence file."""
    file = target.open("xb")
    try:
        with file:
            file.write(data)
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def evidence_name():
    return "observation_" + datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%f") + ".json"


def finite(value, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("finite numeric value required")
    if not lo <= value <= hi:
        raise ValueError(f"value outside display interval [{lo}, {hi}]")
    return float(value)


def apply_kinematic_pose(model, data, angles, theta_deg):
    """Place the four arm axes and exact nonlinear C7 closure; no mj_step."""
    if theta_deg is None:
        for j, angle in enumerate(angles, 1):
            data.qpos[model.jnt_qposadr[model.joint(f"cad_j{j}").id]] = math.radians(angle)
        mujoco.mj_forward(model, data)
        return None  # uninstalled mechanism: no synthetic jaw angle or opening metric
    theta = math.radians(theta_deg)
    x0 = math.sqrt(24**2 - 14**2)
    x = 14 * math.cos(theta) + math.sqrt(24**2 - (14 * math.sin(theta)) ** 2)
    for j, angle in enumerate(angles, 1):
        data.qpos[model.jnt_qposadr[model.joint(f"cad_j{j}").id]] = math.radians(angle)
    for name, value in [
        ("gripper_delta", theta - math.pi / 2),
        ("slider_R", (x - x0) / 1000),
        ("slider_L", -(x - x0) / 1000),
    ]:
        data.qpos[model.jnt_qposadr[model.joint(name).id]] = value
    mujoco.mj_forward(model, data)
    fixed = model.body("c7_fixed").id
    rotation = data.xmat[fixed].reshape(3, 3)
    phi = math.atan2(-14 * math.sin(theta), x - 14 * math.cos(theta))
    delta = phi - math.atan2(-14, x0)
    local = np.array(
        [[math.cos(delta), -math.sin(delta), 0], [math.sin(delta), math.cos(delta), 0], [0, 0, 1]]
    )
    quat = np.zeros(4)
    mujoco.mju_mat2Quat(quat, (rotation @ local).reshape(-1))
    for side, sign in [("R", 1), ("L", -1)]:
        mocap = model.body_mocapid[model.body("c7_link_" + side).id]
        pin = sign * np.array([14 * math.cos(theta), 14 * math.sin(theta), 0]) / 1000
        data.mocap_pos[mocap] = data.xpos[fixed] + rotation @ pin
        data.mocap_quat[mocap] = quat
    mujoco.mj_forward(model, data)
    return x


class Viewer:
    def __init__(self, telemetry=None, calibration=None, live_url=None):
        if telemetry and live_url:
            raise ValueError("Choose live bridge or file input")
        self.lock = threading.Lock()
        self.state = {
            "angles": [0.0] * 4,
            "theta": 90.0,
            "variant": "r5_65",
            "gripper": True,
            "camera": True,
            "animate": False,
            "azimuth": 225.0,
            "elevation": -25.0,
            "distance": 0.64,
            "focus": "arm",
            "source": "manual",
            "frame_seq": 0,
            "render_fps": 0.0,
            "frame_time": None,
            "error": None,
            "telemetry": {"configured": bool(telemetry or live_url), "status": "未接続", "motors": []},
            "live_available": bool(live_url),
            "direction_observation": {"before": None, "result": None, "saved_path": None},
            "calibration": {"verified": False, "status": "未校正", "cad_sha256":
                json.loads((MODEL_DIR / "model-provenance.json").read_text())["source_cad_sha256"]},
        }
        self.telemetry = Path(telemetry) if telemetry else None
        self.calibration = self.read_calibration(calibration) if calibration else None
        self.bridge = live_input.BridgeClient(live_url) if live_url else None
        self.direction_start = None
        if self.bridge:
            self.bridge.start_polling()
        self.jpg = None
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.render_loop, daemon=True)
        self.thread.start()

    @staticmethod
    def read_calibration(path):
        cal = json.loads(Path(path).read_text())
        provenance = json.loads((MODEL_DIR / "model-provenance.json").read_text())
        if (
            cal.get("physical_order_verified") is not True
            or cal.get("calibration_verified") is not True
        ):
            raise ValueError("Calibration and physical ID order must be explicitly verified")
        if cal.get("cad_sha256") != provenance["source_cad_sha256"]:
            raise ValueError("Calibration CAD revision mismatch")
        entries = cal["joints"]
        if len(entries) != 5 or [x["role"] for x in entries] != ["J1", "J2", "J3", "J4", "PG3"]:
            raise ValueError("Five ordered, named calibration entries required")
        ids = [x["motor_id"] for x in entries]
        if len(set(ids)) != 5 or any(type(x) is not int or not 0 <= x <= 252 for x in ids):
            raise ValueError("Invalid or duplicate motor IDs")
        for entry in entries:
            if (
                type(entry["sign"]) is not int
                or entry["sign"] not in (-1, 1)
            ):
                raise ValueError("Measured direction required")
            live_input.joint_reference(entry)
        if type(cal.get("simulated")) is not bool or not isinstance(cal.get("context"), dict):
            raise ValueError("Saved calibration requires explicit source and bound context")
        return live_input.validate_calibration(cal, MODEL_DIR)

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.state))

    def update(self, payload):
        allowed = {
            "angles",
            "theta",
            "variant",
            "gripper",
            "camera",
            "animate",
            "azimuth",
            "elevation",
            "distance",
            "source",
            "focus",
        }
        if not isinstance(payload, dict) or set(payload) - allowed:
            raise ValueError("Unknown state field")
        checked = {}
        if "angles" in payload:
            a = payload["angles"]
            if not isinstance(a, list) or len(a) != 4:
                raise ValueError("Four CAD angles required")
            checked["angles"] = [finite(v, *bounds) for v, bounds in zip(a, RANGES)]
        for key, limits in {
            "theta": (25, 135),
            "azimuth": (-720, 720),
            "elevation": (-89, 0),
            "distance": (0.22, 1.5),
        }.items():
            if key in payload:
                checked[key] = finite(payload[key], *limits)
        for key in ("gripper", "camera", "animate"):
            if key in payload:
                if type(payload[key]) is not bool:
                    raise ValueError("Boolean required")
                checked[key] = payload[key]
        if "variant" in payload:
            if payload["variant"] not in ("r5_65", "compact_75"):
                raise ValueError("Unknown holder candidate")
            checked["variant"] = payload["variant"]
        if "focus" in payload:
            if payload["focus"] not in ("arm", "gripper"):
                raise ValueError("Unknown camera focus")
            checked["focus"] = payload["focus"]
        if "source" in payload:
            if payload["source"] not in ("manual", "telemetry"):
                raise ValueError("Unknown input source")
            if payload["source"] == "telemetry" and not (
                (self.telemetry or self.bridge) and self.calibration
            ):
                raise ValueError("実機姿勢の表示にはREAD入力と確認済み校正が必要です")
            checked["source"] = payload["source"]
        with self.lock:
            source = checked.get("source", self.state["source"])
            if source == "telemetry" and (set(checked) & {"angles", "theta", "animate"}):
                raise ValueError("実機表示中は画面から姿勢を書き換えません")
            if (source == "telemetry" and self.calibration
                and live_input.end_effector(self.calibration) == "bare"):
                if checked.get("gripper") or checked.get("camera"):
                    raise ValueError("裸アーム校正では爪とホルダーは未装着です")
                checked.update(gripper=False, camera=False)
            if source == "manual" and self.state.get("theta") is None and "theta" not in checked:
                checked["theta"] = 90.0  # manual example only, never saved as calibration
            self.state.update(checked)

    def read_telemetry(self):
        if getattr(self, "bridge", None):
            with self.lock:
                cal = self.calibration
            status = live_input.telemetry_status(self.bridge.snapshot(), cal, MODEL_DIR)
            if status.get("calibration_invalid"):
                with self.lock:
                    if self.calibration is cal:
                        self.calibration = None
                        self.state["calibration"].update(verified=False, status=status["status"])
            return status
        if self.telemetry is None:
            return None
        try:
            # Whole JSONL frames only; a partially written last line is ignored.
            # Bounded tail reads keep long-running observers from growing render latency.
            with self.telemetry.open("rb") as stream:
                stream.seek(0, 2)
                offset = max(0, stream.tell() - 262144)
                stream.seek(offset)
                if offset:
                    stream.readline()  # skip a possibly truncated first event
                text = stream.read().decode("utf-8")
            lines = text.splitlines()
            if text and not text.endswith("\n"):
                lines = lines[:-1]
            events = [json.loads(line) for line in lines if line.strip()]
            frames = [
                e["frame"]
                for e in events
                if e.get("schema_version") == 2 and e.get("kind") == "frame"
            ]
            if not frames:
                return {"status": "フレーム待ち", "motors": []}
            if events and events[-1].get("kind") == "end":
                return {
                    "status": "READログ終了",
                    "motors": frames[-1]["motors"],
                    "can_render": False,
                }
            frame = frames[-1]
            age = time.time() - datetime.fromisoformat(frame["finished_at"]).timestamp()
            motors = frame["motors"]
            ids = [motor["motor_id"] for motor in motors]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate motor IDs in READ frame")
            valid = 0 <= age < 1.0 and all(
                type(m["position_counts"]) is int
                and -(2**31) <= m["position_counts"] < 2**31
                and not m.get("faults")
                and not m.get("device_alert")
                and m.get("hardware_error") == 0
                for m in motors
            )
            result = {
                "status": "READ入力・未校正" if valid else "欠測・期限超過",
                "age_seconds": age,
                "motors": motors,
                "can_render": False,
            }
            if valid and self.calibration:
                metadata = [e for e in events if e.get("schema_version") == 2
                            and e.get("kind") == "metadata"]
                if not metadata:
                    result["status"] = "READ入力・source/session未確認（描画停止）"
                    return result
                meta = metadata[-1]
                snapshot = {"state": "running", "port_closed": False, "error": None,
                            "session_id": meta.get("acquisition_id"),
                            "simulated": meta.get("simulated"), "metadata": meta,
                            "frame": {"kind": "frame", "schema_version": 2, "frame": frame}}
                try:
                    angles, theta = live_input.convert_pose(self.calibration, snapshot, MODEL_DIR)
                except (ValueError, KeyError, TypeError):
                    self.calibration = None
                    raise
                result.update(
                    status="READ入力・校正済み", can_render=True, angles=angles, theta=theta,
                    simulated=snapshot["simulated"], end_effector=live_input.end_effector(self.calibration),
                )
            return result
        except (OSError, ValueError, KeyError, TypeError) as e:
            return {"status": "入力エラー", "error": str(e), "motors": [], "can_render": False}

    def live_action(self, path, payload):
        if self.bridge is None:
            raise ValueError("Live bridge is not configured")
        if path.startswith("/api/direction/"):
            return self.observe_direction(path, payload)
        if path == "/api/live/start":
            if not isinstance(payload, dict) or set(payload) != {"duration_seconds"}:
                raise ValueError("Duration required")
            live_input.numeric(payload["duration_seconds"], 0, 86400)
            return self.bridge.request("/api/start", payload)
        if path == "/api/live/stop":
            if payload != {}:
                raise ValueError("Empty stop payload required")
            return self.bridge.request("/api/stop", {})
        if path != "/api/calibration":
            raise ValueError("Unknown live action")
        cal = live_input.bind_calibration(payload, self.bridge.snapshot(), MODEL_DIR)
        # A newly calibrated sample must also be representable before applying it.
        live_input.convert_pose(cal, self.bridge.snapshot(), MODEL_DIR)
        folder = MODEL_DIR / ("calibration-test" if cal["simulated"] else "calibration")
        folder.mkdir(exist_ok=True)
        target = folder / ("calibration_" + datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%f") + ".json")
        target.write_text(json.dumps(cal, ensure_ascii=False, indent=2) + "\n")
        with self.lock:
            self.calibration = cal
            self.state["calibration"].update(
                verified=True, status="試験用校正" if cal["simulated"] else "現物確認済み",
                saved_path=str(target),
            )
            self.state.update(source="telemetry", animate=False)
            if live_input.end_effector(cal) == "bare":
                self.state.update(gripper=False, camera=False)
        return {"saved_path": str(target)}

    def observe_direction(self, path, payload):
        if path == "/api/direction/before":
            return self.direction_before(payload)
        if not isinstance(payload, dict):
            raise TypeError("Object required")
        if path != "/api/direction/after" or set(payload) != {"physical_change_confirmed"}:
            raise ValueError("Physical change confirmation required")
        return self.direction_after(payload)

    def direction_before(self, payload):
        empty = {"before": None, "result": None, "saved_path": None}
        try:
            if not isinstance(payload, dict):
                raise TypeError("Object required")
            if set(payload) != {"motor_id", "physical_confirmed"}:
                raise ValueError("Motor ID and physical confirmation required")
            sample = direction_observation.capture(
                self.bridge.snapshot(), payload["motor_id"], payload["physical_confirmed"], MODEL_DIR
            )
        except Exception:
            # A failed re-capture must not leave an older baseline silently active.
            with self.lock:
                self.direction_start = None
                self.state["direction_observation"] = empty
            raise
        with self.lock:
            self.direction_start = sample
            self.state["direction_observation"] = {**empty, "before": asdict(sample)}
        return {"before": asdict(sample)}

    def direction_after(self, payload):
        with self.lock:
            baseline = self.direction_start
        observed = direction_observation.compare(
            baseline, self.bridge.snapshot(), payload["physical_change_confirmed"], MODEL_DIR
        )
        record = asdict(observed)
        # Encode first: an unencodable record fails before any file exists.
        data = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        folder = OBSERVATION_DIR / ("synthetic" if observed.before.simulated else "hardware")
        with self.lock:
            # Check before writing so a rejected request never leaves evidence behind.
            if self.direction_start is not baseline:
                raise ValueError("Baseline changed during observation; retry the observation")
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / evidence_name()
            write_exclusive(target, data)
            # One confirmed opening yields one record; a new observation needs a new baseline.
            self.direction_start = None
            self.state["direction_observation"] = {
                "before": None, "result": record, "saved_path": str(target),
            }
        return {"result": record, "saved_path": str(target)}

    def render_loop(self):
        renderer = None
        try:
            m = mujoco.MjModel.from_xml_path(str(MODEL_DIR / "scene.xml"))
            d = mujoco.MjData(m)
            renderer = mujoco.Renderer(m, height=760, width=1060)
            camera = mujoco.MjvCamera()
            option = mujoco.MjvOption()
            frames, start = 0, time.monotonic()
            while not self.stop.is_set():
                tick = time.monotonic()
                live = self.read_telemetry()
                with self.lock:
                    if live is not None:
                        self.state["telemetry"] = {"configured": True, **live}
                    if self.state["source"] == "telemetry":
                        self.state["animate"] = False
                        if live and live.get("can_render"):
                            self.state["angles"] = live["angles"]
                            self.state["theta"] = live["theta"]
                            if live.get("end_effector") == "bare":
                                self.state.update(gripper=False, camera=False)
                        else:
                            # Preserve the last frame, explicitly marked stale; never substitute zero.
                            self.state["error"] = (
                                "実機データが欠測・未校正です。描画は最後の姿勢を保持しています。"
                            )
                    elif self.state["animate"]:
                        t = time.monotonic() - start
                        self.state["angles"] = [
                            20 * math.sin(t * 0.5),
                            12 * math.sin(t * 0.4),
                            20 * math.sin(t * 0.6),
                            15 * math.sin(t * 0.7),
                        ]
                        self.state["theta"] = 80 + 35 * math.sin(t * 0.5)
                    state = json.loads(json.dumps(self.state))
                x = apply_kinematic_pose(m, d, state["angles"], state["theta"])
                option.geomgroup[:] = [
                    1,
                    int(state["gripper"]),
                    int(state["camera"] and state["variant"] == "r5_65"),
                    int(state["camera"] and state["variant"] == "compact_75"),
                    0,
                    0,
                ]
                if state["focus"] == "gripper":
                    fixed = m.body("c7_fixed").id
                    camera.lookat[:] = d.xpos[fixed] + d.xmat[fixed].reshape(3, 3) @ [0, 0, 0.03]
                else:
                    camera.lookat[:] = [0, 0.12, 0.14]
                camera.azimuth = state["azimuth"]
                camera.elevation = state["elevation"]
                camera.distance = state["distance"]
                renderer.update_scene(d, camera=camera, scene_option=option)
                rgb = renderer.render()
                ok, encoded = cv2.imencode(
                    ".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 87]
                )
                if not ok:
                    raise RuntimeError("JPEG encoding failed")
                frames += 1
                with self.lock:
                    self.jpg = encoded.tobytes()
                    self.state["frame_seq"] = frames
                    self.state["frame_time"] = time.time()
                    self.state["render_fps"] = round(frames / (time.monotonic() - start), 1)
                    self.state["gap_mm"] = None if x is None else round(2 * (x - 11.5), 2)
                    self.state["mujoco_version"] = mujoco.__version__
                    self.state["model_geoms"] = m.ngeom
                    if self.state["source"] == "manual" or (live and live.get("can_render")):
                        self.state["error"] = None
                self.stop.wait(max(0, 0.05 - (time.monotonic() - tick)))
        except Exception as e:  # noqa: BLE001 -- report worker failure to the UI, never a false success
            with self.lock:
                self.state["error"] = f"{type(e).__name__}: {e}"
        finally:
            if renderer:
                renderer.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8084)
    p.add_argument("--telemetry-jsonl")
    p.add_argument("--calibration")
    p.add_argument("--live-url")
    args = p.parse_args()
    app = Viewer(args.telemetry_jsonl, args.calibration, args.live_url)

    class Handler(BaseHTTPRequestHandler):
        def send(self, code, content, kind):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/":
                self.send(200, STATIC.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/state":
                self.send(200, json.dumps(app.snapshot()).encode(), "application/json")
            elif path == "/frame.jpg":
                with app.lock:
                    jpg = app.jpg
                self.send(
                    200 if jpg else 503,
                    jpg or b"Frame not ready",
                    "image/jpeg" if jpg else "text/plain",
                )
            elif path == "/api/calibration":
                with app.lock:
                    cal = app.calibration
                self.send(200, json.dumps(cal).encode(), "application/json")
            elif path == "/favicon.ico":
                self.send(204, b"", "image/x-icon")
            else:
                self.send(404, b"Not found", "text/plain")

        def do_POST(self):
            if self.path not in (
                "/api/state", "/api/live/start", "/api/live/stop", "/api/calibration",
                "/api/direction/before", "/api/direction/after",
            ):
                self.send(404, b"Not found", "text/plain")
                return
            # Same local origin only. Live actions use the read-only bridge.
            origin = self.headers.get("Origin")
            if origin and origin not in {
                f"http://127.0.0.1:{args.port}",
                f"http://localhost:{args.port}",
            }:
                self.send(403, b"Invalid origin", "text/plain")
                return
            try:
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= 16384:
                    raise ValueError("Invalid payload size")
                payload = json.loads(self.rfile.read(size))
                if self.path == "/api/state":
                    app.update(payload)
                else:
                    app.live_action(self.path, payload)
                self.send(200, json.dumps(app.snapshot()).encode(), "application/json")
            except (ValueError, TypeError, KeyError, OSError) as e:
                self.send(
                    400,
                    json.dumps({"error": str(e)}, ensure_ascii=False).encode(),
                    "application/json",
                )

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(
        f"MuJoCo current-arm viewer: http://127.0.0.1:{args.port} (READ bridge only)", flush=True
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.stop.set()
        app.thread.join(timeout=10)
        if app.bridge:
            try:
                app.bridge.request("/api/stop", {})
            except OSError as exc:
                print(f"READ bridge shutdown not confirmed: {exc}", flush=True)
            finally:
                app.bridge.stop.set()
                app.bridge.thread.join(timeout=2)


if __name__ == "__main__":
    main()
