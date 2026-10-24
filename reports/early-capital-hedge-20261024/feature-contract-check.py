"""Causal saved-feature/market availability only. Never reads outcomes."""
from pathlib import Path
import csv,json,hashlib,collections,math,bisect
import numpy as np
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent
OLD=ROOT/'reports/market-redesign-20261024'; BARS=ROOT/'reports/b-50-90-next-20261023/owner-closed-bars.csv'
DATA=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/inputs/data/normalized')
FEAT=OLD/'native-analysis-sol-R3-features.csv';H=3600000000000;M=60000000000
features=list(csv.DictReader(FEAT.open()));bars=list(csv.DictReader(BARS.open())); paths=[FEAT,BARS,Path(__file__),ROOT/'reports/b-50-90-next-20261023/owner-precheck.py',OLD/'native-analysis-sol-R3-calculate.py']
cl={s:{int(x['close_ns']):float(x['close']) for x in bars if x['symbol']==s and int(x['step_ns'])==H} for s in ['BTCUSDT','SOLUSDT']}
assert all(r['available_ns']==r['close_ns'] for r in bars)
ts=sorted(cl['BTCUSDT']);assert ts==sorted(cl['SOLUSDT']) and len(ts)==17520 and all(b-a==H for a,b in zip(ts,ts[1:]));bi={t:i for i,t in enumerate(ts)}
b=np.array([cl['BTCUSDT'][t] for t in ts]);s=np.array([cl['SOLUSDT'][t] for t in ts]);rb=np.r_[np.nan,b[1:]/b[:-1]-1];rs=np.r_[np.nan,s[1:]/s[:-1]-1];lb=np.r_[np.nan,np.diff(np.log(b))];ls=np.r_[np.nan,np.diff(np.log(s))]
rows=[];counts=collections.Counter()
for f in features:
 t=int(f['decision_ns']);i=bi[t];side=int(f['side']); assert i>=721
 x=rb[i-720:i];y=rs[i-720:i];beta=float(np.cov(x,y,ddof=1)[0,1]/np.var(x,ddof=1));assert math.isclose(beta,float(f['lag720_betaSOLgivenBTC']),rel_tol=1e-12)
 xl=lb[i-720:i];yl=ls[i-720:i];bl=float(np.cov(xl,yl,ddof=1)[0,1]/np.var(xl,ddof=1))
 br=b[i]/b[i-24]-1;sr=s[i]/s[i-24]-1;lrB=math.log(b[i]/b[i-24]);lrS=math.log(s[i]/s[i-24]);res=sr-beta*br;lres=lrS-bl*lrB
 r={k:f[k] for k in ['decision_ns','decision_utc','cycle','period','side','observed_BTCqty','NB_USDT','BTCclose','SOLclose','lag720_last_return_end_ns','lag720_cov','lag720_rho','lag720_sigmaBTC','lag720_sigmaSOL','lag720_betaSOLgivenBTC','closed_H4_return','side_closed_H4_return']}
 r.update(feature_available_ns=t,earliest_conservative_execution_close_ns=t+M,return24_start_ns=ts[i-24],return24_end_ns=t,lag720_first_return_end_ns=ts[i-720],BTC_simple24=br,SOL_simple24=sr,residual_simple24=res,side_residual_simple24=side*res,lag720_logbetaSOLgivenBTC=bl,BTC_log24=lrB,SOL_log24=lrS,residual_log24=lres,side_residual_log24=side*lres)
 rows.append(r);counts[(f['period'],'simple_positive' if side*res>0 else 'simple_nonpositive','H4_adverse' if float(f['side_closed_H4_return'])<0 else 'H4_nonadverse')]+=1
assert len(rows)==1529 and len({r['cycle'] for r in rows})==77
with (OUT/'feature-contract-features.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
coverage={}
for sym in ['BTC','SOL']:
 for kind in ['execution-1m','mark-1m','funding']:
  p=DATA/f'bybit-{sym}USDT-{kind}.parquet';paths.append(p);pf=pq.ParquetFile(p);col='funding_time_ms' if kind=='funding' else 'open_time_ms';z=pq.read_table(p,columns=[col]).column(col).to_numpy(); delta=np.diff(z)
  rec=dict(path=str(p),resolved_path=str(p.resolve()),schema=str(pf.schema_arrow),rows=len(z),first_ms=int(z[0]),last_ms=int(z[-1]),max_gap_ms=int(delta.max()),gap_counts={str(k):int(v) for k,v in zip(*np.unique(delta,return_counts=True))})
  if kind!='funding':
   assert np.all(delta==60000);want=np.array([int(r['decision_ns'])//1000000 for r in rows]);idx=np.searchsorted(z,want);assert np.all(z[idx]==want)
   # Row open=t supplies close at t+60s. Prior mark row open=t-60s supplies mark close at t.
   prior=np.searchsorted(z,want-60000);assert np.all(z[prior]==want-60000);rec['all_1529_next_minute_and_prior_mark_rows_available']=True
  else:
   want=np.array([int(r['decision_ns'])//1000000 for r in rows]);ix=np.searchsorted(z,want,side='left')-1;assert np.all(ix>=0) and np.all(z[ix]<want);rec['all_1529_strictly_lagged_funding_available']=True;rec['decision_funding_boundary_ties']=int(np.isin(want,z).sum())
  coverage[f'{sym}_{kind}']=rec
result={'scope':'FEATURE_AVAILABILITY_ONLY_NO_OUTCOMES_READ','states':len(rows),'cycles':77,'sign_counts':[{'period':k[0],'residual_sign':k[1],'H4_sign':k[2],'n':v} for k,v in sorted(counts.items())],'simple_log_sign_disagreements':int(sum((r['side_residual_simple24']>0)!=(r['side_residual_log24']>0) for r in rows)),'coverage':coverage,'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'output_sha256':hashlib.sha256((OUT/'feature-contract-features.csv').read_bytes()).hexdigest(),'engine_runs':0,'outcome_files_read':0}
(OUT/'feature-contract-availability.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['states','cycles','sign_counts','simple_log_sign_disagreements','engine_runs','outcome_files_read']},indent=2))
