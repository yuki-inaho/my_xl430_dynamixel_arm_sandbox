"""Fit simple exterior envelopes to calibrated GLB samples (millimetres)."""
from pathlib import Path
import json
import numpy as np
from scipy.optimize import least_squares
ROOT=Path(__file__).resolve().parents[1]

def cot_residual(p, points, z0):
    cx,cy,rx0,ry0,rxj,ryj,zj,zt,tx,ty,yaw=p
    z=points[:,2];h=z-z0
    xy=points[:,:2]-[cx,cy]-h[:,None]*[tx,ty]
    co,si=np.cos(yaw),np.sin(yaw)
    u=xy[:,0]*co+xy[:,1]*si;v=-xy[:,0]*si+xy[:,1]*co
    a=np.clip(h/(zj-z0),0,1);rx=rx0+(rxj-rx0)*a;ry=ry0+(ryj-ry0)*a
    f=(u/rx)**2+(v/ry)**2-1
    g=2*np.sqrt((u/rx**2)**2+(v/ry**2)**2)+1e-8
    dc=f/g
    H=zt-zj;hh=z-zj
    fe=(u/rxj)**2+(v/ryj)**2+(hh/H)**2-1
    ge=2*np.sqrt((u/rxj**2)**2+(v/ryj**2)**2+(hh/H**2)**2)+1e-8
    dc[z>zj]=(fe/ge)[z>zj]
    return dc

def voxel(points,spacing=.65):
    _,ids=np.unique(np.floor(points/spacing).astype(int),axis=0,return_index=True)
    return points[np.sort(ids)]

def main():
    d=np.load(ROOT/'inputs/scan_cad_mm.npz');v=d['vertices'];c=d['colors'][:,:3].astype(float)
    b=(c[:,2]>c[:,0]*1.08)&(c[:,2]>c[:,1]*.99)&(c[:,1]>c[:,0]*1.015)
    orange=(c[:,0]>110)&(c[:,0]>c[:,1]*1.18)&(c[:,1]>c[:,2]*1.20)
    dark=(c.max(axis=1)<120)&(~b)&(~orange)
    params={'units':'mm','components':{},'notes':[
        'Six exterior-occupancy components; finger cots are solid envelopes, not measured wall thickness.',
        'Left/right labels refer to provided photograph. Geometry is not forced symmetric.',
        'No hidden internal core or unconfirmed separate contact pads are invented.',
        'Color thresholds plus explicit spatial regions constitute manual-assisted annotation, not SAM/BiRefNet inference.'
    ]}
    all_labels=np.zeros(len(v),np.uint8)
    selections={}
    for side,xlo,xhi,z0 in [('L',-35,-12,61.7),('R',5,29,62.2)]:
        roi=(v[:,0]>xlo)&(v[:,0]<xhi)&(abs(v[:,1]+2)<14)&(v[:,2]>z0-.5)&(v[:,2]<90)
        mask=roi&(b| (v[:,2]>65.5))
        pts=voxel(v[mask]);print(side,'cot points',len(pts))
        cx=-23 if side=='L' else 17;cy=-2.5
        start=np.array([cx,cy,9,9,8,8,78,87.5,.04 if side=='L' else -.10,.05,0.])
        lo=[cx-4,cy-4,6,6,5.5,5.5,72,85.5,-.4,-.4,-1.5707]
        hi=[cx+4,cy+4,12.5,12.5,10.5,10.5,82,90,.4,.4,1.5707]
        rng=np.random.default_rng(20261004)
        best=None;trials=[]
        for k in range(12):
            x0=start if k==0 else np.clip(start+rng.normal(0,1,len(start))*[1,1,.8,.8,.8,.8,1,.4,.05,.05,.2],np.array(lo)+1e-5,np.array(hi)-1e-5)
            res=least_squares(cot_residual,x0,args=(pts,z0),bounds=(lo,hi),loss='soft_l1',f_scale=.7,max_nfev=500)
            cost=float(np.mean(np.sqrt(cot_residual(res.x,pts,z0)**2+.7**2)-.7))
            trials.append({'start':k,'cost':cost,'success':bool(res.success),'nfev':res.nfev})
            if best is None or cost<best[0]:best=(cost,res.x)
        p=best[1];r=cot_residual(p,pts,z0)
        values=dict(zip(['cx0','cy0','rx_base','ry_base','rx_shoulder','ry_shoulder','z_shoulder','z_tip','tilt_x_per_z','tilt_y_per_z','yaw_rad'],p.tolist()))
        values.update({'z_base':z0,'fit_points':len(pts),'fit_abs_residual_median_mm':float(np.median(abs(r))),'fit_abs_residual_p95_mm':float(np.percentile(abs(r),95)),'trials':trials})
        params['components']['cot_'+side]=values
        all_labels[mask]=1 if side=='L' else 2;selections['cot_'+side]=np.flatnonzero(mask)
        # Foam geometry is summarized by observed cross-section envelopes.
        maskf=(v[:,0]>(-43 if side=='L' else 5))&(v[:,0]<(-12 if side=='L' else 35))&(abs(v[:,1])<19)&(v[:,2]>40)&(v[:,2]<z0+.6)&dark
        sections=[]
        for zl,zh in [(40,43),(43,47),(47,50),(50,53),(53,57),(57,z0)]:
            pp=v[maskf&(v[:,2]>zl)&(v[:,2]<=zh)]
            sections.append({'z':(zl+zh)/2,'count':len(pp),'xy_q03_q97':np.percentile(pp[:,:2],[3,97],axis=0).tolist() if len(pp)>5 else None})
        params['components']['foam_'+side]={'source_sections':sections,'approximation':'stepped rounded rectangular envelope; fitted from these sections'}
        all_labels[maskf]=3 if side=='L' else 4;selections['foam_'+side]=np.flatnonzero(maskf)
        masko=orange&(v[:,0]>(-43 if side=='L' else 4))&(v[:,0]<(-12 if side=='L' else 36))&(abs(v[:,1])<23)&(v[:,2]>33)&(v[:,2]<45.5)
        pp=v[masko];
        params['components']['band_'+side]={'source_points':len(pp),'bounds_q03_q97':np.percentile(pp,[3,97],axis=0).tolist()}
        all_labels[masko]=5 if side=='L' else 6;selections['band_'+side]=np.flatnonzero(masko)
    (ROOT/'results/parameters_initial.json').write_text(json.dumps(params,indent=2))
    np.savez_compressed(ROOT/'annotations/selected_vertex_ids.npz',**selections,labels=all_labels)
    print(json.dumps(params,indent=2))
if __name__=='__main__':main()
