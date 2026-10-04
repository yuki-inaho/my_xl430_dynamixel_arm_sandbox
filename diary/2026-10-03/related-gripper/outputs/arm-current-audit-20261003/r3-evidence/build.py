"""Collision revision R3. Millimetres; use actual source B-rep motor geometry.

Retain the base, yaw carrier and shoulder sculpture below the change plane.
Rebuild former XL330 interfaces, not merely a rigid substitution of the motor.
A successful generation is NOT a collision or manufacturing acceptance.
"""
from pathlib import Path
from dataclasses import dataclass
import json, hashlib
import cadquery as cq
from assembly_io import read_step, bounds

ROOT=Path(__file__).resolve().parents[1]
MOTOR_SOURCE='/Robot Arm v14/XL-430_new v1:1'
ORIGIN=(5.44999999999678,116.604346834981,-82.9367090394484)
SHIFT=cq.Location((-ORIGIN[0],-ORIGIN[1],20-ORIGIN[2]))

def box(x0,x1,y0,y1,z0,z1):
    return cq.Solid.makeBox(x1-x0,y1-y0,z1-z0,cq.Vector(x0,y0,z0))
def cyl(r,h,p,axis):
    return cq.Solid.makeCylinder(r,h,cq.Vector(*p),cq.Vector(*axis))
def combine(shapes):
    out=shapes[0]
    for sh in shapes[1:]: out=out.fuse(sh)
    return out.clean()
def cut_all(s,tools):
    for t in tools: s=s.cut(t)
    return s.clean()
def translate(s,p): return s.moved(cq.Location(p))

def horn_ears(length, thickness=4., radius=13.5):
    """X-axis horn/idler planes at +/-19, pitch radius8, centre relief11."""
    shapes=[]
    for x in [-23.,19.]:
        shapes += [cyl(radius,thickness,(x,0,0),(1,0,0)),box(x,x+thickness,0,length,-7,7)]
    return shapes

def horn_tools(two_sided=True):
    # Central hole clears R5.3 idler cap and R4 output boss.
    ranges=[(-25.,8.),(17.,8.)] if two_sided else [(17.,8.)]
    tools=[]
    for x,length in ranges:
        tools.append(cyl(5.5,length,(x,0,0),(1,0,0)))
        for y,z in [(8,0),(-8,0),(0,8),(0,-8)]: tools.append(cyl(1.2,length,(x,y,z),(1,0,0)))
    return tools

def body_floor(xc,yc,zc,front_extra=0.):
    # Motor is Ry(90): local X becomes -world Z.
    # Side-case mounting holes: local Y=-28/-4, Z=+/-6.
    s=box(xc-17,xc+17,yc-35.25,yc+11.25+front_extra,zc-18.25,zc-14.25)
    tools=[cyl(1.2,8,(xc+x,yc+y,zc-20),(0,0,1)) for x in [-6,6] for y in [-28,-4]]
    return cut_all(s,tools)

def generate():
    _,_,original=read_step(ROOT/'reference/arm_original.step')
    _,_,mixed=read_step(ROOT/'reference/mixed_baseline.step')
    mixed_idx={int(r.name.split('_')[0]):r for r in mixed}
    ref_loc=original[0].loc
    motor=[(i,r.name,r.shape.moved(ref_loc.inverse*r.loc),r.color) for i,r in enumerate(original) if r.path.startswith(MOTOR_SOURCE+'/')]
    assert len(motor)==35
    # Actual kinematic order, NOT the legacy J tags of the rigid swap.
    centres=[(0,0,20),(-.2,0,56.3),(-.2,14.8,164.6),(-.2,104.9,164.6),(-.2,164.9,164.6),(-.2,234.9,164.6)]
    rotations=[(0,0,0),(0,-90,0),(0,90,0),(0,90,0),(-90,0,0),(0,90,0)]
    axes=[(0,0,1),(-1,0,0),(1,0,0),(1,0,0),(0,1,0),(1,0,0)]
    motor_loc=[cq.Location(p,r) for p,r in zip(centres,rotations)]
    parts={}
    parts['P01_base']=mixed_idx[56].shape.moved(SHIFT*mixed_idx[56].loc)
    parts['P02_yaw_carrier']=mixed_idx[59].shape.moved(SHIFT*mixed_idx[59].loc)
    # P03: retain the lower 90mm of the original shoulder in its local frame.
    shoulder=original[58]
    local_kept=shoulder.shape.intersect(box(-100,100,-30,90,-100,100))
    kept=local_kept.moved(SHIFT*shoulder.loc)
    x,y,z=centres[2]
    floor=body_floor(x,y,z)
    # Join underside plate to unmodified sculpted shoulder across a 0.2mm overlap.
    bridge=box(x-14.75,x+14.75,-13,13,145.8,146.5)
    shoulder_new=combine([kept,bridge,floor])
    # Reopen the plate holes AFTER union so the connection bridge cannot cap them.
    tools=[cyl(1.2,20,(x+dx,y+dy,z-25),(0,0,1)) for dx in [-6,6] for dy in [-28,-4]]
    # Local underside tool/head relief; not a strength or assembly approval.
    tools += [cyl(2.4,10.35,(x+dx,y+dy,136),(0,0,1)) for dx in [-6,6] for dy in [-28,-4]]
    shoulder_new=cut_all(shoulder_new,tools)
    # q2=-40 exposes a 1.529mm³ rear-case/neck collision in the retained source.
    # Remove a 0.6mm-clearance chamfer ONLY within the measured neck change mask.
    neck_mask=box(-18,18,-14,-8,79,90)
    case_envelope=box(-14.85,14.85,-35.85,11.85,-17.6,17.6).moved(motor_loc[1])
    case_in_shoulder_frame=case_envelope.rotate(centres[1],(centres[1][0]+1,centres[1][1],centres[1][2]),-40)
    shoulder_new=shoulder_new.cut(case_in_shoulder_frame.intersect(neck_mask)).clean()
    parts['P03_shoulder_XL430']=shoulder_new
    change_mask=combine([neck_mask,box(-100,100,-100,100,136,300)])
    cq.exporters.export(change_mask,str(ROOT/'reference/P03_change_mask.step'))
    cq.exporters.export(original[58].shape.moved(SHIFT*original[58].loc),str(ROOT/'reference/P03_original_world.step'))
    # P04 extension: 90.1mm axis spacing, yoke at upstream, case cradle downstream.
    L=90.1
    shapes=horn_ears(L-35.5)
    shapes += [box(-23,23,L-40,L-35.5,-18.25,7),box(-17,17,L-36,L-35,-18.25,-14.25),body_floor(0,L,0)]
    s=cut_all(combine(shapes),horn_tools())
    parts['P04_extension_XL430']=translate(s,centres[2])
    # P05 wrist pitch -> roll, 60mm along Y. Case side plates attach to 8 M2 holes.
    L=60.
    shapes=horn_ears(L-20.5)
    shapes += [box(-23,23,L-24.5,L-20.5,-7,32),
               box(-18.25,-14.25,L-24.5,L+10,-7,32),
               box(14.25,18.25,L-24.5,L+10,-7,32)]
    tools=horn_tools()
    for x0 in [-20,12]:
        for y in [-6,6]:
            for z in [4,28]: tools.append(cyl(1.2,8,(x0,L+y,z),(1,0,0)))
    parts['P05_wrist_XL430']=translate(cut_all(combine(shapes),tools),centres[3])
    # P06 roll output -> gripper body plus stationary finger.
    L=70.
    shapes=[cyl(13.5,4,(0,19,0),(0,1,0)),box(-10,10,19,26,-18.25,-7),
            box(-10,10,23,L-31,-18.25,-14.25),body_floor(0,L,0),
            box(-17,23,L+7,L+70,-18.25,-14.25),
            box(7,23,L+64,L+70,-14.25,-9)]
    tools=[cyl(5.5,8,(0,17,0),(0,1,0))]
    for x,z in [(8,0),(-8,0),(0,8),(0,-8)]:tools.append(cyl(1.2,8,(x,17,z),(0,1,0)))
    parts['P06_fixed_gripper_XL430']=translate(cut_all(combine(shapes),tools),centres[4])
    # P07 moving finger. 2mm nominal gap to stationary tip at q6=0.
    shapes=[cyl(13.5,4,(19,0,0),(1,0,0)),box(19,23,0,70,-7,7),box(7,23,64,70,-7,7)]
    parts['P07_moving_gripper_XL430']=translate(cut_all(combine(shapes),horn_tools(False)),centres[5])
    levels=[0,1,2,3,4,5,6]
    assy=cq.Assembly(name='XL430_R3_COLLISION_STUDY')
    manifest=[]
    for j,loc in enumerate(motor_loc):
        for i,name,sh,color in motor:
            key=f'M{j+1:02d}_ref{i:02d}'
            assy.add(sh,loc=loc,name=key,color=color or cq.Color(.24,.27,.30))
            manifest.append({'name':key,'kind':'supplier','physical_unit':f'M{j+1:02d}','level':j,'source_leaf_index':i,'source_leaf_name':name,'bounds':bounds(sh.moved(loc))})
    for k,(name,sh) in enumerate(parts.items()):
        assert sh.isValid(),f'invalid {name}'
        assert len(sh.Solids())==1,f'{name} {len(sh.Solids())} solids'
        assert sh.Volume()>0
        assy.add(sh,name=name,color=cq.Color(.43,.58,.65) if k>=2 else cq.Color(.64,.65,.66))
        cq.exporters.export(sh,str(ROOT/f'CAD/parts/{name}.step'))
        cq.exporters.export(sh,str(ROOT/f'CAD/parts/{name}.stl'),tolerance=.05,angularTolerance=.12)
        manifest.append({'name':name,'kind':'polymer','physical_unit':name,'level':levels[k],'volume_mm3':sh.Volume(),'bounds':bounds(sh)})
    assy.export(str(ROOT/'CAD/arm_XL430_R3.step'))
    (ROOT/'reports/manifest.json').write_text(json.dumps(manifest,indent=2))
    joints=[{'name':f'J{j+1}','centre_mm':p,'axis':a,'zero_rotation_xyz_deg':r,'motor':f'M{j+1:02d}'} for j,(p,a,r) in enumerate(zip(centres,axes,rotations))]
    (ROOT/'reports/joints.json').write_text(json.dumps(joints,indent=2))
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'reference/arm_original.step',ROOT/'reference/mixed_baseline.step']}
    (ROOT/'reports/inputs.json').write_text(json.dumps(hashes,indent=2))
    cq.exporters.export(kept,str(ROOT/'reference/shoulder_preserved_region.step'))
    print('GENERATED',len(manifest),'components;',len(parts),'polymer parts')
    return parts

if __name__=='__main__': generate()
