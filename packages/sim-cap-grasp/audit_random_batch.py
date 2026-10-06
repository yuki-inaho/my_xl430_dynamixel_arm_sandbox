"""Audit a frozen qualification index and every raw trajectory independently.

Use the visible task console. No implementation module is imported. This file
imports only the reviewer-owned audit_random_trial module beside it.
"""

from __future__ import annotations

import argparse
import json
import math
import traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from audit_random_trial import audit_trial, load, sha


def wilson(successes, n):
    if n == 0:
        return None
    z = 1.959963984540054
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return [center - half, center + half]


def run_one(task):
    row, directory, protocol, frozen = task
    try:
        result = audit_trial(
            directory,
            row["target_m"],
            protocol["standby"]["arm_q_rad"],
            protocol["standby"]["jaw_theta_deg"],
            force_checks=3,
            return_criteria=protocol["return_criteria"],
            timing=protocol["timing_s"],
            approach_offset_m=protocol["planner"]["grip_z_offset_m"],
        )
        result["target_id"] = row["target_id"]
        result["proposal_index"] = row["proposal_index"]
        result["index_status_agrees"] = row["status"] == result["saved_status"]
        meta = load(Path(directory) / "metadata.json")
        provenance = []
        for filename, digest in frozen["inputs"].items():
            if (
                filename.endswith(".py")
                and "/" not in filename
                and meta["source_code_hashes"].get(filename) != digest
            ):
                provenance.append("runtime source hash differs from freeze: " + filename)
        for field in ("python", "numpy", "mujoco"):
            if meta.get(field) != frozen[field]:
                provenance.append("runtime version differs from freeze: " + field)
        for filename, source in (
            ("protocol.json", "protocol.json"),
            ("evaluation_contract.json", "evaluation_contract.json"),
            ("collision_pairs.json", "model/collision_pairs.json"),
            ("assumptions.json", "assumptions.json"),
        ):
            if (
                source in frozen["inputs"]
                and sha(Path(directory) / filename) != frozen["inputs"][source]
            ):
                provenance.append("trial file differs from freeze: " + filename)
        result["provenance_errors"] = provenance
        result["audit_pass"] = (
            result["audit_pass"] and result["index_status_agrees"] and not provenance
        )
        return result
    except Exception as error:  # noqa: BLE001 -- Preserve failed accepted evidence in audit accounting.
        return {
            "target_id": row["target_id"],
            "trial": str(directory),
            "audit_pass": False,
            "exception": f"{type(error).__name__}: {error}",
            "traceback": traceback.format_exc(),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    index = load(args.index)
    protocol = load(args.protocol)
    errors = []

    def need(ok, message):
        if not bool(ok):
            errors.append(message)

    need(index["protocol_sha256"] == sha(args.protocol), "index protocol hash mismatch")
    freeze_path = args.root / "evidence" / (index["name"] + "-freeze.json")
    frozen = load(freeze_path)
    need(index["freeze_sha256"] == sha(freeze_path), "index freeze hash mismatch")
    need(frozen["generator_seed"] == index["generator_seed"], "index seed differs from freeze")
    for filename, digest in frozen["inputs"].items():
        need(sha(args.root / filename) == digest, "frozen input changed: " + filename)
        if not filename.startswith("model/"):
            snapshot = args.root / "evidence" / (index["name"] + "-source") / filename
            need(
                snapshot.is_file() and sha(snapshot) == digest,
                "frozen source snapshot missing/mismatch: " + filename,
            )
    trials = index["trials"]
    rejected = index["rejected"]
    count = index["proposal_count"]
    need(
        len(trials) == protocol["qualification"]["accepted_trial_count"],
        "accepted count differs from preregistration",
    )
    ids = [row["target_id"] for row in trials]
    need(len(set(ids)) == len(ids), "duplicate accepted trial ID")
    need(
        len({row["run_dir"] for row in trials}) == len(trials),
        "duplicate accepted run directory",
    )
    selection = load(args.index.parent / "selection.json")
    selected = selection["selected_before_dynamics"]
    fields = ("target_id", "proposal_index", "target_m", "plan_path")
    selected_identity = [[row[key] for key in fields] for row in selected]
    final_identity = [[row[key] for key in fields] for row in trials]
    need(
        selected_identity == final_identity, "final denominator differs from pre-dynamics selection"
    )
    need(
        selection["protocol_sha256"] == index["protocol_sha256"]
        and selection["freeze_sha256"] == index["freeze_sha256"]
        and selection["generator_seed"] == index["generator_seed"],
        "selection provenance differs from final index",
    )
    accepted_indices = [row["proposal_index"] for row in trials]
    rejected_indices = [row["proposal_index"] for row in rejected]
    all_indices = accepted_indices + rejected_indices
    need(
        len(all_indices) == count
        and len(set(all_indices)) == count
        and set(all_indices) == set(range(count)),
        "proposal accounting missing/duplicate/out-of-range indices",
    )
    need(accepted_indices == sorted(accepted_indices), "accepted targets not in draw order")
    need(count <= protocol["proposal"]["proposal_budget"], "proposal budget exceeded")
    rng = np.random.Generator(np.random.PCG64(index["generator_seed"]))
    xbounds = protocol["proposal"]["x_m"]
    ybounds = protocol["proposal"]["y_m"]
    draws = rng.uniform([xbounds[0], ybounds[0]], [xbounds[1], ybounds[1]], (count, 2))
    z = protocol["proposal"]["z_m"]
    for row in trials + rejected:
        i = row["proposal_index"]
        if isinstance(i, int) and 0 <= i < count:
            expected = np.r_[draws[i], z]
            need(
                np.allclose(row["target_m"], expected, rtol=0, atol=1e-14),
                f"draw differs from frozen PCG64 seed at proposal {i}",
            )
    output_dir = args.output.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    individual = output_dir / (args.output.stem + "-trials")
    individual.mkdir(exist_ok=True)
    tasks = []
    for row in trials:
        directory = Path(row["run_dir"])
        if not directory.is_absolute():
            directory = args.root / directory
        source_plan = load(args.root / row["plan_path"])
        source_plan["timing_s"] = protocol["timing_s"]
        if protocol.get("controller_setdown"):
            source_plan["pregrasp_fraction_on_lift"] = (
                protocol["planner"]["pregrasp_raise_m"] / protocol["planner"]["lift_raise_m"]
            )
        need(
            load(directory / "plan.json") == source_plan,
            "executed plan differs from screened plan: " + str(row["target_id"]),
        )
        tasks.append((row, directory, protocol, frozen))
    results = []
    workers = min(4, max(1, args.workers))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_one, task): task[0]["target_id"] for task in tasks}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            name = str(result["target_id"])
            if not name.replace("-", "").replace("_", "").isalnum():
                name = "trial-" + str(len(results))
            (individual / (name + ".json")).write_text(
                json.dumps(result, indent=2, allow_nan=False) + "\n"
            )
            print(
                f"INDEPENDENT AUDIT {len(results)}/{len(tasks)} {result['target_id']}: "
                f"audit={result['audit_pass']} status={result.get('raw_core_status')} "
                f"errors={result.get('validation_errors', result.get('exception'))}",
                flush=True,
            )
    results.sort(key=lambda row: str(row["target_id"]))
    need(all(row["audit_pass"] for row in results), "one or more independent raw audits failed")
    signatures = {row.get("scene_invariants_sha256") for row in results}
    need(
        len(signatures) == 1 and None not in signatures,
        "physics/scene differs beyond preregistered target and box placement",
    )
    successes = sum(row.get("raw_core_status") == "SUCCESS" for row in results)
    saved_successes = sum(row["status"] == "SUCCESS" for row in trials)
    need(successes == saved_successes, "independent success count differs")
    unsafe = sum(bool(row.get("unsafe_failures")) for row in results)
    invalid_evidence = sum(
        bool(row.get("validation_errors") or row.get("provenance_errors") or row.get("exception"))
        for row in results
    )
    rejected_reasons = Counter(
        str(row.get("reason", row.get("reason_codes", "unspecified"))) for row in rejected
    )
    accepted_xy = np.asarray([row["target_m"][:2] for row in trials])
    proposal_area = (xbounds[1] - xbounds[0]) * (ybounds[1] - ybounds[0])
    coverage = {
        "proposal_area_m2": proposal_area,
        "accepted_coordinate_min_m": accepted_xy.min(axis=0).tolist() if len(trials) else None,
        "accepted_coordinate_max_m": accepted_xy.max(axis=0).tolist() if len(trials) else None,
        "accepted_quadrants": Counter(
            ("x+" if row[0] >= 0 else "x-") + "/" + ("y+" if row[1] >= 0 else "y-")
            for row in accepted_xy
        ),
        "accepted_radius_min_m": float(np.linalg.norm(accepted_xy, axis=1).min())
        if len(trials)
        else None,
        "accepted_radius_max_m": float(np.linalg.norm(accepted_xy, axis=1).max())
        if len(trials)
        else None,
    }
    transfers = [row.get("transfer_diagnostics_non_gating", {}) for row in results]
    speeds = [
        row["cap_center_speed_before_box_contact_m_s"]
        for row in transfers
        if row.get("cap_center_speed_before_box_contact_m_s") is not None
    ]
    forces = [
        row["lower_release_box_force_max_N"]
        for row in transfers
        if row.get("lower_release_box_force_max_N") is not None
    ]
    transfer_summary = {
        "gating": False,
        "trials_with_any_lower_both_finger_contact_absence": sum(
            row.get("lower_first_both_finger_contacts_absent_s") is not None for row in transfers
        ),
        "maximum_contiguous_lower_contact_absence_s": max(
            (row.get("lower_max_both_finger_contact_absence_s", 0.0) for row in transfers),
            default=None,
        ),
        "maximum_lower_grip_relative_displacement_m": max(
            (row.get("lower_grip_relative_displacement_max_m", 0.0) for row in transfers),
            default=None,
        ),
        "cap_center_speed_before_box_contact_min_m_s": min(speeds, default=None),
        "cap_center_speed_before_box_contact_max_m_s": max(speeds, default=None),
        "lower_release_box_force_max_N": max(forces, default=None),
        "interpretation": "Per-step contact-loss diagnostics, not a new pass/fail criterion; a passed hold does not establish continuous secure holding through setdown.",
    }
    report = {
        "index": str(args.index.resolve().relative_to(args.root.resolve())),
        "index_sha256": sha(args.index),
        "protocol_sha256": sha(args.protocol),
        "errors": errors,
        "audit_pass": not errors,
        "trial_count": len(trials),
        "successes": successes,
        "saved_successes": saved_successes,
        "unsafe_trials": unsafe,
        "wilson_95_interval": wilson(successes, len(trials)),
        "invalid_evidence_trials": invalid_evidence,
        "proposals": count,
        "rejected": len(rejected),
        "acceptance_rate": len(trials) / count if count else None,
        "rejection_reasons": rejected_reasons,
        "coverage": coverage,
        "transfer_diagnostics_non_gating": transfer_summary,
        "engineering_acceptance": (
            not errors
            and successes >= protocol["qualification"]["minimum_successes"]
            and unsafe <= protocol["qualification"]["maximum_unsafe_trials"]
        ),
        "trials": results,
        "scope": "Every saved raw trajectory independently reevaluated; nominal frozen screened distribution only."
        " Wilson interval is not a global or real-world guarantee; sequentially selected batch coverage is descriptive.",
    }
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps({k: v for k, v in report.items() if k != "trials"}, indent=2, allow_nan=False),
        flush=True,
    )
    raise SystemExit(0 if report["audit_pass"] else 1)


if __name__ == "__main__":
    main()
