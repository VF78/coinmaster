"""One full-history CNN recipe: fit-only marginal Q initialization; no ES3."""
from __future__ import annotations
import argparse,contextlib,hashlib,json,os,shutil,time
from pathlib import Path
import numpy as np
from .btc_pattern_data import folds,ms,HOUR,META
from .forecast_independent_data import sha,write_json
from .pattern_quality_variants import save_forecast,evaluate_variant,REFERENCES
from .pattern_full_es3 import block_permutation,setup
MODE='CNN_Q_PRIOR_INIT'


def fit_prior(data,ids,cutoff,expected_ids):
    ids=np.asarray(ids)
    if not np.array_equal(ids,expected_ids) or len(ids)==0 or np.any(data.meta['label_end'][ids]>cutoff):raise ValueError('EXACT_PURGED_FIT_IDS_REQUIRED')
    y=data.y[ids]
    if not np.isfinite(y).all():raise ValueError('FINITE_FIT_TARGETS_REQUIRED')
    return np.quantile(y,[.2,.5,.8],axis=0).T.astype('float32')


@contextlib.contextmanager
def initialized_factory(prior):
    import torch
    from . import btc_pattern_models as models
    original=models.CNN
    class PriorInitializedCNN(original):
        def __init__(self):
            super().__init__() # consume ORIGINAL random initialization first, unchanged RNG.
            with torch.no_grad():
                self.heads.quantiles.weight.zero_();self.heads.quantiles.bias.copy_(torch.as_tensor(prior).reshape(-1))
    models.CNN=PriorInitializedCNN
    try:yield
    finally:models.CNN=original


def prior_fit(data,ids,cutoff,out,es_ids=None,epochs=None):
    from . import btc_pattern_train as training
    prior=fit_prior(data,ids,cutoff,ids)
    with initialized_factory(prior):state,receipt=training.neural_fit(data,'CNN',ids,es_ids,out,epochs=epochs,device='mps')
    write_json(out.with_suffix('.prior-init.json'),dict(fit_N=len(ids),cutoff=cutoff,max_label_end=int(data.meta['label_end'][ids].max()),fit_ids_sha256=__import__('hashlib').sha256(ids.tobytes()).hexdigest(),Q_fit_prior=prior.tolist(),weight_initialization='zero after complete original RNG construction',bias_initialization='fit-only marginalquantiles .2/.5/.8'))
    return state,receipt


def verify(a,synthetic=False):
    from . import btc_pattern_train as training
    auth=json.loads(a.authorization.read_text());protocol=json.loads(a.recipe_protocol.read_text());stage='CNN_Q_PRIOR_INIT_SYNTHETIC_GO' if synthetic else 'CNN_Q_PRIOR_INIT_MARKET_GO'
    if auth.get('stage')!=stage or auth.get('source_sha256')!=sha(__file__) or auth.get('recipe_protocol_sha256')!=sha(a.recipe_protocol):raise ValueError('EXACT_PRIOR_INIT_GO_REQUIRED')
    if auth.get('source_hashes')!={str(p):sha(p) for p in Path(training.__file__).parent.glob('btc_pattern_*.py')}:raise ValueError('CORE_SOURCE_DRIFT')
    for p,digest in auth.get('additional_source_hashes',{}).items():
        if sha(p)!=digest:raise ValueError('IMPORTED_HELPER_DRIFT')
    if not synthetic:
        if auth.get('protocol_sha256')!=sha(a.protocol) or auth.get('prepared_manifest_sha256')!=sha(a.prepared/'manifest.json'):raise ValueError('DATA_PROTOCOL_DRIFT')
        if len(auth.get('baseline_forecast_hashes',{}))!=30:raise ValueError('ALL_BASE_FORECASTS_REQUIRED')
        for p,digest in auth['baseline_forecast_hashes'].items():
            if sha(a.baseline/p)!=digest:raise ValueError('BASE_REFERENCE_DRIFT')
        if auth.get('image_cache_sha256')!=sha(a.baseline/'images.npy'):raise ValueError('IMAGE_CACHE_DRIFT')
        receipt=json.loads(a.qa_receipt.read_text())
        if auth.get('qa_receipt_sha256')!=sha(a.qa_receipt) or receipt.get('PASS') is not True or receipt.get('source_sha256')!=sha(__file__):raise ValueError('ACTUAL_PRIOR_INIT_CNN_QA_PASS_REQUIRED')
    return auth,protocol


def synthetic(a):
    auth,protocol=verify(a,synthetic=True);training=setup(auth);a.output.mkdir(parents=True,exist_ok=False);began=time.monotonic();rng=np.random.default_rng(701);n=768;block=8
    # Chronological blocks contain a stable visual/context class plus small noise.
    latent=np.repeat(rng.integers(0,3,n//block),block);data=type('SyntheticData',(),{})();data.c=rng.normal(0,.05,(n,12)).astype('float32');data.c[:,:3]+=np.eye(3)[latent]*2
    colors=np.eye(3,dtype='uint8')*200+20;data.images=np.broadcast_to(colors[latent,None,None,:],(n,224,224,3)).copy();data.x=np.zeros((n,2,64,6),'float32');data.kronos=None
    data.meta=np.zeros(n,dtype=META);data.meta['origin']=np.arange(n)*100*HOUR;data.meta['label_end']=data.meta['origin']+72*HOUR
    original_d=latent.astype('int64');original_y=np.stack((.2+.5*latent,1.2-.4*latent),axis=1).astype('float32');signature=np.tile(latent[:,None],(1,12)).astype('float32')+rng.normal(0,.05,(n,12)).astype('float32');fit=np.arange(512);query=np.arange(512,n);result=[]
    for name in ['positive','block_shuffled']:
        permutation=np.arange(n)
        if name=='block_shuffled':
            permutation[:512]=block_permutation(512,block,702);permutation[512:]=512+block_permutation(256,block,703)
        data.d=original_d[permutation];data.y=original_y[permutation];data.signature=signature[permutation]
        state,receipt=prior_fit(data,fit,int(data.meta['label_end'][fit].max()),a.output/f'{name}.pt',epochs=8);_,p,q=training.neural_predict(data,state,query,device='mps');target=data.d[query];acc=float((p.argmax(1)==target).mean());logloss=float(-np.log(np.maximum(p[np.arange(len(target)),target],1e-12)).mean());prior=np.bincount(data.d[fit],minlength=3)/len(fit);priorloss=float(-np.log(prior[target]).mean());levels=np.array([.2,.5,.8]);prior_q=np.quantile(data.y[fit],levels,axis=0).T
        def pinball(prediction):
            error=data.y[query,:,None]-prediction
            return np.maximum(levels*error,(levels-1)*error).mean(axis=(0,2))
        qprior=pinball(prior_q[None]);qraw=pinball(q);qprojected=pinball(np.maximum(0,np.sort(q,axis=2)))
        result.append(dict(control=name,accuracy=acc,D_logloss=logloss,prior_logloss=priorloss,Q_raw_pinball_long_short=qraw.tolist(),Q_projected_pinball_long_short=qprojected.tolist(),Q_fit_prior_pinball_long_short=qprior.tolist(),Q_raw_loss_ratio_to_prior=(qraw/qprior).tolist(),Q_projected_loss_ratio_to_prior=(qprojected/qprior).tolist(),epochs=8,fit_N=512,heldout_N=256,block_hours=800,permutation_sha256=hashlib.sha256(permutation.tobytes()).hexdigest(),checkpoint_sha256=sha(a.output/f'{name}.pt'),fit_receipt=receipt));del state
    passed=result[0]['accuracy']>=.7 and result[0]['D_logloss']<result[0]['prior_logloss']-.1 and result[1]['accuracy']<.55
    for field in ['Q_raw_loss_ratio_to_prior','Q_projected_loss_ratio_to_prior']:
        passed=passed and bool(np.all(np.array(result[0][field])<=.8)) and bool(np.all(np.array(result[1][field])>=.8))
    receipt=dict(status='ACTUAL_TRAINABLE_CNN_SYNTHETIC_QA',PASS=bool(passed),source_sha256=sha(__file__),protocol_sha256=sha(a.recipe_protocol),synthetic_fits=2,market_fits=0,CHECK_used=False,wall_seconds=time.monotonic()-began,results=result,meaning='plumbing diagnostic only; no market/OOS skill evidence')
    write_json(a.output/'completion.json',receipt);return receipt


def run(a):
    import pandas as pd
    auth,protocol=verify(a);training=setup(auth);a.output.mkdir(parents=True,exist_ok=False);data=training.Data(a.prepared);data.images=np.load(a.baseline/'images.npy',mmap_mode='r');began=time.monotonic();records=[];neighbors=[];learned_fits=0
    for fold in folds(data.meta):
        name=fold['name'];out=a.output/name;out.mkdir()
        for method in REFERENCES:shutil.copyfile(a.baseline/name/(method+'.npz'),out/(method+'.npz'))
        state,receipt=prior_fit(data,fold['subfit'],fold['inner_cutoff'],out/'CNN-es.pt',fold['early_stop']);learned_fits+=1;del state
        state,refit=prior_fit(data,fold['refit'],fold['fit_cutoff'],out/'CNN-refit.pt',epochs=receipt['selected_epochs']);learned_fits+=1
        index=fold['refit'];query=fold['outer'];z,p,q=training.neural_predict(data,state,np.r_[index,query],device='mps');save_forecast(data,out/'CNN-direct.npz',query,p[len(index):],q[len(index):]);p,q,support,nr=training.empirical(data,index,query,z[:len(index)],z[len(index):],fold['fit_cutoff']);save_forecast(data,out/'CNN-knn.npz',query,p,q,support);neighbors.extend([dict(fold=name,method='CNN-knn',**r) for r in nr]);del state
        records.append(dict(fold=name,selected_epochs=receipt['selected_epochs'],subfit_N=len(fold['subfit']),refit_N=len(index),outer_N=len(query),inner_cutoff=fold['inner_cutoff'],fit_cutoff=fold['fit_cutoff']));write_json(a.output/'progress.json',dict(completed=records,market_joint_fits=learned_fits,CHECK_used=False))
    pd.DataFrame(neighbors).to_parquet(a.output/'neighbors.parquet',index=False);completion=dict(mode=MODE,status='VARIANT_FITS_COMPLETE',source_sha256=sha(__file__),recipe_protocol_sha256=sha(a.recipe_protocol),market_joint_fits=learned_fits,folds=records,CHECK_opened=False,wall_seconds=time.monotonic()-began,resource=training.resource_guard());write_json(a.output/'development-complete.json',completion);a.mode=MODE;gates=evaluate_variant(a,a.output);completion.update(gate_status=gates['status'],shortlist=gates['shortlist']);write_json(a.output/'completion.json',completion);return completion


def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['synthetic','market'],required=True)
    for name in ['protocol','recipe-protocol','authorization','prepared','baseline','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--qa-receipt',type=Path);a=p.parse_args();print(json.dumps(synthetic(a) if a.stage=='synthetic' else run(a)))
if __name__=='__main__':main()
