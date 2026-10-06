"""Independent raw-physics acceptance audit; imports no task implementation.

Run only through the task's visible fixed-job console. Recomputes observables
from saved qpos and contacts, checks frozen initial conditions, and performs
sparse same-state forward force checks. This is not a dynamics replay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def iter_contact_lines(trial, statistics):
    """Independent lossless reader; verify exact plaintext and storage hashes."""
    trial = Path(trial)
    plain = trial / "contacts.jsonl"
    compressed = trial / "contacts.jsonl.zst"
    storage = load(trial / "storage.json") if (trial / "storage.json").exists() else None
    if sum((trial / ("contacts.jsonl" + s)).exists() for s in ("", ".gz", ".zst")) != 1:
        raise ValueError("Missing or ambiguous contact trace")
    entry = storage.get("contacts") if storage else None
    process = None
    compressed_verified = False
    if entry and compressed.is_file():
        if (
            sha(compressed) != entry["compressed_sha256"]
            or compressed.stat().st_size != entry["compressed_bytes"]
        ):
            raise ValueError("Compressed contact SHA/size mismatch")
        compressed_verified = True
    if plain.is_file():
        handle = plain.open("rb")
        source = "plain"
    elif compressed.is_file():
        if not entry or entry.get("codec") != "zstd":
            raise ValueError("Compressed contacts lack supported lossless storage metadata")
        if entry.get("path") != "contacts.jsonl.zst" or storage.get("lossless") is not True:
            raise ValueError("Compressed contact path/lossless declaration mismatch")
        process = subprocess.Popen(
            ["zstd", "-dc", "--", str(compressed)], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        handle = process.stdout
        source = "zstd"
    else:
        raise FileNotFoundError("Neither plaintext nor compressed contact trace exists")
    digest = hashlib.sha256()
    size = 0
    try:
        for line in handle:
            digest.update(line)
            size += len(line)
            yield line
    finally:
        handle.close()
        if process:
            stderr = process.stderr.read().decode("utf-8", errors="replace")
            process.stderr.close()
            code = process.wait()
            if code:
                raise ValueError(f"zstd decompression failed ({code}): {stderr}")
    actual = digest.hexdigest()
    if entry and (actual != entry["uncompressed_sha256"] or size != entry["uncompressed_bytes"]):
        raise ValueError("Decompressed/plain contact SHA/size mismatch")
    statistics.update(
        source=source,
        plain_sha256=actual,
        plain_bytes=size,
        lossless_metadata_verified=entry is not None,
        compressed_sha_verified=compressed_verified,
    )


def scene_signature(path):
    """Everything except asset locator and the preregistered cap/box XY placement."""
    tree = ET.parse(path)
    root = tree.getroot()
    compiler = root.find("compiler")
    if compiler is not None:
        compiler.attrib.pop("meshdir", None)
    cap = root.find(".//body[@name='cap']")
    if cap is not None:
        position = cap.attrib.get("pos", "0 0 0").split()
        cap.set("pos", "0 0 " + position[2])
    box = root.find(".//geom[@name='box']")
    if box is not None:
        position = box.attrib.get("pos", "0 0 0").split()
        box.set("pos", "0 0 " + position[2])
    return hashlib.sha256(ET.tostring(root)).hexdigest()


def audit_trial(
    trial,
    expected_target=None,
    expected_standby=None,
    expected_jaw_degrees=50.0,
    force_checks=5,
    return_criteria=None,
    translated_box=True,
    timing=None,
    approach_offset_m=0.006,
):
    trial = Path(trial)
    meta = load(trial / "metadata.json")
    contract = load(trial / "evaluation_contract.json")
    policy = load(trial / "collision_pairs.json")
    saved = load(trial / "result.json")
    saved_protocol = load(trial / "protocol.json") if (trial / "protocol.json").exists() else {}
    model = mujoco.MjModel.from_xml_path(str(trial / "scene.xml"))
    with np.load(trial / "states.npz", allow_pickle=False) as z:
        states = {k: z[k] for k in z.files}
    validation = []
    reasons = []
    safety = []

    def need(ok, message):
        if not bool(ok):
            validation.append(message)

    def reject(message, unsafe=False):
        reasons.append(message)
        if unsafe:
            safety.append(message)

    t = states["time"]
    n = len(t)
    need(n > 0, "empty trace")
    if not n:
        return {"trial": str(trial), "validation_errors": validation, "audit_pass": False}
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
        "actuator_force",
    }
    need(not required - states.keys(), "missing required raw fields")
    if required - states.keys():
        return {"trial": str(trial), "validation_errors": validation, "audit_pass": False}
    for key, value in states.items():
        need(len(value) == n, "length mismatch: " + key)
        if value.dtype.kind in "fiu":
            need(np.isfinite(value).all(), "nonfinite raw field: " + key)
    need(states["qpos"].shape == (n, model.nq), "qpos dimensions")
    need(states["qvel"].shape == (n, model.nv), "qvel dimensions")
    need(states["ctrl"].shape == (n, model.nu), "ctrl dimensions")
    need(abs(t[0]) <= 1e-12, "time does not start at reset")
    need(
        np.all(np.diff(t) > 0)
        and np.allclose(np.diff(t), model.opt.timestep, rtol=1e-7, atol=1e-9),
        "time reset/gap/missing physics samples",
    )
    need(meta.get("completed_samples") == n, "metadata count mismatch")
    need(meta.get("runtime_pose_writes") is False, "runtime pose writes not excluded")
    need(meta.get("external_forces_applied") is False, "external forces not excluded")
    for file, field in (
        ("scene.xml", "scene_xml_sha256"),
        ("evaluation_contract.json", "evaluation_contract_sha256"),
        ("collision_pairs.json", "collision_policy_sha256"),
    ):
        need(meta.get(field) == sha(trial / file), "hash mismatch: " + file)
    for file, field in (("protocol.json", "protocol_sha256"), ("plan.json", "plan_sha256")):
        if field in meta:
            need(meta[field] == sha(trial / file), "hash mismatch: " + file)
    if meta.get("exception"):
        reject("runtime_exception", True)
    if meta.get("stop_reason"):
        reject("abnormal_stop:" + str(meta["stop_reason"].get("code")))
    if meta.get("normal_completion") is not True:
        reject("incomplete_cycle")
    else:
        need(meta.get("planned_samples") == n, "normal completion count mismatch")
    if timing is not None:
        if abs(t[-1] - timing["final_end"]) > 1e-8:
            reject("planned_cycle_duration_not_reached")
        thresholds = (
            "settle_end",
            "transit_end",
            "approach_end",
            "alignment_end",
            "close_end",
            "lift_end",
            "hold_end",
            "lower_end",
            "release_end",
            "retract_end",
            "return_end",
        )
        labels = (
            "settle",
            "transit",
            "approach",
            "alignment",
            "close",
            "lift",
            "hold",
            "lower",
            "release",
            "retract",
            "return",
        )
        expected_phases = np.select(
            [t < timing[key] for key in thresholds], labels, default="standby_final"
        )
        need(
            np.array_equal(states["phase"], expected_phases),
            "phase labels differ from frozen timing",
        )

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
    for key, value in fixed.items():
        need(
            type(contract.get(key)) in (int, float) and contract[key] == value,
            "inherited criterion changed: " + key,
        )
    need(abs(contract["pitch_target_rad"] - math.radians(-50)) < 1e-12, "fixed pitch changed")
    need(
        abs(contract["pitch_error_max_rad"] - math.radians(2)) < 1e-12,
        "fixed pitch tolerance changed",
    )
    need(np.array_equal(model.opt.gravity, [0, 0, -9.81]), "normal gravity")
    for name in ("CONSTRAINT", "CONTACT", "GRAVITY", "ACTUATION", "EQUALITY", "LIMIT"):
        bit = int(getattr(mujoco.mjtDisableBit, "mjDSBL_" + name))
        need(not int(model.opt.disableflags) & bit, "disabled physics: " + name)
    need(
        model.nmocap == 0 and model.ntendon == 0 and model.nplugin == 0,
        "unexpected mocap/tendon/plugin",
    )
    need(np.all(model.body_gravcomp == 0), "body gravity compensation")
    need(model.opt.density == 0 and model.opt.viscosity == 0, "fluid support")
    cap = int(model.body("cap").id)
    capj = int(model.body_jntadr[cap])
    cq = int(model.jnt_qposadr[capj])
    cv = int(model.jnt_dofadr[capj])
    need(
        model.body_parentid[cap] == 0
        and model.body_jntnum[cap] == 1
        and model.jnt_type[capj] == mujoco.mjtJoint.mjJNT_FREE,
        "cap is not independent free body",
    )
    need(
        model.jnt_stiffness[capj] == 0
        and np.all(model.dof_damping[cv : cv + 6] == 0)
        and np.all(model.dof_frictionloss[cv : cv + 6] == 0),
        "cap hidden spring/damping/friction support",
    )
    for i in range(model.neq):
        need(
            model.eq_type[i] == mujoco.mjtEq.mjEQ_CONNECT
            and cap not in (model.eq_obj1id[i], model.eq_obj2id[i]),
            "unexpected/cap equality",
        )
    expected = [int(model.joint(f"cad_j{i}").id) for i in range(1, 5)]
    expected.append(int(model.joint("gripper_delta").id))
    need(
        model.nu == 5 and np.array_equal(model.actuator_trnid[:, 0], expected),
        "actuator inventory/targets",
    )
    need(np.all(model.actuator_forcelimited), "unbounded actuator")
    need(np.isfinite(model.body_mass).all() and np.all(model.body_mass[1:] > 0), "body masses")
    need(
        np.isfinite(model.body_inertia).all() and np.all(model.body_inertia[1:] > 0),
        "body inertias",
    )
    if np.any(states["warnings"] != 0):
        reject("solver_warning", True)
    if np.any(states["solver_iterations"] < 0) or np.any(
        states["solver_iterations"] >= model.opt.iterations
    ):
        reject("solver_iteration_budget", True)
    if np.any(states["external_force_norm"] != 0):
        reject("external_applied_force", True)
    if np.any(states["actuator_force"] < model.actuator_forcerange[:, 0] - 1e-9) or np.any(
        states["actuator_force"] > model.actuator_forcerange[:, 1] + 1e-9
    ):
        reject("actuator_force_bound", True)
    need(
        np.allclose(states["qpos"][0, cq : cq + 7], model.qpos0[cq : cq + 7], rtol=0, atol=1e-12),
        "initial cap differs from compiled reset",
    )
    need(
        np.allclose(
            np.linalg.norm(states["qpos"][:, cq + 3 : cq + 7], axis=1), 1, rtol=0, atol=1e-7
        ),
        "invalid cap quaternion",
    )
    need(np.all(states["qvel"][0] == 0), "nonzero initial velocity")
    if expected_target is not None:
        need(
            np.allclose(states["qpos"][0, cq : cq + 3], expected_target, rtol=0, atol=1e-12),
            "initial cap differs from drawn target",
        )
    arm_qadr = [int(model.joint(f"cad_j{i}").qposadr[0]) for i in range(1, 5)]
    jaw_qa = int(model.joint("gripper_delta").qposadr[0])
    if expected_standby is not None:
        need(
            np.allclose(states["qpos"][0, arm_qadr], expected_standby, rtol=0, atol=1e-12),
            "initial robot differs from common standby",
        )
    need(
        abs(states["qpos"][0, jaw_qa] - math.radians(expected_jaw_degrees - 90)) < 1e-12,
        "initial jaw differs from common opening",
    )

    data = mujoco.MjData(model)
    sid = int(model.site("grip").id)
    grip = np.empty((n, 3))
    rotation = np.empty((n, 3, 3))
    axis = np.empty((n, 3))
    for i, q in enumerate(states["qpos"]):
        data.qpos[:] = q
        mujoco.mj_kinematics(model, data)
        grip[i] = data.site_xpos[sid]
        rotation[i] = data.site_xmat[sid].reshape(3, 3)
        axis[i] = data.xmat[cap].reshape(3, 3)[:, 2]
    cap_position = states["qpos"][:, cq : cq + 3]
    for derived, logged, name in (
        (grip, states["grip_position"], "grip_position"),
        (rotation, states["grip_rotation"], "grip_rotation"),
        (axis, states["cap_axis"], "cap_axis"),
        (cap_position, states["cap_position"], "cap_position"),
    ):
        need(np.allclose(derived, logged, rtol=0, atol=1e-9), "raw FK mismatch: " + name)
    capgeom = int(model.geom("cap_geom").id)
    box = int(model.geom("box").id)
    need(model.geom_type[capgeom] == mujoco.mjtGeom.mjGEOM_CYLINDER, "cap is not finite cylinder")
    need(
        model.geom_bodyid[box] == 0 and np.array_equal(model.geom_quat[box], [1, 0, 0, 0]),
        "support is not fixed horizontal box",
    )
    plane = float(model.geom_pos[box, 2] + model.geom_size[box, 2])
    need(abs(plane - meta["initial_support_plane_z_m"]) < 1e-12, "support plane mismatch")
    need(
        np.allclose(model.geom_size[box], [0.032, 0.032, 0.025], rtol=0, atol=1e-12),
        "fixed support box size changed",
    )
    need(abs(plane - 0.05) < 1e-12, "fixed support box height changed")
    if translated_box and expected_target is not None:
        need(
            np.allclose(model.geom_pos[box, :2], expected_target[:2], rtol=0, atol=1e-12),
            "support box not centered under drawn cap",
        )
    radius, halfheight = model.geom_size[capgeom, :2]
    az = np.clip(np.abs(axis[:, 2]), 0, 1)
    clearance = cap_position[:, 2] - halfheight * az - radius * np.sqrt(1 - az * az) - plane
    gmap = {g["name"]: g for g in policy["geoms"]}
    pmap = {tuple(sorted((p["group1"], p["group2"]))): p for p in policy["group_pairs"]}
    physical = {
        model.geom(i).name
        for i in range(model.ngeom)
        if model.geom_contype[i] or model.geom_conaffinity[i]
    }
    need(set(gmap) == physical, "incomplete physical collision policy")
    need(
        len(pmap) == len(policy["groups"]) * (len(policy["groups"]) - 1) // 2,
        "incomplete pair matrix",
    )
    left, right, support = np.zeros(n), np.zeros(n), np.zeros(n, dtype=bool)
    box_support = np.zeros(n, dtype=bool)
    box_force = np.zeros(n)
    forbidden = []
    phases = states["phase"]
    sample_ids = set()
    for phase in np.unique(phases):
        ids = np.flatnonzero(phases == phase)
        if len(ids):
            sample_ids.update(int(x) for x in np.linspace(ids[0], ids[-1], max(1, force_checks)))
    sample_rows = {}
    rows = 0
    contact_storage = {}
    for i, line in enumerate(iter_contact_lines(trial, contact_storage)):
        row = json.loads(line)
        rows += 1
        if i >= n:
            validation.append("excess contact rows")
            break
        need(
            row.get("i") == i
            and type(row.get("time")) in (int, float)
            and abs(row["time"] - t[i]) <= 1e-9,
            "contact index/time mismatch",
        )
        need(isinstance(row.get("contacts"), list), "missing contact list")
        if i in sample_ids:
            sample_rows[i] = row
        for contact in row["contacts"]:
            force = np.asarray(contact["force"])
            distance = contact["distance"]
            need(
                force.shape == (6,)
                and np.isfinite(force).all()
                and np.isfinite(distance)
                and force[0] >= -1e-12,
                "invalid contact force/distance",
            )
            a, b = gmap[contact["geom1"]], gmap[contact["geom2"]]
            rule = pmap[tuple(sorted((a["group_id"], b["group_id"])))]
            normal = float(force[0])
            if (
                rule["class"] == "forbidden"
                and (normal > 1e-5 or distance < -0.0001)
                and len(forbidden) < 20
            ):
                forbidden.append(
                    {
                        "sample": i,
                        "time": float(t[i]),
                        "geoms": [a["name"], b["name"]],
                        "normal_N": normal,
                        "distance_m": distance,
                    }
                )
            if "cap_geom" in (a["name"], b["name"]):
                other = b if a["name"] == "cap_geom" else a
                if other["name"] == "box":
                    box_force[i] += max(normal, 0)
                if other["category"] == "softtip":
                    if other["side"] == "L":
                        left[i] += max(normal, 0)
                    elif other["side"] == "R":
                        right[i] += max(normal, 0)
                    else:
                        validation.append("unrecognized finger side")
                elif normal > 1e-5:
                    support[i] = True
                    if other["name"] == "box":
                        box_support[i] = True
    need(rows == n, "missing contact rows")
    if forbidden:
        reject("forbidden_collision", True)
    for j in range(model.njnt):
        if not model.jnt_limited[j]:
            continue
        tol = 1e-5 if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_SLIDE else 1e-4
        q = states["qpos"][:, model.jnt_qposadr[j]]
        if np.any(q < model.jnt_range[j, 0] - tol) or np.any(q > model.jnt_range[j, 1] + tol):
            reject("joint_limit:" + model.joint(j).name, True)
    settled = np.flatnonzero(phases == "settle")
    if not len(settled) or not support[settled[-1]] or abs(clearance[settled[-1]]) > 0.0005:
        reject("initial_support_missing")
    approach = np.flatnonzero(phases == "approach")
    metrics = {
        "samples": n,
        "maximum_bottom_clearance_m": float(clearance.max()),
        "initial_arm_q_rad": states["qpos"][0, arm_qadr].tolist(),
        "initial_cap_m": cap_position[0].tolist(),
        "final_arm_q_rad": states["qpos"][-1, arm_qadr].tolist(),
    }
    if len(approach):
        i = int(approach[-1])
        target = np.asarray(meta["approach_target_position_m"])
        if expected_target is not None:
            need(
                np.allclose(
                    target,
                    np.asarray(expected_target) + [0, 0, approach_offset_m],
                    rtol=0,
                    atol=1e-12,
                ),
                "nominal approach target differs from drawn target and fixed offset",
            )
        # The last sampled approach command is legitimately just before the
        # phase endpoint. Evaluate against the fixed endpoint itself; equality
        # to that pre-end command is not an inherited acceptance requirement.
        command_gap = float(np.linalg.norm(target - states["target_position"][i]))
        err = float(np.linalg.norm(grip[i] - target))
        q = states["qpos"][i, arm_qadr]
        pitch = -q[1] + q[2] + q[3]
        pe = abs(
            math.atan2(
                math.sin(pitch - contract["pitch_target_rad"]),
                math.cos(pitch - contract["pitch_target_rad"]),
            )
        )
        metrics.update(
            approach_position_error_m=err,
            approach_pitch_error_rad=pe,
            last_approach_command_to_nominal_endpoint_m=command_gap,
        )
        if err > 0.002 or pe > math.radians(2):
            reject("approach_error")
    else:
        reject("approach_missing")
    start = None
    interval = None
    good = (phases == "hold") & (clearance >= 0.020) & ~support
    for i, valid in enumerate(good):
        if not valid:
            start = None
        elif start is None:
            start = i
        if start is not None and t[i] - t[start] >= 2 - 1e-9:
            interval = (start, i)
            break
    if interval:
        a, b = interval
        relative = np.einsum(
            "nji,nj->ni", rotation[a : b + 1], cap_position[a : b + 1] - grip[a : b + 1]
        )
        drift = float(np.linalg.norm(relative - relative[0], axis=1).max())
        both = (left[a:b] > 1e-5) & (right[a:b] > 1e-5)
        duty = float(np.sum(np.diff(t)[a:b] * both) / (t[b] - t[a]))
        metrics.update(
            hold_start_s=float(t[a]),
            hold_end_s=float(t[b]),
            hold_duration_s=float(t[b] - t[a]),
            hold_bottom_clearance_min_m=float(clearance[a : b + 1].min()),
            hold_bilateral_fraction=duty,
            hold_grip_frame_drift_max_m=drift,
            hold_support_contact_count=int(support[a : b + 1].sum()),
        )
        if duty < 0.8:
            reject("insufficient_bilateral_contact")
        if drift > 0.005:
            reject("hold_drift")
    else:
        reject("no_20mm_2s_unsupported_hold")

    # Descriptive diagnostics only. They do not add or relax acceptance gates.
    transfer = {}
    hold_all = np.flatnonzero(phases == "hold")
    if len(hold_all) > 1:
        a, b = int(hold_all[0]), int(hold_all[-1])
        relative = np.einsum(
            "nji,nj->ni", rotation[a : b + 1], cap_position[a : b + 1] - grip[a : b + 1]
        )
        both = (left[a:b] > 1e-5) & (right[a:b] > 1e-5)
        transfer.update(
            full_hold_observed_duration_s=float(t[b] - t[a]),
            full_hold_bilateral_fraction=float(np.sum(np.diff(t)[a:b] * both) / (t[b] - t[a])),
            full_hold_grip_drift_max_m=float(np.linalg.norm(relative - relative[0], axis=1).max()),
        )
    lower_all = np.flatnonzero(phases == "lower")
    if len(lower_all):
        a, b = int(lower_all[0]), int(lower_all[-1])
        relative = np.einsum(
            "nji,nj->ni", rotation[a : b + 1], cap_position[a : b + 1] - grip[a : b + 1]
        )
        absent = (left[lower_all] <= 1e-5) & (right[lower_all] <= 1e-5)
        first = lower_all[np.flatnonzero(absent)[0]] if absent.any() else None
        longest, current = 0.0, 0.0
        for j, lost in enumerate(absent[:-1]):
            current = current + float(t[lower_all[j + 1]] - t[lower_all[j]]) if lost else 0.0
            longest = max(longest, current)
        contacts = np.flatnonzero(
            (np.arange(n) >= a) & np.isin(phases, ["lower", "release"]) & box_support
        )
        contact_i = int(contacts[0]) if len(contacts) else None
        transfer.update(
            lower_first_both_finger_contacts_absent_s=float(t[first])
            if first is not None
            else None,
            lower_max_both_finger_contact_absence_s=longest,
            lower_grip_relative_displacement_max_m=float(
                np.linalg.norm(relative - relative[0], axis=1).max()
            ),
            first_lower_release_box_contact_s=float(t[contact_i])
            if contact_i is not None
            else None,
            cap_center_speed_before_box_contact_m_s=float(
                np.linalg.norm(states["qvel"][max(0, contact_i - 1), cv : cv + 3])
            )
            if contact_i is not None
            else None,
            lower_release_box_force_max_N=float(
                box_force[np.isin(phases, ["lower", "release"])].max()
            ),
        )

    latch_metrics = {}
    setdown = saved_protocol.get("controller_setdown")
    if setdown:
        latch = meta.get("placement_latch")
        eligible = np.flatnonzero(
            (phases == "lower")
            & (
                (clearance <= setdown["bottom_clearance_stop_m"])
                | (box_force > setdown["support_force_backstop_N"])
            )
        )
        if meta.get("no_close"):
            need(latch is None, "no-close control unexpectedly used setdown latch")
        elif latch is not None:
            i = latch["sample"]
            need(
                len(eligible) > 0 and i == int(eligible[0]),
                "latch is not the first threshold crossing",
            )
            need(0 <= i < n and phases[i] == "lower", "latch sample outside lowering phase")
            need(abs(latch["time_s"] - t[i]) <= 1e-9, "latch timestamp mismatch")
            need(
                abs(latch["actual_clearance_m"] - clearance[i]) <= 1e-9,
                "latch cylinder-bottom mismatch",
            )
            need(
                np.allclose(latch["actual_axis"], axis[i], rtol=0, atol=1e-9),
                "latch cap-axis mismatch",
            )
            need(
                np.allclose(latch["actual_arm_q"], states["qpos"][i, arm_qadr], rtol=0, atol=1e-12),
                "latch actual arm pose mismatch",
            )
            need(
                np.allclose(latch["command_q"], states["target_q"][i], rtol=0, atol=1e-12),
                "latch command mismatch",
            )
            need(
                np.allclose(
                    latch["command_target_m"], states["target_position"][i], rtol=0, atol=1e-12
                ),
                "latch Cartesian command mismatch",
            )
            need(
                abs(latch["support_force_N"] - box_force[i]) <= 1e-5,
                "latch box-support force mismatch",
            )
            held = np.flatnonzero((np.arange(n) > i) & np.isin(phases, ["lower", "release"]))
            need(
                np.allclose(states["target_q"][held], latch["command_q"], rtol=0, atol=1e-12),
                "arm continued descending after setdown latch",
            )
            need(
                np.allclose(
                    states["target_position"][held], latch["command_target_m"], rtol=0, atol=1e-12
                ),
                "Cartesian command changed after setdown latch",
            )
            plan = load(trial / "plan.json")
            waypoint = [row for row in plan["waypoints"] if row["segment"] == "lift"]
            fs = [row["fraction"] for row in waypoint]
            qs = np.asarray([row["q"] for row in waypoint])
            retract = np.flatnonzero(phases == "retract")
            times = saved_protocol["timing_s"]
            ratio = np.clip(
                (t[retract] - times["release_end"]) / (times["retract_end"] - times["release_end"]),
                0,
                1,
            )
            smooth = ratio * ratio * (3 - 2 * ratio)
            end = (
                saved_protocol["planner"]["pregrasp_raise_m"]
                / saved_protocol["planner"]["lift_raise_m"]
            )
            fractions = latch["lift_fraction"] + smooth * (end - latch["lift_fraction"])
            expected_q = np.array([np.interp(fractions, fs, qs[:, joint]) for joint in range(4)]).T
            need(
                np.allclose(states["target_q"][retract], expected_q, rtol=0, atol=1e-10),
                "retract left the declared screened vertical command path",
            )
            latch_metrics = {
                "sample": int(i),
                "time_s": float(t[i]),
                "actual_bottom_clearance_m": float(clearance[i]),
                "box_force_at_latch_N": float(box_force[i]),
                "box_force_lower_release_max_N": float(
                    box_force[np.isin(phases, ["lower", "release"])].max()
                ),
                "hold_then_release_command_samples": len(held),
                "retract_command_samples": len(retract),
            }
        elif meta.get("normal_completion"):
            need(False, "completed close-enabled cycle has no setdown latch")

    cycle_metrics = {}
    if return_criteria is not None:
        duration = float(return_criteria["settling_interval_s"])
        final = np.flatnonzero(t >= t[-1] - duration - 1e-9)
        joint_q = arm_qadr + [jaw_qa]
        joint_v = [int(model.joint(f"cad_j{i}").dofadr[0]) for i in range(1, 5)]
        joint_v.append(int(model.joint("gripper_delta").dofadr[0]))
        target_q = np.r_[expected_standby, math.radians(expected_jaw_degrees - 90)]
        qerr = float(np.abs(states["qpos"][final][:, joint_q] - target_q).max())
        vmax = float(np.abs(states["qvel"][final][:, joint_v]).max())
        extent_xy = halfheight * np.abs(axis[final, :2]) + radius * np.sqrt(
            np.maximum(0, 1 - axis[final, :2] ** 2)
        )
        edge_margin = model.geom_size[box, :2] - (
            np.abs(cap_position[final, :2] - model.geom_pos[box, :2]) + extent_xy
        )
        height_error = float(np.abs(clearance[final]).max())
        detached = bool(np.all(left[final] <= 1e-5) and np.all(right[final] <= 1e-5))
        supported = bool(np.all(box_support[final]))
        cycle_metrics = {
            "final_interval_start_s": float(t[final[0]]),
            "final_interval_end_s": float(t[final[-1]]),
            "joint_position_error_max_rad": qerr,
            "joint_velocity_max_rad_s": vmax,
            "box_support_all_steps": supported,
            "fingers_detached_all_steps": detached,
            "footprint_min_box_edge_margin_m": float(edge_margin.min()),
            "support_height_error_max_m": height_error,
        }
        if t[final[-1]] - t[final[0]] < duration - 1e-9:
            reject("final_settling_interval_missing")
        if qerr > return_criteria["joint_position_error_rad"]:
            reject("return_position_error")
        if vmax > return_criteria["joint_velocity_max_rad_s"]:
            reject("return_velocity_error")
        if not supported or not detached or np.any(edge_margin < -1e-12):
            reject("place_release_not_established")
        if height_error > return_criteria["support_height_error_max_m"]:
            reject("final_cap_support_height")

    checks = []
    for i in sorted(sample_rows):
        data = mujoco.MjData(model)
        data.qpos[:] = states["qpos"][i]
        data.qvel[:] = states["qvel"][i]
        data.ctrl[:] = states["ctrl"][i]
        mujoco.mj_forward(model, data)
        actual, logged = {}, {}
        for j, contact in enumerate(data.contact):
            a, b = model.geom(contact.geom1).name, model.geom(contact.geom2).name
            if "cap_geom" in (a, b):
                force = np.zeros(6)
                mujoco.mj_contactForce(model, data, j, force)
                key = "|".join(sorted((a, b)))
                actual[key] = actual.get(key, 0.0) + float(force[0])
        for contact in sample_rows[i]["contacts"]:
            a, b = contact["geom1"], contact["geom2"]
            if "cap_geom" in (a, b):
                key = "|".join(sorted((a, b)))
                logged[key] = logged.get(key, 0.0) + float(contact["force"][0])
        difference = max(
            (abs(actual.get(k, 0) - logged.get(k, 0)) for k in actual.keys() | logged.keys()),
            default=0.0,
        )
        checks.append(
            {
                "sample": i,
                "time": float(t[i]),
                "phase": str(phases[i]),
                "max_cap_pair_normal_difference_N": difference,
            }
        )
        need(difference <= 1e-4, "sparse force reconstruction mismatch")
    status = "FAILURE" if reasons or validation else "SUCCESS"
    relative_trial = (
        Path(*trial.parts[trial.parts.index("results") :])
        if "results" in trial.parts
        else Path(trial.name)
    )
    return {
        "trial": str(relative_trial),
        "scene_sha256": sha(trial / "scene.xml"),
        "scene_invariants_sha256": scene_signature(trial / "scene.xml"),
        "states_sha256": sha(trial / "states.npz"),
        "contacts_sha256": contact_storage.get("plain_sha256"),
        "contact_storage": contact_storage,
        "validation_errors": list(dict.fromkeys(validation)),
        "acceptance_failures": list(dict.fromkeys(reasons)),
        "unsafe_failures": list(dict.fromkeys(safety)),
        "raw_core_status": status,
        "saved_status": saved["status"],
        "core_status_agrees": status == saved["status"],
        "audit_pass": not validation and not (saved["status"] == "SUCCESS" and status != "SUCCESS"),
        "metrics": metrics,
        "cycle_metrics": cycle_metrics,
        "setdown_latch_metrics": latch_metrics,
        "transfer_diagnostics_non_gating": transfer,
        "forbidden_examples": forbidden,
        "force_checks": checks,
        "scope": "Independent raw core-criteria audit; cycle return criteria separately checked; not dynamics replay",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trial", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target", nargs=3, type=float)
    parser.add_argument("--standby", nargs=4, type=float)
    parser.add_argument("--jaw-degrees", type=float, default=50)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--fixed-box", action="store_true")
    args = parser.parse_args()
    protocol = load(args.protocol) if args.protocol else None
    if protocol:
        args.standby = protocol["standby"]["arm_q_rad"]
        args.jaw_degrees = protocol["standby"]["jaw_theta_deg"]
    result = audit_trial(
        args.trial,
        args.target,
        args.standby,
        args.jaw_degrees,
        return_criteria=protocol["return_criteria"] if protocol else None,
        translated_box=not args.fixed_box,
        timing=protocol["timing_s"] if protocol else None,
        approach_offset_m=protocol["planner"]["grip_z_offset_m"] if protocol else 0.006,
    )
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2, allow_nan=False), flush=True)
    raise SystemExit(0 if result["audit_pass"] else 1)


if __name__ == "__main__":
    main()
