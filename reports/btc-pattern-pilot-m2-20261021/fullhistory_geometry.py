"""Read-only deterministic whole-period geometry probe, no fits or CHECK."""
import json,resource,hashlib
from pathlib import Path
import numpy as np,pandas as pd,torch
from coinmaster.research.btc_pattern_train import Data,neural_predict
from coinmaster.research.btc_pattern_data import folds
root=Path('runtime/var/research-jobs/btc-pattern-pilot-m2-20261021');out=root/'quality-variants/METRIC_OFF-diagnostics';data=Data(root/'prepared');data.images=np.load(root/'development/images.npy',mmap_mode='r');torch.set_num_threads(4);torch.set_num_interop_threads(1);assert torch.backends.mps.is_available();rows=[]
for fold in folds(data.meta):
 for kind in ['TCN','CNN']:
  for mode,folder in [('BASELINE',root/'development'),('METRIC_OFF',root/'quality-variants/METRIC_OFF')]:
   file=folder/fold['name']/f'{kind}-refit.pt';state=torch.load(file,weights_only=False,map_location='cpu')
   for role in ['refit','outer']:
    allids=fold[role];ids=allids[np.unique(np.linspace(0,len(allids)-1,min(512,len(allids))).astype(int))];z,_,_=neural_predict(data,state,ids,device='mps');assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<6*1024**3
    singular=np.linalg.svd(z-z.mean(0),compute_uv=False);energy=singular**2;energy=energy/max(float(energy.sum()),1e-12);rank=float(np.exp(-(energy[energy>0]*np.log(energy[energy>0])).sum()))
    rows.append(dict(fold=fold['name'],model=kind,mode=mode,role=role,sampling='512 deterministic uniformly spaced causal origins across complete role',N=len(ids),population_N=len(allids),first_origin_UTC=pd.to_datetime(data.meta['origin'][ids[0]],unit='ms',utc=True),last_origin_UTC=pd.to_datetime(data.meta['origin'][ids[-1]],unit='ms',utc=True),rank=rank,variance=float(z.var(0).mean()),checkpoint_sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
pd.DataFrame(rows).to_csv(out/'fullhistory-geometry.csv',index=False);print('whole-period geometry complete:24 rows, no fits/CHECK')
