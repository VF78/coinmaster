import os,csv,json,time,resource,hashlib,calendar
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
os.chdir('/root/.openclaw/workspace/coinmaster/coinmaster');out=Path('reports/chop-pair-113');D=86400000;START=1725148800000;SPLIT=1756684800000;END=1788220800000
BT=.005317;ST=.01040878
sources={}
def read(p,cols):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 sources[p]=h.hexdigest();a=[]
 for b in pq.ParquetFile(p).iter_batches(batch_size=8192,columns=cols,use_threads=False):a.append(np.column_stack([np.asarray(b.column(i).to_pylist(),dtype='float64') for i in range(len(cols))]))
 return np.concatenate(a)
def ema(a,n):
 b=a.copy();alpha=2/(n+1)
 for i in range(1,len(a)):b[i]=alpha*a[i]+(1-alpha)*b[i-1]
 return b
p='runtime/var/data/normalized/bybit-';daily={s:read(p+s+'USDT-daily.parquet',['open_time_ms','high','low','close']) for s in ['BTC','SOL']};b=daily['BTC'];c=b[:,3];e=ema(c,34);atr=ema(np.maximum(b[:,1]-b[:,2],np.maximum(abs(b[:,1]-np.roll(c,1)),abs(b[:,2]-np.roll(c,1)))),14);raw=(abs(c-e)/atr<=1)&(abs(e-np.roll(e,3))/atr<=.35);mask=np.zeros(len(c),bool);state=False
for i in range(1,len(c)):
 if raw[i]==raw[i-1]:state=bool(raw[i])
 mask[i]=state
ts=b[:,0].astype('int64')+D
bars={s:read(p+s+'USDT-execution-1m.parquet',['open_time_ms','close']) for s in ['BTC','SOL']};assert np.array_equal(bars['BTC'][:,0],bars['SOL'][:,0]);mt=bars['BTC'][:,0].astype('int64')+60000
ctx='reports/immediate-sol-insurance-113/postmortem-chop-entries.csv';sources[ctx]=hashlib.sha256(Path(ctx).read_bytes()).hexdigest();events=[]
for r in csv.DictReader(open(ctx)):
 ms=int(r['P0_known_ms']);end=min(ms+D,int(r['last_exit_ms']),END);ix=np.searchsorted(mt,ms);last=np.searchsorted(mt,end,side='right');fi=np.arange(ix+1,last);sd=1 if r['BTCside']=='LONG' else -1;di=np.searchsorted(ts,ms,side='right')-1;db=daily['BTC'];ds=daily['SOL'];si=np.searchsorted(ds[:,0],db[di-90:di+1,0]);rb=np.diff(np.log(db[di-90:di+1,3]));rs=np.diff(np.log(ds[si,3]));cv=np.cov(rb,rs,ddof=1);beta=cv[0,1]/cv[0,0];rho2=cv[0,1]**2/(cv[0,0]*cv[1,1]);br=sd*(bars['BTC'][fi,1]/bars['BTC'][ix,1]-1);sr=-sd*(bars['SOL'][fi,1]/bars['SOL'][ix,1]-1);hitB=np.flatnonzero(br>=BT);hitS=np.flatnonzero(sr>=ST);zB=int(hitB[0]) if len(hitB) else len(fi);zS=int(hitS[0]) if len(hitS) else len(fi);z=min(zB,zS);kind='BOTH_same_close' if zB==zS and z<len(fi) else 'BTC' if zB<zS else 'SOL' if zS<zB else 'NONE';z=min(z,len(fi)-1)
 row={'number':int(r['number']),'period':'calibration' if ms<SPLIT else 'holdout','entry_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(ms/1000)),'BTC_side':r['BTCside'],'near_slope':bool(mask[di]),'beta':float(beta),'rho_squared':float(rho2),'first_event':kind,'event_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(mt[fi[z]]/1000)),'elapsed_minutes':int((mt[fi[z]]-ms)/60000),'end_reason':'original_BTC_exit' if int(r['last_exit_ms'])<ms+D else '24h_horizon','BTC_entry_close':float(bars['BTC'][ix,1]),'SOL_entry_close':float(bars['SOL'][ix,1]),'BTC_event_close':float(bars['BTC'][fi[z],1]),'SOL_event_close':float(bars['SOL'][fi[z],1]),'BTC_signed_return':float(br[z]),'SOL_opposite_signed_return':float(sr[z]),'nohit_mark_only':kind=='NONE'}
 for method,a in [('BTC_only',0),('factor_neutral',1/beta),('minimum_variance',rho2/beta)]:
  fee=.0011*(1+a);gross=br+a*sr;net=gross-fee;row[method+'_SOLnotional_perNB']=float(a);row[method+'_fee']=float(fee);row[method+'_gross']=float(gross[z]);row[method+'_net']=float(net[z]);row[method+'_max_path_loss_net']=float(min(0,min(net[:z+1])));row[method+'_net_ge_zero']=bool(net[z]>=0);row[method+'_net_ge_buffer001']=bool(net[z]>=.001)
 events.append(row)
summary=[]
for period in ['calibration','holdout']:
 for subset in ['all','near_slope']:
  rr=[r for r in events if r['period']==period and (subset=='all' or r['near_slope'])]
  for method in ['BTC_only','factor_neutral','minimum_variance']:
   n=np.array([r[method+'_net'] for r in rr]);loss=np.array([r[method+'_max_path_loss_net'] for r in rr]);summary.append(dict(period=period,subset=subset,method=method,n=len(rr),firstBTC=sum(r['first_event']=='BTC' for r in rr),firstSOL=sum(r['first_event']=='SOL' for r in rr),firstBOTH=sum(r['first_event']=='BOTH_same_close' for r in rr),nohit=sum(r['first_event']=='NONE' for r in rr),net_mean=float(np.mean(n)),net_median=float(np.median(n)),net_q10=float(np.quantile(n,.1)),net_positive_count=int(sum(n>0)),net_ge0=int(sum(n>=0)),net_ge001=int(sum(n>=.001)),max_path_loss_BTCnotional=float(min(loss)),median_max_path_loss_BTCnotional=float(np.median(loss)),median_fee=float(np.median([r[method+'_fee'] for r in rr]))))
for file,rr in [('stats-joint-events.csv',events),('stats-joint-summary.csv',summary)]:
 with open(out/file,'w') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
x={'status':'ONE_FIXED_POINTWISE_EVENT_DIAGNOSTIC_NOT_PNL_ENGINE','frozen_thresholds':{'BTC':BT,'oppositeSOL':ST,'horizon_minutes':1440,'max_horizon':'original native BTC exit'},'n':len(events),'sources':sources,'summary':summary,'maxrss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'limitations':['All contexts included, NONE is observed mark not fabricated execution','Entry synchronized close differs native avg fill; exact original context time/side unchanged','Original profitable SOL alpha not simulated; no strategy implementation','Fees .11% roundtrip each notional, funding/spread/slippage/impact/delay UNKNOWN','No sequential partials/BE/rearm/cash/compounding/margin/native TOTAL ROI DD','Max path loss in units initial BTC notional, not portfolio drawdown','Near_slope fixed calibration-selected context, table only; no OOS retuning','Calibration eventpaths crossing split can descriptively include holdout marks; no parameters fitted in this fixed test','Close-only event no intraminute fill guarantee']};(out/'stats-joint-result.json').write_text(json.dumps(x,indent=2));print(json.dumps(x,indent=2))
