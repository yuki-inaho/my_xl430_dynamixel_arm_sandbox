"""Offline check of the ID3 motion evidence (no serial access). Writes a JSON verdict."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "reports/id3_motion_20261004T002034_318712+0900.jsonl"
RUN1 = ROOT / "reports/id3_motion_20261004T001621_347275+0900.jsonl"
PRE = ROOT / "reports/live_20261003T234141_004377+0900.jsonl"
POST = ROOT / "reports/live_20261004T002126_286881+0900.jsonl"
OUT = ROOT / "reports/id3_motion_validation.json"
WRITES = {"torque", "profile_acceleration", "profile_velocity", "goal_pwm", "goal_position"}


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def read_state(path):
    records = lines(path)
    frames = [r["frame"] for r in records if r["kind"] == "frame"]
    end = next(r for r in records if r["kind"] == "end")["summary"]
    complete = [m for f in frames for m in f["motors"] if not m["faults"]]
    return {
        "frames": len(frames), "incomplete_frames": end["incomplete_frames"],
        "deadline_misses": end["deadline_misses"], "achieved_hz": end["achieved_rate_hz"],
        "port_closed": end["port_closed"],
        "id3_counts": sorted({m["position_counts"] for m in complete if m["motor_id"] == 3}),
        "torque_on_any": any(m["torque_enabled"] for m in complete),
    }


def run_checks(records):
    outcome = next(r for r in records if r["kind"] == "outcome")
    released = next(r for r in records if r["kind"] == "released")
    samples = [r for r in records if r["kind"] == "sample"]
    writes = [r for r in records if r["kind"] == "write"]
    start = next(r for r in records if r["kind"] == "start")
    others = {k: max(abs(s["positions"][k] - start["others"][k]) for s in samples)
              for k in start["others"]}
    opened = [s["positions"]["3"] for s in samples if s["stage"] in ("open", "correct", "hold")]
    return {
        "status_converged": outcome["status"] == "converged",
        "final_error_within_5": abs(outcome["final_error_counts"]) <= 5,
        "moved_in_opening_direction": max(opened) - outcome["start_counts"] >= 100,
        "never_beyond_target_plus_15": max(opened) <= outcome["target"] + 15,
        "returned_to_start": abs(outcome["return_error_counts"]) <= 5,
        "torque_off_confirmed": outcome["torque_off_confirmed"] is True,
        "final_torque_all_off": not any(released["final_torque"].values()),
        "no_release_problems": released["problems"] == [],
        "other_ids_still_within_2": max(others.values()) <= 2,
        "writes_only_listed_id3_registers": {w["name"] for w in writes} <= WRITES,
        "port_closed_event": any(r["kind"] == "closed" and r["port_closed"] for r in records),
        "_details": {"outcome": outcome, "other_max_delta": others,
                     "opened_max": max(opened), "writes": [(w["name"], w["value"])
                                                           for w in writes]},
    }


def main() -> int:
    run = run_checks(lines(RUN))
    pre, post = read_state(PRE), read_state(POST)
    state = {
        "pre_folded_1153_torque_off": pre["id3_counts"] == [1153] and not pre["torque_on_any"],
        "post_returned_near_start_torque_off": post["id3_counts"] in ([1153], [1154], [1153, 1154])
        and not post["torque_on_any"] and post["port_closed"],
    }
    checks = {k: v for k, v in {**run, **state}.items() if not k.startswith("_")}
    verdict = {
        "verdict": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
        "details": run["_details"], "pre_read": pre, "post_read": post,
        "run1_outcome": next(r for r in lines(RUN1) if r["kind"] == "outcome"),
        "inputs": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (RUN, RUN1, PRE, POST)},
        "scope": "encoder reached/converged check (D-4); no MuJoCo or visual confirmation",
    }
    OUT.write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"verdict": verdict["verdict"], "checks": checks}, ensure_ascii=False))
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
