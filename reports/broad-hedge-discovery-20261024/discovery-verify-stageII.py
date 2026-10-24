"""Connected StageII verification plus combined Holm and independent bootstrap replay."""
from pathlib import Path
import importlib.util,csv,json,hashlib,math
import numpy as np
O=Path(__file__).resolve().parent
read=lambda p:list(csv.DictReader(Path(p).open()))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
combined=read(O/'discovery-combined-configurations.csv');assert len(combined)==36
tests=[(i,l,float(s[l+'_p'])) for i,s in enumerate(combined) for l in ['capital','protection']]+[(None,None,1.)]*56;assert len(tests)==128
last=0
for rank,j in enumerate(sorted(range(128),key=lambda j:tests[j][2])):
 i,l,p=tests[j];last=max(last,min(1,(128-rank)*p))
 if i is not None:assert abs(float(combined[i][l+'_Holm128'])-last)<1e-14
rows=read(O/'discovery-stageII-episodes.csv');stats=read(O/'discovery-stageII-statistics.csv');configs=read(O/'discovery-stageII-configurations.csv');rng=np.random.default_rng(20261024);cells=0;contrasts=0
calendars={'year1':[f'2024-{m:02}' for m in range(9,13)]+[f'2025-{m:02}' for m in range(1,9)],'year2':[f'2025-{m:02}' for m in range(9,13)]+[f'2026-{m:02}' for m in range(1,9)],'early':[f'2024-{m:02}' for m in range(9,13)]+['2025-01']}
def statistics(a):
 n=len(a);k=math.ceil(n/5);tails=np.sort(a[:,2:5],axis=0)[-k:].mean(0)
 return np.array([a[:,0].mean(),a[:,1].mean(),tails[0]-tails[1],tails[2]-tails[1]])
for conf in configs:
 if conf['statistics']!='BOOTSTRAP_APPROXIMATE_STATIONARY_MONTHS':continue
 zz=[r for r in rows if r['rule']==conf['rule'] and r['horizon_h']==conf['horizon_h']]
 for slip in ['0','2']:
  for boundary in ['BEFORE_ALL','AFTER_ALL']:
   for cohort,months in calendars.items():
    z=[r for r in zz if r['slip_bp']==slip and r['funding_boundary']==boundary and (r['early']=='True' if cohort=='early' else r['year']==cohort)];arr=np.array([[float(r[k]) for k in ['net_H_bp','paired_net_bp','loss_N_bp','loss_H_bp','loss_T_bp']] for r in z]);blocks=[np.array([i for i,r in enumerate(z) if r['entry_month']==m],int) for m in months];obs=statistics(arr);samples=[];attempts=0
    while len(samples)<8192 and attempts<65536:
     draw=rng.integers(0,len(months),size=len(months));idx=np.concatenate([blocks[i] for i in draw]);attempts+=1
     if len(idx):samples.append(statistics(arr[idx]))
    assert len(samples)==8192;a=np.array(samples);p=(1+np.sum(a-obs>=obs,axis=0))/8193;ci=np.quantile(a,[.025,.975],axis=0)
    for j,key in enumerate(['mean_H','mean_H_minus_T','CVaR_N_minus_H','CVaR_T_minus_H']):
     rec=[r for r in stats if r['rule']==conf['rule'] and r['horizon_h']==conf['horizon_h'] and r['slip_bp']==slip and r['funding_boundary']==boundary and r['cohort']==cohort and r['contrast']==key];assert len(rec)==1;rec=rec[0]
     assert abs(float(rec['p'])-p[j])<1e-14 and abs(float(rec['CI_low'])-ci[0,j])<1e-10 and abs(float(rec['CI_high'])-ci[1,j])<1e-10 and int(rec['draw_attempts'])==attempts;contrasts+=1
    cells+=1
spec=importlib.util.spec_from_file_location('independent_prefix_verifier',O/'discovery-verify-outcomes.py');lib=importlib.util.module_from_spec(spec);spec.loader.exec_module(lib);lib.verify('stageII')
p=O/'discovery-stageII-verification.json';result=json.loads(p.read_text());result['combined_Holm128_recomputed']=True;result['independent_bootstrap_cells']=cells;result['independent_bootstrap_contrasts']=contrasts;result['bootstrap_verification']='Independent replay of all StageII B8192 monthly block samples, means, within-resample CVaR, centered one-sided p and percentile CIs PASS';result['wrapper_sha256']=sha(Path(__file__));p.write_text(json.dumps(result,indent=2)+'\n');ledger=json.loads((O/'phase-ledger.json').read_text());ledger['stage_II']['verification_result_sha256']=sha(p);(O/'phase-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');print(json.dumps({'combined_Holm128':True,'bootstrap_cells':cells,'bootstrap_contrasts':contrasts,'status':'FULL_CONNECTED_STAGEII_PASS'},indent=2))
