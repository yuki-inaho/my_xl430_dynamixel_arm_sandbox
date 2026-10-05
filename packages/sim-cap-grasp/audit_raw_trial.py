"""Independent saved-physics audit; no project modules or dynamics integration.

Run through the visible execution console against a frozen candidate. Recomputes
all task metrics from raw qpos, timestamps and per-step contact forces. Sparse
forward solves independently check logged force magnitudes. Never changes input
files and never treats a rendered trajectory as a dynamics rerun.
"""

import gzip
import hashlib
import json
import sys
from pathlib import Path

import mujoco
import numpy as np

trial = Path(sys.argv[1]).resolve()
out = Path(__file__).parent / ("raw-audit-" + trial.name + ".json")
errors = []


def need(ok, message):
    if not bool(ok):
        errors.append(message)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


meta = json.loads((trial / "metadata.json").read_text())
contract = json.loads((trial / "evaluation_contract.json").read_text())
policy = json.loads((trial / "collision_pairs.json").read_text())
m = mujoco.MjModel.from_xml_path(str(trial / "scene.xml"))
with np.load(trial / "states.npz", allow_pickle=False) as z:
    s = {k: z[k] for k in z.files}
n = len(s["time"])
t = s["time"]
need(n >= 2002, "too few physics samples")
need(meta.get("exception") is None, "recorded runtime exception")
need(meta.get("stop_reason") is None, "abnormal runtime stop")
need(meta.get("completed_samples") == n, "metadata sample count mismatch")
need(meta.get("runtime_pose_writes") is False, "runtime pose mutation not excluded")
need(meta.get("external_forces_applied") is False, "external forces not excluded")
need(meta.get("scene_xml_sha256") == sha(trial / "scene.xml"), "scene hash mismatch")
need(
    meta.get("evaluation_contract_sha256") == sha(trial / "evaluation_contract.json"),
    "contract hash mismatch",
)
need(
    meta.get("collision_policy_sha256") == sha(trial / "collision_pairs.json"),
    "policy hash mismatch",
)
fixed = {
    "cap_bottom_clearance_m": 0.020,
    "continuous_hold_s": 2.0,
    "bilateral_contact_fraction_min": 0.80,
    "grip_frame_center_drift_max_m": 0.005,
    "approach_position_error_max_m": 0.002,
    "normal_force_epsilon_N": 0.00001,
    "forbidden_penetration_tolerance_m": 0.0001,
}
for k, v in fixed.items():
    need(type(contract.get(k)) in (int, float) and contract[k] == v, "changed contract " + k)
need(np.array_equal(m.opt.gravity, [0, 0, -9.81]), "gravity vector")
required_enabled = [
    "mjDSBL_CONSTRAINT",
    "mjDSBL_CONTACT",
    "mjDSBL_GRAVITY",
    "mjDSBL_ACTUATION",
    "mjDSBL_EQUALITY",
    "mjDSBL_LIMIT",
]
for flag in required_enabled:
    need(
        not (int(m.opt.disableflags) & int(getattr(mujoco.mjtDisableBit, flag))), "disabled " + flag
    )
need(m.nmocap == 0 and m.ntendon == 0 and m.nplugin == 0, "mocap/tendon/plugin present")
need(np.all(m.body_gravcomp == 0), "gravity compensation")
need(m.opt.density == 0 and m.opt.viscosity == 0, "fluid support possible")
cap = int(m.body("cap").id)
capj = int(m.body_jntadr[cap])
cq = int(m.jnt_qposadr[capj])
cv = int(m.jnt_dofadr[capj])
need(
    m.body_parentid[cap] == 0
    and m.body_jntnum[cap] == 1
    and m.jnt_type[capj] == mujoco.mjtJoint.mjJNT_FREE,
    "cap not independent free body",
)
need(
    m.jnt_stiffness[capj] == 0
    and np.all(m.dof_damping[cv : cv + 6] == 0)
    and np.all(m.dof_frictionloss[cv : cv + 6] == 0),
    "cap hidden spring/damping/friction support",
)
for i in range(m.neq):
    need(m.eq_type[i] == mujoco.mjtEq.mjEQ_CONNECT, "non-connect equality")
    need(cap not in (m.eq_obj1id[i], m.eq_obj2id[i]), "cap equality attachment")
expected = [int(m.joint(f"cad_j{i}").id) for i in range(1, 5)] + [int(m.joint("gripper_delta").id)]
need(m.nu == 5 and np.array_equal(m.actuator_trnid[:, 0], expected), "actuator inventory/targets")
need(
    np.all(m.actuator_forcelimited) and np.isfinite(m.actuator_forcerange).all(),
    "unbounded actuation",
)
need(np.isfinite(m.body_mass).all() and np.all(m.body_mass[1:] > 0), "mass validity")
need(np.isfinite(m.body_inertia).all() and np.all(m.body_inertia[1:] > 0), "inertia validity")
for k, a in s.items():
    if a.dtype.kind in "fiu":
        need(np.isfinite(a).all(), "nonfinite trace " + k)
need(s["qpos"].shape == (n, m.nq) and s["qvel"].shape == (n, m.nv), "raw state dimensions")
need(
    np.all(np.diff(t) > 0) and np.allclose(np.diff(t), m.opt.timestep, rtol=1e-7, atol=1e-9),
    "missing/reset/time gap",
)
need(np.all(s["warnings"] == 0), "solver/runtime warnings")
need(
    np.all((s["solver_iterations"] >= 0) & (s["solver_iterations"] < m.opt.iterations)),
    "solver budget or invalid count",
)
need(np.all(s["external_force_norm"] == 0), "nonzero applied force")
need(
    np.all(s["actuator_force"] >= m.actuator_forcerange[:, 0] - 1e-9)
    and np.all(s["actuator_force"] <= m.actuator_forcerange[:, 1] + 1e-9),
    "actuator force cap exceeded",
)
need(
    np.allclose(s["qpos"][0, cq : cq + 7], m.qpos0[cq : cq + 7], rtol=0, atol=1e-12),
    "cap initial reset differs from fixed scene",
)
need(
    np.allclose(np.linalg.norm(s["qpos"][:, cq + 3 : cq + 7], axis=1), 1, rtol=0, atol=1e-7),
    "cap quaternion invalid",
)

fk = mujoco.MjData(m)
sid = int(m.site("grip").id)
gp = np.empty((n, 3))
gr = np.empty((n, 3, 3))
axis = np.empty((n, 3))
cap_pos = s["qpos"][:, cq : cq + 3]
max_fk_error = 0.0
for i, q in enumerate(s["qpos"]):
    fk.qpos[:] = q
    mujoco.mj_kinematics(m, fk)
    gp[i] = fk.site_xpos[sid]
    gr[i] = fk.site_xmat[sid].reshape(3, 3)
    axis[i] = fk.xmat[cap].reshape(3, 3)[:, 2]
    max_fk_error = max(
        max_fk_error,
        float(np.max(np.abs(gp[i] - s["grip_position"][i]))),
        float(np.max(np.abs(gr[i] - s["grip_rotation"][i]))),
        float(np.max(np.abs(axis[i] - s["cap_axis"][i]))),
    )
need(max_fk_error <= 1e-9, "derived geometry differs from raw FK")
gcap = int(m.geom("cap_geom").id)
gbox = int(m.geom("box").id)
need(m.geom_type[gcap] == mujoco.mjtGeom.mjGEOM_CYLINDER, "unexpected cap geometry")
need(
    m.geom_bodyid[gbox] == 0 and np.array_equal(m.geom_quat[gbox], [1, 0, 0, 0]),
    "support plane is not fixed horizontal box",
)
plane = float(m.geom_pos[gbox, 2] + m.geom_size[gbox, 2])
need(abs(plane - meta["initial_support_plane_z_m"]) < 1e-12, "support datum mismatch")
r, h2 = m.geom_size[gcap, :2]
az = np.clip(np.abs(axis[:, 2]), 0, 1)
bottom = cap_pos[:, 2] - h2 * az - r * np.sqrt(1 - az * az)
clearance = bottom - plane
gmap = {g["name"]: g for g in policy["geoms"]}
pmap = {tuple(sorted((p["group1"], p["group2"]))): p for p in policy["group_pairs"]}
physical = {m.geom(i).name for i in range(m.ngeom) if m.geom_contype[i] or m.geom_conaffinity[i]}
need(set(gmap) == physical, "incomplete physical geom policy")
need(
    len(pmap) == len(policy["groups"]) * (len(policy["groups"]) - 1) // 2,
    "incomplete policy matrix",
)
eps = 1e-5
L = np.zeros(n)
R = np.zeros(n)
support = np.zeros(n, dtype=bool)
forbidden = []
sample_rows = {}
hold_idx = np.where(s["phase"] == "hold")[0]
sample_ids = {int(x) for x in np.linspace(hold_idx[0], hold_idx[-1], 9)} if len(hold_idx) else set()
rows = 0
contact_path = trial / "contacts.jsonl"
if not contact_path.exists():
    contact_path = trial / "contacts.jsonl.gz"
with gzip.open(contact_path, "rt") if contact_path.suffix == ".gz" else contact_path.open() as f:
    for i, line in enumerate(f):
        row = json.loads(line)
        rows += 1
        if i >= n:
            errors.append("too many contact rows")
            break
        need(
            row["i"] == i
            and type(row["time"]) in (int, float)
            and np.isfinite(row["time"])
            and abs(row["time"] - t[i]) <= 1e-9,
            "contact index/time mismatch",
        )
        need(isinstance(row.get("contacts"), list), "missing contact array")
        if i in sample_ids:
            sample_rows[i] = row
        for c in row["contacts"]:
            f6 = np.asarray(c["force"])
            dist = c["distance"]
            need(
                f6.shape == (6,) and np.isfinite(f6).all() and np.isfinite(dist),
                "nonfinite contact",
            )
            need(f6[0] >= -1e-12, "negative normal force")
            a, b = gmap[c["geom1"]], gmap[c["geom2"]]
            pair = pmap[tuple(sorted((a["group_id"], b["group_id"])))]
            fn = float(f6[0])
            if (
                pair["class"] == "forbidden"
                and (fn > eps or dist < -0.0001)
                and len(forbidden) < 15
            ):
                forbidden.append(
                    {"i": i, "pair": [a["name"], b["name"]], "fn": fn, "distance": dist}
                )
            if "cap_geom" in (a["name"], b["name"]):
                other = b if a["name"] == "cap_geom" else a
                if other["category"] == "softtip":
                    if other["side"] == "L":
                        L[i] += max(fn, 0)
                    elif other["side"] == "R":
                        R[i] += max(fn, 0)
                    else:
                        errors.append("unknown finger side")
                elif fn > eps:
                    support[i] = True
need(rows == n, "missing contact rows")
need(not forbidden, "forbidden collision in whole trial")
for j in range(m.njnt):
    if not m.jnt_limited[j]:
        continue
    tol = 1e-5 if m.jnt_type[j] == mujoco.mjtJoint.mjJNT_SLIDE else 1e-4
    q = s["qpos"][:, m.jnt_qposadr[j]]
    need(
        np.all(q >= m.jnt_range[j, 0] - tol) and np.all(q <= m.jnt_range[j, 1] + tol),
        "joint bounds " + m.joint(j).name,
    )
settle = np.where(s["phase"] == "settle")[0]
need(
    len(settle) > 0 and support[settle[-1]] and abs(clearance[settle[-1]]) <= 0.0005,
    "initial support not established",
)
approach = np.where(s["phase"] == "approach")[0]
position_error = pitch_error = None
if len(approach):
    i = int(approach[-1])
    target = np.asarray(meta["approach_target_position_m"])
    position_error = float(np.linalg.norm(gp[i] - target))
    pitch = (
        -s["qpos"][i, m.joint("cad_j2").qposadr[0]]
        + s["qpos"][i, m.joint("cad_j3").qposadr[0]]
        + s["qpos"][i, m.joint("cad_j4").qposadr[0]]
    )
    pitch_error = float(
        abs(
            np.arctan2(
                np.sin(pitch - contract["pitch_target_rad"]),
                np.cos(pitch - contract["pitch_target_rad"]),
            )
        )
    )
    need(
        position_error <= 0.002 and pitch_error <= contract["pitch_error_max_rad"], "approach error"
    )
else:
    errors.append("approach missing")
eligible = (s["phase"] == "hold") & (clearance >= 0.020) & ~support
start = None
interval = None
for i, good in enumerate(eligible):
    if not good:
        start = None
    elif start is None:
        start = i
    if start is not None and (i - start) * m.opt.timestep >= 2 and t[i] - t[start] >= 2 - 1e-9:
        interval = (start, i)
        break
metrics = {
    "approach_position_error_m": position_error,
    "approach_pitch_error_rad": pitch_error,
    "raw_samples": n,
    "fk_max_component_error": max_fk_error,
    "maximum_bottom_clearance_m": float(clearance.max()),
}
if interval:
    a, b = interval
    rel = np.einsum("nji,nj->ni", gr[a : b + 1], cap_pos[a : b + 1] - gp[a : b + 1])
    drift = float(np.max(np.linalg.norm(rel - rel[0], axis=1)))
    both = (L[a:b] > eps) & (R[a:b] > eps)
    duty = float(np.sum(np.diff(t)[a:b] * both) / (t[b] - t[a]))
    need(drift <= 0.005, "hold drift exceeds 5mm")
    need(duty >= 0.80, "bilateral duration below 80%")
    metrics.update(
        hold_start_s=float(t[a]),
        hold_end_s=float(t[b]),
        hold_step_duration_s=float((b - a) * m.opt.timestep),
        hold_observed_duration_s=float(t[b] - t[a]),
        hold_minimum_bottom_clearance_m=float(clearance[a : b + 1].min()),
        hold_bilateral_fraction=duty,
        hold_maximum_relative_drift_m=drift,
        hold_support_steps=int(support[a : b + 1].sum()),
        hold_left_normal_range_N=[float(L[a : b + 1].min()), float(L[a : b + 1].max())],
        hold_right_normal_range_N=[float(R[a : b + 1].min()), float(R[a : b + 1].max())],
    )
else:
    errors.append("no continuous 20mm/2s unsupported hold")

# Independent same-state forward solves; this is validation, not replay.
force_checks = []
for i in sorted(sample_rows):
    d = mujoco.MjData(m)
    d.qpos[:] = s["qpos"][i]
    d.qvel[:] = s["qvel"][i]
    d.ctrl[:] = s["ctrl"][i]
    mujoco.mj_forward(m, d)

    def summarize(contacts):
        v = {}
        for a, b, force in contacts:
            if "cap_geom" in (a, b):
                key = "|".join(sorted((a, b)))
                v[key] = v.get(key, 0) + float(force[0])
        return v

    recalculated = []
    for j, c in enumerate(d.contact):
        force = np.zeros(6)
        mujoco.mj_contactForce(m, d, j, force)
        recalculated.append((m.geom(c.geom1).name, m.geom(c.geom2).name, force))
    actual = summarize(recalculated)
    logged = summarize((c["geom1"], c["geom2"], c["force"]) for c in sample_rows[i]["contacts"])
    difference = max(
        [abs(actual.get(k, 0) - logged.get(k, 0)) for k in actual.keys() | logged.keys()],
        default=0.0,
    )
    force_checks.append(
        {
            "sample": i,
            "time": float(t[i]),
            "max_cap_pair_normal_difference_N": difference,
            "recomputed": actual,
            "logged": logged,
        }
    )
    need(difference <= 1e-4, "sparse independent contact-force mismatch")
result = {
    "trial": "results/" + trial.name,
    "scene_sha256": sha(trial / "scene.xml"),
    "states_sha256": sha(trial / "states.npz"),
    "contacts_sha256": sha(contact_path),
    "contacts_file": contact_path.name,
    "mujoco_version": mujoco.__version__,
    "physics_parameters": {
        "timestep": m.opt.timestep,
        "impratio": m.opt.impratio,
        "noslip_iterations": m.opt.noslip_iterations,
        "cap_mass_kg": float(m.body_mass[cap]),
        "gravity": m.opt.gravity.tolist(),
    },
    "errors": errors,
    "pass": not errors,
    "metrics": metrics,
    "forbidden_examples": forbidden,
    "sparse_force_checks": force_checks,
    "dynamics_reexecuted": False,
    "scope": "Independent full raw-trajectory acceptance and model audit; genuine dynamics replay is a separate required experiment.",
}
out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
print(json.dumps(result, indent=2, allow_nan=False))
raise SystemExit(0 if result["pass"] else 1)
