"""Continuous actuator references and additional standby/return evaluation."""

import json
import math
from pathlib import Path

import mujoco
import numpy as np

from trace_io import contact_rows


def smooth(x):
    x = float(np.clip(x, 0, 1))
    return x * x * (3 - 2 * x)


def interpolate(plan, segment, fraction):
    prepared = plan.get("_interpolators")
    if prepared is not None:
        fractions, qs, targets = prepared[segment]
        return (
            np.array([np.interp(fraction, fractions, column) for column in qs]),
            np.array([np.interp(fraction, fractions, column) for column in targets]),
        )
    points = [x for x in plan["waypoints"] if x["segment"] == segment]
    fractions = [x["fraction"] for x in points]
    q = np.array([np.interp(fraction, fractions, [x["q"][i] for x in points]) for i in range(4)])
    target = np.array(
        [np.interp(fraction, fractions, [x["target_m"][i] for x in points]) for i in range(3)]
    )
    return q, target


def prepare_reference(plan):
    """Cache immutable waypoint arrays once; never change physics or interpolation."""
    prepared = {}
    for segment in ("transit", "approach", "lift"):
        points = [p for p in plan["waypoints"] if p["segment"] == segment]
        prepared[segment] = (
            np.array([p["fraction"] for p in points]),
            np.array([p["q"] for p in points]).T,
            np.array([p["target_m"] for p in points]).T,
        )
    plan["_interpolators"] = prepared


def reference(plan, t, no_close=False):
    timing = plan["timing_s"]
    open_q = math.radians(plan["jaw_open_theta_deg"] - 90)
    closed_q = math.radians(plan["jaw_close_theta_deg"] - 90)
    if t < timing["settle_end"]:
        phase = "settle"
        q, target = interpolate(plan, "transit", 0)
        jaw = open_q
    elif t < timing["transit_end"]:
        phase = "transit"
        q, target = interpolate(
            plan,
            "transit",
            smooth((t - timing["settle_end"]) / (timing["transit_end"] - timing["settle_end"])),
        )
        jaw = open_q
    elif t < timing["approach_end"]:
        phase = "approach"
        q, target = interpolate(
            plan,
            "approach",
            smooth((t - timing["transit_end"]) / (timing["approach_end"] - timing["transit_end"])),
        )
        jaw = open_q
    elif t < timing["alignment_end"]:
        phase = "alignment"
        q, target = np.array(plan["alignment_q"]), np.array(plan["closing_target_m"])
        jaw = open_q
    elif t < timing["close_end"]:
        phase = "close"
        q, target = np.array(plan["alignment_q"]), np.array(plan["closing_target_m"])
        f = smooth(
            (t - timing["alignment_end"]) / (timing["close_end"] - timing["alignment_end"] - 0.5)
        )
        jaw = open_q + f * (closed_q - open_q)
    elif t < timing["lift_end"]:
        phase = "lift"
        q, target = interpolate(
            plan,
            "lift",
            smooth((t - timing["close_end"]) / (timing["lift_end"] - timing["close_end"])),
        )
        jaw = closed_q
    elif t < timing["hold_end"]:
        phase = "hold"
        q, target = np.array(plan["lift_q"]), np.array(plan["lift_target_m"])
        jaw = closed_q
    elif t < timing["lower_end"]:
        phase = "lower"
        q, target = interpolate(
            plan,
            "lift",
            1 - smooth((t - timing["hold_end"]) / (timing["lower_end"] - timing["hold_end"])),
        )
        jaw = closed_q
    elif t < timing["release_end"]:
        phase = "release"
        q, target = np.array(plan["alignment_q"]), np.array(plan["closing_target_m"])
        f = smooth((t - timing["lower_end"]) / (timing["release_end"] - timing["lower_end"]))
        jaw = closed_q + f * (open_q - closed_q)
    elif t < timing["retract_end"]:
        phase = "retract"
        q, target = interpolate(
            plan,
            "approach",
            1
            - smooth((t - timing["release_end"]) / (timing["retract_end"] - timing["release_end"])),
        )
        jaw = open_q
    elif t < timing["return_end"]:
        phase = "return"
        q, target = interpolate(
            plan,
            "transit",
            1
            - smooth((t - timing["retract_end"]) / (timing["return_end"] - timing["retract_end"])),
        )
        jaw = open_q
    else:
        phase = "standby_final"
        q, target = interpolate(plan, "transit", 0)
        jaw = open_q
    return phase, q, target, open_q if no_close else jaw


def reference_with_setdown(plan, t, no_close=False, latch=None):
    phase, q, target, jaw = reference(plan, t, no_close)
    if latch is not None and not no_close:
        if phase in ("lower", "release"):
            q, target = np.array(latch["command_q"]), np.array(latch["command_target_m"])
        elif phase == "retract":
            timing = plan["timing_s"]
            f = smooth(
                (t - timing["release_end"]) / (timing["retract_end"] - timing["release_end"])
            )
            end = plan["pregrasp_fraction_on_lift"]
            fraction = latch["lift_fraction"] + f * (end - latch["lift_fraction"])
            q, target = interpolate(plan, "lift", fraction)
    return phase, q, target, jaw


def evaluate_cycle(directory, result):
    directory = Path(directory)
    protocol = json.loads((directory / "protocol.json").read_text())
    metadata = json.loads((directory / "metadata.json").read_text())
    plan = json.loads((directory / "plan.json").read_text())
    model = mujoco.MjModel.from_xml_path(str(directory / "scene.xml"))
    with np.load(directory / "states.npz", allow_pickle=False) as archive:
        states = {k: archive[k] for k in archive.files}
    if not len(states.get("time", [])):
        result["status"] = "FAILURE"
        result["reason_codes"] = list(dict.fromkeys(result["reason_codes"] + ["CYCLE_INCOMPLETE"]))
        return result
    reasons = []
    cfg = protocol["return_criteria"]
    standby = np.r_[
        protocol["standby"]["arm_q_rad"], math.radians(protocol["standby"]["jaw_theta_deg"] - 90)
    ]
    joint_ids = [model.joint(f"cad_j{i}").id for i in range(1, 5)] + [
        model.joint("gripper_delta").id
    ]
    qadr = model.jnt_qposadr[joint_ids]
    vadr = model.jnt_dofadr[joint_ids]
    initial_error = float(np.max(np.abs(states["qpos"][0, qadr] - standby)))
    initial_v = float(np.max(np.abs(states["qvel"][0])))
    if initial_error > 1e-12 or initial_v > 1e-12:
        reasons.append("STANDBY_RESET_INVALID")
    final = np.where(
        states["time"] >= protocol["timing_s"]["final_end"] - cfg["settling_interval_s"] - 1e-9
    )[0]
    metrics = {"initial_standby_error_rad": initial_error, "initial_velocity_max": initial_v}
    if not len(final) or states["time"][-1] < protocol["timing_s"]["final_end"] - 1e-9:
        reasons.append("CYCLE_INCOMPLETE")
    else:
        qerror = float(np.max(np.abs(states["qpos"][final][:, qadr] - standby)))
        velocity = float(np.max(np.abs(states["qvel"][final][:, vadr])))
        radius = model.geom_size[model.geom("cap_geom").id, 0]
        halfheight = model.geom_size[model.geom("cap_geom").id, 1]
        axis = states["cap_axis"][final]
        center = states["cap_position"][final]
        extent = halfheight * np.abs(axis) + radius * np.sqrt(np.maximum(0, 1 - axis * axis))
        box = np.array(plan["support_center_m"])
        halfsize = model.geom("box").size
        margin = float(np.min(halfsize[:2] - np.abs(center[:, :2] - box[:2]) - extent[:, :2]))
        bottom_error = float(np.max(np.abs(center[:, 2] - extent[:, 2] - (box[2] + halfsize[2]))))
        support_ok, finger_free = True, True
        first = int(final[0])
        for i, row in enumerate(contact_rows(directory)):
            if i < first:
                continue
            contacts = row["contacts"]
            supported = False
            for c in contacts:
                pair = {c["geom1"], c["geom2"]}
                if "cap_geom" not in pair or c["force"][0] <= 1e-5:
                    continue
                other = c["geom2"] if c["geom1"] == "cap_geom" else c["geom1"]
                if other == "box":
                    supported = True
                if any(part in other for part in ("cot_", "foam_", "band_")):
                    finger_free = False
            support_ok &= supported
        if qerror > cfg["joint_position_error_rad"] or velocity > cfg["joint_velocity_max_rad_s"]:
            reasons.append("STANDBY_RETURN_FAILED")
        if (
            margin < cfg["footprint_margin_min_m"]
            or bottom_error > cfg["support_height_error_max_m"]
            or not support_ok
            or not finger_free
        ):
            reasons.append("RELEASE_PLACEMENT_FAILED")
        metrics.update(
            final_interval_s=cfg["settling_interval_s"],
            return_position_error_rad=qerror,
            return_velocity_max_rad_s=velocity,
            released_footprint_margin_min_m=margin,
            released_bottom_error_max_m=bottom_error,
            final_box_support_all=support_ok,
            final_finger_contact_absent=finger_free,
        )
    # Compare sampled target and physically reset object, not merely metadata.
    capadr = int(model.jnt_qposadr[model.body_jntadr[model.body("cap").id]])
    if not np.allclose(
        states["qpos"][0, capadr : capadr + 3], plan["target_m"], atol=1e-12, rtol=0
    ):
        reasons.append("TARGET_RESET_INVALID")
    if metadata["runtime_pose_writes"] or metadata["external_forces_applied"]:
        reasons.append("MODEL_INVALID")
    result["cycle_metrics"] = metrics
    result["reason_codes"] = list(dict.fromkeys(result["reason_codes"] + reasons))
    if reasons:
        result["status"] = "FAILURE"
    return result
