"""Reproducible command-line entry point; all artifacts are written under --root."""
from __future__ import annotations
import argparse,csv,json,os,sys,time,hashlib
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo


def _write_json(path:Path,value)->None:
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False))
    temporary.replace(path)


def run_fit(root:Path,starts:int,seed:int,binding:str,iterations:int,resume:bool=False)->None:
    import numpy as np
    from dataclasses import asdict
    from .geometry import CadModel
    from .observations import Observations
    from .optimize import FitConfig,initialize_from_training,perturb,fit
    from .evaluate import evaluate
    from .native import BINDING
    if starts<1 or starts>10000:raise ValueError('starts must be in [1,10000]')
    model=CadModel.load(root/'model/bare_arm.npz');obs=Observations.load(root)
    initialized=initialize_from_training(model,obs)
    config=FitConfig(iterations_per_sigma=iterations)
    resultdir=root/'results';trials=resultdir/'trials';trials.mkdir(parents=True,exist_ok=True)
    manifest={'start_time':datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds'),
      'seed':seed,'starts':starts,'binding':BINDING,'configuration':asdict(config),
      'annotation_sha256':hashlib.sha256((root/'annotations/annotations.json').read_bytes()).hexdigest(),
      'model_sha256':hashlib.sha256((root/'model/bare_arm.npz').read_bytes()).hexdigest(),
      'target_point_count':len(obs.target_points),'camera_K':obs.K.tolist(),
      'initialized_state':initialized.to_dict(),'initialized_metrics':evaluate(model,obs,initialized),
      'held_out_policy':'No held-out landmarks used for initialization, optimization or ranking.'}
    manifest_path=resultdir/'run_manifest.json'
    if resume and manifest_path.exists():
        previous=json.loads(manifest_path.read_text())
        for key in ('seed','starts','binding','configuration','annotation_sha256','model_sha256'):
            # JSON round-trip normalizes tuple-valued configuration fields.
            if json.loads(json.dumps(previous[key]))!=json.loads(json.dumps(manifest[key])):
                raise ValueError(f'resume manifest mismatch: {key}')
        previous.setdefault('resume_times',[]).append(manifest['start_time'])
        manifest=previous
    _write_json(manifest_path,manifest)
    candidates=[];overall=time.monotonic()
    for index in range(starts):
        existing=trials/f'trial_{index:03}.json'
        if resume and existing.exists():
            record=json.loads(existing.read_text())
            if record.get('seed_entropy')!=[seed,index]:raise ValueError('resume seed mismatch')
            candidates.append(record)
            print(f'trial {index:03} resumed from saved record',flush=True)
            continue
        rng=np.random.default_rng(np.random.SeedSequence([seed,index]))
        initial=perturb(initialized,rng,index)
        try:
            initial_metrics=evaluate(model,obs,initial)
            fitresult=fit(model,obs,initial,config)
            metrics=evaluate(model,obs,fitresult.state)
            record={'id':index,'seed_entropy':[seed,index],'status':fitresult.status,'elapsed_seconds':fitresult.elapsed_seconds,
              'initial':initial.to_dict(),'final':fitresult.state.to_dict(),'initial_metrics':initial_metrics,'final_metrics':metrics,
              'iteration_count':len(fitresult.trace),'trace':fitresult.trace}
        except Exception as error:
            record={'id':index,'seed_entropy':[seed,index],'status':f'failed: {type(error).__name__}: {error}',
              'initial':initial.to_dict(),'final_metrics':{'selection_score':1e9},'trace':[]}
        _write_json(trials/f'trial_{index:03}.json',record)
        candidates.append(record)
        print(f"trial {index:03} {record['status']} score={record['final_metrics']['selection_score']:.7f} "
              f"IoU={record['final_metrics'].get('iou',0):.5f} seconds={record.get('elapsed_seconds',0):.2f}",flush=True)
    eligible=[r for r in candidates if r['status']=='completed' and r['trace'] and np.isfinite(r['final_metrics']['selection_score'])]
    if not eligible:raise RuntimeError('all initializations failed; inspect results/trials')
    winner=min(eligible,key=lambda r:r['final_metrics']['selection_score'])
    summary={**winner};summary.pop('trace',None)
    summary['selection_scope']=f'minimum predefined score among {len(eligible)} completed runs, not a proof of global optimality'
    summary['elapsed_this_invocation_seconds']=time.monotonic()-overall
    _write_json(resultdir/'best.json',summary)
    fields=['id','status','initial_score','final_score','initial_iou','final_iou','trim90_rmse','train_rmse_px','scale','q1_deg','q2_deg','q3_deg','q4_deg','iterations','seconds']
    with (resultdir/'all_trials.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for r in candidates:
            a=r.get('initial_metrics',{});b=r['final_metrics'];final=r.get('final',{});q=final.get('joint_angles_deg',[None]*4)
            writer.writerow(dict(zip(fields,[r['id'],r['status'],a.get('selection_score'),b.get('selection_score'),a.get('iou'),b.get('iou'),
                b.get('symmetric_cloud_trim90_rmse_depth_units'),b.get('training_landmark_rmse_px'),final.get('scale_depth_units_per_meter'),
                *q,r.get('iteration_count'),r.get('elapsed_seconds')])))
    near=[r for r in eligible if r['final_metrics']['selection_score']<=winner['final_metrics']['selection_score']*1.05]
    qs=np.array([r['final']['joint_angles_deg'] for r in near]);scales=np.array([r['final']['scale_depth_units_per_meter'] for r in near])
    _write_json(resultdir/'initialization_stability.json',{'criterion':'within 5% of best selection score','count':len(near),
      'run_ids':[r['id'] for r in near],'scale_range':[float(scales.min()),float(scales.max())],
      'joint_angle_ranges_deg':np.column_stack((qs.min(0),qs.max(0))).tolist(),
      'warning':'Empirical spread across initializations only; not a calibrated confidence interval or physical ground truth.'})
    print('BEST',winner['id'],winner['final_metrics'],flush=True)
    print('TOTAL_SECONDS',time.monotonic()-overall,flush=True)


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['fit','render'])
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--binding',choices=['nanobind','ctypes'],default='nanobind')
    parser.add_argument('--starts',type=int,default=32)
    parser.add_argument('--seed',type=int,default=20261004)
    parser.add_argument('--iterations',type=int,default=14)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();os.environ['AF_BINDING']=args.binding
    if args.command=='fit':run_fit(args.root.resolve(),args.starts,args.seed,args.binding,args.iterations,args.resume)
    else:
        from .reporting import write_visual_results
        write_visual_results(args.root.resolve())

if __name__=='__main__':main()
