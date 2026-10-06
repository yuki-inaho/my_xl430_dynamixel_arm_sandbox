"""Outcome-independent analytical IK and finite-sample motion screening.

The original support is translated with each target. All model geometry and
physical parameters are preserved. This is a reproducible geometric screen,
not a proof of continuous collision-free or dynamically feasible motion.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import mujoco
import numpy as np

from build_scene import ARM_LIMITS, MODEL, ROOT, place_reset, save_json, sha


def wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


def analytic_ik(model, target, pitch, preferred=None):
    """Enumerate both radial/elbow branches; validate every answer using MuJoCo.

    Source offsets: shoulder x=-.0002,z=.0563; upper arm yz=(.0148,.1083),
    forearm y=.0901; wrist+grip yz=(.140,.002), grip x=-.0035.
    q2 rotates about -X; q3 and q4 rotate about +X.
    """
    target = np.asarray(target, dtype=float)
    if target.shape != (3,) or not np.isfinite(target).all():
        return []
    xoff = -0.0037
    radius2 = float(target[0] ** 2 + target[1] ** 2)
    if radius2 < xoff * xoff - 1e-14:
        return []
    l1, l2 = math.hypot(0.0148, 0.1083), 0.0901
    delta = math.atan2(0.1083, 0.0148)
    wy = 0.14 * math.cos(pitch) - 0.002 * math.sin(pitch)
    wz = 0.14 * math.sin(pitch) + 0.002 * math.cos(pitch)
    data = mujoco.MjData(model)
    candidates = []
    for sign in (1, -1):
        local_y = sign * math.sqrt(max(0.0, radius2 - xoff * xoff))
        q1 = wrap(math.atan2(target[1], target[0]) - math.atan2(local_y, xoff))
        yy, zz = local_y - wy, target[2] - 0.0563 - wz
        cosine = (yy * yy + zz * zz - l1 * l1 - l2 * l2) / (2 * l1 * l2)
        if cosine < -1 - 1e-10 or cosine > 1 + 1e-10:
            continue
        for elbow_sign in (1, -1):
            relative = elbow_sign * math.acos(float(np.clip(cosine, -1, 1)))
            alpha = math.atan2(zz, yy) - math.atan2(
                l2 * math.sin(relative), l1 + l2 * math.cos(relative)
            )
            q2 = wrap(delta - alpha)
            q3 = wrap(delta + relative)
            for wrist_turn in (-1, 0, 1):
                q4 = pitch + q2 - q3 + wrist_turn * 2 * math.pi
                q = np.array([q1, q2, q3, q4])
                if np.any(q < ARM_LIMITS[:, 0] + 1e-6) or np.any(q > ARM_LIMITS[:, 1] - 1e-6):
                    continue
                place_reset(model, data, q, 50)
                error = float(np.linalg.norm(data.site_xpos[model.site("grip").id] - target))
                pitch_error = abs(wrap(float(-q2 + q3 + q4 - pitch)))
                if error > 1e-7 or pitch_error > 1e-7:
                    raise ValueError(f"Analytic derivation/FK mismatch: {error}, {pitch_error}")
                candidates.append(
                    {
                        "q": q.tolist(),
                        "position_error_m": error,
                        "pitch_error_rad": pitch_error,
                        "radial_sign": sign,
                        "elbow_sign": elbow_sign,
                        "wrist_turn": wrist_turn,
                    }
                )
    reference = np.zeros(4) if preferred is None else np.asarray(preferred)
    candidates.sort(key=lambda x: (float(np.linalg.norm(np.asarray(x["q"]) - reference)), x["q"]))
    return candidates


def proposal_targets(protocol, seed, count):
    rng = np.random.default_rng(seed)
    p = protocol["proposal"]
    points = rng.uniform([p["x_m"][0], p["y_m"][0]], [p["x_m"][1], p["y_m"][1]], (count, 2))
    return np.c_[points, np.full(count, p["z_m"])]


def make_checker(model, target, policy):
    geoms = {g["name"]: g for g in policy["geoms"]}
    pairs = {tuple(sorted((p["group1"], p["group2"]))): p["class"] for p in policy["group_pairs"]}
    cap_adr = (
        int(model.joint("cap_free").qposadr[0])
        if "cap_free" in [model.joint(i).name for i in range(model.njnt)]
        else int(model.jnt_qposadr[model.body_jntadr[model.body("cap").id]])
    )
    data = mujoco.MjData(model)

    def check(q, theta, cap_z_offset=0):
        mujoco.mj_resetData(model, data)
        data.qpos[cap_adr : cap_adr + 3] = target + np.array([0.0, 0.0, cap_z_offset])
        place_reset(model, data, q, theta)
        bad = []
        for index, contact in enumerate(data.contact):
            a, b = model.geom(contact.geom1).name, model.geom(contact.geom2).name
            x, y = geoms[a], geoms[b]
            if pairs[tuple(sorted((x["group_id"], y["group_id"])))] != "forbidden":
                continue
            force = np.zeros(6)
            mujoco.mj_contactForce(model, data, index, force)
            if force[0] > 1e-5 or contact.dist < -0.0001:
                bad.append(
                    {
                        "geom1": a,
                        "geom2": b,
                        "distance_m": float(contact.dist),
                        "normal_force_N": float(force[0]),
                    }
                )
        return bad

    return check


def plan_target(target, protocol, model=None):
    target = np.asarray(target, dtype=float)
    model = mujoco.MjModel.from_xml_path(str(MODEL / "scene.xml")) if model is None else model
    model.geom_pos[model.geom("box").id] = [target[0], target[1], 0.025]
    policy = json.loads((MODEL / "collision_pairs.json").read_text())
    check = make_checker(model, target, policy)
    cfg = protocol["planner"]
    pitch = math.radians(cfg["pitch_deg"])
    standby = np.array(protocol["standby"]["arm_q_rad"])
    theta_open = protocol["standby"]["jaw_theta_deg"]
    theta_closed = cfg["jaw_close_theta_deg"]
    grip = target + [0, 0, cfg["grip_z_offset_m"]]
    targets = {
        "pregrasp": grip + [0, 0, cfg["pregrasp_raise_m"]],
        "approach": grip,
        "lift": grip + [0, 0, cfg["lift_raise_m"]],
    }
    result = {
        "status": "REJECTED",
        "reason": None,
        "target_m": target.tolist(),
        "support_center_m": [float(target[0]), float(target[1]), 0.025],
        "standby_q": standby.tolist(),
        "ik_endpoints_feasible": False,
        "forbidden_contacts": [],
        "screened_samples": [],
        "waypoints": [],
        "planner_sha256": sha(Path(__file__)),
        "protocol_sha256": sha(ROOT / "protocol.json"),
        "model_sha256": sha(MODEL / "scene.xml"),
        "pitch_rad": pitch,
        "jaw_open_theta_deg": theta_open,
        "jaw_close_theta_deg": theta_closed,
        "grasp_target_m": grip.tolist(),
        "closing_target_m": grip.tolist(),
    }
    # Check every endpoint first, independent of any collision/path outcome.
    solutions = {name: analytic_ik(model, point, pitch, standby) for name, point in targets.items()}
    result["endpoint_branch_counts"] = {name: len(branches) for name, branches in solutions.items()}
    if any(not branches for branches in solutions.values()):
        result["reason"] = "ENDPOINT_IK_FAILED"
        return result
    result["ik_endpoints_feasible"] = True
    bad = check(standby, theta_open)
    if bad:
        result.update(reason="STANDBY_COLLISION", forbidden_contacts=bad)
        return result
    poses = {}
    prior = standby
    for name in ("pregrasp", "approach", "lift"):
        branches = analytic_ik(model, targets[name], pitch, prior)
        poses[name] = branches[0]
        prior = np.array(branches[0]["q"])
        result[name + "_q"] = branches[0]["q"]
        result[name + "_target_m"] = targets[name].tolist()
    result["alignment_q"] = poses["approach"]["q"]
    for name in ("transit", "approach", "lift"):
        if name == "transit":
            begin, end = standby, np.asarray(poses["pregrasp"]["q"])
            count = max(
                2, math.ceil(float(np.max(np.abs(end - begin))) / cfg["joint_sample_step_rad"]) + 1
            )
            entries = []
            for fraction in np.linspace(0, 1, count):
                q = begin + fraction * (end - begin)
                data = mujoco.MjData(model)
                place_reset(model, data, q, theta_open)
                point = data.site_xpos[model.site("grip").id].copy()
                entries.append(
                    {"fraction": float(fraction), "q": q.tolist(), "target_m": point.tolist()}
                )
        else:
            begin_name, end_name = (
                ("pregrasp", "approach") if name == "approach" else ("approach", "lift")
            )
            begin, end = targets[begin_name], targets[end_name]
            count = max(
                2,
                math.ceil(float(np.linalg.norm(end - begin)) / cfg["cartesian_sample_step_m"]) + 1,
            )
            entries = []
            prior = np.array(poses[begin_name]["q"])
            fractions = list(np.linspace(0, 1, count))
            if name == "lift":
                fractions.append(cfg["pregrasp_raise_m"] / cfg["lift_raise_m"])
            for fraction in sorted(set(fractions)):
                point = begin + fraction * (end - begin)
                branches = analytic_ik(model, point, pitch, prior)
                if not branches:
                    result["reason"] = "PATH_IK_FAILED"
                    return result
                chosen = branches[0]
                prior = np.array(chosen["q"])
                entries.append({"fraction": float(fraction), **chosen, "target_m": point.tolist()})
        # A Cartesian path segment may have large joint increments: inspect
        # interpolation substeps as well, using the same interpolation as runtime.
        dense = []
        for i, entry in enumerate(entries):
            if i:
                previous = entries[i - 1]
                qa, qb = np.array(previous["q"]), np.array(entry["q"])
                n = math.ceil(float(np.max(np.abs(qb - qa))) / cfg["joint_sample_step_rad"])
                for sub in range(1, n):
                    f = sub / n
                    dense.append(
                        {
                            "fraction": previous["fraction"]
                            + f * (entry["fraction"] - previous["fraction"]),
                            "q": (qa + f * (qb - qa)).tolist(),
                            "target_m": (
                                np.array(previous["target_m"])
                                + f * (np.array(entry["target_m"]) - previous["target_m"])
                            ).tolist(),
                        }
                    )
            dense.append(entry)
        for entry in dense:
            offset = entry["fraction"] * cfg["lift_raise_m"] if name == "lift" else 0
            theta = theta_closed if name == "lift" else theta_open
            bad = check(entry["q"], theta, offset)
            result["screened_samples"].append(
                {
                    "segment": name,
                    "fraction": entry["fraction"],
                    "q": entry["q"],
                    "theta_deg": theta,
                    "cap_z_offset_m": offset,
                    "forbidden_count": len(bad),
                }
            )
            if bad:
                result.update(reason="PATH_COLLISION", failed_segment=name, forbidden_contacts=bad)
                return result
            result["waypoints"].append({"segment": name, **entry})
    for theta in np.linspace(
        theta_open,
        theta_closed,
        math.ceil(abs(theta_closed - theta_open) / cfg["jaw_sample_step_deg"]) + 1,
    ):
        bad = check(poses["approach"]["q"], float(theta))
        result["screened_samples"].append(
            {
                "segment": "close_and_release",
                "q": poses["approach"]["q"],
                "theta_deg": float(theta),
                "forbidden_count": len(bad),
            }
        )
        if bad:
            result.update(reason="CLOSE_COLLISION", forbidden_contacts=bad)
            return result
    # End references must use the branch actually reached by interpolation.
    for segment, pose_key in (
        ("transit", "pregrasp_q"),
        ("approach", "alignment_q"),
        ("lift", "lift_q"),
    ):
        last = [p for p in result["waypoints"] if p["segment"] == segment][-1]
        if np.max(np.abs(np.asarray(last["q"]) - result[pose_key])) > 1e-7:
            result.update(reason="PATH_BRANCH_DISCONTINUITY", failed_segment=segment)
            return result
    result.update(
        status="ACCEPTED",
        reason=None,
        reverse_segments="lower reverses lift at closed jaw; release reverses close on support; retract reverses approach; return reverses transit",
        approximation="Finite samples only; carried cap screening is upright nominal at translated height, actual dynamic cap pose is checked in every runtime step",
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", nargs=3, type=float, default=[0, 0.18, 0.0575])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = plan_target(args.target, json.loads((ROOT / "protocol.json").read_text()))
    save_json(args.output, result)
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in ("waypoints", "screened_samples")},
            indent=2,
        )
    )
    print("screened_samples", len(result["screened_samples"]))
    raise SystemExit(0 if result["status"] == "ACCEPTED" else 1)


if __name__ == "__main__":
    main()
