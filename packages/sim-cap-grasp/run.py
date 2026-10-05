"""Seeded actuator-only R3/C7 approach, grasp, lift, hold, and release trial."""

from __future__ import annotations

import argparse
import json
import math
import platform
import shutil
import time
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np

from build_scene import MODEL, ROOT, place_reset, save_json, sha
from evaluate import evaluate_run, validate_model


def smooth(value):
    x = float(np.clip(value, 0, 1))
    return x * x * (3 - 2 * x)


def interpolate(plan, segment, fraction):
    points = [x for x in plan["waypoints"] if x["segment"] == segment]
    fs = [x["fraction"] for x in points]
    q = np.array([np.interp(fraction, fs, [x["q"][i] for x in points]) for i in range(4)])
    target = np.array(
        [np.interp(fraction, fs, [x["target_m"][i] for x in points]) for i in range(3)]
    )
    return q, target


def reference(plan, t, no_close):
    open_q = math.radians(plan["jaw_open_theta_deg"] - 90)
    closed_q = math.radians(plan["jaw_close_theta_deg"] - 90)
    if t < 0.5:
        phase = "settle"
        q = np.array(plan["pregrasp_q"])
        target = np.array(plan["pregrasp_target_m"])
        jaw = open_q
    elif t < 3.0:
        phase = "approach"
        q, target = interpolate(plan, "approach", smooth((t - 0.5) / 2.0))
        jaw = open_q
    elif t < 4.5:
        phase = "alignment"
        q, target = interpolate(plan, "alignment", smooth((t - 3.0) / 1.5))
        jaw = open_q
    elif t < 6.5:
        phase = "close"
        q = np.array(plan["alignment_q"])
        target = np.array(plan["closing_target_m"])
        f = smooth((t - 4.5) / 1.5)
        jaw = (1 - f) * open_q + f * closed_q
    elif t < 9.0:
        phase = "lift"
        q, target = interpolate(plan, "lift", smooth((t - 6.5) / 2.5))
        jaw = closed_q
    elif t < 11.5:
        phase = "hold"
        q = np.array(plan["lift_q"])
        target = np.array(plan["lift_target_m"])
        jaw = closed_q
    else:
        phase = "release"
        q = np.array(plan["lift_q"])
        target = np.array(plan["lift_target_m"])
        f = smooth((t - 11.5) / 1.0)
        jaw = (1 - f) * closed_q + f * open_q
    if no_close:
        jaw = open_q
    return phase, q, target, jaw


def run(args):
    for name in ("friction", "mass", "duration", "timestep"):
        value = getattr(args, name)
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    if args.timestep > args.duration or not 0 <= args.seed < 2**32:
        raise ValueError("Invalid timestep/duration or seed")
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Preserving existing trial: {output}")
    plan = json.loads((ROOT / "plan.json").read_text())
    assumptions = json.loads((ROOT / "assumptions.json").read_text())
    audit = json.loads((MODEL / "audit.json").read_text())
    if audit.get("builder_sha256") != sha(ROOT / "build_scene.py"):
        raise ValueError("Stale model: latest builder must complete successfully first")
    if plan.get("ik_sha256") != sha(ROOT / "ik.py") or plan.get("model_sha256") != sha(
        MODEL / "scene.xml"
    ):
        raise ValueError("Stale plan: current model/IK must pass path validation first")
    for asset, digest in audit["mesh_assets_sha256"].items():
        if sha(MODEL / "meshes" / asset) != digest:
            raise ValueError(f"Model mesh asset hash mismatch: {asset}")
    output.mkdir(parents=True)
    tree = ET.parse(MODEL / "scene.xml")
    import os

    tree.find("compiler").set("meshdir", os.path.relpath(MODEL / "meshes", output))
    tree.find("option").set("timestep", str(args.timestep))
    tree.find(".//geom[@name='cap_geom']").set("mass", str(args.mass))
    for pair in tree.findall("contact/pair"):
        pair.set("friction", f"{args.friction} {args.friction} 0.001 0.0001 0.0001")
    tree.write(output / "scene.xml", encoding="unicode")
    for filename in ("evaluation_contract.json", "plan.json", "assumptions.json"):
        shutil.copyfile(ROOT / filename, output / filename)
    shutil.copyfile(MODEL / "collision_pairs.json", output / "collision_pairs.json")
    model = mujoco.MjModel.from_xml_path(str(output / "scene.xml"))
    errors = validate_model(model)
    if errors:
        raise ValueError(errors)
    data = mujoco.MjData(model)
    np.random.seed(args.seed)
    mujoco.mj_resetData(model, data)
    place_reset(model, data, plan["pregrasp_q"], plan["jaw_open_theta_deg"])
    metadata = {
        "schema_version": 3,
        "mesh_assets_sha256": audit["mesh_assets_sha256"],
        "seed": args.seed,
        "friction": args.friction,
        "cap_mass_kg": args.mass,
        "no_close": args.no_close,
        "timestep_s": args.timestep,
        "python": platform.python_version(),
        "mujoco": mujoco.__version__,
        "numpy": np.__version__,
        "initial_support_plane_z_m": assumptions["nominal"]["box"]["top_m"],
        "initial_cap_center_m": assumptions["nominal"]["cap"]["initial_center_m"],
        "approach_target_position_m": plan["grasp_target_m"],
        "runtime_pose_writes": False,
        "external_forces_applied": False,
        "hardware_access": False,
        "scene_registration": "nominal",
        "calibration_verified": False,
        "evaluation_contract_sha256": sha(output / "evaluation_contract.json"),
        "scene_xml_sha256": sha(output / "scene.xml"),
        "collision_policy_sha256": sha(output / "collision_pairs.json"),
        "source_code_hashes": {p.name: sha(p) for p in ROOT.glob("*.py")},
        "controller": {
            "type": "bounded MuJoCo position servo with implicit velocity feedback + model bias feedforward; controls are radians",
            "arm_kp_Nm_per_rad": 60.0,
            "arm_kd_Nm_s_per_rad": 2.0,
            "jaw_kp_Nm_per_rad": 0.12,
            "jaw_kd_Nm_s_per_rad": 0.003,
            "arm_torque_bound_Nm": 1.0,
            "jaw_torque_bound_Nm": 0.08,
        },
    }
    save_json(output / "metadata.json", metadata)
    keys = [
        "time",
        "qpos",
        "qvel",
        "qacc",
        "ctrl",
        "phase",
        "target_position",
        "grip_position",
        "grip_rotation",
        "cap_position",
        "cap_axis",
        "pitch",
        "warnings",
        "solver_iterations",
        "external_force_norm",
        "actuator_force",
        "target_q",
        "target_jaw",
        "left_force",
        "right_force",
    ]
    states = {key: [] for key in keys}
    joint_ids = [model.joint(f"cad_j{i}").id for i in range(1, 5)]
    dofs = [int(model.jnt_dofadr[i]) for i in joint_ids]
    jaw = model.joint("gripper_delta")
    jv = int(jaw.dofadr[0])
    cap = model.body("cap").id
    site = model.site("grip").id
    policy = json.loads((output / "collision_pairs.json").read_text())
    geoms = {g["name"]: g for g in policy["geoms"]}
    pairs = {tuple(sorted((p["group1"], p["group2"]))): p["class"] for p in policy["group_pairs"]}
    started = time.monotonic()
    last_phase = None
    stop_reason = None
    failure_exception = None
    steps = round(args.duration / model.opt.timestep)
    print(
        f"Trial seed={args.seed}, mass={args.mass}kg, friction={args.friction}, no_close={args.no_close}; {steps} physics steps",
        flush=True,
    )
    try:
        with (output / "contacts.jsonl").open("w") as contacts_file:
            for step in range(steps + 1):
                phase, qref, target, jref = reference(plan, data.time, args.no_close)
                mujoco.mj_step1(model, data)
                # MuJoCo's affine velocity bias is integrated implicitly; a
                # Python explicit -Kd*qvel motor law produced a sampled limit cycle.
                data.ctrl[:4] = np.clip(
                    qref + data.qfrc_bias[dofs] / 60,
                    model.actuator_ctrlrange[:4, 0],
                    model.actuator_ctrlrange[:4, 1],
                )
                data.ctrl[4] = np.clip(
                    jref + data.qfrc_bias[jv] / 0.12, *model.actuator_ctrlrange[4]
                )
                # Log a fully forwarded, same-time state BEFORE integrating it.
                mujoco.mj_forward(model, data)
                raw = []
                left_force = 0.0
                right_force = 0.0
                forbidden = []
                for ci, c in enumerate(data.contact):
                    force = np.zeros(6)
                    mujoco.mj_contactForce(model, data, ci, force)
                    a, b = model.geom(c.geom1).name, model.geom(c.geom2).name
                    raw.append(
                        {
                            "geom1": a,
                            "geom2": b,
                            "distance": float(c.dist),
                            "force": force.tolist(),
                            "position_m": c.pos.tolist(),
                            "contact_frame": c.frame.tolist(),
                        }
                    )
                    aa, bb = geoms[a], geoms[b]
                    rule = pairs[tuple(sorted((aa["group_id"], bb["group_id"])))]
                    if rule == "forbidden" and (force[0] > 0.00001 or c.dist < -0.0001):
                        forbidden.append((a, b, float(force[0]), float(c.dist)))
                    if a == "cap_geom" or b == "cap_geom":
                        other = bb if a == "cap_geom" else aa
                        if other["category"] == "softtip":
                            if other["side"] == "L":
                                left_force += max(0, float(force[0]))
                            else:
                                right_force += max(0, float(force[0]))
                contacts_file.write(
                    json.dumps(
                        {"i": step, "time": float(data.time), "contacts": raw}, allow_nan=False
                    )
                    + "\n"
                )
                row = {
                    "time": float(data.time),
                    "qpos": data.qpos.copy(),
                    "qvel": data.qvel.copy(),
                    "qacc": data.qacc.copy(),
                    "ctrl": data.ctrl.copy(),
                    "phase": phase,
                    "target_position": target.copy(),
                    "grip_position": data.site_xpos[site].copy(),
                    "grip_rotation": data.site_xmat[site].reshape(3, 3).copy(),
                    "cap_position": data.xpos[cap].copy(),
                    "cap_axis": data.xmat[cap].reshape(3, 3)[:, 2].copy(),
                    "pitch": float(-data.qpos[1] + data.qpos[2] + data.qpos[3]),
                    "warnings": int(np.sum(data.warning.number)),
                    "solver_iterations": int(np.max(data.solver_niter)),
                    "external_force_norm": float(
                        np.linalg.norm(data.xfrc_applied) + np.linalg.norm(data.qfrc_applied)
                    ),
                    "actuator_force": data.actuator_force.copy(),
                    "target_q": qref.copy(),
                    "target_jaw": jref,
                    "left_force": left_force,
                    "right_force": right_force,
                }
                for key in keys:
                    states[key].append(row[key])
                if phase != last_phase:
                    print(
                        f"t={data.time:.3f}s phase={phase} cap_z={data.xpos[cap, 2] * 1000:.2f}mm left={left_force:.5f}N right={right_force:.5f}N",
                        flush=True,
                    )
                    last_phase = phase
                if forbidden:
                    stop_reason = {
                        "code": "COLLISION",
                        "time": float(data.time),
                        "contacts": forbidden[:15],
                    }
                    break
                if (
                    row["warnings"]
                    or not np.isfinite(data.qpos).all()
                    or not np.isfinite(data.qvel).all()
                ):
                    stop_reason = {"code": "UNSTABLE", "time": float(data.time)}
                    break
                if (
                    phase == "lift"
                    and data.time < 6.502
                    and not args.no_close
                    and (left_force < 0.00001 or right_force < 0.00001)
                ):
                    stop_reason = {
                        "code": "NO_GRIP",
                        "time": float(data.time),
                        "left_N": left_force,
                        "right_N": right_force,
                    }
                    break
                if (
                    phase in {"lift", "hold"}
                    and data.time > 6.55
                    and not args.no_close
                    and left_force < 0.00001
                    and right_force < 0.00001
                ):
                    stop_reason = {
                        "code": "SLIP",
                        "time": float(data.time),
                        "left_N": left_force,
                        "right_N": right_force,
                    }
                    break
                mujoco.mj_step(model, data)
    except (Exception, KeyboardInterrupt) as exc:  # noqa: BLE001 -- Preserve partial evidence.
        failure_exception = f"{type(exc).__name__}: {exc}"
        (output / "exception.txt").write_text(traceback.format_exc())
    finally:
        np.savez_compressed(output / "states.npz", **{k: np.asarray(v) for k, v in states.items()})
        metadata.update(
            wall_time_s=time.monotonic() - started,
            stop_reason=stop_reason,
            exception=failure_exception,
            completed_samples=len(states["time"]),
            planned_samples=steps + 1,
            normal_completion=not stop_reason
            and not failure_exception
            and len(states["time"]) == steps + 1,
        )
        save_json(output / "metadata.json", metadata)
    result = evaluate_run(output)
    if stop_reason:
        result["status"] = "FAILURE"
        result["reason_codes"] = list(dict.fromkeys(result["reason_codes"] + [stop_reason["code"]]))
        result["stop_reason"] = stop_reason
    if failure_exception:
        result["status"] = "FAILURE"
        result["reason_codes"] = list(dict.fromkeys(result["reason_codes"] + ["MODEL_INVALID"]))
        result["exception"] = failure_exception
    save_json(output / "result.json", result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "reason_codes": result["reason_codes"],
                "metrics": result["metrics"],
                "stop_reason": stop_reason,
                "wall_time_s": metadata["wall_time_s"],
                "output": str(output),
            },
            indent=2,
        ),
        flush=True,
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-close", action="store_true")
    parser.add_argument("--friction", type=float, default=0.7)
    parser.add_argument("--mass", type=float, default=0.0015)
    parser.add_argument("--duration", type=float, default=13.0)
    parser.add_argument("--timestep", type=float, default=0.001)
    args = parser.parse_args()
    result = run(args)
    raise SystemExit(0 if result["status"] == "SUCCESS" else 1)
