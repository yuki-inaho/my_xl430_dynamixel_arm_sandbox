"""Rasterize measured-model overlays, without image generation or 2-D warping."""
import json
from pathlib import Path
import numpy as np,cv2,trimesh
from PIL import Image,ImageDraw,ImageFont
from render import raster,ortho
from build_models import DISPLAY,PHYSICAL
ROOT=Path(__file__).resolve().parents[1]

def model_arrays():
    data=np.load(ROOT/'results/model_meshes.npz');vv=[];ff=[];cc=[];labels=[];off=0
    for idx,name in enumerate(PHYSICAL,1):
        v=data[name+'_vertices'];f=data[name+'_faces'];vv.append(v);ff.append(f+off);cc.append(np.tile(DISPLAY[name],(len(v),1)));labels.extend([idx]*len(f));off+=len(v)
    return np.concatenate(vv),np.concatenate(ff),np.concatenate(cc),np.array(labels)

def blend(original,rgb,ids,face_labels,alpha=.32):
    out=np.array(original).copy();mask=ids>=0;out[mask]=(out[mask]*(1-alpha)+rgb[mask]*alpha).astype(np.uint8)
    label=np.zeros(ids.shape,np.uint8);label[mask]=face_labels[ids[mask]]
    for idx,name in enumerate(PHYSICAL,1):
        contours,_=cv2.findContours((label==idx).astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(out,contours,-1,DISPLAY[name],2,cv2.LINE_AA)
    return out,label

def main():
    v,f,c,fl=model_arrays()
    cam=json.loads((ROOT/'results/photo_camera.json').read_text());R=np.array(cam['R_cad_to_camera']);t=np.array(cam['t_cad_to_camera_mm']);focal=cam['focal_px']
    pc=v@R.T+t;q=pc.copy();q[:,:2]=pc[:,:2]/pc[:,2,None]*focal+[704,528]
    rgb,z,ids,b=raster(q,f,c.astype(float),1408,1056,True)
    source=Image.open(ROOT/'annotations/photo_1408.png');result,lab=blend(source,rgb,ids,fl)
    Image.fromarray(result).save(ROOT/'results/photo_overlay_draft.png');Image.fromarray(rgb).save(ROOT/'results/photo_model_only_draft.png')
    # Orthographic scan overlays; no scan-based clipping of the CAD silhouette.
    viewpoints={'front':([0,-300,55],[0,0,55],[0,0,1],110,1400,1200),'top':([0,0,300],[0,0,25],[0,1,0],110,1400,1000),'oblique':([0,-240,220],[0,0,50],[0,0,1],120,1400,1200),'side':([300,0,55],[0,0,55],[0,0,1],100,1200,1200)}
    for name,(eye,target,up,span,w,h) in viewpoints.items():
        rgb,z,ids,b=ortho(v,f,c,eye,target,up,span,w,h)
        scan=Image.open(ROOT/f'annotations/canonical_{name}.png');out,label=blend(scan,rgb,ids,fl,.35)
        Image.fromarray(out).save(ROOT/f'results/scan_overlay_{name}.png')
        Image.fromarray(rgb).save(ROOT/f'results/model_{name}.png')
    print('Rendered')
if __name__=='__main__':main()
