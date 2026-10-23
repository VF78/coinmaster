"""Small saved native event/intent joins only. No trace scan, engine or PnL model."""
import csv,json
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
R=Path(__file__).parent.resolve();BASE=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs');J=BASE/'b-50-90-next-20261023';OLD=BASE/'sol-conditional-hedge-btc-band-20261023/BTC_REGIME_REENTRY_BAND_05/result'
def readart(folder):return json.load(next(x for x in folder.glob('v0*.json') if not x.name.endswith('-raw-native.json')).open())
def write(name,rows):
 if not rows:return
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with (R/name).open('w',newline='') as f:
  w=csv.DictWriter(f,keys);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,separators=(',',':')) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def utc(ns):return datetime.fromtimestamp(int(ns)/1e9,timezone.utc).isoformat()
base=readart(OLD);bp=base['split_cover_audit']['parents'];allactions=[];wait=[];rights=[];mechanics=[];critical=[]
windows={'A':('2024-10-03T04:01:00+00:00','2024-10-03T15:45:00+00:00'),'C':('2025-11-26T12:23:00+00:00','2025-11-28T14:29:00+00:00'),'D':('2026-07-06T13:40:00+00:00','2026-08-19T06:14:00+00:00')}
for receiptpath in sorted(R.glob('owner-*-receipt.json')):
 receipt=json.load(receiptpath.open());recipe=receipt['recipe'];a=json.load(Path(receipt['artifact']).open());events=a.get('next_band_audit',[]);parents=a['split_cover_audit']['parents'];pmap={p['episode_id']:p for p in parents};fills=a['fill_audit'];arms={e['episode_id']:e for e in events if e['event']=='Z_ARM'}
 final_retired={}
 for ev in events:
  if ev['event']=='RISK_FILL' and ev.get('kind')=='Z':
   d=final_retired.setdefault(ev['episode_id'],{})
   for level,lots in ev.get('retired_lots',{}).items():d[str(level)]=max(int(lots),d.get(str(level),0))
 native_risk=[f for f in fills if f.get('reason') in ('ZERO_RETRACE_RISK','SOL_DOMINANT_ADVERSE_RISK')];risk_events=[e for e in events if e['event']=='RISK_FILL'];native_qty=sum((D(f['qty']) for f in native_risk),D(0));event_qty=sum((D(str(e['quantity'])) for e in risk_events),D(0));native_by_asset={asset:str(sum((D(f['qty']) for f in native_risk if f['instrument'].startswith(asset)),D(0))) for asset in ('BTC','SOL')};event_by_asset={asset:str(sum((D(str(e['quantity'])) for e in risk_events if e.get('kind')==kind),D(0))) for asset,kind in (('BTC','Z'),('SOL','S'))}
 # Monetary facts are taken from native fill_audit. This equality only checks joins.
 mechanics.append(dict(recipe=recipe,native_risk_fill_count=len(native_risk),policy_risk_fill_receipts=len(risk_events),native_risk_BTC_units=native_by_asset['BTC'],native_risk_SOL_units=native_by_asset['SOL'],policy_risk_BTC_units=event_by_asset['BTC'],policy_risk_SOL_units=event_by_asset['SOL'],actual_fill_qty_equal=all(D(native_by_asset[asset])==D(event_by_asset[asset]) for asset in native_by_asset),Z_triggers=sum(e['event']=='Z_TRIGGER' for e in events),S_triggers=sum(e['event']=='S_TRIGGER' for e in events),first_risk_fill_utc=utc(min(int(f['fill_ns']) for f in native_risk)) if native_risk else '',no_extra_engine=True))
 for e in events:
  ns=int(e['timestamp_ns']);kind=e.get('kind');event=e['event'];row=dict(recipe=recipe,event=event,timestamp_ns=ns,utc=utc(ns),timestamp_basis='ACCEPTED_D1_ASOF_NOT_EXECUTION' if event=='WAIT_D1_COUNT' else 'NATIVE_ACTUAL_DECISION_OR_FILL_RECEIPT',**{k:v for k,v in e.items() if k not in ('event','timestamp_ns')})
  if event in ('E4_ENTRY_INTENT','Z_ARM','Z_TRIGGER','S_TRIGGER','RISK_CHILD','RISK_FILL','RISK_PREEMPT','S_BLOCK_INCREASE'):allactions.append(row)
  if event=='RISK_FILL':
   reason='ZERO_RETRACE_RISK' if kind=='Z' else 'SOL_DOMINANT_ADVERSE_RISK';matches=[f for f in native_risk if int(f['fill_ns'])==ns and f['reason']==reason];row['native_fill_prices']=[f['px'] for f in matches];row['native_fill_quantities']=[f['qty'] for f in matches];row['native_fees']=str(sum((D(f['commission']) for f in matches),D(0)));row['ordinary_TP_or_SOL_half_done']='NO_SEPARATE_RISK_OWNER'
   if kind=='Z':
    arm=arms.get(e['episode_id'],{});slots=arm.get('slots',{})
    for level,retired in e.get('retired_lots',{}).items():rights.append(dict(recipe=recipe,episode_id=e['episode_id'],risk_fill_ns=ns,level=level,cumulative_actual_risk_retired_lots=retired,logged_terminal_slot_leaves=slots.get(str(level),slots.get(level)),initial_zero_slot_lots_reconstructed=int(slots.get(str(level),slots.get(level,0)))+final_retired.get(e['episode_id'],{}).get(str(level),0),SOL_rights_granted_by_risk_fill=0,meaning='Initial budget reconstructed from terminal task leaves plus actual retired lots because ARM slot dict aliases mutable task; foregone entitlement is not proof of a counterfactual SOL order/fill/profit'))
 for idx,p in enumerate(parents):
  if idx>=len(bp) or (int(p['start_ns']),p['side'])!=(int(bp[idx]['start_ns']),bp[idx]['side']):
   reference=bp[idx] if idx<len(bp) else {};ep=p['episode_id'];e4=next((e for e in events if e['event']=='E4_ENTRY_INTENT' and e['episode_id']==ep),{});wait.append(dict(recipe=recipe,first_divergent_parent_index=idx+1,actual_entry_ns=p['start_ns'],actual_entry_utc=utc(p['start_ns']),actual_side=p['side'],actual_qty=p['filled'],actual_P0=p.get('planref_v1_p0'),reference_B_entry_ns=reference.get('start_ns'),reference_B_side=reference.get('side'),reference_B_qty=reference.get('filled'),permission_signal_asof_ns=e4.get('signal_asof_ns'),permission_decision_time_ns=e4.get('timestamp_ns'),daily_signal_asof_ns=e4.get('daily_asof_ns'),interpretation='First ordered calendar divergence; later paths not forced onto baseline entries'));break
 for label,(peak,trough) in windows.items():
  peakns=int(datetime.fromisoformat(peak).timestamp()*1e9);troughns=int(datetime.fromisoformat(trough).timestamp()*1e9);risk=[f for f in native_risk if peakns<=int(f['fill_ns'])<=troughns];critical.append(dict(recipe=recipe,fixed_B_risk_window=label,baseline_peak_utc=peak,baseline_trough_utc=trough,risk_fills_before_baseline_trough=len(risk),actual_BTC_risk_units=str(sum((D(f['qty']) for f in risk if f['instrument'].startswith('BTC')),D(0))),actual_SOL_risk_units=str(sum((D(f['qty']) for f in risk if f['instrument'].startswith('SOL')),D(0))),actual_risk_fill_receipts=[dict(ns=f['fill_ns'],price=f['px'],qty=f['qty'],reason=f['reason']) for f in risk],qualification='Actual units/actions only; candidate peak/calendar may differ, no alternative TOTAL'))
write('owner-action-mechanism.csv',allactions);write('owner-risk-retirement-rights.csv',rights);write('owner-wait-first-divergence.csv',wait);write('owner-activation-mechanical-checks.csv',mechanics);write('owner-critical-window-action-ledger.csv',critical)
print(json.dumps(mechanics,indent=2))
