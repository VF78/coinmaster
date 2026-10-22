import os,sys,time,json,csv,math,hashlib,subprocess,types,resource,signal
from pathlib import Path
from datetime import datetime,timezone,timedelta
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
T0=time.monotonic(); signal.alarm(180)
BASE=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021'); DATA=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/data/normalized'); OUT=BASE/'reports/btc-sol-causal-modules-20261022'; SCR=Path('/private/tmp/cm-h2-precheck-20261022')
HMS=3600000; HNS=HMS*1000000; DNS=24*HNS; DAYMS=24*HMS
SRC='75ffc9c69e9d79c4da4cd0614634a3eeba48d716'
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def utc(ns):return datetime.fromtimestamp(int(ns)/1e9,tz=timezone.utc).isoformat()
def rss():return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
# macOS ru_maxrss is bytes. Safety gates checked through bounded column batches.
def guard():
 if time.monotonic()-T0>180:raise RuntimeError('WALL_BUDGET_EXCEEDED')
 if rss()>350*1024*1024:raise RuntimeError('RSS_BUDGET_EXCEEDED:'+str(rss()))
pins={'BTCUSDT-daily':'71270c5b9aadad1a2d46003060e04882eaa6a0544802f4c1f025bd7253ea7545','SOLUSDT-daily':'897b89d1e93d5b961e769321edf4bb44981384fad280d8e62e8b9fca64431ab4','BTCUSDT-execution-1m':'9c48e97ce1544bb5b7169772eea2d06d8a0c3fefd2522e32ece452c2946c0f88','SOLUSDT-execution-1m':'fd5392f14c42599b54723c5a257a22b4d35729366f9b4ff76033998a6cb655b8'}
actual={k:sha(DATA/('bybit-'+k+'.parquet')) for k in pins};assert actual==pins
body=subprocess.check_output(['git','show',SRC+':runtime/coinmaster/domain/wave_overlay.py'],cwd=BASE)
assert hashlib.sha256(body).hexdigest()=='a60a7fe8d242fcc87a028bec69bffd08a67e33ad6738abf92e2ef914159ab5b9'
m=types.ModuleType('frozen_s0_daily_features');sys.modules[m.__name__]=m;exec(compile(body,'FROZEN_S0_DOMAIN','exec'),m.__dict__)
audit=json.load(open('/tmp/btc-audit-exact-s0-direction.json'));fill=audit['fill_audit'];config=audit['config']['candidate'];cand=m.Candidate(**config)
daily={s:pq.read_table(DATA/('bybit-'+s+'-daily.parquet')).to_pylist() for s in ['BTCUSDT','SOLUSDT']}
assert [r['open_time_ms'] for r in daily['BTCUSDT']]==[r['open_time_ms'] for r in daily['SOLUSDT']]
ts=[r['open_time_ms'] for r in daily['BTCUSDT']];assert all(b-a==DAYMS for a,b in zip(ts,ts[1:]))
bars=[]
for b,s in zip(daily['BTCUSDT'],daily['SOLUSDT']):
 o=datetime.fromtimestamp(b['open_time_ms']/1000,tz=timezone.utc);c=o+timedelta(days=1)
 bars.append(m.DailyBar(o,c,c,float(b['open']),float(b['close']),float(s['close'])))
features=m.batch_features_for(bars,cand);fmap={int(b.close_time.timestamp()*1e9):f for b,f in zip(bars,features)}
ledger=list(csv.DictReader(open(BASE/'reports/winner-6077107-stats/trades-ledger.csv')));solrows=[r for r in ledger if r['asset']=='SOL'];assert len(solrows)==26
betas=[]
for row in solrows:
 st=int(row['start_ns']);first=[f for f in fill if f['action']=='SOL_ADD' and int(f['fill_ns'])==st];assert first
 assert all(int(f['submit_ns'])==st and f['order_type']=='1' for f in first)
 decision=(st//DNS)*DNS;feat=fmap[decision];assert feat.beta is not None and .2<feat.beta<4
 betas.append({'trade_number':int(row['trade_number']),'actual_entry_ns':str(st),'entry_utc':utc(st),'first_SOL_submit_equals_fill':True,'daily_feature_available_ns':str(decision),'daily_feature_available_utc':utc(decision),'beta0':feat.beta,'origin':'Frozen batch_features_for on exact pinned daily bars; latest completed/available dailyfeature at first actual market SOLADD submit/fill. Original accepted-session cache not exported; current available decision inferred from matched market timing and original stale-add guard, not runtime receipt-attested.'})
(OUT/'h2-precheck.beta-pins.json').write_text(json.dumps({'source':SRC,'source_sha256':hashlib.sha256(body).hexdigest(),'input_pins':actual,'candidate':config,'rows':betas,'no_new_fit':True,'beta_not_BTC_episode_beta':True},indent=2)+'\n')
print('BETA_PINS',len(betas),'early',betas[0]['beta0'],flush=True);guard()
# Exactly one bounded paired native-minute close pass; retained arrays support cost/next-quote diagnostics.
N=1051200;opens=np.empty(N,dtype=np.int64);prices={}
for symbol in ['BTCUSDT','SOLUSDT']:
 arr=np.empty(N,dtype=np.float64);pos=0
 for batch in pq.ParquetFile(DATA/('bybit-'+symbol+'-execution-1m.parquet')).iter_batches(batch_size=32768,columns=['open_time_ms','close']):
  times=batch.column(0).to_numpy(zero_copy_only=False);vals=batch.column(1).cast(pa.float64()).to_numpy(zero_copy_only=False);n=len(times)
  if symbol=='BTCUSDT':opens[pos:pos+n]=times
  else:assert np.array_equal(opens[pos:pos+n],times)
  arr[pos:pos+n]=vals;pos+=n;guard()
 assert pos==N and np.all(arr>0);prices[symbol]=arr
assert np.all(np.diff(opens)==60000)
endns=(opens+60000)*1000000;hi=np.flatnonzero(opens%HMS==HMS-60000);native_ht=endns[hi]
native_hp=np.column_stack([prices[s][hi] for s in ['BTCUSDT','SOLUSDT']])
warm={};quality={};warm_ok=True
for col,symbol in enumerate(['BTCUSDT','SOLUSDT']):
 rows=json.load(open(SCR/(symbol+'-hourly.json')))
 wm={int(r[0])*1000000+HNS:float(r[4]) for r in rows};warm[symbol]=wm
 overlap=[(t,wm[int(t)],native_hp[i,col]) for i,t in enumerate(native_ht[:24]) if int(t) in wm]
 quality[symbol]={'fetched_rows':len(rows),'contiguous':bool(rows) and all(int(b[0])-int(a[0])==HMS for a,b in zip(rows,rows[1:])),'overlap_rows':len(overlap),'exact_close_matches':int(sum(a==b for _,a,b in overlap)),'max_abs_close_delta':float(max([abs(a-b) for _,a,b in overlap],default=0.)),'raw_hourly_sha256':sha(SCR/(symbol+'-hourly.json'))}
 if len(overlap)!=24 or any(a!=b for _,a,b in overlap):warm_ok=False
common=sorted(set(warm['BTCUSDT'])&set(warm['SOLUSDT']))
prior=[t for t in common if t<native_ht[0]] if warm_ok else []
ht=np.concatenate([np.array(prior,dtype=np.int64),native_ht]);hp=np.concatenate([np.array([[warm[s][t] for s in ['BTCUSDT','SOLUSDT']] for t in prior],dtype=float).reshape(-1,2),native_hp])
assert np.all(np.diff(ht)==HNS)
hr=np.diff(np.log(hp),axis=0)
np.savez_compressed(SCR/'all_price_cache.npz',opens=opens,BTC=prices['BTCUSDT'],SOL=prices['SOLUSDT'],ht=ht,hp=hp)
provenance=json.load(open(SCR/'hourly-fetch-provenance.json'))
(OUT/'h2-precheck.warmup.json').write_text(json.dumps({'source':'Genuine Bybit public linear Kline interval60; indicator warmup only','requests':provenance,'quality':quality,'warmup_used':warm_ok,'first_hour_close_utc':utc(ht[0]),'native_data_unchanged':True,'input_pins':actual},indent=2)+'\n')
print('HOURLY',len(ht),'OVERLAP_OK',warm_ok,'scan_elapsed',time.monotonic()-T0,'rss',rss(),flush=True)
def held(asset,start,t):
 rows=[r for r in fill if r['instrument'].startswith(asset+'USDT') and start<=int(r['fill_ns'])<=t]
 add='BTC_ENTRY' if asset=='BTC' else 'SOL_ADD'
 return max(0.,sum(float(r['qty'])*(1 if r['action']==add else -1) for r in rows))
def diagnostic(row,alarm_i,b0,base_returns):
 if alarm_i is None:return {'alarm':False,'action_status':'NO_ALARM'}
 t=int(ht[alarm_i]);st=int(row['start_ns']);en=int(row['end_ns']);q=held('SOL',st,t);nexti=int(np.searchsorted(endns,t,side='right'))
 d={'alarm':True,'alarm_ns':str(t),'alarm_utc':utc(t),'hours_from_entry':(t-st)/HNS,'source_hour_close_SOL':float(hp[alarm_i,1]),'held_SOL_original_fill_path':q,'native_pending_orders':'UNKNOWN_NOT_EXPORTED','actual_eligibility':'UNKNOWN_NOT_EXPORTED'}
 if nexti>=N or int(endns[nexti])>=en or q<=0:d.update(action_status='NO_CAUSAL_QUOTE_BEFORE_ORIGINAL_EXIT_OR_FLAT');return d
 side=1 if row['side']=='LONG' else -1;cut=math.floor(q*.5*10+1e-8)/10;px=float(prices['SOLUSDT'][nexti]);ex=float(row['exit_vwap']);exit_rate=float(row['exit_fees'])/float(row['exit_notional']);fee=cut*px*.00055;avoided_ref=cut*ex*exit_rate
 lo=int(np.searchsorted(endns,t,side='right'));up=int(np.searchsorted(endns,en,side='right'));path=prices['SOLUSDT'][lo:up]
 favorable=max(side*(float(np.max(path) if side==1 else np.min(path))/px-1),0) if len(path) else None
 adverse=max(-side*(float(np.min(path) if side==1 else np.max(path))/px-1),0) if len(path) else None
 lateradds=sum(r['action']=='SOL_ADD' and st<=int(r['fill_ns'])<en and int(r['fill_ns'])>t for r in fill if r['instrument'].startswith('SOL'))
 btc=next((r for r in ledger if r['asset']=='BTC' and int(r['start_ns'])<=t<int(r['end_ns'])),None)
 qb=held('BTC',int(btc['start_ns']),t) if btc else 0.;sb=(1 if btc['side']=='LONG' else -1) if btc else 0
 prev_idx=int(np.searchsorted(endns,t,side='right'))-1;pb=float(prices['BTCUSDT'][prev_idx]);ps=float(prices['SOLUSDT'][prev_idx]);nb=sb*qb*pb;ns=side*q*ps
 shock_before=base_returns@np.array([nb,ns]);shock_after=base_returns@np.array([nb,side*(q-cut)*ps]);sig_before=float(np.std(shock_before));sig_after=float(np.std(shock_after))
 d.update(action_status='SAVED_PATH_HYPOTHETICAL_ONLY',next_quote_ns=str(int(endns[nexti])),next_quote_utc=utc(endns[nexti]),next_quote_SOL=px,ideal_cut_qty_rounded=cut,cut_taker_fee_reference=fee,removed_original_exit_fee_reference=avoided_ref,endpoint_price_delta_reference_USDT=side*cut*(px-ex),endpoint_after_close_fee_difference_reference_USDT=side*cut*(px-ex)-fee+avoided_ref,endpoint_reference_return_per_cut_notional=side*(px-ex)/px-(fee-avoided_ref)/(cut*px) if cut else None,original_cycle_exit_VWAP=ex,original_later_adds_count=lateradds,postalarm_favorable_close_excursion=favorable,postalarm_adverse_close_excursion=adverse,original_cycle_net_ex_funding=float(row['net_ex_funding']),BTC_signed_notional=nb,SOL_signed_notional=ns,prior_hourly_linear_book_sigma_before=sig_before,prior_hourly_linear_book_sigma_after=sig_after,prior_hourly_linear_sigma_increased=sig_after>sig_before*(1+1e-12),beta_factor_abs_increased=abs(nb+b0*side*(q-cut)*ps)>abs(nb+b0*ns),pair_risk_scope='Fixed prior-hour linear return shock diagnostic, not future portfolioDD/nativePnL. Original held qty reconstructed from confirmed fills; pending/eligibility unknown.')
 return d
results=[]
for row,beta in zip(solrows,betas):
 st=int(row['start_ns']);en=int(row['end_ns']);b0=beta['beta0'];side=1 if row['side']=='LONG' else -1;iend=int(np.searchsorted(ht,st,side='left'))
 r={'trade_number':int(row['trade_number']),'side':row['side'],'entry_utc':utc(st),'exit_utc':utc(en),'entry_month':utc(st)[:7],'beta0':b0,'beta_feature_available_utc':beta['daily_feature_available_utc'],'original_net_ex_funding':float(row['net_ex_funding'])}
 if iend<2161:r.update(status='BLOCKED_2160_PRIOR_HOURS_MISSING',available_prior_returns=max(0,iend-1));results.append(r);continue
 seg=hr[iend-2161:iend-1];assert len(seg)==2160
 u=seg[:,1]-b0*seg[:,0];mu=float(u.mean());sigma=float(u.std());assert sigma>0
 r.update(status='COMPLETE_SAVED_PATH_DIAGNOSTIC',baseline_start_utc=utc(ht[iend-2161]),baseline_last_close_utc=utc(ht[iend-1]),prior_returns=2160,mu=mu,sigma_population=sigma)
 z=((u-mu)/sigma).reshape(90,24);flags=[]
 for block in z:
  g=0;alarm=False
  for v in block:g=max(0.,g-side*float(v)-.5);alarm|=g>=5
  flags.append(alarm)
 count=sum(flags);p=count/90
 adverse=np.maximum(0.,np.max(-side*np.cumsum(seg[:,1].reshape(90,24),axis=1),axis=1));distance=float(np.quantile(adverse,1-p,method='linear')) if count else float('inf');past_stop_count=int(np.sum(adverse>=distance)) if count else 0
 r.update(calibration_CUSUM_blocks=count,calibration_total_blocks=90,calibration_price_stop_blocks=past_stop_count,calibration_price_stop_distance_log=None if not math.isfinite(distance) else distance,calibration_quantile='linear q=1-CUSUMblockfraction; >= ties included;0CUSUMalarms=>infinite stop distance',calibration_tie_frequency_delta=(past_stop_count-count)/90)
 indices=np.flatnonzero((ht-HNS>=st)&(ht<en));g=0.;alarm_i=None;stop_i=None;firstpx=float(next(f['px'] for f in fill if f['action']=='SOL_ADD' and int(f['fill_ns'])==st))
 for i in indices:
  resid=hr[i-1,1]-b0*hr[i-1,0];g=max(0.,g-side*(resid-mu)/sigma-.5)
  if alarm_i is None and g>=5:alarm_i=int(i)
  if stop_i is None and -side*math.log(float(hp[i,1])/firstpx)>=distance:stop_i=int(i)
 r['CUSUM']=diagnostic(row,alarm_i,b0,seg);r['price_stop']=diagnostic(row,stop_i,b0,seg)
 results.append(r);guard()
def summarize(method):
 acted=[r[method] for r in results if r.get(method,{}).get('action_status')=='SAVED_PATH_HYPOTHETICAL_ONLY']
 return {'evaluable_cycles':sum(r['status'].startswith('COMPLETE') for r in results),'alarm_cycles':sum(bool(r.get(method,{}).get('alarm')) for r in results),'action_reference_cycles':len(acted),'original_profitable_cycles_affected':sum(d['original_cycle_net_ex_funding']>0 for d in acted),'sum_endpoint_after_fee_difference_REFERENCE_NOT_PORTFOLIO':sum(d['endpoint_after_close_fee_difference_reference_USDT'] for d in acted),'median_endpoint_return_REFERENCE':float(np.median([d['endpoint_reference_return_per_cut_notional'] for d in acted])) if acted else None,'endpoint_positive_references':sum(d['endpoint_after_close_fee_difference_reference_USDT']>0 for d in acted),'sum_immediate_cut_fee_reference':sum(d['cut_taker_fee_reference'] for d in acted),'prior_linear_book_sigma_increase_count':sum(d['prior_hourly_linear_sigma_increased'] for d in acted),'beta_factor_abs_increase_count':sum(d['beta_factor_abs_increased'] for d in acted)}
summary={m:summarize(m) for m in ['CUSUM','price_stop']};monthly={}
for month in sorted({r['entry_month'] for r in results}):
 rr=[r for r in results if r['entry_month']==month];monthly[month]={'cycles':len(rr),'CUSUM_alarms':sum(r.get('CUSUM',{}).get('alarm',False) for r in rr),'price_stop_alarms':sum(r.get('price_stop',{}).get('alarm',False) for r in rr)}
report={'status':'ACTUAL_H2_SAVED_PATH_PRECHECK_COMPLETE_NOT_NATIVE_ADMISSION','scientific_source':SRC,'S0_TOTAL':'6077107.23887483','inputs':actual,'native_audit_sha256':sha('/tmp/btc-audit-exact-s0-direction.json'),'method':{'baseline':'2160contiguoushourlylogreturns strictlypriorentry; fixedentrybeta/currentavailabledailyfeature, populationmean/std','CUSUM':'G=max(0,G-sideSOL*zResidual-.5),G0=0,alarm>=5,onecyclecut50actualremnant/cancelpendingadds/no_restore','comparator':'Atentry90nonoverlap24hblocks in preceding90days, fixedentrymu/sigma/beta; matchpastCUSUMblockfraction with linear quantile of blockmaxadverseSOLlogreturn. ResetG eachblock; tiecountdisclosed. Future26 interventioncount notmatched.','quote':'First native1mclose quote strictlyafterclosedhouralarm; no actualfill assumed.','price_reference':'Endpoint price delta uses cut qty and original WHOLE CYCLE exitVWAP, with proportional originalexitfee and extra0.00055cutfee. Lateradds flagged; no actual counterfactual lot allocation/nativePnL/alternativeequity.','pair_risk':'Original fillderivedbook and frozenpriorhourlinearshock standarddeviation, plusbeta-factor exposure; not a DD guarantee.','NIST':'k.5/h5 common designchoices, NOT crypto calibratedARL or falsealarm probability.','beta_origin_limit':'Latestclosed/availabledailyfeature deterministically reconstructed; submit==fillMARKET checked26/26, accepted_session cache not exported. Eligibility/pending gaps remainUNKNOWN.'},'hourly_warmup_quality':quality,'warmup_used':warm_ok,'summary':summary,'early_SOL1':results[0],'monthly':monthly,'cycles':results,'resources':{'wall_seconds':time.monotonic()-T0,'peak_RSS_bytes':rss(),'RSS_limit_bytes':350*1024*1024,'wall_limit_seconds':180,'original_minute_rows_per_asset':N,'combined_hourly_closes':len(ht),'raw_pair_scans':2,'technical_incident':'Initial paired column pass finished but JSON int64 serialization failed before result output. Second identical bounded column pass recovered; no strategy/native/model run.'},'new_native_engine_runs':0,'full_TOTAL':'UNKNOWN','full_settled_DD':'UNKNOWN','actual_pending_eligibility':'UNKNOWN_NOT_EXPORTED','NIST_sources':['https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/cusumarl.htm','https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm']}
(OUT/'h2-precheck.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
flat=[]
for r in results:
 for method in ['CUSUM','price_stop']:
  d={k:v for k,v in r.items() if k not in ['CUSUM','price_stop']};d['method']=method;d.update(r.get(method,{}));flat.append(d)
keys=list(dict.fromkeys(k for r in flat for k in r))
with (OUT/'h2-precheck.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(flat)
np.savez_compressed(SCR/'paired_hourly_cache.npz',hour_end_ns=ht,hour_prices=hp)
print(json.dumps({'summary':summary,'early_SOL1':results[0],'resources':report['resources']},indent=2),flush=True)
