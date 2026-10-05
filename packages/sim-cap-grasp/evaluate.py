"""Independent, fail-closed evaluation from raw physics-step state and contacts."""

from __future__ import annotations

import argparse
import gzip
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np

from build_scene import save_json, sha


def validate_model(model):
    errors = []
    if not np.array_equal(model.opt.gravity, [0, 0, -9.81]):
        errors.append("gravity_not_normal")
    forbidden_flags = sum(
        int(x)
        for x in (
            mujoco.mjtDisableBit.mjDSBL_GRAVITY,
            mujoco.mjtDisableBit.mjDSBL_CONTACT,
            mujoco.mjtDisableBit.mjDSBL_CONSTRAINT,
            mujoco.mjtDisableBit.mjDSBL_ACTUATION,
            mujoco.mjtDisableBit.mjDSBL_EQUALITY,
            mujoco.mjtDisableBit.mjDSBL_LIMIT,
        )
    )
    if int(model.opt.disableflags) & forbidden_flags:
        errors.append("required_physics_disabled")
    cap = model.body("cap").id
    joints = np.where(model.jnt_bodyid == cap)[0]
    if len(joints) != 1 or model.jnt_type[joints[0]] != mujoco.mjtJoint.mjJNT_FREE:
        errors.append("cap_not_single_freejoint")
    elif (
        model.jnt_stiffness[joints[0]] != 0
        or np.any(
            model.dof_damping[
                int(model.jnt_dofadr[joints[0]]) : int(model.jnt_dofadr[joints[0]]) + 6
            ]
            != 0
        )
        or np.any(
            model.dof_frictionloss[
                int(model.jnt_dofadr[joints[0]]) : int(model.jnt_dofadr[joints[0]]) + 6
            ]
            != 0
        )
    ):
        errors.append("cap_passive_support")
    if model.opt.density != 0 or model.opt.viscosity != 0:
        errors.append("fluid_support_present")
    if model.ntendon or model.nplugin:
        errors.append("unverified_tendon_or_plugin")
    if model.body_mocapid[cap] >= 0 or model.nmocap != 0:
        errors.append("mocap_present")
    if model.body_parentid[cap] != 0:
        errors.append("cap_attached_to_robot")
    if model.nu != 5 or not np.isfinite(model.actuator_forcerange).all():
        errors.append("actuator_inventory_invalid")
    expected_targets = [model.joint(f"cad_j{i}").id for i in range(1, 5)] + [
        model.joint("gripper_delta").id
    ]
    if not np.array_equal(model.actuator_trnid[:, 0], expected_targets) or not np.all(
        model.actuator_trntype == mujoco.mjtTrn.mjTRN_JOINT
    ):
        errors.append("actuator_targets_invalid")
    if not np.all(model.actuator_forcelimited):
        errors.append("unbounded_actuator")
    for i in range(model.neq):
        if model.eq_type[i] == mujoco.mjtEq.mjEQ_WELD or cap in (
            model.eq_obj1id[i],
            model.eq_obj2id[i],
        ):
            errors.append("cap_or_weld_equality")
    if (
        not np.isfinite(model.body_mass).all()
        or np.any(model.body_mass[1:] <= 0)
        or not np.isfinite(model.body_inertia).all()
        or np.any(model.body_inertia[1:] <= 0)
    ):
        errors.append("invalid_inertia")
    if np.any(model.body_gravcomp != 0):
        errors.append("cap_gravity_compensation")
    return errors


def invalid(message, code="MODEL_INVALID"):
    return {
        "status": "FAILURE",
        "reason_codes": [code],
        "diagnostics": [message],
        "metrics": {},
        "scene_registration": "nominal",
        "hardware_success": "not_tested",
    }


def evaluate_arrays(model, states, contact_rows, metadata, contract, policy):
    errors = validate_model(model)
    if errors:
        return invalid(",".join(errors))
    required = {
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
    }
    if required - set(states):
        return invalid("missing_trace_fields:" + ",".join(sorted(required - set(states))))
    required_contract = [
        "cap_bottom_clearance_m",
        "continuous_hold_s",
        "bilateral_contact_fraction_min",
        "grip_frame_center_drift_max_m",
        "approach_position_error_max_m",
        "pitch_target_rad",
        "pitch_error_max_rad",
        "normal_force_epsilon_N",
        "forbidden_penetration_tolerance_m",
        "joint_angle_boundary_tolerance_rad",
        "joint_slide_boundary_tolerance_m",
        "initial_support_height_tolerance_m",
    ]
    for key in required_contract:
        v = contract.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not np.isfinite(v):
            return invalid(f"invalid_contract:{key}")
        if key != "pitch_target_rad" and v <= 0:
            return invalid(f"nonpositive_contract:{key}")
    fixed = {
        "cap_bottom_clearance_m": 0.020,
        "continuous_hold_s": 2.0,
        "bilateral_contact_fraction_min": 0.80,
        "grip_frame_center_drift_max_m": 0.005,
        "approach_position_error_max_m": 0.002,
        "normal_force_epsilon_N": 0.00001,
        "forbidden_penetration_tolerance_m": 0.0001,
        "joint_angle_boundary_tolerance_rad": 0.0001,
        "joint_slide_boundary_tolerance_m": 0.00001,
        "initial_support_height_tolerance_m": 0.0005,
    }
    if any(contract[k] != v for k, v in fixed.items()):
        return invalid("fixed_original_contract_or_numerical_rule_modified")
    if abs(contract["pitch_target_rad"]) > np.pi or contract["pitch_error_max_rad"] > np.pi:
        return invalid("pitch_contract_out_of_domain")
    t = states["time"]
    n = len(t)
    if n < 3 or len(contact_rows) != n:
        return invalid("empty_short_or_missing_contact_trace")
    for key in required:
        a = states[key]
        if len(a) != n:
            return invalid(f"mismatched_length:{key}")
        if key != "phase" and not np.isfinite(a).all():
            return invalid(f"nonfinite:{key}", "UNSTABLE")
    if states["qpos"].shape != (n, model.nq) or states["qvel"].shape != (n, model.nv):
        return invalid("invalid_state_dimensions")
    shapes = {
        "time": (n,),
        "qacc": (n, model.nv),
        "ctrl": (n, model.nu),
        "phase": (n,),
        "target_position": (n, 3),
        "grip_position": (n, 3),
        "cap_position": (n, 3),
        "cap_axis": (n, 3),
        "pitch": (n,),
        "warnings": (n,),
        "solver_iterations": (n,),
        "external_force_norm": (n,),
    }
    if any(states[k].shape != shape for k, shape in shapes.items()):
        return invalid("invalid_trace_dimensions")
    if np.any(states["external_force_norm"] < 0) or np.any(states["solver_iterations"] < 0):
        return invalid("negative_unsigned_diagnostic")
    if states["grip_rotation"].shape != (n, 3, 3):
        return invalid("invalid_grip_rotation_shape")
    dt = np.diff(t)
    if np.any(dt <= 0) or not np.allclose(dt, model.opt.timestep, atol=1e-9, rtol=1e-7):
        return invalid("time_reset_missing_steps_or_timestep_mismatch", "UNSTABLE")
    orth = states["grip_rotation"].transpose(0, 2, 1) @ states["grip_rotation"]
    if not np.allclose(orth, np.eye(3), atol=1e-7) or not np.allclose(
        np.linalg.norm(states["cap_axis"], axis=1), 1, atol=1e-7
    ):
        return invalid("invalid_rotation_or_cap_axis")
    cap_id = model.body("cap").id
    cap_qadr = model.jnt_qposadr[model.body_jntadr[cap_id]]
    if not np.allclose(
        states["qpos"][:, cap_qadr : cap_qadr + 3], states["cap_position"], atol=1e-9
    ):
        return invalid("cap_position_disagrees_with_raw_state")
    # Recompute geometric observables from raw generalized coordinates rather
    # than accepting a runner's precomputed drift/height/approach summary.
    fk = mujoco.MjData(model)
    grip_id = model.site("grip").id
    for i in range(n):
        fk.qpos[:] = states["qpos"][i]
        mujoco.mj_kinematics(model, fk)
        if (
            not np.allclose(fk.site_xpos[grip_id], states["grip_position"][i], atol=1e-9)
            or not np.allclose(
                fk.site_xmat[grip_id].reshape(3, 3), states["grip_rotation"][i], atol=1e-9
            )
            or not np.allclose(
                fk.xmat[cap_id].reshape(3, 3)[:, 2], states["cap_axis"][i], atol=1e-9
            )
        ):
            return invalid("logged_geometry_disagrees_with_raw_fk")
    computed_pitch = (
        -states["qpos"][:, model.joint("cad_j2").qposadr[0]]
        + states["qpos"][:, model.joint("cad_j3").qposadr[0]]
        + states["qpos"][:, model.joint("cad_j4").qposadr[0]]
    )
    if not np.allclose(np.sin(computed_pitch - states["pitch"]), 0, atol=1e-9) or not np.allclose(
        np.cos(computed_pitch - states["pitch"]), 1, atol=1e-9
    ):
        return invalid("logged_pitch_disagrees_with_raw_state")
    geom_map = {x["name"]: x for x in policy["geoms"]}
    physical = {
        model.geom(i).name
        for i in range(model.ngeom)
        if model.geom_contype[i] or model.geom_conaffinity[i]
    }
    if set(geom_map) != physical:
        return invalid("collision_policy_physical_coverage_mismatch")
    pair_map = {
        tuple(sorted((x["group1"], x["group2"]))): x["class"] for x in policy["group_pairs"]
    }
    groups = policy["groups"]
    ng = len(groups)
    if len(pair_map) != ng * (ng - 1) // 2 or len(geom_map) != len(policy["geoms"]):
        return invalid("incomplete_or_duplicate_collision_policy")
    for geom in policy["geoms"]:
        gid = model.geom(geom["name"]).id
        group = groups[geom["group_id"]]
        if (
            model.geom_contype[gid] != 1 << group["id"]
            or model.geom_conaffinity[gid] != group["mask"]
        ):
            return invalid("collision_policy_disagrees_with_compiled_model")
    for pair in policy["group_pairs"]:
        a, b = groups[pair["group1"]], groups[pair["group2"]]
        enabled = bool((a["mask"] & (1 << b["id"])) or (b["mask"] & (1 << a["id"])))
        if enabled != pair["enabled"]:
            return invalid("collision_policy_matrix_disagrees_with_masks")
        categories = {a["category"], b["category"]}
        expected = (
            (
                "left_right_grip"
                if categories == {"cap", "softtip"}
                else "support_allowed_outside_hold"
                if categories == {"cap", "support"}
                else "forbidden"
            )
            if enabled
            else "intentional_rigid_or_adjacent_joint_mount"
        )
        if pair["class"] != expected:
            return invalid("collision_classification_semantics_invalid")
    eps = contract["normal_force_epsilon_N"]
    left, right, support = np.zeros(n), np.zeros(n), np.zeros(n, dtype=bool)
    forbidden = []
    for i, row in enumerate(contact_rows):
        if (
            row.get("i") != i
            or isinstance(row.get("time"), bool)
            or not isinstance(row.get("time"), (int, float))
            or not np.isfinite(row["time"])
            or abs(row["time"] - t[i]) > 1e-9
            or not isinstance(row.get("contacts"), list)
        ):
            return invalid("contact_row_index_or_time_mismatch")
        for contact in row.get("contacts", []):
            names = [contact.get("geom1"), contact.get("geom2")]
            if any(name not in geom_map for name in names):
                return invalid("unclassified_contact:" + str(names))
            force = np.asarray(contact.get("force", []))
            if (
                force.shape != (6,)
                or not np.isfinite(force).all()
                or not np.isfinite(contact.get("distance", np.nan))
            ):
                return invalid("invalid_contact_force_or_distance")
            a, b = (geom_map[x] for x in names)
            if a["group_id"] == b["group_id"]:
                return invalid("unexpected_same_group_contact")
            rule = pair_map[tuple(sorted((a["group_id"], b["group_id"])))]
            active = force[0] > eps
            if (
                rule == "forbidden"
                and (active or contact["distance"] < -contract["forbidden_penetration_tolerance_m"])
                and len(forbidden) < 50
            ):
                forbidden.append(
                    {
                        "i": i,
                        "time": float(t[i]),
                        "pair": names,
                        "force_N": float(force[0]),
                        "distance_m": contact["distance"],
                    }
                )
            if "cap_geom" in names:
                other = b if names[0] == "cap_geom" else a
                if active and other["category"] == "softtip":
                    if other["side"] == "L":
                        left[i] += force[0]
                    elif other["side"] == "R":
                        right[i] += force[0]
                elif active:
                    support[i] = True
    reasons = []
    if forbidden:
        reasons.append("COLLISION")
    if np.any(states["warnings"] != 0) or np.any(
        states["solver_iterations"] >= model.opt.iterations
    ):
        reasons.append("UNSTABLE")
    if np.any(states["external_force_norm"] > 0):
        reasons.append("MODEL_INVALID")
    if metadata.get("runtime_pose_writes") is not False:
        reasons.append("MODEL_INVALID")
    boundary = []
    for jid in range(model.njnt):
        if not model.jnt_limited[jid]:
            continue
        q = states["qpos"][:, model.jnt_qposadr[jid]]
        tol = (
            contract["joint_slide_boundary_tolerance_m"]
            if model.jnt_type[jid] == mujoco.mjtJoint.mjJNT_SLIDE
            else contract["joint_angle_boundary_tolerance_rad"]
        )
        if np.any(q < model.jnt_range[jid, 0] - tol) or np.any(q > model.jnt_range[jid, 1] + tol):
            boundary.append(model.joint(jid).name)
    if boundary:
        reasons.append("COLLISION")
    radius = model.geom_size[model.geom("cap_geom").id, 0]
    halfheight = model.geom_size[model.geom("cap_geom").id, 1]
    az = np.clip(np.abs(states["cap_axis"][:, 2]), 0, 1)
    bottom = states["cap_position"][:, 2] - halfheight * az - radius * np.sqrt(1 - az * az)
    surface = metadata.get("initial_support_plane_z_m")
    if (
        isinstance(surface, bool)
        or not isinstance(surface, (int, float))
        or not np.isfinite(surface)
    ):
        return invalid("missing_initial_support_datum")
    clearance = bottom - surface
    settled = np.where(states["phase"] == "settle")[0]
    if (
        len(settled) == 0
        or not support[settled[-1]]
        or abs(clearance[settled[-1]]) > contract["initial_support_height_tolerance_m"]
    ):
        reasons.append("MODEL_INVALID")
    approach = np.where(states["phase"] == "approach")[0]
    position_error = None
    pitch_error = None
    if len(approach):
        j = approach[-1]
        position_error = float(
            np.linalg.norm(states["grip_position"][j] - states["target_position"][j])
        )
        pitch_error = float(
            abs(
                np.arctan2(
                    np.sin(states["pitch"][j] - contract["pitch_target_rad"]),
                    np.cos(states["pitch"][j] - contract["pitch_target_rad"]),
                )
            )
        )
    if (
        position_error is None
        or position_error > contract["approach_position_error_max_m"]
        or pitch_error > contract["pitch_error_max_rad"]
    ):
        reasons.append("IK_FAILED")
    valid = (
        (states["phase"] == "hold") & (clearance >= contract["cap_bottom_clearance_m"]) & ~support
    )
    interval = None
    start = None
    for i, good in enumerate(valid):
        if not good:
            start = None
        elif start is None:
            start = i
        if start is not None and t[i] - t[start] >= contract["continuous_hold_s"] - 1e-9:
            interval = (start, i)
            break
    metrics = {
        "approach_position_error_m": position_error,
        "approach_pitch_error_rad": pitch_error,
        "max_cap_bottom_clearance_m": float(np.max(clearance)),
        "max_left_normal_force_N": float(np.max(left)),
        "max_right_normal_force_N": float(np.max(right)),
        "max_solver_iterations": int(np.max(states["solver_iterations"])),
        "forbidden_contact_examples": forbidden,
        "joint_boundary_violations": boundary,
        "samples": n,
        "timestep_s": model.opt.timestep,
        "simulated_duration_s": float(t[-1] - t[0]),
    }
    if interval is None:
        reasons.append("INSUFFICIENT_LIFT")
        if not np.any((left > eps) & (right > eps)):
            reasons.append("NO_GRIP")
    else:
        a, b = interval
        rel = np.einsum(
            "nji,nj->ni",
            states["grip_rotation"][a : b + 1],
            states["cap_position"][a : b + 1] - states["grip_position"][a : b + 1],
        )
        drift = float(np.linalg.norm(rel - rel[0], axis=1).max())
        bilateral = (left[a:b] > eps) & (right[a:b] > eps)
        fraction = float(np.sum(dt[a:b] * bilateral) / (t[b] - t[a]))
        metrics.update(
            hold_start_s=float(t[a]),
            hold_end_s=float(t[b]),
            hold_duration_s=float(t[b] - t[a]),
            hold_bottom_clearance_min_m=float(clearance[a : b + 1].min()),
            hold_bilateral_fraction=fraction,
            hold_grip_frame_drift_max_m=drift,
            hold_support_contact_count=int(support[a : b + 1].sum()),
        )
        if fraction < contract["bilateral_contact_fraction_min"]:
            reasons.append("NO_GRIP")
        if drift > contract["grip_frame_center_drift_max_m"]:
            reasons.append("SLIP")
    return {
        "status": "FAILURE" if reasons else "SUCCESS",
        "reason_codes": list(dict.fromkeys(reasons)),
        "metrics": metrics,
        "scene_registration": "nominal",
        "observed_target_fidelity": "unverified",
        "hardware_success": "not_tested",
        "evaluation_contract": contract,
    }


def evaluate_run(directory):
    directory = Path(directory)
    try:
        metadata = json.loads((directory / "metadata.json").read_text())
        model_path = directory / "scene.xml"
        model = mujoco.MjModel.from_xml_path(str(model_path))
        contract = json.loads((directory / "evaluation_contract.json").read_text())
        if sha(directory / "evaluation_contract.json") != metadata["evaluation_contract_sha256"]:
            return invalid("contract_hash_mismatch")
        if sha(model_path) != metadata["scene_xml_sha256"]:
            return invalid("model_hash_mismatch")
        if metadata.get("schema_version", 1) >= 3:
            tree = ET.parse(model_path)
            meshdir = directory / tree.find("compiler").get("meshdir", "")
            assets = {a.get("file") for a in tree.findall("asset/mesh")}
            hashes = metadata.get("mesh_assets_sha256", {})
            if assets != hashes.keys() or any(sha(meshdir / a) != hashes[a] for a in assets):
                return invalid("model_mesh_asset_hash_mismatch")
        with np.load(directory / "states.npz", allow_pickle=False) as f:
            states = {key: f[key] for key in f.files}
        plain, compressed = directory / "contacts.jsonl", directory / "contacts.jsonl.gz"
        if plain.exists() and compressed.exists():
            return invalid("ambiguous_contact_trace")
        with plain.open() if plain.exists() else gzip.open(compressed, "rt") as stream:
            contacts = [json.loads(line) for line in stream]
        if sha(directory / "collision_pairs.json") != metadata["collision_policy_sha256"]:
            return invalid("collision_policy_hash_mismatch")
        policy = json.loads((directory / "collision_pairs.json").read_text())
        result = evaluate_arrays(model, states, contacts, metadata, contract, policy)
        if metadata.get("completed_samples") != len(states.get("time", [])):
            return invalid("metadata_sample_count_mismatch")
        if metadata.get("exception"):
            result["status"] = "FAILURE"
            result["reason_codes"] = list(dict.fromkeys(result["reason_codes"] + ["MODEL_INVALID"]))
            result["runtime_exception"] = metadata["exception"]
        if metadata.get("stop_reason"):
            result["status"] = "FAILURE"
            reason = metadata["stop_reason"].get("code", "MODEL_INVALID")
            result["reason_codes"] = list(dict.fromkeys(result["reason_codes"] + [reason]))
        if metadata.get("schema_version", 1) >= 2 and not metadata.get("normal_completion", False):
            result["status"] = "FAILURE"
            if not metadata.get("stop_reason") and not metadata.get("exception"):
                result["reason_codes"] = list(
                    dict.fromkeys(result["reason_codes"] + ["MODEL_INVALID"])
                )
        if metadata.get("normal_completion") and metadata.get("planned_samples") != len(
            states["time"]
        ):
            return invalid("normal_completion_sample_count_mismatch")
        result["evaluation_contract_sha256"] = sha(directory / "evaluation_contract.json")
        return result
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        return invalid(f"unreadable_or_invalid_trace:{exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    result = evaluate_run(args.run_dir)
    save_json(args.run_dir / "independent-evaluation.json", result)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "SUCCESS" else 1)
