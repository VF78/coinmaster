"""One full-history CNN ES policy; original model/loss and core source immutable."""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,time
from pathlib import Path
import numpy as np
from .btc_pattern_data import folds,ms,DAY,HOUR,META
from .forecast_independent_data import sha,write_json
from .pattern_quality_variants import save_forecast,evaluate_variant,REFERENCES
MODE='FULL_ES3_CNN'
OFFSETS=(90,45,0)


def anchor_ids(meta,cutoff,offset):
    anchor=cutoff-offset*DAY;inner=anchor-28*DAY;start=ms('2024-06-01');eligible=meta['valid']&meta['observed']
    take=lambda a,b:np.flatnonzero(eligible&(meta['origin']>=a)&(meta['origin']<b)&(meta['label_end']<=b))
    return dict(offset_days=offset,anchor=anchor,inner_cutoff=inner,subfit=take(start,inner),early_stop=take(inner,anchor))


def median_epochs(selected):
    if len(selected)!=3 or any(int(x)!=x or x<1 or x>30 for x in selected):raise ValueError('EXACT_THREE_VALID_EPOCHS_REQUIRED')
    return int(np.median(selected))


def block_permutation(n,block,seed):
    if n%block:raise ValueError('COMPLETE_BLOCKS_REQUIRED')
    return np.arange(n).reshape(-1,block)[np.random.default_rng(seed).permutation(n//block)].reshape(-1)


def verify(a,qa=False):
    from . import btc_pattern_train as training
    auth=json.loads(a.authorization.read_text());protocol=json.loads(a.es_protocol.read_text())
    expected='FULL_ES3_CNN_SYNTHETIC_GO' if qa else 'FULL_ES3_CNN_MARKET_GO'
    if auth.get('stage')!=expected or auth.get('source_sha256')!=sha(__file__) or auth.get('es_protocol_sha256')!=sha(a.es_protocol):raise ValueError('EXACT_FULL_ES_GO_REQUIRED')
    source={str(p):sha(p) for p in Path(training.__file__).parent.glob('btc_pattern_*.py')}
    if auth.get('source_hashes')!=source:raise ValueError('FROZEN_CORE_DRIFT')
    for file,digest in auth.get('additional_source_hashes',{}).items():
        if sha(file)!=digest:raise ValueError('IMPORTED_HELPER_DRIFT')
    if not qa:
        if auth.get('protocol_sha256')!=sha(a.protocol) or auth.get('prepared_manifest_sha256')!=sha(a.prepared/'manifest.json'):raise ValueError('PROTOCOL_DATA_DRIFT')
        if len(auth.get('reused_file_hashes',{}))!=50:raise ValueError('EXACT_50_REUSED_BASE_FILES_REQUIRED')
        for file,digest in auth['reused_file_hashes'].items():
            if sha(a.baseline/file)!=digest:raise ValueError('REUSED_BASE_ARTIFACT_DRIFT '+file)
        if auth.get('image_cache_sha256')!=sha(a.baseline/'images.npy'):raise ValueError('IMAGE_CACHE_DRIFT')
        q=json.loads(a.qa_receipt.read_text())
        if auth.get('qa_receipt_sha256')!=sha(a.qa_receipt) or q.get('PASS') is not True or q.get('source_sha256')!=sha(__file__):raise ValueError('ACTUAL_CNN_SYNTHETIC_QA_PASS_REQUIRED')
    return auth,protocol


def setup(auth):
    import torch
    from . import btc_pattern_train as training
    if os.environ.get('PYTORCH_MPS_HIGH_WATERMARK_RATIO')=='0' or not torch.backends.mps.is_available():raise ValueError('MPS_DEFAULT_GUARD_REQUIRED')
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    remaining=ms(auth['pipeline_deadline_utc'])/1000-time.time()
    if remaining<=0:raise ValueError('PIPELINE_BUDGET_EXPIRED')
    training.DEADLINE=time.monotonic()+min(remaining,float(auth['wall_seconds']))
    return training


def synthetic(a):
    auth,protocol=verify(a,qa=True);training=setup(auth);a.output.mkdir(parents=True,exist_ok=False);began=time.monotonic();rng=np.random.default_rng(701);n=768;block=8
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
        state,receipt=training.neural_fit(data,'CNN',fit,None,a.output/f'{name}.pt',epochs=8,device='mps');_,p,q=training.neural_predict(data,state,query,device='mps');target=data.d[query];acc=float((p.argmax(1)==target).mean());logloss=float(-np.log(np.maximum(p[np.arange(len(target)),target],1e-12)).mean());prior=np.bincount(data.d[fit],minlength=3)/len(fit);priorloss=float(-np.log(prior[target]).mean());levels=np.array([.2,.5,.8]);prior_q=np.quantile(data.y[fit],levels,axis=0).T
        def pinball(prediction):
            error=data.y[query,:,None]-prediction
            return np.maximum(levels*error,(levels-1)*error).mean(axis=(0,2))
        qprior=pinball(prior_q[None]);qraw=pinball(q);qprojected=pinball(np.maximum(0,np.sort(q,axis=2)))
        result.append(dict(control=name,accuracy=acc,D_logloss=logloss,prior_logloss=priorloss,Q_raw_pinball_long_short=qraw.tolist(),Q_projected_pinball_long_short=qprojected.tolist(),Q_fit_prior_pinball_long_short=qprior.tolist(),Q_raw_loss_ratio_to_prior=(qraw/qprior).tolist(),Q_projected_loss_ratio_to_prior=(qprojected/qprior).tolist(),epochs=8,fit_N=512,heldout_N=256,block_hours=800,permutation_sha256=hashlib.sha256(permutation.tobytes()).hexdigest(),checkpoint_sha256=sha(a.output/f'{name}.pt'),fit_receipt=receipt));del state
    passed=result[0]['accuracy']>=.7 and result[0]['D_logloss']<result[0]['prior_logloss']-.1 and result[1]['accuracy']<.55
    for field in ['Q_raw_loss_ratio_to_prior','Q_projected_loss_ratio_to_prior']:
        passed=passed and bool(np.all(np.array(result[0][field])<=.8)) and bool(np.all(np.array(result[1][field])>=.8))
    receipt=dict(status='ACTUAL_TRAINABLE_CNN_SYNTHETIC_QA',PASS=bool(passed),source_sha256=sha(__file__),protocol_sha256=sha(a.es_protocol),synthetic_fits=2,market_fits=0,CHECK_used=False,wall_seconds=time.monotonic()-began,results=result,meaning='plumbing diagnostic only; no market/OOS skill evidence')
    write_json(a.output/'completion.json',receipt);return receipt


def regime_arrays(data):
    minutes=np.load(data.path/'minutes.npy',mmap_mode='r');ret=np.full(len(data.meta),np.nan);vol=ret.copy()
    for i,j in enumerate(data.meta['entry_index']-1):
        if j-1-30*24*60<0:continue
        closes=minutes[j-1-60*np.arange(720,-1,-1),3];returns=np.diff(np.log(closes));ret[i]=np.log(closes[-1]/closes[0]);vol[i]=np.std(returns,ddof=1)
    return ret,vol


def regime_counts(ids,fit,ret,vol):
    threshold=float(np.nanmedian(vol[fit]));labels=np.full(len(ids),'UNKNOWN',dtype='<U12');known=np.isfinite(ret[ids])&np.isfinite(vol[ids]);labels[known]=np.char.add(np.where(ret[ids][known]>=0,'UP_','DOWN_'),np.where(vol[ids][known]>=threshold,'HIGH','LOW'))
    return threshold,{str(k):int(v) for k,v in zip(*np.unique(labels,return_counts=True))}


def run(a):
    import pandas as pd
    auth,protocol=verify(a);training=setup(auth);began=time.monotonic();a.output.mkdir(parents=True,exist_ok=False);data=training.Data(a.prepared);data.images=np.load(a.baseline/'images.npy',mmap_mode='r');records=[];nr=[];anchors=[];fits=0
    baseline_neighbors=pd.read_parquet(a.baseline/'neighbors.parquet');regime_ret,regime_vol=regime_arrays(data)
    for fold in folds(data.meta):
        name=fold['name'];out=a.output/name;out.mkdir();selected=[]
        for offset in OFFSETS:
            anchor=anchor_ids(data.meta,fold['fit_cutoff'],offset)
            if offset==0:
                for suffix in ['pt','receipt.json','curve.json']:shutil.copyfile(a.baseline/name/f'CNN-es.{suffix}',out/f'CNN-anchor0-es.{suffix}')
                receipt=json.loads((out/'CNN-anchor0-es.receipt.json').read_text())
            else:
                state,receipt=training.neural_fit(data,'CNN',anchor['subfit'],anchor['early_stop'],out/f'CNN-anchor{offset}-es.pt',device='mps');fits+=1;del state
            selected.append(receipt['selected_epochs'])
            for role in ['subfit','early_stop']:
                ids=anchor[role];threshold,counts=regime_counts(ids,anchor['subfit'],regime_ret,regime_vol);anchors.append(dict(regime_counts_json=json.dumps(counts,sort_keys=True),regime_vol_threshold_subfit_only=threshold,fold=name,offset_days=offset,role=role,N=len(ids),first_origin=int(data.meta['origin'][ids[0]]),last_origin=int(data.meta['origin'][ids[-1]]),max_label_end=int(data.meta['label_end'][ids].max()),inner_cutoff=anchor['inner_cutoff'],anchor=anchor['anchor'],selected_epochs=receipt['selected_epochs'],reused=offset==0,ids_sha256=hashlib.sha256(ids.tobytes()).hexdigest()))
        epochs=median_epochs(selected);old=json.loads((a.baseline/name/'CNN-refit.receipt.json').read_text())['selected_epochs'];reuse=epochs==old
        for method in REFERENCES:shutil.copyfile(a.baseline/name/(method+'.npz'),out/(method+'.npz'))
        if reuse:
            for suffix in ['pt','receipt.json','curve.json']:shutil.copyfile(a.baseline/name/f'CNN-refit.{suffix}',out/f'CNN-refit.{suffix}')
            for head in ['direct','knn']:shutil.copyfile(a.baseline/name/f'CNN-{head}.npz',out/f'CNN-{head}.npz')
            nr.extend(baseline_neighbors[(baseline_neighbors['fold']==name)&(baseline_neighbors['method']=='CNN-knn')].to_dict('records'))
        else:
            state,_=training.neural_fit(data,'CNN',fold['refit'],None,out/'CNN-refit.pt',epochs=epochs,device='mps');fits+=1;index=fold['refit'];query=fold['outer'];z,p,q=training.neural_predict(data,state,np.r_[index,query],device='mps');save_forecast(data,out/'CNN-direct.npz',query,p[len(index):],q[len(index):]);p,q,support,neighbors=training.empirical(data,index,query,z[:len(index)],z[len(index):],fold['fit_cutoff']);save_forecast(data,out/'CNN-knn.npz',query,p,q,support);nr.extend([dict(fold=name,method='CNN-knn',**r) for r in neighbors]);del state
        records.append(dict(fold=name,anchor_epochs=selected,median_epochs=epochs,baseline_epochs=old,refit_and_forecasts_reused=reuse,market_joint_fits=fits));write_json(a.output/'progress.json',dict(completed=records,CHECK_used=False));pd.DataFrame(anchors).to_csv(a.output/'anchor-ledger.csv',index=False)
    pd.DataFrame(nr).to_parquet(a.output/'neighbors.parquet',index=False);completion=dict(mode=MODE,status='VARIANT_FITS_COMPLETE',source_sha256=sha(__file__),protocol_sha256=sha(a.es_protocol),market_joint_fits=fits,synthetic_fits=0,folds=records,CHECK_opened=False,wall_seconds=time.monotonic()-began,resource=training.resource_guard());write_json(a.output/'development-complete.json',completion);a.mode=MODE;gates=evaluate_variant(a,a.output);completion.update(gate_status=gates['status'],shortlist=gates['shortlist']);write_json(a.output/'completion.json',completion);return completion


def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['synthetic','market'],required=True)
    for name in ['protocol','es-protocol','authorization','prepared','baseline','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--qa-receipt',type=Path);a=p.parse_args();print(json.dumps(synthetic(a) if a.stage=='synthetic' else run(a)))
if __name__=='__main__':main()
