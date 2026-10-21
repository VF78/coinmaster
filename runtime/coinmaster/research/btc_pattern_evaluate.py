"""Paired, fixed-head development gates; no conditional CHECK opening."""
from pathlib import Path
import json
import numpy as np
from .btc_pattern_data import DAY
from .forecast_independent_data import write_json
TASKS=('D','Q-long','Q-short')

def losses(p,q,d,y):
    valid=d>=0;dl=np.full(len(d),np.nan);dl[valid]=-np.log(np.maximum(p[valid,d[valid]],1e-12))
    error=y[:,:,None]-q;pin=np.maximum(np.array([.2,.5,.8])*error,(np.array([.2,.5,.8])-1)*error).mean(2)
    return np.column_stack((dl,pin))

def paired_ci(delta,origins):
    good=np.isfinite(delta);delta,origins=delta[good],origins[good];blocks=origins//(14*DAY);u,inv=np.unique(blocks,return_inverse=True)
    sums=np.bincount(inv,weights=delta);counts=np.bincount(inv);rng=np.random.default_rng(7);which=rng.integers(0,len(u),(1000,len(u)));boot=sums[which].sum(1)/counts[which].sum(1)
    return dict(mean=float(delta.mean()),lower=float(np.quantile(boot,.025)),upper=float(np.quantile(boot,.975)),blocks=len(u),rows=len(delta),draws=1000)

def evaluate(a):
    import pandas as pd
    from sklearn.metrics import roc_auc_score
    root=a.prepared # prepared is actual data, input is directory containing fold forecasts
    inputs=a.input;meta=np.load(root/'metadata.npy',mmap_mode='r');groups={};metrics=[];forecasts=[];extras=[]
    for folder in sorted(inputs.glob('F[123]')):
        for f in folder.glob('*.npz'):
            z=dict(np.load(f));ids=z['ids'];p,q,d,y=z['probabilities'],z['q_projected'],z['truth_D'],z['truth_Q'];loss=losses(p,q,d,y);groups.setdefault(f.stem,[]).append((folder.name,ids,loss))
            for j,task in enumerate(TASKS):
                finite=np.isfinite(loss[:,j]);metrics.append(dict(fold=folder.name,method=f.stem,task=task,N=int(finite.sum()),loss=float(loss[finite,j].mean())))
            valid=d>=0;one=np.eye(3)[d[valid]];brier=float(((p[valid]-one)**2).sum(1).mean());auroc=[]
            for k in range(3):
                try:auroc.append(float(roc_auc_score(d[valid]==k,p[valid,k])))
                except ValueError:auroc.append(None)
            extras.append(dict(fold=folder.name,method=f.stem,brier=brier,AUROC=auroc,accuracy=float((p[valid].argmax(1)==d[valid]).mean()),ambiguous_D_count=int((~valid).sum()),Q_zero_fraction=(q==0).mean((0,2)).tolist(),raw_crossing_fraction=float((np.diff(z['q_raw'],axis=2)<0).any(2).mean()),raw_pinball=losses(p,z['q_raw'],d,y)[:,1:].mean(0).tolist(),upper_sensitivity_pinball=losses(p,q,d,z['truth_Q_upper'])[:,1:].mean(0).tolist(),coverage=(y[:,:,None]<=q).mean(0).tolist()))
            for i,oi in enumerate(ids):
                forecasts.append(dict(fold=folder.name,method=f.stem,id=int(oi),origin=int(meta['origin'][oi]),label_end=int(meta['label_end'][oi]),truth_D=int(d[i]),p_UP=float(p[i,0]),p_DOWN=float(p[i,1]),p_NONE=float(p[i,2]),Qlong20=float(q[i,0,0]),Qlong50=float(q[i,0,1]),Qlong80=float(q[i,0,2]),Qshort20=float(q[i,1,0]),Qshort50=float(q[i,1,1]),Qshort80=float(q[i,1,2]),truth_Qlong=float(y[i,0]),truth_Qshort=float(y[i,1]),support=int(z['support'][i])))
    a.output.mkdir(parents=True,exist_ok=False);pd.DataFrame(metrics).to_csv(a.output/'metrics.csv',index=False);pd.DataFrame(forecasts).to_parquet(a.output/'forecasts.parquet',index=False)
    gates={};comparisons=[]
    for method,items in groups.items():
        if method=='prior':continue
        tasks={}
        for j,task in enumerate(TASKS):
            result={}
            for reference in ('prior','CatBoost','numeric-knn','random-context'):
                if reference==method:continue
                dd=[];oo=[];fold_wins=0
                for fold,ids,loss in sorted(items):
                    ref=next(v for v in groups[reference] if v[0]==fold)
                    if not np.array_equal(ids,ref[1]):raise ValueError('PAIRED_IDS_MISMATCH')
                    delta=loss[:,j]-ref[2][:,j];dd.extend(delta);oo.extend(meta['origin'][ids]);fold_wins+=int(np.nanmean(delta)<0)
                ci=paired_ci(np.array(dd),np.array(oo));ci['fold_wins']=fold_wins;ci['PASS']=ci['mean']<0 and fold_wins>=2 and ci['upper']<0;result[reference]=ci;comparisons.append(dict(method=method,task=task,reference=reference,**ci))
            priorpass=result['prior']['PASS'];complex_=method.split('-')[0] in ('TCN','CNN','Kronos');required=['prior']+(['CatBoost'] if complex_ else [])+(['numeric-knn','random-context'] if method.endswith('-knn') and complex_ else [])
            tasks[task]=dict(status='PREDICTIVE_PASS' if all(result[r]['PASS'] for r in required) else 'WEAK_EVIDENCE' if result['prior']['mean']<0 and result['prior']['fold_wins']>=2 else 'NO_SKILL',comparisons=result)
        gates[method]=tasks
    pd.DataFrame(comparisons).to_csv(a.output/'paired-comparisons.csv',index=False);write_json(a.output/'diagnostics.json',extras)
    # Task-specific status is retained; Q exit skill never requires D to pass.
    candidates=[]
    for method,tasks in gates.items():
        passed=[task for task in TASKS if tasks[task]['status']=='PREDICTIVE_PASS']
        if passed and method not in ('random-context',):
            improvement=max(-tasks[t]['comparisons']['prior']['mean'] for t in passed);candidates.append(dict(method=method,tasks=passed,rank=improvement,path=method.endswith('-knn'),status='PREDICTIVE_PASS' if method.endswith('-knn') else 'DIRECT_FORECAST_PASS'))
    candidates=sorted(candidates,key=lambda c:(-c['rank'],c['method']))[:2]
    result=dict(status='SHORTLIST_READY' if candidates else 'NO_SKILL',tasks=gates,shortlist=candidates,CHECK_opened=False,SOL='BLOCKED_PENDING_BTC_PATH_AND_POLICY',policy='PENDING_FROZEN_RECIPE' if any(c['path'] for c in candidates) else 'BLOCKED_NO_PATH_SKILL',economic_goal='TARGET_NOT_MET')
    write_json(a.output/'development-gates.json',result);return result
