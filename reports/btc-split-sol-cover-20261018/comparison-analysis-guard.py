"""Train-only common close-quote model. No backtest or future permission injection."""
import csv,json,hashlib,resource
from collections import defaultdict
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
OUT=Path('reports/btc-split-sol-cover-20261018');INPUT=Path('/var/lib/coinmaster-native-gui/data/normalized/bybit-BTCUSDT-execution-1m.parquet')
parents=[p for p in csv.DictReader(open(OUT/'screening-parents.csv')) if int(p['t'])<1756684800000];assert len(parents)==57
wanted={int(p['day']) for p in parents};chunks={d:[] for d in wanted}
for batch in pq.ParquetFile(INPUT).iter_batches(batch_size=10080,columns=['open_time_ms','high','low','close']):
 ar=np.column_stack([np.array(batch.column(i).to_pylist(),float) for i in range(4)]);ar[:,0]+=60000;days=(ar[:,0]-1)//86400000
 for d in set(days.astype(int))&wanted:chunks[d].append(ar[days==d].copy())
days={d:np.concatenate(v) for d,v in chunks.items()}
def stats(v):
 a=np.array(v);return dict(n=len(a),mean=float(a.mean()),median=float(np.median(a)),min=float(a.min()),p05=float(np.quantile(a,.05)),p10=float(np.quantile(a,.1)),p95=float(np.quantile(a,.95)),max=float(a.max()))
def confs(ar,sign,t):
 b=[]
 for end in range(int(ar[0,0])//900000*900000+900000,int(ar[-1,0])+1,900000):
  z=ar[(ar[:,0]>end-900000)&(ar[:,0]<=end)]
  if len(z)==15 and z[0,0]-60000>=t:b.append((end,z[:,1].max(),z[:,2].min(),z[-1,3]))
 return {cur[0] for prev,cur in zip(b,b[1:]) if (cur[3]>prev[1] if sign==1 else cur[3]<prev[2])}
rows=[]
for p in parents:
 t=int(p['t']);sgn=1 if p['side']=='BUY' else -1;p0=float(p['p']);ar=days[int(p['day'])];confirm=confs(ar,sgn,t);deadline=t+4*3600000;limit=p0*(1-sgn*.0025);q=ar[(ar[:,0]>t)&(ar[:,0]<=deadline+60000)];first_exit=int(p['first_exit'])
 for mode,g in [('OFF',None),('ON',None),('GUARD005',.0005),('GUARD010',.001),('GUARD015',.0015)]:
  pending=None;pending_at=None;reason=None;chosen=None;px=None;ambiguous_ohlc=0
  for bar in q:
   tm=int(bar[0]);close=float(bar[3]);penetrate=sgn*(p0-close)/p0>=.0026
   # Resting limit could win a fill while cancel/ACK pending. No simultaneous live market child.
   if penetrate:chosen=tm;px=limit;reason='LIMIT_CLOSE_PROXY';break
   # OHLC would have crossed while close did not: diagnostic only, never filled.
   if (bar[2]<limit-p0*.0001 if sgn==1 else bar[1]>limit+p0*.0001):ambiguous_ohlc+=1
   if pending_at is not None and tm>pending_at:chosen=tm;px=close;reason=pending;break
   guard=(g is not None and sgn*(close/p0-1)>=g)
   confirmation=(mode=='ON' and tm in confirm and sgn*(p0-close)/p0>=-.001)
   if guard:pending='GUARD';pending_at=tm
   elif confirmation:pending='CONFIRM';pending_at=tm
   elif tm>=deadline:pending='DEADLINE';pending_at=tm
  assert chosen is not None
  benefit=.5*sgn*(p0-px)/p0*10000
  rows.append(dict(parent=p['parent'],side=p['side'],mode=mode,guard_pct=g*100 if g else None,entry_ms=t,first_fill=p0,limit=limit,trigger_ms=pending_at,completion_ms=chosen,actual_completion_px=px,reason=reason,whole_btc_price_bp=benefit,wait_hours=(chosen-t)/3600000,early_exit_conflict=first_exit<=chosen,ohlc_cross_without_close_before_completion=ambiguous_ohlc))
summ=[]
for mode in ('OFF','ON','GUARD005','GUARD010','GUARD015'):
 z=[r for r in rows if r['mode']==mode];f=[r for r in z if r['reason']=='DEADLINE'];summ.append(dict(mode=mode,whole_btc_price_bp=stats([r['whole_btc_price_bp'] for r in z]),wait_hours=stats([r['wait_hours'] for r in z]),limits=sum(r['reason']=='LIMIT_CLOSE_PROXY' for r in z),confirm=sum(r['reason']=='CONFIRM' for r in z),guards=sum(r['reason']=='GUARD' for r in z),fallback=len(f),fallback_price_bp=stats([r['whole_btc_price_bp'] for r in f]) if f else None,early_exit_conflicts=sum(r['early_exit_conflict'] for r in z),ohlc_ambiguous_parents=sum(r['ohlc_cross_without_close_before_completion']>0 for r in z)))
def writecsv(name,rows):
 with open(OUT/name,'w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
writecsv('comparison-analysis-guard-parents.csv',rows)
method=dict(selection='TRAIN57 [2024-09-01,2025-09-01), only constantguards .05/.10/.15%; no laterselection/no perdateexceptions',model='Allcandidates share actualfirstnativefillP0; .25%limit full4h; restinglimitfill only latercompleted1mclose penetratinglimit1bp; makerprice fixedlimit proxy. Markettrigger is observedquoteclose. OFFdeadline, ON15mconfirmation near.10%, runawayguards eachcancelthenonequoteACKdelay then completeatNEXTactual1mclose; limitfillduringcancelpending takespriority. Noidealguardprice. Deadline4h+1minutequote. NoOHLCtouchfills; fullclosed15mhigh/lowonlyforconfirmation. Noqueue/L2/spread certainty.',limits='EarlyhistoricalTP/exit conflicts diagnostic only, notsignals; nativewouldaccelerateTP/cancelmandatoryclose. Samepath grosspriceNOTnativeROI. No claimguardrestoresMarch16permission/trail. OriginalP0usesOHLC1bpproxy anddifferentdeadlinequote assumptions; directmetriccomparisononlythiscommonmodel.',parents=57,resource_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),canonical_parquet_sha256='9c48e97ce1544bb5b7169772eea2d06d8a0c3fefd2522e32ece452c2946c0f88',summaries=summ)
(OUT/'comparison-analysis-guard-summary.json').write_text(json.dumps(method,indent=2)+'\n');print(json.dumps(summ,indent=2))
