"""Frozen 32 saved-data configurations; observed attribution, never native execution."""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D
import csv,json,hashlib,collections,math,re,traceback
import numpy as np
import pyarrow.parquet as pq
O=Path(__file__).resolve().parent;ROOT=O.parents[1];M=60000000000;H=60*M;DAY=24*H;FEE=.00055
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
utc=lambda t:datetime.fromtimestamp(t/1e9,timezone.utc).isoformat()
def ns(s):return int(datetime.fromisoformat(s).timestamp())*10**9
def read(p):return list(csv.DictReader(Path(p).open()))
def dump(name,rows):
 if not rows:return
 with (O/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def load():
 ledger=json.loads((O/'phase-ledger.json').read_text());assert ledger['stage_I']['started']==0 and ledger['stage_I']['completed']==0
 for p,s in ledger['sha256'].items():assert sha(O/p)==s,('FROZEN_INPUT_CHANGED',p)
 build=json.loads((O/'discovery-build.json').read_text())
 for p,s in build['input_sha256'].items():assert sha(p)==s,('SOURCE_CHANGED',p)
 # Start is durable BEFORE any newly labelled outcome.
 ledger['stage_I']['started']=1;ledger['stage_I']['start_utc']=datetime.now(timezone.utc).isoformat();ledger['stage_I']['label_script_sha256']=sha(Path(__file__));ledger['status']='STAGE_I_RUNNING';ledger['candidate_outcomes']='AUTHORIZED_AFTER_VERIFIED_FREEZE'
 (O/'phase-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
 z=np.load(O/'discovery-baseline.npz');baseline={k:z[k] for k in z.files};mt=baseline['timestamp_ns'];start=int(mt[0]);ix=lambda t:int((t-start)//M)
 data=Path(next(p for p in build['input_sha256'] if p.endswith('bybit-BTCUSDT-execution-1m.parquet'))).parent
 market={};rates={}
 for sym in ['BTC','SOL']:
  for kind in ['execution-1m','mark-1m']:
   d=pq.read_table(data/f'bybit-{sym}USDT-{kind}.parquet',columns=['open_time_ms','close']).to_pydict();assert np.array_equal(np.array(d['open_time_ms'],np.int64)*10**6+M,mt);market[sym,kind]=np.array(d['close'],float)
  d=pq.read_table(data/f'bybit-{sym}USDT-funding.parquet').to_pydict();rates[sym]={int(t)*10**6:float(r) for t,r in zip(d['funding_time_ms'],d['funding_rate'])}
 raw=json.loads(Path(next(p for p in build['input_sha256'] if p.endswith('-raw-native.json'))).read_text());fillscsv=read(next(p for p in build['input_sha256'] if p.endswith('-fills.csv')));side=collections.defaultdict(list)
 for f in fillscsv:side[(ns(f['ts_last']),D(f['filled_qty']),D(f['avg_px']).quantize(D('.1')),D(re.search(r'([0-9.]+) USDT',f['commissions'])[1]))].append(1 if f['side']=='BUY' else -1)
 fills=collections.defaultdict(list)
 for j,a in enumerate(raw['fill_audit']):
  t=int(a['fill_ns']);key=t,D(a['qty']),D(a['px']).quantize(D('.1')),D(a['commission']);sg=side[key].pop();fills[t].append(dict(dq=sg*float(a['qty']),px=float(a['px']),fee=float(a['commission']),index=j))
 funds=collections.defaultdict(float)
 for a in raw['funding']['signed_native_cash_deltas']:funds[int(a[2])]+=float(a[5])
 return ledger,build,baseline,mt,ix,market,rates,fills,funds

def action_path(f,hours,slip,boundary,baseline,mt,ix,market,rates,fills,funds,cycle):
 e=int(f['entry_reference_ns']);end=min(e+hours*H,int(cycle['actual_flat_ns']));assert end>=e and end<=int(mt[-1]);i0=ix(e);i1=ix(end);s=int(f['side']);NB=float(f['NB_t']);qref=float(f['qref_t']);rule=f['rule']
 hs=float(f['J2_qSOL_t'] if rule=='J2' else f['standard_qSOL_t']);hj=float(f['J2_qBTCtrim_t']) if rule=='J2' else 0.
 pb=market['BTC','execution-1m'][i0];ps=market['SOL','execution-1m'][i0];ht=hj+float(f['beta'])*hs*ps/pb
 if ht>qref+1e-12:return None,'UNKNOWN_COMPARATOR_CAP'
 assert hs>=0 and hj>=0 and ht>=0 and hj<=qref+1e-12
 if any(e in rates[sym] for sym in ['BTC','SOL']):return None,'UNKNOWN_ENTRY_FUNDING'
 qbase=float(baseline['q'][i0]);cbase=float(baseline['pricecash'][i0]);assert math.isclose(qbase,s*qref,abs_tol=1e-12)
 # Component order S (SOL), J (joint BTC removal), T (equal-factor BTC removal).
 held=np.zeros(3);cash=np.zeros(3);fees=np.zeros(3);slips=np.zeros(3);avoid=np.zeros(3);funding=np.zeros(3)
 mn=np.full(3,np.inf);peak=np.full(3,-np.inf);maxdrop=np.zeros(3);anchor=None;pointcount=0;fundties=0;reductions=0;nativeavoidedchecks=0;pending_actualfund=0.
 def sample(i):
  nonlocal pointcount
  w=cbase+qbase*market['BTC','mark-1m'][i];vs=cash[0]-s*held[0]*market['SOL','mark-1m'][i];vj=cash[1]-s*held[1]*market['BTC','mark-1m'][i];vt=cash[2]-s*held[2]*market['BTC','mark-1m'][i]
  # Fixed baseline bracket at actual funding/native-fill ties, identical in all scenarios.
  for df in set([0.,pending_actualfund]):
   vals=np.array([w+df,w+df+vs+vj,w+df+vt]);mn[:]=np.minimum(mn,vals);peak[:]=np.maximum(peak,vals);maxdrop[:]=np.maximum(maxdrop,peak-vals);pointcount+=1
 def trade(k,delta,i,avoided=None):
  # Positive delta starts/increases opposite inventory; negative closes it.
  sym='SOL' if k==0 else 'BTC';p=market[sym,'execution-1m'][i]
  if avoided is None:
   notional=abs(delta)*p;cash[k]+=s*delta*p-FEE*notional-slip/10000*notional;fees[k]+=FEE*notional;slips[k]+=slip/10000*notional
  else:
   px,fee=avoided;cash[k]+=s*delta*px+fee;avoid[k]+=fee
  held[k]+=delta
 def apply_funding(t,i):
  nonlocal fundties
  for k,sym in [(0,'SOL'),(1,'BTC'),(2,'BTC')]:
   rate=rates[sym].get(t)
   if rate is not None:
    v=s*held[k]*market[sym,'mark-1m'][i]*rate;cash[k]+=v;funding[k]+=v
  if any(t in rates[sym] for sym in ['BTC','SOL']) and (t==e or t==end or t in fills):fundties+=1
 for i in range(i0,i1+1):
  t=int(mt[i]);entry=t==e;pending_actualfund=0. if entry else funds.get(t,0.)
  if not entry:sample(i)
  if boundary=='BEFORE_ALL':apply_funding(t,i)
  if entry:
   anchor=cbase+qbase*market['BTC','mark-1m'][i];sample(i)
   for k,h in enumerate([hs,hj,ht]):trade(k,h,i)
   sample(i)
  else:
   if boundary=='BEFORE_ALL':sample(i)
   for a in fills.get(t,()):
    before=qbase;after=before+a['dq'];after=0. if abs(after)<1e-10 else after;reducing=before*a['dq']<0
    cbase-=a['dq']*a['px']+a['fee'];qbase=after
    if reducing:
     ratio=max(0.,abs(after)/abs(before));assert -1e-12<=ratio<=1+1e-12;old=held.copy();dh=old*(1-ratio);trade(0,-dh[0],i)
     for k in [1,2]:
      fee=a['fee']*old[k]/abs(before);trade(k,-dh[k],i,(a['px'],fee));nativeavoidedchecks+=1
     reductions+=1
    else:assert before==0 or before*after>0
    sample(i)
  if not entry:
   # Actual baseline funding is fixed, independent of hypothetical exposure order.
   cbase+=funds.get(t,0.);pending_actualfund=0.;sample(i)
  if t==end:
   # Native flat reduction already closes all diagnostics. Otherwise scheduled close.
   for k in range(3):
    if held[k]>1e-12:trade(k,-held[k],i)
   sample(i)
  if boundary=='AFTER_ALL':apply_funding(t,i);sample(i)
  assert np.all(held>=-1e-9) and max(held[1],held[2])<=abs(qbase)+1e-8
 assert np.max(np.abs(held))<1e-8
 expected=float(baseline['Wraw'][i1]);observed=cbase+qbase*market['BTC','mark-1m'][i1];assert math.isclose(expected,observed,abs_tol=2e-6),('BASELINE_ENDPOINT',expected,observed)
 loss=np.maximum(0.,anchor-mn)/NB;netH=cash[0]+cash[1];netT=cash[2]
 return dict(rule=rule,horizon_h=hours,cycle=int(f['cycle']),decision_ns=int(f['decision_ns']),entry_ns=e,end_ns=end,entry_utc=utc(e),entry_month=utc(e)[:7],year='year1' if e<ns('2025-09-01T00:00:00+00:00') else 'year2',early=e<ns('2025-01-15T00:00:00+00:00'),side=s,NB_t=NB,slip_bp=slip,funding_boundary=boundary,SOL_qty_t=hs,joint_BTCtrim_qty_t=hj,comparator_BTCtrim_qty_e=ht,J2_tag=f['J2_tag'] if rule=='J2' else 'STANDARD_SOL',anchor_Wraw=anchor,baseline_end_Wraw=observed,net_H=netH,net_T=netT,net_SOL=cash[0],net_jointBTC=cash[1],net_H_bp=netH/NB*10000,net_T_bp=netT/NB*10000,paired_net_bp=(netH-netT)/NB*10000,loss_N_bp=loss[0]*10000,loss_H_bp=loss[1]*10000,loss_T_bp=loss[2]*10000,sampled_drop_N_bp=maxdrop[0]/NB*10000,sampled_drop_H_bp=maxdrop[1]/NB*10000,sampled_drop_T_bp=maxdrop[2]/NB*10000,fees_SOL=fees[0],fees_jointBTC=fees[1],fees_comparator=fees[2],slip_SOL=slips[0],slip_jointBTC=slips[1],slip_comparator=slips[2],avoided_fees_jointBTC=avoid[1],avoided_fees_comparator=avoid[2],funding_SOL=funding[0],funding_jointBTC=funding[1],funding_comparator=funding[2],funding_action_ties=fundties,native_reductions=reductions,native_avoided_fee_checks=nativeavoidedchecks,sampled_points=pointcount,terminal_kind='ACTUAL_FLAT' if end==int(cycle['actual_flat_ns']) else 'SCHEDULED_HELD',status='DESCRIPTIVE_IDEAL_SYNCHRONOUS_ATTRIBUTION'),None

def cvar(v):
 v=np.asarray(v,float);assert len(v);n=math.ceil(.2*len(v));return float(np.sort(v)[-n:].mean())
def metrics(z):
 return dict(n=len(z),longs=sum(r['side']==1 for r in z),shorts=sum(r['side']==-1 for r in z),mean_H=float(np.mean([r['net_H_bp'] for r in z])),mean_T=float(np.mean([r['net_T_bp'] for r in z])),mean_paired=float(np.mean([r['paired_net_bp'] for r in z])),CVaR_N=cvar([r['loss_N_bp'] for r in z]),CVaR_H=cvar([r['loss_H_bp'] for r in z]),CVaR_T=cvar([r['loss_T_bp'] for r in z]))
def contrasts(m):return np.array([m['mean_H'],m['mean_paired'],m['CVaR_N']-m['CVaR_H'],m['CVaR_T']-m['CVaR_H']])
COHORTS={'year1':[f'2024-{m:02}' for m in range(9,13)]+[f'2025-{m:02}' for m in range(1,9)],'year2':[f'2025-{m:02}' for m in range(9,13)]+[f'2026-{m:02}' for m in range(1,9)],'early':[f'2024-{m:02}' for m in range(9,13)]+['2025-01']}
def cohort(z,name):return [r for r in z if r['early']] if name=='early' else [r for r in z if r['year']==name]
def bootstrap(z,name,rng):
 months=COHORTS[name];blocks=[[r for r in z if r['entry_month']==mo] for mo in months];obs=contrasts(metrics(z));samples=[];attempts=0
 while len(samples)<8192 and attempts<65536:
  draw=rng.integers(0,len(months),size=len(months));zz=[r for j in draw for r in blocks[j]];attempts+=1
  if not zz:continue
  samples.append(contrasts(metrics(zz)))
 assert len(samples)==8192,('BOOTSTRAP_EMPTY_MAX',name)
 a=np.array(samples);p=(1+np.sum(a-obs>=obs,axis=0))/8193;ci=np.quantile(a,[.025,.975],axis=0)
 return p,ci,attempts

def analyze(rows,registry):
 summaries=[];tables=[];statrows=[];rng=np.random.default_rng(20261024)
 for reg in registry:
  rule=reg['rule']
  for h in [4,24]:
   zz=[r for r in rows if r['rule']==rule and r['horizon_h']==h];mm=[];valid=True;sparse=False
   for slip in [0,2]:
    for boundary in ['BEFORE_ALL','AFTER_ALL']:
     scenario=[r for r in zz if r['slip_bp']==slip and r['funding_boundary']==boundary]
     for name in COHORTS:
      z=cohort(scenario,name)
      if not z:valid=False;sparse=True;continue
      m=metrics(z);m.update(rule=rule,horizon_h=h,slip_bp=slip,funding_boundary=boundary,cohort=name);tables.append(m);mm.append(m);sparse|=m['n']<(3 if name=='early' else 10)
   capital=valid and all(m['mean_H']>0 and m['mean_paired']>0 for m in mm)
   protectionBase=valid and all(m['CVaR_N']>m['CVaR_H'] for m in mm)
   routeR=protectionBase and all(m['mean_paired']>0 for m in mm);routeK=protectionBase and all(m['CVaR_T']>m['CVaR_H'] for m in mm);protection=routeR or routeK
   # Admission as a SOL family additionally excludes no-SOL actions/control lanes.
   trueSOL=rule not in ['A0','C2'] and any(r['SOL_qty_t']>0 for r in zz)
   qualC=capital and not sparse and trueSOL;qualP=protection and not sparse and trueSOL
   pC=pP=1.;ci_status='NOT_TESTED_FAIL_OR_SPARSE'
   if (capital or protection) and not sparse and valid:
    components=[]
    for m in mm:
     scenario=[r for r in zz if r['slip_bp']==m['slip_bp'] and r['funding_boundary']==m['funding_boundary']];z=cohort(scenario,m['cohort']);p,ci,attempts=bootstrap(z,m['cohort'],rng);components.append(p)
     for j,key in enumerate(['mean_H','mean_H_minus_T','CVaR_N_minus_H','CVaR_T_minus_H']):statrows.append(dict(rule=rule,horizon_h=h,slip_bp=m['slip_bp'],funding_boundary=m['funding_boundary'],cohort=m['cohort'],contrast=key,p=float(p[j]),CI_low=float(ci[0,j]),CI_high=float(ci[1,j]),B=8192,draw_attempts=attempts))
    ps=np.array(components);pC=float(ps[:,:2].max());pReturn=float(ps[:,[2,1]].max());pRisk=float(ps[:,[2,3]].max());pP=min(1.,2*min(pReturn,pRisk));ci_status='BOOTSTRAP_APPROXIMATE_STATIONARY_MONTHS'
   main=[m for m in mm if m['cohort']!='early'];base=next((m for m in mm if m['cohort']=='year1' and m['slip_bp']==2 and m['funding_boundary']=='BEFORE_ALL'),None);second=next((m for m in mm if m['cohort']=='year2' and m['slip_bp']==2 and m['funding_boundary']=='BEFORE_ALL'),None);early=next((m for m in mm if m['cohort']=='early' and m['slip_bp']==2 and m['funding_boundary']=='BEFORE_ALL'),None)
   summary=dict(rule=rule,family=reg['family'],horizon_h=h,episodes=len({r['cycle'] for r in zz}),no_action_episodes=83-len({r['cycle'] for r in zz}),year1_n=base['n'] if base else 0,year2_n=second['n'] if second else 0,early_n=early['n'] if early else 0,raw_capital_positive=bool(capital),raw_protection_positive=bool(protection),consistent_route='RETURN_AND_RISK' if routeR and routeK else 'RETURN' if routeR else 'RISK' if routeK else 'NONE',sparse=bool(sparse),true_SOL_eligible=bool(trueSOL),qualified_raw_capital=bool(qualC),qualified_raw_protection=bool(qualP),capital_p=pC if qualC else 1.,protection_p=pP if qualP else 1.,statistics=ci_status,min_main_paired_mean=min((m['mean_paired'] for m in main),default=None),min_main_CVaR_gain=min((m['CVaR_N']-m['CVaR_H'] for m in main),default=None),min_main_CVaR_vs_trim_gain=min((m['CVaR_T']-m['CVaR_H'] for m in main),default=None))
   for name,m in [('year1',base),('year2',second),('early',early)]:
    for key in ['mean_H','mean_T','mean_paired','CVaR_N','CVaR_H','CVaR_T']:summary[name+'_'+key]=m[key] if m else None
   summaries.append(summary)
 # All 128 potential tests retained; untested future horizons/invalids are p=1.
 tests=[(i,l,float(s[l+'_p'])) for i,s in enumerate(summaries) for l in ['capital','protection']]+[(None,None,1.)]*64;order=sorted(range(128),key=lambda j:tests[j][2]);last=0.
 for rank,j in enumerate(order):
  i,l,p=tests[j];last=max(last,min(1.,(128-rank)*p))
  if i is not None:summaries[i][l+'_Holm128']=last
 for s in summaries:s['capital_confirmed']=s['qualified_raw_capital'] and s['capital_Holm128']<=.05;s['protection_confirmed']=s['qualified_raw_protection'] and s['protection_Holm128']<=.05
 return summaries,tables,statrows

def main():
 ledger,build,baseline,mt,ix,market,rates,fills,funds=load();features=read(O/'discovery-features.csv');registry=read(O/'discovery-registry.csv');cycles={int(c['cycle']):c for c in read(O/'discovery-actual-cycles.csv')};rows=[];attempts=[];selection=[]
 entryties=sum(any(int(f['entry_reference_ns']) in rates[sym] for sym in ['BTC','SOL']) for f in features)
 assert len(registry)==16 and len({r['rule'] for r in registry})==16
 for reg in registry:
  rule=reg['rule'];selected={}
  for f0 in features:
   cy=int(f0['cycle'])
   if cy in selected or f0['signal_'+rule]!='1':continue
   f=dict(f0,rule=rule)
   if f['common_valid']!='True':attempts.append(dict(rule=rule,cycle=cy,decision_ns=f['decision_ns'],status='UNKNOWN_T_OR_E_FILL_POSITION_OR_FEATURE'));continue
   e=int(f['entry_reference_ns']);i=ix(e);hs=float(f['J2_qSOL_t'] if rule=='J2' else f['standard_qSOL_t']);hj=float(f['J2_qBTCtrim_t']) if rule=='J2' else 0.;ht=hj+float(f['beta'])*hs*market['SOL','execution-1m'][i]/market['BTC','execution-1m'][i]
   if any(e in rates[sym] for sym in ['BTC','SOL']):attempts.append(dict(rule=rule,cycle=cy,decision_ns=f['decision_ns'],status='UNKNOWN_ENTRY_FUNDING'));continue
   if ht>float(f['qref_t'])+1e-12:attempts.append(dict(rule=rule,cycle=cy,decision_ns=f['decision_ns'],status='UNKNOWN_COMPARATOR_CAP'));continue
   selected[cy]=f;selection.append(dict(rule=rule,cycle=cy,decision_ns=f['decision_ns'],entry_ns=f['entry_reference_ns'],qref_t=f['qref_t'],SOL_qty_t=hs,joint_trim_t=hj,comparator_trim_e=ht,status='FIRST_VALID_SELECTED'))
  for cy,f in selected.items():
   for h in [4,24]:
    for slip in [0,2]:
     for boundary in ['BEFORE_ALL','AFTER_ALL']:
      row,error=action_path(f,h,slip,boundary,baseline,mt,ix,market,rates,fills,funds,cycles[cy]);assert error is None;rows.append(row)
 summaries,tables,stats=analyze(rows,registry);dump('discovery-stageI-episodes.csv',rows);dump('discovery-stageI-cohorts.csv',tables);dump('discovery-stageI-configurations.csv',summaries);dump('discovery-stageI-statistics.csv',stats);dump('discovery-stageI-entry-attempts.csv',attempts);dump('discovery-stageI-selected.csv',selection)
 result={'status':'STAGE_I_COMPLETE_PENDING_CONNECTED_VERIFICATION','configurations':32,'rows':len(rows),'raw_capital_positive':[s['rule']+':'+str(s['horizon_h']) for s in summaries if s['raw_capital_positive']],'raw_protection_positive':[s['rule']+':'+str(s['horizon_h']) for s in summaries if s['raw_protection_positive']],'qualified_raw_capital':[s['rule']+':'+str(s['horizon_h']) for s in summaries if s['qualified_raw_capital']],'qualified_raw_protection':[s['rule']+':'+str(s['horizon_h']) for s in summaries if s['qualified_raw_protection']],'confirmed_capital':[s['rule']+':'+str(s['horizon_h']) for s in summaries if s['capital_confirmed']],'confirmed_protection':[s['rule']+':'+str(s['horizon_h']) for s in summaries if s['protection_confirmed']],'stage_II_selection':'PENDING_ROOT_REVIEW_OF_FROZEN_RANKING' if any(s['qualified_raw_capital'] or s['qualified_raw_protection'] for s in summaries) else 'NONE_NO_QUALIFIED_RAW_POSITIVE','baseline_terminal':'120718.40416503','baseline_funding':'4063.32156049','funding_entry_anchor':'Fixed actual baseline after all actual flows at e; hypothetical BEFORE/AFTER exposure only; entry funding tie UNKNOWN','entry_funding_calendar_tied_states':entryties,'limitations':['Observed-fill raw-mark local attribution only, not candidate capital/native wallet/global DD/retention.','Ideal synchronous reduction pairing is optimistic; native latency/3TP/margin/capacity/pending risk UNKNOWN.','Same-time baseline native fill audit order retained; funding before/after ALL are coherent fixed alternatives, not all mixed orders.','Already viewed history; monthly cluster statistics approximate, not OOS.'],'physical_engine_runs':0,'script_sha256':sha(Path(__file__)),'output_sha256':{p.name:sha(p) for p in O.glob('discovery-stageI-*.csv')}}
 (O/'discovery-stageI-result.json').write_text(json.dumps(result,indent=2)+'\n');ledger['stage_I']['completed']=1;ledger['stage_I']['completed_utc']=datetime.now(timezone.utc).isoformat();ledger['stage_I']['configurations_evaluated']=32;ledger['stage_I']['result_sha256']=sha(O/'discovery-stageI-result.json');ledger['status']='STAGE_I_COMPLETE_PENDING_VERIFICATION';(O/'phase-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':
 try:main()
 except Exception:
  failure=traceback.format_exc();(O/'discovery-stageI-initial-failure.txt').write_text(failure);raise
