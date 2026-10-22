"""Post-completion only: immutable forecast pairing, no model inference/fit."""
from pathlib import Path
import csv,json,time
import numpy as np
from coinmaster.research.btc_pattern_evaluate import losses,paired_ci,validate_artifacts
from coinmaster.research.forecast_independent_data import sha,write_json

def main():
    start=time.monotonic();r=Path('reports/btc-pattern-pilot-m2-20261021/form-signal-20261022');root=Path('runtime/var/research-jobs/btc-pattern-pilot-m2-20261021');job=root/'form03-spatial';freeze=json.loads((r/'form03-source-freeze.json').read_text());result=json.loads((job/'form-result.json').read_text());assert result['market_joint_fits']==6
    validate_artifacts(job,root/'prepared',r/'experiment-protocol-draft.json');meta=np.load(root/'prepared/metadata.npy',mmap_mode='r');rows=[];fits=[];contextpins=freeze['mandatory_postrun_context_comparison']['forecasts']
    for comparator in ('CNN-direct','Context-direct'):
        delta=[];origins=[];fd={}
        for fold in ('F1','F2','F3'):
            a=dict(np.load(job/fold/'CNNSpatial-direct.npz'));p=job/fold/(comparator+'.npz') if comparator=='CNN-direct' else root/'form01-context'/fold/(comparator+'.npz')
            if comparator=='Context-direct':assert sha(p)==contextpins[str(p)]
            b=dict(np.load(p))
            for key in ('ids','truth_D','truth_Q','truth_Q_upper'):assert np.array_equal(a[key],b[key])
            difference=losses(a['probabilities'],a['q_projected'],a['truth_D'],a['truth_Q'])-losses(b['probabilities'],b['q_projected'],b['truth_D'],b['truth_Q']);delta.append(difference);origins.extend(meta['origin'][a['ids']]);fd[fold]=np.nanmean(difference,axis=0)
        dd=np.concatenate(delta)
        for j,task in enumerate(('D','Q-long','Q-short')):
            ci=paired_ci(dd[:,j],np.asarray(origins));rows.append(dict(candidate='CNNSpatial-direct',comparator=comparator,task=task,orientation='candidate_minus_comparator_negative_better',**{f+'_delta':float(fd[f][j]) for f in fd},fold_wins=int(sum(fd[f][j]<0 for f in fd)),**ci))
    for fold in ('F1','F2','F3'):
        es=json.loads((job/fold/'CNNSpatial-es.receipt.json').read_text());refit=json.loads((job/fold/'CNNSpatial-refit.receipt.json').read_text());fits.append(dict(fold=fold,selected_epochs=es['selected_epochs'],ES_epochs_executed=es['epochs_executed'],ES_optimizer_steps=es['optimizer_steps'],refit_optimizer_steps=refit['optimizer_steps'],refit_rows=refit['fit_rows']))
    with (r/'form03-paired-comparison.csv').open('w') as out:
        w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    complete=json.loads((job/'development-complete.json').read_text());manifest={str(p):sha(p) for p in sorted(job.rglob('*')) if p.is_file()};write_json(r/'form03-local-artifact-manifest.json',manifest)
    qa=dict(status='PASS',helper_source_sha256=sha(__file__),all_forecast_groups_validated=36,outer_ids_each_method=8496,Context_comparator_hashes_verified=True,comparison_orientation='CNNSpatial minus comparator; negativebetter',market_joint_fits=6,total_optimizer_steps=sum(f['ES_optimizer_steps']+f['refit_optimizer_steps'] for f in fits),folds=fits,gate=result['gate'],runtime_seconds=result['wall_seconds'],resource=complete['resource'],CHECK_opened=False,analysis_fits=0,analysis_model_inference=0,analysis_wall_seconds=time.monotonic()-start)
    write_json(r/'form03-QA.json',qa);print(json.dumps(dict(paired=rows,QA=qa)),flush=True)
if __name__=='__main__':main()
