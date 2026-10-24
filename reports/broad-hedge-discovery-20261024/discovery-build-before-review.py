"""Feature and observed-baseline build ONLY. No hypothetical action labels."""
from pathlib import Path
from decimal import Decimal as D, getcontext
from datetime import datetime,timezone
import csv,json,hashlib,sqlite3,collections,bisect,math,re
import numpy as np
import pyarrow.parquet as pq
getcontext().prec=60
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
DATA=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/inputs/data/normalized')
M=60000000000;H=60*M;DAY=24*H
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return list(csv.DictReader(Path(p).open()))
def utc(t):return datetime.fromtimestamp(t/1e9,timezone.utc).isoformat()
def ns(s):return int(datetime.fromisoformat(s).timestamp())*10**9
inputs={}
def pin(p):p=Path(p);inputs[str(p)]=sha(p);return p
def dump(name,rows):
 with (O/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
led=json.loads(pin(R/'reports/early-capital-hedge-20261024/screen-ledger.json').read_text())
fp=pin(next(p for p in led['input_sha256'] if p.endswith('-fills.csv')));rp=pin(next(p for p in led['input_sha256'] if p.endswith('-raw-native.json')))
assert inputs[str(fp)]==led['input_sha256'][str(fp)] and inputs[str(rp)]==led['input_sha256'][str(rp)]
raw=json.loads(rp.read_text());artifact=json.loads(pin(rp.with_name(rp.name.replace('-raw-native.json','.json'))).read_text())
accept=json.loads(pin(R/'reports/market-redesign-20261024/native-analysis-R3.json').read_text())
journal=pin(artifact['funding_journal']);assert inputs[str(journal)]==accept['input_sha256'][str(journal)]
assert not Path(str(journal)+'-wal').exists()
conn=sqlite3.connect(journal.as_uri()+'?mode=ro&immutable=1',uri=True)
fund=conn.execute('SELECT event_id,instrument_id,ts_event,before_total,after_total,signed_delta FROM funding_cash ORDER BY ts_event,event_id').fetchall();conn.close()
assert collections.Counter(fund)==collections.Counter(tuple(x) for x in raw['funding']['signed_native_cash_deltas'])
assert all(x[1].startswith('BTC') for x in fund)
# Native audit order is preserved. Resolve its fill side against CSV identity.
csvfills=read(fp);sideby=collections.defaultdict(list)
for f in csvfills:
 key=(ns(f['ts_last']),D(f['filled_qty']),D(f['avg_px']).quantize(D('.1')),D(re.search(r'([0-9.]+) USDT',f['commissions'])[1]))
 sideby[key].append(1 if f['side']=='BUY' else -1)
fills=[]
for k,a in enumerate(raw['fill_audit']):
 key=(int(a['fill_ns']),D(a['qty']),D(a['px']).quantize(D('.1')),D(a['commission']));sides=sideby[key];assert sides and len(set(sides))==1
 side=sides.pop();fills.append(dict(t=int(a['fill_ns']),dq=D(a['qty'])*side,px=D(a['px']),fee=D(a['commission']),audit_index=k,action=a['action'],reason=a['reason']))
assert len(fills)==354 and all(not x for x in sideby.values())
assert all(a['t']<=b['t'] for a,b in zip(fills,fills[1:]))
groups=[];bytime=collections.defaultdict(list);fundby=collections.defaultdict(list)
for f in fills:bytime[f['t']].append(f)
for f in fund:fundby[int(f[2])].append(D(f[5]))
q=D(0);c=D(10000);cycles=[];cycle=0;firstpx=None
for t,fs in sorted(bytime.items()):
 before=q
 for f in fs:q+=f['dq']
 if not before and q:
  cycle+=1;firstpx=fs[0]['px'];cycles.append(dict(cycle=cycle,first_fill_ns=t,first_fill_price=str(firstpx),side=1 if q>0 else -1,actual_flat_ns=0))
 assert not before or not q or before*q>0
 kind='add' if not before or before*(q-before)>0 else 'reduce'
 assert all((before*f['dq']>=0 if kind=='add' else before*f['dq']<0) for f in fs)
 groups.append(dict(t=t,before=before,after=q,cycle=cycle,kind=kind,fills=fs))
 if not q:cycles[-1]['actual_flat_ns']=t
assert q==0 and cycle==83 and all(z['actual_flat_ns'] for z in cycles)
gts=[g['t'] for g in groups]
dump('discovery-actual-cycles.csv',cycles)
market={};daily={};rates={};schemas={}
for sym in ['BTC','SOL']:
 for kind in ['execution-1m','mark-1m','daily','funding']:
  p=pin(DATA/f'bybit-{sym}USDT-{kind}.parquet');table=pq.read_table(p);d=table.to_pydict();schemas[str(p)]=str(table.schema)
  if kind=='daily':daily[sym]=d
  elif kind=='funding':rates[sym]=(np.array(d['funding_time_ms'],np.int64)*10**6,np.array(d['funding_rate'],float))
  else:market[sym,kind]=(np.array(d['open_time_ms'],np.int64)*10**6+M,{k:np.array(v,float) for k,v in d.items() if k!='open_time_ms'})
mt=market['BTC','execution-1m'][0];assert all(np.array_equal(mt,v[0]) for v in market.values())
marks=market['BTC','mark-1m'][1]['close'];N=len(mt);ix={int(t):i for i,t in enumerate(mt)}
qgrid=np.zeros(N);cgrid=np.zeros(N);wgrid=np.zeros(N);pregrid=np.zeros(N);highgrid=np.zeros(N);q=D(0);c=D(10000);high=10000.;baserows=[]
for i,t0 in enumerate(mt):
 t=int(t0);mark=marks[i];before=float(c)+float(q)*mark;pregrid[i]=before
 fs=bytime.get(t,());ff=sum(fundby.get(t,()),D(0));prefix=[before];cq=c;qq=q
 for f in fs:
  cq-=f['dq']*f['px']+f['fee'];qq+=f['dq'];prefix.append(float(cq)+float(qq)*mark)
 # Exact same-time funding/fill chronology not invented: retain both extrema.
 bracket=prefix+[x+float(ff) for x in prefix];c=cq+ff;q=qq
 qgrid[i]=float(q);cgrid[i]=float(c);wgrid[i]=float(c)+float(q)*mark;high=max(high,*bracket,wgrid[i]);highgrid[i]=high
 if fs or ff:
  baserows.append(dict(timestamp_ns=t,utc=utc(t),fill_audit_indices=','.join(str(f['audit_index']) for f in fs),fill_count=len(fs),funding_event_count=len(fundby.get(t,())),q_after=str(q),pricecash_after=str(c),rawmark=repr(mark),Wraw_pre=repr(before),Wraw_after=repr(wgrid[i]),same_timestamp_funding_fill_tie=bool(fs and ff),boundary_wealth_min=repr(min(bracket)),boundary_wealth_max=repr(max(bracket))))
fundsum=sum((D(f[5]) for f in fund),D(0));assert fundsum==D('4063.32156049') and q==0
assert abs(c-D('120718.40416503'))<=D('.000001')
dump('discovery-baseline-events.csv',baserows)
np.savez_compressed(O/'discovery-baseline.npz',timestamp_ns=mt,q=qgrid,pricecash=cgrid,Wraw=wgrid,Wraw_pre=pregrid,Hraw_bracketed=highgrid)
# Closed bar arrays are independent of future candidate horizons/actions.
bars={}
for sym in ['BTC','SOL']:
 d=market[sym,'execution-1m'][1]
 for hours in [1,4]:
  n=hours*60;assert N%n==0
  z={k:v.reshape(-1,n) for k,v in d.items()};bars[sym,hours]=dict(t=mt[n-1::n],open=z['open'][:,0],high=z['high'].max(1),low=z['low'].min(1),close=z['close'][:,-1],turnover=z['turnover'].sum(1))
b4=bars['BTC',4];s4=bars['SOL',4];b1=bars['BTC',1];s1=bars['SOL',1]
tr=np.full(len(b4['t']),np.nan);atr=tr.copy()
for i in range(1,len(tr)):tr[i]=max(b4['high'][i]-b4['low'][i],abs(b4['high'][i]-b4['close'][i-1]),abs(b4['low'][i]-b4['close'][i-1]))
atr[14]=np.mean(tr[1:15])
for i in range(15,len(tr)):atr[i]=(13*atr[i-1]+tr[i])/14
dt=np.array(daily['BTC']['open_time_ms'],np.int64)*10**6+DAY;assert np.array_equal(dt,np.array(daily['SOL']['open_time_ms'],np.int64)*10**6+DAY)
db=np.array(daily['BTC']['close'],float);ds=np.array(daily['SOL']['close'],float);drb=np.r_[np.nan,db[1:]/db[:-1]-1];drs=np.r_[np.nan,ds[1:]/ds[:-1]-1]
mb=np.array(daily['BTC']['mark_close'],float)/db-1;ms=np.array(daily['SOL']['mark_close'],float)/ds-1
rb4=np.r_[np.nan,b4['close'][1:]/b4['close'][:-1]-1];rs4=np.r_[np.nan,s4['close'][1:]/s4['close'][:-1]-1]
rb1=np.r_[np.nan,b1['close'][1:]/b1['close'][:-1]-1];rs1=np.r_[np.nan,s1['close'][1:]/s1['close'][:-1]-1]
features=[];maskcounts=collections.Counter();NA=''
for k,t0 in enumerate(b4['t']):
 t=int(t0);j=bisect.bisect_left(gts,t)-1
 if j<0 or not groups[j]['after']:continue
 g=groups[j];cy=g['cycle'];s=1 if g['after']>0 else -1;e=t+M
 if e not in ix:continue
 je=bisect.bisect_left(gts,e)-1;ge=groups[je];qe=ge['after'];entry_valid=t not in bytime and e not in bytime and qe and ge['cycle']==cy and (1 if qe>0 else -1)==s
 di=int(np.searchsorted(dt,t-DAY,side='right'))-1
 if di<30:continue
 br=drb[di-29:di+1];sr=drs[di-29:di+1];cov=float(np.cov(br,sr,ddof=1)[0,1]);sb=float(np.std(br,ddof=1));ss=float(np.std(sr,ddof=1));beta=cov/(sb*sb);rho=cov/(sb*ss);a=.5*sb/ss
 positive=all(math.isfinite(v) and v>0 for v in [sb,ss,beta,rho]) and rho<=1+1e-12;common=bool(entry_valid and positive)
 i=ix[t];ei=ix[e];PB=b4['close'][k];PS=s4['close'][k];rB=rb4[k];rS=rs4[k];A=bool(s*rB<0)
 h1i=int(np.searchsorted(b1['t'],t));assert b1['t'][h1i]==t
 corr=float(np.corrcoef(rb1[h1i-23:h1i+1],rs1[h1i-23:h1i+1])[0,1]) if h1i>=24 else math.nan
 lag720last=int(b1['t'][h1i-1]) if h1i>=721 else NA
 peakstart=int(np.searchsorted(mt,cycles[cy-1]['first_fill_ns']));seen=market['BTC','execution-1m'][1]['close'][peakstart:i+1];peak=float(seen.max() if s==1 else seen.min());giveback=s*(peak-PB)
 previous_basis=ms[di-29:di+1]-beta*mb[di-29:di+1];basis=market['SOL','mark-1m'][1]['close'][i]/PS-1-beta*(marks[i]/PB-1);basismean=float(np.mean(previous_basis));basissd=float(np.std(previous_basis,ddof=1))
 gfund={};reserve={}
 for sym in ['BTC','SOL']:
  ft,fr=rates[sym];fi=int(np.searchsorted(ft,t,side='left'))-1;assert fi>=1
  gfund[sym]=fr[fi]/((ft[fi]-ft[fi-1])/H);lo=int(np.searchsorted(ft,t-30*DAY,side='left'));reserve[sym]=float(np.max(np.abs(fr[lo:fi+1])))
 bmax=float(np.max(np.abs(br)));epsmax=float(np.max(np.abs(sr-beta*br)));ell=(1-beta*a)*bmax+a*epsmax
 C=wgrid[i]-.5*highgrid[i];x=abs(float(qe))*market['BTC','execution-1m'][1]['close'][ei];L0=x*(bmax+.00075+3*reserve['BTC'])
 masks={'A0':True,'A1':A,'B1': bool(PB<min(b4['low'][k-6:k])) if s==1 and k>=6 else bool(PB>max(b4['high'][k-6:k])) if k>=6 else None,'B2':None,'V1':bool(A and abs(rB)>2*math.sqrt(float(np.mean(rb4[k-6:k]**2)))) if k>=7 else None,'C1':bool(A and s*rS<0 and rho>=.5),'C2':bool(A and corr<=0) if math.isfinite(corr) else None,'M1':bool(A and s*(basis-basismean)>2*basissd),'L1':None,'P1':bool(A and s*(PB/float(cycles[cy-1]['first_fill_price'])-1)<0),'P2':bool(A and giveback>=atr[k]) if math.isfinite(atr[k]) else None,'R1':None,'R2':None,'F0':bool(A and s*(gfund['SOL']-beta*gfund['BTC'])>0),'J1_raw_tL0_eX_PENDING_REVIEW':bool(L0>.5*max(C,0) and ell<bmax),'J2_raw_tL0_eX_PENDING_REVIEW':bool(L0>max(C,0))}
 if k>=7:
  extreme=max(b4['high'][k-7:k-1]) if s==1 else min(b4['low'][k-7:k-1]);broke=b4['close'][k-1]>extreme if s==1 else b4['close'][k-1]<extreme;inside=PB<=extreme if s==1 else PB>=extreme;masks['B2']=bool(broke and inside and A)
 if k>=42:
  ranges=(b4['high']-b4['low'])/b4['close'];masks['L1']=bool(A and b4['turnover'][k]<.5*np.median(b4['turnover'][k-42:k]) and ranges[k]>np.median(ranges[k-42:k]))
 RB24=PB/b4['close'][k-6]-1 if k>=6 else math.nan;RS24=PS/s4['close'][k-6]-1 if k>=6 else math.nan;res=RS24-beta*RB24
 if math.isfinite(res):masks['R1']=bool(A and s*res<0);masks['R2']=bool(A and s*res>0)
 f=dict(cycle=cy,decision_ns=t,decision_utc=utc(t),entry_reference_ns=e,side=s,common_valid=common,actual_q_t=str(g['after']),actual_q_e=str(qe),fills_t_or_e=bool(t in bytime or e in bytime),daily_window_first_return_end_ns=int(dt[di-29]),daily_window_last_return_end_ns=int(dt[di]),beta=beta,rho=rho,sigmaB=sb,sigmaS=ss,HALFVOL_a=a,H1lag720_last_return_end_ns=lag720last,BTCclose_t=PB,SOLclose_t=PS,BTCexecution_e=market['BTC','execution-1m'][1]['close'][ei],SOLexecution_e=market['SOL','execution-1m'][1]['close'][ei],rB4=rB,rS4=rS,adverseH4=A,H1corr24=corr,BTC24=RB24,SOL24=RS24,signed_residual24=s*res,first_actual_fill_px=cycles[cy-1]['first_fill_price'],running_favorable_close=peak,adverse_giveback=giveback,H4_WilderATR14=atr[k],basis_now=basis,basis_D1mean=basismean,basis_D1sd=basissd,bmax=bmax,epsmax=epsmax,ellH=ell,fB30=reserve['BTC'],fS30=reserve['SOL'],gB=gfund['BTC'],gS=gfund['SOL'],observed_Wraw_t=wgrid[i],observed_Hraw_t=highgrid[i],cushion_t=C,x_e_PENDING_REVIEW=x,L0_PENDING_REVIEW=L0)
 for rule,v in masks.items():f['signal_'+rule]=NA if v is None else int(v);maskcounts[rule+'_true']+=int(common and v is True);maskcounts[rule+'_NA']+=int(v is None)
 features.append(f)
dump('discovery-features.csv',features)
res=dict(status='FEATURE_AND_FACTUAL_BASELINE_ONLY_WAITING_ROOT_FREEZE',engine_runs=0,candidate_outcomes_read=0,candidate_labels_computed=0,held_H4_states=len(features),states_commonvalid=sum(f['common_valid'] for f in features),actual_episodes=83,episodes_with_H4_states=len({f['cycle'] for f in features}),episodes_with_commonvalid=len({f['cycle'] for f in features if f['common_valid']}),native_fills=354,baseline_terminal_pricecash=str(c),baseline_terminal_q=str(q),baseline_actual_signed_funding=str(fundsum),baseline_terminal_native_residual=str(c-D('120718.40416503')),baseline_funding_events=len(fund),baseline_fill_funding_ties=sum(bool(t in bytime) for t in fundby),feature_signal_counts=dict(maskcounts),J_raw_fields='PENDING_ROOT_CLOCK_SIZE_REVIEW_NOT_FINAL_MASKS',Hraw_basis='Causal raw minute completed marks; all native-audit fill-prefix boundaries bracket funding-before/after ties',input_sha256=inputs,schemas=schemas,script_sha256=sha(Path(__file__)),output_sha256={p.name:sha(p) for p in O.glob('discovery-*') if p.is_file() and p.name!='discovery-build.py'})
(O/'discovery-build.json').write_text(json.dumps(res,indent=2)+'\n');print(json.dumps({k:res[k] for k in ['status','held_H4_states','states_commonvalid','episodes_with_H4_states','episodes_with_commonvalid','baseline_terminal_pricecash','baseline_actual_signed_funding','baseline_terminal_native_residual','feature_signal_counts']},indent=2))
