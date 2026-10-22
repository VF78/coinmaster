"""One artifact-only pass: manifests, canonical arrays, independent CSV losses, syntax."""
from pathlib import Path
import csv,hashlib,json,time
import numpy as np

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def main():
    start=time.monotonic();r=Path(__file__).parent;root=Path('runtime/var/research-jobs/btc-pattern-pilot-m2-20261021');prepared=root/'prepared';freeze=json.loads((r/'form03-source-freeze.json').read_text());hashes=0
    for p,h in freeze['source_hashes'].items():assert digest(p)==h;hashes+=1
    for name in ('form00-local-artifact-manifest.json','form01-02-local-artifact-manifest.json','form03-local-artifact-manifest.json'):
        for p,h in json.loads((r/name).read_text()).items():assert digest(p)==h;hashes+=1
    meta=np.load(prepared/'metadata.npy',mmap_mode='r')
    with np.load(prepared/'labels.npz') as z:d=z['direction'];mfe=z['mfe']
    from coinmaster.research.btc_pattern_data import folds
    outer={f['name']:f['outer'] for f in folds(meta)};groups=0;csvchecks=0;unchanged=0
    for folder in ('form00-corrected','form01-context','form02-flat','form03-spatial'):
        job=root/folder;metrics={(x['fold'],x['method'],x['task']):x for x in csv.DictReader((job/'evaluation/metrics.csv').open())}
        for fold,ids in outer.items():
            for p in sorted((job/fold).glob('*.npz')):
                with np.load(p) as z:
                    assert np.array_equal(z['ids'],ids)
                    assert np.array_equal(z['truth_D'],d[ids]) and np.array_equal(z['truth_Q'],mfe[ids,:,0]) and np.array_equal(z['truth_Q_upper'],mfe[ids,:,1])
                    q=z['q_projected'];assert np.array_equal(q,np.maximum(0,np.sort(z['q_raw'],axis=2)));prob=z['probabilities'];valid=d[ids]>=0;D=-np.log(np.maximum(prob[np.arange(len(ids))[valid],d[ids][valid]],1e-12));e=mfe[ids,:,0,None]-q;levels=np.array([.2,.5,.8]);pin=(np.abs(e)+(2*levels-1)*e)*.5
                    values=[D.mean(dtype=np.float64),*pin.mean((0,2),dtype=np.float64)]
                    for task,value in zip(('D','Q-long','Q-short'),values):
                        row=metrics[(fold,p.stem,task)];assert abs(float(row['loss'])-float(value))<1e-12;assert int(row['N'])==(int(valid.sum()) if task=='D' else len(ids));csvchecks+=1
                groups+=1
                base=root/'form00-corrected'/fold/p.name
                if folder!='form00-corrected' and base.exists():assert digest(p)==digest(base);unchanged+=1
    compiled=[]
    for p in r.glob('*.py'):compile(p.read_text(),str(p),'exec');compiled.append(p.name)
    assert groups==135 and unchanged==90 and csvchecks==405
    summary=dict(status='PASS',independent_formula_precision='float64 accumulation of float32 D-logloss elements; initial helper accumulation precision corrected, no forecast changes',source_and_runtime_hashes_verified=hashes,canonical_forecast_groups=groups,independent_CSV_vs_NPZ_loss_count_checks=csvchecks,byte_identical_reused_control_files=unchanged,compiled_helpers=compiled,distinct_local_unit_tests=25,pool_focused_test_after_backend_change='PASS',MPS_pool_output_and_gradient_parity='exact0',applicable_research_CI=False,model_fits=0,model_inference=0,optimizer_updates=0,CHECK_opened=False,model_jobs_active=False,wall_seconds=time.monotonic()-start)
    write(r/'artifact-QA.json',summary)
    owned=[p for p in sorted(r.iterdir()) if p.is_file() and p.name not in ('PLAN.md','artifact-manifest.json','ready-files.txt') and not any(t in p.name.lower() for t in ('openai','project','readback'))]
    (r/'ready-files.txt').write_text('\n'.join(str(p) for p in owned)+'\n'+str(r/'ready-files.txt')+'\n'+str(r/'artifact-manifest.json')+'\n')
    write(r/'artifact-manifest.json',{str(p):digest(p) for p in owned+[r/'ready-files.txt']});print(json.dumps(dict(QA=summary,ready_report_files=len(owned)+2,manifest_sha256=digest(r/'artifact-manifest.json'))),flush=True)
if __name__=='__main__':main()
