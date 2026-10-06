"""Deterministic development/qualification target accounting and real trials."""

from __future__ import annotations

import datetime
import json
import math
import platform
import re
import shutil
import time
import traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

import mujoco
import numpy as np

from build_scene import MODEL, ROOT, save_json, sha
from random_plan import analytic_ik, plan_target, proposal_targets
from trace_io import finalize_after_interrupt

_WORKER_MODEL = None
RUNTIME_FILES = [
    "build_scene.py",
    "ik.py",
    "evaluate.py",
    "random_plan.py",
    "random_cycle.py",
    "random_run.py",
    "random_study.py",
    "batch.py",
    "protocol.json",
    "evaluation_contract.json",
    "assumptions.json",
    "pyproject.toml",
    "uv.lock",
    "trace_io.py",
    "physics_step.py",
]


def wilson(successes, n):
    if not n:
        return None
    z = 1.959963984540054
    p = successes / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [center - half, center + half]


def freeze(name, seed):
    validate_name_seed(name, seed)
    out = ROOT / "evidence" / f"{name}-freeze.json"
    if out.exists():
        raise FileExistsError(out)
    files = [ROOT / name for name in RUNTIME_FILES]
    tests = [p for p in (ROOT / "tests").rglob("*.py") if p.is_file()]
    files += [p for p in MODEL.rglob("*") if p.is_file()] + tests
    record = {
        "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "qualification_name": name,
        "generator_seed": seed,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "mujoco": mujoco.__version__,
        "inputs": {str(p.relative_to(ROOT)): sha(p) for p in files},
    }
    save_json(out, record)
    snapshot = ROOT / "evidence" / f"{name}-source"
    snapshot.mkdir()
    for filename in RUNTIME_FILES + [str(p.relative_to(ROOT)) for p in tests]:
        destination = snapshot / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / filename, destination)
    print("FROZEN", out, sha(out), "seed=", seed, flush=True)
    return record


def verify_freeze(name, seed):
    validate_name_seed(name, seed)
    file = ROOT / "evidence" / f"{name}-freeze.json"
    record = json.loads(file.read_text())
    if record["generator_seed"] != seed:
        raise ValueError("Frozen seed mismatch")
    for filename, digest in record["inputs"].items():
        if sha(ROOT / filename) != digest:
            raise ValueError("Frozen input changed: " + filename)
    return sha(file)


def plan_worker(task):
    global _WORKER_MODEL
    target, protocol, proposal_index, directory, kind = task
    if _WORKER_MODEL is None:
        _WORKER_MODEL = mujoco.MjModel.from_xml_path(str(MODEL / "scene.xml"))
    plan = plan_target(target, protocol, _WORKER_MODEL)
    name = f"proposal-{proposal_index:04d}"
    path = Path(directory) / f"{name}.json"
    save_json(path, plan)
    return {
        "proposal_index": proposal_index,
        "target_m": list(map(float, target)),
        "kind": kind,
        "status": plan["status"],
        "reason": plan["reason"],
        "ik_endpoints_feasible": plan["ik_endpoints_feasible"],
        "screened_sample_count": len(plan["screened_samples"]),
        "plan_path": str(path.relative_to(ROOT)),
    }


def trial_worker(task):
    from random_run import run

    row, seed, directory = task
    target_id = row["target_id"]
    output = Path(directory) / target_id
    try:
        result = run(
            SimpleNamespace(
                output=output,
                plan=ROOT / row["plan_path"],
                target_id=target_id,
                seed=seed,
                no_close=False,
                friction=0.7,
                mass=0.0015,
                timestep=0.001,
            )
        )
        return {
            **row,
            "run_dir": str(output.relative_to(ROOT)),
            "status": result["status"],
            "reason_codes": result["reason_codes"],
            "metrics": result["metrics"],
            "cycle_metrics": result.get("cycle_metrics", {}),
        }
    except Exception as exc:  # noqa: BLE001 -- Preserve every accepted target and failure.
        # Accepted targets remain in the denominator even for implementation or I/O errors.
        output.mkdir(parents=True, exist_ok=True)
        failure = {
            "status": "FAILURE",
            "reason_codes": ["RUNTIME_ERROR"],
            "exception": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        save_json(output / "uncaught-failure.json", failure)
        return {**row, "run_dir": str(output.relative_to(ROOT)), **failure}


@finalize_after_interrupt()
def run_batch(name, seed, mode, workers=4):
    validate_name_seed(name, seed)
    if mode not in {"development", "qualification"} or not 1 <= workers <= 4:
        raise ValueError("Invalid batch mode or worker count (1..4)")
    protocol = json.loads((ROOT / "protocol.json").read_text())
    directory = ROOT / "results" / name
    if directory.exists():
        raise FileExistsError(directory)
    frozen_sha = verify_freeze(name, seed) if mode == "qualification" else None
    directory.mkdir(parents=True)
    plans = directory / "plans"
    plans.mkdir()
    save_json(directory / "protocol.json", protocol)
    started = time.monotonic()
    records = []
    selected = []
    budget = protocol["proposal"]["proposal_budget"]
    if mode == "development":
        # Outcome-independent radial probes cover all yaw quadrants and inner/outer edges.
        points = [
            [float(radius * math.sin(angle)), float(radius * math.cos(angle)), 0.0575]
            for radius in (0.13, 0.15, 0.18, 0.21, 0.225)
            for angle in np.linspace(-math.pi, math.pi, 8, endpoint=False)
        ]
        random_points = proposal_targets(protocol, seed, budget)
        points += random_points.tolist()
        needed_random = protocol["development"]["initial_random_trials"]
    else:
        points = proposal_targets(protocol, seed, budget).tolist()
        needed_random = protocol["qualification"]["accepted_trial_count"]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        random_accepted = 0
        stop = False
        for begin in range(0, len(points), 16):
            tasks = [
                (
                    point,
                    protocol,
                    i,
                    str(plans),
                    "boundary_probe" if mode == "development" and i < 40 else "iid_random",
                )
                for i, point in enumerate(points[begin : begin + 16], begin)
            ]
            chunk = list(pool.map(plan_worker, tasks))
            for row in chunk:
                if stop:
                    # Prefetched checks are retained in plans; they are outside the fixed prefix.
                    continue
                records.append(row)
                if row["status"] == "ACCEPTED":
                    selected.append(row)
                    if row["kind"] == "iid_random":
                        random_accepted += 1
                print(
                    f"SCREEN {name} proposal={row['proposal_index']} {row['status']} {row['reason']}; accepted={len(selected)}",
                    flush=True,
                )
                if random_accepted >= needed_random:
                    stop = True
            if stop:
                break
    rejected = [r for r in records if r["status"] != "ACCEPTED"]
    for i, row in enumerate(selected):
        row["target_id"] = f"{name}-t{i:03d}"
    index = {
        "name": name,
        "mode": mode,
        "generator_seed": seed,
        "protocol_sha256": sha(ROOT / "protocol.json"),
        "freeze_sha256": frozen_sha,
        "proposal_count": len(records),
        "rejected": rejected,
        "selected_before_dynamics": selected,
        "trials": [],
        "screening_wall_time_s": time.monotonic() - started,
        "rng": protocol["proposal"]["rng"],
        "screening_reasons": dict(Counter(str(r["reason"]) for r in rejected)),
        "endpoint_IK_feasible_proposals": sum(r["ik_endpoints_feasible"] for r in records),
        "prefetch_note": "Up to 15 extra static plans may exist beyond the selected prefix; no dynamic result influences selection.",
    }
    save_json(directory / "selection.json", index)
    if random_accepted < needed_random:
        index.update(status="INCOMPLETE", reason="PROPOSAL_BUDGET_SHORTFALL")
        save_json(directory / "index.json", index)
        print("INCOMPLETE proposal budget; no denominator substitutions", flush=True)
        return index
    # Selection is complete and durably saved before any dynamics starts.
    print(
        f"DYNAMICS {name}: {len(selected)} prespecified accepted targets, workers={workers}",
        flush=True,
    )
    completed = {}
    pool = ProcessPoolExecutor(max_workers=workers)
    try:
        futures = [pool.submit(trial_worker, (row, seed, str(directory))) for row in selected]
        for future in as_completed(futures):
            row = future.result()
            completed[row["target_id"]] = row
            index["trials"] = [
                completed[r["target_id"]] for r in selected if r["target_id"] in completed
            ]
            save_json(directory / "index.partial.json", index)
            print(
                f"RESULT {name} {len(completed)}/{len(selected)} {row['target_id']}: {row['status']} {row['reason_codes']}",
                flush=True,
            )
    except (Exception, KeyboardInterrupt):
        pool.shutdown(wait=True, cancel_futures=True)
        save_json(directory / "index.json", interrupted_index(index, directory, completed))
        raise
    finally:
        pool.shutdown(wait=True)
    if mode == "qualification":
        verify_freeze(name, seed)
    successes = sum(r["status"] == "SUCCESS" for r in index["trials"])
    unsafe_codes = {"COLLISION", "UNSTABLE"}
    invalid_codes = {
        "MODEL_INVALID",
        "RUNTIME_ERROR",
        "STANDBY_RESET_INVALID",
        "TARGET_RESET_INVALID",
    }
    unsafe = sum(bool(unsafe_codes.intersection(r["reason_codes"])) for r in index["trials"])
    index.update(
        successes=successes,
        trial_count=len(selected),
        unsafe_trials=unsafe,
        invalid_trials=sum(
            bool(invalid_codes.intersection(r["reason_codes"])) for r in index["trials"]
        ),
        wilson_95_interval=wilson(successes, len(selected)),
        status="PASS"
        if successes
        >= (
            protocol["qualification"]["minimum_successes"]
            if mode == "qualification"
            else len(selected)
        )
        and unsafe == 0
        else "FAILURE",
        total_wall_time_s=time.monotonic() - started,
    )
    save_json(directory / "index.json", index)
    print(
        json.dumps(
            {
                k: v
                for k, v in index.items()
                if k not in ("trials", "rejected", "selected_before_dynamics")
            },
            indent=2,
        ),
        flush=True,
    )
    return index


def validate_name_seed(name, seed):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        raise ValueError("Batch name must be a simple identifier")
    if not isinstance(seed, int) or seed < 0:
        raise ValueError("Seed must be a nonnegative integer")


def interrupted_index(index, directory, completed):
    """Keep the fixed denominator; missing evidence is administrative FAILURE, never success."""
    rows = []
    for selected in index["selected_before_dynamics"]:
        row = completed.get(selected["target_id"])
        if row is None:
            trial = directory / selected["target_id"]
            result_path = trial / "result.json"
            if result_path.exists():
                result = json.loads(result_path.read_text())
                row = {**selected, "run_dir": str(trial.relative_to(ROOT)), **result}
            else:
                row = {
                    **selected,
                    "run_dir": str(trial.relative_to(ROOT)),
                    "status": "FAILURE",
                    "reason_codes": ["EXECUTION_INTERRUPTED", "EVIDENCE_INCOMPLETE"],
                    "result_provenance": "administrative_failure_no_physical_result",
                    "metrics": {},
                    "cycle_metrics": {},
                }
        rows.append(row)
    return {
        **index,
        "trials": rows,
        "trial_count": len(rows),
        "successes": sum(r["status"] == "SUCCESS" for r in rows),
        "status": "INCOMPLETE",
        "reason": "EXECUTION_INTERRUPTED",
        "qualification_valid": False,
        "unsafe_trials": sum(
            bool({"COLLISION", "UNSTABLE"}.intersection(r["reason_codes"])) for r in rows
        ),
        "unsafe_scope": "recorded prefixes only; missing/unexecuted portions are not safety evidence",
        "invalid_trials": sum("EVIDENCE_INCOMPLETE" in r["reason_codes"] for r in rows),
    }


def workspace_map():
    model = mujoco.MjModel.from_xml_path(str(MODEL / "scene.xml"))
    protocol = json.loads((ROOT / "protocol.json").read_text())
    pitch = math.radians(protocol["planner"]["pitch_deg"])
    grid = []
    for x in np.linspace(-0.3, 0.3, 61):
        for y in np.linspace(-0.3, 0.3, 61):
            center = np.array([x, y, 0.0575])
            counts = {}
            for name, offset in [("grasp", 0.006), ("pregrasp", 0.041), ("lift", 0.046)]:
                counts[name] = len(analytic_ik(model, center + [0, 0, offset], pitch))
            grid.append(
                {
                    "x": float(x),
                    "y": float(y),
                    "grasp_ik": bool(counts["grasp"]),
                    "all_endpoints_ik": all(counts.values()),
                    "branch_counts": counts,
                }
            )
    result = {
        "spacing_m": 0.01,
        "grid": grid,
        "scope": "Analytic fixed-pitch IK endpoint level sets at 10mm grid; path-screen samples overlaid separately",
        "radial_upper_bound_formula": protocol["proposal"]["coverage_bound"],
    }
    save_json(ROOT / "evidence/workspace-map.json", result)
    print(
        "Workspace endpoint map:",
        len(grid),
        "points;",
        sum(g["grasp_ik"] for g in grid),
        "grasp IK feasible;",
        sum(g["all_endpoints_ik"] for g in grid),
        "all endpoints feasible",
        flush=True,
    )
