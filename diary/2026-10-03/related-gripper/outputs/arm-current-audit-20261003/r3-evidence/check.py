"""Checks re-imported STEP. No external contact exemptions; fail on errors."""
from pathlib import Path
import json, itertools, time, math, sys
import numpy as np
import cadquery as cq
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from assembly_io import read_step,bounds
ROOT=Path(__file__).resolve().parents[1]
TOL=1e-4

def common_volume(a,b):
    op=BRepAlgoAPI_Common(a.wrapped,b.wrapped);op.Build()
    if not op.IsDone() or op.Shape().IsNull(): raise ValueError('failed common')
    c=cq.Shape.cast(op.Shape())
    if not c.isValid(): raise ValueError('invalid common')
    vols=[s.Volume() for s in c.Solids()]
    if any(not math.isfinite(v) or v < -TOL for v in vols):raise ValueError('invalid volume')
    return sum(vols)

def load():
    _,_,rows=read_step(ROOT/'CAD/arm_XL430_R3.step')
    meta={r['name']:r for r in json.loads((ROOT/'reports/manifest.json').read_text())}
    if len(rows)!=len(meta) or {r.name for r in rows}!=set(meta): raise ValueError('occurrence identity mismatch')
    parts=['P01_base','P02_yaw_carrier','P03_shoulder_XL430','P04_extension_XL430','P05_wrist_XL430','P06_fixed_gripper_XL430','P07_moving_gripper_XL430']
    trusted={f'M{j+1:02d}_ref{i:02d}':('supplier',f'M{j+1:02d}',j) for j in range(6) for i in range(35)}
    trusted.update({name:('polymer',name,j) for j,name in enumerate(parts)})
    if set(meta)!=set(trusted):raise ValueError('Unexpected physical component registry')
    for name,(kind,unit,level) in trusted.items():
        if (meta[name]['kind'],meta[name]['physical_unit'],meta[name]['level'])!=(kind,unit,level):raise ValueError('Physical grouping or kinematic level changed')
    return rows,meta

def scan(rows,meta):
    t=time.monotonic();external=[];internal=[];errors=[];data={};boxes={};nonsolid=[]
    for row in rows:
        s=row.world
        if not s.isValid():errors.append({'part':row.name,'error':'invalid'})
        if not s.Solids():nonsolid.append(row.name);continue
        data[row.name]=s;boxes[row.name]=bounds(s)
    pairs=[]
    for a,b in itertools.combinations(data,2):
        if all(min(boxes[a][k+3],boxes[b][k+3])-max(boxes[a][k],boxes[b][k])>1e-7 for k in range(3)):pairs.append((a,b))
    print('pairs',len(pairs),flush=True)
    for n,(a,b) in enumerate(pairs):
        try:
            v=common_volume(data[a],data[b])
            if v>TOL:
                record={'a':a,'b':b,'volume_mm3':v}
                (internal if meta[a]['kind']==meta[b]['kind']=='supplier' and meta[a]['physical_unit']==meta[b]['physical_unit'] else external).append(record)
        except Exception as e:errors.append({'a':a,'b':b,'error':str(e)})
        if n%50==0:print(n,'external',len(external),'internal',len(internal),flush=True)
    return {'check':'static_reimported_BREP','tolerance_mm3':TOL,'external_collision_count':len(external),'external':external,'supplier_internal_count':len(internal),'supplier_internal':internal,'errors':errors,'non_solid_supplier':nonsolid,'leaf_count':len(rows),'solid_occurrence_count':len(data),'all_pairs':len(data)*(len(data)-1)//2,'brep_pairs':len(pairs),'seconds':time.monotonic()-t,'passed':not external and not errors}

if __name__=='__main__':
    rows,meta=load();report=scan(rows,meta)
    (ROOT/'reports/static.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ['external','supplier_internal','non_solid_supplier']},indent=2))
    for r in report['external']:print(r)
    sys.exit(0 if report['passed'] else 2)
