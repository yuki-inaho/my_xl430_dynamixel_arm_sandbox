"""ID5 overhead, fixed-angle, two-part mount. Units mm; world is the supplied arm.

This module deliberately does not call the rejected P05 camera factory.
All hardware/camera envelopes are declared nominal assumptions, not purchased parts.
"""
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import cadquery as cq
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'outputs/pg3-id5-p05-windows-r2/ID5_mid_P05_windows_CANDIDATE.step'
RUN = ROOT / 'outputs/camera-mount-id5-overhead-r4'
ORIGIN = (-0.2, 164.9, 164.6)
TOP = 199.85
ANCHORS = tuple((x, y, TOP) for x in (-8.2, 7.8) for y in (158.9, 170.9))


@dataclass(frozen=True)
class Spec:
    revision: str = 'ID5-CAM-R4-C2'
    motor: str = 'XL430-W250-T'
    parent: str = 'fixed_case_external_top_holes'
    extra_motor_count: int = 0
    pitch_deg: float = 63.0
    camera_pitch_mm: float = 28.0
    plate_center: tuple = (-0.2, 177.9, 238.0)
    base_seat_thickness: float = 2.0
    base_screw_length: float = 5.0
    board_thickness: float = 1.6
    board_clearance: float = 5.0
    lens_length: float = 12.0
    board_side: float = 32.0
    hole_depth: float = 4.0
    structural_mass_rating_kg: object = None
    actual_camera_model: object = None


def screw_stack(length, thickness, washer, depth):
    vals=(length, thickness, washer, depth)
    if not all(math.isfinite(x) and x >= 0 for x in vals):
        raise ValueError('non-finite/negative screw stack')
    penetration=length-thickness-washer
    margin=depth-penetration
    if penetration <= 0 or margin < 0.5:
        raise ValueError('screw has no penetration or insufficient bottom margin')
    return {'penetration_mm':penetration,'bottom_margin_mm':margin,
            'actual_thread_strength_verified':False,
            'complete_thread_engagement_mm':None}


def validate_spec(s):
    if s.motor!='XL430-W250-T' or s.parent!='fixed_case_external_top_holes':
        raise ValueError('wrong motor or rotating/case-tie anchor')
    if s.extra_motor_count!=0 or s.camera_pitch_mm!=28:
        raise ValueError('single-ID5 / camera 28 mm contract')
    if not math.isfinite(s.pitch_deg) or not 40<=s.pitch_deg<=75:
        raise ValueError('camera must look forward and downward')
    if s.base_seat_thickness<1.5 or s.board_clearance<4:
        raise ValueError('seat material or component keepout too small')
    if not .8<=s.board_thickness<=2 or s.board_side!=32:
        raise ValueError('outside declared diagnostic camera envelope; redesign required')
    if not all(math.isfinite(x) for x in s.plate_center):
        raise ValueError('non-finite camera position')
    screw_stack(s.base_screw_length,s.base_seat_thickness,.5,s.hole_depth)


def basis(pitch_deg):
    t=math.radians(pitch_deg)
    return np.array((1.,0,0)),np.array((0,math.sin(t),math.cos(t))),np.array((0,-math.cos(t),math.sin(t)))


def box(x0,x1,y0,y1,z0,z1):
    if min(x1-x0,y1-y0,z1-z0)<=0: raise ValueError('degenerate box')
    return cq.Solid.makeBox(x1-x0,y1-y0,z1-z0,cq.Vector(x0,y0,z0))


def cylinder(radius, length, pos, direction=(0,0,1)):
    return cq.Solid.makeCylinder(radius,length,cq.Vector(*pos),cq.Vector(*direction))


def local_to_world(shape, s):
    # Plane axes: u=X, v=(0,sin(p),cos(p)), normal=(0,-cos(p),sin(p)).
    return shape.rotate((0,0,0),(1,0,0),90-s.pitch_deg).translate(s.plate_center)


def local_point(p,s):
    u,v,n=basis(s.pitch_deg)
    return np.array(s.plate_center)+u*p[0]+v*p[1]+n*p[2]


def hexagon(radius,height,pos=(0,0,0)):
    return cq.Workplane('XY').polygon(6,2*radius).extrude(height).val().translate(pos)


def cut_many(shape,cutters):
    for c in cutters: shape=shape.cut(c)
    return shape.clean()


def base(s):
    """Flat foot, two continuous cheeks, captive nuts loaded from outer sides."""
    b=box(-26.2,25.8,152.9,176.9,TOP,TOP+3)
    # Round only the outer vertical edges of the unperforated foot.
    b=cq.Workplane(obj=b).edges('|Z').fillet(2).val()
    top_a=local_point((0,-6,0),s); top_b=local_point((0,6,0),s)
    profile=[(154.9,TOP+2.5),(176.9,TOP+2.5),
             (float(top_b[1]),float(top_b[2])),(float(top_a[1]),float(top_a[2]))]
    for sign in (-1,1):
        cx=s.plate_center[0]+22*sign
        pl=cq.Plane(origin=(cx-4,0,0),xDir=(0,1,0),normal=(1,0,0))
        cheek=cq.Workplane(pl).polyline(profile).close().extrude(8).val()
        b=b.fuse(cheek)
    cutters=[]
    for x,y,z in ANCHORS:
        cutters += [cylinder(1.45,6,(x,y,TOP-1)),
                    cylinder(3.25,4,(x,y,TOP+s.base_seat_thickness))]
    for sign in (-1,1):
        x=22*sign
        cutters.append(local_to_world(cylinder(1.65,20,(x,0,-15)),s))
        cutters.append(local_to_world(hexagon(3.4,2.7,(x,0,-6.8)),s))
        a,bx=sorted((x,x+sign*4.5))
        cutters.append(local_to_world(box(a,bx,-3.05,3.05,-6.8,-4.1),s))
    return cut_many(b,cutters)


def carrier_local(s):
    p=box(-26,26,-22,19,0,3)
    p=cq.Workplane(obj=p).edges('|Z').fillet(2).val()
    p=p.cut(box(-12,12,-12,12,-1,4))
    for x in (-14,14):
        for y in (-14,14):
            p=p.fuse(cylinder(2.6,s.board_clearance,(x,y,-s.board_clearance)))
            p=p.cut(cylinder(1.2,s.board_clearance+5,(x,y,-s.board_clearance-1)))
    for x in (-22,22): p=p.cut(cylinder(1.65,5,(x,0,-1)))
    # Rear tie slots sit outside the assumed 32mm PCB projection.
    for x in (-4,4): p=p.cut(box(x-1.25,x+1.25,-20,-18,-1,4))
    return p.clean()


def ring(ro,ri,t,pos):
    return cylinder(ro,t,pos).cut(cylinder(ri,t+2,(pos[0],pos[1],pos[2]-1)))


def bolt_z(diameter,underhead,head_height,head_diameter,seat,pos_xy,positive=False):
    """Envelope with hex socket. positive=False: shaft goes in -Z from seat."""
    x,y=pos_xy
    if not positive:
        shaft=cylinder(diameter/2,underhead,(x,y,seat-underhead))
        head=cylinder(head_diameter/2,head_height,(x,y,seat))
        recess=hexagon(diameter/math.sqrt(3),head_height*.75,(x,y,seat+head_height*.4))
    else:
        shaft=cylinder(diameter/2,underhead,(x,y,seat))
        head=cylinder(head_diameter/2,head_height,(x,y,seat-head_height))
        recess=hexagon(diameter/math.sqrt(3),head_height*.75,(x,y,seat-head_height-.1))
    return shaft.fuse(head.cut(recess)).clean()


def nut_z(af,h,bore,pos):
    return hexagon(af/math.sqrt(3),h,pos).cut(cylinder(bore,h+2,(pos[0],pos[1],pos[2]-1)))


def build(s=None):
    s=s or Spec()
    validate_spec(s)
    p={'CAM4_BASE':base(s),'CAM4_CARRIER':local_to_world(carrier_local(s),s)}
    for i,(x,y,z) in enumerate(ANCHORS):
        p[f'CAM4_BASE_WASHER_{i}']=ring(3,1.4,.5,(x,y,TOP+s.base_seat_thickness))
        p[f'CAM4_BASE_TAP_{i}']=bolt_z(2.6,s.base_screw_length,2,5.2,TOP+s.base_seat_thickness+.5,(x,y))
    for i,x in enumerate((-22,22)):
        p[f'CAM4_CARRIER_WASHER_{i}']=local_to_world(ring(3.5,1.6,.5,(x,0,3)),s)
        p[f'CAM4_CARRIER_BOLT_{i}']=local_to_world(bolt_z(3,12,3,5.5,3.5,(x,0)),s)
        # Top face seated at -4.1. Pocket has 0.3mm thickness clearance on rear side.
        p[f'CAM4_CARRIER_NUT_{i}']=local_to_world(nut_z(5.5,2.4,1.5,(x,0,-6.5)),s)
    board_front=-s.board_clearance-s.board_thickness
    board=box(-16,16,-16,16,board_front,-s.board_clearance)
    for i,(x,y) in enumerate([(x,y) for x in (-14,14) for y in (-14,14)]):
        board=board.cut(cylinder(1.1,4,(x,y,board_front-1)))
        p[f'CAM4_PCB_WASHER_{i}']=local_to_world(ring(2.1,1.1,.3,(x,y,board_front-.3)),s)
        p[f'CAM4_PCB_BOLT_{i}']=local_to_world(bolt_z(2,12,1.8,3.8,board_front-.3,(x,y),True),s)
        p[f'CAM4_PCB_NUT_{i}']=local_to_world(nut_z(4,1.6,1,(x,y,3)),s)
    p['CAM4_ASSUMED_PCB']=local_to_world(board,s)
    p['CAM4_ASSUMED_REAR_COMPONENTS']=local_to_world(box(-11,11,-10,10,-s.board_clearance,-s.board_clearance+3),s)
    p['CAM4_ASSUMED_LENS']=local_to_world(cylinder(7,s.lens_length,(0,0,board_front-s.lens_length)),s)
    # Connector is a parameterized envelope, NOT a purchased camera model.
    p['CAM4_ASSUMED_USB_PORT']=local_to_world(box(-5,5,-16,-10,-s.board_clearance,-s.board_clearance+3.5),s)
    p['CAM4_ASSUMED_USB_PLUG']=local_to_world(box(-5,5,-23,-16,-4.8,-.6),s)
    p['CAM4_ASSUMED_USB_CABLE']=camera_cable(s)
    return p


def cable_path(s):
    _,v,_=basis(s.pitch_deg)
    start=local_point((0,-23,-2.7),s)
    a=start-v*6
    heading=math.radians(270-s.pitch_deg)
    R=12.0
    center=a+np.array((0,R*math.sin(heading),-R*math.cos(heading)))
    start_phi=heading+math.pi/2; end_phi=3*math.pi/2
    # start_phi is 297 degrees; clockwise to 270 gives a tangent-continuous arc.
    def point(phi): return center+np.array((0,R*math.cos(phi),R*math.sin(phi)))
    middle=point((start_phi+end_phi)/2); end=point(end_phi)
    finish=end.copy(); finish[1]=110
    return start,a,middle,end,finish


def camera_cable(s,diameter=3.0):
    start,a,middle,end,finish=cable_path(s)
    edges=[cq.Edge.makeLine(cq.Vector(*start),cq.Vector(*a)),
           cq.Edge.makeThreePointArc(cq.Vector(*a),cq.Vector(*middle),cq.Vector(*end)),
           cq.Edge.makeLine(cq.Vector(*end),cq.Vector(*finish))]
    path=cq.Wire.assembleEdges(edges)
    tangent=a-start; tangent/=np.linalg.norm(tangent)
    pl=cq.Plane(origin=tuple(start),xDir=(1,0,0),normal=tuple(tangent))
    return cq.Workplane(pl).circle(diameter/2).sweep(path).val()


def optical(s):
    _,v,n=basis(s.pitch_deg)
    eye=local_point((0,0,-s.board_clearance-s.board_thickness-s.lens_length),s)
    return {'eye':eye.tolist(),'direction':(-n).tolist(),'up':v.tolist(),
            'reference':'assumed lens front; not calibrated entrance pupil','hfov_actual':None}


def opening_mm(a):
    t=math.radians(a)
    return 2*(14*math.cos(t)+math.sqrt(24**2-(14*math.sin(t))**2)-11.5)


def retained_at(neutral,angle):
    """Move ONLY the existing saved gripper moving groups; retain fixed B-rep."""
    if not 25<=angle<=135: raise ValueError('mechanism angle outside 25..135')
    x=opening_mm(angle)/2+11.5; x90=math.sqrt(24**2-14**2)
    t=math.radians(angle); pin=np.array((14*math.cos(t),14*math.sin(t),0))
    result={}
    for name,s in neutral.items():
        short=name.removeprefix('PG3_')
        group=None
        if name.startswith('PG3_'):
            if short.startswith(('carriage_','finger_','pad_','pivot_carriage_')):
                group='L' if ('_L' in short) else 'R'
            elif short.startswith('link_'): group=short
            elif short in ['crank','horn_spacer','XL430_horn'] or short.startswith(('horn_bolt_','pivot_drive_')):
                group='drive'
                if short.endswith('_washer') and short.startswith('pivot_drive_'):
                    group='pin_L' if '_L_' in short else 'pin_R'
        if group is None or angle==90:
            result[name]=s
            continue
        local=s.translate(tuple(-v for v in ORIGIN)).rotate((0,0,0),(1,0,0),90)
        delta=0.; trans=np.zeros(3)
        if group in ('R','L'): trans[0]=(1 if group=='R' else -1)*(x-x90)
        elif group.startswith('pin_'): trans=(1 if group=='pin_R' else -1)*(pin-np.array((0,14,0)))
        elif group=='drive': delta=angle-90
        else:
            delta=math.degrees(math.atan2(-pin[1],x-pin[0])-math.atan2(-14,x90))
            dt=math.radians(delta); R=np.array([[math.cos(dt),-math.sin(dt),0],[math.sin(dt),math.cos(dt),0],[0,0,1]])
            trans=(1 if group=='link_R' else -1)*(pin-R@np.array((0,14,0)))
        local=local.rotate((0,0,0),(0,0,1),delta).translate(tuple(trans))
        result[name]=local.rotate((0,0,0),(1,0,0),-90).translate(ORIGIN)
    return result


def metadata(s):
    return {'spec':asdict(s),'anchors_world_mm':ANCHORS,'optical':optical(s),
            'base_stack':screw_stack(s.base_screw_length,s.base_seat_thickness,.5,s.hole_depth),
            'physical_tests_performed':[], 'fabrication_approved':False,
            'printed_parts':['CAM4_BASE','CAM4_CARRIER']}