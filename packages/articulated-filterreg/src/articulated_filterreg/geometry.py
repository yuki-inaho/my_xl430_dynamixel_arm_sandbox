"""Camera conventions, reference-space serial kinematics, and similarity state."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

@dataclass(frozen=True)
class State:
    rotation: np.ndarray
    translation: np.ndarray
    log_scale: float
    joints: np.ndarray
    def __post_init__(self):
        R=np.array(self.rotation,dtype=float,copy=True);t=np.array(self.translation,dtype=float,copy=True);q=np.array(self.joints,dtype=float,copy=True)
        if R.shape!=(3,3) or t.shape!=(3,) or q.ndim!=1 or not all(np.isfinite(a).all() for a in (R,t,q)):
            raise ValueError('state needs finite rotation (3,3), translation (3,), and a joint vector')
        if not np.allclose(R.T@R,np.eye(3),atol=1e-8,rtol=0) or abs(np.linalg.det(R)-1)>1e-8:
            raise ValueError('state rotation must belong to SO(3)')
        if not np.isfinite(self.log_scale) or not -700<float(self.log_scale)<700:
            raise ValueError('log_scale is outside the finite numeric range')
        for name,a in [('rotation',R),('translation',t),('joints',q)]:
            a.setflags(write=False);object.__setattr__(self,name,a)
    @property
    def scale(self)->float:return float(np.exp(self.log_scale))
    def increment(self,delta:np.ndarray)->'State':
        d=np.asarray(delta,dtype=float)
        if d.shape!=(7+len(self.joints),) or not np.isfinite(d).all():raise ValueError('invalid state increment')
        r=Rotation.from_rotvec(d[:3]).as_matrix()
        return State(r@self.rotation,r@self.translation+d[3:6],self.log_scale+d[6],self.joints+d[7:])
    def to_dict(self)->dict:
        return {'rotation_camera_from_reference':self.rotation.tolist(),'translation_depth_units':self.translation.tolist(),
          'log_scale':float(self.log_scale),'scale_depth_units_per_meter':self.scale,'meters_per_depth_unit':1/self.scale,
          'joint_angles_rad':self.joints.tolist(),'joint_angles_deg':np.rad2deg(self.joints).tolist(),
          'J5':None,'J5_reason':'unobservable without downstream installed geometry'}
    @classmethod
    def from_dict(cls,v:dict)->'State':
        return cls(np.array(v['rotation_camera_from_reference']),np.array(v['translation_depth_units']),
                   float(v['log_scale']),np.array(v['joint_angles_rad']))
    @classmethod
    def from_vector(cls,x:np.ndarray)->'State':
        return cls(Rotation.from_rotvec(x[:3]).as_matrix(),np.array(x[3:6]),float(x[6]),np.array(x[7:]))
    def vector(self)->np.ndarray:
        return np.r_[Rotation.from_matrix(self.rotation).as_rotvec(),self.translation,self.log_scale,self.joints]

@dataclass(frozen=True)
class KinematicChain:
    """Pivots and axes are in the saved STEP reference frame, in meters.

    Products of exponentials avoid reapplying the STEP's already-baked zero pose.
    A body's level is the number of upstream movable joints.
    """
    pivots:np.ndarray
    axes:np.ndarray
    def __post_init__(self):
        p=np.asarray(self.pivots);a=np.asarray(self.axes)
        if p.ndim!=2 or p.shape[1]!=3 or a.shape!=p.shape or not np.isfinite(p).all() or not np.isfinite(a).all():
            raise ValueError('pivots and axes must be finite (joints,3)')
        if not np.allclose(np.linalg.norm(a,axis=1),1,atol=1e-10):raise ValueError('axes must be unit vectors')
    def fk(self,q:np.ndarray)->np.ndarray:
        q=np.asarray(q)
        if q.shape!=(len(self.pivots),) or not np.isfinite(q).all():raise ValueError('invalid joint state')
        T=np.broadcast_to(np.eye(4),(len(q)+1,4,4)).copy()
        for j,(c,a) in enumerate(zip(self.pivots,self.axes)):
            r=Rotation.from_rotvec(a*q[j]).as_matrix();g=np.eye(4);g[:3,:3]=r;g[:3,3]=c-r@c
            T[j+1]=T[j]@g
        return T
    def transforms(self,state:State)->np.ndarray:
        camera=np.eye(4);camera[:3,:3]=state.scale*state.rotation;camera[:3,3]=state.translation
        return camera@self.fk(state.joints)
    def transform(self,points:np.ndarray,levels:np.ndarray,state:State)->np.ndarray:
        p=np.asarray(points);lv=np.asarray(levels)
        if p.ndim!=2 or p.shape[1]!=3 or not np.isfinite(p).all() or lv.shape!=(len(p),) or not np.issubdtype(lv.dtype,np.integer) or (lv<0).any() or (lv>len(self.pivots)).any():
            raise ValueError('invalid point/level arrays')
        T=self.transforms(state);out=np.empty_like(p,dtype=float)
        for b,t in enumerate(T):
            ix=lv==b;out[ix]=p[ix]@t[:3,:3].T+t[:3,3]
        return out
    def space_maps(self,state:State)->np.ndarray:
        n=len(self.pivots);d=7+n;S=np.zeros((n+1,7,d));T=self.fk(state.joints)
        for b in range(n+1):
            S[b,:6,:6]=np.eye(6)
            S[b,3:6,6]=-state.translation;S[b,6,6]=1
            for j in range(b):
                axis=state.rotation@T[j,:3,:3]@self.axes[j]
                center=state.scale*state.rotation@(T[j,:3,:3]@self.pivots[j]+T[j,:3,3])+state.translation
                S[b,:3,7+j]=axis;S[b,3:6,7+j]=-np.cross(axis,center)
        return S

def projection(points:np.ndarray,K:np.ndarray)->np.ndarray:
    p=np.asarray(points)
    if p.ndim!=2 or p.shape[1]!=3 or not np.isfinite(p).all() or np.any(p[:,2]<=0):raise ValueError('finite (n,3) points must lie in front of camera')
    return np.column_stack((K[0,0]*p[:,0]/p[:,2]+K[0,2],K[1,1]*p[:,1]/p[:,2]+K[1,2]))

def projection_jacobian(points:np.ndarray,K:np.ndarray)->np.ndarray:
    p=np.asarray(points);z=p[:,2];J=np.zeros((len(p),2,3))
    J[:,0,0]=K[0,0]/z;J[:,0,2]=-K[0,0]*p[:,0]/z**2
    J[:,1,1]=K[1,1]/z;J[:,1,2]=-K[1,1]*p[:,1]/z**2
    return J

def point_jacobians(points:np.ndarray,levels:np.ndarray,space_maps:np.ndarray)->np.ndarray:
    p=np.asarray(points);A=np.zeros((len(p),3,7));x,y,z=p.T
    A[:,0,1]=z;A[:,0,2]=-y;A[:,1,0]=-z;A[:,1,2]=x;A[:,2,0]=y;A[:,2,1]=-x
    A[:,:,3:6]=np.eye(3);A[:,:,6]=p
    return np.einsum('nij,njk->nik',A,space_maps[levels])

@dataclass
class CadModel:
    vertices:np.ndarray
    faces:np.ndarray
    vertex_level:np.ndarray
    face_level:np.ndarray
    face_kind:np.ndarray
    face_unit:np.ndarray
    units:list[str]
    chain:KinematicChain
    @classmethod
    def load(cls,path:Path)->'CadModel':
        with np.load(path,allow_pickle=False) as a:
            return cls(a['vertices'],a['faces'],a['vertex_level'],a['face_level'],a['face_kind'],a['face_unit'],
                       a['units'].tolist(),KinematicChain(a['pivots'],a['axes']))
    def camera_vertices(self,state:State)->np.ndarray:
        return self.chain.transform(self.vertices,self.vertex_level,state)
