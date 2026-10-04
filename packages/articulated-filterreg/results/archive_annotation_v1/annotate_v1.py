"""Manual image observations with explicit provenance, not SAM/BiRefNet inference.

Coordinates were read from the submitted RGB and magnified crops. The held-out
screw/plate landmarks are not passed to the optimizer or to candidate selection.
"""
from pathlib import Path
import json,hashlib
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
POLYGONS={
 'M01':[[159,298],[246,300],[241,334],[160,331]],
 'P01_base':[[116,278],[155,278],[156,295],[247,300],[240,350],[212,347],[207,341],[195,345],[176,344],[159,350],[132,339],[100,329],[103,314],[112,294],[117,293]],
 'M02':[[164,224],[196,216],[200,279],[154,277]],
 'P02_yaw_carrier':[[117,275],[157,278],[162,282],[189,285],[210,294],[248,293],[247,302],[153,297],[154,286],[117,285]],
 'P03_shoulder_XL430':[[198,121],[232,124],[230,155],[235,173],[246,188],[254,208],[254,233],[250,254],[252,273],[249,299],[226,298],[211,290],[201,278]],
 'M03':[[182,49],[191,34],[220,29],[242,34],[284,36],[290,47],[288,83],[286,103],[280,119],[204,123],[185,115]],
 'P03_top':[[184,113],[233,116],[282,123],[260,130],[189,123]],
 'P04_extension_XL430':[[288,51],[373,71],[382,111],[371,140],[361,153],[279,123],[279,117],[289,111]],
 'M04':[[377,73],[389,68],[409,72],[432,76],[456,82],[471,97],[475,111],[461,152],[436,162],[372,147],[379,121]],
 'P05_wrist_XL430':[[468,135],[518,107],[539,130],[544,125],[581,174],[579,186],[539,224],[526,230],[479,187],[455,166],[433,164],[423,151],[420,137],[425,120],[436,112],[450,110],[465,116]]}
OCCLUSIONS={
 'yellow_tape':[[126,225],[141,226],[164,233],[154,280],[102,268],[110,252]],
 'foreground_fabric':[[0,367],[13,363],[38,348],[61,333],[79,330],[100,332],[121,339],[145,349],[168,361],[183,367]]}

def landmark(name,p_mm,uv,level,split,uncertainty=2):
    return {'name':name,'reference_point_m':(np.array(p_mm)/1000).tolist(),'pixel_uv':uv,'level':level,'split':split,'annotation_uncertainty_px':uncertainty}

def main():
    o=np.load(ROOT/'model/observations.npz');rgb=o['rgb'];h,w=rgb.shape[:2]
    mask=np.zeros((h,w),np.uint8);part=np.zeros_like(mask)
    for j,(name,poly) in enumerate(POLYGONS.items(),1):
        cv2.fillPoly(mask,[np.array(poly,np.int32)],255)
        cv2.fillPoly(part,[np.array(poly,np.int32)],j)
    cv2.ellipse(mask,(260,95),(30,32),-12,0,360,255,-1)
    # The narrow opening in the upper-link side wall is background, not solid CAD.
    hole=np.array([[248,221],[254,222],[253,235],[246,252],[246,244]],np.int32)
    cv2.fillPoly(mask,[hole],0)
    occ=np.zeros_like(mask)
    for poly in OCCLUSIONS.values():cv2.fillPoly(occ,[np.array(poly,np.int32)],255)
    mask[occ>0]=0
    lms=[
      landmark('J2_front_center',[21.8,0,56.3],[224.3,278.3],2,'train',1.5),
      landmark('J3_front_center',[22.8,14.8,164.6],[260.6,93.4],3,'train',1.5),
      landmark('J4_front_center',[22.8,104.9,164.6],[448.5,137.0],4,'train',1.5),
      landmark('P05_plate_near_low',[18.05,158.9,168.6],[517.0,196.0],4,'train',2),
      landmark('P05_plate_near_high',[18.05,158.9,192.6],[554.6,168.2],4,'train',2),
      landmark('P03_screw_left',[21.8,-8,56.3],[208.5,277.8],2,'held_out'),
      landmark('P03_screw_up',[21.8,0,64.3],[225.2,267.8],2,'held_out'),
      landmark('P03_screw_right',[21.8,8,56.3],[238.5,280.5],2,'held_out'),
      landmark('P03_screw_down',[21.8,0,48.3],[225.0,292.0],2,'held_out'),
      landmark('P04_screw_left',[22.8,6.8,164.6],[242.5,93.3],3,'held_out'),
      landmark('P04_screw_up',[22.8,14.8,172.6],[263.8,81.4],3,'held_out'),
      landmark('P04_screw_right',[22.8,22.8,164.6],[278.8,101.4],3,'held_out'),
      landmark('P04_screw_down',[22.8,14.8,156.6],[257.5,114.4],3,'held_out'),
      landmark('P05_screw_yminus',[22.8,96.9,164.6],[439.4,128.9],4,'held_out'),
      landmark('P05_screw_zplus',[22.8,104.9,172.6],[463.1,129.4],4,'held_out'),
      landmark('P05_screw_yplus',[22.8,112.9,164.6],[460.1,151.6],4,'held_out'),
      landmark('P05_screw_zminus',[22.8,104.9,156.6],[436.5,151.5],4,'held_out'),
      landmark('P05_plate_far_low',[18.05,170.9,168.6],[530.0,212.0],4,'held_out',2.5),
      landmark('P05_plate_far_high',[18.05,170.9,192.6],[567.2,182.6],4,'held_out',2.5)]
    annotation={'method':'manual assistant visual annotation of submitted RGB; no neural inference',
      'image_size':[w,h],'image_sha256':hashlib.sha256(Path('/mnt/data/standby.jpg').read_bytes()).hexdigest(),
      'frozen_before_multistart_optimization':True,'mask_boundary_uncertainty_px':2,
      'polygons':POLYGONS,'background_opening_polygon':hole.tolist(),'external_occlusions':OCCLUSIONS,'landmarks':lms,
      'mask_note':'Includes black motor ID1 explicitly. Excludes cables and external foreground. Polygon part IDs are approximate semantic assistance, not an automatic segmentation result.',
      'held_out_policy':'Held-out landmarks must not enter initialization, optimization, or candidate ranking; used only for final diagnostic evaluation.',
      'geometry_difference':'The photographed large P05 far-low opening is wider than the R3 source hole. Its center is evaluated, not its radius; CAD is not edited to match it.'}
    (ROOT/'annotations/annotations.json').write_text(json.dumps(annotation,ensure_ascii=False,indent=2))
    cv2.imwrite(str(ROOT/'annotations/robot_mask.png'),mask);cv2.imwrite(str(ROOT/'annotations/external_occlusion.png'),occ)
    cv2.imwrite(str(ROOT/'annotations/manual_part_ids.png'),part)
    out=rgb.copy();inside=mask>0;out[inside]=(out[inside]*.7+np.array([20,200,210])*.3).astype(np.uint8)
    for k,lm in enumerate(lms):
        u,v=map(round,lm['pixel_uv']);c=(250,210,30) if lm['split']=='train' else (240,70,160)
        cv2.circle(out,(u,v),2,c,-1)
    cv2.imwrite(str(ROOT/'annotations/annotation_overlay.png'),cv2.cvtColor(out,cv2.COLOR_RGB2BGR))
    print('Manual foreground pixels',int((mask>0).sum()),'External occlusion',int((occ>0).sum()),'Training/held-out',sum(l['split']=='train' for l in lms),sum(l['split']=='held_out' for l in lms))
if __name__=='__main__':main()
