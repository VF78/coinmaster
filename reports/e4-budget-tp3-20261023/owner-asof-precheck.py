"""Read archived E4 native snapshots; stress sizing only, never PnL simulation."""
import csv,gzip,json,bisect
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import pyarrow.parquet as pq
R=Path(__file__).parent
ROOT=Path('/Users/vf/Documents/ChatGPT/Coinmaster')
E=ROOT/'runtime/var/research-jobs/b-50-90-next-20261023/E4/result'
DATA=ROOT/'runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/inputs/data'
DAY=86400000000000
atrs={}
for asset in ('BTC','SOL'):
 rows=pq.read_table(DATA/f'normalized/bybit-{asset}USDT-daily.parquet').to_pylist()
 previous=atr=None;trs=[];out={}
 for row in rows:
  close=float(row['close']);h=float(row['high']);l=float(row['low'])
  if previous is not None:
   tr=max(h-l,abs(h-previous),abs(l-previous))
   if atr is None:
    trs.append(tr)
    if len(trs)==14:atr=sum(trs)/14
   else:atr=(13*atr+tr)/14
  ns=(row['open_time_ms']+86400000)*1000000
  if atr is not None:out[ns]=D(str(atr))
  previous=close
 atrs[asset]=out
result=json.loads(next(x for x in E.glob('v0*.json') if not x.name.endswith('raw-native.json')).read_text())
interesting={int(x['fill_ns']) for x in result['fill_audit'] if x['action'] in ('SOL_ADD','BTC_REDUCE')}
peak=D(10000);selected=[];first={};counts={};fee=D('.00055')
with gzip.open(E/'minute-native-settled-receipts.csv.gz','rt') as f:
 for row in csv.DictReader(f):
  ns=int(row['source_quote_ns']);equity=D(row['paired_close_equity']);peak=max(peak,equity)
  date=datetime.fromtimestamp(ns/1e9,timezone.utc).isoformat()
  if date[:7] not in ('2024-10','2025-01','2025-09'):continue
  positions=json.loads(row['native_positions_and_mark_ohlc_json'])
  by={x['instrument_id'][:3]:x for x in positions}
  if 'SOL' not in by:continue
  qs=D(by['SOL']['quantity']);qb=D(by['BTC']['quantity']) if 'BTC' in by else D(0)
  daily=ns//DAY*DAY
  ab=atrs['BTC'].get(daily);ass=atrs['SOL'].get(daily)
  if ab is None or ass is None:continue
  sm=D(by['SOL']['mark_ohlc']['close']);bm=D(by['BTC']['mark_ohlc']['close']) if 'BTC' in by else D(0)
  rb=qb*(ab+fee*(bm+ab));cap=max(D(0),(equity-D('.55')*peak-rb-fee*sm*qs)/(ass*(1+fee)))
  cap=(cap//D('.1'))*D('.1');dd=1-equity/peak
  trigger=dd>=D('.35') and qs*ass>qb*ab and cap<qs
  cohort=date[:7]
  if trigger:counts[cohort]=counts.get(cohort,0)+1
  if ns not in interesting and not (trigger and cohort not in first):continue
  out=dict(utc=date,native_equity=str(equity),global_peak=str(peak),DD_percent=str(dd*100),BTC_qty=str(qb),SOL_qty=str(qs),BTC_ATR14=str(ab),SOL_ATR14=str(ass),BTC_stress=str(qb*ab),SOL_stress=str(qs*ass),BTC_reserve=str(rb),admissible_SOL_remaining=str(cap),cut_qty=str(max(D(0),qs-cap)),trigger=trigger,source_quote_ns=ns,receipt_ns=row['receipt_ns'],selection='FIRST_BUDGET_TRIGGER_IN_MONTH' if trigger and cohort not in first else 'ACTUAL_FILL_MINUTE')
  if trigger and cohort not in first:first[cohort]=out
  selected.append(out)
with (R/'owner-asof-snapshots.csv').open('w') as f:
 w=csv.DictWriter(f,list(selected[0]));w.writeheader();w.writerows(selected)
summary=dict(status='ARCHIVED_NATIVE_ASOF_STRESS_SIZING_ONLY',historical_engines_started=0,first_trigger_by_requested_month=first,archived_trigger_minutes_by_month=counts,selected_snapshots=len(selected),qualification='Saved settled native inventory/equity and causal completed-D1 ATR; original archived path only. Native ACK/queued ownership unavailable in receipt, so these are potential size snapshots, not executable order claims or alternative PnL. No parameter optimization, future extrema, or policy path simulation.')
(R/'owner-asof-precheck.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
