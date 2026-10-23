"""Saved actual guarded-cohort price/timing evidence; no alternative account/PnL."""
import csv,json
from pathlib import Path
from decimal import Decimal as D,ROUND_CEILING,ROUND_FLOOR
from datetime import datetime,timezone
R=Path(__file__).parent.resolve();J=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/b-50-90-next-20261023');bars=[x for x in csv.DictReader((R/'owner-closed-bars.csv').open()) if x['symbol']=='BTCUSDT' and x['step_ns']=='14400000000000'];out=[]
def utc(ns):return datetime.fromtimestamp(int(ns)/1e9,timezone.utc).isoformat()
for recipe in ['Z','XZ','XZS']:
 receipt=R/('owner-'+recipe+'-receipt.json')
 if not receipt.exists():continue
 a=json.load(Path(json.load(receipt.open())['artifact']).open());ps=a['split_cover_audit']['parents'];fills=a['fill_audit'];events=a['next_band_audit']
 for day in ['2025-11-26','2026-08-19']:
  matches=[(i,p) for i,p in enumerate(ps) if utc(p['start_ns']).startswith(day)]
  if not matches:
   out.append(dict(recipe=recipe,case_day=day,status='NO_SAME_DAY_NATIVE_ENTRY_CALENDAR_DIFFERS'));continue
  for i,p in matches:
   start=int(p['start_ns']);end=int(ps[i+1]['start_ns']) if i+1<len(ps) else 1788220800000000000;entries=[f for f in fills if start<=int(f['fill_ns'])<end and f['action']=='BTC_ENTRY'];fees=sum((D(f['commission']) for f in entries),D(0));A=D(p['planref_v1_actual_blended_vwap']);P0=D(p['planref_v1_p0']);c=fees/D(p['filled']);side=int(p['side']);be=(A+c)/D('.99945') if side==1 else (A-c)/D('1.00055');G=max(P0,be) if side==1 else min(P0,be);G=(G/D('.1')).to_integral_value(rounding=ROUND_CEILING if side==1 else ROUND_FLOOR)*D('.1');ordinary=[f for f in fills if start<=int(f['fill_ns'])<end and f['action']=='BTC_REDUCE' and f.get('reason')!='ZERO_RETRACE_RISK'];firstTP=min((int(f['fill_ns']) for f in ordinary),default=end);favorable=[b for b in bars if start<int(b['close_ns'])<end and side*(D(b['close'])-G)>=D('.1')];arms=[e for e in events if e['event']=='Z_ARM' and e.get('episode_id')==p['episode_id']];risk=[f for f in fills if start<=int(f['fill_ns'])<end and f.get('reason')=='ZERO_RETRACE_RISK'];firstfav=int(favorable[0]['close_ns']) if favorable else None
   out.append(dict(recipe=recipe,case_day=day,episode_id=p['episode_id'],parent=i+1,status='ACTUAL_NATIVE_EPISODE',entry_utc=utc(start),G=str(G),actual_entry_VWAP=str(A),actual_P0=str(P0),first_favorable_closed4h_ns=firstfav,first_favorable_closed4h_utc=utc(firstfav) if firstfav else '',first_ordinary_TP_ns=firstTP,first_ordinary_TP_utc=utc(firstTP),favorable4h_before_ordinaryTP=bool(firstfav and firstfav<firstTP),actual_arm_log_rows=len(arms),first_actual_arm_ns=arms[0]['timestamp_ns'] if arms else '',actual_guard_fill_rows=risk,actual_ordinary_TP_rows=ordinary,qualification='Trade fee floor excludes funding; actual guard IOC price is not G; actual ordinary recovery is not counterfactual candidate profit'))
keys=list(dict.fromkeys(k for r in out for k in r))
with (R/'owner-critical-zero-counterexamples.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,keys);w.writeheader()
 for r in out:w.writerow({k:json.dumps(v,separators=(',',':')) if isinstance(v,(list,dict)) else v for k,v in r.items()})
print(json.dumps([{k:v for k,v in r.items() if not isinstance(v,list)} for r in out],indent=2))
