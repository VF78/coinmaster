"""Reviewed single-change FORM01/02/03 runner; never opens CHECK or trains controls."""
import argparse,json,os,shutil,time
from pathlib import Path
import numpy as np
from .btc_pattern_data import folds
from .btc_pattern_train import Data,neural_fit,neural_predict,normalize,l2,empirical,resource_guard
from .btc_pattern_evaluate import evaluate,write_evaluation_contract,losses,paired_ci
from .forecast_independent_data import sha,write_json
from .pattern_form_models import full_descriptor

def source_hashes():
    root=Path(__file__).parent
    names=['btc_pattern_data.py','btc_pattern_train.py','btc_pattern_evaluate.py','btc_pattern_models.py','pattern_form_models.py','pattern_form_experiment.py']
    return {str(root/n):sha(root/n) for n in names}

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['context','flat','spatial'],required=True)
    for name in ('prepared','baseline','protocol','authorization','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--images',type=Path);p.add_argument('--device',choices=['cpu','mps'],default='cpu');a=p.parse_args()
    import torch,pandas as pd
    from . import btc_pattern_train as training
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    auth=json.loads(a.authorization.read_text());protocol=json.loads(a.protocol.read_text())
    if auth.get('mode')!=a.mode or auth.get('source_hashes')!=source_hashes() or auth.get('protocol_sha256')!=sha(a.protocol) or auth.get('prepared_manifest_sha256')!=sha(a.prepared/'manifest.json') or auth.get('device')!=a.device:raise ValueError('EXACT_FORM_MODE_GO_REQUIRED')
    if os.environ.get('PYTORCH_MPS_HIGH_WATERMARK_RATIO')=='0':raise ValueError('WATERMARK_DISABLED')
    if a.device=='mps' and not torch.backends.mps.is_available():raise ValueError('REQUESTED_MPS_UNAVAILABLE')
    if auth.get('baseline_contract_sha256')!=sha(a.baseline/'evaluation-contract.json'):raise ValueError('BASELINE_COMPATIBILITY_HASH')
    baseline_contract=json.loads((a.baseline/'evaluation-contract.json').read_text())
    if sha(a.baseline/'development-complete.json')!=baseline_contract['completion_sha256']:raise ValueError('BASELINE_COMPLETION_CHANGED')
    if baseline_contract['prepared_manifest_sha256']!=sha(a.prepared/'manifest.json'):raise ValueError('BASELINE_DATA_MISMATCH')
    for name,digest in baseline_contract['files'].items():
        if sha(a.baseline/name)!=digest:raise ValueError('IMMUTABLE_BASELINE_CHANGED')
    manifest=json.loads((a.prepared/'manifest.json').read_text())
    for name in ('metadata.npy','features.npy','context.npy','raw.npy','labels.npz'):
        if sha(a.prepared/name)!=manifest['artifacts'][name]['sha256']:raise ValueError('PREPARED_ARTIFACT_HASH_MISMATCH')
    start=time.monotonic();training.DEADLINE=start+auth['wall_seconds'];a.output.mkdir(parents=True,exist_ok=False);data=Data(a.prepared)
    if a.mode=='spatial':
        if a.images is None or sha(a.images)!=auth.get('image_cache_sha256'):raise ValueError('ORIGINAL_IMAGE_CACHE_REQUIRED')
        data.images=np.load(a.images,mmap_mode='r')
    kind={'context':'Context','flat':'Flat','spatial':'CNNSpatial'}[a.mode];ledger=[];neighbors=[];fits=0;paired=[];origins=[]
    for fold in folds(data.meta):
        resource_guard(a.device);name=fold['name'];out=a.output/name;out.mkdir();index,query=fold['refit'],fold['outer']
        for relative,digest in baseline_contract['files'].items():
            if Path(relative).parent.name==name:shutil.copyfile(a.baseline/relative,out/Path(relative).name)
        def save(method,p,q,support=None):
            np.savez(out/(method+'.npz'),ids=query,probabilities=p,q_raw=q,q_projected=np.maximum(0,np.sort(q,axis=2)),support=np.zeros(len(query),int) if support is None else support,truth_D=data.d[query],truth_Q=data.y[query],truth_Q_upper=data.upper[query])
        if a.mode=='flat':
            descriptor=full_descriptor(data);mean,std=normalize(descriptor,index);iz=l2((descriptor[index]-mean)/std);qz=l2((descriptor[query]-mean)/std);np.savez(a.output/(name+'-Flat-transform.npz'),mean=mean,std=std,fit_ids=index);support_method='flat-knn'
        else:
            _,receipt=neural_fit(data,kind,fold['subfit'],fold['early_stop'],out/(kind+'-es.pt'),device=a.device);fits+=1
            state,_=neural_fit(data,kind,index,None,out/(kind+'-refit.pt'),epochs=receipt['selected_epochs'],device=a.device);fits+=1
            z,p,q=neural_predict(data,state,np.r_[index,query],a.device);iz,qz=z[:len(index)],z[len(index):];save(kind+'-direct',p[len(index):],q[len(index):]);np.savez(a.output/(name+'-'+kind+'-representations.npz'),ids=np.r_[index,query],z=z)
            support_method='CNN' # common conservative raw support isolates window readout, not eligibility
        p,q,support,nr=empirical(data,index,query,iz,qz,fold['fit_cutoff'],support_method=support_method);save(kind+'-knn',p,q,support)
        neighbors.extend(dict(fold=name,method=kind+'-knn',**r) for r in nr)
        comparator='numeric-knn' if a.mode=='flat' else 'CNN-direct'
        candidate=kind+'-knn' if a.mode=='flat' else kind+'-direct'
        ref=dict(np.load(out/(comparator+'.npz')));new=dict(np.load(out/(candidate+'.npz')))
        paired.append(losses(new['probabilities'],new['q_projected'],data.d[query],data.y[query])-losses(ref['probabilities'],ref['q_projected'],data.d[query],data.y[query]));origins.extend(data.meta['origin'][query])
        ledger.extend(dict(fold=name,method=f.stem,rows=len(query)) for f in out.glob('*.npz'));write_json(a.output/'progress.json',dict(mode=a.mode,completed_fold=name,market_joint_fits=fits,partial_quality_read=False))
    if fits not in (0,6):raise ValueError('UNEXPECTED_FIT_COUNT')
    pd.DataFrame(neighbors).to_parquet(a.output/'neighbors.parquet',index=False)
    compatibility=dict(baseline_contract_sha256=sha(a.baseline/'evaluation-contract.json'),baseline_source_hashes=baseline_contract['source_hashes'],baseline_protocol_sha256=baseline_contract['protocol_sha256'],mode=a.mode,original_targets_and_full_history=True,market_joint_fits=fits,CHECK_opened=False)
    write_json(a.output/'development-complete.json',dict(status='DEVELOPMENT_FITS_COMPLETE_METRICS_PENDING',ledger=ledger,source_hashes=source_hashes(),compatibility=compatibility,wall_seconds=time.monotonic()-start,resource=resource_guard(a.device)))
    write_evaluation_contract(a.output,a.prepared,a.protocol,sorted({r['method'] for r in ledger}),compatibility)
    result=evaluate(argparse.Namespace(input=a.output,prepared=a.prepared,protocol=a.protocol,output=a.output/'evaluation'));delta=np.concatenate(paired)
    direct_comparison={task:paired_ci(delta[:,j],np.asarray(origins)) for j,task in enumerate(('D','Q-long','Q-short'))}
    write_json(a.output/'form-result.json',dict(status='FORM_COMPLETE',mode=a.mode,gate=result['status'],paired_comparator=comparator,paired=direct_comparison,market_joint_fits=fits,wall_seconds=time.monotonic()-start,CHECK_opened=False));print(json.dumps(dict(mode=a.mode,status='COMPLETE',fits=fits,wall_seconds=time.monotonic()-start)),flush=True)
if __name__=='__main__':main()
