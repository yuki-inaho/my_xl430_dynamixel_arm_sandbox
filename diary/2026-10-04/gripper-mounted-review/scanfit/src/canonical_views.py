from pathlib import Path
import numpy as np
from render import ortho
ROOT=Path(__file__).resolve().parents[1]
d=np.load(ROOT/'inputs/scan_cad_mm.npz');v=d['vertices'];f=d['faces'];c=d['colors']
fc=v[f].mean(1);sel=(abs(fc[:,0])<49)&(abs(fc[:,1])<31)&(fc[:,2]>16)&(fc[:,2]<110)
f=f[sel];np.save(ROOT/'inputs/scan_faces_object.npy',f)
print('object bounds',v[np.unique(f)].min(0),v[np.unique(f)].max(0),'vertices',len(np.unique(f)))
ortho(v,f,c,[0,-300,55],[0,0,55],[0,0,1],110,width=1400,height=1200,out=ROOT/'annotations/canonical_front')
ortho(v,f,c,[0,0,300],[0,0,25],[0,1,0],110,width=1400,height=1000,out=ROOT/'annotations/canonical_top')
ortho(v,f,c,[0,-240,220],[0,0,50],[0,0,1],120,width=1400,height=1200,out=ROOT/'annotations/canonical_oblique')
ortho(v,f,c,[300,0,55],[0,0,55],[0,0,1],100,width=1200,height=1200,out=ROOT/'annotations/canonical_side')
