"""Native D405 reference-pose, manual torque and RGB-D capture station."""

import argparse
import io
import json
import queue
import shutil
import signal
import threading
import time
import tkinter as tk
import urllib.request
from contextlib import ExitStack, contextmanager
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk

from PIL import Image, ImageOps, ImageTk

from arm_observer.configuration import load_config
from arm_observer.pose_gui_control import PoseGuiController, PoseGuiPort
from arm_observer.standby_motion import open_standby_bus

ROOT = Path(__file__).resolve().parents[2]
TITLE = "D405 Pose Capture"


class ImageView(tk.Label):
    image: ImageTk.PhotoImage


def http(base: str, path: str, payload: dict | None = None) -> bytes:
    request = urllib.request.Request(
        base.rstrip("/") + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.read()


def camera_status(base: str, serial: str) -> dict:
    status = json.loads(http(base, "/status.json"))
    if status.get("serial") != serial or status.get("age_seconds", 999) > 2:
        raise RuntimeError("D405 serial mismatch or stale camera frame")
    return status


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def capture(controller, base: str, serial: str, output: Path) -> Path:
    camera_status(base, serial)
    before = controller.snapshot() if controller is not None else None
    not_before = time.time()
    receipt = json.loads(http(base, "/capture", {"not_before_unix_s": not_before}))
    after = controller.snapshot() if controller is not None else None
    if receipt["metadata"]["requested_serial"] != serial:
        raise RuntimeError("Capture came from a different camera")
    received = datetime.fromisoformat(receipt["metadata"]["host_frame_received_at"]).timestamp()
    if not not_before <= received <= (after["observed_at"] if after else time.time()):
        raise RuntimeError("Camera frame is outside the encoder time bracket")
    source = Path(receipt["path"])
    required = ("color.png", "depth.png", "aligned_depth.png", "depth_preview.png",
                "ir_left.png", "ir_right.png", "metadata.json", "calibration.toml")
    if not all((source / name).is_file() for name in required):
        raise RuntimeError("Incomplete RGB-D capture")
    destination = output / datetime.now().strftime("capture-%H%M%S-%f")
    destination.mkdir()
    for name in required:
        shutil.copy2(source / name, destination / name)
    accepted = bool(before and after) and all(a["velocity_raw"] == b["velocity_raw"] == 0
                   and abs(a["position_counts"] - b["position_counts"]) <= 3
                   and a["torque_enabled"] == b["torque_enabled"]
                   and a["hardware_error"] == b["hardware_error"] == 0
                   and not a["device_alert"] and not b["device_alert"]
                   for a, b in zip(before["motors"], after["motors"], strict=True))
    save_json(destination / "capture.json", {
        "schema": "d405-pose-gui-v1", "accepted": accepted,
        "label": destination.name, "image": "color.png",
        "counts": [m["position_counts"] for m in after["motors"]] if after else None,
        "before": before, "after": after, "camera_receipt": receipt,
        "not_before_unix_s": not_before,
        "synchronization": "host-time bracketing; not hardware synchronized",
        "calibration_verified": False,
        "camera_only": controller is None,
    })
    return destination / "capture.json"


@contextmanager
def gui_bus(device: str, control: bool):
    # The standard observer remains read-only; GUI adds a transaction-locked Port.
    if not control:
        from arm_observer.bus import open_bus
        with open_bus(device, 1000000) as pair:
            yield pair
        return
    with open_standby_bus(device, port_factory=PoseGuiPort) as pair:
        yield pair


class Station:
    """One serial worker; a separate camera worker; Tk touched only in main thread."""

    def __init__(self, args, output: Path):
        self.args, self.output = args, output
        self.stop = threading.Event()
        self.commands = queue.Queue(maxsize=1)
        self.events = queue.Queue()
        self.preview = queue.Queue(maxsize=1)
        self.threads = [threading.Thread(target=self.robot, daemon=True),
                        threading.Thread(target=self.camera, daemon=True)]

    def start(self):
        for thread in self.threads:
            thread.start()

    def robot(self):
        with (self.output / "events.jsonl").open("x", encoding="utf-8") as log:
            def emit(event):
                log.write(json.dumps(event, ensure_ascii=False) + "\n")
                log.flush()
            try:
                with ExitStack() as stack:
                    controller = None
                    try:
                        port, packet = stack.enter_context(gui_bus(self.args.device,
                                                                   self.args.control))
                        controller = PoseGuiController(port, packet, emit)
                    except Exception as error:
                        self.events.put(("fatal", str(error)))
                    last_error = None
                    while not self.stop.is_set():
                        try:
                            command = self.commands.get(timeout=0.4)
                        except queue.Empty:
                            command = ("poll", None)
                        name, payload = command
                        if self.stop.is_set():
                            break  # closing cancels pending operations before their first write
                        try:
                            if name == "recheck":
                                controller = None
                                stack.close()
                                port, packet = stack.enter_context(gui_bus(
                                    self.args.device, self.args.control))
                                controller = PoseGuiController(port, packet, emit)
                                controller.routes()
                                self.events.put(("state", controller.snapshot()))
                                self.events.put(("rearmed", None))
                            if name in ("capture", "camera_only"):
                                if name == "capture" and controller is None:
                                    raise RuntimeError("No robot; use explicit camera-only capture")
                                subject = controller if name == "capture" else None
                                path = capture(subject, self.args.camera, self.args.serial,
                                               self.output)
                                emit({"kind": "gui_capture", "path": str(path)})
                                self.events.put(("capture", path))
                            elif name == "torque":
                                if not self.args.control:
                                    raise RuntimeError("READ-only session")
                                if controller is None:
                                    raise RuntimeError("No robot connection")
                                if not isinstance(payload, tuple) or len(payload) != 2:
                                    raise RuntimeError("Invalid torque command")
                                enabled, supported = payload
                                controller.torque(enabled, support_confirmed=supported)
                                self.events.put(("torque", enabled))
                            if controller is not None and name != "camera_only":
                                self.events.put(("state", controller.snapshot()))
                                last_error = None
                        except Exception as error:
                            if str(error) != last_error or name != "poll":
                                emit({"kind": "gui_fault", "operation": name,
                                      "error": str(error)})
                                self.events.put(("fault", str(error)))
                            last_error = str(error)
                        finally:
                            if name != "poll":
                                self.events.put(("done", None))
            except Exception as error:
                self.events.put(("fatal", str(error)))
            finally:
                emit({"kind": "gui_closed", "port_closed": True,
                      "torque_unchanged_on_exit": True})
                self.events.put(("closed", None))

    def camera(self):
        while not self.stop.is_set():
            try:
                status = camera_status(self.args.camera, self.args.serial)
                rgb = http(self.args.camera, "/color.jpg")
                depth = http(self.args.camera, "/depth.jpg")
                value = (time.monotonic(), status, rgb, depth, None)
            except Exception as error:
                value = (time.monotonic(), None, None, None, str(error))
            if self.preview.full():
                self.preview.get_nowait()
            self.preview.put_nowait(value)
            self.stop.wait(0.2)


class Window:
    def __init__(self, root, station: Station, reference: Path | None):
        self.root, self.station = root, station
        self.busy = False
        self.faulted = False
        self.closing = False
        self.state = None
        self.reference = None
        self.reference_path = None
        self.last_capture = None
        self.camera_at = 0
        self.camera_error = None
        root.title(TITLE + (" — CONTROL" if station.args.control else " — READ ONLY"))
        root.geometry("1420x910+30+40")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", padding=(12, 8), font=("sans-serif", 11))
        style.configure("TLabel", font=("sans-serif", 11))
        outer = ttk.Frame(root, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="D405 · 手本姿勢 / 保持 / RGB-D撮影",
                  font=("sans-serif", 19, "bold")).pack(anchor="w")
        ttk.Label(outer, text="手で重量を支える → OFF → 手本を見て合わせる → 現在位置でON → 撮影"
                  "    |    閉じてもトルクは切り替わりません").pack(anchor="w", pady=(5, 12))
        panels = ttk.Frame(outer)
        panels.pack(fill="x")
        self.reference_view = self.panel(panels, "手本（選択した基準写真）", 0)
        self.live_view = self.panel(panels, "D405 ライブ · RGB / 深度切替", 1)
        self.reference_text = tk.StringVar(value="手本を読み込んでください")
        ttk.Label(outer, textvariable=self.reference_text, wraplength=1340).pack(anchor="w", pady=8)
        self.camera_text = tk.StringVar(value="D405接続確認中")
        ttk.Label(outer, textvariable=self.camera_text).pack(anchor="w")
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=10)
        ttk.Button(bar, text="手本を開く", command=self.load_reference).pack(side="left")
        self.set_button = ttk.Button(bar, text="直前の撮影を手本にする", command=self.set_reference)
        self.set_button.pack(side="left", padx=6)
        self.depth = tk.BooleanVar()
        ttk.Checkbutton(bar, text="深度表示", variable=self.depth).pack(side="left", padx=12)
        self.capture_button = ttk.Button(bar, text="RGB-D + 関節状態を撮影 [F8]",
                                         command=lambda: self.command("capture", None))
        self.capture_button.pack(side="right")
        self.camera_only_button = ttk.Button(bar, text="D405のみ撮影（関節値なし）",
                                            command=lambda: self.command("camera_only", None))
        self.camera_only_button.pack(side="right", padx=8)
        self.table = ttk.Treeview(outer, columns=("id", "count", "reference", "delta", "torque",
                                                 "temp", "voltage"), show="headings", height=5)
        for key, label in zip(self.table["columns"],
                              ("ID", "現在count", "手本count", "差[count]", "トルク", "℃", "V")):
            self.table.heading(key, text=label)
            self.table.column(key, width=150, anchor="center")
        self.table.pack(fill="x")
        for mid in range(1, 6):
            self.table.insert("", "end", iid=str(mid), values=(mid, "?", "—", "—", "UNKNOWN"))
        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=12)
        self.recheck_button = ttk.Button(controls, text="接続を再確認",
                                         command=lambda: self.command("recheck", None))
        self.recheck_button.pack(side="left", padx=(0, 8))
        self.support = tk.BooleanVar()
        ttk.Checkbutton(controls, text="腕・カメラの重さを手/受け台で支えている（切替ごとに確認）",
                        variable=self.support).pack(side="left")
        self.off_button = ttk.Button(controls, text="全ID トルクOFF（脱力）",
                                     command=lambda: self.torque(False))
        self.off_button.pack(side="right")
        self.on_button = ttk.Button(controls, text="全ID 現在位置でON（保持）",
                                    command=lambda: self.torque(True))
        self.on_button.pack(side="right", padx=8)
        self.message = tk.StringVar(value="接続中。起動時のWRITEはありません。")
        ttk.Label(outer, textvariable=self.message, wraplength=1340,
                  foreground="#174b75").pack(anchor="w", pady=5)
        ttk.Label(outer, text=f"保存先: {station.output}", wraplength=1340).pack(anchor="w")
        ttk.Label(outer, text="countは未校正の生値。手本への自動移動・PWM増加は行いません。"
                  + ("" if station.args.control else "  READ ONLY：トルク操作は無効。"),
                  foreground="#7c4311").pack(anchor="w", pady=5)
        root.bind("<F8>", lambda _: self.command("capture", None))
        root.protocol("WM_DELETE_WINDOW", self.close)
        if reference:
            self.open_reference(reference)
        root.after(100, self.tick)

    @staticmethod
    def panel(parent, label, column):
        frame = ttk.LabelFrame(parent, text=label, padding=5)
        frame.grid(row=0, column=column, padx=(0, 12), sticky="nsew")
        parent.columnconfigure(column, weight=1)
        placeholder = ImageTk.PhotoImage(Image.new("RGB", (640, 360), "#152331"))
        view = ImageView(frame, background="#152331", image=placeholder)
        view.image = placeholder
        view.pack()
        return view

    @staticmethod
    def show_image(view, image):
        fitted = ImageOps.pad(image.convert("RGB"), (640, 360), color="#152331")
        photo = ImageTk.PhotoImage(fitted)
        view.configure(image=photo, width=640, height=360)
        view.image = photo

    def open_reference(self, path: Path):
        try:
            record = json.loads(path.read_text())
            if record.get("accepted") is not True:
                raise ValueError("未承認/動いた撮影は手本にできません")
            counts = record.get("counts")
            if counts is not None and (len(counts) != 5 or any(type(p) is not int for p in counts)):
                raise ValueError("手本のcountは5台分必要です")
            image_path = path.parent / record["image"]
            with Image.open(image_path) as image:
                self.show_image(self.reference_view, image)
            self.reference, self.reference_path = record, path
            self.reference_text.set(f"手本: {record.get('label', path.name)}  |  "
                                    "生count比較用。校正済み世界姿勢・自動移動目標ではありません。")
            # Store actual reference data alongside this session, not just a source path.
            dest = self.station.output / "reference"
            dest.mkdir(exist_ok=True)
            shutil.copy2(image_path, dest / "image.png")
            save_json(dest / "reference.json", {**record, "image": "image.png",
                                               "source_reference": str(path)})
        except Exception as error:
            self.message.set(f"手本エラー: {error}")

    def load_reference(self):
        selected = filedialog.askopenfilename(title="手本のreference.json / capture.jsonを選択",
                                             filetypes=[("Pose JSON", "*.json")])
        if selected:
            self.open_reference(Path(selected))

    def set_reference(self):
        if self.last_capture:
            self.open_reference(self.last_capture)

    def torque(self, enabled: bool):
        supported = self.support.get()
        self.support.set(False)
        if not supported:
            self.message.set("腕・カメラの重量を支えてからチェックを入れてください。WRITEなし。")
            return
        self.command("torque", (enabled, supported))

    def command(self, name, payload):
        fresh = (time.monotonic() - self.camera_at <= 2 and self.camera_error is None
                 if name in ("camera_only", "recheck") else self.fresh())
        if self.busy or self.closing or not fresh:
            self.message.set("処理中、または最新のカメラ/関節状態を取得できていません。")
            return
        if name == "torque" and (not self.station.args.control or self.faulted):
            self.message.set("このセッションのトルク切替は無効です。")
            return
        self.busy = True
        self.message.set("撮影・保存中…" if name in ("capture", "camera_only")
                         else "現在状態を確認して切替中…")
        self.station.commands.put_nowait((name, payload))

    def fresh(self):
        now = time.monotonic()
        return (self.state is not None and now - self.state["at"] <= 2
                and now - self.camera_at <= 2 and self.camera_error is None)

    def tick(self):
        while not self.station.events.empty():
            kind, value = self.station.events.get_nowait()
            if kind == "state":
                self.state = value
            elif kind == "capture":
                self.last_capture = value
                record = json.loads(value.read_text())
                accepted = record["accepted"]
                label = ("D405のみ保存OK（関節値なし）" if record["camera_only"] else
                         "保存OK" if accepted else "保存（動作/異常あり: rejected）")
                self.message.set(f"{label}: {value}")
            elif kind == "torque":
                self.message.set("全IDの現在位置保持ONを確認。" if value
                                 else "全IDのOFFを読取確認。重量を支えたまま合わせてください。")
            elif kind == "rearmed":
                self.faulted = False
                self.message.set("5台の接続・ID・modeを確認。トルク状態は変更していません。")
            elif kind in ("fault", "fatal"):
                self.state = None
                self.faulted = True  # no silent rearming after a partial write/fault
                self.message.set(f"エラー（トルクを自動変更しません）: {value}")
            elif kind == "done":
                self.busy = False
            elif kind == "closed" and self.closing:
                self.root.destroy()
                return
        if not self.station.preview.empty():
            at, status, rgb, depth, error = self.station.preview.get_nowait()
            self.camera_at, self.camera_error = at, error
            if error:
                self.camera_text.set(f"D405 UNKNOWN: {error}")
            else:
                try:
                    with Image.open(io.BytesIO(depth if self.depth.get() else rgb)) as image:
                        self.show_image(self.live_view, image)
                    rate = status.get("acquisition_rate_hz")
                    rate_text = f"{rate:.1f}" if rate is not None else "—"
                    self.camera_text.set(f"D405 {status['serial']} · {status['size']} · "
                                         f"{rate_text} fps · "
                                         f"frame {status['frameset_frame_number']}")
                except Exception as error:
                    self.camera_error = str(error)
                    self.camera_text.set(f"D405 preview UNKNOWN: {error}")
        fresh = self.fresh()
        for index in range(5):
            motor = self.state["motors"][index] if self.state else {}
            targets = (self.reference or {}).get("counts")
            count = motor.get("position_counts") if fresh else None
            target = targets[index] if targets else None
            torque = motor.get("torque_enabled") if fresh else None
            self.table.item(str(index + 1), values=(index + 1, count if count is not None else "?",
                            target if target is not None else "—",
                            count - target if count is not None and target is not None else "—",
                            "UNKNOWN" if torque is None else "ON" if torque else "OFF",
                            motor.get("temperature_c", "?"),
                            (motor["voltage_raw"] / 10) if motor.get("voltage_raw") else "?"))
        active = fresh and not self.busy and not self.closing
        self.recheck_button.configure(state="normal" if not self.busy and not self.closing
                                      else "disabled")
        self.capture_button.configure(state="normal" if active else "disabled")
        self.camera_only_button.configure(
            state="normal" if not self.busy and not self.closing
            and time.monotonic() - self.camera_at <= 2 and self.camera_error is None
            else "disabled")
        for button in (self.on_button, self.off_button):
            button.configure(state="normal" if active and self.station.args.control
                             and not self.faulted else "disabled")
        self.set_button.configure(
            state="normal" if self.last_capture and not self.busy else "disabled")
        if not self.closing:
            self.root.after(100, self.tick)
        elif any(t.is_alive() for t in self.station.threads):
            self.root.after(100, self.tick)
        else:
            self.root.destroy()

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.station.stop.set()
        self.message.set("serialを閉じています。トルク状態は保持します。")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/arm.toml")
    parser.add_argument("--device")
    parser.add_argument("--camera", default="http://127.0.0.1:18109")
    parser.add_argument("--serial", default="230322272284")
    parser.add_argument("--reference", type=Path, default=ROOT / "config/pose_gui_reference.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--control", action="store_true", help="Enable manual torque buttons")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if config.bus.expected_ids != (1, 2, 3, 4, 5) or config.bus.baudrate != 1000000:
        parser.error("GUI supports five XL430 IDs at 1 Mbps")
    args.device = args.device or config.bus.device
    output = args.output or (Path.home() / "data/xl430-arm" / datetime.now().strftime("%Y-%m-%d")
                            / "pose-gui" / datetime.now().strftime("session-%H%M%S-%f"))
    output.mkdir(parents=True, exist_ok=False)
    save_json(output / "session.json", {"created_at": datetime.now().astimezone().isoformat(),
                                       "control": args.control, "camera": args.camera,
                                       "serial": args.serial, "device": args.device})
    root = tk.Tk()
    station = Station(args, output)
    window = Window(root, station, args.reference)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: window.close())
    station.start()
    print(f"GUI: {output}", flush=True)
    root.mainloop()
    for thread in station.threads:
        thread.join(timeout=6)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
