"""Convert the supplied GLB and produce the fixed annotation views."""
from pathlib import Path
import hashlib,json
import numpy as np,trimesh
from PIL import Image
from render import ortho
ROOT=Path(__file__).resolve().parents[1]

def main():
    for folder in ['annotations','results','models']: (ROOT/folder).mkdir(exist_ok=True)
    mesh=trimesh.load(ROOT/'inputs/scan.glb',force='mesh',process=False)
    v=mesh.vertices;f=mesh.faces;c=mesh.visual.to_color().vertex_colors
    if not np.isfinite(v).all() or f.shape[1]!=3: raise ValueError('Invalid scan')
    np.savez_compressed(ROOT/'inputs/scan_raw.npz',vertices=v,faces=f,colors=c)
    fc=v[f].mean(axis=1)
    ff=f[(fc[:,1]>.023)&(abs(fc[:,0]+.015)<.105)&(abs(fc[:,2]-.06)<.09)]
    np.save(ROOT/'inputs/scan_faces_gripper.npy',ff)
    ortho(v,ff,c,[-.015,.6,.06],[-.015,.03,.06],[0,0,-1],.145,out=ROOT/'annotations/gripper_top')
    ortho(v,ff,c,[-.015,.36,.48],[-.015,.055,.06],[0,1,0],.145,out=ROOT/'annotations/gripper_front')
    Image.open(ROOT/'inputs/photo.jpg').resize((1408,1056)).save(ROOT/'annotations/photo_1408.png')
    source_files = [ROOT/'inputs/scan.glb', ROOT/'inputs/photo.jpg']
    source_files += sorted((ROOT/'inputs/reference_cad').glob('*.step'))
    manifest = {
        'source_names': {'scan.glb': 'Scaniverse 2026-10-04 205850.glb',
                         'photo.jpg': '写真 2026-10-04 21 00 35.jpg'},
        'scan_vertices': len(v), 'scan_faces': len(f),
        'sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in source_files},
    }
    (ROOT/'results/input_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
