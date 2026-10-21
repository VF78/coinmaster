"""Two predeclared DEVELOPMENT-only learning-policy variants.

METRIC_OFF changes only metric coefficient to zero. RECENT180 changes only
prefix/window eligibility, retaining the original metric and all other recipes.
Frozen baseline source and artifacts are never edited.
"""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,time
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from .btc_pattern_data import folds,ms,DAY
from .forecast_independent_data import sha,write_json

MODES=('METRIC_OFF','RECENT180')
FAMILIES=('TCN','CNN')
REFERENCES=('prior','CatBoost','numeric-knn','random-context')


def variant_folds(meta,mode):
    if mode not in MODES:raise ValueError('UNFROZEN_VARIANT')
    for original in folds(meta):
        f=dict(original);start=ms('2024-06-01')
        if mode=='RECENT180':
            start=max(start,f['fit_cutoff']-180*DAY)
            # One fixed start derived from FULL fit cutoff; never shift subfit independently.
            for part in ('subfit','early_stop','refit'):f[part]=f[part][meta['origin'][f[part]]>=start]
        f['window_start']=start
        yield f


def install_metric_off():
    from . import btc_pattern_models as models
    original=models.soft_metric
    def metric_off(*args,**kwargs):
        loss,statistics=original(*args,**kwargs)
        return loss*0,statistics # preserve entropy/support diagnostics; no metric gradient.
    models.soft_metric=metric_off


def verify(a):
    from . import btc_pattern_train as training
    auth=json.loads(a.authorization.read_text());variant=json.loads(a.variant_protocol.read_text())
    sources={str(p):sha(p) for p in Path(training.__file__).parent.glob('btc_pattern_*.py')}
    if a.mode not in auth.get('authorized_modes',[]) or auth.get('variant_source_sha256')!=sha(__file__) or auth.get('variant_protocol_sha256')!=sha(a.variant_protocol):raise ValueError('EXACT_VARIANT_GO_REQUIRED')
    if auth.get('source_hashes')!=sources or auth.get('protocol_sha256')!=sha(a.protocol) or auth.get('prepared_manifest_sha256')!=sha(a.prepared/'manifest.json'):raise ValueError('BASE_SOURCE_PROTOCOL_DATA_DRIFT')
    if auth.get('baseline_completion_sha256')!=sha(a.baseline/'development-complete.json'):raise ValueError('BASE_COMPLETION_DRIFT')
    for name,expected in auth.get('baseline_reference_hashes',{}).items():
        if sha(a.baseline/name)!=expected:raise ValueError('BASE_REFERENCE_DRIFT '+name)
    if len(auth.get('baseline_reference_hashes',{}))!=30:raise ValueError('ALL_30_BASE_FORECAST_GROUPS_REQUIRED')
    if auth.get('image_cache_sha256')!=sha(a.baseline/'images.npy'):raise ValueError('IMAGE_CACHE_DRIFT')
    return auth,variant


def save_forecast(data,path,query,p,q,support=None):
    np.savez(path,ids=query,probabilities=p,q_raw=q,q_projected=np.maximum(0,np.sort(q,axis=2)),support=np.zeros(len(query),int) if support is None else support,truth_D=data.d[query],truth_Q=data.y[query],truth_Q_upper=data.upper[query])


def evaluate_variant(a,output):
    import pandas as pd
    from .btc_pattern_evaluate import evaluate,losses,paired_ci,TASKS
    from .btc_pattern_train import Data
    evaluation=output/'evaluation';evaluate(SimpleNamespace(prepared=a.prepared,input=output,output=evaluation,protocol=a.protocol))
    data=Data(a.prepared);comparisons=[];gates=json.loads((evaluation/'development-gates.json').read_text())
    # RECENT180 must beat BOTH its current controls and the original full-prefix controls.
    for method in [p.stem for p in (output/'F1').glob('*.npz')]:
        references=list(dict.fromkeys([method,*REFERENCES]))
        for refname in references:
            for j,task in enumerate(TASKS):
                delta_all=[];origins=[];wins=0
                for folder in sorted(output.glob('F[123]')):
                    current=dict(np.load(folder/(method+'.npz')));baseline=dict(np.load(a.baseline/folder.name/(refname+'.npz')))
                    if not np.array_equal(current['ids'],baseline['ids']):raise ValueError('ARCHIVED_CONTROL_IDS_MISMATCH')
                    loss=losses(current['probabilities'],current['q_projected'],current['truth_D'],current['truth_Q'])[:,j]
                    baseline_loss=losses(baseline['probabilities'],baseline['q_projected'],baseline['truth_D'],baseline['truth_Q'])[:,j]
                    delta=loss-baseline_loss;wins+=int(np.nanmean(delta)<0);delta_all.extend(delta);origins.extend(data.meta['origin'][current['ids']])
                ci=paired_ci(np.array(delta_all),np.array(origins));comparisons.append(dict(method=method,task=task,archived_reference=refname,fold_wins=wins,PASS=bool(ci['mean']<0 and ci['upper']<0 and wins>=2),**ci))
    pd.DataFrame(comparisons).to_csv(evaluation/'archived-baseline-comparisons.csv',index=False)
    for method,tasks in gates['tasks'].items():
        complex_=method.split('-')[0] in FAMILIES
        required=['prior']+(['CatBoost'] if complex_ else [])+(['numeric-knn','random-context'] if complex_ and method.endswith('-knn') else [])
        for task,details in tasks.items():
            archive={r['archived_reference']:r for r in comparisons if r['method']==method and r['task']==task}
            details['archived_comparisons']=archive
            if details['status']=='PREDICTIVE_PASS' and not all(archive[r]['PASS'] for r in required if r!=method):
                details['status']='WEAK_EVIDENCE' if archive['prior']['mean']<0 and archive['prior']['fold_wins']>=2 else 'NO_SKILL'
                details['archive_gate']='FAILED_ADDITIONAL_ORIGINAL_CONTROL_REQUIREMENT'
    candidates=[]
    for method,tasks in gates['tasks'].items():
        passed=[t for t,v in tasks.items() if v['status']=='PREDICTIVE_PASS']
        if passed and method!='random-context':
            improvement=max(-tasks[t]['comparisons']['prior']['mean'] for t in passed);candidates.append(dict(method=method,tasks=passed,rank=improvement,path=method.endswith('-knn'),status='PREDICTIVE_PASS' if method.endswith('-knn') else 'DIRECT_FORECAST_PASS'))
    gates['shortlist']=sorted(candidates,key=lambda c:(-c['rank'],c['method']))[:2];gates['status']='SHORTLIST_READY' if gates['shortlist'] else 'NO_SKILL';gates['policy']='PENDING_FROZEN_RECIPE' if any(c['path'] for c in gates['shortlist']) else 'BLOCKED_NO_PATH_SKILL';gates['mode']=a.mode;gates['original_controls_required']=True
    write_json(evaluation/'development-gates.json',gates)
    return gates


def run(a):
    import pandas as pd,torch
    from . import btc_pattern_train as training
    auth,variant=verify(a)
    if os.environ.get('PYTORCH_MPS_HIGH_WATERMARK_RATIO')=='0':raise ValueError('MPS_WATERMARK_MUST_REMAIN_ENABLED')
    samples={}
    old_guard=training.resource_guard
    def monitored_guard(device='cpu'):
        current=old_guard(device)
        for key,value in current.items():
            if value is not None:samples[key]=max(samples.get(key,0),int(value))
        current['sampled_maxima_not_exact_peak']=dict(samples)
        return current
    training.resource_guard=monitored_guard
    if a.mode=='METRIC_OFF':install_metric_off()
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    deadline_seconds=min(float(auth['wall_seconds']),max(0.,ms(auth['pipeline_deadline_utc'])/1000-time.time()))
    if deadline_seconds<=0:raise ValueError('BTC_TOTAL_BUDGET_EXPIRED')
    training.DEADLINE=time.monotonic()+deadline_seconds
    a.output.mkdir(parents=True,exist_ok=False);data=training.Data(a.prepared);data.images=np.load(a.baseline/'images.npy',mmap_mode='r');started=time.monotonic();records=[];neighbor_rows=[];learned_cutoffs=[];neural_fits=0;cb_fits=0
    for fold in variant_folds(data.meta,a.mode):
        name=fold['name'];out=a.output/name;out.mkdir();index=fold['refit'];query=fold['outer']
        for part in ('subfit','early_stop','refit','outer'):
            ids=fold[part];cut=fold['inner_cutoff'] if part=='subfit' else fold['outer_end'] if part=='outer' else fold['fit_cutoff']
            if np.any(data.meta['label_end'][ids]>cut):raise ValueError('VARIANT_PURGE_BREACH')
            learned_cutoffs.append(dict(fold=name,part=part,window_start=fold['window_start'],cutoff=cut,N=len(ids),first_origin=int(data.meta['origin'][ids].min()),last_origin=int(data.meta['origin'][ids].max()),max_label_end=int(data.meta['label_end'][ids].max()),ids_sha256=hashlib.sha256(ids.tobytes()).hexdigest()))
        if a.mode=='METRIC_OFF':
            for method in REFERENCES:
                shutil.copyfile(a.baseline/name/(method+'.npz'),out/(method+'.npz'));records.append(dict(fold=name,method=method,rows=len(query),reused_sha256=sha(out/(method+'.npz'))))
        else:
            valid=index[data.d[index]>=0];pp=np.bincount(data.d[valid],minlength=3)/len(valid);pq=np.quantile(data.y[index],[.2,.5,.8],axis=0).T;save_forecast(data,out/'prior.npz',query,np.tile(pp,(len(query),1)),np.tile(pq,(len(query),1,1)))
            dm,ds=training.normalize(data.descriptor,index);iz=training.l2((data.descriptor[index]-dm)/ds);qz=training.l2((data.descriptor[query]-dm)/ds)
            for method,random in [('numeric-knn',False),('random-context',True)]:
                p,q,support,nr=training.empirical(data,index,query,iz,qz,fold['fit_cutoff'],random);save_forecast(data,out/(method+'.npz'),query,p,q,support);neighbor_rows.extend([dict(fold=name,method=method,**r) for r in nr])
            models,iters=training.catboost_fit(data,fold['subfit'],fold['early_stop'],out/'catboost-es');cb_fits+=3;del models
            models,_=training.catboost_fit(data,index,None,out/'catboost-refit',iters);cb_fits+=3;save_forecast(data,out/'CatBoost.npz',query,models[0].predict_proba(data.descriptor[query]),np.stack([m.predict(data.descriptor[query]) for m in models[1:]],axis=1));del models
            records.extend([dict(fold=name,method=method,rows=len(query),reused=False) for method in REFERENCES])
        for family in FAMILIES:
            device='mps' if torch.backends.mps.is_available() else 'cpu'
            if device!='mps':raise RuntimeError('MEASURED_MPS_REQUIRED_NO_SILENT_CPU_FALLBACK')
            state,receipt=training.neural_fit(data,family,fold['subfit'],fold['early_stop'],out/f'{family}-es.pt',device=device);neural_fits+=1;del state
            state,_=training.neural_fit(data,family,index,None,out/f'{family}-refit.pt',epochs=receipt['selected_epochs'],device=device);neural_fits+=1
            z,p,q=training.neural_predict(data,state,np.r_[index,query],device=device);iz,qz=z[:len(index)],z[len(index):];save_forecast(data,out/(family+'-direct.npz'),query,p[len(index):],q[len(index):]);p,q,support,nr=training.empirical(data,index,query,iz,qz,fold['fit_cutoff']);save_forecast(data,out/(family+'-knn.npz'),query,p,q,support);neighbor_rows.extend([dict(fold=name,method=family+'-knn',**r) for r in nr]);del state
            records.extend([dict(fold=name,method=family+'-'+head,rows=len(query),reused=False) for head in ['direct','knn']]);write_json(a.output/'progress.json',dict(mode=a.mode,completed=records,neural_joint_fits=neural_fits,CatBoost_head_fits=cb_fits,CHECK_opened=False,resource=training.resource_guard(device)))
    pd.DataFrame(learned_cutoffs).to_csv(a.output/'learned-cutoffs.csv',index=False);pd.DataFrame(neighbor_rows).to_parquet(a.output/'neighbors.parquet',index=False)
    completion=dict(mode=a.mode,status='VARIANT_FITS_COMPLETE',neural_joint_fits=neural_fits,CatBoost_head_fits=cb_fits,source_sha256=sha(__file__),variant_protocol_sha256=sha(a.variant_protocol),base_source_hashes=auth['source_hashes'],prepared_manifest_sha256=auth['prepared_manifest_sha256'],wall_seconds=time.monotonic()-started,resource=training.resource_guard(),CHECK_opened=False)
    write_json(a.output/'development-complete.json',completion);gates=evaluate_variant(a,a.output);completion['gate_status']=gates['status'];completion['shortlist']=gates['shortlist'];write_json(a.output/'completion.json',completion);return completion


def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=MODES,required=True)
    for name in ['protocol','variant-protocol','authorization','prepared','baseline','output']:p.add_argument('--'+name,type=Path,required=True)
    print(json.dumps(run(p.parse_args())))
if __name__=='__main__':main()
