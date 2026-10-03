"""Export R4 camera fixture against the exact supplied full-arm checkpoint."""
import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path

import cadquery as cq

from gripper_design.camera_overhead_r4 import (
    INPUT,
    ROOT,
    RUN,
    Spec,
    base,
    build,
    carrier_local,
    metadata,
    retained_at,
)
from scripts.assembly_io import bounds, read_step
from scripts.render_cad import render


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def color(name):
    if name=='CAM4_BASE': return (0.78,.38,.12)
    if name=='CAM4_CARRIER': return (.15,.37,.61)
    if 'ASSUMED_PCB' in name: return (.16,.48,.29)
    if 'ASSUMED' in name: return (.15,.17,.19)
    if name.startswith('CAM4_'): return (.70,.73,.77)
    if 'finger_' in name and name.startswith('PG3_'): return (.27,.48,.67)
    if 'pad_' in name: return (.21,.23,.25)
    if name in ['PG3_link_R','PG3_link_L']: return (.36,.62,.48)
    if name=='PG3_crank': return (.75,.42,.22)
    if 'XL430' in name or name.startswith('ARM_M'): return (.39,.42,.46)
    return (.66,.70,.73)


def export_assembly(parts,path):
    a=cq.Assembly(name=path.stem)
    for n,s in parts.items(): a.add(s,name=n,color=cq.Color(*color(n)))
    a.export(str(path))
    saved=read_step(path)[2]
    if len(saved)!=len(parts) or {r.name for r in saved}!=set(parts):
        raise ValueError('saved STEP inventory mismatch')
    checks=[]
    for r in saved:
        expected=parts[r.name]; actual=r.world
        dv=abs(expected.Volume()-actual.Volume())
        db=max(abs(a-b) for a,b in zip(bounds(expected),bounds(actual)))
        checks.append({'name':r.name,'volume_error_mm3':dv,'bounds_error_mm':db,
                       'solid_count':len(actual.Solids()),'valid':actual.isValid()})
        if dv>0.01 or db>1e-4: raise ValueError(f'round-trip geometry mismatch {r.name}')
    return {'path':str(path.relative_to(RUN)),'sha256':sha(path),'count':len(saved),'checks':checks}


def run():
    s=Spec(); p=build(s)
    rows=read_step(INPUT)[2]
    removed=[r.name for r in rows if r.name.startswith('CAMERA_')]
    neutral={r.name:r.world for r in rows if not r.name.startswith('CAMERA_')}
    if len(removed)!=21: raise ValueError('unexpected old camera inventory')
    RUN.mkdir(exist_ok=True)
    for n in ['CAD','STL','images','reports','source','docs']: (RUN/n).mkdir(exist_ok=True)
    manifest=metadata(s)
    manifest.update(input_step_sha256=sha(INPUT), input_count=len(rows),removed_camera=removed,
                    retained_names=sorted(neutral), new_names=sorted(p),outputs={})
    for n,shape in [('01_ID5_top_base',p['CAM4_BASE']),('02_camera_carrier',p['CAM4_CARRIER'])]:
        cq.exporters.export(shape,str(RUN/'CAD'/f'{n}.step'))
    # Each print file is explicitly transformed to its own bed coordinates.
    b=base(s); bb=bounds(b); b=b.translate((-bb[0],-bb[1],-bb[2]))
    plate=carrier_local(s).rotate((0,0,0),(1,0,0),180)
    bb=bounds(plate); plate=plate.translate((-bb[0],-bb[1],-bb[2]))
    for n,shape in [('01_ID5_top_base',b),('02_camera_carrier',plate)]:
        cq.exporters.export(shape,str(RUN/'STL'/f'{n}.stl'),tolerance=.025,angularTolerance=.08)
    for pose,angle in [('open',25),('mid',90),('closed',135)]:
        parts=retained_at(neutral,angle)|p
        path=RUN/'CAD'/f'ID5_camera_{pose}_ASSEMBLY.step'
        manifest['outputs'][pose]=export_assembly(parts,path)
        if pose=='mid':
            scene=[(v,color(k)) for k,v in parts.items()]
            render(scene,RUN/'images/full_arm.png',(1,1,.8),size=(1200,1050))
            for view,d in [('local_iso',(1,1,.7)),('front',(0,1,0)),('side',(1,0,0)),('top',(0,0,1))]:
                render(scene,RUN/f'images/{view}.png',d,size=(1200,1000),focus=(-.2,191,196),scale=66)
            render([(b,color('CAM4_BASE')),(plate.translate((62,0,0)),color('CAM4_CARRIER'))],RUN/'images/print_layout.png',(1,-1,1),size=(1200,850))
            render([(p[k],color(k)) for k in p],RUN/'images/mount_only.png',(1,1,.6),size=(1000,850))
        print('export',pose,len(parts),flush=True)
    (RUN/'reports/export.json').write_text(json.dumps(manifest,indent=2))
    (ROOT/'specs/camera_mount_overhead_r4.json').write_text(json.dumps(asdict(s),indent=2))
    for path in [ROOT/'gripper_design/camera_overhead_r4.py',ROOT/'scripts/build_camera_overhead_r4.py',ROOT/'tests/test_camera_overhead_r4.py']:
        shutil.copy2(path,RUN/'source'/path.name)
    return manifest


if __name__=='__main__': run()