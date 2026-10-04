"""Extract immutable R3 STEP occurrences; produce a bare-arm derived URDF and mesh cache.

Usage: python scripts/build_model.py --source /path/to/3d-printed-dynamixel-gripper-main
The saved STEP already contains the reference joint rotations. They must not be
applied a second time. All derived meshes use meters; original geometry is unedited.
"""
from pathlib import Path
import argparse, json, sys, shutil, hashlib, time
import numpy as np
import trimesh
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]

def main(source:Path):
    sys.path.insert(0,str(source/'scripts'))
    from assembly_io import read_step,bounds
    ref=source/'references/arm-r3'
    manifest=json.loads((ref/'manifest.json').read_text())
    chosen={r['name']:r for r in manifest if r['level']<=4}
    _,_,rows=read_step(ref/'arm_XL430_R3.step')
    joints=json.loads((ref/'joints.json').read_text())
    for name in ('joints.json','manifest.json','LICENSE','README_ja.md','NOT_MANUFACTURING_APPROVED.txt'):
        shutil.copy2(ref/name,ROOT/'model'/('source_'+name))
    shutil.copy2(source/'references/arm-baseline/low-cost-arm.urdf',ROOT/'model/source_baseline.urdf')
    # Deliver the exact assembly STEP alongside the derived selection, with its license.
    shutil.copy2(ref/'arm_XL430_R3.step',ROOT/'model/source_arm_XL430_R3.step')
    units=sorted({r['physical_unit'] for r in chosen.values()})
    vs=[]; fs=[]; vl=[]; fl=[]; fk=[]; fu=[]; leaves=[]; n=0
    start=time.monotonic()
    for row in rows:
        if row.name not in chosen: continue
        entry=chosen[row.name]
        shape=row.world
        b=np.array(bounds(shape)); mb=np.array(entry['bounds'])
        if np.max(abs(b-mb))>1e-4: raise ValueError(f'Unexpected STEP bounds for {row.name}')
        vv,ff=shape.tessellate(0.18,0.28)
        v=np.array([t.toTuple() for t in vv],dtype=np.float64)/1000
        f=np.array(ff,dtype=np.int32).reshape(-1,3)
        if not len(f): raise ValueError(f'Empty tessellation: {row.name}')
        lv=entry['level']; kind=1 if entry['kind']=='printed' else 0
        # Source manifest uses "printed" for printed parts; also validate by unit.
        kind=int(entry['physical_unit'].startswith('P'))
        vs.append(v);fs.append(f+n);vl.append(np.full(len(v),lv,np.int32));fl.append(np.full(len(f),lv,np.int32))
        fk.append(np.full(len(f),kind,np.int32));fu.append(np.full(len(f),units.index(entry['physical_unit']),np.int32))
        leaves.append({'name':row.name,'unit':entry['physical_unit'],'level':lv,'vertex_start':n,'vertex_count':len(v),'face_count':len(f),
          'source_bounds_mm':b.tolist(),'mesh_bounds_m':np.array([v.min(0),v.max(0)]).ravel().tolist()})
        n+=len(v)
    v=np.concatenate(vs);f=np.concatenate(fs);vl=np.concatenate(vl);fl=np.concatenate(fl);fk=np.concatenate(fk);fu=np.concatenate(fu)
    np.savez_compressed(ROOT/'model/bare_arm.npz',vertices=v,faces=f,vertex_level=vl,face_level=fl,face_kind=fk,face_unit=fu,units=np.array(units),
                        pivots=np.array([j['centre_mm'] for j in joints[:4]])/1000,axes=np.array([j['axis'] for j in joints[:4]]))
    # URDF has identity reference orientations, origin offsets from the saved assembly.
    robot=ET.Element('robot',name='xl430_r3_bare_observation_model')
    origins=np.vstack((np.zeros((1,3)),np.array([j['centre_mm'] for j in joints[:4]])/1000))
    for lv in range(5):
        link=ET.SubElement(robot,'link',name=f'body_{lv}')
        sel=fl==lv; mesh=trimesh.Trimesh(v-origins[lv],f[sel],process=False)
        mesh.remove_unreferenced_vertices(); mesh.export(ROOT/f'model/body_{lv}.stl')
        vis=ET.SubElement(link,'visual');ET.SubElement(vis,'origin',xyz='0 0 0',rpy='0 0 0')
        ET.SubElement(ET.SubElement(vis,'geometry'),'mesh',filename=f'body_{lv}.stl',scale='1 1 1')
        if lv:
            joint=ET.SubElement(robot,'joint',name=f'J{lv}',type='revolute')
            ET.SubElement(joint,'parent',link=f'body_{lv-1}');ET.SubElement(joint,'child',link=f'body_{lv}')
            ET.SubElement(joint,'origin',xyz=' '.join(map(str,origins[lv]-origins[lv-1])),rpy='0 0 0')
            ET.SubElement(joint,'axis',xyz=' '.join(map(str,joints[lv-1]['axis'])))
            # Modeling search bounds, explicitly not physical or firmware limits.
            ET.SubElement(joint,'limit',lower=str(-np.pi),upper=str(np.pi),effort='0',velocity='0')
    ET.indent(robot)
    ET.ElementTree(robot).write(ROOT/'model/bare_arm_r3.urdf',encoding='utf-8',xml_declaration=True)
    info={'source_leaf_count':len(rows),'included_leaf_count':len(leaves),'units':units,'vertices':len(v),'triangles':len(f),
      'tessellation_linear_tolerance_mm':.18,'tessellation_angular_tolerance_rad':.28,'elapsed_seconds':time.monotonic()-start,
      'reference_bounds_m':np.array([v.min(0),v.max(0)]).tolist(),'leaves':leaves,
      'urdf_search_limits_note':'+/-pi are mathematical search bounds only, not calibrated hardware limits',
      'J5_note':'No downstream observed geometry; excluded/unobservable, not fitted as zero'}
    (ROOT/'model/provenance.json').write_text(json.dumps(info,ensure_ascii=False,indent=2))
    print(json.dumps({k:vv for k,vv in info.items() if k!='leaves'},ensure_ascii=False,indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True)
    main(ap.parse_args().source)
