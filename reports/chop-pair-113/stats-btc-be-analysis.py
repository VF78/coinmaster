import os,csv,json,time,resource,hashlib
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
os.chdir('/root/.openclaw/workspace/coinmaster/coinmaster');out=Path('reports/chop-pair-113');D=86400000;SPLIT=1756684800000;END=1788220800000;L1=.005317;L2=.012082;L3=.021041;BE=.0011
src={}
def read(p,cols):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 src[p]=h.hexdigest();a=[]
 for b in pq.ParquetFile(p).iter_batches(batch_size=8192,columns=cols,use_threads=False):a.append(np.column_stack([np.asarray(b.column(i).to_pylist(),dtype='float64') for i in range(len(cols))]))
 return np.concatenate(a)
b=read('runtime/var/data/normalized/bybit-BTCUSDT-daily.parquet',['open_time_ms','close']);c=b[:,1];e=c.copy()
for i in range(1,len(c)):e[i]=2/35*c[i]+33/35*e[i-1]
side=np.where(c>=e,1,-1);flip=np.r_[0,np.diff(side)!=0];raw=np.array([sum(flip[max(0,i-6):i+1])>=2 for i in range(len(c))]);mask=np.zeros(len(c),bool);state=False
for i in range(1,len(c)):
 if raw[i]==raw[i-1]:state=bool(raw[i])
 mask[i]=state
ts=b[:,0].astype('int64')+D;bars=read('runtime/var/data/normalized/bybit-BTCUSDT-execution-1m.parquet',['open_time_ms','close']);mt=bars[:,0].astype('int64')+60000
ctx='reports/immediate-sol-insurance-113/postmortem-chop-entries.csv';src[ctx]=hashlib.sha256(Path(ctx).read_bytes()).hexdigest();rr=[]
for r in csv.DictReader(open(ctx)):
 ms=int(r['P0_known_ms']);exitms=int(r['last_exit_ms']);end=min(ms+D,exitms,END);ix=np.searchsorted(mt,ms);stop=np.searchsorted(mt,end,side='right');fi=np.arange(ix+1,stop);sd=1 if r['BTCside']=='LONG' else -1;ret=sd*(bars[fi,1]/bars[ix,1]-1);di=np.searchsorted(ts,ms,side='right')-1;N=len(ret)
 def first(level):
  hit=np.flatnonzero(ret>=level);return int(hit[0]) if len(hit) else N
 t1,t2,t3=first(L1),first(L2),first(L3);tbe=N
 if t1<N:
  hits=np.flatnonzero(ret[t1+1:]<=BE)
  if len(hits):tbe=t1+1+int(hits[0])
 before=tbe<t2 and tbe<N;later2=before and t2<N;later3=before and t3<N
 rr.append(dict(number=int(r['number']),period='calibration' if ms<SPLIT else 'holdout',entry_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(ms/1000)),side=r['BTCside'],CHOP_flips2_fixed=bool(mask[di]),observed_minutes=N,horizon_truncated=N<1440,end_reason='original_BTC_exit' if exitms<ms+D else '24h_horizon',TP1_hit=t1<N,TP2_hit=t2<N,TP3_hit=t3<N,TP1_minutes=t1+1 if t1<N else None,TP2_minutes=t2+1 if t2<N else None,TP3_minutes=t3+1 if t3<N else None,postTP1_BE_minutes=tbe+1 if tbe<N else None,BE_before_TP2=before,TP2_before_BE=t2<tbe and t2<N,TP2_already_by_TP1=t2==t1 and t2<N,later_TP2_despite_BE=later2,later_TP3_despite_BE=later3,BE_before_TP2_terminal_negative=before and ret[-1]<0,BE_before_TP2_terminal_below_cost=before and ret[-1]<BE,terminal_signed_return=float(ret[-1]),path_MAE=float(min(0,min(ret))),path_MFE=float(max(0,max(ret)))))
summary=[]
for p in ['calibration','holdout']:
 for subset in ['all','CHOP_flips2']:
  a=[r for r in rr if r['period']==p and (subset=='all' or r['CHOP_flips2_fixed'])];no=[r for r in a if not r['TP1_hit']];mae=np.array([r['path_MAE'] for r in no]);record=dict(period=p,subset=subset,n=len(a),censored=sum(r['horizon_truncated'] for r in a))
  for k in ['TP1_hit','TP2_hit','TP3_hit','BE_before_TP2','TP2_before_BE','TP2_already_by_TP1','later_TP2_despite_BE','later_TP3_despite_BE','BE_before_TP2_terminal_negative','BE_before_TP2_terminal_below_cost']:record[k]=sum(r[k] for r in a)
  record.update(never_TP1=len(no),neverTP1_terminal_negative=sum(r['terminal_signed_return']<0 for r in no),neverTP1_MAE_median=float(np.median(mae)) if len(mae) else None,neverTP1_MAE_q10=float(np.quantile(mae,.1)) if len(mae) else None,neverTP1_MAE_min=float(min(mae)) if len(mae) else None)
  summary.append(record)
for name,a in [('stats-btc-be-events.csv',rr),('stats-btc-be-summary.csv',summary)]:
 with open(out/name,'w') as f:
  w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
x={'status':'FIXED_PRICE_PATH_FIRST_PASSAGE_COUNTS_NO_PNL_SIMULATION','thresholds':{'TP1':L1,'TP2':L2,'TP3':L3,'postTP1_return_BE':BE},'CHOP':'Exact earlier frozen flips2 baseline: >=2 EMA34 sign flips among7completed daily transitions,2 consecutive raw states enter/exit; frozen entry flag','observations':'All105 native-derived entrytime/side contexts; synchronized minuteclose anchor; stop min24h/originalBTCexit. Entryclose not claimed native avg fill. BE is first later close signed return<=+.11%; report all laterTPs on unchanged observed originalpricepath. BE at observed close can be below threshold; no stop-fill guarantee. TP2 already present atfirstTP1 classified separately.','summary':summary,'sources':src,'maxrss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'limitations':['No actual exit cash/PnL/fill/order simulation, fees not charged to portfolio','+.11% is fixed nominal roundtrip taker allowance, not actual native cost-adjustedBE; funding/slippage UNKNOWN','BE-first negative terminal mark is potential avoided price loss only, not proven realized saving','SubsequentTP afterBE is potential profitable-tail cut, not lost actual profit calculation','Minuteclose returns omit intraminute excursions; no path stop execution guarantee','24h/originalexit truncation informative; no future probability/DD guarantee','No threshold retuning or extra filtering; CHOPsubset sparse','No SOL/nativeobserver/nativeengine read or execution']};(out/'stats-btc-be-result.json').write_text(json.dumps(x,indent=2,default=lambda v:v.item() if hasattr(v,"item") else str(v)));print(json.dumps(x,indent=2,default=lambda v:v.item() if hasattr(v,"item") else str(v)))
