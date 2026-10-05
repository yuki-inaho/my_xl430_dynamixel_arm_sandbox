"""PG3 C92: compact upright XL430 parallel gripper, millimetres.
Construction: X opening, Y up, Z forward. Export: X opening, Z up, -Y forward.
No actuator commands. All parts are independently printable, not print-in-place.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import math
import cadquery as cq
import numpy as np
ROOT=Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Parameters:
    servo: str='XL430-W250'
    width: float=92.0
    frame_height: float=56.0
    r: float=14.0
    L: float=24.0
    theta_open: float=25.0
    theta_close: float=135.0
    jaw_inner: float=10.5
    pad: float=1.0
    finger_start: float=32.7
    finger_mount_z: float=33.0
    finger_end: float=44.8
    finger_nut_z: float=20.8
    link_bow: float=4.5
    link_width: float=5.0
    link_thickness: float=3.2
    link_bore: float=5.4
    shoulder_d: float=5.0
    shoulder_base: float=26.0
    shoulder_top: float=29.8
    guide_gap: float=0.6
    revision: str='PG3-C92-X430-C7'
    def validate(self):
        for v in asdict(self).values():
            if isinstance(v,(int,float)) and not math.isfinite(v): raise ValueError('nonfinite')
        checks = [
            (self.servo == 'XL430-W250', 'wrong servo family'),
            (self.width == 92 and self.frame_height == 56, 'unreviewed frame dimensions'),
            (0 < self.r < self.L, 'invalid kinematics'),
            (self.theta_open == 25 and self.theta_close == 135, 'unreviewed motion interval'),
            (opening(self.theta_open, self) >= 48, 'cannot shrink aperture to pass size gate'),
            (.3 <= opening(self.theta_close, self) <= 1.5, 'closed aperture out of bounds'),
            (self.link_bore > self.shoulder_d, 'interference pivot fit'),
            (self.shoulder_top-self.shoulder_base > self.link_thickness, 'link clamped by fastener'),
        ]
        for ok, reason in checks:
            if not ok: raise ValueError(reason)

P=Parameters()

def box(x0,x1,y0,y1,z0,z1):
    if min(x1-x0,y1-y0,z1-z0)<=0: raise ValueError('bad box')
    return cq.Solid.makeBox(x1-x0,y1-y0,z1-z0,cq.Vector(x0,y0,z0))
def cyl(r,h,p=(0,0,0),d=(0,0,1)):
    return cq.Solid.makeCylinder(r,h,cq.Vector(*p),cq.Vector(*d))
def cut(s,*ts):
    for t in ts:s=s.cut(t)
    return s.clean()
def fuse(*ss):return ss[0].fuse(*ss[1:]).clean()
def poly(pts,z,h):return cq.Workplane('XY',origin=(0,0,z)).polyline(pts).close().extrude(h).val()
def hexagon(x,y,z,af,h):return cq.Workplane('XY',origin=(x,y,z)).polygon(6,af*2/math.sqrt(3)).extrude(h).val()
def capsule(a,b,r,z,h):
    a,b=np.array(a,float),np.array(b,float);v=b-a;length=np.linalg.norm(v)
    if length<1e-9:return cyl(r,h,(*a,z))
    n=np.array([-v[1],v[0]])*r/length
    return fuse(poly([tuple(a+n),tuple(b+n),tuple(b-n),tuple(a-n)],z,h),cyl(r,h,(*a,z)),cyl(r,h,(*b,z)))
def mirror(s):return s.mirror('YZ')
def turn(s,a):return s.rotate((0,0,0),(0,0,1),a)
def world(s):return s.rotate((0,0,0),(1,0,0),90)
def bounds(s):
    b=s.BoundingBox();return [b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax]
def pos(a,p=P):
    t=math.radians(a);return p.r*math.cos(t)+math.sqrt(p.L**2-(p.r*math.sin(t))**2)
def derivative(a,p=P):
    t=math.radians(a);q=math.sqrt(p.L**2-(p.r*math.sin(t))**2)
    return -p.r*math.sin(t)-p.r**2*math.sin(t)*math.cos(t)/q

def opening(a,p=P):return 2*(pos(a,p)-p.jaw_inner-p.pad)

def frame(p=P):
    w=p.width/2;hh=p.frame_height/2
    s=box(-w,w,-hh,hh,17,19.5)
    s=cq.Workplane(obj=s).edges('|Z').fillet(.8).val()
    for k in(-1,1):
        c=box(16,42,-16.5,16.5,16.8,19.7)
        s=cut(s,c if k==1 else mirror(c))
    s=cut(s,cyl(10.65,3,(0,0,16.8)))
    # Case-front pilot holes from the supplied XL430 B-rep, not XL330 holes.
    for x in(-11,11):
        s=cut(s,cyl(1.45,3,(x,-8,16.8)),cq.Solid.makeCone(1.45,2.75,1.3,cq.Vector(x,-8,18.2)))
    # Rails have continuous outside lands: fasteners lie outside the moving shoes.
    for k in(-1,1):
        s=fuse(s,box(-w,w,22,hh,19.5,24.1) if k==1 else box(-w,w,-hh,-22,19.5,24.1))
        for j in(-1,1):
            end=box(44,46,18.5,22,19.5,24.1)
            if k<0:end=end.mirror('XZ')
            if j<0:end=mirror(end)
            s=fuse(s,end)
        for x in(-37.5,37.5):
            y=k*24.5
            s=cut(s,cyl(1.15,8,(x,y,16.8)),hexagon(x,y,16.9,4.35,1.9))
    return s

def cap(p=P,relief=0):
    s=box(-46,46,19,28,24.1,27.1)
    s=cq.Workplane(obj=s).edges('|Z').fillet(.6).val()
    for x in(-37.5,37.5):s=cut(s,cyl(1.15,3.4,(x,24.5,23.9)))
    if relief:s=cut(s,box(-43.9,43.9,18.9,22,24.09,24.1+relief))
    return s

def carriage(p=P):
    z=19.8
    s=fuse(box(-7,7,18,21.7,z,23.8),box(-7,7,-21.7,-18,z,23.8),
           box(4.5,9.6,-18.5,18.5,z,26),
           cyl(4.5,3.1,(0,0,22.9)),box(0,7,-3,3,22.9,26),
           cyl(p.shoulder_d/2,p.shoulder_top-26,(0,0,26)))
    # Rear access for captive M2 nut. Slot is cut from the outside toward pivot.
    s=cut(s,cyl(1.15,7.4,(0,0,22.7)),hexagon(0,0,22.8,4.35,1.85))
    for y in(-14,14):
        s=fuse(s,box(3,9.6,y-3.3,y+3.3,z,p.finger_mount_z))
        s=cut(s,cyl(1.15,p.finger_mount_z-19.6+.4,(6.3,y,19.6)),hexagon(6.3,y,19.7,4.35,p.finger_nut_z+1.6-19.7))
    return s

def finger(p=P):
    origin=(-p.jaw_inner,0,0)
    pl=cq.Plane(origin=origin,xDir=(0,1,0),normal=(1,0,0))
    s=cq.Workplane(pl).center(0,(p.finger_start+p.finger_end)/2).rect(36,p.finger_end-p.finger_start).extrude(5).val()
    s=cq.Workplane(obj=s).edges('|X').fillet(1.5).val()
    hole=cq.Workplane(cq.Plane(origin=(-p.jaw_inner-.1,0,0),xDir=(0,1,0),normal=(1,0,0))).center(0,p.finger_start+6.1).rect(23,5.7).extrude(5.2).val()
    hole=cq.Workplane(obj=hole).edges('|X').fillet(1).val();s=cut(s,hole)
    for y in(-14,14):
        s=fuse(s,box(-p.jaw_inner,9.6,y-3.3,y+3.3,p.finger_mount_z,p.finger_mount_z+3))
        s=cut(s,cyl(1.15,3.5,(6.3,y,p.finger_mount_z-.2)))
    return s

def crank(p=P):
    s=fuse(capsule((-p.r,0),(p.r,0),4.5,20.5,2),cyl(10.1,2,(0,0,20.5)))
    for x in(-p.r,p.r):
        s=fuse(s,cyl(4.5,5.5,(x,0,20.5)),cyl(2.5,3.8,(x,0,26)))
        s=cut(s,cyl(1.15,10,(x,0,20.3)),hexagon(x,0,20.4,4.35,1.9))
    s=cut(s,cyl(4.3,3,(0,0,20.3)))
    for x,y in[(8,0),(-8,0),(0,8),(0,-8)]:s=cut(s,cyl(1.15,3,(x,y,20.3)),cyl(2.15,2,(x,y,22.5)))
    return s

def spacer(p=P):
    s=cut(cyl(10.0,1.5,(0,0,19)),cyl(4.3,2,(0,0,18.8)))
    for x,y in[(8,0),(-8,0),(0,8),(0,-8)]:s=cut(s,cyl(1.15,2,(x,y,18.8)))
    return s

def link(p=P):
    pts=[(0,0),(.3*p.L,p.link_bow),(.7*p.L,p.link_bow),(p.L,0)]
    s=fuse(*(capsule(a,b,p.link_width/2,0,p.link_thickness) for a,b in zip(pts,pts[1:])),cyl(4.5,p.link_thickness),cyl(4.5,p.link_thickness,(p.L,0,0)))
    for x in(0,p.L):s=cut(s,cyl(p.link_bore/2,p.link_thickness+.4,(x,0,-.2)))
    return s

def parts(p=P):
    p.validate();c=carriage(p);f=finger(p)
    d={'01_frame':frame(p),'02_cap':cap(p),'03_carriage_R':c,'04_carriage_L':mirror(c),
       '05_finger_R':f,'06_finger_L':mirror(f),'07_crank':crank(p),'08_link':link(p),'09_horn_spacer':spacer(p)}
    for n,s in d.items():
        if not s.isValid() or len(s.Solids())!=1 or s.Volume()<=0:raise ValueError('invalid part '+n)
    return d

@dataclass
class Item:
    name:str
    shape:cq.Shape
    group:str
    kind:str
    color:tuple
COLORS={'frame':(.24,.25,.29),'jaw':(.90,.28,.10),'link':(.23,.64,.25),'crank':(.16,.39,.76),'metal':(.65,.69,.72),'motor':(.17,.18,.21),'pad':(.09,.10,.11)}
def washer(x,y,z):return cut(cyl(2.5,.3,(x,y,z)),cyl(1.1,.5,(x,y,z-.1)))
def pivot_retainer(x,y,z):return cut(cyl(3.5,.5,(x,y,z)),cyl(1.1,.7,(x,y,z-.1)))
def nut(x,y,z):return cut(hexagon(x,y,z,4,1.6),cyl(1,1.8,(x,y,z-.1)))
def bolt(x,y,seat,L,d=2,head=3.8,hh=2.0):
    s=fuse(cyl(d/2,L,(x,y,seat-L)),cyl(head/2,hh,(x,y,seat)))
    return cut(s,hexagon(x,y,seat+hh-.9,1.5,.95))
def flat_tapper(x,y):
    return fuse(cyl(1.3,3.7,(x,y,14.35)),cq.Solid.makeCone(1.3,2.6,1.3,cq.Vector(x,y,18.05)))

from functools import lru_cache
@lru_cache(maxsize=1)
def motor_parts():
    src=cq.importers.importStep(str(ROOT/'reference/XL430_from_supplied_arm.step')).val()
    mask=cyl(10.3,6,(0,0,15.5))
    # Separating only the front horn to visualize its rotation; keep raw input as provenance.
    return cut(src,mask),src.intersect(mask)

def assembled(a,p=P,d=None,hardware=True,motor=True,world_coords=False):
    p.validate()
    if not p.theta_open<=a<=p.theta_close:raise ValueError('angle outside admitted interval')
    d=parts(p) if d is None else d;t=math.radians(a);x=pos(a,p)
    A=np.array([p.r*math.cos(t),p.r*math.sin(t)]);Q=np.array([x,0.])
    phi=math.degrees(math.atan2((Q-A)[1],(Q-A)[0]));items=[]
    def add(n,s,group='fixed',kind='printed',col='frame'):
        items.append(Item(n,world(s) if world_coords else s,group,kind,COLORS[col]))
    add('frame',d['01_frame']);add('cap_U',d['02_cap']);add('cap_D',turn(d['02_cap'],180))
    add('crank',turn(d['07_crank'],a),'drive',col='crank')
    add('horn_spacer',turn(d['09_horn_spacer'],a),'drive',col='crank')
    for sign,lr in[(1,'R'),(-1,'L')]:
        for typ,part in [('carriage','03_carriage_R' if sign>0 else '04_carriage_L'),('finger','05_finger_R' if sign>0 else '06_finger_L')]:
            add(typ+'_'+lr,d[part].translate((sign*x,0,0)),lr,col='jaw')
        pad=box(-p.jaw_inner-p.pad,-p.jaw_inner,-14,14,p.finger_end-3,p.finger_end)
        if sign<0:pad=mirror(pad)
        add('pad_'+lr,pad.translate((sign*x,0,0)),lr,'pad','pad')
        add('link_'+lr,turn(d['08_link'],phi+(180 if sign<0 else 0)).translate((*list(sign*A),26.3)),'link_'+lr,col='link')
    if motor:
        m,h=motor_parts();add('XL430_fixed',m,kind='supplier',col='motor');add('XL430_horn',turn(h,a),'drive','supplier','metal')
    if hardware:
        for nm,pt,grp,z,L in [('pivot_drive_R',A,'drive',20.7,10),('pivot_drive_L',-A,'drive',20.7,10),('pivot_carriage_R',Q,'R',23.05,8),('pivot_carriage_L',-Q,'L',23.05,8)]:
            xx,yy=pt
            add(nm+'_washer',pivot_retainer(xx,yy,29.8),grp,'fastener','metal')
            bb=bolt(xx,yy,30.3,L)
            if grp=='drive':bb=bb.rotate((xx,yy,0),(xx,yy,1),a)
            add(nm+'_bolt',bb,grp,'fastener','metal')
            nn=nut(xx,yy,z)
            if grp=='drive':nn=nn.rotate((xx,yy,0),(xx,yy,1),a)
            add(nm+'_nut',nn,grp,'fastener','metal')
        for xx in(-37.5,37.5):
            for yy in(-24.5,24.5):
                nm=f'cap_{xx}_{yy}'
                add(nm+'_washer',washer(xx,yy,27.1),kind='fastener',col='metal')
                add(nm+'_bolt',bolt(xx,yy,27.4,12),kind='fastener',col='metal')
                add(nm+'_nut',nut(xx,yy,17.2),kind='fastener',col='metal')
        for sign,lr in[(1,'R'),(-1,'L')]:
            for yy in(-14,14):
                xx=sign*(x+6.3);nm=f'finger_{lr}_{yy}'
                add(nm+'_washer',washer(xx,yy,p.finger_mount_z+3),lr,'fastener','metal')
                add(nm+'_bolt',bolt(xx,yy,p.finger_mount_z+3.3,16),lr,'fastener','metal')
                add(nm+'_nut',nut(xx,yy,p.finger_nut_z),lr,'fastener','metal')
        for i,(xx,yy) in enumerate([(8,0),(-8,0),(0,8),(0,-8)]):
            b=turn(bolt(xx,yy,22.5,6),a);add('horn_bolt_'+str(i),b,'drive','fastener','metal')
        for xx in(-11,11):add('case_tapper_'+str(xx),flat_tapper(xx,-8),kind='fastener',col='metal')
    return items

PRINT_COUNTS={'01_frame':1,'02_cap':2,'03_carriage_R':1,'04_carriage_L':1,'05_finger_R':1,'06_finger_L':1,'07_crank':1,'08_link':2,'09_horn_spacer':1}
def print_orientation(n,s):
    if 'carriage_R' in n:s=s.rotate((0,0,0),(0,1,0),90) # flat outer X side on bed
    elif 'carriage_L' in n:s=s.rotate((0,0,0),(0,1,0),-90)
    elif 'finger_R' in n:s=s.rotate((0,0,0),(0,1,0),-90)
    elif 'finger_L' in n:s=s.rotate((0,0,0),(0,1,0),90)
    b=bounds(s);return s.translate((-(b[0]+b[3])/2,-(b[1]+b[4])/2,-b[2]))
