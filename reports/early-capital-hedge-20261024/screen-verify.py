"""One independent Decimal cash/quantity/funding verification of frozen screen."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from datetime import datetime
import csv,json,collections,hashlib,math
import pyarrow.parquet as pq
getcontext().prec=50
R=Path(__file__).resolve().parent;led=json.loads((R/'screen-ledger.json').read_text());assert led['logical_outcome_screens_completed']==1 and not led.get('arithmetic_verifications_started',0)
led['arithmetic_verifications_started']=1;led['verification_script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();(R/'screen-ledger.json').write_text(json.dumps(led,indent=2)+'\n')
def read(p):return list(csv.DictReader(Path(p).open()))
nativefills=read(next(p for p in led['input_sha256'] if p.endswith('fills.csv')));native_byid={x['client_order_id']:x for x in nativefills}
actions=read(R/'screen-actions.csv');events=read(R/'screen-cashflows.csv');features=read(R/'feature-contract-features.csv');F=D('.00055');M=60000000000
checks=collections.Counter();bycy=collections.defaultdict(list)
for x in events:bycy[int(x['cycle'])].append(x)
DATA=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/inputs/data/normalized');fund={};marks={}
for sym in ['BTC','SOL']:
 z=pq.read_table(DATA/f'bybit-{sym}USDT-funding.parquet').to_pylist();fund[sym]=[(int(x['funding_time_ms'])*10**6,D(x['funding_rate'])) for x in z]
 d=pq.read_table(DATA/f'bybit-{sym}USDT-mark-1m.parquet',columns=['open_time_ms','close']).to_pydict();marks[sym]={int(t)*10**6+M:D(p) for t,p in zip(d['open_time_ms'],d['close'])}
def close(a,b,tol=D('0.0000002')):
 assert abs(D(str(a))-D(str(b)))<=tol,(a,b)
for a in actions:
 cy=int(a['cycle']);s=D(a['side']);slip=D(a['slip_bp'])/10000;evs=bycy[cy];e=int(a['execution_ns']);end=int(a['exit_ns']);nb=D(a['NB_USDT']);feeS=feeT=avoided=D(0);ss=st=D(0);cashS=cashT=D(0);heldS=heldT=D(0)
 assert len({int(x['decision_ns']) for x in actions if x['cycle']==a['cycle']})==1
 for ev in evs:
  ds=D(ev['delta_SOLqty']);dt=D(ev['delta_trimqty']);ps=D(ev['SOLexecution']);pb=D(ev['BTCexecution']);nf=D(ev['native_avoided_fee']);qsf=abs(ds)*ps*F;qss=abs(ds)*ps*slip
  cashS+=s*ds*ps-qsf-qss;feeS+=qsf;ss+=qss;heldS+=ds;heldT+=dt
  if ev['event_kind']=='BASELINE_REDUCTION':
   assert ds<=0 and dt<=0 and nf>=0
   native=native_byid[ev['native_order_id']];import re
   close(pb,D(native['avg_px']));close(nf,D(re.search(r'([0-9.]+) USDT',native['commissions'])[1])*abs(dt)/D(native['filled_qty']));checks['actual_native_exit_price_and_avoided_fee']+=1
   cashT+=s*dt*pb+nf;avoided+=nf;checks['avoided_native_exit_not_restored']+=1
  else:
   qtf=abs(dt)*pb*F;qts=abs(dt)*pb*slip;cashT+=s*dt*pb-qtf-qts;feeT+=qtf;st+=qts
  assert heldS>=D('-1e-8') and heldT>=D('-1e-8')
  # No re-add after initial entry; proportional adjustment identical on both quantities.
  if ev['event_kind']!='ENTRY':assert ds<=0 and dt<=0
  if dt:close(ds/dt,D(a['initial_SOLqty'])/D(a['initial_trimqty']),D('1e-9'))
  checks['cashflow_quantity_events']+=1
 close(heldS,0);close(heldT,0)
 if a['exit_reason']=='BTC_FLAT':assert not any(x['event_kind']=='SCHEDULED_EXIT_RESTORE' for x in evs)
 funding={}
 for sym,qfield in [('SOL','delta_SOLqty'),('BTC','delta_trimqty')]:
  total=D(0)
  for t,rate in fund[sym]:
   if not e<=t<=end:continue
   # Independently sum signed trades preceding settlement; choose before/after tie exactly frozen.
   h=sum((D(ev[qfield]) for ev in evs if int(ev['event_ns'])<t or (a['funding_boundary']=='AFTER_REDUCTION' and int(ev['event_ns'])==t)),D(0))
   assert h>=D('-1e-8');total+=s*h*marks[sym][t]*rate;checks['independent_funding_events']+=1
  funding[sym]=total
 close(cashS+funding['SOL'],a['SOL_net_USDT']);close(cashT+funding['BTC'],a['trim_net_USDT']);close(funding['SOL'],a['SOL_funding_USDT']);close(funding['BTC'],a['trim_avoided_funding_USDT']);close(feeS,a['SOL_fees_USDT']);close(feeT,a['trim_fees_USDT']);close(avoided,a['avoided_native_fees_USDT']);close(ss,a['SOL_slip_USDT']);close(st,a['trim_slip_USDT']);checks['independent_endpoint_cash_fee_slip_scenarios']+=1
 close((D(a['SOL_net_USDT'])-D(a['trim_net_USDT']))/nb*10000,a['SOL_minus_trim_bp'],D('1e-9'))
# Protection remains UNKNOWN; there is no constructed equity series to verify.
# Recompute cohort means independently from action rows, including fixed early entry cut.
for c in read(R/'screen-cohorts.csv'):
 z=[a for a in actions if a['slip_bp']==c['slip_bp'] and a['funding_boundary']==c['funding_boundary'] and ((a['early']=='True') if c['cohort']=='early' else a['period']==c['cohort'])];assert len(z)==int(c['episodes'])
 for k,m in [('SOL_net_bp','mean_SOL_net_bp'),('trim_net_bp','mean_trim_net_bp'),('SOL_minus_trim_bp','mean_SOL_minus_trim_bp')]:close(sum(D(a[k]) for a in z)/len(z),c[m],D('1e-8'));checks['cohort_equal_episode_means']+=1
# Fresh source pin verification protects accidental mutations while calculating.
for p,sha in led['input_sha256'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha
v=dict(status='PASS',method='Independent Decimal direct cashflows and direct funding integration; actualnative avoidedexit/fee and equal-episode means',checks=dict(checks),actions_scenarios=len(actions),distinct_episodes=len(bycy),sourcepins_unchanged=True,verification_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),protection_clock_qualification='See screen-result.json; arithmetic PASS does not establish missing coherent protection samples',engine_runs=0)
(R/'screen-verification.json').write_text(json.dumps(v,indent=2)+'\n');led.update(arithmetic_verifications_completed=1,status='ONE_OUTCOME_PASS_ONE_ARITHMETIC_VERIFICATION_COMPLETE');(R/'screen-ledger.json').write_text(json.dumps(led,indent=2)+'\n');res=json.loads((R/'screen-result.json').read_text());res['accounting_verification']='PASS';(R/'screen-result.json').write_text(json.dumps(res,indent=2)+'\n');print(json.dumps(v,indent=2))
