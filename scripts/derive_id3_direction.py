"""Derive the ID3 elbow opening count sign from the R3 CAD and a finished read-only log.

No serial access. Inputs: the R3 manifest/joints (immutable donor CAD evidence) and a
completed arm-live/watch JSONL (schema v2) taken with the elbow fully folded.
"""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

GRIPPER = Path(__file__).resolve().parents[2] / "3d-printed-dynamixel-gripper"
R3 = GRIPPER / "references/arm-r3"
MOTOR_ID = 3


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


def cad_direction(manifest: list[dict], joints: list[dict]) -> dict:
    j2, j3, j4 = (next(j for j in joints if j["name"] == n) for n in ("J2", "J3", "J4"))
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


def folded_read(log: Path) -> dict:
    records = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    frames = [r["frame"] for r in records if r.get("kind") == "frame"]
    end = next((r for r in records if r.get("kind") == "end"), None)
    motors = [m for f in frames for m in f["motors"] if m["motor_id"] == MOTOR_ID]
    # Frames with a communication fault carry unknown values; they are excluded, not filled.
    complete = [m for m in motors if not m["faults"] and type(m["position_counts"]) is int]
    if not end or end["summary"]["port_closed"] is not True or len(complete) < 50:
        raise ValueError("Read log must be a completed run with port_closed=true")
    if any(m["torque_enabled"] is not False for m in complete):
        raise ValueError("ID3 must read torque OFF in every complete frame")
    counts = [m["position_counts"] for m in complete]
    if max(counts) - min(counts) > 2:
        raise ValueError(f"ID3 was not still: {min(counts)}..{max(counts)}")
    return {"log": str(log), "sha256": sha256(log), "frames": len(complete),
            "excluded_fault_frames": len(motors) - len(complete),
            "min": min(counts), "max": max(counts), "folded_count": counts[-1]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_path, joints_path = R3 / "manifest.json", R3 / "joints.json"
    derivation = cad_direction(json.loads(manifest_path.read_text()),
                               json.loads(joints_path.read_text()))
    read = folded_read(args.read_log)
    record = {
        "kind": "cad_derivation", "motor_id": MOTOR_ID,
        "opening_count_sign": derivation["opening_count_sign"],
        "folded_count": read["folded_count"], "folded_read": read,
        "derivation": derivation,
        "sources": {str(p): sha256(p) for p in (manifest_path, joints_path)},
        "physical_report": "user: ID3 is the elbow, fully folded; requested motion opens it",
        "assumptions": [
            "XL430 Drive Mode 0: position counts increase counter-clockwise seen from the horn",
            "the horn is on the side opposite the idler",
            "the printed arm matches the R3 layout at the elbow (photo check: R3 family)",
            "fully folded means the forearm lies toward the upper arm by the short rotation",
        ],
        "runtime_check": "arm-id3-open aborts if ID3 does not progress in this direction "
                         "within the early-progress window (a fold stop would block it)",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"opening_count_sign": record["opening_count_sign"],
                      "folded_count": record["folded_count"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
