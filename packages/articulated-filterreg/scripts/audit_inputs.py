"""Audit submitted monocular data without changing the submitted files."""
from pathlib import Path
import os, json, hashlib, sys
os.environ['OPENCV_IO_ENABLE_OPENEXR']='1'
import cv2
import numpy as np
import trimesh
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
INPUT=Path('/mnt/data')
SRC=INPUT/'work/input/3d-printed-dynamixel-gripper-main'

def main(input_dir:Path=INPUT,source_dir:Path=SRC):
    INPUT=input_dir
    SRC=source_dir
    image=cv2.imread(str(INPUT/'standby.jpg')); h,w=image.shape[:2]
    depth=cv2.imread(str(INPUT/'depth.exr'),cv2.IMREAD_UNCHANGED)
    xyz=cv2.imread(str(INPUT/'points.exr'),cv2.IMREAD_UNCHANGED)[...,::-1].copy()
    v,u=np.indices((h,w)); good=np.isfinite(xyz).all(-1)&(xyz[...,2]>0)
    xz=xyz[...,0][good]/xyz[...,2][good]; yz=xyz[...,1][good]/xyz[...,2][good]
    fx,cx=np.linalg.lstsq(np.column_stack((xz,np.ones(len(xz)))),u[good],rcond=None)[0]
    fy,cy=np.linalg.lstsq(np.column_stack((yz,np.ones(len(yz)))),v[good],rcond=None)[0]
    K=np.array([[w/(2*np.tan(np.deg2rad(51/2))),0,(w-1)/2],[0,h/(2*np.tan(np.deg2rad(30/2))),(h-1)/2],[0,0,1.]])
    target=np.dstack(((u-K[0,2])/K[0,0]*depth,(v-K[1,2])/K[1,1]*depth,depth))
    ply=trimesh.load(INPUT/'pointcloud.ply',process=False).vertices*np.array([1,-1,-1])
    from scipy.spatial import cKDTree
    dd,_=cKDTree(xyz[good]).query(ply[::53])
    manifests=json.loads((SRC/'references/arm-r3/manifest.json').read_text())
    bare=[r for r in manifests if r['level']<=4]
    old=ET.parse(SRC/'references/arm-baseline/low-cost-arm.urdf').getroot()
    report={'image_size':[w,h], 'supplied_fov_deg':[51.,30.], 'camera_K_nominal':K.tolist(),
      'exr_fitted_intrinsics':{'fx':float(fx),'fy':float(fy),'cx':float(cx),'cy':float(cy),
      'fov_deg':[float(np.rad2deg(2*np.arctan(w/(2*fx)))),float(np.rad2deg(2*np.arctan(h/(2*fy))))]},
      'depth_points_z_max_abs_diff':float(np.max(np.abs(depth-xyz[...,2]))),
      'exr_intrinsics_max_reprojection_px':float(max(np.max(abs(fx*xz+cx-u[good])),np.max(abs(fy*yz+cy-v[good])))),
      'ply_to_exr_transform':'diag(1,-1,-1); PLY uses camera x-right y-up z-backward',
      'ply_sample_max_nearest_error':float(dd.max()),'ply_vertices':len(ply),
      'depth_units':'arbitrary monocular reconstruction units, not independently measured meters',
      'fit_target_definition':'reproject depth.exr with nominal supplied H51/V30 intrinsics; original EXR preserved',
      'source_step':'3d-printed-dynamixel-gripper-main/references/arm-r3/arm_XL430_R3.step',
      'source_step_sha256':hashlib.sha256((SRC/'references/arm-r3/arm_XL430_R3.step').read_bytes()).hexdigest(),
      'source_units':'mm; divide by 1000 once for generated meter model',
      'all_leaf_count':len(manifests),'bare_leaf_count':len(bare),
      'included_physical_units':sorted({r['physical_unit'] for r in bare}),
      'included_levels':sorted({r['level'] for r in bare}),
      'excluded':['M06','P06_fixed_gripper_XL430','P07_moving_gripper_XL430','D405','camera mount','unmodeled cables'],
      'old_urdf_links':[el.attrib['name'] for el in old.findall('link')],
      'urdf_decision':'retain old URDF as topology reference only; derive a separate R3 bare-arm URDF from R3 STEP+joint source',
      'joint5_observability':'M05 output has no downstream installed shape; J5 is unobservable and excluded from estimation',
      'joint6_status':'not installed',
      'annotation_model_status':'No EdgeTAM/BiRefNet weights or user-produced foreground mask attached; no neural inference performed'}
    np.savez_compressed(ROOT/'model/observations.npz',rgb=cv2.cvtColor(image,cv2.COLOR_BGR2RGB),depth=depth,xyz=target,K=K)
    (ROOT/'docs/input_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',type=Path,default=INPUT)
    parser.add_argument('--source',type=Path,default=SRC)
    args=parser.parse_args();main(args.input_dir,args.source)
