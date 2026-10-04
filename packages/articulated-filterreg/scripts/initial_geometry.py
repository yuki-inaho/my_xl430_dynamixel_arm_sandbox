from pathlib import Path
import numpy as np,json,cv2
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from articulated_filterreg.geometry import CadModel,State,projection
from articulated_filterreg.render import render,shaded_image
ROOT=Path(__file__).resolve().parents[1]
m=CadModel.load(ROOT/'model/bare_arm.npz');o=np.load(ROOT/'model/observations.npz');K=o['K'];xyz=o['xyz'];rgb=o['rgb']
pixels=np.array([[224.,278.],[260.,94.],[448.,137.]])
p=np.array([[.0218,0,.0563],[.0228,.0148,.1646],[.0228,.1049,.1646]])
lv=np.array([2,3,4],np.int32)
y=np.array([xyz[int(v),int(u)] for u,v in pixels])
# Similarity initialization from observed joint-face centers, not encoder states.
u=p-p.mean(0);v=y-y.mean(0);U,_,Vt=np.linalg.svd(v.T@u);R=U@Vt
if np.linalg.det(R)<0:U[:,-1]*=-1;R=U@Vt
s=np.sum((u@R.T)*v)/np.sum(u*u);t=y.mean(0)-s*R@p.mean(0)
st=State(R,t,np.log(s),np.deg2rad([0,0,0,-30]))
x0=st.vector()
def residual(x):
 st=State.from_vector(x);a=m.chain.transform(p,lv,st)
 return np.r_[((a-y)/.006).ravel(),x[7:9]/.2,(x[10]-np.deg2rad(-30))/.3]
r=least_squares(residual,x0,max_nfev=80)
st=State.from_vector(r.x)
(ROOT/'results/initial_state.json').write_text(json.dumps(st.to_dict(),indent=2))
d,idx,verts=render(m,st,K,652,367);cad=shaded_image(m,verts,idx)
img=rgb.copy();valid=idx>=0;img[valid]=(img[valid]*.5+cad[valid]*.5).astype(np.uint8)
for x,y in projection(m.chain.transform(p,lv,st),K):cv2.circle(img,(round(x),round(y)),3,(255,0,0),-1)
cv2.imwrite(str(ROOT/'results/initial_overlay.png'),cv2.cvtColor(img,cv2.COLOR_RGB2BGR))
cv2.imwrite(str(ROOT/'results/initial_cad.png'),cv2.cvtColor(cad,cv2.COLOR_RGB2BGR))
print(st.to_dict());print('train projected',projection(m.chain.transform(p,lv,st),K))
features=np.array([[.01805,.1589,.1686],[.01805,.1589,.1926],[.01805,.1709,.1686],[.01805,.1709,.1926]])
print('P05 holes',projection(m.chain.transform(features,np.full(4,4,np.int32),st),K))
