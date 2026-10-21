"""TRAIN-only portability admission of frozen transferred models; never refits."""
from pathlib import Path
import argparse,hashlib,json,os,resource,time
p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);a=p.parse_args();job=a.job.resolve();os.nice(10);resource.setrlimit(resource.RLIMIT_CPU,(300,300));started=time.process_time()
import numpy as np
from coinmaster.research.forecast_independent_data import Dataset
from coinmaster.research.forecast_independent_run import _load_model,_predict,average
from coinmaster.research.forecast_independent_models import Budget
ds=Dataset(job/'prepared-v1',job/'reports/forecast-independent-20261021/protocol.json');shared=time.process_time()-started;records=[]
for family in ['control','stumpy','minirocket']:
 begin=time.process_time();base=job/'frozen-models'/family;seal=json.loads((base/'seal.json').read_text())
 with np.load(base/'calibration-predictions.npz') as z:ids=z['ids'][:16].copy();reference=(z['q'][:16].copy(),z['logits'][:16].copy())
 predictions=[]
 for item in seal['models']:
  model=_load_model(ds,base/item['path'],job/'portability-cache'/family);predictions.append(_predict(model,ids,Budget(5)))
 q,logits=average(predictions);comparisons={name:{'max_abs_error':float(np.max(abs(actual-target))),'allclose':bool(np.allclose(actual,target,rtol=1e-5,atol=3e-6))} for name,actual,target in [('q',q,reference[0]),('logits',logits,reference[1])]}
 records.append({'family':family,'rows':ids.tolist(),'comparisons':comparisons,'cpu_seconds':time.process_time()-begin+(shared if family=='control' else 0),'seal_sha256':hashlib.sha256((base/'seal.json').read_bytes()).hexdigest()})
 del model,predictions
out={'status':'PASS' if all(v['allclose'] for r in records for v in r['comparisons'].values()) else 'PORTABILITY_DIFFERENCE_REPORT_BEFORE_CHECK','TRAIN_only':True,'CHECK_opened':False,'refit_or_recalibration':False,'rtol':1e-5,'atol':3e-6,'records':records,'native_maxrss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
(job/'transferred-model-readback.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out),flush=True)
