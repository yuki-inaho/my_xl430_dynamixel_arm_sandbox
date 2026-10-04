"""Deterministic perspective-correct triangle rasterizer; no learned imagery."""
from __future__ import annotations
import numpy as np
from numba import njit
from .geometry import CadModel,State

@njit(cache=True)
def rasterize(vertices,faces,K,width,height):
    depth=np.full((height,width),np.inf)
    index=np.full((height,width),-1,np.int32)
    uv=np.empty((len(vertices),2))
    for i in range(len(vertices)):
        z=vertices[i,2]
        if z<=1e-8:uv[i,0]=-1e8;uv[i,1]=-1e8
        else:
            uv[i,0]=K[0,0]*vertices[i,0]/z+K[0,2]
            uv[i,1]=K[1,1]*vertices[i,1]/z+K[1,2]
    for f in range(len(faces)):
        i0,i1,i2=faces[f]
        z0,z1,z2=vertices[i0,2],vertices[i1,2],vertices[i2,2]
        if min(z0,z1,z2)<=1e-8:continue
        x0,y0=uv[i0];x1,y1=uv[i1];x2,y2=uv[i2]
        den=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
        if abs(den)<1e-10:continue
        xmin=max(0,int(np.ceil(min(x0,x1,x2))));xmax=min(width-1,int(np.floor(max(x0,x1,x2))))
        ymin=max(0,int(np.ceil(min(y0,y1,y2))));ymax=min(height-1,int(np.floor(max(y0,y1,y2))))
        if xmin>xmax or ymin>ymax:continue
        for y in range(ymin,ymax+1):
            for x in range(xmin,xmax+1):
                a=((y1-y2)*(x-x2)+(x2-x1)*(y-y2))/den
                b=((y2-y0)*(x-x2)+(x0-x2)*(y-y2))/den
                c=1-a-b
                if min(a,b,c)<-1e-9:continue
                z=1/(a/z0+b/z1+c/z2)
                if z<depth[y,x]:depth[y,x]=z;index[y,x]=f
    return depth,index

def render(model:CadModel,state:State,K:np.ndarray,width:int,height:int):
    vertices=model.camera_vertices(state)
    depth,index=rasterize(vertices,model.faces,K,width,height)
    return depth,index,vertices

def shaded_image(model:CadModel,vertices:np.ndarray,index:np.ndarray)->np.ndarray:
    triangles=vertices[model.faces]
    normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    n=np.linalg.norm(normals,axis=1);normals/=np.maximum(n[:,None],1e-15)
    light=np.array([-.3,-.5,-1.]);light/=np.linalg.norm(light)
    shade=.55+.45*np.abs(normals@light)
    color=np.where(model.face_kind[:,None]==1,np.array([230.,238.,242.]),np.array([43.,48.,56.]))
    color=np.clip(color*shade[:,None],0,255).astype(np.uint8)
    out=np.full((*index.shape,3),248,np.uint8);valid=index>=0;out[valid]=color[index[valid]]
    return out
