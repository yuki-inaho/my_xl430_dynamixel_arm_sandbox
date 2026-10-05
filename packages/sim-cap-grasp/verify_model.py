"""Offline source-FK, closed-loop rank, and nominal dynamics-model checks."""

import json
import math

import mujoco
import numpy as np

from build_scene import INPUT, MODEL, ROOT, X90, closure, place_reset, save_json, sha


def main():
    audit = json.loads((MODEL / "audit.json").read_text())
    if audit.get("builder_sha256") != sha(ROOT / "build_scene.py"):
        raise SystemExit("Model is stale relative to builder: build must succeed first.")
    model = mujoco.MjModel.from_xml_path(str(MODEL / "scene.xml"))
    reference = mujoco.MjModel.from_xml_path(str(INPUT / "viewer/scene.xml"))
    tests = []
    for arm_deg, theta_deg in [
        ([0, 0, 0, 0], 90),
        ([15, 20, -30, 40], 25),
        ([-20, -20, 60, -70], 135),
        ([0, 10, 25, -45], 55),
        ([25, -25, 95, -70], 110),
    ]:
        arm = np.deg2rad(arm_deg)
        actual, old = mujoco.MjData(model), mujoco.MjData(reference)
        place_reset(model, actual, arm, theta_deg)
        theta = math.radians(theta_deg)
        x, delta = closure(theta)
        for i, q in enumerate(arm, 1):
            old.qpos[reference.joint(f"cad_j{i}").qposadr[0]] = q
        old.qpos[reference.joint("gripper_delta").qposadr[0]] = theta - math.pi / 2
        for side, sign in (("R", 1), ("L", -1)):
            old.qpos[reference.joint(f"slider_{side}").qposadr[0]] = sign * (x - X90)
        mujoco.mj_forward(reference, old)
        fixed = reference.body("c7_fixed").id
        rot = old.xmat[fixed].reshape(3, 3)
        local = np.array(
            [
                [math.cos(delta), -math.sin(delta), 0],
                [math.sin(delta), math.cos(delta), 0],
                [0, 0, 1],
            ]
        )
        quat = np.zeros(4)
        mujoco.mju_mat2Quat(quat, (rot @ local).reshape(-1))
        for side, sign in (("R", 1), ("L", -1)):
            mocap = reference.body_mocapid[reference.body(f"c7_link_{side}").id]
            old.mocap_pos[mocap] = old.xpos[fixed] + rot @ (
                sign * np.array([0.014 * math.cos(theta), 0.014 * math.sin(theta), 0])
            )
            old.mocap_quat[mocap] = quat
        mujoco.mj_forward(reference, old)
        errors = []
        for gid in range(reference.ngeom):
            name = reference.geom(gid).name
            if name.startswith("compact_") or name in {"table_display", "c7_L_pad", "c7_R_pad"}:
                continue
            nid = model.geom(name).id
            errors.append(float(np.linalg.norm(old.geom_xpos[gid] - actual.geom_xpos[nid])))
            errors.append(float(np.max(np.abs(old.geom_xmat[gid] - actual.geom_xmat[nid]))))
        equality_rows = np.where(actual.efc_type == mujoco.mjtConstraint.mjCNSTR_EQUALITY)[0]
        jac = actual.efc_J.reshape(-1, model.nv)[equality_rows, 4:9]
        max_error = max(errors)
        closure_error = float(np.max(np.abs(actual.efc_pos[equality_rows])))
        rank = int(np.linalg.matrix_rank(jac, tol=1e-8))
        tests.append(
            {
                "arm_deg": arm_deg,
                "theta_deg": theta_deg,
                "source_geometry_pose_max_error": max_error,
                "loop_anchor_error_m": closure_error,
                "jaw_constraint_rank": rank,
                "jaw_effective_dof": 5 - rank,
                "C7_design_pad_opening_m": 2 * (x - 0.0115),
                "pass": bool(max_error < 1e-9 and closure_error < 1e-9 and rank == 4),
            }
        )
    report = {
        "tests": tests,
        "all_pass": all(x["pass"] for x in tests),
        "total_mass_kg": float(model.body_mass.sum()),
        "cap_mass_kg": float(model.body_mass[model.body("cap").id]),
        "positive_moving_body_mass": bool(np.all(model.body_mass[1:] > 0)),
        "all_finite_parameters": bool(np.isfinite(model.body_inertia).all()),
        "gravity": model.opt.gravity.tolist(),
        "actuators": model.nu,
        "mocap": model.nmocap,
    }
    save_json(ROOT / "evidence/model-validation.json", report)
    print(json.dumps(report, indent=2))
    if not report["all_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
