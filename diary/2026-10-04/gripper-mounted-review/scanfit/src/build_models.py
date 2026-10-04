"""Build editable B-rep primitive envelopes in mm and GLB meshes in metres."""
from pathlib import Path
import json, math
import numpy as np
from scipy.optimize import least_squares
import cadquery as cq
import trimesh
ROOT=Path(__file__).resolve().parents[1]

PHYSICAL={'cot_L':(145,180,211),'cot_R':(145,180,211),'foam_L':(47,47,43),'foam_R':(47,47,43),'band_L':(231,130,44),'band_R':(231,130,44)}
DISPLAY={'cot_L':(36,176,238),'cot_R':(36,176,238),'foam_L':(246,171,54),'foam_R':(246,171,54),'band_L':(210,76,188),'band_R':(210,76,188)}

def cot(p):
    z0=p['z_base'];zj=p['z_shoulder'];zt=p['z_tip'];cx=p['cx0'];cy=p['cy0'];tx=p['tilt_x_per_z'];ty=p['tilt_y_per_z'];yaw=p['yaw_rad']
    def wire(z,rx,ry):
        return cq.Workplane('XY',origin=(0,0,z)).ellipse(rx,ry).val().rotate((0,0,0),(0,0,1),math.degrees(yaw)).translate((cx+tx*(z-z0),cy+ty*(z-z0),0))
    body=cq.Solid.makeLoft([wire(z0,p['rx_base'],p['ry_base']),wire(zj,p['rx_shoulder'],p['ry_shoulder'])])
    rx=p['rx_shoulder'];ry=p['ry_shoulder'];h=zt-zj;co=math.cos(yaw);si=math.sin(yaw)
    # Affine image of an upper hemisphere. This is a true smooth B-rep ellipsoid cap.
    M=cq.Matrix([[co*rx,-si*ry,tx*h,cx+tx*(zj-z0)],[si*rx,co*ry,ty*h,cy+ty*(zj-z0)],[0,0,h,zj],[0,0,0,1]])
    dome=cq.Solid.makeSphere(1,angleDegrees1=0,angleDegrees2=90).transformGeometry(M)
    return body.fuse(dome).clean()

def rounded_wire(cx,cy,z,width,depth,radius=1.0):
    wire=cq.Workplane('XY',origin=(cx,cy,z)).rect(width,depth).val()
    return wire.fillet2D(radius,wire.Vertices())

def prism(rows,radius=1.0):
    return cq.Solid.makeLoft([rounded_wire(*row,radius=radius) for row in rows],ruled=True)

def cut_above_plane_y(shape,A,B):
    tool=cq.Workplane('YZ').polyline([(-60,A-60*B),(60,A+60*B),(60,180),(-60,180)]).close().extrude(200,both=True).val()
    return shape.cut(tool)

def cut_above_plane_x(shape,A,B):
    tool=cq.Workplane('XZ').polyline([(-70,A-70*B),(70,A+70*B),(70,180),(-70,180)]).close().extrude(200,both=True).val()
    return shape.cut(tool)

def foam(p):
    a=prism(p['lower_sections'],p['edge_radius'])
    for plane in p['foot_top_cuts']:
        fn=cut_above_plane_y if plane['axis']=='y' else cut_above_plane_x
        a=fn(a,plane['A'],plane['B'])
    cp=p['stalk_top_cot'];cx,cy,z,rx,ry=p['stalk_bottom_ellipse']
    bottom=cq.Workplane('XY',origin=(cx,cy,z)).ellipse(rx,ry).val()
    top=cq.Workplane('XY',origin=(0,0,cp['z_base']+.05)).ellipse(cp['rx_base']+.15,cp['ry_base']+.15).val().rotate((0,0,0),(0,0,1),math.degrees(cp['yaw_rad'])).translate((cp['cx0'],cp['cy0'],0))
    b=cq.Solid.makeLoft([bottom,top]);sh=a.fuse(b).clean()
    lo,hi=p['visible_tab_relief']
    box=cq.Solid.makeBox(hi[0]-lo[0],hi[1]-lo[1],hi[2]-lo[2],cq.Vector(*lo))
    return sh.cut(box).clean()

def band_fit(points):
    qlo,qhi=np.percentile(points[:,:2],[1,99],axis=0);center=(qlo+qhi)/2;r=(qhi-qlo)/2
    def err(p):
        xy=points[:,:2]-p[:2]
        th=p[4];co=np.cos(th);si=np.sin(th);u=xy[:,0]*co+xy[:,1]*si;v=-xy[:,0]*si+xy[:,1]*co
        n=np.sqrt((u/p[2])**2+(v/p[3])**2)
        return (n-1)*np.sqrt(p[2]*p[3])
    p0=np.r_[center,r,0.];res=least_squares(err,p0,loss='soft_l1',f_scale=.8,bounds=([center[0]-4,center[1]-4,7,13,-.3],[center[0]+4,center[1]+4,16,23,.3]))
    p=res.x;xy=points[:,:2]-p[:2];co=np.cos(p[4]);si=np.sin(p[4]);u=xy[:,0]*co+xy[:,1]*si;v=-xy[:,0]*si+xy[:,1]*co;th=np.arctan2(v/p[3],u/p[2]);A=np.stack([np.ones(len(th)),np.cos(th),np.sin(th),np.cos(2*th),np.sin(2*th)],axis=1)
    zfit=least_squares(lambda a:A@a-points[:,2],np.linalg.lstsq(A,points[:,2],rcond=None)[0],loss='soft_l1',f_scale=1.2)
    thickness=1.2;width=float(np.clip(2*np.percentile(abs(A@zfit.x-points[:,2]),80),3.5,6.))
    return {'cx':float(p[0]),'cy':float(p[1]),'rx':float(p[2]),'ry':float(p[3]),'yaw_rad':float(p[4]),'z_harmonics':zfit.x.tolist(),'radial_thickness_mm':thickness,'band_width_mm':width,'thickness_status':'chosen visualization thickness; not measured material thickness','radial_residual_median_mm':float(np.median(abs(err(p))))}

def band(p):
    # A planar elliptic ribbon is deliberately used instead of an invalid
    # closed 3-D rectangular sweep. Second harmonics remain measurement metadata.
    rx,ry=p['rx'],p['ry'];t=p['radial_thickness_mm'];w=p['band_width_mm']
    outer=cq.Workplane('XY').ellipse(rx+t/2,ry+t/2).extrude(w).val().translate((0,0,-w/2))
    inner=cq.Workplane('XY').ellipse(rx-t/2,ry-t/2).extrude(w+2).val().translate((0,0,-w/2-1))
    sh=outer.cut(inner)
    co,si=np.cos(p['yaw_rad']),np.sin(p['yaw_rad']);a,b,c,_,_=p['z_harmonics']
    M=cq.Matrix([[co,-si,0,p['cx']],[si,co,0,p['cy']],[b/rx,c/ry,1,a],[0,0,0,1]])
    p['geometric_model']='planar elliptical ribbon with first-harmonic tilt; second harmonics not modeled'
    return sh.transformGeometry(M)

def mesh_from_shape(s):
    vertices,faces=s.tessellate(.12,.13)
    m=trimesh.Trimesh(np.array([v.toTuple() for v in vertices]),np.asarray(faces),process=True)
    if not m.is_watertight: m.fill_holes()
    m.fix_normals()
    return m

def cot_mesh(p,n=128):
    z0,zj,zt=p['z_base'],p['z_shoulder'],p['z_tip']
    zz=list(np.linspace(z0,zj,10))
    aa=list(np.linspace(0,np.pi/2,25)[1:-1]);zz+=list(zj+(zt-zj)*np.sin(aa))
    theta=np.arange(n)*2*np.pi/n;co,si=np.cos(p['yaw_rad']),np.sin(p['yaw_rad'])
    verts=[]
    for z in zz:
        if z<=zj:
            frac=(z-z0)/(zj-z0);rx=p['rx_base']*(1-frac)+p['rx_shoulder']*frac;ry=p['ry_base']*(1-frac)+p['ry_shoulder']*frac
        else:
            frac=np.sqrt(max(0,1-((z-zj)/(zt-zj))**2));rx=p['rx_shoulder']*frac;ry=p['ry_shoulder']*frac
        x=rx*np.cos(theta);y=ry*np.sin(theta)
        verts.extend(np.stack([co*x-si*y+p['cx0']+p['tilt_x_per_z']*(z-z0),si*x+co*y+p['cy0']+p['tilt_y_per_z']*(z-z0),np.full(n,z)],1))
    faces=[]
    for j in range(len(zz)-1):
        for i in range(n):
            a=j*n+i;b=j*n+(i+1)%n;c=(j+1)*n+(i+1)%n;d=(j+1)*n+i
            faces.extend([[a,b,c],[a,c,d]])
    bottom=len(verts);verts.append([p['cx0'],p['cy0'],z0]);top=len(verts);verts.append([p['cx0']+p['tilt_x_per_z']*(zt-z0),p['cy0']+p['tilt_y_per_z']*(zt-z0),zt])
    for i in range(n):
        faces.append([bottom,(i+1)%n,i]);a=(len(zz)-1)*n+i;b=(len(zz)-1)*n+(i+1)%n;faces.append([top,a,b])
    m=trimesh.Trimesh(np.array(verts),np.array(faces),process=True);m.fix_normals()
    if not m.is_watertight:raise ValueError('Analytic cot tessellation not closed')
    return m


def main():
    pp=json.loads((ROOT/'results/parameters_initial.json').read_text());parts=pp['components']
    # Section rows = cx, cy, z, width X, depth Y. Limits derived from recorded scan quantiles.
    parts['foam_L'].update({'lower_sections':[[-28.,-.4,38.8,21.4,29.4],[-28.5,-1.2,50.8,23.,25.8]],'upper_sections':[[-25.,-2.9,49.6,17.,20.],[-23.8,-3.7,62.1,19.,18.2]],'edge_radius':1.0,'fit_method':'section-quantile initialization, piecewise rounded prism envelope; no claim of hidden surfaces'})
    parts['foam_R'].update({'lower_sections':[[22.9,-1.,37.9,23.7,29.5],[21.3,-1.7,54.1,23.,25.2]],'upper_sections':[[18.9,-2.5,52.5,20.1,22.8],[16.7,-3.7,63.0,20.,20.]],'edge_radius':1.0,'fit_method':'section-quantile initialization, piecewise rounded prism envelope; no claim of hidden surfaces'})
    parts['foam_L'].update({'foot_top_cuts':[{'axis':'x','A':68.2,'B':.5},{'axis':'y','A':56.,'B':-.8},{'axis':'y','A':55.,'B':.5}],'stalk_bottom_ellipse':[-25.,-2.9,49.2,8.7,10.4],'stalk_top_cot':parts['cot_L'],'visible_tab_relief':[[-29.1,-19,37.5],[-24.,-10.4,45.0]]})
    parts['foam_R'].update({'foot_top_cuts':[{'axis':'x','A':63.2,'B':-.35},{'axis':'y','A':60.,'B':-.8},{'axis':'y','A':58.,'B':.35}],'stalk_bottom_ellipse':[18.9,-2.5,52.3,10.1,11.4],'stalk_top_cot':parts['cot_R'],'visible_tab_relief':[[20.6,-20,37.5],[25.6,-10.2,45.0]]})
    d=np.load(ROOT/'inputs/scan_cad_mm.npz');ann=np.load(ROOT/'annotations/selected_vertex_ids.npz')
    for side in ['L','R']:
        parts['band_'+side].update(band_fit(d['vertices'][ann['band_'+side]]))
    shapes={};validation={};meshes={}
    for name,p in parts.items():
        kind=name.split('_')[0];sh=globals()[kind](p)
        valid=sh.isValid();solids=len(sh.Solids());vol=sh.Volume();print(name,'valid',valid,'solids',solids,'volume',vol,flush=True)
        if not valid or solids!=1 or vol<=0:raise ValueError('Invalid component '+name)
        shapes[name]=sh;bb=sh.BoundingBox();p['export_bbox_mm']={'min':[bb.xmin,bb.ymin,bb.zmin],'max':[bb.xmax,bb.ymax,bb.zmax],'size':[bb.xlen,bb.ylen,bb.zlen]}
        cq.exporters.export(sh,str(ROOT/'models'/f'{name}.step'))
        m=cot_mesh(p) if kind=='cot' else mesh_from_shape(sh);m.visual.face_colors=(*PHYSICAL[name],255);meshes[name]=m
        m.export(str(ROOT/'models'/f'{name}.stl'))
        re=cq.importers.importStep(str(ROOT/'models'/f'{name}.step')).val()
        validation[name]={'valid_after_step_reimport':re.isValid(),'solids':len(re.Solids()),'volume_mm3':re.Volume(),'relative_volume_roundtrip_error':abs(re.Volume()-vol)/vol,'mesh_vertices':len(m.vertices),'mesh_faces':len(m.faces),'mesh_watertight':bool(m.is_watertight),'mesh_volume_relative_error':float(abs(m.volume-vol)/vol)}
    assembly=cq.Assembly(name='scan_fitted_soft_addons_mm')
    for name,s in shapes.items():assembly.add(s,name=name,color=cq.Color(*[v/255 for v in PHYSICAL[name]]))
    assembly.export(str(ROOT/'models/soft_addons_scanfit.step'))
    # Reference frame only: known imported B-reps; moving rigid geometry is not inferred.
    refroot=ROOT/'inputs/reference_cad'
    frame=cq.importers.importStep(str(refroot/'01_frame.step')).val();cap=cq.importers.importStep(str(refroot/'02_cap.step')).val()
    refs={'reference_frame':frame,'reference_cap_back':cap,'reference_cap_front':cap.rotate((0,0,0),(0,0,1),180)}
    for name,s in refs.items():assembly.add(s,name=name,color=cq.Color(.82,.82,.78))
    assembly.export(str(ROOT/'models/soft_addons_with_reference_frame.step'))
    for side in ['L','R']:
        ass=cq.Assembly(name=f'photo_{side}_soft_addons')
        for name,s in shapes.items():
            if name.endswith(side):ass.add(s,name=name,color=cq.Color(*[v/255 for v in PHYSICAL[name]]))
        ass.export(str(ROOT/'models'/f'soft_addons_{side}.step'))
    # Geometry units: STEP/STL mm with Z up; GLB metres with Y up (x,z,-y).
    scene=trimesh.Scene()
    glb_rotation=np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]],float)
    scene.metadata['coordinate_note']='GLB metres, +Y up; CAD mm uses +Z up; GLB=(CAD_x,CAD_z,-CAD_y)/1000'
    for name,m in meshes.items():
        mm=m.copy();mm.apply_scale(.001);mm.apply_transform(glb_rotation);scene.add_geometry(mm,node_name=name,geom_name=name)
    scene.export(ROOT/'models/soft_addons_scanfit.glb')
    frame_scene=scene.copy()
    for name,s in refs.items():
        m=mesh_from_shape(s);m.visual.face_colors=(219,221,211,255);m.apply_scale(.001);m.apply_transform(glb_rotation);frame_scene.add_geometry(m,node_name=name,geom_name=name)
    frame_scene.export(ROOT/'models/soft_addons_with_reference_frame.glb')
    np.savez_compressed(ROOT/'results/model_meshes.npz',**{f'{n}_{k}':a for n,m in meshes.items() for k,a in [('vertices',m.vertices),('faces',m.faces)]})
    (ROOT/'results/parameters.json').write_text(json.dumps(pp,indent=2))
    (ROOT/'results/step_validation.json').write_text(json.dumps(validation,indent=2))
    print(json.dumps(validation,indent=2))
if __name__=='__main__':main()
