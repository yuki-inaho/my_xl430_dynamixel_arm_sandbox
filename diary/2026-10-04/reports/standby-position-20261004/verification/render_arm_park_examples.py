"""Render bare-arm park examples; no hardware interface."""
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")
import cv2
import mujoco


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulation-root",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--photo",type=Path,required=True)
    args=parser.parse_args()
    sys.path.insert(0,str(args.simulation_root/"simulation/current_arm_viewer"))
    from server import apply_kinematic_pose
    spec=importlib.util.spec_from_file_location("park_evaluator",Path(__file__).with_name("evaluate_arm_park_pose.py"))
    evaluator=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    model=mujoco.MjModel.from_xml_path(str(args.simulation_root/"outputs/current-arm-mujoco-20261003/scene.xml"))
    renderer=mujoco.Renderer(model,height=760,width=1060)
    option=mujoco.MjvOption()
    option.geomgroup[:]=[1,0,0,0,0,0]  # R3 bare arm, no assumed camera/C7
    cases={"photo_shape_approximation":[0,-30,-75,25],"standby_bare_example":[0,-30,-30,-30]}
    result={"simulation_only":True,"current_hardware_reconstruction_verified":False,
        "photo_path":str(args.photo),"photo_sha256":hashlib.sha256(args.photo.read_bytes()).hexdigest(),
        "photo_observation":"folded bare arm; no C7 jaws or D405 holder visibly installed",
        "approximation_basis":(
            "assumed side-plane CAD angles from photograph; not calibrated"),
        "world_forward":"+Y","model_groups":[0],"cases":{}}
    args.output_dir.mkdir(exist_ok=True,parents=True)
    try:
        for name,q in cases.items():
            d=mujoco.MjData(model)
            apply_kinematic_pose(model,d,q,90)
            measured=evaluator.measure(model,q,90,apply_kinematic_pose)
            measured["mesh_bounds"]=evaluator.visible_mesh_bounds(model,d,groups=(0,))
            result["cases"][name]=measured
            for view,azimuth,elevation in (("side",0,-8),("iso",225,-25)):
                camera=mujoco.MjvCamera()
                camera.lookat[:]=[0,0.07,0.13]
                camera.distance=0.46
                camera.azimuth=azimuth
                camera.elevation=elevation
                renderer.update_scene(d,camera=camera,scene_option=option)
                rgb=renderer.render()
                assert cv2.imwrite(str(args.output_dir/f"{name}-{view}.png"),
                                   cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR))
    finally:
        renderer.close()
    shutil.copyfile(args.photo,args.output_dir/"current-photo.jpeg")
    (args.output_dir/"photo-pose-analysis.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"photo_sha256":result["photo_sha256"],"pose_examples":cases,
        "standby_forearm_pitch":result["cases"]["standby_bare_example"]["forearm_pitch_deg"],
        "standby_id5_pitch":result["cases"]["standby_bare_example"]["id5_pitch_deg"],
        "photo_approximation_is_calibrated":False}))
if __name__=="__main__":
    main()


