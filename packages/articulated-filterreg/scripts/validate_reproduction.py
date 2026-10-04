"""Replay the selected initialization, then perform clearly separated sensitivities."""
from pathlib import Path
from dataclasses import replace
import json,time,sys,platform,subprocess,importlib.metadata
import numpy as np
import cv2
from articulated_filterreg.geometry import CadModel,State
from articulated_filterreg.observations import Observations
from articulated_filterreg.optimize import FitConfig,fit,initialize_from_training
from articulated_filterreg.evaluate import evaluate
from articulated_filterreg.native import GaussianMoments
ROOT=Path(__file__).resolve().parents[1]

def main():
    m=CadModel.load(ROOT/'model/bare_arm.npz');o=Observations.load(ROOT)
    best=json.loads((ROOT/'results/best.json').read_text());run=json.loads((ROOT/'results/run_manifest.json').read_text())
    config=FitConfig(**run['configuration'])
    original=State.from_dict(best['final']);initial=State.from_dict(best['initial'])
    replay=fit(m,o,initial,config)
    maximum=float(np.max(abs(replay.state.vector()-original.vector())))
    score=evaluate(m,o,replay.state)['selection_score']
    score_difference=abs(score-best['final_metrics']['selection_score'])
    result={'binding':'ctypes','best_trial_id':best['id'],'replay_status':replay.status,
        'max_abs_state_parameter_difference':maximum,'selection_score_difference':score_difference,
        'passed':bool(replay.status=='completed' and maximum<1e-9 and score_difference<1e-10)}
    (ROOT/'results/reproducibility.json').write_text(json.dumps(result,indent=2))
    assert result['passed'],result
    sensitivities={}
    audit=json.loads((ROOT/'docs/input_audit.json').read_text());native=audit['exr_fitted_intrinsics']
    K=np.array([[native['fx'],0,native['cx']],[0,native['fy'],native['cy']],[0,0,1.]])
    v,u=np.indices(o.mask.shape);z=o.xyz[...,2]
    xyz=np.dstack(((u-K[0,2])*z/K[0,0],(v-K[1,2])*z/K[1,1],z))
    interior=cv2.erode(o.mask.astype(np.uint8),np.ones((3,3),np.uint8))>0
    sample=np.zeros_like(interior);sample[::3,::3]=True
    alt=replace(o,K=K,xyz=xyz,target_points=xyz[interior&sample])
    other=fit(m,alt,initialize_from_training(m,alt),config)
    sensitivities['EXR_intrinsics_single_start']={'camera_K':K.tolist(),'state':other.state.to_dict(),'metrics':evaluate(m,alt,other.state),
        'note':'Separate single-start sensitivity; not mixed into primary 32-run selection.'}
    data_only_config=replace(config,landmark_weight=0.,silhouette_weight=0.)
    data_only=fit(m,o,initialize_from_training(m,o),data_only_config)
    sensitivities['Gaussian_only_single_start']={'state':data_only.state.to_dict(),'metrics':evaluate(m,o,data_only.state),
        'status':data_only.status,'configuration':{'landmark_weight':0.,'silhouette_weight':0.},
        'note':'Same articulated Gaussian/block core with image terms disabled; initialized from the same five training landmarks. Not a fully annotation-free run.'}
    (ROOT/'results/sensitivity.json').write_text(json.dumps(sensitivities,ensure_ascii=False,indent=2))
    rng=np.random.default_rng(133);y=rng.normal(0,.025,(700,3))+[.1,.2,.6];x=rng.normal(0,.018,(150,3))+[.1,.2,.6]
    sigma=.012
    with GaussianMoments(y,sigma,'direct') as exact,GaussianMoments(y,sigma,'lattice') as lattice:
        a=exact.evaluate(x);b=lattice.evaluate(x)
    good=(a[:,0]>1e-9)&(b[:,0]>1e-9);ea=a[good,1:4]/a[good,0,None];eb=b[good,1:4]/b[good,0,None]
    errors=np.linalg.norm(ea-eb,axis=1)
    gauss={'sigma':sigma,'observations':len(y),'queries':len(x),'valid_queries':int(good.sum()),
       'lattice_vs_exact_centroid_median_error':float(np.median(errors)),
       'lattice_vs_exact_centroid_p95_error':float(np.quantile(errors,.95)),
       'note':'No-blur permutohedral is an approximation, not exactly equal to the Gaussian oracle; recorded without treating density gains as exact.'}
    (ROOT/'results/gaussian_approximation.json').write_text(json.dumps(gauss,indent=2))
    env={'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'machine':platform.machine(),'binding_used':'ctypes',
         'nanobind_build_verified':False,'fresh_uv_sync_verified':False,'versions':{}}
    for package in ['numpy','scipy','opencv-python','opencv-python-headless','trimesh','numba','pillow','pytest','cadquery']:
        try:env['versions'][package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:pass
    for command in [['uv','--version'],['cmake','--version'],['g++','--version']]:
        env[command[0]]=subprocess.check_output(command,text=True).splitlines()[0]
    (ROOT/'docs/environment.json').write_text(json.dumps(env,ensure_ascii=False,indent=2))
    print(json.dumps({'reproduction':result,'gaussian_approximation':gauss,'sensitivity_summary':{
       key:{'scale':value['state']['scale_depth_units_per_meter'],'iou':value['metrics']['iou'],
            'train_rmse':value['metrics']['training_landmark_rmse_px']} for key,value in sensitivities.items()}},indent=2))
if __name__=='__main__':main()
