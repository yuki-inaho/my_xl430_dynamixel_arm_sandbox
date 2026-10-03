"""Certify ONLY added fixed camera parts vs declared PG3 opening motion.
Finite pose lower bounds + conservative speed*half-step movement bounds.
This is not a full-arm joint-space or physical tolerance certificate.
"""
import json
import math

from gripper_design.camera_overhead_r4 import ORIGIN, RUN, Spec
from scripts.assembly_io import bounds, read_step
from scripts.validate_camera_overhead_r4 import digest


def group(name):
    n=name.removeprefix('PG3_')
    if not name.startswith('PG3_'):return 'fixed'
    if n in ['frame','cap_U','cap_D','XL430_fixed'] or n.startswith(('cap_','case_tapper_')):return 'fixed'
    if n.startswith(('carriage_','finger_','pad_','pivot_carriage_')):return 'L' if '_L' in n else 'R'
    if n in ['link_R','link_L']:return n
    if n.startswith('pivot_drive_') and n.endswith('_washer'):return 'pin_L' if '_L_' in n else 'pin_R'
    if n in ['crank','horn_spacer','XL430_horn'] or n.startswith(('horn_bolt_','pivot_drive_')):return 'drive'
    raise ValueError('unclassified mechanism '+name)


def speed_bound(g,b):
    r=14.;L=24.;root=math.sqrt(L*L-r*r)
    if g in ['L','R']:return r+r*r/(2*root)
    if g.startswith('pin_'):return r
    pin_y=(14 if g=='link_R' else -14) if g.startswith('link') else 0
    radius=max(math.hypot(x,y-pin_y) for x in [b[0],b[3]] for y in [b[1],b[4]])
    return radius if g=='drive' else r+r/root*radius


def run():
    source=RUN/'reports/geometry.json';geo=json.loads(source.read_text())
    if not geo['local_geometric_checks_pass']:raise ValueError('requires passing current sampled material-first validation')
    rows=read_step(RUN/'CAD/ID5_camera_mid_ASSEMBLY.step')[2]
    motion=[]
    for row in rows:
        g=group(row.name)
        if g=='fixed':continue
        local=row.world.translate(tuple(-v for v in ORIGIN)).rotate((0,0,0),(1,0,0),90)
        speed=speed_bound(g,bounds(local))
        motion.append({'part':row.name,'group':g,'conservative_point_speed_mm_per_rad':speed})
    maxspeed=max(x['conservative_point_speed_mm_per_rad'] for x in motion)
    nearest=math.radians(geo['motion']['step_deg']/2)
    observed=geo['motion']['minimum_measured_or_bounded_gap_mm']
    loss=maxspeed*nearest
    result={'revision':Spec().revision,'saved_mid_sha':geo['saved_mid_sha'],'checker_sha':digest(__file__),'sampled_geometry_sha':digest(source),
            'scope':'fixed new CAM4 parts versus all moving PG3 parts over 25..135 degrees only; all other arm joints fixed; ideal rigid geometry',
            'motion_groups':motion,'sample_count':geo['motion']['pose_count'],'maximum_distance_to_nearest_sample_rad':nearest,
            'maximum_speed_bound_mm_per_rad':maxspeed,'maximum_between_sample_distance_loss_mm':loss,
            'sampled_distance_lower_bound_mm':observed,'continuous_distance_lower_bound_mm':observed-loss,
            'required_gap_mm':.3,'pass':observed-loss>.3,'method':'distance is 1-Lipschitz under bounded point motion; link point p(theta)=pin(theta)+R(phi(theta))*(p0-pin0), |pin_prime|=r, |phi_prime|<=r/sqrt(L^2-r^2). Slider derivative <= r+r^2/(2sqrt(L^2-r^2)). All local points bounded by their exact axis-aligned box.',
            'not_proven':['other joints moving','part deflection','manufacturing variation','mechanism internal collisions','unmodeled real camera or cable']}
    (RUN/'reports/continuous_clearance.json').write_text(json.dumps(result,indent=2))
    print('certified',result['pass'],'gap lower bound',observed-loss,'speed bound',maxspeed,flush=True)
    return result

if __name__=='__main__':run()
