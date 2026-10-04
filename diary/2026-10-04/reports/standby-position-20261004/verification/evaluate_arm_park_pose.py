"""Offline R3 park-pose evaluation. No acquisition, port, or motion code."""
import argparse
import hashlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import mujoco
import numpy as np


def pitch(vector):
    return math.degrees(math.atan2(vector[2], math.hypot(vector[0], vector[1])))

def visible_mesh_bounds(model, data, groups=(0,1,2)):
    points = []
    detail = {}
    for gid in range(model.ngeom):
        if (model.geom_type[gid] != mujoco.mjtGeom.mjGEOM_MESH
                or model.geom_group[gid] not in groups):
            continue
        mid = model.geom_dataid[gid]
        start, count = model.mesh_vertadr[mid], model.mesh_vertnum[mid]
        vertices = model.mesh_vert[start:start+count].astype(float)
        world = vertices @ data.geom_xmat[gid].reshape(3,3).T + data.geom_xpos[gid]
        points.append(world)
        detail[mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_GEOM,gid)] = {
            "min_m":world.min(0).tolist(),"max_m":world.max(0).tolist()}
    all_points = np.concatenate(points)
    return {"min_m":all_points.min(0).tolist(),"max_m":all_points.max(0).tolist(),"by_geom":detail}

def measure(model, q, theta, apply_pose):
    data = mujoco.MjData(model)
    apply_pose(model,data,q,theta)
    elbow = data.xpos[model.body("arm_link_3").id]
    wrist = data.xpos[model.body("arm_link_4").id]
    id5 = data.xpos[model.body("c7_fixed").id]
    forearm = (wrist-elbow)/np.linalg.norm(wrist-elbow)
    hand = (id5-wrist)/np.linalg.norm(id5-wrist)
    return {"q_cad_deg":q,"theta_cad_deg":theta,
            "qpos":data.qpos.tolist(),
            "elbow_world_m":elbow.tolist(),"wrist_world_m":wrist.tolist(),"id5_world_m":id5.tolist(),
            "forearm_unit_world":forearm.tolist(),"forearm_pitch_deg":pitch(forearm),
            "id5_support_direction_unit_world":hand.tolist(),"id5_pitch_deg":pitch(hand),
            "mesh_bounds":visible_mesh_bounds(model,data)}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulation-root",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--baseline",type=Path,required=True)
    parser.add_argument("--example-shoulder-deg",type=float,default=-20)
    args=parser.parse_args()
    if not math.isfinite(args.example_shoulder_deg) or not -40 <= args.example_shoulder_deg <= 40:
        parser.error("Example shoulder must be finite and within the existing display interval")
    simulation_root=args.simulation_root.resolve()
    sys.path.insert(0,str(simulation_root/"simulation/current_arm_viewer"))
    from server import apply_kinematic_pose
    model_dir=simulation_root/"outputs/current-arm-mujoco-20261003"
    scene=model_dir/"scene.xml"
    model=mujoco.MjModel.from_xml_path(str(scene))
    # These equations are only valid for this explicitly verified R3 axis layout.
    for i, axis in enumerate(([0,0,1],[-1,0,0],[1,0,0],[1,0,0]),1):
        np.testing.assert_allclose(model.jnt_axis[model.joint(f"cad_j{i}").id],axis,atol=1e-12)
    cases=[]
    for shoulder in sorted(set([-20.0,0.0,20.0,args.example_shoulder_deg])):
        case=measure(model,[0,shoulder,shoulder,-30],90,apply_kinematic_pose)
        np.testing.assert_allclose(case["forearm_unit_world"],[0,1,0],atol=1e-9)
        np.testing.assert_allclose(case["id5_support_direction_unit_world"],[0,math.cos(math.pi/6),-0.5],atol=1e-9)
        cases.append(case)
    baseline=json.loads(args.baseline.read_text())
    motors=baseline["last_valid_frame"]["motors"]
    assert len({m["motor_id"] for m in motors})==5
    assert all(m["torque_enabled"] is False for m in motors)
    assert baseline["end"]["summary"]["port_closed"] is True
    chosen=next(c for c in cases if c["q_cad_deg"][1]==args.example_shoulder_deg)
    # This is solely an illustration of a folded R3 link, not current hardware reconstruction.
    centres=[np.array(j["centre_mm"],dtype=float) for j in baseline["cad_joints"]]
    upper=centres[1]-centres[2]
    folded_q3=math.degrees(math.atan2(upper[2],upper[1]))
    folded_example=measure(model,[0,0,folded_q3,0],90,apply_kinematic_pose)
    definition={
        "schema_version":1,"created_at":datetime.now().astimezone().isoformat(),
        "configuration":"R3/C7/R5_65 candidate","simulation_only":True,"hardware_targets":None,
        "source_scene_sha256":hashlib.sha256(scene.read_bytes()).hexdigest(),
        "world_frame":{"forward":[0,1,0],"up":[0,0,1],"origin":"R3 base CAD frame"},
        "standby":{
            "status":"CAD_ORIENTATION_CANDIDATE_UNCALIBRATED",
            "neutral_yaw_cad_deg":0,"shoulder_cad_deg":None,
            "shoulder_rule":"preserve the calibrated current shoulder angle",
            "elbow_rule":"q3 = q2 for horizontal +Y forearm in this R3 model",
            "wrist_rule":"q4 = -30 degrees after the forearm is horizontal",
            "gripper_motor_neutral_count":None,
            "gripper_rule":"preserve/confirm physical ID5 neutral; do not equate it to CAD theta90",
            "example_only":chosen},
        "power_off":{
            "name":"POWER_OFF_SUPPORTED_CURRENT",
            "status":"USER_REPORTED_STABLE_SUPPORT_NEEDS_PHYSICAL_CAPTURE",
            "user_condition":"keep approximately the current stable pose; front cushion about5mm",
            "target_counts":None,"target_cad_deg":None,
            "historical_counts":{str(m["motor_id"]):m["position_counts"] for m in motors},
            "historical_observed_at":baseline["last_valid_frame"]["finished_at"],
            "historical_log":baseline["source_log"],"historical_log_sha256":baseline["source_sha256"],
            "support":{"front_of_base":True,"top_height_m_approx":0.005,
                       "xy_footprint_m":None,"contact_points":None,
                       "compression_stiffness":None,"physical_load_transfer_verified":False},
            "folded_CAD_example_not_current":folded_example},
        "verification":{"standby_orientation":"PASS","cases":cases,
            "self_collision":"UNKNOWN_BOOLEAN_INPUT_CONTROL_ERROR",
            "continuous_path":"UNKNOWN","power_off_dynamic_stability":"UNKNOWN",
            "model_gravity_m_s2":model.opt.gravity.tolist(),
            "contacts_enabled":bool(np.any(model.geom_contype) or np.any(model.geom_conaffinity)),
            "mass_inertia":"placeholder; no force or stability claims"}
    }
    args.output_dir.mkdir(exist_ok=True,parents=True)
    (args.output_dir/"positions.json").write_text(json.dumps(definition,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"orientation":"PASS","example_cad_deg":chosen["q_cad_deg"],
       "forearm_pitch":chosen["forearm_pitch_deg"],"id5_pitch":chosen["id5_pitch_deg"],
       "lowest_non_base_mesh_mm":min(
           v["min_m"][2] for n,v in chosen["mesh_bounds"]["by_geom"].items()
           if n not in ("M01","P01_base","M02","P02_yaw_carrier"))*1000,
       "folded_example_q3":folded_q3,"hardware_targets":None},ensure_ascii=False))
if __name__=="__main__":
    main()


