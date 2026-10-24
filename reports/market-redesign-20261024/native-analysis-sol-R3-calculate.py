#!/usr/bin/env python3
"""Frozen paired action arithmetic, not an execution or portfolio simulator."""
import csv,json,math,hashlib,collections,bisect,statistics,argparse,gzip
from decimal import Decimal as D
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
BASE=ROOT/'reports/b-50-90-next-20261023';H=3600000000000;FEE=.00055
parser=argparse.ArgumentParser(description='Same predeclared frozen-action screen on actual accepted R3 inventory; no engine/lifecycle')
parser.add_argument('--artifact',required=True);parser.add_argument('--raw');parser.add_argument('--acceptance',default=str(OUT/'native-analysis-R3.json'));parser.add_argument('--bars',default=str(BASE/'owner-closed-bars.csv'));parser.add_argument('--output-prefix',default='native-analysis-sol-R3');ARGS=parser.parse_args()
assert ARGS.output_prefix.startswith('native-analysis-sol-R3') and Path(ARGS.output_prefix).name==ARGS.output_prefix
ARTIFACT=Path(ARGS.artifact).resolve();RAW=Path(ARGS.raw).resolve() if ARGS.raw else ARTIFACT.with_name(ARTIFACT.stem+'-raw-native.json')
R3=json.loads(ARTIFACT.read_text());R3RAW=json.loads(RAW.read_text());ACCEPT=json.loads(Path(ARGS.acceptance).read_text())
assert ACCEPT['row']['variant']=='R3' and ACCEPT['row']['status']=='VALIDATED_FULL_NATIVE' and ACCEPT['row']['mechanical_and_cash_acceptance'] is True
assert ACCEPT['input_sha256'][str(ARTIFACT)]==hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() and ACCEPT['input_sha256'][str(RAW)]==hashlib.sha256(RAW.read_bytes()).hexdigest()
INPUTS=[Path(ARGS.bars),Path(R3['execution_artifacts']['fills']['path']),ARTIFACT,RAW,OUT/'sol-screen-design.json',Path(ARGS.acceptance)]
def outputpath(name):return OUT/name.replace('sol-screen',ARGS.output_prefix)
def read(p):
 with p.open(newline='') as f:return list(csv.DictReader(f))
def writecsv(name,rows):
 with outputpath(name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def iso(t):return datetime.fromtimestamp(t/1e9,timezone.utc).isoformat()
bars=read(INPUTS[0]);fills=[x for x in read(INPUTS[1]) if x['instrument_id'].startswith('BTC')];audit=[x for x in R3RAW['fill_audit'] if x['instrument'].startswith('BTC')];sp=R3['split_cover_audit']['parents'];assert len(fills)==len(audit)
assert hashlib.sha256(INPUTS[1].read_bytes()).hexdigest()==ACCEPT['input_sha256'][str(INPUTS[1])]==R3['execution_artifacts']['fills']['sha256']
# This archive contains one full fill per order; reject aggregate/partial timing ambiguity.
assert all(x['status']=='FILLED' and D(x['quantity'])==D(x['filled_qty']) for x in fills)
def ns(s):return int(datetime.fromisoformat(s).timestamp())*10**9
# Verify one-to-one actual fill records independently of side.
auditkeys=collections.Counter((int(x['fill_ns']),D(x['qty']),D(x['px'])) for x in audit)
fillkeys=collections.Counter((ns(x['ts_last']),D(x['filled_qty']),D(x['avg_px']).quantize(D('.1'))) for x in fills)
assert auditkeys==fillkeys
bytime=collections.defaultdict(list)
for f in fills:bytime[ns(f['ts_last'])].append(f)
states=[];q=D(0);active=0;ends={};starts={};sid=0
for t,fs in sorted(bytime.items()):
 old=q;q+=sum((D(x['filled_qty'])*(1 if x['side']=='BUY' else -1) for x in fs),D(0))
 if not old and q:sid+=1;active=sid;starts[sid]=t
 if old and not q:ends[active]=t
 assert not old or not q or (old>0)==(q>0)
 states.append((t,q,active))
assert q==0 and sid==len(sp) and len(ends)==len(sp)
assert list(starts.values())==[int(x['start_ns']) for x in sp]
state_ts=[x[0] for x in states]
close={symbol:{int(x['close_ns']):float(x['close']) for x in bars if x['symbol']==symbol and int(x['step_ns'])==H} for symbol in ['BTCUSDT','SOLUSDT']}
ts=sorted(close['BTCUSDT']);assert ts==sorted(close['SOLUSDT']) and len(ts)==17520 and all(b-a==H for a,b in zip(ts,ts[1:]))
b=[close['BTCUSDT'][t] for t in ts];s=[close['SOLUSDT'][t] for t in ts]
rb=[None]+[b[i]/b[i-1]-1 for i in range(1,len(ts))];rs=[None]+[s[i]/s[i-1]-1 for i in range(1,len(ts))]
h4={int(x['close_ns']):float(x['close']) for x in bars if x['symbol']=='BTCUSDT' and int(x['step_ns'])==4*H};assert len(h4)==4380
counts=collections.Counter();features=[];outcomes=[];cut=int(datetime(2025,9,1,tzinfo=timezone.utc).timestamp()*1e9)
for i,t in enumerate(ts):
 if t not in h4:continue
 counts['H4_total']+=1
 stidx=bisect.bisect_left(state_ts,t)-1
 if t in bytime:counts['excluded_fill_at_exact_decision']+=1;continue
 if stidx<0 or not states[stidx][1]:counts['excluded_BTCflat']+=1;continue
 _,qty,cycle=states[stidx];side=1 if qty>0 else -1
 if i<721:counts['excluded_missing_lag720']+=1;continue
 # Return indices i-720...i-1: strictly lagged,720 synchronized observations.
 xb=rb[i-720:i];xs=rs[i-720:i];assert len(xb)==len(xs)==720 and None not in xb
 mb=sum(xb)/720;ms=sum(xs)/720
 vb=sum((x-mb)**2 for x in xb)/719;vs=sum((x-ms)**2 for x in xs)/719;cov=sum((x-mb)*(y-ms) for x,y in zip(xb,xs))/719
 if vb<=0 or vs<=0:counts['excluded_invalid_variance']+=1;continue
 rho=cov/math.sqrt(vb*vs);beta=cov/vb
 if rho<=0 or beta<=0:counts['excluded_nonpositive_link']+=1;continue
 assert abs(h4[t]-b[i])<1e-8
 h4r=b[i]/b[i-4]-1;den=sum(abs(b[k]-b[k-4]) for k in range(i-92,i+1,4));er=abs(b[i]-b[i-96])/den if den else 0
 erbin='low' if er<=.25 else 'middle' if er<=.5 else 'high';corrbin='low' if rho<.3 else 'middle' if rho<.7 else 'high';adverse=side*h4r<0
 nb=abs(float(qty))*b[i];period='first_year' if t<cut else 'second_year'
 sizes={'OWNER_VOL':.5*nb*math.sqrt(vb/vs),'HALF_MV':.5*nb*cov/vs,'HALF_FACTOR':.5*nb/beta}
 feature={'decision_ns':t,'decision_utc':iso(t),'cycle':cycle,'period':period,'side':side,'observed_BTCqty':str(qty),'NB_USDT':nb,'BTCclose':b[i],'SOLclose':s[i],'lag720_last_return_end_ns':ts[i-1],'lag720_cov':cov,'lag720_rho':rho,'lag720_sigmaBTC':math.sqrt(vb),'lag720_sigmaSOL':math.sqrt(vs),'lag720_betaSOLgivenBTC':beta,'closed_H4_return':h4r,'side_closed_H4_return':side*h4r,'H4_stratum':'adverse' if adverse else 'nonadverse','ER24H4':er,'ER_stratum':erbin,'corr_stratum':corrbin,'observed_native_flat_ns':ends[cycle],'actual_R3_parent_episode_id':sp[cycle-1]['episode_id']}
 feature.update({'NS_'+name:n for name,n in sizes.items()});features.append(feature);counts['eligible_decisions']+=1
 actions=[('NO_HEDGE','NONE',0.,0.)]+[(name,'SOL',n,n*beta) for name,n in sizes.items()]+[('TRIM_MATCH_'+name,'BTC_TRIM',n*beta,n*beta) for name,n in sizes.items()]
 for horizon in [4,24]:
  if i+horizon>=len(ts):counts['labels_missing_'+str(horizon)+'h']+=1;continue
  rrB=[b[i+j]/b[i]-1 for j in range(1,horizon+1)];rrS=[s[i+j]/s[i]-1 for j in range(1,horizon+1)]
  baseline=[side*r for r in rrB];btcworst=min(baseline)
  for name,kind,n,relief in actions:
   rr=rrS if kind=='SOL' else rrB
   gross=[-side*n*r for r in rr] if kind!='NONE' else [0.]*horizon
   fees=[FEE*n*(2+r) for r in rr] if kind!='NONE' else [0.]*horizon
   benefit=[(g-f)/nb for g,f in zip(gross,fees)];combined=[x+y for x,y in zip(baseline,benefit)]
   outcomes.append({'decision_ns':t,'decision_utc':iso(t),'cycle':cycle,'period':period,'side':side,'H4_stratum':feature['H4_stratum'],'ER_stratum':erbin,'corr_stratum':corrbin,'horizon_h':horizon,'endpoint_stratum':'BTCdownside' if baseline[-1]<0 else 'BTCupside','crosses_observed_native_flat':ts[i+horizon]>=ends[cycle],'action':name,'kind':kind,'NB_USDT':nb,'action_notional_USDT':n,'estimated_factor_relief_notional_USDT':relief,'relief_fraction_NB':relief/nb,'endpoint_BTC_change_bp':baseline[-1]*10000,'endpoint_gross_action_benefit_USDT':gross[-1],'roundtrip_action_fee_USDT':fees[-1],'endpoint_net_action_benefit_USDT':gross[-1]-fees[-1],'endpoint_net_action_benefit_bp':benefit[-1]*10000,'endpoint_combined_change_bp':combined[-1]*10000,'BTC_adverse_H1close_change_bp':min(0.,btcworst)*10000,'combined_adverse_H1close_change_bp':min(0.,min(combined))*10000,'adverse_H1close_improvement_bp':(min(0.,min(combined))-min(0.,btcworst))*10000,'action_fee_bp':fees[-1]/nb*10000})
# Independent observed state check against actual settled trace, never used as future features.
TRACE=Path(R3['minute_risk_observations']['settled_native_close_receipts']['trace_path']);assert hashlib.sha256(TRACE.read_bytes()).hexdigest()==ACCEPT['input_sha256'][str(TRACE)]
featureby={r['decision_ns']:r for r in features};tracechecked=0
with gzip.open(TRACE,'rt') as f:
 for z in csv.DictReader(f):
  t=int(z['source_quote_ns'])
  if t not in featureby:continue
  qty=D(0)
  for pos in json.loads(z['native_positions_and_mark_ohlc_json']):
   if pos['instrument_id'].startswith('BTC'):
    assert str(pos['side']) in ['2','3'];qty+=D(pos['quantity'])*(1 if str(pos['side'])=='2' else -1)
  assert qty==D(featureby[t]['observed_BTCqty']);tracechecked+=1
assert tracechecked==len(features)
INPUTS.append(TRACE)
writecsv('sol-screen-features.csv',features);writecsv('sol-screen-outcomes.csv',outcomes)
# Prespecified descriptive views. These tables do not select an operating gate.
views=[('overall',[]),('H4',['H4_stratum']),('ER24H4',['ER_stratum']),('correlation',['corr_stratum']),('endpoint',['endpoint_stratum'])]
aggregates=[];blocks=[]
for view,extra in views:
 grouped=collections.defaultdict(list)
 for row in outcomes:
  for year in ['all',row['period']]:grouped[(year,row['horizon_h'],row['action'],*[row[x] for x in extra])].append(row)
 for key,z in sorted(grouped.items()):
  cycles=collections.defaultdict(list)
  for r in z:cycles[r['cycle']].append(r)
  clustermeans=[];clustertails=[]
  for cycle,cz in cycles.items():
   cm=statistics.mean(r['endpoint_net_action_benefit_bp'] for r in cz);ct=statistics.mean(r['adverse_H1close_improvement_bp'] for r in cz);clustermeans.append(cm);clustertails.append(ct)
   blocks.append({'view':view,'period':key[0],'horizon_h':key[1],'action':key[2],'stratum':','.join(map(str,key[3:])) or 'ALL','cycle':cycle,'n_H4_labels':len(cz),'mean_endpoint_net_benefit_bp':cm,'mean_adverse_close_improvement_bp':ct})
  aggregates.append({'view':view,'period':key[0],'horizon_h':key[1],'action':key[2],'stratum':','.join(map(str,key[3:])) or 'ALL','n_H4_labels':len(z),'n_cycle_blocks':len(cycles),'mean_action_notional_over_NB':statistics.mean(r['action_notional_USDT']/r['NB_USDT'] for r in z),'mean_estimated_factor_relief':statistics.mean(r['relief_fraction_NB'] for r in z),'mean_endpoint_BTC_change_bp':statistics.mean(r['endpoint_BTC_change_bp'] for r in z),'mean_endpoint_net_benefit_bp':statistics.mean(r['endpoint_net_action_benefit_bp'] for r in z),'mean_action_fee_bp':statistics.mean(r['action_fee_bp'] for r in z),'mean_adverse_H1close_improvement_bp':statistics.mean(r['adverse_H1close_improvement_bp'] for r in z),'pct_endpoint_benefit_positive':100*sum(r['endpoint_net_action_benefit_bp']>0 for r in z)/len(z),'equal_cycle_mean_endpoint_benefit_bp':statistics.mean(clustermeans),'equal_cycle_mean_adverse_improvement_bp':statistics.mean(clustertails),'pct_cycle_blocks_mean_benefit_positive':100*sum(x>0 for x in clustermeans)/len(clustermeans),'n_crosses_native_flat':sum(r['crosses_observed_native_flat'] for r in z)})
writecsv('sol-screen-summary.csv',aggregates);writecsv('sol-screen-cycle-blocks.csv',blocks)
# One connected arithmetic verification: zero reference, formulas, matched relief and label bounds.
assert all(r['lag720_last_return_end_ns']<r['decision_ns'] for r in features)
for r in outcomes:
 assert r['NB_USDT']>0 and r['action_notional_USDT']>=0
 if r['kind']=='BTC_TRIM':assert r['action_notional_USDT']<=r['NB_USDT']*(1+1e-12)
 assert r['relief_fraction_NB']<=1+1e-12
 if r['action']=='NO_HEDGE':assert r['endpoint_net_action_benefit_bp']==r['action_fee_bp']==r['adverse_H1close_improvement_bp']==0
 if r['action']=='HALF_FACTOR':assert abs(r['relief_fraction_NB']-.5)<1e-12
 assert abs(r['endpoint_combined_change_bp']-r['endpoint_BTC_change_bp']-r['endpoint_net_action_benefit_bp'])<1e-9
# Analytical identities relative to factor-covariance estimate.
for r in features:
 rho=r['lag720_rho'];beta=r['lag720_betaSOLgivenBTC'];nb=r['NB_USDT']
 assert abs(r['NS_OWNER_VOL']*beta/nb-.5*rho)<1e-12
 assert abs(r['NS_HALF_MV']*beta/nb-.5*rho*rho)<1e-12
meta={'status':'STOP_SOL_INCONCLUSIVE_NO_OPERATING_GATE_SELECTED','actual_inventory_source':'ACCEPTED_R3_NATIVE_FILLS_NOT_E4_CALENDAR','R3_parent_count':len(sp),'observed_native_trace_state_checks':tracechecked,'predeclared_definition_sha256':hashlib.sha256((OUT/'sol-screen-design.json').read_bytes()).hexdigest(),'counts':dict(counts),'actual_BTC_native_fills':len(fills),'verified_one_to_one_fill_audit':True,'fill_price_check':'native avg_px normalized to archivedBTCtick0.1 for floating representation; filltimestamp+quantity exact','observed_BTCcycles':sid,'terminal_BTCqty':str(q),'eligible_cycles':len(set(r['cycle'] for r in features)),'outputs':{'features':len(features),'action_horizon_rows':len(outcomes),'aggregate_rows':len(aggregates),'cycle_blocks':len(blocks)},'lag_correlation_range':[min(r['lag720_rho'] for r in features),max(r['lag720_rho'] for r in features)],'input_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in INPUTS},'full_native_attempts':0,'verification':'PASS actualR3 filled orders all singlefullfill, matched nativeaudit; nativeinventory terminal0 and actualparent starts match; all eligibledecision nativeQ match settledtrace; lag availability, NO_HEDGEzero, relief identities, additive comparisons pass','limitations':['Observed actualR3 inventory only; action outcomes are frozen conditional arithmetic, not a SOL candidate lifecycle or ROI.','Fixed observed initial BTC quantity is held hypothetically for outcome horizon; crosses-native-flat labels flagged. No lifecycle, equity, margin or cap admission.','H1 close-grid excursions omit intrahour extrema, order sequence, fees beyond declared hypothetical action roundtrip, slippage/funding/L2/queue.','H4 observations overlap; cycle block means are descriptive and not independent inference. History already viewed, not fresh OOS.','No 3TP/SL or chosen risk gate, no candidate strategy PnL/TOTAL/DD/ROI.','Positive covariance required; very small covariance may inflate factor hedge; no invented leverage/margin cap.','ER24 defined before outcomes here as24closedH4 increments(96h); no claim this matches missing precheck ZIP definition.']}
outputpath('sol-screen-meta.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
