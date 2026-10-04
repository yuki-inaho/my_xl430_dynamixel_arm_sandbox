"""Render measured results from the selected CAD state; never synthesize geometry."""
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import cv2
from PIL import Image,ImageDraw,ImageFont
import trimesh
from .geometry import CadModel,State,projection
from .observations import Observations
from .evaluate import evaluate
from .render import render,shaded_image

def _save_rgb(path:Path,array:np.ndarray):
    if not cv2.imwrite(str(path),cv2.cvtColor(array,cv2.COLOR_RGB2BGR)):raise IOError(f'Cannot write {path}')

def _font(size:int):
    candidates=[Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    for p in candidates:
        if p.exists():return ImageFont.truetype(str(p),size)
    return ImageFont.load_default()

def write_visual_results(root:Path)->dict:
    model=CadModel.load(root/'model/bare_arm.npz');obs=Observations.load(root)
    best=json.loads((root/'results/best.json').read_text());state=State.from_dict(best['final'])
    depth,index,vertices=render(model,state,obs.K,obs.width,obs.height)
    cad=shaded_image(model,vertices,index);raw=index>=0;visible=raw&~obs.occlusion
    raw_overlay=obs.rgb.copy();raw_overlay[raw]=(.52*obs.rgb[raw]+.48*cad[raw]).astype(np.uint8)
    _save_rgb(root/'results/raw_geometry_overlay.png',raw_overlay)
    # Material-shaded overlay plus visible CAD part boundaries.
    overlay=obs.rgb.copy();overlay[visible]=(.55*obs.rgb[visible]+.45*cad[visible]).astype(np.uint8)
    unit=np.full(index.shape,-1,np.int16);unit[raw]=model.face_unit[index[raw]]
    edge=np.zeros_like(raw)
    edge[1:]|=unit[1:]!=unit[:-1];edge[:,1:]|=unit[:,1:]!=unit[:,:-1]
    edge &= cv2.dilate(raw.astype(np.uint8),np.ones((3,3),np.uint8))>0
    edge &= ~obs.occlusion
    overlay[edge]=np.array([32,190,230],np.uint8)
    _save_rgb(root/'results/overlay.png',overlay);_save_rgb(root/'results/cad_view.png',cad)
    _save_rgb(root/'results/input_rgb.png',obs.rgb)
    Image.fromarray(overlay).resize((obs.width*2,obs.height*2),Image.Resampling.LANCZOS).save(root/'results/overlay_2x.png')
    cv2.imwrite(str(root/'results/predicted_visible_mask.png'),visible.astype(np.uint8)*255)
    cv2.imwrite(str(root/'results/predicted_raw_mask.png'),raw.astype(np.uint8)*255)
    diff=obs.rgb.copy();agreement=visible&obs.mask;extra=visible&~obs.mask;missing=obs.mask&~visible
    diff[agreement]=(.72*diff[agreement]+.28*np.array([235,235,235])).astype(np.uint8)
    diff[extra]=np.array([232,77,74]);diff[missing]=np.array([58,119,217])
    _save_rgb(root/'results/silhouette_error.png',diff)
    # Only now are held-out points evaluated; winner selection has already finished.
    metrics=evaluate(model,obs,state,include_held_out=True)
    (root/'results/metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2,allow_nan=False))
    diagnostic=obs.rgb.copy()
    for result in metrics['held_out_landmarks']:
        observed=np.rint(result['annotation_uv']).astype(int);predicted=np.rint(result['prediction_uv']).astype(int)
        cv2.line(diagnostic,tuple(observed),tuple(predicted),(255,205,50),1,cv2.LINE_AA)
        cv2.circle(diagnostic,tuple(observed),3,(240,80,150),1,cv2.LINE_AA)
        cv2.drawMarker(diagnostic,tuple(predicted),(30,195,235),cv2.MARKER_CROSS,5,1,cv2.LINE_AA)
    _save_rgb(root/'results/held_out_landmarks.png',diagnostic)
    # Numeric geometry, camera coordinates x-right/y-down/z-forward in depth units.
    face_colors=np.where(model.face_kind[:,None]==1,np.array([226,234,240,255]),np.array([44,49,57,255])).astype(np.uint8)
    mesh=trimesh.Trimesh(vertices,model.faces,face_colors=face_colors,process=False)
    mesh.export(root/'results/fitted_cad_camera.ply')
    viewer_mesh=trimesh.Trimesh(vertices*np.array([1.,-1.,-1.]),model.faces,face_colors=face_colors,process=False)
    viewer_mesh.export(root/'results/fitted_cad_opengl.glb')
    viewer_mesh.export(root/'results/fitted_cad_opengl.ply')
    trimesh.PointCloud(obs.target_points).export(root/'results/foreground_target.ply')
    numeric={'state':state.to_dict(),'camera_K':obs.K.tolist(),'width':obs.width,'height':obs.height,
      'body_transforms_camera_depth_units':model.chain.transforms(state).tolist(),
      'translation_camera_m':(state.translation/state.scale).tolist(),
      'opengl_from_camera_cv':np.diag([1.,-1.,-1.,1.]).tolist(),
      'coordinate_convention':'*_camera.ply uses x-right/y-down/z-forward; *_opengl files use x-right/y-up/z-backward like original MoGE PLY. CAD input meters; fitted geometry depth units.',
      'source_step_reference':'model/source_arm_XL430_R3.step','derived_urdf':'model/bare_arm_r3.urdf',
      'best_trial':best['id'],'binding_used':json.loads((root/'results/run_manifest.json').read_text())['binding']}
    (root/'results/transforms.json').write_text(json.dumps(numeric,ensure_ascii=False,indent=2))
    np.savez_compressed(root/'results/render_depth.npz',depth=np.where(raw,depth,np.nan),triangle_id=index,K=obs.K)
    # Presentation contact sheet. Fonts are used locally, never shipped as font files.
    pad=22;header=55;footer=80;w=3*obs.width+4*pad;h=obs.height+header+footer
    canvas=Image.new('RGB',(w,h),(249,250,251));draw=ImageDraw.Draw(canvas)
    titles=['入力画像','最良候補のCAD重畳','同じ推定姿勢のCAD描画']
    for k,(title,im) in enumerate(zip(titles,[obs.rgb,overlay,cad])):
        x=pad+k*(obs.width+pad);draw.text((x,12),title,font=_font(23),fill=(32,41,48))
        canvas.paste(Image.fromarray(im),(x,header))
    text=f"32初期値／採用 #{best['id']:02d}　領域IoU {metrics['iou']:.4f}　未使用14点の再投影誤差中央値 {metrics['held_out_landmark_median_px']:.2f} px　尺度 {state.scale:.6f} 深度単位/m"
    draw.text((pad,header+obs.height+12),text,font=_font(21),fill=(32,41,48))
    draw.text((pad,header+obs.height+43),'青線：実CADの可視部品境界。布・テープのみ前景遮蔽。単眼推定値であり、実測精度・実機関節指令ではありません。',font=_font(18),fill=(80,88,96))
    canvas.save(root/'results/comparison.png')
    print(json.dumps(metrics,ensure_ascii=False,indent=2),flush=True)
    return metrics
