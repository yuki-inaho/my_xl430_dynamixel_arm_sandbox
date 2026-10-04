"""Visible-surface articulated Gaussian registration with declared image assistance.

The E-step and block-reduced M-step are performed by the C++ core. Sparse image
landmarks and silhouette distances are explicit extensions, not hidden ICP steps.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
import time
import numpy as np
import cv2
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from .geometry import CadModel,State,projection,projection_jacobian,point_jacobians
from .observations import Observations,sample_image
from .native import GaussianMoments,assemble_blocks,BINDING
from .render import render

@dataclass(frozen=True)
class FitConfig:
    sigmas:tuple[float,...]=(.035,.023,.015,.010,.007)
    iterations_per_sigma:int=12
    source_stride:int=3
    outlier_probability:float=.1
    geometry_sigma:float=.012
    landmark_sigma_px:float=3.
    landmark_weight:float=1.5
    silhouette_sigma_px:float=3.
    silhouette_weight:float=.6
    damping:float=2e-4
    step_tolerance:float=2e-6

@dataclass
class FitResult:
    initial:State
    state:State
    trace:list[dict]
    elapsed_seconds:float
    status:str


def initialize_from_training(model:CadModel,obs:Observations)->State:
    """Similarity from first three visible joint faces; q1/q2 gauge fixed only here."""
    p=obs.train_reference[:3];pixels=obs.train_pixels[:3];z=obs.train_depth[:3]
    y=np.column_stack(((pixels[:,0]-obs.K[0,2])*z/obs.K[0,0],(pixels[:,1]-obs.K[1,2])*z/obs.K[1,1],z))
    u=p-p.mean(0);v=y-y.mean(0);U,_,Vt=np.linalg.svd(v.T@u)
    if np.linalg.det(U@Vt)<0:U[:,-1]*=-1
    R=U@Vt;s=np.sum((u@R.T)*v)/np.sum(u*u);t=y.mean(0)-s*R@p.mean(0)
    state=State(R,t,np.log(s),np.deg2rad([0,0,0,-30]))
    def residual(x):
        q=State.from_vector(x);a=model.chain.transform(obs.train_reference,obs.train_levels,q)
        if (a[:,2]<=.05).any():return np.full(17,1e5)
        return np.r_[((projection(a,obs.K)-obs.train_pixels)/2).ravel(),(a[:,2]-obs.train_depth)/.015,x[7:9]/.015]
    r=least_squares(residual,state.vector(),max_nfev=150,xtol=1e-11,ftol=1e-11,gtol=1e-11,
                    bounds=(np.r_[[-np.inf]*6,np.log(.3),[-np.pi]*4],np.r_[[np.inf]*6,np.log(6.),[np.pi]*4]))
    return State.from_vector(r.x)


def perturb(state:State,rng:np.random.Generator,index:int)->State:
    if index==0:return state
    spread=1. if index%6 else 1.8
    rotation=Rotation.from_rotvec(rng.normal(0,np.deg2rad(5)*spread,3)).as_matrix()@state.rotation
    translation=state.translation+rng.normal(0,.009*spread,3)
    joints=state.joints+rng.normal(0,np.deg2rad(8)*spread,4)
    scale=state.log_scale+rng.normal(0,.07*spread)
    return State(rotation,translation,scale,joints)


def _reference_from_camera(model:CadModel,p:np.ndarray,body:np.ndarray,state:State)->np.ndarray:
    transforms=model.chain.transforms(state);out=np.empty_like(p)
    for b,T in enumerate(transforms):
        ix=body==b
        out[ix]=(p[ix]-T[:3,3])@np.linalg.inv(T[:3,:3]).T
    return out


def _surface(model:CadModel,obs:Observations,state:State,stride:int):
    depth,idx,_=render(model,state,obs.K,obs.width,obs.height)
    raw=idx>=0;visible=raw&~obs.occlusion
    sparse=np.zeros_like(visible);sparse[::stride,::stride]=True
    v,u=np.nonzero(visible&sparse)
    if len(v)<100:raise RuntimeError('fewer than 100 visible model samples')
    z=depth[v,u];p=np.column_stack(((u-obs.K[0,2])*z/obs.K[0,0],(v-obs.K[1,2])*z/obs.K[1,1],z))
    body=model.face_level[idx[v,u]]
    # Only true model boundaries: do not optimize artificial cuts along fabric/tape.
    boundary=raw & ~(cv2.erode(raw.astype(np.uint8),np.ones((3,3),np.uint8))>0)
    safe=cv2.erode((~obs.occlusion).astype(np.uint8),np.ones((5,5),np.uint8))>0
    boundary&=safe;boundary[[0,1,-2,-1],:]=False;boundary[:,[0,1,-2,-1]]=False
    vv,uu=np.nonzero(boundary);vv=vv[::2];uu=uu[::2]
    zz=depth[vv,uu]
    bp=np.column_stack(((uu-obs.K[0,2])*zz/obs.K[0,0],(vv-obs.K[1,2])*zz/obs.K[1,1],zz))
    bl=model.face_level[idx[vv,uu]]
    return p,body,bp,bl,raw


def _image_terms(model:CadModel,obs:Observations,state:State,bp:np.ndarray,bl:np.ndarray,config:FitConfig):
    maps=model.chain.space_maps(state);d=maps.shape[2];H=np.zeros((d,d));g=np.zeros(d)
    lp=model.chain.transform(obs.train_reference,obs.train_levels,state)
    uv=projection(lp,obs.K);r=(uv-obs.train_pixels).ravel()
    J=np.einsum('nij,njk->nik',projection_jacobian(lp,obs.K),point_jacobians(lp,obs.train_levels,maps)).reshape(-1,d)
    fac=config.landmark_weight/(len(lp)*config.landmark_sigma_px**2)
    H+=fac*J.T@J;g-=fac*J.T@r
    if len(bp):
        buv=projection(bp,obs.K);res=sample_image(obs.signed_distance,buv)
        grad=sample_image(obs.distance_gradient,buv)
        jb=np.einsum('nij,njk->nik',projection_jacobian(bp,obs.K),point_jacobians(bp,bl,maps))
        js=np.einsum('ni,nij->nj',grad,jb)
        robust=np.minimum(1.,6./np.maximum(np.abs(res),1e-10))
        fac=config.silhouette_weight/(len(bp)*config.silhouette_sigma_px**2)
        H+=fac*js.T@(robust[:,None]*js);g-=fac*js.T@(robust*res)
    return H,g


def _frozen_cost(model:CadModel,obs:Observations,state:State,reference,body,mu,w,bref,bl,config):
    p=model.chain.transform(reference,body,state)
    if not np.isfinite(p).all() or (p[:,2]<.08).any() or state.scale<.3 or state.scale>6 or (abs(state.joints)>np.pi).any():return np.inf
    data=np.sum(w*np.sum((p-mu)**2,axis=1))/(max(w.sum(),1e-20)*config.geometry_sigma**2)
    lp=model.chain.transform(obs.train_reference,obs.train_levels,state)
    if (lp[:,2]<=0).any():return np.inf
    land=config.landmark_weight*np.mean(np.sum((projection(lp,obs.K)-obs.train_pixels)**2,axis=1))/config.landmark_sigma_px**2
    bp=model.chain.transform(bref,bl,state)
    sil=0.
    if len(bp):
        if (bp[:,2]<=0).any():return np.inf
        r=np.abs(sample_image(obs.signed_distance,projection(bp,obs.K)))
        huber=np.where(r<=6,r*r,12*r-36)
        sil=config.silhouette_weight*np.mean(huber)/config.silhouette_sigma_px**2
    return float(data+land+sil)


def fit(model:CadModel,obs:Observations,initial:State,config:FitConfig)->FitResult:
    state=initial;trace=[];start=time.monotonic();status='completed'
    try:
        for stage,sigma in enumerate(config.sigmas):
            with GaussianMoments(obs.target_points,sigma) as gaussian:
                for iteration in range(config.iterations_per_sigma):
                    p,body,bp,bl,raw=_surface(model,obs,state,config.source_stride)
                    moment=gaussian.evaluate(p);mass=moment[:,0]
                    usable=mass>1e-10
                    if usable.sum()<50:raise RuntimeError('Gaussian overlap too small')
                    p=p[usable];body=body[usable];moment=moment[usable];mass=mass[usable]
                    mu=moment[:,1:4]/mass[:,None]
                    w0=config.outlier_probability
                    c=(2*np.pi*sigma*sigma)**1.5*w0/(1-w0)*len(obs.target_points)/len(p)
                    weights=mass/(mass+c)
                    maps=model.chain.space_maps(state)
                    H,g=assemble_blocks(p,mu,weights,body,maps)
                    fac=1/(weights.sum()*config.geometry_sigma**2);H*=fac;g*=fac
                    ih,ig=_image_terms(model,obs,state,bp,bl,config);H+=ih;g+=ig
                    regularizer=config.damping*np.maximum(np.diag(H),1.)
                    delta=np.linalg.solve(H+np.diag(regularizer),g)
                    # Clip the complete increment, preserving rotation/translation coupling.
                    origin_motion=delta[3:6]+np.cross(delta[:3],state.translation)
                    ratio=max(1.,np.linalg.norm(delta[:3])/.13,np.linalg.norm(origin_motion)/.03,
                              abs(delta[6])/.08,float(np.max(abs(delta[7:])))/.2)
                    delta/=ratio
                    reference=_reference_from_camera(model,p,body,state)
                    bref=_reference_from_camera(model,bp,bl,state)
                    old=_frozen_cost(model,obs,state,reference,body,mu,weights,bref,bl,config)
                    factor=1.;candidate=state;new=old;accepted=False
                    for _ in range(8):
                        proposed=state.increment(delta*factor)
                        value=_frozen_cost(model,obs,proposed,reference,body,mu,weights,bref,bl,config)
                        if value<old:
                            candidate=proposed;new=value;accepted=True;break
                        factor*=.5
                    state=candidate
                    trace.append({'stage':stage,'sigma':sigma,'iteration':iteration,'gaussian_queries':len(p),
                      'boundary_points':len(bp),'mean_mass':float(mass.mean()),'frozen_cost_before':old,'frozen_cost_after':new,
                      'accepted':accepted,'step_factor':factor,'increment_norm':float(np.linalg.norm(delta*factor)),
                      'scale':state.scale,'joints_rad':state.joints.tolist(),'binding':BINDING})
                    if accepted and np.linalg.norm(delta*factor)<config.step_tolerance:break
    except (ValueError,RuntimeError,np.linalg.LinAlgError) as error:
        status=f'failed: {error}'
    return FitResult(initial,state,trace,time.monotonic()-start,status)
