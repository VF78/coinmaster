"""Single immutable observer scan: BTC entry-relative adverse price excursion, no PnL engine."""
import bisect,csv,gzip,json,math,time
from pathlib import Path
from collections import Counter
out=Path('reports/h1-b1-113')
base=Path('/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-sizing-v3-20261011/result')
raw=json.load(open(base/'v0-selective-lifecycle-cap30m-btc-direction.json'))
audit=json.load(open('reports/selective-lifecycle-cap30m-113/v3-drawdown-causes/attribution.json'))
eps=[dict(e,close_mae_pct=0.,held_ohlc_mae_pct=0.,close_samples=0,held_ohlc_samples=0,avg_entries=set()) for e in audit['episodes']['BTC']]
starts=[int(e['start_ns']) for e in eps]
entries=sorted(int(f['fill_ns']) for f in raw['fill_audit'] if f['action']=='BTC_ENTRY')
rows=0;phases=Counter();skip_ohlc=0;begin=time.time()
for r in csv.DictReader(gzip.open(base/'minute-native-risk.csv.gz','rt')):
 rows+=1;phase=r['phase'];phases[phase]+=1;ns=int(r['close_available_ns'])
 if phase not in ('pre_quote_paired_close','post_btc_quote_paired_close','post_quote_paired_close'):continue
 if ns>1788220800000000000 or ns==1788220800000000000 and phase!='pre_quote_paired_close':continue
 for p in json.loads(r['native_positions_and_mark_ohlc_json']):
  if not p['instrument_id'].startswith('BTC'):continue
  idx=bisect.bisect_right(starts,ns)-1;assert idx>=0
  e=eps[idx];assert ns<=int(e['end_ns'])
  assert str(p['side'])==('3' if e['side']=='SELL' else '2')
  v=float(p['avg_px_open']);e['avg_entries'].add(v);ohlc=p['mark_ohlc'];c=float(ohlc['close']);short=e['side']=='SELL'
  adverse=max(0.,(c/v-1) if short else (1-c/v))*100
  if adverse>e['close_mae_pct']:e.update(close_mae_pct=adverse,close_max_ns=ns,close_max_phase=phase,close_max_entry_vwap=v,close_max_mark=c)
  e['close_samples']+=1
  # Prequote is before actual quote fills. Full previous minute is held only
  # if the last entry fill (incl. partial opening extension) predates bar open.
  if phase!='pre_quote_paired_close':continue
  baropen=int(r['bar_open_ms'])*1000000
  last_entry=entries[bisect.bisect_right(entries,ns)-1]
  if last_entry>baropen:skip_ohlc+=1;continue
  x=float(ohlc['high' if short else 'low']);adverse=max(0.,(x/v-1) if short else (1-x/v))*100
  if adverse>e['held_ohlc_mae_pct']:e.update(held_ohlc_mae_pct=adverse,ohlc_max_ns=ns,ohlc_max_entry_vwap=v,ohlc_max_mark=x)
  e['held_ohlc_samples']+=1
 if rows%600000==0:print('scanned',rows,'elapsed_s',round(time.time()-begin),flush=True)
assert rows==3153600
assert len(eps)==105 and all(e['close_samples'] and e['held_ohlc_samples'] for e in eps)
def quant(a,q):
 a=sorted(a);i=(len(a)-1)*q;k=math.floor(i);return a[k]+(a[min(k+1,len(a)-1)]-a[k])*(i-k)
def stats(es,k):
 a=[e[k] for e in es];return dict(n=len(a),mean=sum(a)/len(a),median=quant(a,.5),p75=quant(a,.75),p90=quant(a,.9),max=max(a))
summary={}
for label,es in [('all',eps),('long',[e for e in eps if e['side']=='BUY']),('short',[e for e in eps if e['side']=='SELL'])]:
 summary[label]={k:stats(es,k) for k in ('close_mae_pct','held_ohlc_mae_pct')}
 for label2,sub in [('completed_fill_net_wins',[e for e in es if float(e['confirmed_fill_net_ex_funding'])>0]),('completed_fill_net_losses',[e for e in es if float(e['confirmed_fill_net_ex_funding'])<0])]:
  summary[label][label2]={k:stats(sub,k) for k in ('close_mae_pct','held_ohlc_mae_pct')}
for e in eps:e['avg_entries']=sorted(e['avg_entries'])
result=dict(provenance=audit['provenance'],definition='Per episode maximum max(0, adverse BTC price movement / contemporaneous actual native position entry VWAP). LONG=(VWAP-price)/VWAP; SHORT=(price-VWAP)/VWAP. Unweighted arithmetic mean across episodes, not minute-weighted drawdown or portfolio PnL.',ohlc_definition='BTC-only saved high for SHORT / low for LONG; prequote native held-position phase and last entry fill <= bar-open. No entry-bar prefill extremes and no post-flat bars. Single-asset actual saved extremes; no cross-asset synchronisation inference.',close_definition='Exact saved minute close while native BTC position held at the observer phase, including actual post-entry close samples and pre-final-fill close samples. Three phases can duplicate a minute but cannot change maximum.',subset_limit='Win/loss labels are existing confirmed native fill weighted-entry fee-net attribution ex unknown funding; not independently authoritative native settled per-trade PnL. No new PnL calculation.',rows=rows,phases=dict(phases),episodes=105,all_completed=True,coverage={'close_samples':sum(e['close_samples'] for e in eps),'held_ohlc_samples':sum(e['held_ohlc_samples'] for e in eps),'episodes_with_both':105,'excluded_prefill_extrema':skip_ohlc,'input_minutes_per_asset':1051200,'entry_fills':len(entries),'multiple_vwap_episodes':sum(len(e['avg_entries'])>1 for e in eps)},summary=summary,calibration_scope='In-sample descriptive calibration only, not out-of-sample proof. Episode maxima are not available to trading decisions; online rule must use only current available price and native entry VWAP.',elapsed_seconds=round(time.time()-begin,2))
(out/'calibration-mae.json').write_text(json.dumps(result,indent=2)+'\n')
with open(out/'calibration-mae-episodes.csv','w') as f:
 fields=sorted(set().union(*(e.keys() for e in eps)));w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(eps)
print(json.dumps(result,indent=2))
