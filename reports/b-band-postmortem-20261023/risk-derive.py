"""Derive compact evidence from cached native snapshots only; no additional stream reads."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import json,csv
P=Path(__file__).parent; data=json.loads((P/'risk-native-extract.json').read_text());B=data['BTC_REGIME_REENTRY_BAND_05'];rows=[];eps=[];feas=[]
def iso(t):return datetime.fromtimestamp(int(t)/1e9,timezone.utc).isoformat()
def write(n,rs):
 keys=sorted(set().union(*(r.keys() for r in rs)))
 with (P/n).open('w',newline='') as f:
  w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rs)
for name,x in data.items():
 for i,e in enumerate(x['top3'],1):
  peak=D(e['peak']['equity']);trough=D(e['trough']['equity']);assert peak-trough==D(e['drawdown_amount']);assert abs((peak-trough)/peak*100-D(e['drawdown_peak_percent']))<D('1e-22')
  for k in ['peak','trough','recovery']:
   if not e.get(k):continue
   r=x['snapshots'][e[k]['timestamp_ns']];ps=json.loads(r['native_positions_and_mark_ohlc_json']);row=dict(recipe=name,interval=i,point=k,receipt_utc=iso(r['receipt_ns']),source_mark_utc=iso(r['source_quote_ns']),native_cash=r['cash'],native_equity=r['paired_close_equity'],native_aggregate_UPNL=str(D(r['paired_close_equity'])-D(r['cash'])))
   for a in ['BTC','SOL']:
    z=next((z for z in ps if z['instrument_id'].startswith(a)),None);row.update({a+'_side':('LONG' if z['side']=='2' else 'SHORT') if z else 'FLAT',a+'_qty':z['quantity'] if z else '0',a+'_avg_open':z['avg_px_open'] if z else '',a+'_unrounded_source_close':z['mark_ohlc']['close'] if z else '',a+'_gross_source_notional':str(D(z['quantity'])*D(z['mark_ohlc']['close'])) if z else '0'})
   rows.append(row)
  if name!='S0':
   for target in ['50','30']:feas.append(dict(interval=i,target_DD_percent=target,original_peak=str(peak),original_trough=str(trough),endpoint_gap_to_target=str(peak*(1-D(target)/100)-trough),basis='ENDPOINT_GAP_ONLY_NOT_INTERVENTION_PNL_OR_NATIVE_RESULT'))
 for e in x['excursions_ge20']:
  for th,r in e['thresholds'].items():
   ps=json.loads(r['native_positions_and_mark_ohlc_json']);eps.append(dict(recipe=name,peak_utc=e['peak_utc'],threshold_percent=th,first_cross_utc=r['utc'],actual_first_cross_DD=r['drawdown_percent'],full_excursion_DD=e['maxdd_percent'],recovery_utc=e.get('recovery_utc',''),positions_json=json.dumps(ps,separators=(',',':')),native_cash=r['cash'],native_equity=r['paired_close_equity']))
write('risk-top3-endpoints.csv',rows);write('risk-threshold-counterexamples.csv',eps);write('risk-target-gaps.csv',feas);write('risk-B-native-events.csv',B['fill_events'])
# Fixed unchanged-quantity mark movement diagnostics for I/II. Source close is quantized to instrument native mark precision inferred by exact aggregate checks, not a new account.
diag=[]
for i,e in enumerate(B['top3'][:2],1):
 a=B['snapshots'][e['peak']['timestamp_ns']];b=B['snapshots'][e['trough']['timestamp_ns']];aa=json.loads(a['native_positions_and_mark_ohlc_json']);bb=json.loads(b['native_positions_and_mark_ohlc_json']);s=D(0)
 for z in aa:
  y=next(y for y in bb if y['instrument_id']==z['instrument_id']);assert z['quantity']==y['quantity'];q=D(z['quantity'])*(1 if z['side']=='2' else -1);quant=D('.1') if z['instrument_id'].startswith('BTC') else D('.01');v=q*(D(y['mark_ohlc']['close']).quantize(quant)-D(z['mark_ohlc']['close']).quantize(quant));s+=v;diag.append(dict(interval=i,asset=z['instrument_id'][:3],fixed_quantity_mark_delta=str(v),basis='FIXED_UNCHANGED_NATIVE_INVENTORY_MARK_DIAGNOSTIC_NOT_ASSET_SETTLED_PNL',native_asset_signed_funding='UNKNOWN'))
 cash=D(b['cash'])-D(a['cash']);delta=D(b['paired_close_equity'])-D(a['paired_close_equity']);residual=delta-cash-s;assert abs(residual)<D('.000001');diag.append(dict(interval=i,asset='CASH_CHANGE_PLUS_CHECK',cash_delta=str(cash),native_equity_delta=str(delta),arithmetic_residual=str(residual)))
write('risk-fixed-state-decomposition.csv',diag)
print('DERIVED',len(rows),len(eps),len(diag))
oracles=[]
for i,e in enumerate(B['top3'],1):
 ex=next(z for z in B['excursions_ge20'] if z['peak_ns']==int(e['peak']['timestamp_ns']));r=ex['thresholds']['45'];t=B['snapshots'][e['trough']['timestamp_ns']];p=json.loads(r['native_positions_and_mark_ohlc_json']);q=json.loads(t['native_positions_and_mark_ohlc_json']);target_gap=D(e['peak']['equity'])*D('.5')-D(e['trough']['equity'])
 for a in p:
  b=next((b for b in q if b['instrument_id']==a['instrument_id']),None)
  if not b:continue
  quant=D('.1') if a['instrument_id'].startswith('BTC') else D('.01');v=D(a['quantity'])*(1 if a['side']=='2' else -1)*(D(b['mark_ohlc']['close']).quantize(quant)-D(a['mark_ohlc']['close']).quantize(quant));unchanged=a['side']==b['side'] and a['quantity']==b['quantity'];fraction=target_gap/-v if unchanged and v<0 else None
  oracles.append(dict(interval=i,first45_utc=r['utc'],first45_DD_percent=r['drawdown_percent'],asset=a['instrument_id'][:3],current_qty=a['quantity'],first45_side=a['side'],fixed_current_qty_mark_tail=str(v),actual_inventory_unchanged_to_trough=unchanged,original_trough_to50_floor_gap=str(target_gap),oracle_minimum_losing_leg_trim_fraction_before_costs=str(fraction) if fraction is not None else 'NOT_IDENTIFIABLE_FROM_UNCHANGED_ACTUAL_INVENTORY',oracle_trim_quantity=str(D(a['quantity'])*fraction) if fraction is not None else '',feasible_fraction_le1=(fraction is not None and fraction<=1),claim='RETROSPECTIVE_ORACLE_BOUND_ONLY_NOT_CAUSAL_PERFORMANCE',DD30_at_first45='ALREADY_BREACHED'))
write('risk-first45-oracle-bounds.csv',oracles)
