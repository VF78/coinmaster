"""FORM00: corrected method support, immutable saved weights; zero model fits."""
import argparse,json,os,time,shutil
from pathlib import Path
import numpy as np
from .btc_pattern_data import folds,method_input_start
from .btc_pattern_train import Data,normalize,l2,empirical,neural_predict
from .btc_pattern_evaluate import evaluate,write_evaluation_contract
from .forecast_independent_data import sha,write_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--prepared',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    import torch,pandas as pd
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    if os.environ.get('PYTORCH_MPS_HIGH_WATERMARK_RATIO')=='0':raise ValueError('WATERMARK_DISABLED')
    start=time.monotonic();a.output.mkdir(parents=True,exist_ok=False)
    prepared_manifest=json.loads((a.prepared/'manifest.json').read_text())
    for name in ('metadata.npy','features.npy','context.npy','raw.npy','labels.npz'):
        if sha(a.prepared/name)!=prepared_manifest['artifacts'][name]['sha256']:raise ValueError('PREPARED_ARTIFACT_HASH_MISMATCH: '+name)
    data=Data(a.prepared);ledger=[];changes=[];records=[];weights={}
    baseline_complete=sha(a.baseline/'development-complete.json');manifest=sha(a.prepared/'manifest.json')
    from . import btc_pattern_train as training
    training.DEADLINE=time.monotonic()+180
    for fold in folds(data.meta):
        index,query=fold['refit'],fold['outer'];out=a.output/fold['name'];out.mkdir()
        for source in sorted((a.baseline/fold['name']).glob('*.npz')):
            if source.stem not in ('TCN-knn','numeric-knn'):shutil.copyfile(source,out/source.name)
        dm,ds=normalize(data.descriptor,index);iz=l2((data.descriptor[index]-dm)/ds);qz=l2((data.descriptor[query]-dm)/ds)
        for method in ('numeric-knn','TCN-knn'):
            if method=='TCN-knn':
                checkpoint=a.baseline/fold['name']/'TCN-refit.pt';weights[str(checkpoint)]=sha(checkpoint);state=torch.load(checkpoint,map_location='cpu',weights_only=False)
                if not np.array_equal(state['fit_ids'],index):raise ValueError('REFIT_IDS_CHANGED')
                ids=np.r_[index,query];z,_,_=neural_predict(data,state,ids,'cpu');np.savez(out/'TCN-representation-cache.npz.tmp',ids=ids,z=z)
                # cache lives outside the forecast-glob schema
                (out/'TCN-representation-cache.npz.tmp.npz').rename(a.output/(fold['name']+'-TCN-representations.npz'))
                iz,qz=z[:len(index)],z[len(index):]
            pp,qq,ss,nr=empirical(data,index,query,iz,qz,fold['fit_cutoff'],support_method='TCN' if method=='TCN-knn' else 'numeric-knn')
            old=dict(np.load(a.baseline/fold['name']/(method+'.npz')));np.savez(out/(method+'.npz'),**dict(old,probabilities=pp,q_raw=qq,q_projected=np.maximum(0,np.sort(qq,axis=2)),support=ss))
            changes.append(dict(fold=fold['name'],method=method,rows=len(query),changed_probability_rows=int((abs(pp-old['probabilities']).max(1)>1e-12).sum()),changed_Q_rows=int((abs(qq-old['q_raw']).max((1,2))>1e-12).sum())))
            for r in nr:
                if r['neighbor_label_end']>r['query_input_start']:raise ValueError('SUPPORT_VIOLATION')
                records.append(dict(fold=fold['name'],method=method,**r))
        for file in out.glob('*.npz'):ledger.append(dict(fold=fold['name'],method=file.stem,rows=len(query)))
    pd.DataFrame(records).to_parquet(a.output/'neighbors.parquet',index=False)
    compatibility=dict(reason='FORM00 only TCN/numeric retrieval support corrected; all other forecast bytes copied',prepared_manifest_sha256=manifest,baseline_completion_sha256=baseline_complete,baseline_protocol_sha256=sha(a.protocol),baseline_checkpoints=weights,unchanged_methods=['prior','CatBoost','TCN-direct','CNN-direct','CNN-knn','Kronos-direct','Kronos-knn','random-context'],engineered_offset_hours=80,random_support='legacy raw256h conservative retained',fits=0)
    write_json(a.output/'compatibility.json',compatibility);write_json(a.output/'development-complete.json',dict(status='FORM00_ZERO_FIT_COMPLETE',ledger=ledger,compatibility_sha256=sha(a.output/'compatibility.json'),wall_seconds=time.monotonic()-start))
    write_evaluation_contract(a.output,a.prepared,a.protocol,sorted({r['method'] for r in ledger}),compatibility)
    result=evaluate(argparse.Namespace(input=a.output,prepared=a.prepared,protocol=a.protocol,output=a.output/'evaluation'))
    write_json(a.output/'form00-result.json',dict(status='FORM00_COMPLETE',gate=result['status'],changes=changes,wall_seconds=time.monotonic()-start,encoder_fits=0,CHECK_opened=False))
    print(json.dumps(dict(status='FORM00_COMPLETE',wall_seconds=time.monotonic()-start,gate=result['status'])),flush=True)
if __name__=='__main__':main()
