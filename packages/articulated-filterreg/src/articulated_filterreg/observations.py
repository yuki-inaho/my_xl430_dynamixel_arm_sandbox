"""Immutable RGB/depth observations and separately tracked annotation splits."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import numpy as np
import cv2
from scipy.ndimage import distance_transform_edt

@dataclass
class Observations:
    rgb:np.ndarray
    xyz:np.ndarray
    K:np.ndarray
    mask:np.ndarray
    occlusion:np.ndarray
    signed_distance:np.ndarray
    distance_gradient:np.ndarray
    target_points:np.ndarray
    train_reference:np.ndarray
    train_levels:np.ndarray
    train_pixels:np.ndarray
    train_depth:np.ndarray
    annotations:dict
    @classmethod
    def load(cls,root:Path,target_stride:int=3)->'Observations':
        with np.load(root/'model/observations.npz',allow_pickle=False) as a:
            rgb=a['rgb'];xyz=a['xyz'];K=a['K']
        mask=cv2.imread(str(root/'annotations/robot_mask.png'),cv2.IMREAD_GRAYSCALE)>0
        occ=cv2.imread(str(root/'annotations/external_occlusion.png'),cv2.IMREAD_GRAYSCALE)>0
        ann=json.loads((root/'annotations/annotations.json').read_text())
        sd=distance_transform_edt(~mask)-distance_transform_edt(mask)
        gy,gx=np.gradient(sd);grad=np.dstack((gx,gy))
        # Erode the hand mask once to avoid background-depth bleeding at uncertain edges.
        interior=cv2.erode(mask.astype(np.uint8),np.ones((3,3),np.uint8))>0
        sampling=np.zeros_like(mask);sampling[::target_stride,::target_stride]=True
        target=xyz[interior&sampling&np.isfinite(xyz).all(-1)]
        if len(target)<100:raise ValueError('too few foreground depth points')
        train=[lm for lm in ann['landmarks'] if lm['split']=='train']
        ref=np.array([lm['reference_point_m'] for lm in train]);levels=np.array([lm['level'] for lm in train],np.int32)
        pixels=np.array([lm['pixel_uv'] for lm in train]);depth=[]
        for u,v in pixels:
            x,y=round(u),round(v);patch=xyz[max(0,y-2):y+3,max(0,x-2):x+3,2]
            depth.append(float(np.nanmedian(patch)))
        return cls(rgb,xyz,K,mask,occ,sd,grad,target,ref,levels,pixels,np.array(depth),ann)
    @property
    def height(self):return self.rgb.shape[0]
    @property
    def width(self):return self.rgb.shape[1]

def sample_image(image:np.ndarray,pixels:np.ndarray)->np.ndarray:
    """Bilinear interpolation with bounded coordinates and no implicit NaN handling."""
    h,w=image.shape[:2];u=np.clip(pixels[:,0],0,w-1.000001);v=np.clip(pixels[:,1],0,h-1.000001)
    x=np.floor(u).astype(int);y=np.floor(v).astype(int);a=u-x;b=v-y
    if image.ndim==3:a=a[:,None];b=b[:,None]
    return (1-a)*(1-b)*image[y,x]+a*(1-b)*image[y,x+1]+(1-a)*b*image[y+1,x]+a*b*image[y+1,x+1]
