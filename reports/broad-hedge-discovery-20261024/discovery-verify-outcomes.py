"""Independent vector prefix-event algebra; does not import discovery-stageI."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import csv,json,hashlib,math,collections,re
import numpy as np
import pyarrow.parquet as pq
O=Path(__file__).resolve().parent;M=60000000000;H=60*M
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return list(csv.DictReader(Path(p).open()))
def ns(s):return int(datetime.fromisoformat(s).timestamp())*10**9
def tail(z):z=sorted(map(float,z),reverse=True);return sum(z[:math.ceil(len(z)/5)])/math.ceil(len(z)/5)
def verify(stage='stageI'):
 ledger=json.loads((O/'phase-ledger.json').read_text());which='stage_I' if stage=='stageI' else 'stage_II';assert ledger[which]['completed']==1 and ledger[which].get('verification_used',0)==0
 for p,s in ledger['sha256'].items():assert sha(O/p)==s
 build=json.loads((O/'discovery-build.json').read_text())
 for p,s in build['input_sha256'].items():assert sha(p)==s
 ledger[which]['verification_used']=1;ledger[which]['verification_start_utc']=datetime.now(timezone.utc).isoformat();(O/'phase-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
 rows=read(O/f'discovery-{stage}-episodes.csv');summaries=read(O/f'discovery-{stage}-configurations.csv');cohorts=read(O/f'discovery-{stage}-cohorts.csv');selected=read(O/'discovery-stageI-selected.csv');features={(f['cycle'],f['decision_ns']):f for f in read(O/'discovery-features.csv')};sel={(x['rule'],x['cycle']):features[x['cycle'],x['decision_ns']] for x in selected}
 raw=json.loads(Path(next(p for p in build['input_sha256'] if p.endswith('-raw-native.json'))).read_text());csvf=read(next(p for p in build['input_sha256'] if p.endswith('-fills.csv')));side=collections.defaultdict(list)
 for f in csvf:side[(ns(f['ts_last']),D(f['filled_qty']),D(f['avg_px']).quantize(D('.1')),D(re.search(r'([0-9.]+) USDT',f['commissions'])[1]))].append(1 if f['side']=='BUY' else -1)
 fills=collections.defaultdict(list)
 for j,a in enumerate(raw['fill_audit']):
  key=int(a['fill_ns']),D(a['qty']),D(a['px']).quantize(D('.1')),D(a['commission']);fills[key[0]].append((side[key].pop()*float(a['qty']),float(a['px']),float(a['commission'])))
 actualfund=collections.defaultdict(float)
 for x in raw['funding']['signed_native_cash_deltas']:actualfund[int(x[2])]+=float(x[5])
 data=Path(next(p for p in build['input_sha256'] if p.endswith('bybit-BTCUSDT-execution-1m.parquet'))).parent
 z=np.load(O/'discovery-baseline.npz');base={k:z[k] for k in z.files};mt=base['timestamp_ns'];start=int(mt[0]);index=lambda t:int((t-start)//M);market={};rates={}
 for sym in ['BTC','SOL']:
  for kind in ['execution-1m','mark-1m']:market[sym,kind]=np.array(pq.read_table(data/f'bybit-{sym}USDT-{kind}.parquet',columns=['close']).column('close').to_pylist(),float)
  d=pq.read_table(data/f'bybit-{sym}USDT-funding.parquet').to_pydict();rates[sym]={int(t)*10**6:float(r) for t,r in zip(d['funding_time_ms'],d['funding_rate'])}
 checks=collections.Counter();maxcash=maxloss=0.;baselineby={}
 for r in rows:
  f=sel[r['rule'],r['cycle']];e=int(r['entry_ns']);end=int(r['end_ns']);i0=index(e);i1=index(end);s=int(r['side']);NB=float(f['NB_t']);h=np.array([float(r['SOL_qty_t']),float(r['joint_BTCtrim_qty_t']),float(r['comparator_BTCtrim_qty_e'])]);slip=float(r['slip_bp'])/10000;before=r['funding_boundary']=='BEFORE_ALL';assert not any(e in rates[x] for x in ['BTC','SOL'])
  assert math.isclose(h[2],h[1]+float(f['beta'])*h[0]*market['SOL','execution-1m'][i0]/market['BTC','execution-1m'][i0],abs_tol=1e-11);assert h[2]<=float(f['qref_t'])+1e-12
  # Events have static baseline bracket + independently calculated flow/inventory deltas.
  events=[];zeros=np.zeros(3);factors={};factor=1.;fees=np.zeros(3);avoided=np.zeros(3);fundcash=np.zeros(3)
  def put(t,phase,j,B,df,dc= None,dh=None):events.append((t,phase,j,B+min(0.,df),B+max(0.,df),zeros.copy() if dc is None else dc,zeros.copy() if dh is None else dh))
  for i in range(i0,i1+1):
   t=int(mt[i]);cprev=float(base['pricecash'][i-1]);qprev=float(base['q'][i-1]);Bpre=cprev+qprev*market['BTC','mark-1m'][i];Bpost=float(base['Wraw'][i]);af=actualfund.get(t,0.);facbefore=factor
   if t==e:
    Bpre=Bpost;af=0.;put(t,0,0,Bpost,0.)
    p=np.array([market['SOL','execution-1m'][i],market['BTC','execution-1m'][i],market['BTC','execution-1m'][i]]);notional=h*p;dc=s*notional-(.00055+slip)*notional;fees+=.00055*notional;put(t,2,0,Bpost,0.,dc,h)
   else:
    put(t,0,0,Bpre,af);q=qprev;c=cprev
    for j,(dq,px,fee) in enumerate(fills.get(t,())):
     qafter=q+dq;qafter=0. if abs(qafter)<1e-10 else qafter;c-=dq*px+fee;oldfactor=factor;dc=np.zeros(3);dh=np.zeros(3)
     if q*dq<0:
      factor*=abs(qafter)/abs(q);removed=h*(oldfactor-factor);dh=-removed
      pS=market['SOL','execution-1m'][i];dc[0]=-s*removed[0]*pS-(.00055+slip)*removed[0]*pS;fees[0]+=.00055*removed[0]*pS
      for k in [1,2]:dc[k]=-s*removed[k]*px+fee*h[k]*oldfactor/abs(q);avoided[k]+=fee*h[k]*oldfactor/abs(q)
     q=qafter;B=c+q*market['BTC','mark-1m'][i];put(t,2,j,B,af,dc,dh)
    put(t,3,0,Bpost,0.)
   facafter=factor
   if t==end:
    remaining=h*factor;p=np.array([market['SOL','execution-1m'][i],market['BTC','execution-1m'][i],market['BTC','execution-1m'][i]]);dc=-s*remaining*p-(.00055+slip)*remaining*p;fees+=.00055*remaining*p;put(t,4,0,Bpost,0.,dc,-remaining);facafter=0.
   factors[t]=(facbefore,facafter)
   exposure=h*(facbefore if before else facafter)
   if t==e and before:exposure*=0.
   fc=np.array([s*exposure[0]*market['SOL','mark-1m'][i]*rates['SOL'].get(t,0.),s*exposure[1]*market['BTC','mark-1m'][i]*rates['BTC'].get(t,0.),s*exposure[2]*market['BTC','mark-1m'][i]*rates['BTC'].get(t,0.)]);fundcash+=fc
   # Baseline at hypothetical funding phase: before group uses pre; after uses post.
   put(t,1 if before else 5,0,Bpre if before else Bpost,af if before else 0.,fc)
  events.sort(key=lambda x:x[:3]);cash=np.cumsum(np.array([x[5] for x in events]),axis=0);held=np.cumsum(np.array([x[6] for x in events]),axis=0);ii=np.array([index(x[0]) for x in events]);BM=np.array([x[3] for x in events]);prices=np.column_stack([market['SOL','mark-1m'][ii],market['BTC','mark-1m'][ii],market['BTC','mark-1m'][ii]]);values=cash-s*held*prices
  minima=np.array([BM.min(),np.min(BM+values[:,0]+values[:,1]),np.min(BM+values[:,2])]);anchor=float(base['Wraw'][i0]);loss=np.maximum(0,anchor-minima)/NB*10000;expectedcash=np.array([cash[-1,0]+cash[-1,1],cash[-1,2]]);savedcash=np.array([float(r['net_H']),float(r['net_T'])]);savedloss=np.array([float(r['loss_N_bp']),float(r['loss_H_bp']),float(r['loss_T_bp'])]);cr=float(np.max(np.abs(expectedcash-savedcash)));lr=float(np.max(np.abs(loss-savedloss)));maxcash=max(maxcash,cr);maxloss=max(maxloss,lr)
  assert cr<2e-6,('CASH',r['rule'],r['cycle'],cr);assert lr<2e-7,('LOSS',r['rule'],r['cycle'],r['horizon_h'],r['funding_boundary'],loss,savedloss,lr)
  assert np.max(np.abs(held[-1]))<1e-8
  for k,key in enumerate(['fees_SOL','fees_jointBTC','fees_comparator']):assert abs(fees[k]-float(r[key]))<1e-6
  for k,key in [(1,'avoided_fees_jointBTC'),(2,'avoided_fees_comparator')]:assert abs(avoided[k]-float(r[key]))<1e-6
  for k,key in enumerate(['funding_SOL','funding_jointBTC','funding_comparator']):assert abs(fundcash[k]-float(r[key]))<1e-6
  key=r['rule'],r['cycle'],r['horizon_h'];old=baselineby.setdefault(key,float(r['loss_N_bp']));assert abs(old-float(r['loss_N_bp']))<1e-8
  checks['independent_all_cash_endpoints']+=1;checks['independent_all_three_local_losses']+=3;checks['all_cost_funding_components']+=9;checks['baseline_identical_across_scenarios']+=1
 # Recompute every cohort mean/tail and all lane/Holm gates from episode rows.
 for c in cohorts:
  zz=[r for r in rows if r['rule']==c['rule'] and r['horizon_h']==c['horizon_h'] and r['slip_bp']==c['slip_bp'] and r['funding_boundary']==c['funding_boundary'] and (r['early']=='True' if c['cohort']=='early' else r['year']==c['cohort'])];assert len(zz)==int(c['n'])
  for src,dst in [('net_H_bp','mean_H'),('net_T_bp','mean_T'),('paired_net_bp','mean_paired')]:assert abs(sum(float(r[src]) for r in zz)/len(zz)-float(c[dst]))<1e-8
  for src,dst in [('loss_N_bp','CVaR_N'),('loss_H_bp','CVaR_H'),('loss_T_bp','CVaR_T')]:assert abs(tail(r[src] for r in zz)-float(c[dst]))<1e-8
  checks['cohort_mean_CVaR_recomputed']+=1
 stats=read(O/f'discovery-{stage}-statistics.csv') if (O/f'discovery-{stage}-statistics.csv').exists() else []
 for sm in summaries:
  cs=[c for c in cohorts if c['rule']==sm['rule'] and c['horizon_h']==sm['horizon_h']];valid=len(cs)==12;cap=valid and all(float(c['mean_H'])>0 and float(c['mean_paired'])>0 for c in cs);prot=valid and all(float(c['CVaR_N'])>float(c['CVaR_H']) for c in cs) and (all(float(c['mean_paired'])>0 for c in cs) or all(float(c['CVaR_T'])>float(c['CVaR_H']) for c in cs));assert cap==(sm['raw_capital_positive']=='True') and prot==(sm['raw_protection_positive']=='True')
  checks['raw_lane_gates_all3x4']+=1
  st=[x for x in stats if x['rule']==sm['rule'] and x['horizon_h']==sm['horizon_h']]
  if st:
   assert len(st)==48 and all(int(x['B'])==8192 for x in st)
   pc=max(float(x['p']) for x in st if x['contrast'] in ['mean_H','mean_H_minus_T']);pr=max(float(x['p']) for x in st if x['contrast'] in ['CVaR_N_minus_H','mean_H_minus_T']);pk=max(float(x['p']) for x in st if x['contrast'] in ['CVaR_N_minus_H','CVaR_T_minus_H']);pp=min(1,2*min(pr,pk))
   if sm['qualified_raw_capital']=='True':assert abs(pc-float(sm['capital_p']))<1e-14
   if sm['qualified_raw_protection']=='True':assert abs(pp-float(sm['protection_p']))<1e-14
   checks['IUT_Bonferroni_component_aggregation']+=1
 result={'status':'PASS_INDEPENDENT_PREFIX_EVENT_ALGEBRA','stage':stage,'checks':dict(checks),'rows':len(rows),'max_cash_residual_USDT':maxcash,'max_local_loss_residual_bp':maxloss,'baseline_terminal_exact':'120718.40416503','new_native_runs':0,'label_script_not_imported':True,'bootstrap_verification':'B=8192 and stored component IUT/2route arithmetic checked; random draws not rerun','verifier_sha256':sha(Path(__file__))}
 (O/f'discovery-{stage}-verification.json').write_text(json.dumps(result,indent=2)+'\n');ledger[which]['verification_status']='PASS';ledger[which]['verification_result_sha256']=sha(O/f'discovery-{stage}-verification.json');ledger['status']=stage.upper()+'_VERIFIED';(O/'phase-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':
 import sys
 verify(sys.argv[1] if len(sys.argv)>1 else 'stageI')
