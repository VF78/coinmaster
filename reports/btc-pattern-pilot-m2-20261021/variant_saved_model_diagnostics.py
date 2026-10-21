"""Read-only saved V1 inference, raw losses and ES epoch conflict; no fits/CHECK."""
import json,hashlib,time
from pathlib import Path
import numpy as np,pandas as pd,torch
from coinmaster.research.btc_pattern_train import Data,neural_predict
from coinmaster.research.btc_pattern_data import folds
from coinmaster.research.btc_pattern_evaluate import losses,TASKS
root=Path('runtime/var/research-jobs/btc-pattern-pilot-m2-20261021');run=root/'quality-variants/METRIC_OFF';out=root/'quality-variants/METRIC_OFF-diagnostics';baseline=root/'development'
assert (run/'completion.json').exists()
manifest={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(run.glob('F*/*.pt'))}
(out/'saved-model-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
torch.set_num_threads(4);torch.set_num_interop_threads(1)
assert torch.backends.mps.is_available()
data=Data(root/'prepared');data.images=np.load(baseline/'images.npy',mmap_mode='r');rows=[];epochs=[];began=time.monotonic()
for fold in folds(data.meta):
 for kind in ['TCN','CNN']:
  folder=run/fold['name'];curve=pd.read_json(folder/f'{kind}-es.curve.json');receipt=json.loads((folder/f'{kind}-es.receipt.json').read_text())
  epochs.append(dict(fold=fold['name'],model=kind,selected=receipt['selected_epochs'],executed=len(curve),best_D_epoch=int(curve.loc[curve.early_stop_D.idxmin(),'epoch']),best_Q_epoch=int(curve.loc[curve.early_stop_Q.idxmin(),'epoch']),D_at_selected=float(curve.set_index('epoch').loc[receipt['selected_epochs'],'early_stop_D']),Q_at_selected=float(curve.set_index('epoch').loc[receipt['selected_epochs'],'early_stop_Q']),D_min=float(curve.early_stop_D.min()),Q_min=float(curve.early_stop_Q.min())))
  for role,ids,version in [('subfit_in_sample',fold['subfit'],'es'),('inner_early_stop',fold['early_stop'],'es'),('refit_in_sample',fold['refit'],'refit')]:
   state=torch.load(folder/f'{kind}-{version}.pt',weights_only=False,map_location='cpu');_,p,q=neural_predict(data,state,ids,device='mps');score=losses(p,np.maximum(0,np.sort(q,axis=2)),data.d[ids],data.y[ids])
   for j,task in enumerate(TASKS):rows.append(dict(fold=fold['name'],method=kind,role=role,task=task,N=int(np.isfinite(score[:,j]).sum()),loss=float(np.nanmean(score[:,j]))))
  z=dict(np.load(folder/f'{kind}-direct.npz'));score=losses(z['probabilities'],z['q_projected'],z['truth_D'],z['truth_Q'])
  for j,task in enumerate(TASKS):rows.append(dict(fold=fold['name'],method=kind,role='outer_validation',task=task,N=int(np.isfinite(score[:,j]).sum()),loss=float(np.nanmean(score[:,j]))))
pd.DataFrame(rows).to_csv(out/'fit-es-outer-losses.csv',index=False);pd.DataFrame(epochs).to_csv(out/'epoch-selection-conflicts.csv',index=False)
(out/'saved-diagnostic-completion.json').write_text(json.dumps(dict(fits=0,CHECK_used=False,wall_seconds=time.monotonic()-began,checkpoint_count=len(manifest)),indent=2)+'\n')
print('read-only diagnostic inference complete')
