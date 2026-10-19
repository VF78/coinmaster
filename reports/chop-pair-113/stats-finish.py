import json,csv,math,hashlib
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
out=Path('reports/chop-pair-113')
x=json.load(open(out/'stats-summary.json')); prior=x['selected_detector_calibration_only']
s=(out/'stats-analysis.py').read_text().split('# One sequential read per symbol')[0]
s=s.replace('evalm=(ts>=lo)&(ts<hi)&valid','evalm=(ts>=lo)&(ts+7*D<hi)&valid')
exec(compile(s,'daily_only_embargo','exec'))
assert selected==prior
x['detectors']=rows;x['diagnostic_calibration_embargo']='Diagnostic forward7 label must end strictly before split; same end7D exclusion on holdout. Daily-only correction; selected unchanged.'
rows_tp=list(csv.DictReader(open(out/'stats-TP.csv')))
for r in rows_tp:
 n=int(r['n']);k=int(r['hits']);ph=k/n;den=1+3.8416/n;center=(ph+1.9208/n)/den;rad=1.96*math.sqrt(ph*(1-ph)/n+3.8416/(4*n*n))/den;r['Wilson95_low']=center-rad;r['Wilson95_high']=center+rad
with open(out/'stats-TP.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows_tp[0]));w.writeheader();w.writerows(rows_tp)
# Same representative raw synchronized price endpoints, only coefficient method changes.
rho={};coef=[];d1=daily['BTCUSDT'];d2=daily['SOLUSDT']
for di in range(91,len(d1)):
 if not START<=ts[di]<END:continue
 rb=np.diff(np.log(d1[di-90:di+1,3]));idx=np.searchsorted(d2[:,0],d1[di-90:di+1,0]);rs=np.diff(np.log(d2[idx,3]));cv=np.cov(rb,rs,ddof=1);rho2=float(cv[0,1]**2/(cv[0,0]*cv[1,1]));beta=float(cv[0,1]/cv[0,0]);rho[int(ts[di])]=rho2;coef.append({'ms':int(ts[di]),'period':'calibration' if ts[di]<SPLIT else 'holdout','beta':beta,'rho_squared':rho2,'SOLnotional_factorneutral_perNB':1/beta,'SOLnotional_minvar_perNB':rho2/beta})
with open(out/'stats-coefficients.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=list(coef[0]));w.writeheader();w.writerows(coef)
ex=list(csv.DictReader(open(out/'stats-pair-examples.csv')))
for r in ex:
 import calendar,time
 ms=calendar.timegm(time.strptime(r['event_utc'],'%Y-%m-%dT%H:%M:%SZ'))*1000;di=np.searchsorted(ts,ms,side='right')-1;rr=rho[int(ts[di])];sd=1 if r['BTC_side']=='LONG' else -1;br=sd*(float(r['BTC_exit'])/float(r['BTC_entry'])-1);sr=-sd*(float(r['SOL_exit'])/float(r['SOL_entry'])-1);a=rr/float(r['beta']);r['rho_squared']=rr;r['minvar_SOLnotional_perNB']=a;r['minvar_pair_after_fee_before_unknown_friction']=br+a*sr-.0011*(1+a)
with open(out/'stats-pair-examples.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=list(ex[0]));w.writeheader();w.writerows(ex)
x['tp']=rows_tp;x['coefficient_summary']={p:{k:{'min':float(min(r[k] for r in coef if r['period']==p)),'median':float(np.median([r[k] for r in coef if r['period']==p])),'max':float(max(r[k] for r in coef if r['period']==p))} for k in ['beta','rho_squared','SOLnotional_factorneutral_perNB','SOLnotional_minvar_perNB']} for p in ['calibration','holdout']};x['minvar_comparison_scope']='Only stored30 representative15m native-entry BTC-trigger endpoints; not TP-family distribution or standalone edge. All paired distributions in TP.csv remain factor-neutral.'
(out/'stats-summary.json').write_text(json.dumps(x,indent=2));print(json.dumps({'detectors':rows,'coefficient_summary':x['coefficient_summary']},indent=2))
