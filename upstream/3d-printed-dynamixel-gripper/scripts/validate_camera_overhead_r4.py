"""Independent saved-file checks for the mount; inherited statuses are not erased."""
import hashlib
import json
import math
from itertools import combinations, product
from pathlib import Path

import numpy as np
import trimesh
from OCP.BRepAdaptor import BRepAdaptor_Surface

from gripper_design.camera_overhead_r4 import (
    ANCHORS,
    INPUT,
    RUN,
    TOP,
    Spec,
    box,
    cylinder,
    opening_mm,
    retained_at,
)
from scripts.assembly_io import bounds, read_step


def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def box_distance(a,b):
    a,b=np.asarray(a),np.asarray(b)
    return float(np.linalg.norm(np.maximum(0,np.maximum(a[:3]-b[3:],b[:3]-a[3:]))))


def pair(a,b,min_gap=.3,contact=False,roi=None):
    """Fail closed. AABB disjointness works for surface-only source obstacles too."""
    gap=box_distance(bounds(a),bounds(b))
    if gap>=min_gap-1e-6:
        return {'status':'PASS','method':'AABB_lower_bound','gap_mm':gap}
    if not a.Solids() or not b.Solids():
        # The surface is not deleted. Its entire bounding box is a conservative
        # solid superset. Prove separation only; overlap remains UNKNOWN.
        if bool(a.Solids()) != bool(b.Solids()):
            solid, surface = (a,b) if a.Solids() else (b,a)
            q=bounds(surface)
            if min(q[3+i]-q[i] for i in range(3))>1e-8:
                cover=box(q[0],q[3],q[1],q[4],q[2],q[5])
                dist=solid.distance(cover)
                # Boundary distance on a Compound can be positive for containment.
                # Reject cover occupancy before accepting the distance bound.
                intersection=abs(solid.intersect(cover).Volume())
                if math.isfinite(dist) and math.isfinite(intersection) and intersection<=1e-5 and dist >= min_gap-1e-6:
                    return {'status':'PASS','method':'solid_vs_surface_enclosing_box',
                            'gap_mm':float(dist),'conservative_cover_bounds':q}
        return {'status':'UNKNOWN','method':'overlapping_non_solid_bounds','gap_mm':gap}
    try:
        # Some Compound distances are boundary-only: positive distance is NOT
        # a non-overlap proof. Test material intersection before using distance.
        v=abs(a.intersect(b).Volume())
        if not math.isfinite(v): raise ValueError('non-finite intersection')
        if v>1e-5 and roi is None:
            return {'status':'FAIL','method':'material_intersection_before_distance','intersection_mm3':v}
        dist=a.distance(b)
        if not math.isfinite(dist): raise ValueError('non-finite distance')
        if dist>=min_gap-1e-6:
            return {'status':'PASS','method':'BRep_distance','gap_mm':float(dist)}
        if roi is not None:
            outside=a.cut(roi)
            outside_v=abs(outside.intersect(b).Volume())
            return {'status':'PASS' if outside_v<=1e-5 else 'FAIL',
                    'method':'named_receiver_ROI','intersection_mm3':v,'outside_roi_mm3':outside_v,
                    'gap_mm':float(dist),'actual_thread_strength_verified':False}
        if v>1e-5: return {'status':'FAIL','method':'intersection','intersection_mm3':v,'gap_mm':float(dist)}
        return {'status':'PASS' if contact else 'FAIL','method':'declared_contact' if contact else 'insufficient_gap',
                'intersection_mm3':v,'gap_mm':float(dist)}
    except Exception as e:  # noqa: BLE001 - any kernel failure must become ERROR, never PASS
        return {'status':'ERROR','method':'exception','error':str(e)}


def new_pair_contact(a,b):
    """Explicit contact/fit list. No wholesale exemption of arbitrary hardware."""
    for i in range(4):
        family={f'CAM4_BASE_WASHER_{i}',f'CAM4_BASE_TAP_{i}','CAM4_BASE'}
        if {a,b}<=family: return True
        fam={f'CAM4_PCB_WASHER_{i}',f'CAM4_PCB_BOLT_{i}',f'CAM4_PCB_NUT_{i}'}
        if a in fam and b in fam|{'CAM4_CARRIER','CAM4_ASSUMED_PCB'}: return True
        if b in fam and a in fam|{'CAM4_CARRIER','CAM4_ASSUMED_PCB'}: return True
    for i in range(2):
        family={f'CAM4_CARRIER_WASHER_{i}',f'CAM4_CARRIER_BOLT_{i}',f'CAM4_CARRIER_NUT_{i}'}
        if a in family and b in family|{'CAM4_BASE','CAM4_CARRIER'}: return True
        if b in family and a in family|{'CAM4_BASE','CAM4_CARRIER'}: return True
    if {a,b}=={'CAM4_CARRIER','CAM4_BASE'}: return True
    if {a,b}=={'CAM4_CARRIER','CAM4_ASSUMED_PCB'}: return True
    joins=[{'CAM4_ASSUMED_PCB',x} for x in ['CAM4_ASSUMED_LENS','CAM4_ASSUMED_REAR_COMPONENTS','CAM4_ASSUMED_USB_PORT']]
    joins += [{'CAM4_ASSUMED_USB_PORT','CAM4_ASSUMED_REAR_COMPONENTS'},
              {'CAM4_ASSUMED_USB_PORT','CAM4_ASSUMED_USB_PLUG'},
              {'CAM4_ASSUMED_USB_PLUG','CAM4_ASSUMED_USB_CABLE'},
              {'CAM4_ASSUMED_PCB','CAM4_ASSUMED_USB_PLUG'}]
    # PCB/plug is an internal fixed assumed device fit (0.2 mm), not the
    # external printed-part clearance rule. Positive overlap still fails.
    return {a,b} in joins


def external_pair(n,a,m,b):
    if m=='PG3_XL430_fixed' and n=='CAM4_BASE':
        gap=bounds(a)[2]-bounds(b)[5]
        return {'status':'PASS' if gap>=-1e-6 else 'FAIL', 'method':'shared_top_plane_separation',
                'signed_gap_mm':gap,'contact_is_intended':True}
    if m=='PG3_XL430_fixed' and n.startswith('CAM4_BASE_TAP_'):
        i=int(n.rsplit('_',1)[1]); x,y,z=ANCHORS[i]
        roi=cylinder(1.301,4.001,(x,y,TOP-4))
        # Outside hole-forming ROI the screw remains above the case's enclosing plane.
        outside=a.cut(roi)
        diff=bounds(outside)[2]-bounds(b)[5]
        return {'status':'PASS' if diff>=-1e-5 else 'FAIL','method':'receiver_ROI_and_top_plane',
                'outside_roi_signed_gap_mm':diff,'roi_axis':(x,y,z),'roi_radius_mm':1.301,
                'thread_forming_contact_is_intended':True}
    return pair(a,b)


def counter(rows):
    return {k:sum(r['status']==k for r in rows) for k in ['PASS','FAIL','ERROR','UNKNOWN']}


def controls():
    a=box(0,10,0,10,0,10)
    vals=[('separated',pair(a,a.translate((11,0,0)))['status']=='PASS'),
          ('overlap',pair(a,a.translate((9,0,0)))['status']=='FAIL'),
          ('contained',pair(a,box(2,3,2,3,2,3))['status']=='FAIL'),
          ('small_gap',pair(a,a.translate((10.1,0,0)))['status']=='FAIL'),
          ('touch_not_clear',pair(a,a.translate((10,0,0)))['status']=='FAIL')]
    return [{'test':n,'passed':bool(v)} for n,v in vals]


def run():
    s=Spec()
    saved_path=RUN/'CAD/ID5_camera_mid_ASSEMBLY.step'
    if not saved_path.exists(): raise FileNotFoundError(saved_path)
    saved={r.name:r.world for r in read_step(saved_path)[2]}
    source={r.name:r.world for r in read_step(INPUT)[2]}
    p={n:v for n,v in saved.items() if n.startswith('CAM4_')}
    retained={n:v for n,v in saved.items() if not n.startswith('CAM4_')}
    ctl=controls()
    if not all(r['passed'] for r in ctl): raise ValueError(f'geometry controls failed {ctl}')
    report={'revision':s.revision,'input_sha':digest(INPUT),'saved_mid_sha':digest(saved_path),
            'checker_sha':digest(__file__),'controls':ctl,'scope':'new camera mount versus all retained source obstacles; unchanged existing collisions inherited',
            'minimum_external_gap_mm':.3,'fixed_assumed_device_fit':{'pair':['CAM4_ASSUMED_PCB','CAM4_ASSUMED_USB_PLUG'],'nominal_gap_mm':.2,'actual_fit_verified':False,'reason':'internal device geometry, not two moving/printed parts'},'intersection_tolerance_mm3':1e-5,
            'inherited_checkpoint':{'PASS':1806,'ERROR':1,'UNKNOWN':6,'FAIL':0,'approved':False},
            'source_preservation':[], 'anchor_holes':[], 'new_internal':[], 'external_static':[], 'motion':{},'saved_files':[]}
    for n,b in retained.items():
        a=source[n]
        dv=abs(a.Volume()-b.Volume()); db=max(abs(x-y) for x,y in zip(bounds(a),bounds(b)))
        ar=abs(a.Area()-b.Area())
        report['source_preservation'].append({'name':n,'volume_error':dv,'area_error':ar,'bbox_error':db,
                                            'pass':dv<.01 and db<1e-4 and ar<.01})
    # Real cylinder faces, not just the YAML pitch.
    motor=retained['PG3_XL430_fixed']
    found=[]
    for i,f in enumerate(motor.Faces()):
        if f.geomType()!='CYLINDER':continue
        c=BRepAdaptor_Surface(f.wrapped).Cylinder(); axis=c.Axis().Direction(); pos=c.Location(); bb=bounds(f)
        if abs(axis.Z())>.99 and abs(c.Radius()-1.05)<1e-6 and bb[5]>199:
            found.append((pos.X(),pos.Y(),199.85))
            report['anchor_holes'].append({'face':i,'radius':c.Radius(),'axis':(axis.X(),axis.Y(),axis.Z()),'center':found[-1],'span':bb[2:6:3]})
    report['anchors_pass']=len(found)==4 and all(min(math.dist(a,b) for b in found)<1e-5 for a in ANCHORS)
    # Hole axes are extracted independently from the saved base too.
    holes=[]
    for i,f in enumerate(p['CAM4_BASE'].Faces()):
        if f.geomType()=='CYLINDER':
            c=BRepAdaptor_Surface(f.wrapped).Cylinder(); d=c.Axis().Direction(); q=c.Location()
            if abs(c.Radius()-1.45)<1e-5 and abs(d.Z())>.99: holes.append((q.X(),q.Y(),TOP))
    report['base_holes_pass']=len(holes)==4 and all(min(math.dist(a,b) for b in holes)<1e-5 for a in ANCHORS)
    report['base_measured_holes']=holes
    for a,b in combinations(p,2):
        res=pair(p[a],p[b],contact=new_pair_contact(a,b)); res.update(a=a,b=b)
        report['new_internal'].append(res)
    pb={n:bounds(v) for n,v in p.items()}; rb={n:bounds(v) for n,v in retained.items()}
    for a,b in product(p,retained):
        lower=box_distance(pb[a],rb[b])
        res=({'status':'PASS','method':'AABB_lower_bound','gap_mm':lower}
             if lower>=.3-1e-6 else external_pair(a,p[a],b,retained[b]));res.update(a=a,b=b)
        report['external_static'].append(res)
    print('internal',counter(report['new_internal']),'external',counter(report['external_static']),flush=True)
    # Moving groups are recomputed from saved neutral geometry, not a stale proxy scene.
    fixed_names={n for n in retained if not n.startswith('PG3_') or n in ['PG3_XL430_fixed','PG3_frame','PG3_cap_U','PG3_cap_D'] or n.startswith(('PG3_cap_','PG3_case_tapper_'))}
    motion_summary=[]; failures=[]; min_gap=1e9
    for angle in np.linspace(25,135,221):
        dynamic=retained_at(retained,float(angle))
        checks=[]
        movers={n:s for n,s in dynamic.items() if n not in fixed_names}
        db={n:bounds(s) for n,s in movers.items()}
        for a,shape_a in p.items():
            for b,shape_b in movers.items():
                # Every new part is static relative to the motor case.
                lower=box_distance(pb[a],db[b])
                res=({'status':'PASS','method':'AABB_lower_bound','gap_mm':lower}
                     if lower>=.3-1e-6 else external_pair(a,shape_a,b,shape_b))
                if res['status']!='PASS': failures.append({'angle':float(angle),'a':a,'b':b,**res})
                min_gap=min(min_gap,res.get('gap_mm',1e9))
                checks.append(res)
        if len(motion_summary)%50==0: print('motion pose',angle,flush=True)
        motion_summary.append({'angle':float(angle),'opening_mm':opening_mm(float(angle)),**counter(checks)})
    report['motion']={'pose_count':221,'range_deg':[25,135],'step_deg':.5,
                      'pair_count_per_pose':len(checks),'results':motion_summary,'failures':failures,
                      'minimum_measured_or_bounded_gap_mm':min_gap,'continuous_all_arm_motion_proven':False}
    for pose in ['open','mid','closed']:
        path=RUN/f'CAD/ID5_camera_{pose}_ASSEMBLY.step'
        q=read_step(path)[2]
        report['saved_files'].append({'path':str(path.relative_to(RUN)),'sha':digest(path),'count':len(q),'inventory_pass':{r.name for r in q}==set(saved)})
    for path in (RUN/'STL').glob('*.stl'):
        mesh=trimesh.load(path,force='mesh')
        report['saved_files'].append({'path':str(path.relative_to(RUN)),'sha':digest(path),
                                     'watertight':mesh.is_watertight,'winding_consistent':mesh.is_winding_consistent,
                                     'components':len(mesh.split()),'positive_volume':mesh.volume>0,
                                     'bounds':mesh.bounds.tolist()})
    report['counts']={'new_internal':counter(report['new_internal']),'external_static':counter(report['external_static'])}
    report['local_geometric_checks_pass']=all(r['pass'] for r in report['source_preservation']) and report['anchors_pass'] and report['base_holes_pass'] and not failures and all(r['status']=='PASS' for r in report['new_internal']+report['external_static'])
    (RUN/'reports/geometry.json').write_text(json.dumps(report,indent=2,default=lambda o:o.item() if isinstance(o,np.generic) else str(o)))
    print('motion',min_gap,len(failures),'overall_local',report['local_geometric_checks_pass'],flush=True)
    bad=[r for r in report['new_internal']+report['external_static'] if r['status']!='PASS']
    print(json.dumps(bad,indent=2),flush=True)
    return report


if __name__=='__main__': run()