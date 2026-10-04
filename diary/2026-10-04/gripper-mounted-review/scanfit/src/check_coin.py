"""Independent scale check: coin is not used to set the CAD scale."""
from pathlib import Path
import json
import numpy as np,cv2
from scipy.optimize import least_squares
from PIL import Image,ImageDraw
from render import ortho
ROOT=Path(__file__).resolve().parents[1]

def main():
    d=np.load(ROOT/'inputs/scan_cad_mm.npz');v=d['vertices'];f=d['faces'];c=d['colors'];fc=v[f].mean(1)
    ff=f[(abs(fc[:,0]+72)<20)&(abs(fc[:,1]+27)<20)&(fc[:,2]>12)&(fc[:,2]<23)]
    rgb,z,ids,b=ortho(v,ff,c,[-72,-27,300],[-72,-27,17],[0,1,0],34,850,850)
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    values=[];best=None
    for th in [110,120,130,140,150]:
        m=((gray>th)&(ids>=0)&(rgb[:,:,0].astype(float)>rgb[:,:,2]+5)).astype(np.uint8)*255
        m=cv2.morphologyEx(m,cv2.MORPH_CLOSE,np.ones((7,7),np.uint8))
        conts,_=cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
        conts=[a for a in conts if cv2.contourArea(a)>80000]
        if not conts:continue
        cnt=max(conts,key=cv2.contourArea)[:,0,:].astype(float)
        res=least_squares(lambda p:np.linalg.norm(cnt-p[:2],axis=1)-p[2],[425,425,280],loss='soft_l1',f_scale=2)
        diameter=2*res.x[2]*34/850
        values.append({'brightness_threshold':th,'circle_diameter_mm':float(diameter),'outline_radial_median_residual_mm':float(np.median(abs(res.fun))*34/850)})
        if th==130:best=(res.x,cnt)
    if best is None:raise ValueError('No stable coin contour')
    im=Image.fromarray(rgb);dr=ImageDraw.Draw(im);cx,cy,r=best[0];dr.ellipse((cx-r,cy-r,cx+r,cy+r),outline=(30,205,105),width=3)
    im.save(ROOT/'results/coin_scale_check.png')
    report={'role':'independent check, not a scale constraint','nominal_coin_diameter_mm':22.6,'nominal_source':'https://www.mint.go.jp/faq-list/faq_coin','measurement':'circle fit to textured orthographic coin boundary after CAD-based scale correction','threshold_sensitivity':values,'selected_threshold':130,'measured_diameter_mm':float(2*r*34/850),'diameter_difference_mm':float(2*r*34/850-22.6),'limitations':'Mesh/texture edge and scan smoothing; threshold spread is sensitivity, not a calibrated confidence interval.'}
    (ROOT/'results/coin_check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
