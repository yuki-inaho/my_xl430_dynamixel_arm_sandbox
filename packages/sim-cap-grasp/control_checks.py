"""Matched real-dynamics controls, repeats and sensitivity checks after freeze."""

import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from audit_random_trial import audit_trial
from batch import verify_freeze
from build_scene import ROOT, save_json
from random_run import run


def execute(case):
    name, options, plan_path, target, protocol = case
    directory = ROOT / "results" / "controls-001" / name
    args = {
        "output": directory,
        "plan": Path(plan_path),
        "target_id": name,
        "seed": 81020261005,
        "no_close": False,
        "friction": 0.7,
        "mass": 0.0015,
        "timestep": 0.001,
    }
    args.update(options)
    result = run(SimpleNamespace(**args))
    audit = audit_trial(
        directory,
        target,
        protocol["standby"]["arm_q_rad"],
        protocol["standby"]["jaw_theta_deg"],
        return_criteria=protocol["return_criteria"],
        timing=protocol["timing_s"],
        approach_offset_m=protocol["planner"]["grip_z_offset_m"],
    )
    save_json(directory / "independent-audit.json", audit)
    return {
        "name": name,
        "parameters": options,
        "run_dir": str(directory.relative_to(ROOT)),
        "status": result["status"],
        "reason_codes": result["reason_codes"],
        "metrics": result["metrics"],
        "cycle_metrics": result.get("cycle_metrics", {}),
        "independent_audit_pass": audit["audit_pass"],
        "independent_status_agrees": audit["core_status_agrees"],
    }


def main():
    verify_freeze("qualification-001", 81020261005)
    directory = ROOT / "results" / "controls-001"
    if directory.exists():
        raise FileExistsError(directory)
    directory.mkdir()
    protocol = json.loads((ROOT / "protocol.json").read_text())
    index = json.loads((ROOT / "results/qualification-001/index.json").read_text())
    first = index["trials"][0]
    base = ROOT / first["run_dir"]
    plan = str(ROOT / first["plan_path"])
    cases = [
        ("repeat", {}),
        ("no-close", {"no_close": True}),
        ("half-step", {"timestep": 0.0005}),
        ("friction-low", {"friction": 0.15}),
        ("friction-high", {"friction": 1.0}),
        ("mass-low", {"mass": 0.00075}),
        ("mass-high", {"mass": 0.003}),
    ]
    results = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(execute, (name, options, plan, first["target_m"], protocol))
            for name, options in cases
        ]
        for future in as_completed(futures):
            row = future.result()
            results.append(row)
            save_json(directory / "controls.partial.json", results)
            print(
                "CONTROL",
                row["name"],
                row["status"],
                row["reason_codes"],
                "audit=",
                row["independent_audit_pass"],
                flush=True,
            )
    results.sort(key=lambda row: [name for name, _ in cases].index(row["name"]))
    with (
        np.load(base / "states.npz", allow_pickle=False) as a,
        np.load(directory / "repeat/states.npz", allow_pickle=False) as b,
    ):
        identical = set(a.files) == set(b.files) and all(
            np.array_equal(a[key], b[key]) for key in a.files
        )
        arrays = {key: bool(np.array_equal(a[key], b[key])) for key in a.files}
    left = json.loads((base / "storage.json").read_text())["contacts"]["uncompressed_sha256"]
    right = json.loads((directory / "repeat/storage.json").read_text())["contacts"][
        "uncompressed_sha256"
    ]
    by_name = {row["name"]: row for row in results}
    report = {
        "base_trial": first["run_dir"],
        "target_m": first["target_m"],
        "trials": results,
        "deterministic_repeat": {
            "all_state_arrays_bit_exact": identical,
            "arrays": arrays,
            "all_contact_bytes_bit_exact": left == right,
        },
        "matched_negative_failed": by_name["no-close"]["status"] == "FAILURE"
        and "NO_GRIP" in by_name["no-close"]["reason_codes"],
        "half_timestep_passed": by_name["half-step"]["status"] == "SUCCESS",
        "all_independent_audits_agree": all(
            row["independent_audit_pass"] and row["independent_status_agrees"] for row in results
        ),
        "scope": "Single matched target sensitivity; not broad-domain robustness to parameter changes",
    }
    verify_freeze("qualification-001", 81020261005)
    save_json(ROOT / "evidence/controls-summary.json", report)
    print(json.dumps(report, indent=2), flush=True)
    assert identical and left == right
    assert report["matched_negative_failed"]
    assert report["all_independent_audits_agree"]
    assert report["half_timestep_passed"]
