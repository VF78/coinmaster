"""Read-only raw quantile/CDF and representation comparisons versus baseline."""
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
p=argparse.ArgumentParser();p.add_argument('--mode-run',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--regimes',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);rows=[];geometry=[];cohorts={}
if a.regimes:
    rg=pd.read_csv(a.regimes);regime_map={(r.fold,int(r.id)):r.regime for r in rg.itertuples()}
    from coinmaster.research.btc_pattern_evaluate import losses,paired_ci,TASKS
    meta=np.load(a.baseline.parent/'prepared/metadata.npy',mmap_mode='r')
for folder in sorted(a.mode_run.glob('F[123]')):
    for f in folder.glob('*.npz'):
        current=dict(np.load(f));base=dict(np.load(a.baseline/folder.name/f.name))
        if not np.array_equal(current['ids'],base['ids']):raise ValueError('MODE_DIAGNOSTIC_PAIRED_IDS_DIFFER')
        y=current['truth_Q'];upper=current['truth_Q_upper']
        if a.regimes:
            prior=dict(np.load(a.baseline/folder.name/'prior.npz'));lc=losses(current['probabilities'],current['q_projected'],current['truth_D'],y);lb=losses(base['probabilities'],base['q_projected'],base['truth_D'],base['truth_Q']);lp=losses(prior['probabilities'],prior['q_projected'],prior['truth_D'],prior['truth_Q']);labels=np.array([regime_map[(folder.name,int(i))] for i in current['ids']])
            for regime in np.unique(labels):
                sel=labels==regime;cohorts.setdefault((f.stem,regime),[]).append((lc[sel],lb[sel],lp[sel],meta['origin'][current['ids'][sel]]))
        for s,side in enumerate(['long','short']):
            for k,level in enumerate([.2,.5,.8]):
                raw=current['q_raw'][:,s,k];pred=current['q_projected'][:,s,k];bpred=base['q_projected'][:,s,k];e=y[:,s]-pred;be=y[:,s]-bpred;loss=np.maximum(level*e,(level-1)*e);bloss=np.maximum(level*be,(level-1)*be)
                rows.append(dict(fold=folder.name,method=f.stem,side=side,q=level,N=len(y),pinball=float(loss.mean()),original_pinball=float(bloss.mean()),delta=float((loss-bloss).mean()),CDF_le=float((y[:,s]<=pred).mean()),original_CDF_le=float((y[:,s]<=bpred).mean()),CDF_lt=float((y[:,s]<pred).mean()),ties=float((y[:,s]==pred).mean()),zero_prediction=float((pred==0).mean()),TP_hit_lower=float((y[:,s]>=pred).mean()),TP_hit_upper=float((upper[:,s]>=pred).mean()),raw_mean=float(raw.mean()),projected_mean=float(pred.mean()),original_projected_mean=float(bpred.mean()),raw_crossing=float((np.diff(current['q_raw'][:,s],axis=1)<0).any(1).mean())))
    for f in folder.glob('*-refit.curve.json'):
        row=json.loads(f.read_text())[-1];original=json.loads((a.baseline/folder.name/f.name).read_text())[-1]
        geometry.append(dict(fold=folder.name,model=f.stem.split('-')[0],selected_epochs=row['epoch'],original_epochs=original['epoch'],metric=row['metric'],original_metric=original['metric'],target_entropy=row['target_entropy'],rank=row['embedding_effective_rank'],original_rank=original['embedding_effective_rank'],variance=row['embedding_variance'],original_variance=original['embedding_variance']))
regime_rows=[]
for (method,regime),parts in cohorts.items():
    lc,lb,lp,origins=[np.concatenate([part[j] for part in parts]) for j in range(4)]
    for j,task in enumerate(TASKS):
        for reference,other in [('same_original_method',lb),('original_prior',lp)]:regime_rows.append(dict(method=method,regime=regime,task=task,reference=reference,loss=float(np.nanmean(lc[:,j])),reference_loss=float(np.nanmean(other[:,j])),**paired_ci(lc[:,j]-other[:,j],origins)))
if regime_rows:pd.DataFrame(regime_rows).to_csv(a.output/'causal-regime-loss-comparison.csv',index=False)
pd.DataFrame(rows).to_csv(a.output/'quantile-cdf-comparison.csv',index=False);pd.DataFrame(geometry).to_csv(a.output/'embedding-comparison.csv',index=False);print(json.dumps(dict(quantile_rows=len(rows),geometry_rows=len(geometry))))
