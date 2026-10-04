"""Manual CAD/scan datum correspondences and least-squares similarity."""
from pathlib import Path
import json,numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]

def sample_xyz(uv, view, vertices, faces):
    x,y=map(int,uv);i=int(view['ids'][y,x]);b=view['bary'][y,x]
    if i<0:raise ValueError(f'No surface at {uv}')
    return b@vertices[faces[i]]

def similarity(a,b):
    """Row vectors: b = scale * a @ rotation.T + translation."""
    ma=a.mean(0);mb=b.mean(0);aa=a-ma;bb=b-mb
    U,S,Vt=np.linalg.svd(bb.T@aa/len(a));D=np.eye(3);D[2,2]=np.linalg.det(U@Vt)
    R=U@D@Vt;s=(S*np.diag(D)).sum()/np.mean(np.sum(aa**2,axis=1));t=mb-s*R@ma
    return s,R,t

def main():
    d=np.load(ROOT/'inputs/scan_raw.npz');v=d['vertices'];c=d['colors'];faces=np.load(ROOT/'inputs/scan_faces_gripper.npy')
    view=np.load(ROOT/'annotations/gripper_top.npz')
    points=[[321,391],[946,440],[291,802],[916,848]]
    # z=29.4 is nominal bolt-head top; retained as initial datum only.
    cad=np.array([[-37.5,24.5,29.4],[37.5,24.5,29.4],[-37.5,-24.5,29.4],[37.5,-24.5,29.4]])
    xyz=np.array([sample_xyz(p,view,v,faces) for p in points])
    s,R,t=similarity(xyz,cad);q=s*v@R.T+t
    # Fit the visible upper cap surface to z=27.1. Median avoids screw and edge pixels.
    capmask=(abs(q[:,0])<32)&(abs(q[:,1])>21)&(abs(q[:,1])<26.5)&(q[:,2]>24)&(q[:,2]<29)&(c[:,:3].min(1)>120)
    dz=27.1-np.median(q[capmask,2]);t[2]+=dz;q[:,2]+=dz
    error=s*xyz@R.T+t-cad
    result={'method':'manual 4 cap screw correspondences + similarity; Z datum from cap plane', 'source_glb':'Scaniverse 2026-10-04 205850.glb',
    'scale_mm_per_source_unit':s,'scale_relative_to_meters':s/1000,'R_source_to_cad':R.tolist(),'t_source_to_cad_mm':t.tolist(),
    'coordinate_definition':'X photo right, Y toward back rail, Z up; native C92 construction frame in mm',
    'manual_top_view_pixels':points,'scan_correspondences_raw':xyz.tolist(),'cad_correspondences_mm':cad.tolist(),
    'datum_residual_xyz_mm':error.tolist(),'datum_xy_rms_mm':float(np.sqrt(np.mean(np.sum(error[:,:2]**2,axis=1)))),
    'cap_datum_z_shift_mm':float(dz),'cap_points':int(capmask.sum()),'cap_height_p10_p50_p90_mm':np.percentile(q[capmask,2],[10,50,90]).tolist(),
    'limitations':'Screw center picks are manual; nominal hardware height is not metrology. No independent instrument scale calibration.'}
    (ROOT/'results/calibration.json').write_text(json.dumps(result,indent=2))
    np.savez_compressed(ROOT/'inputs/scan_cad_mm.npz',vertices=q,faces=d['faces'],colors=c)
    im=Image.open(ROOT/'annotations/gripper_top.png');dr=ImageDraw.Draw(im)
    for i,p in enumerate(points):
        x,y=p;dr.ellipse((x-8,y-8,x+8,y+8),outline='red',width=3);dr.text((x+14,y-15),str(i+1),fill='red')
    im.save(ROOT/'annotations/scan_datum_picks.png')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
