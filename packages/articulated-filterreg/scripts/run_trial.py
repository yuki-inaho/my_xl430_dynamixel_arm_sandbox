from pathlib import Path
import json,cv2,time
from articulated_filterreg.geometry import CadModel
from articulated_filterreg.observations import Observations
from articulated_filterreg.optimize import FitConfig,initialize_from_training,fit
from articulated_filterreg.evaluate import evaluate
from articulated_filterreg.render import render,shaded_image
ROOT=Path(__file__).resolve().parents[1]
m=CadModel.load(ROOT/'model/bare_arm.npz');o=Observations.load(ROOT)
s=initialize_from_training(m,o)
print('initial',s.to_dict(),flush=True);print(evaluate(m,o,s),flush=True)
c=FitConfig(iterations_per_sigma=10)
r=fit(m,o,s,c)
print('result',r.status,r.elapsed_seconds,r.state.to_dict(),flush=True);print(evaluate(m,o,r.state),flush=True)
(ROOT/'results/trial_state.json').write_text(json.dumps(r.state.to_dict(),indent=2))
(ROOT/'results/trial_trace.json').write_text(json.dumps(r.trace,indent=2))
for name,state in [('training_initialized',s),('trial',r.state)]:
 d,idx,vs=render(m,state,o.K,o.width,o.height);cad=shaded_image(m,vs,idx);img=o.rgb.copy();valid=idx>=0
 img[valid]=(img[valid]*.55+cad[valid]*.45).astype('uint8')
 cv2.imwrite(str(ROOT/f'results/{name}_overlay.png'),cv2.cvtColor(img,cv2.COLOR_RGB2BGR))
