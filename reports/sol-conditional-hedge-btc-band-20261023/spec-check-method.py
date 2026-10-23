"""One shared cached price read; H2/H3 specification diagnostics only, no native/PnL."""
import json,csv,hashlib,time,resource,signal
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
signal.alarm(90);beg=time.monotonic()
BASE=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021')
OLD=BASE/'reports/btc-sol-causal-modules-20261022';OUT=BASE/'reports/sol-conditional-hedge-btc-band-20261023'
CACHE=Path('/private/tmp/cm-h2-precheck-20261022/all_price_cache.npz');NATIVE=Path('/private/tmp/btc-audit-exact-s0-direction.json')
M=60_000_000_000;H=60*M;B=4*H

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc(t):return datetime.fromtimestamp(int(t)/1e9,timezone.utc).isoformat()
def dump(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
assert sha(NATIVE)=='e7854784dce9bcf27e77d45ebe12873d78a42a0ecb43b3686f2a0da810fb2bfa'
n=json.loads(NATIVE.read_text());fills=n['fill_audit']
# Load each required cached array once. No raw Parquet scan or second price read.
with np.load(CACHE,allow_pickle=False) as z:
 assert set(['opens','BTC','SOL','ht','hp'])<=set(z.files)
 opens=z['opens'];btc=z['BTC'];sol=z['SOL'];ht=z['ht'];hp=z['hp']
a=(opens+60000)*1000000
assert len(a)==1051200 and np.all(np.diff(a)==M) and np.all(np.diff(ht)==H)
assert hp.shape==(len(ht),2) and len(btc)==len(sol)==len(a)
assert np.all(np.isfinite(hp)) and np.all(hp>0)
hi=np.flatnonzero(a%H==0);pos=np.searchsorted(ht,a[hi]);assert np.array_equal(ht[pos],a[hi])
assert np.array_equal(hp[pos,0],btc[hi]) and np.array_equal(hp[pos,1],sol[hi])
hr=np.diff(np.log(hp),axis=0)
ledger=list(csv.DictReader((BASE/'reports/winner-6077107-stats/trades-ledger.csv').open()))
solrows=[r for r in ledger if r['asset']=='SOL'];betas=json.loads((OLD/'h2-precheck.beta-pins.json').read_text())['rows']
assert len(solrows)==len(betas)==26
h2=[]
for row,beta in zip(solrows,betas):
 st=int(row['start_ns']);en=int(row['end_ns']);num=int(row['trade_number']);assert num==beta['trade_number']
 side=1 if row['side']=='LONG' else -1;b0=beta['beta0'];iend=int(np.searchsorted(ht,st,side='left'))
 assert iend>=721
 seg=hr[iend-721:iend-1];assert len(seg)==720
 u=seg[:,1]-b0*seg[:,0];mu=float(u.mean());sigma=float(u.std(ddof=1));assert sigma>0
 first=[f for f in fills if f['action']=='SOL_ADD' and int(f['fill_ns'])==st];assert first
 firstpx=sum(float(f['qty'])*float(f['px']) for f in first)/sum(float(f['qty']) for f in first)
 indices=np.flatnonzero((ht-H>=st)&(ht<en));g=0.;maxg=0.;alarm=None;stop=None
 for i in indices:
  residual=hr[i-1,1]-b0*hr[i-1,0];g=max(0.,g-side*(float(residual)-mu)/sigma-.5);maxg=max(g,maxg)
  if alarm is None and g>=5:alarm=int(ht[i])
  if stop is None and side*(float(hp[i,1])/firstpx-1)<=-.02:stop=int(ht[i])
 def reference(t):
  if t is None:return None
  j=int(np.searchsorted(a,t,side='right'))
  return {'signal_ns':t,'signal_utc':utc(t),'next_close_reference_ns':int(a[j]) if j<len(a) and int(a[j])<en else None,'next_close_SOL_price':float(sol[j]) if j<len(a) and int(a[j])<en else None,'candidate_fill':'UNKNOWN'}
 h2.append({'trade_number':num,'side':row['side'],'entry_utc':utc(st),'baseline_first_close_utc':utc(ht[iend-721]),'baseline_last_close_utc':utc(ht[iend-1]),'prior_returns':720,'beta0':b0,'mu':mu,'sigma_sample_ddof1':sigma,'complete_postentry_hours':len(indices),'max_G':maxg,'CUSUM':reference(alarm),'fixed_price_stop_2pct':reference(stop)})
old3=json.loads((OLD/'h3-feasibility.json').read_text());h3=[]
parents=sorted(n['split_cover_audit']['parents'],key=lambda p:int(p['start_ns']))
for old in old3['rows']:
 num=old['trade_number'];st=int(parents[num-1]['start_ns']);en=int(old['original_final_fill_ns']);p0=float(old['P0']);side=1 if old['side']=='LONG' else -1
 start=int(old['first_eligible_full_4h_close_ns']);ii=int(np.searchsorted(a,start));peak=None;peakns=None;trigger=None
 while ii<len(a) and int(a[ii])<=en:
  now=int(a[ii]);ret=side*(float(btc[ii])/p0-1)
  if peak is None or ret>peak:peak=ret;peakns=now
  if peak>.03 and ret<=peak-.03:trigger=ii;break
  ii+=240
 r={'trade_number':num,'activation_ns':old['activation_fill_ns'],'original_trigger_ns':old.get('trigger_ns'),'original_peak_signed_return':old.get('peak_signed_close_return'),'guarded_trigger_ns':int(a[trigger]) if trigger is not None else None,'guarded_trigger_utc':utc(a[trigger]) if trigger is not None else None,'guarded_peak':peak,'guarded_peak_ns':peakns,'status':'GUARDED_TRIGGER' if trigger is not None else 'NO_GUARDED_TRIGGER_BEFORE_ORIGINAL_EXIT','candidate_fill':'UNKNOWN','actual_intent_eligibility':'UNKNOWN'}
 if trigger is not None:
  j=trigger+1;within=j<len(a) and int(a[j])<en;r.update(reference_before_original_exit=within,reference_ns=int(a[j]) if within else None,reference_price=float(btc[j]) if within else None)
  if within:
   stop=int(parents[num]['start_ns']) if num<len(parents) else 10**30
   outs=[f for f in fills if f['instrument'].startswith('BTC') and f['action']!='BTC_ENTRY' and st<=int(f['fill_ns'])<stop and int(f['fill_ns'])>int(a[j])]
   outs.sort(key=lambda f:int(f['fill_ns']));assert outs
   endpoint=outs[0];fee=float(endpoint['commission'])/float(endpoint['qty'])
   r['next_original_fill_price_cost_proxy_percent']=(side*(float(btc[j])-float(endpoint['px']))+fee-.00055*float(btc[j]))/p0*100
 h3.append(r)
triggered=[r for r in h3 if r['guarded_trigger_ns'] is not None]
oldtrigger=[r for r in h3 if r['original_trigger_ns'] is not None]
rejected=[r['trade_number'] for r in oldtrigger if r['original_peak_signed_return']<=.03]
late=[r['trade_number'] for r in triggered if r['original_trigger_ns']!=r['guarded_trigger_ns']]
result={'status':'CACHED_RECHECK_COMPLETE_DIAGNOSTIC_ONLY','new_native_runs':0,'raw_price_scans':0,'shared_cache_price_reads':1,'alternative_TOTAL_DD':'NOT_COMPUTED','inputs':{'cache_path':str(CACHE),'cache_sha256':sha(CACHE),'native_path':str(NATIVE),'native_sha256':sha(NATIVE),'beta_pins_sha256':sha(OLD/'h2-precheck.beta-pins.json'),'prior_h3_sha256':sha(OLD/'h3-feasibility.json'),'prior_h2_sha256':sha(OLD/'h2-precheck.json')},'cache_validation':{'minute_rows':len(a),'hourly_rows':len(ht),'continuous_minutes':True,'continuous_hours':True,'all_native_hourly_closes_match_cache_minutes':True,'upstream_pins':'Prior h2-precheck.json/warmup.json. Cache hash acquired now; cache was not independently hash-pinned at original generation. No claim of original receipt attestation.'},'H2':{'contract':'720 strictly preceding complete hourly logreturns, frozen existing entry beta, mean/sample std(ddof1), k=.5 h=5. G starts0. Full postentry UTC hours only; signals before original exit. Separate fixed 2% signed simple price loss from actual first SOL entry VWAP; closed-hour checks. Long price<=.98entry, short price>=1.02entry. Same next-minute-close reference semantics as prior collector. No matching to future alarm count.','CUSUM_alarms':[r['trade_number'] for r in h2 if r['CUSUM']],'fixed_2pct_price_stops':[r['trade_number'] for r in h2 if r['fixed_price_stop_2pct']],'rows':h2},'H3':{'contract':'All28 actualpositiveTP2 activations; full UTC4h bars opened>=activation; best=max signed close return vs originalP0 after activation; guard best>.03 AND f<=best-.03; rescan whole postactivation path until original final fill, including bars after rejected earliesttrigger. Next1mclose conditional reference strictly before original finalfill; not guaranteed actualfill.','old_trigger_count':len(oldtrigger),'old_first_triggers_rejected_by_guard':rejected,'guarded_trigger_count':len(triggered),'guarded_trades':[r['trade_number'] for r in triggered],'new_late_guarded_trades':late,'primary_price_proxy_mean_all28_percent':sum(r.get('next_original_fill_price_cost_proxy_percent',0.) for r in h3)/len(h3),'rows':h3},'limitations':['No candidate intents/pendingorders/native liquidity/reexecution or alternative portfolio equity.','Beta retains previous reconstruction availability limitation; original accepted-session cache receipts absent.','Old negative priceproxies and these corrected counts cannot veto C0/H4/B under accepted v2.','No full strategy 50/90 economic rejection follows from an unrun policy.'],'resources':{'wall_seconds':time.monotonic()-beg,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}}
dump(OUT/'spec-check-results.json',result)
print(json.dumps({'H2_CUSUM':result['H2']['CUSUM_alarms'],'H2_2pct':result['H2']['fixed_2pct_price_stops'],'early_SOL1':h2[0],'H3_summary':{k:v for k,v in result['H3'].items() if k not in ['rows','contract']},'resources':result['resources']},indent=2))
