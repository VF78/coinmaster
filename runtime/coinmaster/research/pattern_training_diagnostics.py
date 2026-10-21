"""Read-only post-development diagnostic inference; no model fits or CHECK use."""
import argparse,json,time
from pathlib import Path
import numpy as np
from .btc_pattern_data import folds,ms
from .btc_pattern_train import Data,neural_predict
from .btc_pattern_evaluate import losses,TASKS


def run(a):
    import pandas as pd,torch
    from catboost import CatBoostClassifier,CatBoostRegressor
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    if not (a.main_run/'development-complete.json').exists():raise ValueError('DIAGNOSTICS_REQUIRE_COMPLETE_FIXED_BASELINE')
    data=Data(a.prepared);data.images=np.load(a.main_run/'images.npy',mmap_mode='r');data.kronos=np.load(a.main_run/'kronos-cache.npy',mmap_mode='r');a.output.mkdir(parents=True,exist_ok=False);rows=[];drift=[];began=time.monotonic()
    def record(fold,method,role,ids,p,q):
        qproject=np.maximum(0,np.sort(q,axis=2));score=losses(p,qproject,data.d[ids],data.y[ids])
        for j,task in enumerate(TASKS):rows.append(dict(fold=fold,method=method,role=role,task=task,N=int(np.isfinite(score[:,j]).sum()),loss=float(np.nanmean(score[:,j])),q_score='fixed max0/sort projection',fit_in_sample='fit' in role.lower()))
    for fold in folds(data.meta):
        folder=a.main_run/fold['name']
        roles=[('subfit_in_sample',fold['subfit'],'es'),('inner_early_stop',fold['early_stop'],'es'),('refit_in_sample',fold['refit'],'refit')]
        for model in ['TCN','Kronos','CNN']:
            for role,ids,version in roles:
                state=torch.load(folder/f'{model}-{version}.pt',weights_only=False,map_location='cpu');_,p,q=neural_predict(data,state,ids,device='mps' if model in ('TCN','CNN') and torch.backends.mps.is_available() else 'cpu');record(fold['name'],model,role,ids,p,q);del state
            z=dict(np.load(folder/(model+'-direct.npz')));record(fold['name'],model,'outer_validation',z['ids'],z['probabilities'],z['q_raw'])
        for role,ids,version in roles:
            models=[]
            for h in range(3):
                model=CatBoostClassifier() if h==0 else CatBoostRegressor();model.load_model(str(folder/f'catboost-{version}-head{h}.cbm'));models.append(model)
            p=models[0].predict_proba(data.descriptor[ids]);q=np.stack([m.predict(data.descriptor[ids]) for m in models[1:]],axis=1);record(fold['name'],'CatBoost',role,ids,p,q);del models
            fit=fold['subfit'] if version=='es' else fold['refit'];valid=fit[data.d[fit]>=0];priorp=np.bincount(data.d[valid],minlength=3)/len(valid);priorq=np.quantile(data.y[fit],[.2,.5,.8],axis=0).T;record(fold['name'],'prior',role,ids,np.tile(priorp,(len(ids),1)),np.tile(priorq,(len(ids),1,1)))
        for name in ['CatBoost','prior']:
            z=dict(np.load(folder/(name+'.npz')));record(fold['name'],name,'outer_validation',z['ids'],z['probabilities'],z['q_raw'])
        for role,ids in [('subfit',fold['subfit']),('inner_early_stop',fold['early_stop']),('refit',fold['refit']),('outer_validation',fold['outer'])]:
            y=data.y[ids];d=data.d[ids];valid=d>=0
            drift.append(dict(fold=fold['name'],role=role,N=len(ids),D_UP=float((d[valid]==0).mean()),D_DOWN=float((d[valid]==1).mean()),D_NONE=float((d[valid]==2).mean()),ambiguity=float((~valid).mean()),long_Q20=float(np.quantile(y[:,0],.2)),long_Q50=float(np.quantile(y[:,0],.5)),long_Q80=float(np.quantile(y[:,0],.8)),short_Q20=float(np.quantile(y[:,1],.2)),short_Q50=float(np.quantile(y[:,1],.5)),short_Q80=float(np.quantile(y[:,1],.8)),long_zero=float((y[:,0]==0).mean()),short_zero=float((y[:,1]==0).mean())))
    pd.DataFrame(rows).to_csv(a.output/'fit-es-outer-losses.csv',index=False);pd.DataFrame(drift).to_csv(a.output/'label-distribution-drift.csv',index=False)
    receipt=dict(status='READ_ONLY_DIAGNOSTICS_COMPLETE',learned_fits=0,CHECK_used=False,rows=len(rows),wall_seconds=time.monotonic()-began)
    (a.output/'completion.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt

def main():
    p=argparse.ArgumentParser()
    for name in ['prepared','main-run','output']:p.add_argument('--'+name,type=Path,required=True)
    print(json.dumps(run(p.parse_args())))
if __name__=='__main__':main()
