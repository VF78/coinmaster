"""Actual native exposure/entitlement cohorts; no execution or PnL reconstruction."""
import sys,csv,json
sys.dont_write_bytecode=True
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone,timedelta
import pyarrow.parquet as pq
R=Path(__file__).parent.resolve();ROOT=Path('/Users/vf/Documents/ChatGPT/Coinmaster');J=ROOT/'runtime/var/research-jobs/b-50-90-next-20261023';DATA=ROOT/'runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/inputs/data/normalized';sys.path.insert(0,str(J/'source-bd04c9b/runtime'))
from coinmaster.domain.wave_overlay import Candidate,DailyBar,Episode,WaveOverlayState,features_for,completed_wave_levels
UTC=timezone.utc;DAY=86400000000000
b=pq.read_table(DATA/'bybit-BTCUSDT-daily.parquet').to_pylist();sol={r['open_time_ms']:r for r in pq.read_table(DATA/'bybit-SOLUSDT-daily.parquet').to_pylist()};bars=[]
for row in b:
 t=row['open_time_ms'];s=sol.get(t)
 if s:bars.append(DailyBar(datetime.fromtimestamp(t/1000,UTC),datetime.fromtimestamp(t/1000,UTC)+timedelta(days=1),datetime.fromtimestamp(t/1000,UTC)+timedelta(days=1),float(row['open']),float(row['close']),float(s['close'])))
def utc(n):return datetime.fromtimestamp(int(n)/1e9,UTC).isoformat()
def write(name,rows):
 if not rows:return
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with (R/name).open('w',newline='') as f:
  w=csv.DictWriter(f,keys);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,separators=(',',':')) if isinstance(v,(dict,list)) else v for k,v in r.items()})
zero=[];cycles=[];aliases=[]
for receipt in sorted(R.glob('owner-*-receipt.json')):
 rr=json.load(receipt.open());recipe=rr['recipe'];a=json.load(Path(rr['artifact']).open());cand=Candidate(**a['config']['candidate']);features=features_for(bars,cand);domain=WaveOverlayState(cand);domain.set_execution_lots(btc=D('.001'),sol=D('.1'));ps=a['split_cover_audit']['parents'];entry={e['episode_id']:e for e in a['entry_sizing_audit']};events=a.get('next_band_audit',[]);fills=a['fill_audit']
 for n,p in enumerate(ps):
  e=entry[p['episode_id']];idx=int(p['decision_index']);waves=completed_wave_levels(bars,features,idx,cand,int(p['side']));refs=e['reference_target_lots'];refs=json.loads(refs) if isinstance(refs,str) else refs;omitted=e['omitted_zero_levels'];omitted=json.loads(omitted) if isinstance(omitted,str) else omitted
  ep=Episode(p['episode_id'],int(p['side']),0,float(p['planref_v1_beta']),btc_initial_qty=float(p['filled']),btc_open_qty=float(p['filled']),btc_target_basis_qty=float(p['quantity']),btc_reference_target_lots={int(k):v for k,v in refs.items()} if e['branch']=='PASSIVE_NET_ZERO_LEVELS' else {},btc_omitted_zero_levels=set(omitted));domain._ensure_btc_targets(ep)
  zerolevels=[k for k,w in enumerate(waves or ()) if w==0 and k not in omitted];original={k:ep.btc_tp_target_lots[k] for k in zerolevels};start=int(p['start_ns']);end=int(ps[n+1]['start_ns']) if n+1<len(ps) else 1788220800000000000;evs=[x for x in events if x.get('episode_id')==p['episode_id']];arms=[x for x in evs if x['event']=='Z_ARM'];triggers=[x for x in evs if x['event']=='Z_TRIGGER'];risk=[x for x in evs if x['event']=='RISK_FILL' and x.get('kind')=='Z'];ret={}
  for x in risk:
   for k,v in x.get('retired_lots',{}).items():ret[int(k)]=max(int(v),ret.get(int(k),0))
  terminal_leaves={int(k):int(v) for k,v in arms[-1].get('slots',{}).items()} if arms else {};reconstructed={k:terminal_leaves.get(k,0)+ret.get(k,0) for k in original} if arms else {};ordinary=[f for f in fills if start<=int(f['fill_ns'])<end and f['action']=='BTC_REDUCE' and f.get('reason')!='ZERO_RETRACE_RISK'];riskfills=[f for f in fills if start<=int(f['fill_ns'])<end and f.get('reason')=='ZERO_RETRACE_RISK'];soladds=[f for f in fills if start<=int(f['fill_ns'])<end and f['action']=='SOL_ADD']
  zero.append(dict(recipe=recipe,parent=n+1,episode_id=p['episode_id'],start_utc=utc(start),decision_index=idx,branch=e['branch'],actual_wave_levels=waves,omitted_levels=omitted,original_zero_target_lots_from_frozen_domain=original,reconstructed_initial_arm_slots=reconstructed,arm_alias_reconstruction_matches_native_entry_budget=(reconstructed==original) if arms else 'NOT_ARMED',arm_log_rows=len(arms),first_arm_ns=arms[0]['timestamp_ns'] if arms else '',last_confirmation_ns=arms[-1]['timestamp_ns'] if arms else '',trigger_count=len(triggers),trigger_ns=triggers[0]['timestamp_ns'] if triggers else '',G=arms[0]['G'] if arms else '',actual_risk_filled_BTC=str(sum((D(f['qty']) for f in riskfills),D(0))),actual_risk_fill_prices=[f['px'] for f in riskfills],actual_retired_lots=ret,SOL_right_fraction_retired={k:str(D(ret.get(k,0))/D(v)) if v else '0' for k,v in original.items()},ordinary_BTC_TP_after_guard=[dict(ns=f['fill_ns'],level=f['level'],qty=f['qty'],price=f['px']) for f in ordinary],actual_later_SOL_adds=[dict(ns=f['fill_ns'],level=f['level'],qty=f['qty'],price=f['px']) for f in soladds],not_armed_reason='RAW_NATIVE_STATE_ELIGIBILITY_NOT_FULLY_EXPORTED_DO_NOT_INVENT' if e['branch']=='MARKETABLE_FULL_ENTRY_FALLBACK' and original and not arms else ('NON_FULL_OR_NO_RETAINED_ZERO_SLOT' if not arms else ''),qualification='Actual native target reconstruction; retired rights are foregone entitlement, not guaranteed counterfactual SOL fills/profit'))
  if arms:aliases.append(dict(recipe=recipe,episode_id=p['episode_id'],actual_initial_target_lots=original,terminal_alias_leaves=terminal_leaves,actual_risk_retired_lots=ret,reconstructed_initial_lots=reconstructed,exact_equal=original==reconstructed))
 # Confirmed quantity/basis diagnostic only; all money/PnL/funding remains native.
 current=None;held=D(0);vwap=D(0);number=0
 for f in fills:
  if not f['instrument'].startswith('SOL'):continue
  q=D(f['qty']);px=D(f['px']);t=int(f['fill_ns'])
  if f['action']=='SOL_ADD':
   if held==0:
    number+=1;current=dict(recipe=recipe,cycle=number,start_ns=t,start_utc=utc(t),initial_actual_fill_price=str(px),total_actual_added_qty='0',risk_qty='0',risk_fills=[],ordinary_exits=[],actual_adds=[])
   vwap=(vwap*held+q*px)/(held+q);held+=q;current['total_actual_added_qty']=str(D(current['total_actual_added_qty'])+q);current['actual_adds'].append(dict(ns=t,qty=str(q),price=str(px),level=f['level']))
  else:
   if current is None:raise ValueError('SOL_REDUCTION_WITHOUT_NATIVE_CYCLE')
   if f.get('reason')=='SOL_DOMINANT_ADVERSE_RISK':
    current['risk_qty']=str(D(current['risk_qty'])+q);current['risk_fills'].append(dict(ns=t,qty=str(q),price=str(px),held_before=str(held),actual_fill_basis=str(vwap),fee=f['commission']))
   else:current['ordinary_exits'].append(dict(ns=t,qty=str(q),price=str(px),action=f['action'],reason=f.get('reason')))
   held-=q
   if held<0:raise ValueError('NATIVE_SOL_QUANTITY_NEGATIVE')
   if held==0:
    current.update(end_ns=t,end_utc=utc(t),actual_adds_after_first_risk=[x for x in current['actual_adds'] if current['risk_fills'] and x['ns']>current['risk_fills'][0]['ns']],signed_funding='UNKNOWN',net_cycle_PnL='VERIFIER_NATIVE_FILL_ACCOUNTING_NOT_RECONSTRUCTED_HERE');cycles.append(current);current=None;vwap=D(0)
write('owner-zero-guard-cohort.csv',zero);write('owner-sol-risk-cohort.csv',cycles);write('owner-Z-slot-alias-reconstruction.csv',aliases)
print(json.dumps(dict(zero_parent_rows=len(zero),SOL_cycles=len(cycles),armed_aliases=len(aliases),all_alias_initial_budgets_exact=all(x['exact_equal'] for x in aliases)),indent=2))
