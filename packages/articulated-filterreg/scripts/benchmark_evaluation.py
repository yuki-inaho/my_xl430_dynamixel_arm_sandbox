from pathlib import Path
import time,json
from articulated_filterreg.geometry import CadModel,State
from articulated_filterreg.observations import Observations
from articulated_filterreg.evaluate import evaluate
R=Path(__file__).resolve().parents[1]
t=time.monotonic();m=CadModel.load(R/'model/bare_arm.npz');o=Observations.load(R);print('load',time.monotonic()-t,flush=True)
r=json.loads((R/'results/trials/trial_001.json').read_text())
for k in ['initial','final']:
 t=time.monotonic();v=evaluate(m,o,State.from_dict(r[k]));print(k,time.monotonic()-t,flush=True)
