"""Stage-specific nominal assembly / removal and full tool envelope checks.
Real bit engagement, finger motion and physical cable flexibility remain unknown.
"""
import json
import math

import numpy as np

from gripper_design.camera_overhead_r4 import ANCHORS, RUN, TOP, Spec, basis, cylinder, local_point
from scripts.assembly_io import bounds, read_step
from scripts.validate_camera_overhead_r4 import box_distance, digest, external_pair, pair


def serial(v):
    if isinstance(v,np.generic):return v.item()
    raise TypeError(type(v).__name__)


def check_pose(moving,obstacles,offset=(0,0,0),fit_pairs=(),gap=.3):
    rows=[]; obsbox={n:bounds(sh) for n,sh in obstacles.items()}
    for a,original in moving.items():
        shape=original.translate(tuple(offset));bb=bounds(shape)
        for b,ob in obstacles.items():
            lower=box_distance(bb,obsbox[b]);contact=(a,b) in fit_pairs
            if lower>=gap-1e-6:res={'status':'PASS','method':'AABB_lower_bound','gap_mm':lower}
            elif a.startswith('CAM4_BASE_TAP') and b=='PG3_XL430_fixed':res=external_pair(a,shape,b,ob)
            else:res=pair(shape,ob,min_gap=gap,contact=contact)
            rows.append({'a':a,'b':b,**res})
    return rows


def sweep(name,moving,obstacles,direction,length,fit_pairs=()):
    # Finite samples, expressly not continuous certification.
    bad=[];min_gap=math.inf;total=0
    direction=np.array(direction,dtype=float);direction/=np.linalg.norm(direction)
    steps=np.linspace(length,0,math.ceil(length/2)+1)
    for d in steps:
        out=check_pose(moving,obstacles,direction*d,fit_pairs)
        # Intended mating pairs are allowed to approach their seats within 0.3mm.
        total+=len(out)
        bad += [{'distance_to_seat_mm':float(d),**r} for r in out if r['status']!='PASS']
        good=[r['gap_mm'] for r in out if r.get('gap_mm',0)>1e-5 and (r['a'],r['b']) not in fit_pairs]
        if good:min_gap=min(min_gap,min(good))
    return {'name':name,'moving':list(moving),'obstacle_count':len(obstacles),'travel_mm':length,
            'direction_from_seated':direction.tolist(),'sample_count':len(steps),'pair_checks':total,
            'sample_pitch_max_mm':2.0,'failures':bad,'sampled_path_pass':not bad,
            'minimum_reported_non_mating_gap_mm':min_gap if math.isfinite(min_gap) else None,
            'reverse_removal_same_rigid_path':True,'continuous_certification':False}


def tool(pos,direction,shaft_d=3.0,shaft_l=35.0,handle_d=18.,handle_l=30.,travel=0.):
    v=np.array(direction,dtype=float); v/=np.linalg.norm(v);p=np.array(pos)
    if travel<0 or not math.isfinite(travel):raise ValueError('invalid tool travel')
    # Exact union of coaxial cylinder sweeps for a pure axial extraction.
    return cylinder(shaft_d/2,shaft_l+travel,tuple(p),tuple(v)).fuse(cylinder(handle_d/2,handle_l+travel,tuple(p+v*shaft_l),tuple(v))).clean()


def nut_driver_envelope(pos,direction,travel=0.):
    """Conservative external nut-driver envelope plus mandatory screw-tip relief.
    Central free bore is >=2.6 mm diameter and >=2 mm depth; actual AF4 socket
    and operator torque still require physical selection. Do not ignore bolt.
    """
    return tool(pos,direction,shaft_d=7,travel=travel).cut(cylinder(1.3,2,tuple(pos),tuple(direction))).clean()


def run():
    s=Spec();_,v,n=basis(s.pitch_deg)
    path=RUN/'CAD/ID5_camera_mid_ASSEMBLY.step'
    allparts={r.name:r.world for r in read_step(path)[2]}
    arm={k:v for k,v in allparts.items() if not k.startswith('CAM4_')}
    p={k:v for k,v in allparts.items() if k.startswith('CAM4_')}
    report={'revision':s.revision,'saved_mid_sha':digest(path),'checker_sha':digest(__file__),
            'tool_assumption':{'shaft_diameter_mm':3.,'shaft_length_mm':35.,'handle_diameter_mm':18.,'handle_length_mm':30.,'measured_real_tool':False},
            'stages':[],'tools':[],'tool_withdrawals':[],'fasteners':[],
            'limitations':['arm fixed at supplied mid pose','USB cable disconnected during carrier service','operator hands and torque/bit engagement not certified','sampled straight insertion paths are not continuous path proof']}
    base={'CAM4_BASE':p['CAM4_BASE']}
    report['stages'].append(sweep('B1 base placed from above, carrier absent',base,arm,(0,0,1),30,[('CAM4_BASE','PG3_XL430_fixed')]))
    base_hw={k:v for k,v in p.items() if k.startswith(('CAM4_BASE_TAP','CAM4_BASE_WASHER'))}
    for i,(x,y,z) in enumerate(ANCHORS):
        moving={k:v for k,v in base_hw.items() if k.endswith('_'+str(i))}
        fit=[(a,'CAM4_BASE') for a in moving]+[(a,'PG3_XL430_fixed') for a in moving if 'TAP' in a]
        report['stages'].append(sweep(f'B2 base fastener {i} from above',moving,arm|base,(0,0,1),16,fit))
        pos=(x,y,TOP+4.55)
        tsh=tool(pos,(0,0,1))
        # The tool starts 0.05mm outside the head; socket fit is a separate unknown.
        obs=arm|base|base_hw
        rr=check_pose({f'TOOL_BASE_{i}':tsh},obs,fit_pairs=[(f'TOOL_BASE_{i}',f'CAM4_BASE_TAP_{i}')])
        report['tools'].append({'name':f'B3 base screw {i}','direction':[0,0,1],'obstacles':len(obs),'failures':[r for r in rr if r['status']!='PASS']})
        out=check_pose({f'PULLOUT_BASE_{i}':tool(pos,(0,0,1),travel=30)},obs,fit_pairs=[(f'PULLOUT_BASE_{i}',f'CAM4_BASE_TAP_{i}')])
        report['tool_withdrawals'].append({'name':f'BASE_{i}','travel_mm':30,'method':'exact_axial_cylinder_sweep_union','failures':[r for r in out if r['status']!='PASS']})
        report['fasteners'].append({'id':f'base_{i}','candidate':'M2.6 x 5 TAP envelope','quantity':1,'screw_length_mm':5,'seat_material_mm':2,'washer_mm':.5,'penetration_mm':2.5,'bottom_margin_mm':1.5,'complete_thread_engagement_mm':None,'procurement_approved':False})
    carrier_cluster={k:v for k,v in p.items() if k=='CAM4_CARRIER' or k.startswith('CAM4_PCB_') or k.startswith('CAM4_ASSUMED_') and 'USB_PLUG' not in k and 'USB_CABLE' not in k}
    # A: camera-to-carrier screws are installed on the bench before base attachment.
    for i,(x,y) in enumerate([(x,y) for x in (-14,14) for y in (-14,14)]):
        pos=local_point((x,y,-8.75),s)
        tsh=tool(pos,-n)
        rr=check_pose({f'TOOL_PCB_{i}':tsh},carrier_cluster,fit_pairs=[(f'TOOL_PCB_{i}',f'CAM4_PCB_BOLT_{i}')])
        report['tools'].append({'name':f'A1 PCB screw {i}, bench only','direction':(-n).tolist(),'obstacles':len(carrier_cluster),'failures':[r for r in rr if r['status']!='PASS']})
        out=check_pose({f'PULLOUT_PCB_{i}':tool(pos,-n,travel=30)},carrier_cluster,fit_pairs=[(f'PULLOUT_PCB_{i}',f'CAM4_PCB_BOLT_{i}')])
        report['tool_withdrawals'].append({'name':f'PCB_{i}','travel_mm':30,'method':'exact_axial_cylinder_sweep_union','failures':[r for r in out if r['status']!='PASS']})
        report['fasteners'].append({'id':f'pcb_{i}','candidate':'M2 x12 + nut','quantity':1,'stack_mm':{'washer':.3,'pcb':1.6,'printed_standoff':5,'plate':3,'nut':1.6},'nominal_tip_past_nut_mm':.5,'actual_board_verified':False})
    for i,(x,y) in enumerate([(x,y) for x in (-14,14) for y in (-14,14)]):
        pos=local_point((x,y,4.65),s)
        fits=[(f'TOOL_PCB_NUT_{i}',f'CAM4_PCB_NUT_{i}')]
        for travel in [0,30]:
            rr=check_pose({f'TOOL_PCB_NUT_{i}':nut_driver_envelope(pos,n,travel=travel)},carrier_cluster,fit_pairs=fits)
            record={'name':f'PCB counterhold nut {i}','shaft_diameter_mm':7,'mandatory_central_relief_diameter_mm':2.6,'mandatory_central_relief_depth_mm':2,'travel_mm':travel,'obstacles':len(carrier_cluster),'failures':[r for r in rr if r['status']!='PASS']}
            if travel: record['method']='exact_axial_cylinder_sweep_union'
            report['tool_withdrawals' if travel else 'tools'].append(record)
    nutparts={k:v for k,v in p.items() if k.startswith('CAM4_CARRIER_NUT_')}
    for i,sign in enumerate((-1,1)):
        name=f'CAM4_CARRIER_NUT_{i}'
        report['stages'].append(sweep(f'B4 nut {i} side loading',{name:p[name]},arm|base|base_hw,(sign,0,0),10,[(name,'CAM4_BASE')]))
    fixed=arm|base|base_hw|nutparts
    report['stages'].append(sweep('C1 preassembled carrier from rear/up normal',carrier_cluster,fixed,n,30,[('CAM4_CARRIER','CAM4_BASE')]))
    for i,x in enumerate((-22,22)):
        m={k:v for k,v in p.items() if k in [f'CAM4_CARRIER_BOLT_{i}',f'CAM4_CARRIER_WASHER_{i}']}
        fits=[(a,b) for a in m for b in ['CAM4_CARRIER','CAM4_BASE',f'CAM4_CARRIER_NUT_{i}']]
        report['stages'].append(sweep(f'C2 carrier screw {i} insertion',m,fixed|carrier_cluster,n,16,fits))
        pos=local_point((x,0,6.55),s)
        tsh=tool(pos,n)
        obs=fixed|carrier_cluster|m
        rr=check_pose({f'TOOL_CARRIER_{i}':tsh},obs,fit_pairs=[(f'TOOL_CARRIER_{i}',f'CAM4_CARRIER_BOLT_{i}')])
        report['tools'].append({'name':f'C3 carrier screw {i}','direction':n.tolist(),'obstacles':len(obs),'failures':[r for r in rr if r['status']!='PASS']})
        out=check_pose({f'PULLOUT_CARRIER_{i}':tool(pos,n,travel=30)},obs,fit_pairs=[(f'PULLOUT_CARRIER_{i}',f'CAM4_CARRIER_BOLT_{i}')])
        report['tool_withdrawals'].append({'name':f'CARRIER_{i}','travel_mm':30,'method':'exact_axial_cylinder_sweep_union','failures':[r for r in out if r['status']!='PASS']})
        report['fasteners'].append({'id':f'carrier_{i}','candidate':'M3 x12 + captured nut','quantity':1,'nut_thickness_mm':2.4,'nominal_tip_past_nut_mm':2.0,'actual_thread_and_load_verified':False})
    # D: plug arrives along +v; cable is separately handled and strain relieved.
    plug={'CAM4_ASSUMED_USB_PLUG':p['CAM4_ASSUMED_USB_PLUG']}
    plugob={k:v for k,v in allparts.items() if k not in plug and k!='CAM4_ASSUMED_USB_CABLE'}
    fits=[('CAM4_ASSUMED_USB_PLUG','CAM4_ASSUMED_USB_PORT'),('CAM4_ASSUMED_USB_PLUG','CAM4_ASSUMED_PCB')]
    report['stages'].append(sweep('D1 diagnostic camera plug from rear edge',plug,plugob,-v,20,fits))
    report['all_nominal_sampled_paths_pass']=all(r['sampled_path_pass'] for r in report['stages'])
    report['all_nominal_tool_envelopes_pass']=all(not r['failures'] for r in report['tools'])
    report['all_tool_withdrawal_envelopes_pass']=all(not r['failures'] for r in report['tool_withdrawals'])
    report['physical_assembly_performed']=False
    (RUN/'reports/service.json').write_text(json.dumps(report,indent=2,default=serial))
    for r in report['stages']:print(r['name'],r['sampled_path_pass'],len(r['failures']),flush=True)
    for r in report['tools']:print(r['name'],'tool',len(r['failures']),flush=True)
    print(json.dumps([r for r in report['stages'] if r['failures']],indent=2,default=serial)[-15000:],flush=True)
    print(json.dumps([r for r in report['tools']+report['tool_withdrawals'] if r['failures']],indent=2,default=serial),flush=True)
    return report

if __name__=='__main__':run()
