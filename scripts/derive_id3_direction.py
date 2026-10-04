"""Derive the ID3 elbow opening count sign from the R3 CAD and a finished read-only log.

No serial access. Inputs: the R3 manifest/joints (immutable donor CAD evidence) and a
completed arm-live/watch JSONL (schema v2) taken with the elbow fully folded.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from arm_observer.id3_direction import cad_direction, folded_read, sha256

GRIPPER = Path(__file__).resolve().parents[2] / "3d-printed-dynamixel-gripper"
R3 = GRIPPER / "references/arm-r3"
MOTOR_ID = 3




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
