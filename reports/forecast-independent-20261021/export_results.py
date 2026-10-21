"""Report-only export of saved ONE-CHECK predictions; never loads models or infers."""
import argparse,csv,gzip,hashlib,io,json,re,shutil
from pathlib import Path
import numpy as np

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def probabilities(x):
 x=x-x.max(1,keepdims=True);x=np.exp(x);return x/x.sum(1,keepdims=True)
def export(job,out):
 out.mkdir(parents=True,exist_ok=False);prepared=job/'prepared-v1';meta=np.load(prepared/'metadata.npy',mmap_mode='r');truth=np.load(prepared/'labels-check.npz');summary={};artifacts=[]
 for family in ['control','stumpy','minirocket','rdst','cnn']:
  runs=[p for p in job.glob('run-check-'+family+'-*') if (p/'completion.json').exists() and json.loads((p/'completion.json').read_text())['status']=='PASS']
  if len(runs)!=1:raise ValueError(('REQUIRES_EXACTLY_ONE_COMPLETED_CHECK',family,len(runs)))
  run=runs[0];src=run/'result';result=json.loads((src/'result.json').read_text());assert result['status']=='ONE_FROZEN_CHECK_EVALUATION_COMPLETE'
  a=np.load(src/'predictions-all-origins.npz');ids=a['ids'];observed=a['observed'];assert len(ids)==9744 and observed.sum()==9696 and (~observed).sum()==48 and np.array_equal(ids,truth['ids']) and np.array_equal(observed,meta['observed'][ids])
  dest=out/family;dest.mkdir()
  for name in ['result.json','predictions.npz','predictions-all-origins.npz','actionable-forecasts.json','censored-forecasts.json']:
   shutil.copy2(src/name,dest/name)
  for pattern in ['example-*.json','example-*.png','TRAIN-example-*.png']:
   for p in src.glob(pattern):shutil.copy2(p,dest/p.name)
  for name in ['launch.json','completion.json','stderr-time.txt']:shutil.copy2(run/name,dest/name)
  actionable={int(v['row']):v for v in json.loads((src/'actionable-forecasts.json').read_text())}
  columns=['row','asset','origin_ms','entry_ms','expiry_ms','reference','entry','sigma24','fully_observed','censored','direction_truth']
  columns += ['truth_'+bound+'_'+side for bound in ['lower','upper'] for side in ['long','short']]
  for stage in ['raw','calibrated']:
   columns += [stage+'_'+bound+'_'+side+'_q'+q for bound in ['lower','upper'] for side in ['long','short'] for q in ['20','50','80']]
   columns += [stage+'_'+kind+'_'+d for kind in ['logit','probability'] for d in ['UP','DOWN','NEUTRAL']]
  columns += ['actionable','actionable_details_json']
  rawp=probabilities(a['logits']);calp=probabilities(a['calibrated_logits'])
  with (dest/'forecasts.csv.gz').open('wb') as f,gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as gz,io.TextIOWrapper(gz,encoding='utf-8',newline='') as text:
   w=csv.writer(text);w.writerow(columns)
   for i,r in enumerate(ids):
    m=meta[r];obs=bool(observed[i]);values=[int(r),('BTCUSDT','SOLUSDT')[int(m['asset'])],int(m['origin']),int(m['origin'])+60000,int(m['expiry']),float(m['reference']),float(m['entry']),float(m['sigma']),int(obs),int(not obs),('UP','DOWN','NEUTRAL')[int(truth['direction'][i])] if obs else 'UNKNOWN']
    values += truth['target'][i].reshape(-1).tolist() if obs else ['']*4
    for q,logits,probs in [(a['q'],a['logits'],rawp),(a['calibrated_q'],a['calibrated_logits'],calp)]:values += q[i].reshape(-1).tolist()+logits[i].tolist()+probs[i].tolist()
    values += [int(int(r) in actionable),json.dumps(actionable[int(r)],separators=(',',':')) if int(r) in actionable else ''];w.writerow(values)
  coverage={}
  for stage,key in [('raw','q'),('calibrated','calibrated_q')]:
   coverage[stage]={}
   for asset in ['ALL',0,1]:
    mask=observed.copy()
    if asset!='ALL':mask &= meta['asset'][ids]==asset
    y=truth['target'][mask,:,:,None];q=a[key][mask]
    coverage[stage][str(asset)]={'n':int(mask.sum()),'strict_exceedance_gt':(y>q).mean(0).tolist(),'nonstrict_exceedance_ge':(y>=q).mean(0).tolist(),'exact_tie_count':(y==q).sum(0).tolist(),'zero_truth_count':(y[...,0]==0).sum(0).tolist(),'zero_prediction_count':(q==0).sum(0).tolist()}
  write(dest/'quantile-tie-coverage.json',coverage)
  timing=(run/'stderr-time.txt').read_text();match=re.search(r'([0-9.]+) real\s+([0-9.]+) user\s+([0-9.]+) sys',timing);assert match
  wall,user,system=map(float,match.groups());prior=json.loads((run/'completion.json').read_text())['prior_cpu_seconds']
  summary[family]={'raw':result['raw']['all'],'calibrated':result['calibrated']['all'],'coverage':result['coverage'],'vs_prefix_prior':result['vs_prefix_prior'],'vs_calibrated_control':result.get('vs_raw_control'),'actual_output':str(src),'export_directory':str(dest),'CHECK_wall_seconds':wall,'CHECK_external_CPU_seconds':user+system,'cumulative_CPU_seconds':prior+user+system,'seal_sha256':result['seal_sha256'],'actionable_touch_summary':result['actionable_touch_summary']}
 write(out/'schema.json',{'rows_per_family':9744,'mature':9696,'censored':48,'columns':columns,'UTC_times':'epoch milliseconds; entry=origin+60000; expiry=entry+24h exclusive','targets':'MFE before SL, logdistance divided by sigma24; bounds lower/upper, sides long/short','quantiles':[.2,.5,.8],'censored_truth':'blank MFE and UNKNOWN direction, never zero; future labels unavailable','actionable_details':'saved evaluation JSON with E-anchored SL/TP and minute touch bounds; no new inference','tie_coverage':'strict/nonstrict empirical exceedance; nominal 80/50/20 requires continuous truth','models_loaded':False,'data_manifest_sha256':sha(prepared/'manifest.json'),'source_exporter_sha256':sha(__file__)})
 write(out/'summary.json',summary)
 for p in sorted(out.rglob('*')):
  if p.is_file():artifacts.append({'path':str(p.relative_to(out)),'bytes':p.stat().st_size,'sha256':sha(p)})
 write(out/'artifact-manifest.json',{'artifacts':artifacts,'total_bytes':sum(a['bytes'] for a in artifacts),'source_job':str(job),'models_or_raw_history_in_export':False})
 print(json.dumps({'status':'SAVED_PREDICTION_EXPORT_PASS','output':str(out),'families':list(summary),'files':len(artifacts),'artifact_bytes':sum(a['bytes'] for a in artifacts)}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();export(a.job,a.output)
