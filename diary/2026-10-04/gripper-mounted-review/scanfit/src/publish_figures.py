"""Publish deterministic, full-resolution photographic overlays."""
from pathlib import Path
import json
import numpy as np,cv2
from PIL import Image,ImageDraw,ImageFont
from render import raster
from render_results import model_arrays,blend
ROOT=Path(__file__).resolve().parents[1]


def font(size):
    path=Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
    if not path.exists(): raise FileNotFoundError('Noto Sans CJK is required for Japanese figure labels; geometry export is unaffected.')
    return ImageFont.truetype(str(path),size)


def main():
    src=Image.open(ROOT/'inputs/photo.jpg').convert('RGB');w,h=src.size;scale=w/1408
    cam=json.loads((ROOT/'results/photo_camera.json').read_text());R=np.array(cam['R_cad_to_camera']);t=np.array(cam['t_cad_to_camera_mm']);focal=cam['focal_px']*scale
    v,f,c,labels=model_arrays();pc=v@R.T+t;q=pc.copy();q[:,:2]=pc[:,:2]/pc[:,2,None]*focal+[w/2,h/2]
    rgb,z,ids,b=raster(q,f,c.astype(float),w,h,True)
    out,lab=blend(src,rgb,ids,labels,.30)
    Image.fromarray(out).save(ROOT/'results/photo_overlay.png')
    # Store full-resolution geometric labels, without a 2-D silhouette mask.
    Image.fromarray(lab).save(ROOT/'results/photo_model_labels.png')
    im=Image.fromarray(out);dr=ImageDraw.Draw(im)
    box=(30,h-115,1075,h-28);dr.rounded_rectangle(box,radius=12,fill=(246,247,249),outline=(200,206,214),width=1)
    items=[('指サック',(36,176,238)),('黒いゴム',(246,171,54)),('輪ゴム',(210,76,188))]
    x=60
    for label,color in items:
        dr.rectangle((x,h-82,x+26,h-56),fill=color);dr.text((x+42,h-91),label,font=font(30),fill=(35,42,48));x+=280
    dr.text((900,h-82),'GLB再推定',font=font(21),fill=(72,82,92))
    im.save(ROOT/'results/photo_overlay_labeled.png')
    im.resize((1408,1056),Image.Resampling.LANCZOS).save(ROOT/'results/photo_overlay_preview.png')
    # A clean comparison image with original and fitted overlay, same crop and scale.
    crop=(470,90,1650,1120);a=src.crop(crop);bim=Image.fromarray(out).crop(crop)
    vieww=840;viewh=round(a.height*vieww/a.width);panel=Image.new('RGB',(2*vieww+60,viewh+138),(247,248,250));dr=ImageDraw.Draw(panel)
    dr.text((24,14),'元写真',font=font(30),fill=(35,42,48));dr.text((vieww+38,14),'実尺度の近似モデルを重畳',font=font(30),fill=(35,42,48))
    panel.paste(a.resize((vieww,viewh),Image.Resampling.LANCZOS),(20,66));panel.paste(bim.resize((vieww,viewh),Image.Resampling.LANCZOS),(vieww+40,66))
    dr.text((24,viewh+82),'水色：指サック　　橙：黒いゴム　　紫：輪ゴム　｜　内部形状・肉厚・表面の粒状突起は未復元',font=font(23),fill=(55,64,72))
    panel.save(ROOT/'results/photo_comparison.png')
    print('Full-resolution overlay and comparison saved.')
if __name__=='__main__':main()
