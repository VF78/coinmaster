"""Oracle DEVELOPMENT label-space diagnostic; no causal forecasts/fits/CHECK."""
import json,time
from pathlib import Path
import numpy as np
from coinmaster.research.btc_pattern_data import folds,HOUR
from coinmaster.research.btc_pattern_train import scales
out=Path(__file__).parent;root=out.parents[3];p=root/'runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/prepared';start=time.monotonic()
meta=np.load(p/'metadata.npy',mmap_mode='r');labels=np.load(p/'labels.npz');sig=labels['signature'];direction=labels['direction'];q=labels['mfe'][:,:,0]
class Tiny:pass
data=Tiny();data.signature=sig;data.y=q;data.meta=meta
records=[]
for fold in folds(meta):
 ids=fold['refit'];ys,_,tau=scales(data,ids);anchors=ids[np.unique(np.linspace(0,len(ids)-1,128).round().astype(int))];rng=np.random.default_rng(7)
 for ai in anchors:
  eligible=ids[(meta['origin'][ai]>=meta['label_end'][ids])|(meta['label_end'][ai]<=meta['origin'][ids])]
  distance=.5*np.abs((sig[eligible,:6]-sig[ai,:6])/ys).mean(1)+.5*np.abs(sig[eligible,6:]-sig[ai,6:]).mean(1)
  for method,order in [('oracle-signature',np.argsort(distance,kind='stable')),('random',rng.permutation(len(eligible)))]:
   chosen=[]
   for ri in order:
    k=int(eligible[ri])
    if all(abs(int(meta['origin'][k])-int(meta['origin'][j]))>=72*HOUR for j in chosen):
     chosen.append(k)
     if len(chosen)==32:break
   chosen=np.array(chosen);valid=(direction[chosen]>=0)&(direction[ai]>=0)
   records.append(dict(fold=fold['name'],method=method,anchor=int(ai),n=len(chosen),D_count=int(valid.sum()),D_disagree=int((direction[chosen][valid]!=direction[ai]).sum()),long_abs=float(abs(q[chosen,0]-q[ai,0]).mean()),short_abs=float(abs(q[chosen,1]-q[ai,1]).mean()),signature_distance=float((.5*np.abs((sig[chosen,:6]-sig[ai,:6])/ys).mean(1)+.5*np.abs(sig[chosen,6:]-sig[ai,6:]).mean(1)).mean())))
summary=[]
for fold in ['F1','F2','F3']:
 for method in ['oracle-signature','random']:
  rows=[r for r in records if r['fold']==fold and r['method']==method]
  summary.append(dict(fold=fold,method=method,anchors=len(rows),pairs=sum(r['n'] for r in rows),D_disagreement=sum(r['D_disagree'] for r in rows)/sum(r['D_count'] for r in rows),long_absolute_MFE_deviation=float(np.mean([r['long_abs'] for r in rows])),short_absolute_MFE_deviation=float(np.mean([r['short_abs'] for r in rows])),signature_distance=float(np.mean([r['signature_distance'] for r in rows]))))
result=dict(scope='ORACLE LABEL SPACE, NOT CAUSAL FORECAST, NOT TRADEABLE UPPER BOUND; DEVELOPMENT REFIT ONLY',selection='128 uniform anchors per fold; all refit peer labels disjoint from anchor label window; stable target-distance ranking or seed7 random; same greedy72h peer spacing; k32',q_units='original normalized MFE sigma72; not currency/percent',summary=summary,execution=dict(wall_seconds=time.monotonic()-start,fits=0,optimizer_steps=0,market_predictions=0,CHECK_accessed=False))
(out/'target-adequacy.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
