"""Deterministic triangle rasterizer. No generative image synthesis."""
from pathlib import Path
import numpy as np
from numba import njit
from PIL import Image

@njit(cache=True)
def raster(p, faces, colors, width, height, perspective=False):
    zbuf=np.full((height,width), np.inf)
    rgb=np.full((height,width,3),245.,np.float64)
    ids=np.full((height,width), -1,np.int32)
    bary=np.zeros((height,width,3),np.float32)
    for i in range(len(faces)):
        ia,ib,ic=faces[i]
        a,b,c=p[ia],p[ib],p[ic]
        if min(a[2],b[2],c[2])<=0: continue
        x0=max(0,int(np.floor(min(a[0],b[0],c[0]))));x1=min(width-1,int(np.ceil(max(a[0],b[0],c[0]))))
        y0=max(0,int(np.floor(min(a[1],b[1],c[1]))));y1=min(height-1,int(np.ceil(max(a[1],b[1],c[1]))))
        den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den)<1e-10: continue
        for y in range(y0,y1+1):
          for x in range(x0,x1+1):
            wa=((b[1]-c[1])*(x+.5-c[0])+(c[0]-b[0])*(y+.5-c[1]))/den
            wb=((c[1]-a[1])*(x+.5-c[0])+(a[0]-c[0])*(y+.5-c[1]))/den
            wc=1-wa-wb
            if wa>=-1e-6 and wb>=-1e-6 and wc>=-1e-6:
                if perspective:
                    denom=wa/a[2]+wb/b[2]+wc/c[2]
                    z=1/denom
                    wa=wa/a[2]/denom;wb=wb/b[2]/denom;wc=wc/c[2]/denom
                else:
                    z=wa*a[2]+wb*b[2]+wc*c[2]
                if z<zbuf[y,x]:
                    zbuf[y,x]=z; ids[y,x]=i
                    bary[y,x,0]=wa;bary[y,x,1]=wb;bary[y,x,2]=wc
                    for k in range(3): rgb[y,x,k]=wa*colors[ia,k]+wb*colors[ib,k]+wc*colors[ic,k]
    return np.minimum(255,np.maximum(0,rgb)).astype(np.uint8),zbuf,ids,bary

def camera(eye,target,up):
    eye,target,up=map(lambda x:np.array(x,dtype=float),(eye,target,up))
    f=target-eye;f/=np.linalg.norm(f)
    r=np.cross(f,up);r/=np.linalg.norm(r)
    d=np.cross(f,r)
    return np.stack([r,d,f]),eye

def ortho(vertices,faces,colors,eye,target,up,span,width=1200,height=1200,out=None):
    R,t=camera(eye,target,up)
    pc=(vertices-t)@R.T
    q=pc.copy();q[:,:2]*=width/span;q[:,0]+=width/2;q[:,1]+=height/2
    rgb,z,ids,b=raster(q,np.asarray(faces,np.int64),np.array(colors[:,:3],dtype=float),width,height)
    if out:
        Image.fromarray(rgb).save(str(out)+'.png')
        np.savez_compressed(str(out)+'.npz',ids=ids,bary=b,R=R,eye=t,span=span,width=width,height=height)
    return rgb,z,ids,b

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    d=np.load(root/'inputs/scan_raw.npz');v=d['vertices'];f=d['faces'];c=d['colors']
    mask=(v[f].mean(axis=1)[:,1]>.015)
    ortho(v,f[mask],c,[0,.8,0],[0,.03,0],[0,0,-1],.42,out=root/'annotations/scan_top')
    ortho(v,f[mask],c,[0,.55,.6],[0,.06,0],[0,1,0],.4,out=root/'annotations/scan_oblique')
    np.save(root/'inputs/scan_faces_crop.npy',f[mask])
