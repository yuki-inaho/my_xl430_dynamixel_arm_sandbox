"""CAD camera renders and segmentation; declared optical hypotheses, no calibration."""
import json
import math

import numpy as np
import vtk
from scipy.optimize import brentq
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray, vtk_to_numpy

from gripper_design.camera_overhead_r4 import RUN, Spec, box, opening_mm, optical, retained_at
from scripts.assembly_io import read_step
from scripts.build_camera_overhead_r4 import color
from scripts.validate_camera_overhead_r4 import digest, pair


class View:
    def __init__(self,shapes,eye,direction,up,hfov,size=(800,600)):
        self.renderer=vtk.vtkRenderer(); self.renderer.SetBackground(0.96,.97,.98)
        self.window=vtk.vtkRenderWindow();self.window.SetOffScreenRendering(True)
        self.window.SetSize(*size);self.window.AddRenderer(self.renderer);self.window.SetMultiSamples(0)
        self.actors={};self.ids={}
        for i,(name,shape) in enumerate(shapes.items(),1):
            vs,fs=shape.tessellate(.08,.15)
            vv=np.array([v.toTuple() for v in vs]);ff=np.array(fs,dtype=np.int64)
            if not len(ff): raise ValueError('empty tessellation '+name)
            pts=vtk.vtkPoints();pts.SetData(numpy_to_vtk(vv,deep=True))
            cells=vtk.vtkCellArray();cells.SetCells(len(ff),numpy_to_vtkIdTypeArray(np.c_[np.full(len(ff),3),ff].ravel(),deep=True))
            pd=vtk.vtkPolyData();pd.SetPoints(pts);pd.SetPolys(cells)
            mapper=vtk.vtkPolyDataMapper();mapper.SetInputData(pd)
            actor=vtk.vtkActor();actor.SetMapper(mapper);self.renderer.AddActor(actor)
            self.actors[name]=actor;self.ids[name]=i
        cam=self.renderer.GetActiveCamera();cam.ParallelProjectionOff()
        cam.SetPosition(eye);cam.SetFocalPoint(np.array(eye)+np.array(direction)*100);cam.SetViewUp(up)
        vfov=math.degrees(2*math.atan(math.tan(math.radians(hfov)/2)*size[1]/size[0]))
        cam.SetViewAngle(vfov);cam.SetClippingRange(.1,1500)
    def capture(self,path=None,seg=False,only=None):
        for n,a in self.actors.items():
            a.SetVisibility(only is None or n in only)
            p=a.GetProperty()
            if seg:
                i=self.ids[n];p.SetColor((i%256)/255,(i//256)/255,0);p.LightingOff()
            else:
                p.SetColor(*( (.90,.65,.22) if n=='DIAGNOSTIC_CUBE' else color(n)));p.LightingOn();p.SetAmbient(.35);p.SetDiffuse(.65)
        self.renderer.SetBackground((1,1,1) if seg else (.96,.97,.98))
        self.window.Render()
        w=vtk.vtkWindowToImageFilter();w.SetInput(self.window);w.ReadFrontBufferOff();w.Update()
        im=w.GetOutput(); ww,hh,_=im.GetDimensions()
        arr=vtk_to_numpy(im.GetPointData().GetScalars()).reshape(hh,ww,3)[::-1].copy()
        if path:
            from PIL import Image
            Image.fromarray(arr).save(path)
        return arr[:,:,0].astype(np.int32)+256*arr[:,:,1].astype(np.int32) if seg else arr
    def close(self):self.window.Finalize()


def category(n):
    if n=='DIAGNOSTIC_CUBE':return 'grasped_cube'
    if n.startswith('CAM4_'):
        return 'camera_cable' if 'USB' in n else 'camera_mount_or_camera'
    if 'pad_' in n:return 'pad'
    if 'finger_' in n and n.startswith('PG3_'):return 'finger'
    if 'link_' in n or 'crank' in n:return 'link_or_crank'
    if 'XL430' in n or n.startswith('ARM_M'):return 'motor'
    return 'arm_or_frame'


def run():
    s=Spec();opt=optical(s)
    path=RUN/'CAD/ID5_camera_mid_ASSEMBLY.step'
    source={r.name:r.world for r in read_step(path)[2]}
    base={n:v for n,v in source.items() if not n.startswith('CAM4_')}
    mount={n:v for n,v in source.items() if n.startswith('CAM4_')}
    report={'revision':s.revision,'saved_mid_sha':digest(path),'checker_sha':digest(__file__),
            'camera':opt,'assumed_horizontal_fov_deg':[50,60,70],'resolution':[800,600],
            'all_source_obstacles_included':True,'physical_camera_validation':False,
            'test_definition':'Both jaw silhouettes and a centred rigid cube; target-only render supplies projected reference. Closed jaws are tested empty, not penetrating a cube.',
            'cases':[]}
    folder=RUN/'images/camera';folder.mkdir(exist_ok=True)
    cases=[('open_empty',25,None),('mid_empty',90,None),('closed_empty',135,None)]
    for edge in [10,20,30]:
        a=brentq(lambda a,e=edge:opening_mm(a)-e,25,135)
        cases.append((f'cube_{edge}_grasp',a,edge))
    for label,angle,edge in cases:
        scene=retained_at(base,angle)|mount
        checks=[]
        if edge:
            scene['DIAGNOSTIC_CUBE']=box(-.2-edge/2,-.2+edge/2,214.6-edge/2,214.6+edge/2,164.6-edge/2,164.6+edge/2)
            for n,sh in scene.items():
                if n=='DIAGNOSTIC_CUBE':continue
                checks.append({'name':n,**pair(scene['DIAGNOSTIC_CUBE'],sh,contact=n in ['PG3_pad_L','PG3_pad_R'])})
        for fov in [50,60,70]:
            view=View(scene,opt['eye'],opt['direction'],opt['up'],fov)
            image=folder/f'{label}_hfov{fov}.png'
            view.capture(image)
            visible=view.capture(seg=True)
            ids_inv={i:n for n,i in view.ids.items()}
            targets={'jaw_L':{'PG3_finger_L','PG3_pad_L'},'jaw_R':{'PG3_finger_R','PG3_pad_R'}, 'pad_L':{'PG3_pad_L'},'pad_R':{'PG3_pad_R'}}
            if edge:targets['cube']={'DIAGNOSTIC_CUBE'}
            result={}
            for key,names in targets.items():
                ref=view.capture(seg=True,only=names)
                codes=[view.ids[n] for n in names]
                mask=np.isin(ref,codes);actual=np.isin(visible,codes)
                hits=actual&mask; rows,cols=np.where(mask)
                crop=bool(np.any(mask[0]) or np.any(mask[-1]) or np.any(mask[:,0]) or np.any(mask[:,-1]))
                occ={}
                for i,c in zip(*np.unique(visible[mask&~actual],return_counts=True)):
                    n=ids_inv.get(int(i),'outside_background');cat=category(n)
                    occ[cat]=occ.get(cat,0)+int(c)
                result[key]={'reference_pixels':int(mask.sum()),'visible_pixels':int(hits.sum()),
                             'visible_fraction':float(hits.sum()/mask.sum()) if mask.sum() else 0,
                             'reference_touches_image_edge':crop,'occluded_by_pixel_count':occ,
                             'margin_pixels':int(min(cols.min(),799-cols.max(),rows.min(),599-rows.max())) if len(rows) else None}
            report['cases'].append({'label':label,'angle':angle,'cube_edge_mm':edge,'hfov':fov,
                                   'opening_mm':opening_mm(angle),'targets':result,
                                   'cube_clearance_failures':[c for c in checks if c['status']!='PASS'],
                                   'image':str(image.relative_to(RUN)),'image_sha':digest(image)})
            view.close()
            print(label,fov,{k:(round(v['visible_fraction'],3),v['margin_pixels']) for k,v in result.items()},flush=True)
            (RUN/'reports/camera_views.json').write_text(json.dumps(report,indent=2))
    return report

if __name__=='__main__':run()
