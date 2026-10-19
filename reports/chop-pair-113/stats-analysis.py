import os,json,csv,hashlib,time,resource,calendar
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
ROOT=Path('/root/.openclaw/workspace/coinmaster/coinmaster'); os.chdir(ROOT)
OUT=ROOT/'reports/chop-pair-113'; OUT.mkdir(exist_ok=True)
D=86400000; START=1725148800000; SPLIT=1756684800000; END=1788220800000
sources={}
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p,cols):
 sources[str(p)]=sha(p); q=pq.ParquetFile(p); a=[]
 for batch in q.iter_batches(batch_size=8192,columns=cols,use_threads=False):
  a.append(np.column_stack([np.array(batch.column(i).to_pylist(),dtype=np.float64) for i in range(len(cols))]))
 return np.concatenate(a)
def ema(x,n):
 y=x.copy(); al=2/(n+1)
 for i in range(1,len(x)):y[i]=al*x[i]+(1-al)*y[i-1]
 return y
p='runtime/var/data/normalized/bybit-'; daily={}
for sym in ['BTCUSDT','SOLUSDT']:
 daily[sym]=read(p+sym+'-daily.parquet',['open_time_ms','high','low','close'])
b=daily['BTCUSDT']; ts=b[:,0].astype('int64')+D;c=b[:,3]; e=ema(c,34); tr=np.maximum(b[:,1]-b[:,2],np.maximum(abs(b[:,1]-np.roll(c,1)),abs(b[:,2]-np.roll(c,1))));atr=ema(tr,14); side=np.where(c>=e,1,-1);flip=np.r_[0,np.diff(side)!=0]; flips=np.array([sum(flip[max(0,i-6):i+1]) for i in range(len(c))]);er=np.full(len(c),np.nan)
for i in range(7,len(c)):er[i]=abs(c[i]-c[i-7])/sum(abs(np.diff(c[i-7:i+1])))
near=abs(c-e)/atr<=1;slope=abs(e-np.roll(e,3))/atr<=.35
raw={'flips2':flips>=2,'flips2_near':(flips>=2)&near,'near_ER':near&(er<=.35),'near_slope':near&slope,'ER_slope':(er<=.35)&slope}
def hyst(x):
 y=np.zeros(len(x),bool); state=False
 for i in range(1,len(x)):
  if x[i]==x[i-1]:state=bool(x[i])
  y[i]=state
 return y
masks={k:hyst(v) for k,v in raw.items()};label=np.zeros(len(c),bool);valid=np.zeros(len(c),bool)
for i in range(len(c)-7):
 path=c[i:i+8];label[i]=abs(path[-1]-path[0])/sum(abs(np.diff(path)))<=.35 and sum(flip[i+1:i+8])>=2;valid[i]=True

def runs(mask):
 starts=np.flatnonzero(mask&~np.r_[False,mask[:-1]]); ends=np.flatnonzero(mask&~np.r_[mask[1:],False]);return list(zip(starts,ends))
rows=[]
for period,lo,hi in [('calibration',START,SPLIT),('holdout',SPLIT,END)]:
 evalm=(ts>=lo)&(ts<hi)&valid
 for name,m in masks.items():
  tp=sum(m&label&evalm);fp=sum(m&~label&evalm); fn=sum(~m&label&evalm);tn=sum(~m&~label&evalm)
  onset=[];endlat=[];miss=0
  for a,z in runs(label&evalm):
   found=np.flatnonzero(m[a:z+1]);
   if len(found):onset.append(int(found[0]))
   else:miss+=1
   off=np.flatnonzero(~m[z+1:min(z+15,len(m))]);
   if len(off):endlat.append(int(off[0]))
  rows.append(dict(period=period,detector=name,days=int(sum(evalm)),flag_days=int(sum(m&evalm)),label_days=int(sum(label&evalm)),tp=int(tp),fp=int(fp),fn=int(fn),tn=int(tn),precision=float(tp/(tp+fp)) if tp+fp else None,recall=float(tp/(tp+fn)) if tp+fn else None,false_positive_rate=float(fp/(fp+tn)) if fp+tn else None,balanced_accuracy=float(.5*(tp/(tp+fn)+tn/(tn+fp))) if tp+fn and tn+fp else None,onset_detected=len(onset),onset_missed=miss,onset_delay_median_D=float(np.median(onset)) if onset else None,end_delay_median_D=float(np.median(endlat)) if endlat else None))
selected=max([r for r in rows if r['period']=='calibration'],key=lambda r:r['balanced_accuracy'])['detector'];mask=masks[selected]
with open(OUT/'stats-detectors.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
# One sequential read per symbol; no native observer and no economic engine.
bars={}
for sym in ['BTCUSDT','SOLUSDT']:
 bars[sym]=read(p+sym+'-execution-1m.parquet',['open_time_ms','high','low','close'])
assert np.array_equal(bars['BTCUSDT'][:,0],bars['SOLUSDT'][:,0]);mt=bars['BTCUSDT'][:,0].astype('int64')+60000
assert len(mt)==1051200 and mt[0]==START+60000 and mt[-1]==END
bclose=bars['BTCUSDT'][:,3];sclose=bars['SOLUSDT'][:,3]
ctx='reports/immediate-sol-insurance-113/postmortem-chop-entries.csv';sources[ctx]=sha(ctx); events=[]
with open(ctx) as f:
 for r in csv.DictReader(f):events.append(dict(kind='native_BTC_entry',ms=int(r['P0_known_ms']),end=int(r['last_exit_ms']),side=1 if r['BTCside']=='LONG' else -1,number=int(r['number'])))
for i in np.flatnonzero(mask&~np.r_[False,mask[:-1]]):
 if START<=ts[i]<END:events.append(dict(kind='chop_onset_context',ms=int(ts[i]),end=END,side=int(side[i]),number=int(i)))
# Completed SOL 15m/1h EMA flips inside selected causal chop, solely signal diagnostics.
for step in [15,60]:
 idx=np.arange(step-1,len(mt),step);cc=sclose[idx];ss=np.where(cc>=ema(cc,34),1,-1)
 for j in np.flatnonzero(np.r_[False,np.diff(ss)!=0]):
  ms=int(mt[idx[j]]);di=np.searchsorted(ts,ms,side='right')-1
  if mask[di]:events.append(dict(kind='SOL_'+str(step)+'m_flip',ms=ms,end=END,side=int(-ss[j]),number=int(j)))
obs=[]; paths={}
for event in events:
 ms=event['ms'];ix=int(np.searchsorted(mt,ms));di=int(np.searchsorted(ts,ms,side='right')-1)
 if ix>=len(mt) or di<91:continue
 # beta from 90 prior fully completed paired daily log-return observations.
 db=daily['BTCUSDT'];ds=daily['SOLUSDT'];ixs=np.searchsorted(ds[:,0],db[di-90:di+1,0]);assert np.array_equal(ds[ixs,0],db[di-90:di+1,0]);rb=np.diff(np.log(db[di-90:di+1,3]));rs=np.diff(np.log(ds[ixs,3]));beta=float(np.cov(rb,rs,ddof=1)[0,1]/np.var(rb,ddof=1))
 if beta<=0:continue
 for h in ([15,60,1440,10080] if event['kind'] in ['native_BTC_entry','chop_onset_context'] else [1440]):
  stop=min(ix+h+1,len(mt),int(np.searchsorted(mt,event['end'],side='right')));n=stop-ix
  if n<1:continue
  # Entry observation is close, future observations start next minute; fixed entry beta.
  fi=np.arange(ix+1,stop); n=len(fi)
  if n<1:continue
  sd=event['side']; br=sd*(bclose[fi]/bclose[ix]-1); sr=-sd*(sclose[fi]/sclose[ix]-1)
  row=dict(event=len(obs),kind=event['kind'],number=event['number'],utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(ms/1000)),period='calibration' if ms<SPLIT else 'holdout',horizon_minutes=h,observed_minutes=n,censored=n<h,beta=beta,BTC_side='LONG' if sd>0 else 'SHORT',chop=bool(mask[di]),BTC_entry_close=float(bclose[ix]),SOL_entry_close=float(sclose[ix]),BTC_MFE_close=float(max(0,max(br))),BTC_MAE_close=float(min(0,min(br))),SOL_MFE_close=float(max(0,max(sr))),SOL_MAE_close=float(min(0,min(sr))))
  obs.append(row);paths[row['event']]=(br,sr,fi)
# Quantile thresholds use calibration event starts AND full horizon ending before split, excluding native truncation.
tps=[];examples=[]
for kind in sorted(set(r['kind'] for r in obs)):
 for h in sorted(set(r['horizon_minutes'] for r in obs if r['kind']==kind)):
  for leg in ['BTC','SOL']:
   train=[r for r in obs if r['kind']==kind and r['horizon_minutes']==h and r['period']=='calibration' and not r['censored'] and int(calendar.timegm(time.strptime(r['utc'],'%Y-%m-%dT%H:%M:%SZ')))*1000+h*60000<SPLIT]
   if len(train)<8:continue
   levels=np.quantile([r[leg+'_MFE_close'] for r in train],[.2,.5,.8])
   for ti,level in enumerate(levels,1):
    if level<=0:continue
    for period in ['calibration','holdout']:
     sample=[r for r in obs if r['kind']==kind and r['horizon_minutes']==h and r['period']==period];hit=[];net=[];maes=[];amb=0
     for r in sample:
      br,sr,fi=paths[r['event']];lr=br if leg=='BTC' else sr;hits=np.flatnonzero(lr>=level)
      if len(hits):
       z=int(hits[0]);fee=.0011*(1+1/r['beta']);pair=float(br[z]+sr[z]/r['beta']);nv=pair-fee;hit.append(z+1);net.append(nv);maes.append(float(min(lr[:z+1])))
       if period=='holdout' and len(examples)<30 and kind=='native_BTC_entry':examples.append(dict(kind=kind,event_utc=r['utc'],horizon_minutes=h,trigger_leg=leg,TP=ti,level=float(level),hit_minutes=z+1,hit_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(mt[fi[z]]/1000)),BTC_entry=r['BTC_entry_close'],SOL_entry=r['SOL_entry_close'],BTC_exit=float(bclose[fi[z]]),SOL_exit=float(sclose[fi[z]]),BTC_side=r['BTC_side'],beta=r['beta'],pair_gross_per_BTC_notional=pair,taker_roundtrip_cost=fee,pair_after_fee_before_unknown_friction=nv))
     tps.append(dict(kind=kind,horizon_minutes=h,leg=leg,TP=ti,desired_hit_probability=[.8,.5,.2][ti-1],level_fraction=float(level),train_uncensored_n=len(train),period=period,n=len(sample),censored=sum(r['censored'] for r in sample),hits=len(hit),observed_hit_fraction=len(hit)/len(sample) if sample else None,hit_latency_median_min=float(np.median(hit)) if hit else None,conditional_pair_net_median=float(np.median(net)) if net else None,conditional_pair_net_positive_fraction=float(np.mean(np.array(net)>0)) if net else None,conditional_leg_MAE_median=float(np.median(maes)) if maes else None))
for name,rr in [('stats-paths.csv',obs),('stats-TP.csv',tps),('stats-pair-examples.csv',examples)]:
 with open(OUT/name,'w') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
result={'status':'DESCRIPTIVE_NO_ECONOMIC_SIMULATION','head':os.popen('git rev-parse HEAD').read().strip(),'selected_detector_calibration_only':selected,'detectors':rows,'tp':tps,'sources':sources,'resource_maxrss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'source_hash_reuse_manifest':'reports/alpha-cushion-113/analysis-preflight.json','diagnostic_label':'At completed daily close forward7 daily ER<=.35 AND >=2 forward EMA34 sign flips; label never a feature','detector_rules':'EMA34; ATR EMA14 true range; near<=1ATR; ER7<=.35; slope abs(EMA[t]-EMA[t-3])/ATR<=.35; flips>=2 among7 completed daily sign transitions. All masks enter/exit only after2 consecutive raw states.','split':'calibration 2024-09-01..2025-09-01; holdout 2025-09-01..2026-09-01. Calibration TP training excludes horizons crossing split. End limited by dataset or actual native BTC exit.','cost_arithmetic':'Fixed entry beta from90 completed daily log returns, opposite SOL notional=BTCnotional/beta. pairgross=signedBTCreturn+oppositeSOLreturn/beta. subtract .0011*(1+1/beta), conservative taker roundtrip BOTH legs. Funding/slippage/marketimpact unknown; not true net lower bound. BTC TP triggers diagnostically change close fractions only, preserve native entry context.','limitations':['No counterfactual fills, sizing, margin, cash, equity, TOTAL, ROI or DD computed','Overlapping paths are dependent; hit fractions are descriptive not guarantees','Minute close trigger executable only later; no fill guarantee. Entry close differs from actual native avg fill; context side/time exact','Censored paths counted nonhits in observed hit fraction; native actual exit truncation informative','No high-low ordering used for TP; all MFE/MAE here close-based conservative diagnostics','SOL signals within chop are descriptive context and not substituted native entries','Daily source hashes fresh; minute execution source hashes fresh sequentially; no mark/observer scan','Conditional pair net excludes nonhits and is NOT an unconditional edge estimate']}
(OUT/'stats-summary.json').write_text(json.dumps(result,indent=2));print(json.dumps({'selected':selected,'maxrss':result['resource_maxrss_KiB'],'events':len(events),'observations':len(obs),'TP_rows':len(tps),'detectors':rows},indent=2))
