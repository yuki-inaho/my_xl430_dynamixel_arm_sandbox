"""Estimate photograph intrinsics/extrinsics from saved manual scan correspondences."""
import json
from pathlib import Path
import cv2,numpy as np
from scipy.optimize import least_squares
from PIL import Image,ImageDraw
from render import camera,raster
from calibrate_scan import sample_xyz
ROOT=Path(__file__).resolve().parents[1]

def main():
    d=np.load(ROOT/'inputs/scan_cad_mm.npz');v=d['vertices'];f=np.load(ROOT/'inputs/scan_faces_object.npy');c=d['colors']
    view=np.load(ROOT/'annotations/canonical_oblique.npz')
    # All photo coordinates refer to the 1408x1056 image, not the 2048x1536 source.
    names=['cap_front_L','cap_front_R','finger_screw_L','finger_screw_R','drive_screw_back','drive_screw_front','white_tab_L','white_tab_R','cot_rim_L','cot_rim_R']
    scan=np.array([[263,978],[1135,976],[231,824],[1140,826],[554, 712],[813,836],[391,757],[969,759],[422,571],[888,565]])
    image=np.array([[426,655],[1039,661],[405,539],[1046,548],[646,444],[806,544],[517,507],[936,513],[532,378],[896,377]],float)
    xyz=np.array([sample_xyz(p,view,v,f) for p in scan])
    R0,eye=camera([0,-200,200],[0,0,50],[0,0,1]);rv=cv2.Rodrigues(R0)[0].ravel();tv=-R0@eye
    def project(p):
        focal=np.exp(p[6]);K=np.array([[focal,0,704],[0,focal,528],[0,0,1]])
        return cv2.projectPoints(xyz,p[:3],p[3:6],K,None)[0][:,0,:]
    def error(p):return (project(p)-image).ravel()
    best=None;trials=[]
    for focal in [900,1400,2100,3000]:
        p0=np.r_[rv,tv*focal/1800,np.log(focal)]
        res=least_squares(error,p0,loss='soft_l1',f_scale=3,max_nfev=1500,bounds=([-np.inf]*6+[np.log(500)],[np.inf]*6+[np.log(6000)]))
        cost=np.sum(np.sqrt(error(res.x)**2+9)-3);trials.append({'initial_focal':focal,'cost':cost,'success':bool(res.success)})
        if best is None or cost<best[0]:best=(cost,res.x)
    p=best[1];pr=project(p);err=np.linalg.norm(pr-image,axis=1);focal=np.exp(p[6]);R=cv2.Rodrigues(p[:3])[0];K=np.array([[focal,0,704],[0,focal,528],[0,0,1]])
    data={'resolution':[1408,1056],'focal_px':float(focal),'principal_point':[704,528],'K':K.tolist(),'R_cad_to_camera':R.tolist(),'t_cad_to_camera_mm':p[3:6].tolist(),'manual_features':names,'scan_view_pixels':scan.tolist(),'scan_points_cad_mm':xyz.tolist(),'photo_pixels':image.tolist(),'reprojected_pixels':pr.tolist(),'residual_pixels':err.tolist(),'median_error_px':float(np.median(err)),'rms_error_px':float(np.sqrt(np.mean(err**2))),'trials':trials,'note':'All correspondences used for calibration, not independent held-out validation. Focal fitted, principal point fixed to image center; zero lens distortion assumed. Scan/photo are separate captures.'}
    (ROOT/'results/photo_camera.json').write_text(json.dumps(data,indent=2))
    im=Image.open(ROOT/'annotations/photo_1408.png').convert('RGB');dr=ImageDraw.Draw(im)
    for name,a,b in zip(names,image,pr):
        x,y=a;dr.ellipse((x-5,y-5,x+5,y+5),outline='yellow',width=2);dr.line((tuple(a),tuple(b)),fill='red',width=2);dr.text((x+6,y+6),name,fill='yellow')
    im.save(ROOT/'annotations/photo_calibration.png')
    pc=v@R.T+p[3:6];q=pc.copy();q[:,:2]=pc[:,:2]/pc[:,2,None]*focal+[704,528]
    rgb,z,ids,b=raster(q,f,c[:,:3].astype(float),1408,1056,True)
    Image.fromarray(rgb).save(ROOT/'annotations/photo_projected_scan.png')
    np.savez_compressed(ROOT/'annotations/photo_projected_scan_maps.npz',ids=ids,bary=b)
    orig=np.array(Image.open(ROOT/'annotations/photo_1408.png'));mask=ids>=0;orig[mask]=(orig[mask]*.45+rgb[mask]*.55).astype(np.uint8)
    Image.fromarray(orig).save(ROOT/'annotations/photo_scan_check.png')
    print(json.dumps(data,indent=2))
if __name__=='__main__':main()
