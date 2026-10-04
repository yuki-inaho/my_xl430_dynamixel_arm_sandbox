"""Common candidate ranking without access to held-out landmarks."""
from __future__ import annotations
import numpy as np
from scipy.spatial import cKDTree
from .geometry import CadModel,State,projection
from .observations import Observations
from .render import render

def evaluate(model:CadModel,obs:Observations,state:State,include_held_out:bool=False)->dict:
    depth,index,_=render(model,state,obs.K,obs.width,obs.height)
    raw=index>=0;pred=raw&~obs.occlusion;target=obs.mask&~obs.occlusion
    union=int((pred|target).sum());intersection=int((pred&target).sum());iou=intersection/max(union,1)
    v,u=np.nonzero(pred);v=v[::9];u=u[::9];z=depth[v,u]
    p=np.column_stack(((u-obs.K[0,2])*z/obs.K[0,0],(v-obs.K[1,2])*z/obs.K[1,1],z))
    if len(p)<20:return {'selection_score':1e9,'iou':iou,'status':'insufficient_model_points'}
    d1=cKDTree(obs.target_points).query(p)[0];d2=cKDTree(p).query(obs.target_points)[0]
    rmse=float(np.sqrt((np.mean(d1*d1)+np.mean(d2*d2))/2))
    trimmed=np.r_[np.sort(d1)[:max(1,int(.9*len(d1)))],np.sort(d2)[:max(1,int(.9*len(d2)))]]
    trimrmse=float(np.sqrt(np.mean(trimmed**2)))
    lp=model.chain.transform(obs.train_reference,obs.train_levels,state)
    reproj=np.linalg.norm(projection(lp,obs.K)-obs.train_pixels,axis=1)
    lm_rmse=float(np.sqrt(np.mean(reproj**2)))
    # This predetermined score uses no held-out point or encoder position.
    score=float((1-iou)+.12*trimrmse/.01+.03*lm_rmse/3)
    overlap=pred&target
    zerr=(depth[overlap]-obs.xyz[...,2][overlap])
    out={'selection_score':score,'iou':float(iou),'foreground_intersection_px':intersection,'foreground_union_px':union,
      'predicted_visible_pixels':int(pred.sum()),'observed_foreground_pixels':int(target.sum()),
      'symmetric_cloud_rmse_depth_units':rmse,'symmetric_cloud_trim90_rmse_depth_units':trimrmse,
      'symmetric_cloud_trim90_rmse_cad_equivalent_mm':1000*trimrmse/state.scale,
      'training_landmark_rmse_px':lm_rmse,'training_landmark_errors_px':reproj.tolist(),
      'overlap_depth_median_abs_error_units':float(np.median(abs(zerr))),
      'overlap_depth_rmse_units':float(np.sqrt(np.mean(zerr*zerr))),
      'scale_depth_units_per_meter':state.scale,
      'score_definition':'(1-IoU)+0.12*(trim90 symmetric point-cloud RMSE / 0.01)+0.03*(training landmark RMSE / 3)',
      'metric_warning':'CAD-equivalent mm are conditional reconstruction residuals, not independent real-world accuracy.'}
    if include_held_out:
        checks=[a for a in obs.annotations['landmarks'] if a['split']=='held_out']
        pp=np.array([a['reference_point_m'] for a in checks]);ll=np.array([a['level'] for a in checks],np.int32)
        uv=projection(model.chain.transform(pp,ll,state),obs.K)
        errors=np.linalg.norm(uv-np.array([a['pixel_uv'] for a in checks]),axis=1)
        out['held_out_landmark_median_px']=float(np.median(errors));out['held_out_landmark_rmse_px']=float(np.sqrt(np.mean(errors**2)))
        out['held_out_landmark_max_px']=float(errors.max())
        out['held_out_landmarks']=[{'name':a['name'],'annotation_uv':a['pixel_uv'],'prediction_uv':p.tolist(),'error_px':float(e)} for a,p,e in zip(checks,uv,errors)]
        out['provisional_acceptance']={'iou_threshold':.7,'held_out_median_threshold_px':8.,'passed':bool(iou>=.7 and np.median(errors)<=8)}
    return out
