"""Descriptive paired actual entry-day price contrast; never a counterfactual TOTAL."""
import json,csv
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
R=Path(__file__).parent.resolve();BASE=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs');bp=BASE/'sol-conditional-hedge-btc-band-20261023/BTC_REGIME_REENTRY_BAND_05/result';b=json.load(next(x for x in bp.glob('v0*.json') if not x.name.endswith('-raw-native.json')).open());parents=b['split_cover_audit']['parents'];byidx={int(p['decision_index']):(n,p) for n,p in enumerate(parents)};out=[]
def utc(t):return datetime.fromtimestamp(int(t)/1e9,timezone.utc).isoformat()
for recipe in ['Z','XZ','XZS']:
 receipt=R/('owner-'+recipe+'-receipt.json')
 if not receipt.exists():continue
 a=json.load(Path(json.load(receipt.open())['artifact']).open());ps=a['split_cover_audit']['parents'];fills=a['fill_audit']
 for i,p in enumerate(ps):
  start=int(p['start_ns']);end=int(ps[i+1]['start_ns']) if i+1<len(ps) else 1788220800000000000;guard=[f for f in fills if start<=int(f['fill_ns'])<end and f.get('reason')=='ZERO_RETRACE_RISK']
  if not guard:continue
  reference=byidx.get(int(p['decision_index']))
  for level in [0,1,2]:
   retired=max([int(e.get('retired_lots',{}).get(str(level),0)) for e in a['next_band_audit'] if e.get('episode_id')==p['episode_id'] and e['event']=='RISK_FILL' and e.get('kind')=='Z'] or [0])
   if not retired:continue
   row=dict(recipe=recipe,episode_id=p['episode_id'],actual_entry_utc=utc(start),actual_retired_zero_level=level,actual_risk_retired_qty=str(D(retired)*D('.001')),actual_guard_fill_ns=[f['fill_ns'] for f in guard],actual_guard_prices=[f['px'] for f in guard],actual_candidate_entry_VWAP=p['planref_v1_actual_blended_vwap'],actual_future_SOL_adds_same_level=[f for f in fills if start<=int(f['fill_ns'])<end and f['action']=='SOL_ADD' and f['level']==str(level)],qualification='Different actual capital/quantities; unit price contrast descriptive, not recoverable profit or alternative native account; signed funding UNKNOWN')
   if reference:
    j,q=reference;rend=int(parents[j+1]['start_ns']) if j+1<len(parents) else 1788220800000000000;old=[f for f in b['fill_audit'] if int(q['start_ns'])<=int(f['fill_ns'])<rend and f['action']=='BTC_REDUCE' and f['level']==str(level)];row.update(reference_B_entry_utc=utc(q['start_ns']),reference_B_entry_VWAP=q['planref_v1_actual_blended_vwap'],reference_B_actual_zero_TP_fills=old)
    if old:
     exitpx=sum(D(f['qty'])*D(f['px']) for f in old)/sum(D(f['qty']) for f in old);gpx=sum(D(f['qty'])*D(f['px']) for f in guard)/sum(D(f['qty']) for f in guard);row['reference_B_actual_zero_exit_VWAP']=str(exitpx);row['descriptive_later_B_exit_minus_guard_per_BTC_signed']=str(int(p['side'])*(exitpx-gpx));row['reference_B_zero_trade_gross_per_BTC']=str(int(q['side'])*(exitpx-D(q['planref_v1_actual_blended_vwap'])))
   out.append(row)
keys=list(dict.fromkeys(k for r in out for k in r))
with (R/'owner-zero-profitable-fallback-contrast.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,keys);w.writeheader()
 for r in out:w.writerow({k:json.dumps(v,separators=(',',':')) if isinstance(v,(dict,list)) else v for k,v in r.items()})
print('actual retired level contrasts',len(out),'allforegonefutureSOLleveladds0',all(not r['actual_future_SOL_adds_same_level'] for r in out))
