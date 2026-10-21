"""Paired, fixed-head development gates; no conditional CHECK opening."""
from pathlib import Path
import json
import numpy as np
from .btc_pattern_data import DAY,folds
from .forecast_independent_data import write_json,sha
TASKS=('D','Q-long','Q-short')

def write_evaluation_contract(inputs,prepared,protocol,methods,compatibility):
    """Bind completed artifacts explicitly; legacy reuse requires a reviewed compatibility receipt."""
    if not compatibility:raise ValueError('COMPATIBILITY_RECEIPT_REQUIRED')
    complete=inputs/'development-complete.json'
    if not complete.exists():raise ValueError('COMPLETION_REQUIRED')
    completion=json.loads(complete.read_text())
    if completion.get('status') not in ('DEVELOPMENT_FITS_COMPLETE_METRICS_PENDING','FORM00_ZERO_FIT_COMPLETE'):raise ValueError('COMPLETE_STATUS_REQUIRED')
    files={str(f.relative_to(inputs)):sha(f) for f in sorted(inputs.glob('F[123]/*.npz'))}
    contract=dict(schema='btc-pattern.evaluation.v2',methods=sorted(methods),protocol_sha256=sha(protocol),prepared_manifest_sha256=sha(prepared/'manifest.json'),completion_sha256=sha(complete),source_hashes={p.name:sha(p) for p in (Path(__file__),Path(__file__).with_name('btc_pattern_data.py'),Path(__file__).with_name('btc_pattern_train.py'))},files=files,compatibility=compatibility)
    write_json(inputs/'evaluation-contract.json',contract)
    return contract


def validate_artifacts(inputs,prepared,protocol):
    contract=json.loads((inputs/'evaluation-contract.json').read_text())
    if contract.get('schema')!='btc-pattern.evaluation.v2' or not contract.get('compatibility'):raise ValueError('EVALUATION_CONTRACT_REQUIRED')
    checks=[(protocol,contract['protocol_sha256']),(prepared/'manifest.json',contract['prepared_manifest_sha256']),(inputs/'development-complete.json',contract['completion_sha256']),*[(Path(__file__).with_name(name),digest) for name,digest in contract['source_hashes'].items()]]
    if any(sha(p)!=h for p,h in checks):raise ValueError('EVALUATION_HASH_MISMATCH')
    required_sources={'btc_pattern_evaluate.py','btc_pattern_data.py','btc_pattern_train.py'}
    if set(contract['source_hashes'])!=required_sources:raise ValueError('SOURCE_MANIFEST_INCOMPLETE')
    completion=json.loads((inputs/'development-complete.json').read_text())
    if completion.get('status') not in ('DEVELOPMENT_FITS_COMPLETE_METRICS_PENDING','FORM00_ZERO_FIT_COMPLETE'):raise ValueError('COMPLETE_STATUS_REQUIRED')
    manifest=json.loads((prepared/'manifest.json').read_text())
    for name in ('metadata.npy','labels.npz'):
        if sha(prepared/name)!=manifest['artifacts'][name]['sha256']:raise ValueError('PREPARED_ARTIFACT_HASH_MISMATCH')
    methods=contract['methods']
    if len(set(methods))!=len(methods) or not set(('prior','CatBoost','numeric-knn','random-context')).issubset(methods):raise ValueError('REQUIRED_METHODS_MISSING')
    actual={str(p.relative_to(inputs)):sha(p) for p in inputs.glob('F*/*.npz')}
    expected={f"{f}/{m}.npz" for f in ('F1','F2','F3') for m in methods}
    if set(actual)!=expected or actual!=contract['files']:raise ValueError('INCOMPLETE_OR_CHANGED_FORECASTS')
    meta=np.load(prepared/'metadata.npy',mmap_mode='r')
    with np.load(prepared/'labels.npz') as labels:
        for fold in folds(meta):
            ids=fold['outer']
            for method in methods:
                with np.load(inputs/fold['name']/(method+'.npz')) as z:
                    if z['ids'].dtype.kind not in 'iu' or not np.array_equal(z['ids'],ids):raise ValueError('CANONICAL_IDS_MISMATCH')
                    for key,truth in [('truth_D',labels['direction'][ids]),('truth_Q',labels['mfe'][ids,:,0]),('truth_Q_upper',labels['mfe'][ids,:,1])]:
                        if not np.array_equal(z[key],truth):raise ValueError('CANONICAL_TRUTH_MISMATCH')
                    n=len(ids);p=z['probabilities'];raw=z['q_raw'];q=z['q_projected'];support=z['support']
                    if p.shape!=(n,3) or raw.shape!=(n,2,3) or q.shape!=raw.shape or support.shape!=(n,):raise ValueError('FORECAST_SCHEMA')
                    if not all(np.isfinite(v).all() for v in (p,raw,q,support)) or (p<0).any() or (p>1).any() or not np.allclose(p.sum(1),1,atol=1e-6,rtol=0):raise ValueError('INVALID_PROBABILITY_OR_FINITE')
                    if not np.array_equal(q,np.maximum(0,np.sort(raw,axis=2))) or (support<0).any() or (support!=support.astype(int)).any():raise ValueError('INVALID_PROJECTION_OR_SUPPORT')
    return contract


def safe_auc(labels,scores):
    from sklearn.metrics import roc_auc_score
    if len(np.unique(labels))!=2:return None
    value=float(roc_auc_score(labels,scores))
    return value if np.isfinite(value) else None


def losses(p,q,d,y):
    valid=d>=0;dl=np.full(len(d),np.nan);dl[valid]=-np.log(np.maximum(p[valid,d[valid]],1e-12))
    error=y[:,:,None]-q;pin=np.maximum(np.array([.2,.5,.8])*error,(np.array([.2,.5,.8])-1)*error).mean(2)
    return np.column_stack((dl,pin))

def paired_ci(delta,origins):
    good=np.isfinite(delta);delta,origins=delta[good],origins[good]
    if not len(delta):return dict(mean=None,lower=None,upper=None,blocks=0,rows=0,draws=1000)
    blocks=origins//(14*DAY);u,inv=np.unique(blocks,return_inverse=True)
    sums=np.bincount(inv,weights=delta);counts=np.bincount(inv);rng=np.random.default_rng(7);which=rng.integers(0,len(u),(1000,len(u)));boot=sums[which].sum(1)/counts[which].sum(1)
    return dict(mean=float(delta.mean()),lower=float(np.quantile(boot,.025)),upper=float(np.quantile(boot,.975)),blocks=len(u),rows=len(delta),draws=1000)

def evaluate(a):
    validate_artifacts(a.input,a.prepared,a.protocol)
    import pandas as pd
    from sklearn.metrics import roc_auc_score
    root=a.prepared # prepared is actual data, input is directory containing fold forecasts
    inputs=a.input;meta=np.load(root/'metadata.npy',mmap_mode='r');groups={};metrics=[];forecasts=[];extras=[]
    for folder in sorted(inputs.glob('F[123]')):
        for f in folder.glob('*.npz'):
            z=dict(np.load(f));ids=z['ids'];p,q,d,y=z['probabilities'],z['q_projected'],z['truth_D'],z['truth_Q'];loss=losses(p,q,d,y);groups.setdefault(f.stem,[]).append((folder.name,ids,loss))
            for j,task in enumerate(TASKS):
                finite=np.isfinite(loss[:,j]);metrics.append(dict(fold=folder.name,method=f.stem,task=task,N=int(finite.sum()),loss=float(loss[finite,j].mean()) if finite.any() else None))
            valid=d>=0;one=np.eye(3)[d[valid]];brier=float(((p[valid]-one)**2).sum(1).mean()) if valid.any() else None;auroc=[]
            for k in range(3):
                auroc.append(safe_auc(d[valid]==k,p[valid,k]))
            extras.append(dict(fold=folder.name,method=f.stem,brier=brier,AUROC=auroc,accuracy=float((p[valid].argmax(1)==d[valid]).mean()) if valid.any() else None,AUROC_undefined_reason=['absent_binary_class_or_empty_valid_D' if v is None else None for v in auroc],ambiguous_D_count=int((~valid).sum()),Q_zero_fraction=(q==0).mean((0,2)).tolist(),raw_crossing_fraction=float((np.diff(z['q_raw'],axis=2)<0).any(2).mean()),raw_pinball=losses(p,z['q_raw'],d,y)[:,1:].mean(0).tolist(),upper_sensitivity_pinball=losses(p,q,d,z['truth_Q_upper'])[:,1:].mean(0).tolist(),coverage=(y[:,:,None]<=q).mean(0).tolist()))
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
                ci=paired_ci(np.array(dd),np.array(oo));ci['fold_wins']=fold_wins;ci['PASS']=ci['mean'] is not None and ci['mean']<0 and fold_wins>=2 and ci['upper']<0;result[reference]=ci;comparisons.append(dict(method=method,task=task,reference=reference,**ci))
            priorpass=result['prior']['PASS'];complex_=method.split('-')[0] in ('TCN','CNN','Kronos');required=['prior']+(['CatBoost'] if complex_ else [])+(['numeric-knn','random-context'] if method.endswith('-knn') and complex_ else [])
            tasks[task]=dict(status='PREDICTIVE_PASS' if all(result[r]['PASS'] for r in required) else 'WEAK_EVIDENCE' if result['prior']['mean'] is not None and result['prior']['mean']<0 and result['prior']['fold_wins']>=2 else 'NO_SKILL',comparisons=result)
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
