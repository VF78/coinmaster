"""Predeclared mandatory 4h-only paired control; no independent promotion.

Reuses the frozen causal/fit machinery. It changes only the 64x4h window
branch; hourly causal context is shared exactly, per the owner contract.
"""
import argparse,json,time
from pathlib import Path
import numpy as np
from .forecast_independent_data import sha,write_json
from .btc_pattern_data import folds
from .btc_pattern_evaluate import losses,paired_ci,TASKS


def run(a):
    import torch,pandas as pd
    from . import btc_pattern_train as training
    from . import btc_pattern_models as models
    auth=json.loads(a.authorization.read_text())
    if auth.get('fourhour_control')!=a.family or auth.get('protocol_sha256')!=sha(a.protocol) or auth.get('control_source_sha256')!=sha(__file__):raise ValueError('EXACT_4H_CONTROL_GO_REQUIRED')
    if auth.get('source_hashes')!={str(p):sha(p) for p in Path(training.__file__).parent.glob('btc_pattern_*.py')} or auth.get('prepared_manifest_sha256')!=sha(a.prepared/'manifest.json'):raise ValueError('FOURH_BASE_OR_DATA_DRIFT')
    torch.set_num_threads(4);torch.set_num_interop_threads(1);training.DEADLINE=time.monotonic()+auth.get('wall_seconds',21600)
    a.output.mkdir(parents=True,exist_ok=False);data=training.Data(a.prepared);data.x=data.x[:,0:1];data.descriptor=np.column_stack((np.asarray(data.x).reshape(len(data.x),16,4,6).mean(2).reshape(len(data.x),-1),data.c)).astype('float32')
    if a.family=='TCN':
        base=models.TCN
        class FourHourTCN(base):
            def __init__(self):super().__init__(branches=1)
        models.TCN=FourHourTCN
    if a.family=='Kronos':
        base=models.Projection
        class FourHourProjection(base):
            def __init__(self):super().__init__(size=512)
        models.Projection=FourHourProjection;data.kronos=np.load(a.main_run/'kronos-cache.npy',mmap_mode='r')[:,:512]
    results=[];neighbor_rows=[];comparisons=[];all_deltas={};origins={};forecasts=[]
    for fold in folds(data.meta):
        path=a.output/fold['name'];path.mkdir();index=fold['refit'];query=fold['outer']
        if a.family=='numeric-knn':
            dm,ds=training.normalize(data.descriptor,index);iz=training.l2((data.descriptor[index]-dm)/ds);qz=training.l2((data.descriptor[query]-dm)/ds);pp,qq,support,nr=training.empirical(data,index,query,iz,qz,fold['fit_cutoff']);neighbor_rows.extend([dict(fold=fold['name'],**r) for r in nr]);predictions={'knn':(pp,qq,support)}
        elif a.family=='CatBoost':
            model,iters=training.catboost_fit(data,fold['subfit'],fold['early_stop'],path/'es');del model
            model,_=training.catboost_fit(data,index,None,path/'refit',iters);p=model[0].predict_proba(data.descriptor[query]);q=np.stack([m.predict(data.descriptor[query]) for m in model[1:]],axis=1);del model
            predictions={'direct':(p,q,None)}
        else:
            device='mps' if a.family=='TCN' and torch.backends.mps.is_available() else 'cpu'
            state,receipt=training.neural_fit(data,a.family,fold['subfit'],fold['early_stop'],path/'es.pt',device=device);del state
            state,_=training.neural_fit(data,a.family,index,None,path/'refit.pt',epochs=receipt['selected_epochs'],device=device);z,p,q=training.neural_predict(data,state,np.r_[index,query],device=device);iz,qz=z[:len(index)],z[len(index):]
            pp,qq,support,nr=training.empirical(data,index,query,iz,qz,fold['fit_cutoff']);neighbor_rows.extend([dict(fold=fold['name'],**r) for r in nr]);predictions={'direct':(p[len(index):],q[len(index):],None),'knn':(pp,qq,support)}
        for head,(p,q,support) in predictions.items():
            projected=np.maximum(0,np.sort(q,axis=2));loss=losses(p,projected,data.d[query],data.y[query]);main_name=a.family if a.family in ('CatBoost','numeric-knn') else a.family+'-'+head
            main=dict(np.load(a.main_run/fold['name']/(main_name+'.npz')));prior=dict(np.load(a.main_run/fold['name']/'prior.npz'))
            if not np.array_equal(main['ids'],query) or not np.array_equal(prior['ids'],query):raise ValueError('FOURH_PAIRED_IDS_DIFFER')
            np.savez(path/(head+'.npz'),ids=query,probabilities=p,q_raw=q,q_projected=projected,truth_D=data.d[query],truth_Q=data.y[query],support=np.zeros(len(query),int) if support is None else support)
            for j,task in enumerate(TASKS):
                results.append(dict(fold=fold['name'],model=a.family,variant='4h-'+head,task=task,loss=float(np.nanmean(loss[:,j]))))
                for refname,ref in [('prior',prior),('same-family-4h+1h',main)]:
                    delta=loss[:,j]-losses(ref['probabilities'],ref['q_projected'],ref['truth_D'],ref['truth_Q'])[:,j];key=(head,task,refname);all_deltas.setdefault(key,[]).extend(delta);origins.setdefault(key,[]).extend(data.meta['origin'][query])
            for i,oi in enumerate(query):forecasts.append(dict(fold=fold['name'],variant='4h-'+head,id=int(oi),origin=int(data.meta['origin'][oi]),probabilities=p[i].tolist(),q_raw=q[i].tolist(),q_projected=projected[i].tolist(),truth_D=int(data.d[oi]),truth_Q=data.y[oi].tolist()))
    for key,delta in all_deltas.items():comparisons.append(dict(variant=key[0],task=key[1],reference=key[2],**paired_ci(np.array(delta),np.array(origins[key]))))
    pd.DataFrame(results).to_csv(a.output/'metrics.csv',index=False);pd.DataFrame(comparisons).to_csv(a.output/'paired-comparisons.csv',index=False);pd.DataFrame(forecasts).to_parquet(a.output/'forecasts.parquet',index=False)
    if neighbor_rows:pd.DataFrame(neighbor_rows).to_parquet(a.output/'neighbors.parquet',index=False)
    receipt=dict(status='FOURH_CONTROL_COMPLETE',family=a.family,auxiliary_only=True,main_recipe_unchanged=True,independent_CHECK_promotion=False,CB_head_fits=18 if a.family=='CatBoost' else 0,neural_joint_fits=6 if a.family in ('TCN','Kronos') else 0,scaler_fits=3 if a.family=='numeric-knn' else 0,source_sha256=sha(__file__))
    write_json(a.output/'completion.json',receipt);return receipt


def main():
    p=argparse.ArgumentParser();p.add_argument('--family',choices=['CatBoost','TCN','Kronos','numeric-knn'],required=True)
    for name in ['protocol','prepared','main-run','output','authorization']:p.add_argument('--'+name,type=Path,required=True)
    print(json.dumps(run(p.parse_args())))
if __name__=='__main__':main()
