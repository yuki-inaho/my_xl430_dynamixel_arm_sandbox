"""Passive local HTTP input and explicit calibration; never imports a motor SDK."""
import copy
import hashlib
import json
import math
import threading
import time
from datetime import datetime
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Bridge redirect rejected")


def urlopen(request, timeout):
    return build_opener(NoRedirect()).open(request, timeout=timeout)

ROLES = ["J1", "J2", "J3", "J4", "PG3"]
# Display coverage, not collision-certified or actuator limits.
RANGES = [(-180, 180), (-40, 40), (-180, 180), (-138, 128)]
METADATA_NAMES = ["id", "baud_rate", "protocol_type", "operating_mode", "drive_mode", "homing_offset"]


def age_seconds(timestamp):
    stamp = datetime.fromisoformat(timestamp)
    if stamp.tzinfo is None:
        raise ValueError("Timezone required")
    return time.time() - stamp.timestamp()


def integer(value, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError("Measured integer outside range")
    return value


def numeric(value, lo, hi):
    if type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError("Finite number outside range")
    return float(value)


def healthy_motor(motor):
    integer(motor["motor_id"], 0, 252)
    integer(motor["position_counts"], -(2**31), 2**31-1)
    if (type(motor["torque_enabled"]) is not bool or motor.get("faults")
        or motor.get("device_alert") is not False or motor.get("hardware_error") != 0):
        raise ValueError("Motor read incomplete or fault/alert")


def metadata_values(motor):
    identity = motor["identity"]
    if (identity is None or identity["model_number"] != 1060 or identity.get("device_error") != 0
        or identity.get("faults") or motor.get("faults")):
        raise ValueError("Unsupported or missing motor identity")
    integer(identity["firmware_version"], 1, 255)
    readings = motor["registers"]
    names = [r["name"] for r in readings]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate metadata register")
    values = {r["name"]: r["value"] for r in readings}
    for name in METADATA_NAMES:
        if name not in values or type(values[name]) is not int:
            raise ValueError("Required motor metadata missing")
    if any(r.get("device_alert") is not False for r in readings):
        raise ValueError("Metadata alert")
    if values["id"] != motor["motor_id"] or values["protocol_type"] != 2:
        raise ValueError("Metadata identity/protocol mismatch")
    if values["operating_mode"] not in (3, 4):
        raise ValueError("Position conversion supports mode3/4 only")
    return values


def source_kind(snapshot):
    source = snapshot.get("simulated")
    if type(source) is not bool:
        raise ValueError("READ source is unknown; explicit simulated boolean required")
    return source


def validated_snapshot(snapshot):
    source_kind(snapshot)
    if (snapshot.get("state") != "running" or snapshot.get("port_closed") is not False
        or not isinstance(snapshot.get("session_id"), str) or not snapshot["session_id"]
        or snapshot.get("error")):
        raise ValueError(snapshot.get("error") or "READ未接続・停止中")
    event, meta = snapshot["frame"], snapshot["metadata"]
    if event["schema_version"] != 2 or event["kind"] != "frame":
        raise ValueError("Unsupported frame contract")
    if meta["schema_version"] != 2 or meta["kind"] != "metadata":
        raise ValueError("Unsupported metadata contract")
    frame = event["frame"]
    if not 0 <= age_seconds(frame["finished_at"]) < 1.0:
        raise ValueError("READ期限超過（最後の姿勢を保持）")
    if not 0 <= age_seconds(meta["observed_at"]) < 31.0:
        raise ValueError("Metadata期限超過")
    motors, metadata = frame["motors"], meta["metadata"]
    ids, meta_ids = [m["motor_id"] for m in motors], [m["motor_id"] for m in metadata]
    if len(ids) != 5 or len(set(ids)) != 5 or sorted(ids) != sorted(meta_ids) or len(meta_ids) != 5:
        raise ValueError("Five unique corresponding motor IDs required")
    for motor in motors:
        healthy_motor(motor)
    for motor in metadata:
        metadata_values(motor)
    return frame, {m["motor_id"]: m for m in motors}, {m["motor_id"]: m for m in metadata}


def model_context(model_dir):
    provenance = json.loads((model_dir / "model-provenance.json").read_text())
    signature = hashlib.sha256((model_dir / "scene.xml").read_bytes()
                              + (model_dir / "model-provenance.json").read_bytes()).hexdigest()
    return provenance["source_cad_sha256"], signature


def current_context(snapshot, model_dir):
    _, motors, metadata = validated_snapshot(snapshot)
    _, signature = model_context(model_dir)
    return {"session_id": snapshot["session_id"], "simulated": source_kind(snapshot),
            "model_signature": signature, "motors": [
        {"motor_id": mid, "model": metadata[mid]["identity"]["model_number"],
         "firmware": metadata[mid]["identity"]["firmware_version"],
         "registers": metadata_values(metadata[mid]), "torque_enabled": motors[mid]["torque_enabled"]}
        for mid in sorted(motors)
    ]}


def end_effector(cal):
    kind = cal.get("end_effector", "pg3")
    if kind not in ("pg3", "bare"):
        raise ValueError("Unknown end-effector configuration")
    return kind


def joint_reference(joint):
    """A known nonzero observation is an anchor, never an invented mechanical zero."""
    if "reference_count" in joint or "reference_angle_deg" in joint:
        if joint.get("zero_count") is not None:
            raise ValueError("Choose observed reference or zero_count, not both")
        return (integer(joint["reference_count"], -(2**31), 2**31-1),
                numeric(joint["reference_angle_deg"], -180, 180))
    return integer(joint["zero_count"], -(2**31), 2**31-1), 0.0


def validate_calibration(cal, model_dir):
    cal = copy.deepcopy(cal)
    if any(cal.get(key) is not True for key in ["physical_order_verified", "calibration_verified",
                                              "baseline_verified", "directions_verified"]):
        raise ValueError("現物のID対応・基準姿勢・方向の明示確認が必要です")
    cad_sha, _ = model_context(model_dir)
    if cal.get("cad_sha256") != cad_sha:
        raise ValueError("Calibration CAD revision mismatch")
    entries = cal["joints"]
    if len(entries) != 5 or [j["role"] for j in entries] != ROLES:
        raise ValueError("Five ordered CAD joint entries required")
    ids = [integer(j["motor_id"], 0, 252) for j in entries]
    if len(set(ids)) != 5:
        raise ValueError("Duplicate motor IDs")
    for j in entries:
        joint_reference(j)
        if type(j["sign"]) is not int or j["sign"] not in (-1, 1):
            raise ValueError("Direction must be +1 or -1")
    if end_effector(cal) == "bare":
        if entries[-1].get("theta_at_zero_deg") is not None:
            raise ValueError("Bare arm has no measured PG3 mechanism angle; use null")
    else:
        numeric(entries[-1]["theta_at_zero_deg"], 25, 135)
    return cal


def bind_calibration(cal, snapshot, model_dir):
    source = source_kind(snapshot)
    if "simulated" in cal and (type(cal["simulated"]) is not bool or cal["simulated"] != source):
        raise ValueError("Calibration source differs from the connected READ source")
    cal = validate_calibration(cal, model_dir)
    context = current_context(snapshot, model_dir)
    if sorted(j["motor_id"] for j in cal["joints"]) != [m["motor_id"] for m in context["motors"]]:
        raise ValueError("Calibration IDs do not match connected motors")
    cal["context"] = context
    cal["simulated"] = source
    return cal


def convert_pose(cal, snapshot, model_dir):
    if type(cal.get("simulated")) is not bool or cal["simulated"] != source_kind(snapshot):
        raise ValueError("Calibration source differs from the connected READ source")
    cal = validate_calibration(cal, model_dir)
    context = current_context(snapshot, model_dir)
    if cal.get("context") != context:
        raise ValueError("校正条件が変わりました。ID・基準・方向を再確認してください")
    _, motors, metadata = validated_snapshot(snapshot)
    angles = []
    for j in cal["joints"]:
        mid = j["motor_id"]
        reference_count, reference_angle = joint_reference(j)
        delta = motors[mid]["position_counts"] - reference_count
        if metadata_values(metadata[mid])["operating_mode"] == 3:
            delta = (delta + 2048) % 4096 - 2048
        angles.append(reference_angle + j["sign"] * delta * 360 / 4096)
    id5_angle = angles.pop()
    theta = (None if end_effector(cal) == "bare"
             else id5_angle + cal["joints"][-1]["theta_at_zero_deg"])
    for angle, bounds in zip(angles, RANGES, strict=True):
        numeric(angle, *bounds)
    if theta is not None:
        numeric(theta, 25, 135)
    return angles, theta


def telemetry_status(snapshot, cal, model_dir):
    motors = (snapshot or {}).get("frame") or {}
    motors = motors.get("frame", {}).get("motors", [])
    result = {"configured": True, "status": "READ未接続", "motors": motors, "fresh": False,
              "can_render": False, "session_id": (snapshot or {}).get("session_id"),
              "state": (snapshot or {}).get("state", "idle"),
              "port_closed": (snapshot or {}).get("port_closed"),
              "summary": (snapshot or {}).get("summary"), "calibration_invalid": False}
    result["simulated"] = (snapshot or {}).get("simulated") is True
    try:
        if not snapshot:
            return result
        frame, _, _ = validated_snapshot(snapshot)
        result.update(fresh=True, status="READ live・未校正", sequence=frame.get("sequence"),
                      age_seconds=age_seconds(frame["finished_at"]))
        if cal is not None:
            angles, theta = convert_pose(cal, snapshot, model_dir)
            result.update(can_render=True, status="READ live・校正済み", angles=angles, theta=theta,
                          end_effector=end_effector(cal))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        result.update(status=str(exc), calibration_invalid=cal is not None)
    return result


class BridgeClient:
    def __init__(self, url):
        parts = urlsplit(url)
        if (parts.scheme != "http" or parts.hostname not in ("localhost", "127.0.0.1")
            or parts.username or parts.password or parts.path not in ("", "/")
            or parts.query or parts.fragment or not parts.port):
            raise ValueError("Bridge must be an explicit localhost HTTP origin")
        self.url = url.rstrip("/")
        self._snapshot = None
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = None

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self._snapshot)

    def request(self, path, payload=None):
        data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        req = Request(self.url + path, data=data, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=0.7) as response:
            if response.geturl() != self.url + path:
                raise ValueError("Bridge redirect rejected")
            raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError("Bridge response too large")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise TypeError("Bridge object required")
        return value

    def start_polling(self):
        self.thread = threading.Thread(target=self.poll, daemon=True)
        self.thread.start()

    def poll(self):
        while not self.stop.is_set():
            try:
                value = self.request("/api/status")
            except (OSError, ValueError, TypeError) as exc:
                value = {"state": "error", "error": f"READ bridge: {exc}"}
            with self.lock:
                self._snapshot = value
            self.stop.wait(0.05)
