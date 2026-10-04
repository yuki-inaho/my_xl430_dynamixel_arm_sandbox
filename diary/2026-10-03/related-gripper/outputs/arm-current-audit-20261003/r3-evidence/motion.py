"""Finite-pose exact B-rep checks, with reusable relative-transform cache.

Not a continuous configuration-space proof. Never label a finite grid 'full ROM'.
Supplier-internal geometry remains grouped, but every different physical unit is
checked, including units on the same rigid link. Mounting bolts/cables absent in
this stage are explicitly reported.
"""
import json,math,itertools,time,sys
from pathlib import Path
import numpy as np
import cadquery as cq
from OCP.gp import gp_Trsf,gp_Ax1,gp_Pnt,gp_Dir
from check import ROOT,load,common_volume,TOL
from assembly_io import bounds

def rotation(joint,angle):
    t=gp_Trsf();t.SetRotation(gp_Ax1(gp_Pnt(*joint['centre_mm']),gp_Dir(*joint['axis'])),math.radians(angle));return cq.Location(t)
def matrix(loc):
    t=loc.wrapped.Transformation();return np.array([[t.Value(i+1,j+1) for j in range(4)] for i in range(3)])
def transformed_box(bb,loc):
    pts=np.array(list(itertools.product(*[(bb[k],bb[k+3]) for k in range(3)])))
    m=matrix(loc);v=pts@m[:,:3].T+m[:,3];return np.r_[v.min(0),v.max(0)]

class Checker:
    def __init__(self):
        rows,self.meta=load();self.joints=json.loads((ROOT/'reports/joints.json').read_text())
        groups={};self.level={};self.shapes={};self.boxes={};self.cache={};self.boolean_count=0
        for r in rows:
            m=self.meta[r.name];name=m['physical_unit'];self.level[name]=m['level']
            for s in r.world.Solids():groups.setdefault(name,[]).append(s)
        for name,solids in groups.items():
            self.shapes[name]=cq.Compound.makeCompound(solids);self.boxes[name]=bounds(self.shapes[name])
        self.pairs=[]
        for a,b in itertools.combinations(self.shapes,2):
            if self.level[a]>self.level[b]:a,b=b,a
            self.pairs.append((a,b))
    def pose(self,q):
        bad=[]
        for a,b in self.pairs:
            lo,hi=self.level[a],self.level[b];angles=tuple(round(float(v),6) for v in q[lo:hi]);key=(a,b,angles)
            if key not in self.cache:
                relative=cq.Location()
                for j in range(lo,hi):relative=relative*rotation(self.joints[j],q[j])
                ba=np.array(self.boxes[a]);bb=transformed_box(self.boxes[b],relative)
                if np.any(np.minimum(ba[3:],bb[3:])-np.maximum(ba[:3],bb[:3])<=1e-7):self.cache[key]=0.
                else:
                    self.boolean_count+=1
                    try:self.cache[key]=common_volume(self.shapes[a],self.shapes[b].moved(relative))
                    except Exception as e:self.cache[key]={'error':str(e)}
            v=self.cache[key]
            if isinstance(v,dict) or v>TOL:bad.append({'a':a,'b':b,**(v if isinstance(v,dict) else {'volume_mm3':v})})
        return bad

def main(mode='screen'):
    start=time.monotonic();checker=Checker()
    ranges=[(-180,180),(-40,40),(-60,60),(-60,60),(-90,90),(0,50)]
    step=10 if mode=='screen' else 5
    poses=[('home',[0.]*6)]
    for j,(a,b) in enumerate(ranges):
        for v in np.arange(a,b+step*.1,step):
            q=[0.]*6;q[j]=float(v);poses.append((f'axis_J{j+1}',q))
    if mode!='screen':
        for p in itertools.product([-40,-20,0,20,40],[-60,-30,0,30,60],[-60,-30,0,30,60],[-90,0,90],[0,25,50]):poses.append(('combined_grid',[0,*p]))
    result=[]
    for i,(family,q) in enumerate(poses):
        bad=checker.pose(q);result.append({'family':family,'q_deg':q,'passed':not bad,'collisions':bad})
        if i%10==0:print(i,'/',len(poses),'bad',sum(not r['passed'] for r in result),'booleans',checker.boolean_count,flush=True)
        if bad:print('COLLISION',q,bad,flush=True)
        # Save progress as NOT COMPLETE to avoid promoting an interrupted run.
        if i%25==0:(ROOT/f'reports/motion_{mode}_progress.json').write_text(json.dumps({'complete':False,'poses':result},indent=2))
    report={'complete':True,'method':'finite_pose_exact_BREP_relative_transform_cache','tolerance_mm3':TOL,'declared_test_ranges_deg':ranges,'single_axis_step_deg':step,'pose_count':len(result),'failed_pose_count':sum(not r['passed'] for r in result),'boolean_count':checker.boolean_count,'all_unit_pairs_per_pose':len(checker.pairs),'cache_entries':len(checker.cache),'seconds':time.monotonic()-start,'passed':all(r['passed'] for r in result),'continuous_motion_proven':False,'limits':['Finite tested poses only; no interpolation proof','Not all Cartesian products of ranges','No cables, tolerances or elastic deformations','New attachment fasteners are absent from this stage'],'poses':result}
    (ROOT/f'reports/motion_{mode}.json').write_text(json.dumps(report,indent=2));print('FINISHED',report['passed'],report['failed_pose_count'],flush=True)
    sys.exit(0 if report['passed'] else 2)
if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else 'screen')
