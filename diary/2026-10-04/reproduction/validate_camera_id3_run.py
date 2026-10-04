"""Independently check a finished bounded run and adjacent READ/video artifacts."""
import argparse
import hashlib
import json
from pathlib import Path

from arm_observer.id3_direction import folded_read

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--report-dir", required=True, type=Path)
parser.add_argument("--expected-degrees", type=int, choices=(10, 30), default=10)
parser.add_argument("--visual-review", required=True,
                    help="actual observations recorded after viewing the extracted frames")
args = parser.parse_args()
directory = args.report_dir.resolve()
result_path = directory / "execution-result.json"
result = json.loads(result_path.read_text())
log = Path(result["log"]).resolve()
records = [json.loads(x) for x in log.read_text().splitlines()]
samples = [r for r in records if r["kind"] == "sample"]
start = next(r for r in records if r["kind"] == "start")
outcome = next(r for r in records if r["kind"] == "outcome")
release = next(r for r in records if r["kind"] == "released")
plan = next(r for r in records if r["kind"] == "plan")
expected_counts = {10: 114, 30: 341}[args.expected_degrees]
routes = next(r for r in records if r["kind"] == "routing")["motors"]
restores = [r for r in records if r["kind"] == "restore_readback"]
active = [r for r in samples if r["stage"] in ("open", "correct", "hold", "return")]
hold = [r for r in samples if r["stage"] == "hold"]
others = {i: max(abs(s["positions"][i] - position) for s in samples)
          for i, position in start["others"].items()}
pre = folded_read(directory / "pre-read.jsonl")
post = folded_read(directory / "post-read.jsonl")
checks = {
    "converged_exit0": result["exit_code"] == 0 and outcome["status"] == "converged",
    "requested_counts": outcome["target"] - outcome["torque_on_counts"] == expected_counts,
    "logged_plan_matches_external_request": plan["open_counts"] == expected_counts,
    "opening_error_within5": abs(outcome["final_error_counts"]) <= 5,
    "return_error_within5": abs(outcome["return_error_counts"]) <= 5,
    "opening_sign_positive": outcome["sign"] == 1,
    "all_other_ids_within_existing20": set(others) == {"1", "2", "4", "5"} and all(v <= 20 for v in others.values()),
    "id3_torque_on_all_active_samples": bool(active) and all(s["torque"]["3"] is True for s in active),
    "other_torques_off_all_samples": all(s["torque"][str(i)] is False for s in samples for i in (1, 2, 4, 5)),
    "hold_about2seconds": len(hold) >= 20 and hold[-1]["t"] - hold[0]["t"] >= 1.9,
    "five_routes_no_alias": sorted(r["motor_id"] for r in routes) == [1, 2, 3, 4, 5] and all(r["secondary_id"] == 255 for r in routes),
    "final_all5_off": all(release["final_torque"].get(str(i)) is False for i in range(1, 6)),
    "no_restore_or_release_problem": release["problems"] == [] and outcome["release_problems"] == [],
    "three_ram_readbacks_match": len(restores) == 3 and all(r["observed"] == r["expected"] for r in restores),
    "closed_result_and_event": result["port_closed"] is True and records[-1]["kind"] == "closed" and records[-1]["port_closed"] is True,
    "pre_near_start": abs(pre["folded_count"] - outcome["start_counts"]) <= 5,
    "post_near_start": abs(post["folded_count"] - outcome["start_counts"]) <= 5,
}
files = [result_path, log, directory / "pre-read.jsonl", directory / "post-read.jsonl",
         directory / "actual-motion.mkv"] + [directory / f"frame-{s}.jpg" for s in ("before", "open", "return")]
report = {
    "verdict": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
    "other_max_delta_counts": others, "start_count": outcome["start_counts"],
    "opened_count": outcome["target"] + outcome["final_error_counts"],
    "opened_delta_deg": (outcome["target"] + outcome["final_error_counts"] - outcome["start_counts"]) * 360 / 4096,
    "pre": pre, "post": post,
    "visual_review": args.visual_review,
    "expected_degrees": args.expected_degrees,
    "absolute_cad_calibration": None,
    "sources": [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
}
(directory / "validation.json").open("x").write(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: v for k, v in report.items() if k not in ("pre", "post", "sources")}))
raise SystemExit(0 if report["verdict"] == "PASS" else 1)
