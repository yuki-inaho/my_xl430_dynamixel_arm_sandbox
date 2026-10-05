"""Four-axis bounded damped-least-squares IK using MuJoCo's site Jacobian."""

from __future__ import annotations

import argparse
import json
import math

import mujoco
import numpy as np

from build_scene import ARM_LIMITS, MODEL, ROOT, place_reset, save_json, sha


def angle_error(value):
    return math.atan2(math.sin(value), math.cos(value))


def fk(model, data, q):
    data.qpos[:4] = q
    mujoco.mj_kinematics(model, data)
    mujoco.mj_comPos(model, data)
    return data.site_xpos[model.site("grip").id].copy(), float(-q[1] + q[2] + q[3])


def solve(model, target, pitch, seed, max_iterations=180):
    data = mujoco.MjData(model)
    place_reset(model, data, np.asarray(seed), 50)
    q = np.clip(np.asarray(seed, dtype=float), ARM_LIMITS[:, 0] + 1e-5, ARM_LIMITS[:, 1] - 1e-5)
    weight = 0.06
    damping = 0.0003
    best = None
    for iteration in range(max_iterations):
        pos, actual_pitch = fk(model, data, q)
        error = np.r_[target - pos, weight * angle_error(pitch - actual_pitch)]
        cost = float(np.linalg.norm(error))
        if best is None or cost < best["weighted_error"]:
            best = {
                "q": q.copy(),
                "weighted_error": cost,
                "position_error_m": float(np.linalg.norm(error[:3])),
                "pitch_error_rad": abs(float(error[3] / weight)),
                "iterations": iteration + 1,
            }
        if best["position_error_m"] < 0.00005 and best["pitch_error_rad"] < 0.0005:
            break
        jp, jr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
        mujoco.mj_jacSite(model, data, jp, jr, model.site("grip").id)
        jac = np.vstack([jp[:, :4], weight * np.array([0, -1, 1, 1])])
        step = jac.T @ np.linalg.solve(jac @ jac.T + damping * damping * np.eye(4), error)
        step *= min(1, 0.18 / max(np.max(np.abs(step)), 1e-12))
        accepted = False
        for scale in (1.0, 0.5, 0.25, 0.1):
            candidate = np.clip(q + scale * step, ARM_LIMITS[:, 0] + 1e-5, ARM_LIMITS[:, 1] - 1e-5)
            pp, aa = fk(model, data, candidate)
            cc = np.linalg.norm(np.r_[target - pp, weight * angle_error(pitch - aa)])
            if cc < cost - 1e-12:
                q = candidate
                accepted = True
                damping = max(0.0001, damping * 0.7)
                break
        if not accepted:
            damping = min(0.1, damping * 3)
            if damping >= 0.1:
                break
    best["status"] = (
        "SUCCESS"
        if best["position_error_m"] <= 0.002 and best["pitch_error_rad"] <= math.radians(2)
        else "IK_FAILED"
    )
    best["q"] = best["q"].tolist()
    return best


def multistart(model, target, pitch, preferred=None):
    seeds = [] if preferred is None else [preferred]
    seeds += [
        np.deg2rad([0, shoulder, elbow, math.degrees(pitch) + shoulder - elbow])
        for shoulder, elbow in (
            (0, 0),
            (20, -30),
            (-20, -60),
            (30, 30),
            (-30, 30),
            (0, 70),
            (0, -90),
        )
    ]
    results = [solve(model, np.asarray(target), pitch, s) for s in seeds]
    return min(results, key=lambda x: x["weighted_error"])


def forbidden_contacts(model, data, policy):
    geoms = {g["name"]: g for g in policy["geoms"]}
    pairs = {tuple(sorted((p["group1"], p["group2"]))): p["class"] for p in policy["group_pairs"]}
    bad = []
    for c in data.contact:
        a, b = model.geom(c.geom1).name, model.geom(c.geom2).name
        x, y = geoms[a], geoms[b]
        rule = pairs[tuple(sorted((x["group_id"], y["group_id"])))]
        if rule == "forbidden" and c.dist < -0.0001:
            bad.append({"geom1": a, "geom2": b, "distance_m": float(c.dist)})
    return bad


def main(y_offset=0.0, fixed_pitch=None, close_angle=90.0, grasp_pitch=None, grasp_z_offset=0.006):
    model = mujoco.MjModel.from_xml_path(str(MODEL / "scene.xml"))
    assumptions = json.loads((ROOT / "assumptions.json").read_text())
    policy = json.loads((MODEL / "collision_pairs.json").read_text())
    center = np.array(assumptions["nominal"]["cap"]["initial_center_m"])
    # Upper-half pinch avoids table contact by the tip outer envelope. The cap
    # itself is never moved from the independently observed nominal location.
    target = center + np.array([0, 0, 0.006])
    trials = []
    for degrees in [-60, -50, -40, -30, -20, 0] if fixed_pitch is None else [fixed_pitch]:
        pitch = math.radians(degrees)
        poses = []
        seed = None
        for stage, position in [
            ("pregrasp", target + [0, 0, 0.035]),
            ("approach", target),
            ("lift", target + [0, 0, 0.040]),
        ]:
            result = multistart(model, position, pitch, seed)
            data = mujoco.MjData(model)
            place_reset(model, data, result["q"], 50)
            bad = forbidden_contacts(model, data, policy)
            poses.append(
                {
                    "stage": stage,
                    "target_m": position.tolist(),
                    **result,
                    "forbidden_contacts": bad[:20],
                    "forbidden_count": len(bad),
                }
            )
            seed = result["q"]
        trials.append(
            {
                "pitch_deg": degrees,
                "poses": poses,
                "feasible": all(
                    p["status"] == "SUCCESS" and not p["forbidden_count"] for p in poses
                ),
            }
        )
        print(
            "reachability",
            degrees,
            [
                (
                    p["stage"],
                    p["status"],
                    round(p["position_error_m"] * 1000, 3),
                    p["forbidden_count"],
                )
                for p in poses
            ],
            flush=True,
        )
    feasible = [x for x in trials if x["feasible"]]
    preferred = next(
        (x for x in feasible if x["pitch_deg"] == -50), feasible[0] if feasible else None
    )
    generated = []
    for q in np.deg2rad([[0, 10, -20, 15], [20, -15, 40, -35], [-20, 25, 40, -70]]):
        data = mujoco.MjData(model)
        place_reset(model, data, q, 50)
        pos, pitch = fk(model, data, q)
        result = multistart(model, pos, pitch)
        generated.append(result)
    unreachable = multistart(model, np.array([2, 2, 2]), 0)
    report = {
        "algorithm": "MuJoCo mj_jacSite bounded DLS, 4 position/pitch tasks; no roll",
        "position_tolerance_m": 0.002,
        "pitch_tolerance_deg": 2,
        "trials": trials,
        "FK_generated_tests": generated,
        "unreachable_test": unreachable,
        "selected": preferred,
    }
    save_json(ROOT / "evidence/ik-validation.json", report)
    if (
        preferred is None
        or unreachable["status"] != "IK_FAILED"
        or any(x["status"] != "SUCCESS" for x in generated)
    ):
        raise SystemExit("IK_FAILED: inspect saved reachability evidence; target unchanged")
    # Waypoints get checked with the same model before any dynamics trial.
    waypoints = []
    poses = preferred["poses"]
    grasp_angle = math.radians(preferred["pitch_deg"] if grasp_pitch is None else grasp_pitch)
    closing_target = center + np.array([0, y_offset, grasp_z_offset])
    aligned = multistart(model, closing_target, grasp_angle, poses[1]["q"])
    aligned.update(stage="alignment", target_m=closing_target.tolist())
    lifted = multistart(
        model, closing_target + [0, 0, 0.04], math.radians(preferred["pitch_deg"]), aligned["q"]
    )
    lifted.update(stage="lift", target_m=(closing_target + [0, 0, 0.04]).tolist())
    segments = [
        (
            poses[0],
            poses[1],
            math.radians(preferred["pitch_deg"]),
            math.radians(preferred["pitch_deg"]),
        ),
        (poses[1], aligned, math.radians(preferred["pitch_deg"]), grasp_angle),
        (aligned, lifted, grasp_angle, math.radians(preferred["pitch_deg"])),
    ]
    for begin, end, pitch_start, pitch_end in segments:
        q = np.array(begin["q"])
        for f in np.linspace(0, 1, 31):
            point = (1 - f) * np.array(begin["target_m"]) + f * np.array(end["target_m"])
            res = solve(model, point, (1 - f) * pitch_start + f * pitch_end, q)
            data = mujoco.MjData(model)
            place_reset(model, data, res["q"], 50)
            bad = forbidden_contacts(model, data, policy)
            waypoints.append(
                {
                    "segment": end["stage"],
                    "fraction": float(f),
                    "target_m": point.tolist(),
                    **res,
                    "forbidden_count": len(bad),
                    "forbidden_contacts": bad[:10],
                }
            )
            q = np.array(res["q"])
    save_json(ROOT / "evidence/ik-waypoints.json", waypoints)
    if any(x["status"] != "SUCCESS" or x["forbidden_count"] for x in waypoints):
        raise SystemExit("IK_FAILED: path collision/reach check failed, no trial launched")
    contract = json.loads((ROOT / "evaluation_contract.json").read_text())
    contract.update(
        pitch_target_rad=math.radians(preferred["pitch_deg"]),
        pitch_error_max_rad=math.radians(2),
        pitch_status="Fixed by saved reachability before judged trials",
    )
    save_json(ROOT / "evaluation_contract.json", contract)
    save_json(
        ROOT / "plan.json",
        {
            "pitch_rad": contract["pitch_target_rad"],
            "grasp_target_m": target.tolist(),
            "ik_sha256": sha(ROOT / "ik.py"),
            "model_sha256": sha(MODEL / "scene.xml"),
            "approach_offset_from_cap_center_m": [0, 0, 0.006],
            "grasp_offset_from_cap_center_m": [0, y_offset, grasp_z_offset],
            "pregrasp_target_m": poses[0]["target_m"],
            "lift_target_m": lifted["target_m"],
            "pregrasp_q": poses[0]["q"],
            "approach_q": poses[1]["q"],
            "lift_q": lifted["q"],
            "alignment_q": aligned["q"],
            "closing_target_m": closing_target.tolist(),
            "grasp_pitch_rad": grasp_angle,
            "jaw_open_theta_deg": 50,
            "jaw_close_theta_deg": close_angle,
            "waypoints": waypoints,
        },
    )
    print(
        "Reachability and93pathwaypoints PASS; fixed approach pitch=",
        preferred["pitch_deg"],
        "post-approach grasp alignment pitch=",
        math.degrees(grasp_angle),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--y-offset", type=float, default=0.0)
    parser.add_argument("--fixed-pitch", type=float)
    parser.add_argument("--close-angle", type=float, default=90.0)
    parser.add_argument("--grasp-pitch", type=float)
    parser.add_argument("--grasp-z-offset", type=float, default=0.006)
    args = parser.parse_args()
    if not 25 <= args.close_angle <= 135:
        parser.error("close-angle must stay within unchanged CAD25..135deg range")
    main(args.y_offset, args.fixed_pitch, args.close_angle, args.grasp_pitch, args.grasp_z_offset)
