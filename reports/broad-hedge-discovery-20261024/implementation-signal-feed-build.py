"""Pure market ALL_H4 feed. No positions, parents, capital, execution or outcome inputs."""
from pathlib import Path
from decimal import Decimal as D,localcontext
from datetime import datetime,timezone
import csv,json,hashlib,math
import numpy as np
import pyarrow.parquet as pq
O=Path(__file__).resolve().parent
DATA=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/inputs/data/normalized')
M=60000000000;H=60*M;DAY=24*H
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dec(v):return format(float(v),'.17g') if math.isfinite(float(v)) else ''
def load_market():
 out={};paths={}
 for sym in ['BTC','SOL']:
  for kind,cols in [('execution-1m',['open_time_ms','open','high','low','close']),('daily',['open_time_ms','close']),('funding',['funding_time_ms','funding_rate'])]:
   p=DATA/f'bybit-{sym}USDT-{kind}.parquet';paths[str(p)]=sha(p);out[sym,kind]=pq.read_table(p,columns=cols).to_pydict()
 return out,paths

def aggregate(d,end_ns=None):
 ts=d['open_time_ms'];n=len(ts)
 if end_ns is not None:n=int(np.searchsorted(np.array(ts,np.int64)*1000000+M,end_ns,side='right'))
 assert n%240==0 and int(ts[0])*1000000%(4*H)==0
 t=np.array(ts[:n],np.int64);assert np.all(np.diff(t)==60000)
 rows=[]
 for i in range(0,n,240):
  rows.append({'end_ns':(int(ts[i])+240*60000)*1000000,'open':str(d['open'][i]),'close':str(d['close'][i+239]),'high':max(D(str(v)) for v in d['high'][i:i+240]),'low':min(D(str(v)) for v in d['low'][i:i+240])})
 return rows

def build_rows(market,end_ns=None):
 bars={sym:aggregate(market[sym,'execution-1m'],end_ns) for sym in ['BTC','SOL']};assert [b['end_ns'] for b in bars['BTC']]==[b['end_ns'] for b in bars['SOL']]
 dB=market['BTC','daily'];dS=market['SOL','daily'];dt=np.array(dB['open_time_ms'],np.int64)*1000000+DAY;assert np.array_equal(dt,np.array(dS['open_time_ms'],np.int64)*1000000+DAY) and np.all(np.diff(dt)==DAY)
 cb=np.array(dB['close'],float);cs=np.array(dS['close'],float);rb=np.r_[np.nan,cb[1:]/cb[:-1]-1];rs=np.r_[np.nan,cs[1:]/cs[:-1]-1]
 funding={sym:(np.array(market[sym,'funding']['funding_time_ms'],np.int64)*1000000,np.array(market[sym,'funding']['funding_rate'],float)) for sym in ['BTC','SOL']}
 rows=[];TR=[];ATR=None
 with localcontext() as ctx:
  ctx.prec=50
  for k,(B,S) in enumerate(zip(bars['BTC'],bars['SOL'])):
   t=B['end_ns'];previous=D(bars['SOL'][k-1]['close']) if k else None;tr=S['high']-S['low'] if previous is None else max(S['high']-S['low'],abs(S['high']-previous),abs(S['low']-previous));TR.append(tr)
   if k==13:ATR=sum(TR,D(0))/D(14)
   elif k>13:ATR=(D(13)*ATR+tr)/D(14)
   i=int(np.searchsorted(dt,t-DAY,side='right'))-1;beta=rho=sb=ss=math.nan;di_first=di_last='';coeff=False
   if i>=30:
    x=rb[i-29:i+1];y=rs[i-29:i+1];sb=float(np.std(x,ddof=1));ss=float(np.std(y,ddof=1));cov=float(np.cov(x,y,ddof=1)[0,1]);beta=cov/(sb*sb) if sb else math.nan;rho=cov/(sb*ss) if sb and ss else math.nan;coeff=all(math.isfinite(v) and v>0 for v in [beta,rho,sb,ss]) and rho<=1+1e-12;di_first=int(dt[i-29]);di_last=int(dt[i])
   bvalid=k>=7;bl=bs=False;kl=ks='';current=D(B['close']);prior=D(bars['BTC'][k-1]['close']) if k else None
   if bvalid:
    kl=max(x['high'] for x in bars['BTC'][k-7:k-1]);ks=min(x['low'] for x in bars['BTC'][k-7:k-1]);bl=bool(prior>kl and current<=kl and current<prior);bs=bool(prior<ks and current>=ks and current>prior)
   fdates={};g={};fund_valid=True
   for sym in ['BTC','SOL']:
    ft,fr=funding[sym];j=int(np.searchsorted(ft,t,side='left'))-1
    if j<1:fund_valid=False;fdates[sym]=('','');g[sym]=math.nan
    else:
     assert ft[j]<t and ft[j]>ft[j-1];fdates[sym]=(int(ft[j]),int(ft[j-1]));g[sym]=float(fr[j])/((int(ft[j])-int(ft[j-1]))/H)
   diff=g['SOL']-beta*g['BTC'] if fund_valid and math.isfinite(beta) else math.nan;fvalid=bool(k>=1 and coeff and fund_valid and math.isfinite(diff));fl=bool(fvalid and current<prior and diff>0);fs=bool(fvalid and current>prior and diff<0)
   row=dict(decision_ns=t,available_ns=t,not_before_ns=t+M,btc_close=B['close'],sol_close=S['close'],btc_h4_open=B['open'],btc_previous_h4_close=bars['BTC'][k-1]['close'] if k else '',beta_d1_30=dec(beta),rho_d1_30=dec(rho),sigma_btc_d1_30=dec(sb),sigma_sol_d1_30=dec(ss),risk_coefficients_valid=int(coeff),d1_last_return_end_ns=di_last,d1_first_return_end_ns=di_first,sol_atr_h4_14=str(ATR) if ATR is not None else '',sol_atr_valid=int(ATR is not None and ATR>0),atr_last_h4_end_ns=t if ATR is not None else '',b2_pattern_valid=int(bvalid),b2_long=int(bl),b2_short=int(bs),b2_long_k=str(kl) if bvalid else '',b2_short_k=str(ks) if bvalid else '',f0_pattern_valid=int(fvalid),f0_long=int(fl),f0_short=int(fs),f0_open_o=B['open'],btc_funding_last_ns=fdates['BTC'][0],btc_funding_previous_ns=fdates['BTC'][1],sol_funding_last_ns=fdates['SOL'][0],sol_funding_previous_ns=fdates['SOL'][1],funding_differential_per_hour=dec(diff))
   rows.append(row)
 return rows

def main():
 contract=O/'implementation-signal-feed-contract.json';schema=json.loads(contract.read_text());market,pins=load_market();rows=build_rows(market);assert len(rows)==4380 and list(rows[0])==schema['columns'];ts=[r['decision_ns'] for r in rows];assert all(b-a==4*H for a,b in zip(ts,ts[1:]));assert ts[-1]==1788220800000000000
 p=O/'implementation-signal-feed.csv'
 with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=schema['columns'],lineterminator='\n');w.writeheader();w.writerows(rows)
 metadata={'schema':schema['schema'],'status':'MARKET_ONLY_FEATURE_FEED_BUILT_PENDING_VERIFICATION','rows':4380,'columns':schema['columns'],'first_decision_ns':ts[0],'last_decision_ns':ts[-1],'counts':{key:sum(int(r[key]) for r in rows) for key in ['risk_coefficients_valid','sol_atr_valid','b2_pattern_valid','b2_long','b2_short','f0_pattern_valid','f0_long','f0_short']},'b2_true_without_ATR':sum((r['b2_long'] or r['b2_short']) and not r['sol_atr_valid'] for r in rows),'BTC_rawopen_differs_previous_H4close':sum(bool(r['btc_previous_h4_close']) and D(r['btc_h4_open'])!=D(r['btc_previous_h4_close']) for r in rows),'coefficient_serialization':'17significant-digit finite float sample estimates, emitted UTF8decimalstrings; no NaN/Inf','ATR_arithmetic':'Decimal50, firstTR high-low, first14TR mean thenWilder1/14','no_native_or_outcome_inputs':True,'market_input_sha256':pins,'contract_sha256':sha(contract),'builder_sha256':sha(Path(__file__)),'csv_sha256':sha(p),'numpy_version':np.__version__,'pyarrow_version':__import__('pyarrow').__version__,'engine_runs':0,'new_trade_outcomes':0,'runtime_source_changes':0}
 (O/'implementation-signal-feed-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n');print(json.dumps({k:metadata[k] for k in ['rows','counts','b2_true_without_ATR','BTC_rawopen_differs_previous_H4close','csv_sha256','builder_sha256']},indent=2))
if __name__=='__main__':main()
