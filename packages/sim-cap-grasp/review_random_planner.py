"""Independent FK-generated branch and stage-continuity tests, visible console.

Expected positions use MuJoCo directly, without the task's FK helper. The tested
inverse/planner is imported from the implementation supplied on the command line.
These are development tests and are never counted as held-out grasp trials.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from collections import Counter
from pathlib import Path

import mujoco
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("tested_random_plan", root / "random_plan.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model = mujoco.MjModel.from_xml_path(str(root / "model/scene.xml"))
    data = mujoco.MjData(model)
    sid = int(model.site("grip").id)
    qadr = [int(model.joint(f"cad_j{i}").qposadr[0]) for i in range(1, 5)]
    limits = np.array([model.jnt_range[model.joint(f"cad_j{i}").id] for i in range(1, 5)])
    pitch = math.radians(-50)
    seed = 610202611
    rng = np.random.Generator(np.random.PCG64(seed))
    cases = []
    while len(cases) < 240:
        q = rng.uniform(limits[:, 0] + 1e-5, limits[:, 1] - 1e-5)
        for turn in (-1, 0, 1):
            q[3] = pitch + q[1] - q[2] + turn * 2 * math.pi
            if limits[3, 0] + 1e-5 < q[3] < limits[3, 1] - 1e-5:
                cases.append(("random_fk", q.copy()))
                break
    for q1 in (-math.pi + 1e-5, math.pi - 1e-5, 0):
        for q2 in (limits[1, 0] + 1e-5, 0, limits[1, 1] - 1e-5):
            q3 = 0.0
            cases.append(("yaw_shoulder_boundary", np.array([q1, q2, q3, pitch + q2 - q3])))
    delta = math.atan2(0.1083, 0.0148)
    for relative in (0.0, 1e-8, -1e-8, math.pi, math.pi - 1e-8, -math.pi + 1e-8):
        q3 = math.atan2(math.sin(delta + relative), math.cos(delta + relative))
        q4 = pitch - q3
        cases.append(("elbow_singular", np.array([0.7, 0, q3, q4])))
    for q3 in (-math.pi + 1e-5, math.pi - 1e-5):
        q2 = -0.5
        q4 = pitch + q2 - q3
        q4 = math.atan2(math.sin(q4), math.cos(q4))
        cases.append(("elbow_wrap", np.array([-0.8, q2, q3, q4])))
    failures = []
    branch_counts = Counter()
    max_error = 0.0
    maximum_roundtrip = 0.0
    negative_radial_expected = 0
    for name, q in cases:
        if np.any(q <= limits[:, 0]) or np.any(q >= limits[:, 1]):
            failures.append({"case": name, "error": "invalid reviewer fixture", "q": q.tolist()})
            continue
        data.qpos[qadr] = q
        mujoco.mj_kinematics(model, data)
        target = data.site_xpos[sid].copy()
        local_y = -math.sin(q[0]) * target[0] + math.cos(q[0]) * target[1]
        negative_radial_expected += local_y < 0
        answers = module.analytic_ik(model, target, pitch, q)
        if not answers:
            failures.append(
                {
                    "case": name,
                    "error": "FK-reachable target rejected",
                    "q": q.tolist(),
                    "target": target.tolist(),
                }
            )
            continue
        roundtrip = min(float(np.max(np.abs(np.asarray(a["q"]) - q))) for a in answers)
        maximum_roundtrip = max(maximum_roundtrip, roundtrip)
        if roundtrip > 2e-6:
            failures.append(
                {
                    "case": name,
                    "error": "original branch missing",
                    "maximum_joint_error_rad": roundtrip,
                    "q": q.tolist(),
                    "returned": [a["q"] for a in answers],
                }
            )
        for answer in answers:
            qa = np.asarray(answer["q"])
            data.qpos[qadr] = qa
            mujoco.mj_kinematics(model, data)
            err = float(np.linalg.norm(data.site_xpos[sid] - target))
            max_error = max(max_error, err)
            branch_counts[
                f"radial{answer['radial_sign']}/elbow{answer['elbow_sign']}/turn{answer['wrist_turn']}"
            ] += 1
            if err > 1e-7 or np.any(qa < limits[:, 0]) or np.any(qa > limits[:, 1]):
                failures.append(
                    {"case": name, "error": "returned branch invalid", "position_error_m": err}
                )
    if negative_radial_expected == 0:
        failures.append({"error": "reviewer suite lacks negative-radial input"})
    protocol = json.loads((root / "protocol.json").read_text())
    plans = []
    for radius in (0.15, 0.18, 0.23):
        for angle in np.linspace(-math.pi, math.pi, 8, endpoint=False):
            target = np.array([radius * math.sin(angle), radius * math.cos(angle), 0.0575])
            result = module.plan_target(target, protocol, model)
            entry = {
                "target_m": target.tolist(),
                "status": result["status"],
                "reason": result["reason"],
            }
            if result["status"] == "ACCEPTED":
                chains = {
                    segment: [r for r in result["waypoints"] if r["segment"] == segment]
                    for segment in ("transit", "approach", "lift")
                }
                continuity = []
                expected = [
                    (chains["transit"][0]["q"], protocol["standby"]["arm_q_rad"]),
                    (chains["transit"][-1]["q"], chains["approach"][0]["q"]),
                    (chains["approach"][-1]["q"], result["approach_q"]),
                    (chains["approach"][-1]["q"], chains["lift"][0]["q"]),
                    (chains["lift"][-1]["q"], result["lift_q"]),
                ]
                for a, b in expected:
                    continuity.append(float(np.max(np.abs(np.asarray(a) - b))))
                entry["max_phase_boundary_jump_rad"] = max(continuity)
                if max(continuity) > 1e-7:
                    failures.append({"error": "phase-boundary branch jump", **entry})
                for segment, points in chains.items():
                    qs = np.asarray([row["q"] for row in points])
                    step = float(np.max(np.abs(np.diff(qs, axis=0))))
                    if step > protocol["planner"]["joint_sample_step_rad"] + 1e-10:
                        failures.append(
                            {
                                "error": "screen joint sampling exceeds limit",
                                "segment": segment,
                                "max_step_rad": step,
                            }
                        )
            plans.append(entry)
            print(
                f"REVIEW PLAN r={radius:.3f} yaw={math.degrees(angle):.1f}: "
                f"{result['status']} {result['reason']}",
                flush=True,
            )
    report = {
        "pass": not failures,
        "failures": failures,
        "fk_generated_cases": len(cases),
        "fk_generator_seed": seed,
        "negative_radial_inputs": int(negative_radial_expected),
        "returned_branch_counts": branch_counts,
        "maximum_FK_error_m": max_error,
        "maximum_original_branch_joint_error_rad": maximum_roundtrip,
        "static_plan_probes": plans,
        "dynamic_trials": 0,
        "scope": "Analytic IK branch correctness and screened-stage consistency; not complete reachability or dynamic grasp proof",
    }
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, indent=2, allow_nan=False), flush=True)
    raise SystemExit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
