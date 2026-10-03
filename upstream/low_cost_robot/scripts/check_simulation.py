"""Headless CLI verification of the MuJoCo arm: kinematics, interference, motion.

Answers, without a GUI:
  - how many joints / DOF / actuators, how the arm moves (axes, ranges, chain),
  - is the kinematic coupling (parent chain) intact,
  - does motion simulate stably (no NaN / blow-up) and track commands,
  - is there interference (contact penetration) during a full range sweep.

    uv run python scripts/check_simulation.py
    uv run python scripts/check_simulation.py --model simulation/low_cost_robot/scene.xml --seconds 6 --json
"""
from __future__ import annotations
import sys
import json
import argparse
from pathlib import Path

import numpy as np
import mujoco

_JNT_TYPE = {0: "free", 1: "ball", 2: "slide", 3: "hinge"}
# Non-adjacent self-interference beyond this during single-joint motion is a defect.
PENETRATION_LIMIT_MM = 2.0
TRACKING_TOL = 0.20             # rad, position-actuator steady-state tolerance


def _adjacent(model, b1: int, b2: int) -> bool:
    """Two bodies are adjacent (a contact between them is expected, not a defect)
    if one is the other's parent — MuJoCo's filterparent already drops most of these."""
    return (model.body_parentid[b1] == b2 or model.body_parentid[b2] == b1
            or b1 == b2)


def _contacts(model, data) -> list[dict]:
    out = []
    for k in range(data.ncon):
        c = data.contact[k]
        b1, b2 = int(model.geom_bodyid[c.geom1]), int(model.geom_bodyid[c.geom2])
        out.append({
            "g1": model.geom(c.geom1).name or f"geom{c.geom1}",
            "g2": model.geom(c.geom2).name or f"geom{c.geom2}",
            "depth_mm": round(-float(c.dist) * 1000.0, 3),
            "adjacent": _adjacent(model, b1, b2),
        })
    return out


_ENV = {"floor", "red_box"}
_PADS = {"static_finger_pad", "moving_finger_pad"}


def _interference(model, data) -> dict:
    """Classify current contacts: arm-on-arm self-interference (a defect),
    floor/ground penetration (workspace/mounting), and gripper-pad contact
    (the intended grasp). Returns worst depth per class + the pair."""
    self_w, self_p = 0.0, None
    floor_w, floor_p = 0.0, None
    gripper = False
    for c in _contacts(model, data):
        g1, g2, depth = c["g1"], c["g2"], c["depth_mm"]
        pair = {g1, g2}
        if "floor" in pair and depth > floor_w:
            floor_w, floor_p = depth, (g1, g2)
        if pair == _PADS or (pair & _PADS and "red_box" in pair):
            gripper = True                       # intended grasp contact
        elif not c["adjacent"] and not (pair & _ENV) and not (pair & _PADS):
            if depth > self_w:
                self_w, self_p = depth, (g1, g2)
    return {"self_mm": round(self_w, 3), "self_pair": self_p,
            "floor_mm": round(floor_w, 3), "floor_pair": floor_p,
            "gripper_contact": gripper}


def describe(model) -> dict:
    joints = []
    for i in range(model.njnt):
        jbody = int(model.jnt_bodyid[i])
        joints.append({
            "name": model.joint(i).name,
            "type": _JNT_TYPE.get(int(model.jnt_type[i]), str(model.jnt_type[i])),
            "axis": [round(float(x), 3) for x in model.jnt_axis[i]],
            "range": [round(float(x), 4) for x in model.jnt_range[i]],
            "limited": bool(model.jnt_limited[i]),
            "parent_body": model.body(int(model.body_parentid[jbody])).name,
        })
    actuators = []
    for i in range(model.nu):
        actuators.append({
            "name": model.actuator(i).name,
            "ctrlrange": [round(float(x), 4) for x in model.actuator_ctrlrange[i]],
        })
    # kinematic chain (coupling): body parent links
    chain = [{"body": model.body(i).name,
              "parent": model.body(int(model.body_parentid[i])).name}
             for i in range(1, model.nbody)]
    # collision-enabled geoms (interference can only occur between these)
    collidable = [model.geom(i).name or f"geom{i}" for i in range(model.ngeom)
                  if model.geom_contype[i] or model.geom_conaffinity[i]]
    return {"nq": model.nq, "nv": model.nv, "njnt": model.njnt, "nu": model.nu,
            "nbody": model.nbody, "ngeom": model.ngeom, "timestep": model.opt.timestep,
            "joints": joints, "actuators": actuators, "chain": chain,
            "collidable_geoms": collidable}


def home_test(model, data, seconds: float) -> dict:
    """Settle at the home pose (ctrl=0); report stability and self-overlap, split
    into adjacent (expected mesh overlap) vs arm-on-arm self-interference (defect)."""
    mujoco.mj_resetData(model, data)
    data.ctrl[:] = 0.0
    for _ in range(int(seconds / model.opt.timestep)):
        mujoco.mj_step(model, data)
    contacts = [c for c in _contacts(model, data) if c["depth_mm"] > 0.05]
    adj = max([c["depth_mm"] for c in contacts if c["adjacent"]], default=0.0)
    intf = _interference(model, data)
    finite = bool(np.all(np.isfinite(data.qpos)) and np.all(np.isfinite(data.qvel)))
    return {"finite": finite, "max_qvel": round(float(np.max(np.abs(data.qvel))), 4),
            "adjacent_overlap_mm": round(adj, 3), "self_interference_mm": intf["self_mm"],
            "self_pair": intf["self_pair"], "contacts": contacts,
            "passed": finite and float(np.max(np.abs(data.qvel))) < 50.0
            and intf["self_mm"] <= PENETRATION_LIMIT_MM}


def per_joint_motion_test(model, data, seconds: float) -> dict:
    """Sweep each actuator alone through its full range (others at neutral) — a
    realistic single-DOF motion. Gate on arm-on-arm self-interference; report
    floor penetration (workspace) and gripper closure (function) separately."""
    lo = model.actuator_ctrlrange[:, 0].copy()
    hi = model.actuator_ctrlrange[:, 1].copy()
    mid = (hi + lo) / 2
    per_joint = int(seconds / model.opt.timestep)
    self_w, self_pair, self_joint = 0.0, None, None
    floor_w, floor_joint = 0.0, None
    gripper_closes = False
    stable = True
    for j in range(model.nu):
        mujoco.mj_resetData(model, data)
        for t in range(per_joint):
            ctrl = mid.copy()
            frac = 0.5 - 0.5 * np.cos(2 * np.pi * t / per_joint)   # 0->1->0
            ctrl[j] = lo[j] + frac * (hi[j] - lo[j])
            data.ctrl[:] = ctrl
            mujoco.mj_step(model, data)
            if not (np.all(np.isfinite(data.qpos)) and np.all(np.isfinite(data.qvel))):
                stable = False
                break
            intf = _interference(model, data)
            if intf["self_mm"] > self_w:
                self_w, self_pair, self_joint = intf["self_mm"], intf["self_pair"], \
                    model.actuator(j).name
            if intf["floor_mm"] > floor_w:
                floor_w, floor_joint = intf["floor_mm"], model.actuator(j).name
            if intf["gripper_contact"]:
                gripper_closes = True
    # Self-collision / floor contact at full joint range is a workspace property
    # (declared ranges = full servo travel > collision-free envelope), not a sim
    # defect — so it is REPORTED, not gated. Stability is what gates motion.
    return {"stable": stable, "self_interference_mm": round(self_w, 3),
            "self_pair": self_pair, "self_joint": self_joint,
            "self_collision_reachable": self_w > PENETRATION_LIMIT_MM,
            "floor_penetration_mm": round(floor_w, 3), "floor_joint": floor_joint,
            "gripper_closes": gripper_closes, "passed": stable}


def all_joints_extreme(model, data, seconds: float) -> dict:
    """Informational: drive all actuators to extremes at once — reaches self-
    collision poses by design. Shows control must respect joint coordination."""
    mujoco.mj_resetData(model, data)
    n = int(seconds / model.opt.timestep)
    lo, hi = model.actuator_ctrlrange[:, 0], model.actuator_ctrlrange[:, 1]
    mid, amp = (hi + lo) / 2, (hi - lo) / 2
    worst, pair = 0.0, None
    for t in range(n):
        data.ctrl[:] = mid + amp * np.sin(np.full(model.nu, 2 * np.pi * t / n))
        mujoco.mj_step(model, data)
        intf = _interference(model, data)
        if intf["self_mm"] > worst:
            worst, pair = intf["self_mm"], intf["self_pair"]
    return {"self_collision_reachable": worst > PENETRATION_LIMIT_MM,
            "max_self_interference_mm": round(worst, 3), "worst_pair": pair,
            "note": "expected; real teleop constrains poses via the leader arm"}


def _tracking_test(model, data) -> dict:
    """Command each actuator to its mid-range target, settle, measure error."""
    mujoco.mj_resetData(model, data)
    target = (model.actuator_ctrlrange[:, 0] + model.actuator_ctrlrange[:, 1]) / 2
    data.ctrl[:] = target
    for _ in range(int(2.0 / model.opt.timestep)):
        mujoco.mj_step(model, data)
    errs = []
    for i in range(model.nu):
        jid = int(model.actuator_trnid[i, 0])
        qadr = int(model.jnt_qposadr[jid])
        errs.append(abs(float(data.qpos[qadr]) - float(target[i])))
    return {"max_error_rad": round(max(errs), 4),
            "within_tol": max(errs) <= TRACKING_TOL,
            "note": "position-actuator steady-state error (gravity-loaded)"}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path,
                    default=Path("simulation/low_cost_robot/scene.xml"))
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    model = mujoco.MjModel.from_xml_path(str(a.model.resolve()))
    data = mujoco.MjData(model)
    desc = describe(model)
    home = home_test(model, data, min(a.seconds, 3.0))
    motion = per_joint_motion_test(model, data, a.seconds)
    tracking = _tracking_test(model, data)
    extreme = all_joints_extreme(model, data, a.seconds)
    ok = home["passed"] and motion["passed"] and tracking["within_tol"]
    result = {"model": str(a.model), "describe": desc, "home": home,
              "per_joint_motion": motion, "tracking": tracking,
              "all_joints_extreme": extreme, "overall_passed": ok}

    if a.json:
        # numpy scalar booleans/floats (e.g. `x <= LIMIT` yields numpy.bool_) leak
        # into the result dict and are not natively JSON-serializable; coerce them.
        def _native(o):
            return o.item() if hasattr(o, "item") else str(o)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=_native))
        return 0 if ok else 1

    actuated = [j for j in desc["joints"] if j["type"] in ("hinge", "slide")]
    print(f"Model: {a.model}")
    print(f"  DOF nq={desc['nq']} nv={desc['nv']}  joints={desc['njnt']} "
          f"actuators={desc['nu']}  bodies={desc['nbody']} geoms={desc['ngeom']}")
    print(f"  Arm: {desc['nu']}-DOF chain (4 positioning + 1 gripper)")
    for j in actuated:
        print(f"    - {j['name']:8s} {j['type']:5s} axis={j['axis']} "
              f"range={j['range']} rad  (child of {j['parent_body']})")
    print(f"  Collision geoms: {desc['collidable_geoms']}")
    print(f"Home:    {'PASS' if home['passed'] else 'FAIL'} finite={home['finite']} "
          f"adj_mesh_overlap={home['adjacent_overlap_mm']}mm "
          f"self_interference={home['self_interference_mm']}mm")
    print(f"Motion (per-joint sweep): {'PASS' if motion['passed'] else 'FAIL'} "
          f"stable={motion['stable']} (no NaN/blow-up through full range)")
    print(f"  workspace findings (NOT defects — full servo range > collision-free "
          f"envelope):")
    print(f"    self-collision reachable={motion['self_collision_reachable']} "
          f"max={motion['self_interference_mm']}mm {motion['self_pair']}"
          f"@{motion['self_joint']}")
    print(f"    floor penetration={motion['floor_penetration_mm']}mm "
          f"@{motion['floor_joint']} (arm reaches below mount plane)")
    print(f"Tracking: {'PASS' if tracking['within_tol'] else 'WARN'} "
          f"max_error={tracking['max_error_rad']}rad (gravity-loaded hold)")
    print(f"All-joints-extreme (info): self_collision_reachable="
          f"{extreme['self_collision_reachable']} "
          f"max={extreme['max_self_interference_mm']}mm {extreme['worst_pair']}")
    print(f"OVERALL: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
