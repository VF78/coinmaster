"""Zero-fit decomposition: same CPU embeddings, legacy vs corrected support."""
from pathlib import Path
import json,time
from unittest.mock import patch
import numpy as np,pandas as pd
from coinmaster.research import btc_pattern_train as tr
from coinmaster.research.btc_pattern_data import folds
from coinmaster.research.btc_pattern_evaluate import losses,paired_ci
from coinmaster.research.forecast_independent_data import write_json,sha

def main():
    import torch
    torch.set_num_threads(4);torch.set_num_interop_threads(1);start=time.monotonic();tr.DEADLINE=start+180
    root=Path('runtime/var/research-jobs/btc-pattern-pilot-m2-20261021');corrected=root/'form00-corrected';out=root/'form00-precision-diagnostic';out.mkdir(exist_ok=False);data=tr.Data(root/'prepared');oldneighbors=pd.read_parquet(root/'development/neighbors.parquet');newneighbors=pd.read_parquet(corrected/'neighbors.parquet');all_delta={};byfold=[];records=[]
    for fold in folds(data.meta):
        name=fold['name'];index,query=fold['refit'],fold['outer'];cache=corrected/(name+'-TCN-representations.npz')
        with np.load(cache) as z:
            assert np.array_equal(z['ids'],np.r_[index,query]);iz,qz=z['z'][:len(index)],z['z'][len(index):]
        with patch.object(tr,'method_input_start',lambda meta,method:meta['input_start']):
            p,q,support,nr=tr.empirical(data,index,query,iz,qz,fold['fit_cutoff'],support_method='TCN')
        np.savez(out/(name+'-CPU-legacy-support.npz'),ids=query,probabilities=p,q_raw=q,support=support)
        old=dict(np.load(root/'development'/name/'TCN-knn.npz'));new=dict(np.load(corrected/name/'TCN-knn.npz'));oldL=losses(old['probabilities'],old['q_projected'],data.d[query],data.y[query]);cpuL=losses(p,np.maximum(0,np.sort(q,axis=2)),data.d[query],data.y[query]);newL=losses(new['probabilities'],new['q_projected'],data.d[query],data.y[query])
        original=oldneighbors[(oldneighbors.fold==name)&(oldneighbors.method=='TCN-knn')].groupby('query').neighbor.apply(set).to_dict();cpu={}
        for r in nr:cpu.setdefault(r['query'],set()).add(r['neighbor']);records.append(dict(fold=name,**r))
        changed_sets=sum(cpu.get(int(i),set())!=original.get(int(i),set()) for i in query)
        byfold.append(dict(fold=name,queries=len(query),CPU_legacy_vs_archived_changed_neighbor_sets=changed_sets,CPU_legacy_vs_archived_Q_changed_exact=int((abs(q-old['q_raw']).max((1,2))>1e-12).sum()),CPU_legacy_vs_archived_Q_changed_gt_1e_6=int((abs(q-old['q_raw']).max((1,2))>1e-6).sum()),corrected_vs_CPU_legacy_Q_changed=int((abs(new['q_raw']-q).max((1,2))>1e-12).sum())))
        for tag,delta in [('device_reconstruction',cpuL-oldL),('support_only_same_CPU_embeddings',newL-cpuL),('total_vs_archived',newL-oldL)]:
            all_delta.setdefault(tag,[]).append((delta,data.meta['origin'][query]))
    pd.DataFrame(records).to_parquet(out/'CPU-legacy-neighbors.parquet',index=False)
    comparisons={tag:{task:paired_ci(np.concatenate([x[0][:,j] for x in vals]),np.concatenate([x[1] for x in vals])) for j,task in enumerate(('D','Q-long','Q-short'))} for tag,vals in all_delta.items()}
    result=dict(status='ZERO_FIT_PRECISION_DECOMPOSITION_COMPLETE',source_sha256=sha(__file__),wall_seconds=time.monotonic()-start,byfold=byfold,comparisons=comparisons,corrected_support_violations=int((newneighbors.neighbor_label_end>newneighbors.query_input_start).sum()),encoder_fits=0,new_inference=0,CHECK_opened=False)
    write_json(out/'result.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
