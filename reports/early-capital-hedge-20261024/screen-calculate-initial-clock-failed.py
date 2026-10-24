"""One frozen 24h saved-native conditional cashflow screen. No execution engine."""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D
import csv,json,hashlib,gzip,bisect,re,collections,math
import numpy as np
import pyarrow.parquet as pq
R=Path(__file__).resolve().parent;L=R/'screen-ledger.json';led=json.loads(L.read_text());assert led['logical_outcome_screens_started']==1 and led['logical_outcome_screens_completed']==0
assert hashlib.sha256((R/'PROTOCOL_PREDECLARED.md').read_bytes()).hexdigest()=='878eeeec8383996a0081703e253d1a1b2c994786a8c1715cc88473668d3a1d06'
for p,s in led['input_sha256'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==s
led['calculation_script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();L.write_text(json.dumps(led,indent=2)+'\n')
def read(p):return list(csv.DictReader(Path(p).open()))
def write(name,z):
 assert z
 with (R/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(z[0]));w.writeheader();w.writerows(z)
def ns(s):return int(datetime.fromisoformat(s).timestamp())*10**9
def utc(t):return datetime.fromtimestamp(t/1e9,timezone.utc).isoformat()
M=60*10**9;H=60*M;F=.00055;DAY=24*H;Y=ns('2025-09-01T00:00:00+00:00');EARLY=ns('2025-01-15T00:00:00+00:00')
fp=Path(next(p for p in led['input_sha256'] if p.endswith('fills.csv')));rawp=Path(next(p for p in led['input_sha256'] if p.endswith('raw-native.json')));tracep=Path(next(p for p in led['input_sha256'] if p.endswith('settled-receipts.csv.gz')))
fills=read(fp);raw=json.loads(rawp.read_text());audit=raw['fill_audit'];assert len(fills)==len(audit)==354
ak=collections.Counter((int(x['fill_ns']),D(x['qty']),D(x['px']).quantize(D('.1')),D(x['commission'])) for x in audit)
fk=collections.Counter((ns(x['ts_last']),D(x['filled_qty']),D(x['avg_px']).quantize(D('.1')),D(re.search(r'([0-9.]+) USDT',x['commissions'])[1])) for x in fills);assert ak==fk
bytime=collections.defaultdict(list)
for f in fills:
 assert f['instrument_id'].startswith('BTC') and f['status']=='FILLED' and D(f['quantity'])==D(f['filled_qty'])
 t=ns(f['ts_last']);bytime[t].append(dict(t=t,oid=f['client_order_id'],dq=D(f['filled_qty'])*(1 if f['side']=='BUY' else -1),px=float(f['avg_px']),fee=float(re.search(r'([0-9.]+) USDT',f['commissions'])[1])))
q=D(0);cycle=0;groups=[]
for t,fs in sorted(bytime.items()):
 before=q;delta=sum((f['dq'] for f in fs),D(0));q+=delta
 if not before and q:cycle+=1
 assert not before or not q or before*q>0,'UNORDERED_REVERSAL'
 kinds={'add' if before*f['dq']>0 or not before else 'reduce' for f in fs};assert len(kinds)==1,'MIXED_SAME_TIMESTAMP_ADD_REDUCE_UNKNOWN'
 groups.append(dict(t=t,before=before,after=q,cycle=cycle,kind=next(iter(kinds)),fills=fs))
assert q==0 and cycle==83
gts=[g['t'] for g in groups]
def state(t):
 i=bisect.bisect_left(gts,t)-1
 return (groups[i]['after'],groups[i]['cycle']) if i>=0 else (D(0),0)
features=read(R/'feature-contract-features.csv');trig=[];attempts=[];selected={}
for f in features:
 if not(float(f['side_residual_simple24'])<0 and float(f['side_closed_H4_return'])<0):continue
 assert all(float(f[k])>0 and math.isfinite(float(f[k])) for k in ['lag720_sigmaBTC','lag720_sigmaSOL','lag720_rho','lag720_betaSOLgivenBTC'])
 trig.append(f);cy=int(f['cycle']);t=int(f['decision_ns']);e=t+M
 if cy in selected:continue
 qb,cye=state(e);reason='ELIGIBLE'
 if t in bytime or e in bytime:reason='NO_ACTION_UNKNOWN_EXACT_FILL_T_OR_E'
 elif not qb or (1 if qb>0 else -1)!=int(f['side']) or cye!=cy:reason='NO_ACTION_FLAT_OR_CHANGED_SIDE'
 attempts.append(dict(cycle=cy,decision_ns=t,execution_ns=e,status=reason))
 if reason=='ELIGIBLE':selected[cy]=(f,qb,e)
assert len(trig)==391
DATA=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/inputs/data/normalized');market={};fund={}
for sym in ['BTC','SOL']:
 for kind in ['execution','mark']:
  p=DATA/f'bybit-{sym}USDT-{kind}-1m.parquet';d=pq.read_table(p,columns=['open_time_ms','close']).to_pydict();t=np.array(d['open_time_ms'],np.int64)*10**6+M;v=np.array(d['close'],float);assert np.all(np.diff(t)==M) and np.all(np.isfinite(v));market[(sym,kind)]=(t,v)
 p=DATA/f'bybit-{sym}USDT-funding.parquet';d=pq.read_table(p).to_pydict();ft=np.array(d['funding_time_ms'],np.int64)*10**6;fr=np.array(d['funding_rate'],float);assert np.all(np.diff(ft)>0);fund[sym]=(ft,fr)
mt=market['BTC','execution'][0];assert all(np.array_equal(mt,x[0]) for x in market.values())
def px(sym,kind,t):
 i=int((t-int(mt[0]))//M);assert 0<=i<len(mt) and int(mt[i])==t,('MISSING_COMPLETED_PRICE',sym,t)
 return float(market[sym,kind][1][i])
actions=[];cashrows=[];minuteplans={};unknown=[];needed=set()
for cy,(f,Q,e) in selected.items():
 s=int(f['side']);qb=float(abs(Q));B=px('BTC','execution',e);S=px('SOL','execution',e);NB=qb*B;rho=float(f['lag720_rho']);beta=float(f['lag720_betaSOLgivenBTC']);NS=.5*NB*float(f['lag720_sigmaBTC'])/float(f['lag720_sigmaSOL']);qs=NS/S;qt=beta*NS/B
 assert 0<rho<=1+1e-12 and 0<qt<=qb*(1+1e-12) and math.isclose(qt/qb,.5*rho,rel_tol=1e-12)
 end=e+DAY;exitreason='SCHEDULED_RESTORE';reductions=[];adds=0
 for g in groups[bisect.bisect_right(gts,e):]:
  if g['t']>end:break
  if g['kind']=='add':adds+=1;continue
  assert g['before']*s>0
  reductions.append(g)
  if not g['after']:end=g['t'];exitreason='BTC_FLAT';break
 if end in bytime and exitreason=='SCHEDULED_RESTORE':unknown.append(dict(cycle=cy,reason='SCHEDULED_ENDPOINT_SAME_TIMESTAMP_BTC_FILL'));continue
 assert end>=e and end%M==0
 rows=[];helds=qs;heldt=qt
 def event(t,kind,ds,dt,pS,pB,nfee=0.,oid=''):
  rows.append(dict(cycle=cy,event_ns=t,event_utc=utc(t),event_kind=kind,delta_SOLqty=ds,delta_trimqty=dt,SOLexecution=pS,BTCexecution=pB,native_avoided_fee=nfee,native_order_id=oid))
 event(e,'ENTRY',qs,qt,S,B)
 reductionmap={}
 for g in reductions:
  ratio=float(abs(g['after'])/abs(g['before']));ds=helds*(1-ratio);dt=heldt*(1-ratio)
  actualtotal=sum(float(abs(x['dq'])) for x in g['fills']);assert math.isclose(actualtotal,float(abs(g['before'])-abs(g['after'])),abs_tol=1e-10)
  # Proportional allocation across simultaneous baseline exits is invariant to exit order.
  for x in g['fills']:
   share=float(abs(x['dq']))/actualtotal;allocateddt=dt*share;allocatedds=ds*share;avoidfee=x['fee']*allocateddt/float(abs(x['dq']))
   event(g['t'],'BASELINE_REDUCTION',-allocatedds,-allocateddt,px('SOL','execution',g['t']),x['px'],avoidfee,x['oid'])
  helds*=ratio;heldt*=ratio;reductionmap[g['t']]=ratio
 if helds>1e-10:
  assert exitreason=='SCHEDULED_RESTORE';event(end,'SCHEDULED_EXIT_RESTORE',-helds,-heldt,px('SOL','execution',end),px('BTC','execution',end));helds=heldt=0.
 assert abs(sum(r['delta_SOLqty'] for r in rows))<1e-8 and abs(sum(r['delta_trimqty'] for r in rows))<1e-8
 cashrows.extend(rows);tgrid=range(e,end+M,M);needed.update(tgrid);minuteplans[cy]=(f,e,end,s,NB,qs,qt,rows)
 actions.append(dict(cycle=cy,decision_ns=int(f['decision_ns']),execution_ns=e,execution_utc=utc(e),exit_ns=end,exit_utc=utc(end),exit_reason=exitreason,period='first_year' if e<Y else 'second_year',early=e<EARLY,side=s,NB_USDT=NB,observed_BTCqty=qb,initial_SOLqty=qs,initial_trimqty=qt,lag_rho=rho,lag_beta=beta,proportional_reduction_groups=len(reductions),BTC_add_groups_ignored=adds,crosses_year=e<Y<=end,initial_SOLnotional_USDT=NS,quantity_after_flat=0.))
assert not unknown,unknown
# Existing native settled trace supplies reference only, never a synthetic portfolio.
equities={};qcheck=0;entries={e:cy for cy,(_,e,*_) in minuteplans.items()}
with gzip.open(tracep,'rt') as ff:
 for z in csv.DictReader(ff):
  t=int(z['source_quote_ns'])
  if t not in needed:continue
  eq=float(z['paired_close_equity']);assert math.isfinite(eq);equities[t]=eq
  if t in entries:
   qty=sum((D(p['quantity'])*(1 if str(p['side'])=='2' else -1) for p in json.loads(z['native_positions_and_mark_ohlc_json']) if p['instrument_id'].startswith('BTC')),D(0));cy=entries[t];assert qty==selected[cy][1],('NATIVE_ENTRY_STATE_MISMATCH',cy,qty,selected[cy][1]);qcheck+=1
assert len(equities)==len(needed) and qcheck==len(actions)
# Only two fixed funding boundary alternatives and the two frozen slip assumptions.
resultrows=[];minuterows=[]
for cy,(f,e,end,s,NB,qs0,qt0,evs) in minuteplans.items():
 evmap=collections.defaultdict(list)
 for ev in evs:evmap[ev['event_ns']].append(ev)
 for slipbp in [0.,2.]:
  for boundary in ['BEFORE_REDUCTION','AFTER_REDUCTION']:
   cs=ct=0.;hs=ht=0.;fundS=fundB=feeS=feeT=avoidFees=slipS=slipT=0.;minbase=0.;minsol=0.;mintrim=0.;E0=equities[e];fundties=0
   flookup={}
   for sym in ['BTC','SOL']:
    ft,fr=fund[sym];inds=np.where((ft>=e)&(ft<=end))[0]
    for i in inds:flookup.setdefault(int(ft[i]),{})[sym]=float(fr[i])
   def funding(t):
    global_dummy=None
    return (s*hs*px('SOL','mark',t)*flookup[t].get('SOL',0.),s*ht*px('BTC','mark',t)*flookup[t].get('BTC',0.))
   for t in range(e,end+M,M):
    if t in flookup and t in evmap:fundties+=1
    if t in flookup and boundary=='BEFORE_REDUCTION':
     fs,fb=funding(t);cs+=fs;ct+=fb;fundS+=fs;fundB+=fb
    for ev in evmap[t]:
     ds=ev['delta_SOLqty'];dt=ev['delta_trimqty'];pS=ev['SOLexecution'];pB=ev['BTCexecution'];nsnot=abs(ds)*pS;ntnot=abs(dt)*pB
     sf=F*nsnot;ss=slipbp/10000*nsnot;cs+=s*ds*pS-sf-ss;feeS+=sf;slipS+=ss;hs+=ds
     tf=F*ntnot if ev['event_kind']!='BASELINE_REDUCTION' else 0.;st=slipbp/10000*ntnot if ev['event_kind']!='BASELINE_REDUCTION' else 0.;ct+=s*dt*pB-tf-st+ev['native_avoided_fee'];feeT+=tf;slipT+=st;avoidFees+=ev['native_avoided_fee'];ht+=dt
    if t in flookup and boundary=='AFTER_REDUCTION':
     fs,fb=funding(t);cs+=fs;ct+=fb;fundS+=fs;fundB+=fb
    assert hs>=-1e-8 and ht>=-1e-8
    incS=cs-s*hs*px('SOL','mark',t);incT=ct-s*ht*px('BTC','mark',t);base=(equities[t]-E0)/NB;sol=base+incS/NB;trim=base+incT/NB;minbase=min(minbase,base);minsol=min(minsol,sol);mintrim=min(mintrim,trim)
    minuterows.append(dict(cycle=cy,slip_bp=slipbp,funding_boundary=boundary,mark_ns=t,baseline_equity=equities[t],entry_baseline_equity=E0,NB_USDT=NB,SOL_qty=hs,trim_qty=ht,SOL_cash=cs,trim_cash=ct,SOL_incremental_marked=incS,trim_incremental_marked=incT,baseline_change_NB=base,with_SOL_change_NB=sol,with_trim_change_NB=trim))
   assert abs(hs)<1e-8 and abs(ht)<1e-8
   a=next(x for x in actions if x['cycle']==cy)
   resultrows.append(dict(**a,slip_bp=slipbp,funding_boundary=boundary,SOL_net_USDT=cs,trim_net_USDT=ct,SOL_net_bp=cs/NB*10000,trim_net_bp=ct/NB*10000,SOL_minus_trim_bp=(cs-ct)/NB*10000,SOL_fees_USDT=feeS,trim_fees_USDT=feeT,avoided_native_fees_USDT=avoidFees,SOL_slip_USDT=slipS,trim_slip_USDT=slipT,SOL_funding_USDT=fundS,trim_avoided_funding_USDT=fundB,funding_reduction_ties=fundties,baseline_local_worst_bp=minbase*10000,with_SOL_local_worst_bp=minsol*10000,with_trim_local_worst_bp=mintrim*10000,SOL_protection_delta_bp=(minsol-minbase)*10000))
write('screen-entry-attempts.csv',attempts);write('screen-cashflows.csv',cashrows);write('screen-actions.csv',resultrows);write('screen-minute-reference.csv',minuterows)
cohorts=[]
for cohort in ['first_year','second_year','early']:
 for slip in [0.,2.]:
  for boundary in ['BEFORE_REDUCTION','AFTER_REDUCTION']:
   z=[r for r in resultrows if r['slip_bp']==slip and r['funding_boundary']==boundary and ((r['early']) if cohort=='early' else r['period']==cohort)];assert z
   n=len(z);avg=lambda k:sum(r[k] for r in z)/n
   cohorts.append(dict(cohort=cohort,slip_bp=slip,funding_boundary=boundary,episodes=n,long_episodes=sum(r['side']==1 for r in z),short_episodes=sum(r['side']==-1 for r in z),min_required=3 if cohort=='early' else 10,mean_SOL_net_bp=avg('SOL_net_bp'),mean_trim_net_bp=avg('trim_net_bp'),mean_SOL_minus_trim_bp=avg('SOL_minus_trim_bp'),mean_baseline_local_worst_bp=avg('baseline_local_worst_bp'),mean_with_SOL_local_worst_bp=avg('with_SOL_local_worst_bp'),mean_SOL_protection_delta_bp=avg('SOL_protection_delta_bp'),descriptive_sum_SOL_USDT=sum(r['SOL_net_USDT'] for r in z),descriptive_sum_trim_USDT=sum(r['trim_net_USDT'] for r in z),SOL_positive_episodes=sum(r['SOL_net_bp']>0 for r in z),trim_advantage_positive_episodes=sum(r['SOL_minus_trim_bp']>0 for r in z)))
write('screen-cohorts.csv',cohorts)
small=any(r['episodes']<r['min_required'] for r in cohorts);fails=[]
for r in cohorts:
 for metric,gate in [('mean_SOL_net_bp','STOP_CAPITAL'),('mean_SOL_minus_trim_bp','STOP_TRIM_DOMINATES'),('mean_SOL_protection_delta_bp','STOP_PROTECTION')]:
  if r[metric]<(0 if gate=='STOP_PROTECTION' else 1e-14):fails.append(dict(cohort=r['cohort'],slip_bp=r['slip_bp'],funding_boundary=r['funding_boundary'],gate=gate,value=r[metric]))
status='INCONCLUSIVE_SMALL_SAMPLE' if small else ('STOP' if fails else 'LOCAL_SIGNAL_SUPPORTED')
res=dict(task='CM-EARLY-HEDGE-20261024',hypothesis='H_RESIDUAL_CONTINUATION',status=status,accounting_verification='PENDING_ONE_INDEPENDENT_PASS',frozen_protocol_sha256=hashlib.sha256((R/'PROTOCOL_PREDECLARED.md').read_bytes()).hexdigest(),trigger_states=len(trig),selected_episodes=len(actions),entry_attempt_reasons=dict(collections.Counter(x['status'] for x in attempts)),native_BTC_fills=len(fills),native_BTC_episodes=cycle,baseline_native_entry_quantity_checks=qcheck,NO_FEATURE_HISTORY_September_cycles=4,funding_boundary_tied_episodes=len({r['cycle'] for r in resultrows if r['funding_reduction_ties']}),proportional_reduction_groups=sum(x['proportional_reduction_groups'] for x in actions),ignored_BTC_add_groups=sum(x['BTC_add_groups_ignored'] for x in actions),all_SOL_closed_at_or_before_first_BTCflat=True,cohorts=cohorts,failed_gates=fails,source_sha256=led['input_sha256'],calculation_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),outcome_files_reused=0,engine_runs=0,limitations=['Local conditional actualR3 cashflow screen; no counterfactualTOTAL/DD/ROI or E4 capital restoration.','Continuous diagnostic quantities and raw completed1m execution/mark references; no lot/margin/queue/L2/capacity/native3TP guarantee.','Actual native settled equity by source_quote_ns; receipt_ns is delayed60s. This is saved settled reference, not executable event equity or intraminute protection.','Partial-reduction ties use native fills/fees pro rata; funding boundary before/after fixed alternatives, every gate must survive both.','No re-add; BTC adds do not increase diagnostic hedge/trim, so mandatory coverage of all future BTC is unproven.','First4SeptemberR3cycles absent due720H1history; earlycohort is partial.','Already viewed R3 history, no freshOOS.2bp fixed stress is not capacity proof.'])
(R/'screen-result.json').write_text(json.dumps(res,indent=2)+'\n');led.update(status='OUTCOME_CALCULATION_COMPLETE_VERIFICATION_PENDING',logical_outcome_screens_completed=1,outcome_pass_completed_utc=datetime.now(timezone.utc).isoformat(),result=status,output_sha256={str(R/p):hashlib.sha256((R/p).read_bytes()).hexdigest() for p in ['screen-actions.csv','screen-cohorts.csv','screen-cashflows.csv','screen-minute-reference.csv','screen-result.json']});L.write_text(json.dumps(led,indent=2)+'\n')
print(json.dumps({k:res[k] for k in ['status','selected_episodes','entry_attempt_reasons','funding_boundary_tied_episodes','proportional_reduction_groups','ignored_BTC_add_groups','cohorts']},indent=2))
