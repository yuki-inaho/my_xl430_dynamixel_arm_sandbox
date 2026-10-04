"""Round-trip checks, scan-to-model distances, and a textured comparison GLB."""
from pathlib import Path
import json,numpy as np,trimesh
import vtk
from vtk.util.numpy_support import numpy_to_vtk,numpy_to_vtkIdTypeArray
from build_models import PHYSICAL,DISPLAY
from fit_addons import voxel
ROOT=Path(__file__).resolve().parents[1]


def distances(vertices,faces,points):
    pd=vtk.vtkPolyData();vp=vtk.vtkPoints();vp.SetData(numpy_to_vtk(np.asarray(vertices,dtype=float),deep=True));pd.SetPoints(vp)
    cells=vtk.vtkCellArray();arr=np.c_[np.full(len(faces),3,dtype=np.int64),faces].astype(np.int64).ravel();cells.ImportLegacyFormat(numpy_to_vtkIdTypeArray(arr,deep=True));pd.SetPolys(cells)
    loc=vtk.vtkStaticCellLocator();loc.SetDataSet(pd);loc.BuildLocator()
    closest=[0.,0.,0.];cell=vtk.reference(0);sub=vtk.reference(0);d2=vtk.reference(0.)
    result=[]
    for p in points:
        loc.FindClosestPoint(p,closest,cell,sub,d2);result.append(np.sqrt(float(d2)))
    return np.array(result)


def main():
    data=np.load(ROOT/'results/model_meshes.npz');scan=np.load(ROOT/'inputs/scan_cad_mm.npz');ann=np.load(ROOT/'annotations/selected_vertex_ids.npz')
    metrics={}
    for name in PHYSICAL:
        v=data[name+'_vertices'];f=data[name+'_faces'];pts=voxel(scan['vertices'][ann[name]],1.)
        dd=distances(v,f,pts)
        metrics[name]={'evaluation_points':len(pts),'distance_mean_mm':float(np.mean(dd)),'distance_median_mm':float(np.median(dd)),'distance_p95_mm':float(np.percentile(dd,95)),'distance_max_mm':float(np.max(dd))}
    report={'definition':'one-sided closest Euclidean distance from uniformly downsampled annotated scan vertices to exported model surface triangulation','not_an_accuracy_certificate':'Fit-region residual, not held-out physical accuracy, not a confidence interval. Unseen surfaces are not validated.','components':metrics}
    (ROOT/'results/surface_residuals.json').write_text(json.dumps(report,indent=2))
    cal=json.loads((ROOT/'results/calibration.json').read_text());s=cal['scale_mm_per_source_unit'];R=np.array(cal['R_source_to_cad']);t=np.array(cal['t_source_to_cad_mm'])
    glb_rotation=np.array([[1,0,0],[0,0,1],[0,-1,0]],float)
    orig=trimesh.load(ROOT/'inputs/scan.glb',force='mesh',process=False)
    q=orig.vertices@(s*R).T+t;fc=q[orig.faces].mean(axis=1)
    mask=(abs(fc[:,0])<49)&(abs(fc[:,1])<31)&(fc[:,2]>16)&(fc[:,2]<110)
    # Preserve source UV and texture; only crop faces and change coordinates.
    orig.vertices=q*.001@glb_rotation.T;crop=orig.submesh([np.flatnonzero(mask)],append=True)
    scene=trimesh.Scene();scene.add_geometry(crop,node_name='scan_reference',geom_name='scan_reference')
    scene.metadata={'units':'m','up_axis':'Y','note':'Textured source scan and independently selectable approximate soft components. Components are exterior occupancy envelopes.'}
    for name in PHYSICAL:
        m=trimesh.Trimesh(data[name+'_vertices']*.001@glb_rotation.T,data[name+'_faces'],process=False)
        color=(*DISPLAY[name],115)
        mat=trimesh.visual.material.PBRMaterial(name=name,baseColorFactor=color,metallicFactor=0,roughnessFactor=.75,alphaMode='BLEND',doubleSided=True)
        m.visual=trimesh.visual.TextureVisuals(material=mat)
        scene.add_geometry(m,node_name=name,geom_name=name)
    scene.export(ROOT/'models/scan_with_fitted_addons.glb')
    scan_scene=trimesh.Scene(crop);scan_scene.export(ROOT/'models/scan_cropped_metric.glb')
    # Annotation evidence as a colorized mesh (retains base colors outside annotations).
    colors=scan['colors'].copy();labels=ann['labels']
    for idx,name in enumerate(['cot_L','cot_R','foam_L','foam_R','band_L','band_R'],1):
        colors[labels==idx,:3]=DISPLAY[name]
    m=trimesh.Trimesh(scan['vertices'],np.load(ROOT/'inputs/scan_faces_object.npy'),process=False,vertex_colors=colors);m.remove_unreferenced_vertices();m.export(ROOT/'annotations/segmented_scan_mm.ply')
    checks=json.loads((ROOT/'results/step_validation.json').read_text())
    loaded=trimesh.load(ROOT/'models/soft_addons_scanfit.glb',force='scene',process=False)
    maxdiff=0.
    for name in PHYSICAL:
        trans,key=loaded.graph[name];m=loaded.geometry[key].copy();m.apply_transform(trans);back=m.vertices@glb_rotation*1000
        old=data[name+'_vertices'];delta=np.max(abs(np.r_[back.min(0),back.max(0)]-np.r_[old.min(0),old.max(0)]));maxdiff=max(maxdiff,float(delta))
    final={'step_components':checks,'glb_geometry_count':len(loaded.geometry),'glb_roundtrip_bounds_max_error_mm':maxdiff,'glb_units':'metres, +Y up','step_stl_units':'millimetres, +Z up in C92 construction coordinates',
           'all_step_valid':all(v['valid_after_step_reimport'] and v['solids']==1 for v in checks.values()),'all_addon_meshes_watertight':all(v['mesh_watertight'] for v in checks.values()),'all_volumes_positive':all(v['volume_mm3']>0 for v in checks.values()),'scale_positive':s>0,'rotation_determinant':float(np.linalg.det(R)),'max_mesh_vs_step_volume_relative_error':max(v['mesh_volume_relative_error'] for v in checks.values()),'mesh_volume_tolerance_relative':.025}
    final['pass']=final['all_step_valid'] and final['all_addon_meshes_watertight'] and final['all_volumes_positive'] and maxdiff<.01 and final['max_mesh_vs_step_volume_relative_error']<.025 and final['glb_geometry_count']==6
    (ROOT/'results/validation.json').write_text(json.dumps(final,indent=2))
    if not final['pass']:raise ValueError('Geometry validation failed')
    print(json.dumps(report,indent=2));print(json.dumps(final,indent=2))
if __name__=='__main__':main()
