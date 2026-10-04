"""Validate ID3 direction against fixed donor CAD and completed hardware READ evidence.

Parsing is a serialization boundary. Unknown source provenance is never hardware evidence.
No serial port is opened here.
"""
import hashlib
import json
from pathlib import Path

IDS = (1, 2, 3, 4, 5)
MOTOR_ID = 3
R3_HASHES = {
    "manifest.json": "d2fa5203e88d36589c3083a1649467522f275b91f12e9c6040a95e8fc1188d21",
    "joints.json": "988890dd93df387ce22f027c10f9e7f3e4f7ac1841e010f18fd7aec47eebf7a7",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(manifest: list[dict], name: str) -> list[float]:
    return next(entry["bounds"] for entry in manifest if entry["name"] == name)


def link_holding_case(manifest: list[dict], case: list[float]) -> str:
    """The link whose top face meets the case bottom and spans the same Y range."""
    for name in ("P03_shoulder_XL430", "P04_extension_XL430"):
        link = bounds(manifest, name)
        touches = abs(link[5] - case[2]) < 0.5
        same_y = abs(link[1] - case[1]) < 0.5 and abs(link[4] - case[4]) < 0.5
        if touches and same_y:
            return name
    raise ValueError("No link holds the M03 case by the expected face contact")


def joint_named(joints: list[dict], name: str) -> dict:
    return next(j for j in joints if j["name"] == name)


def cad_direction(manifest: list[dict], joints: list[dict]) -> dict:
    j2, j3, j4 = (joint_named(joints, name) for name in ("J2", "J3", "J4"))
    if j3["motor"] != "M03" or j3["axis"] != [1, 0, 0]:
        raise ValueError("Unexpected J3 definition")
    axis_x = j3["centre_mm"][0]
    idler = bounds(manifest, "M03_ref07")
    idler_side = -1 if (idler[0] + idler[3]) / 2 < axis_x else 1
    horn_side = -idler_side
    case = bounds(manifest, "M03_ref00")
    case_link = link_holding_case(manifest, case)
    upper = [b - a for a, b in zip(j3["centre_mm"], j2["centre_mm"])]  # elbow -> shoulder
    forearm = [b - a for a, b in zip(j3["centre_mm"], j4["centre_mm"])]  # elbow -> wrist
    # Rotation of the forearm about +X by +theta maps (y, z) -> (y cos - z sin, y sin + z cos).
    # Folding brings the forearm toward the upper arm along the short way.
    cross_x = forearm[1] * upper[2] - forearm[2] * upper[1]
    folding_sign_about_x = 1 if cross_x > 0 else -1
    opening_sign_about_x = -folding_sign_about_x
    # XL430, Drive Mode 0: counts increase counter-clockwise seen from the horn side.
    count_sign_about_x = horn_side
    relative_sign = 1 if case_link.startswith("P03") else -1  # horn drives the other link
    opening_count_sign = opening_sign_about_x * count_sign_about_x * relative_sign
    return {
        "j3_axis": j3["axis"], "j3_centre_mm": j3["centre_mm"],
        "idler_centre_x_mm": round((idler[0] + idler[3]) / 2, 3), "horn_side_x": horn_side,
        "case_bounds_mm": case, "case_link": case_link,
        "elbow_to_shoulder_mm": upper, "elbow_to_wrist_mm": forearm,
        "folding_sign_about_x": folding_sign_about_x, "opening_count_sign": opening_count_sign,
    }



def exact_ids(items: list[dict]) -> None:
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError("READ motors must be a list of objects")
    ids = [item.get("motor_id") for item in items]
    if (len(ids) != len(IDS) or any(type(mid) is not int for mid in ids)
            or set(ids) != set(IDS)):
        raise ValueError("READ evidence must contain each of ID1..5 exactly once")


def check_identity(motor: dict) -> None:
    identity = motor.get("identity") or {}
    if (motor.get("faults") or identity.get("faults")
            or type(identity.get("device_error")) is not int or identity["device_error"] != 0):
        raise ValueError("READ identity has faults or alert")
    if identity.get("motor_id") != motor["motor_id"] or identity.get("model_number") != 1060:
        raise ValueError("READ identity does not match the XL430 arm")


def metadata_settings(motor: dict) -> dict:
    check_identity(motor)
    registers = motor["registers"]
    if any(r.get("device_alert") is not False for r in registers):
        raise ValueError("READ metadata register has an alert")
    values = {r["name"]: r["value"] for r in registers}
    expected = {"id": motor["motor_id"], "drive_mode": 0, "operating_mode": 3,
                "homing_offset": 0, "protocol_type": 2, "baud_rate": 3}
    if any(type(values.get(k)) is not int or values[k] != v for k, v in expected.items()):
        raise ValueError("READ motor settings differ from the CAD direction assumptions")
    return values


def metadata_context(record: dict) -> tuple:
    if record.get("simulated") is not False:
        raise ValueError("READ source must explicitly be hardware (simulated=false)")
    session = record.get("acquisition_id")
    if not isinstance(session, str) or not session.strip():
        raise ValueError("READ evidence needs a bound acquisition session")
    bus = record["config"]["bus"]
    if (bus.get("expected_ids") != list(IDS) or bus.get("baudrate") != 1000000
            or bus.get("protocol") != 2.0 or not bus.get("device", "").startswith("/dev/")):
        raise ValueError("READ bus context does not match the hardware arm")
    motors = record["metadata"]
    exact_ids(motors)
    settings = tuple((m["motor_id"], json.dumps(metadata_settings(m), sort_keys=True))
                     for m in sorted(motors, key=lambda m: m["motor_id"]))
    return session, json.dumps(record["config"], sort_keys=True), settings


def check_hardware_fault(motor: dict) -> None:
    error = motor.get("hardware_error")
    if (error is not None and (type(error) is not int or error != 0)
            or motor.get("device_alert") is not False):
        raise ValueError("READ contains a hardware error or device alert")


def check_complete_motor(motor: dict) -> None:
    count = motor.get("position_counts")
    if (type(count) is not int or not 0 <= count <= 4095
            or motor.get("torque_enabled") is not False
            or type(motor.get("hardware_error")) is not int):
        raise ValueError("Complete hardware READ must have valid counts and all torque OFF")


def hardware_frame(frame: dict) -> int | None:
    motors = frame["motors"]
    exact_ids(motors)
    # A latched hardware error is fatal even if another register was lost.
    for motor in motors:
        check_hardware_fault(motor)
    if any(m.get("faults") for m in motors):
        return None  # explicit communication loss: exclude, never fill
    for motor in motors:
        check_complete_motor(motor)
    return next(m["position_counts"] for m in motors if m["motor_id"] == MOTOR_ID)


def check_record(record: object) -> None:
    if not isinstance(record, dict):
        raise ValueError("READ record must be an object")
    if (type(record.get("schema_version")) is not int or record["schema_version"] != 2
            or record.get("kind") not in ("metadata", "frame", "end")):
        raise ValueError("READ evidence has an unknown record/schema")


def read_records(path: Path) -> list[dict]:
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    for record in records:
        check_record(record)
    if not records or records[0].get("kind") != "metadata" or records[-1].get("kind") != "end":
        raise ValueError("READ evidence must start with metadata and end with closure")
    if sum(r["kind"] == "end" for r in records) != 1:
        raise ValueError("READ evidence combines multiple runs")
    return records


def completed_counts(records: list[dict]) -> tuple[list[int], int, str]:
    counts, total, sequence = [], 0, -1
    context = metadata_context(records[0])
    for record in records:
        if record["kind"] == "metadata" and metadata_context(record) != context:
            raise ValueError("READ settings/source/session changed during acquisition")
        if record["kind"] != "frame":
            continue
        frame = record["frame"]
        current = frame.get("sequence")
        if type(current) is not int or current <= sequence:
            raise ValueError("READ sequence is not strictly increasing")
        sequence, total = current, total + 1
        if record.get("simulated", False) is not False:
            raise ValueError("Synthetic frame cannot be used as hardware evidence")
        count = hardware_frame(frame)
        if count is not None:
            counts.append(count)
    return counts, total, context[0]


def folded_read(log: Path) -> dict:
    log = log.resolve(strict=True)
    records = read_records(log)
    counts, total, session = completed_counts(records)
    summary = records[-1]["summary"]
    if summary.get("port_closed") is not True or len(counts) < 50:
        raise ValueError("READ must be closed with at least 50 complete hardware frames")
    if summary.get("frames") != total:
        raise ValueError("READ frame count differs from its end summary")
    if max(counts) - min(counts) > 2:
        raise ValueError(f"ID3 was not still: {min(counts)}..{max(counts)}")
    return {"log": str(log), "sha256": sha256(log), "frames": len(counts),
            "excluded_fault_frames": total - len(counts), "acquisition_id": session,
            "min": min(counts), "max": max(counts), "folded_count": counts[-1]}


def fixed_cad(sources: object) -> dict:
    if not isinstance(sources, dict) or len(sources) != len(R3_HASHES):
        raise ValueError("CAD evidence must name the two fixed R3 source files")
    loaded = {}
    for name, claimed in sources.items():
        path = Path(name)
        expected = R3_HASHES.get(path.name)
        if expected is None or claimed != expected or sha256(path) != expected:
            raise ValueError(f"CAD source {path} differs from the fixed R3 contract")
        if path.name in loaded:
            raise ValueError("Duplicate CAD source name")
        loaded[path.name] = json.loads(path.read_text())
    return cad_direction(loaded["manifest.json"], loaded["joints.json"])


def validate_cad_record(record: dict) -> None:
    sign = record.get("opening_count_sign")
    folded = record.get("folded_count")
    if record.get("motor_id") != MOTOR_ID or type(sign) is not int or type(folded) is not int:
        raise ValueError("CAD evidence needs integer ID3 sign and folded count")
    expected = fixed_cad(record.get("sources"))
    if sign != expected["opening_count_sign"]:
        raise ValueError("Opening sign disagrees with independent CAD derivation")
    if json.dumps(record.get("derivation"), sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError("Recorded derivation disagrees with independent CAD computation")
    read = record.get("folded_read")
    if not isinstance(read, dict):
        raise ValueError("CAD evidence needs a completed hardware READ")
    verified = folded_read(Path(read["log"]))
    if read != verified or folded != verified["folded_count"]:
        raise ValueError("Folded READ hash/content/summary disagrees with its original")


def cad_problem(record: dict) -> str | None:
    try:
        validate_cad_record(record)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        return f"CAD direction evidence invalid: {exc}"
    return None
