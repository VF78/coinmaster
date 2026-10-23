"""One bounded B native receipt scan. Fixed 1%/gross-return/20% proposal diagnostic only."""
from pathlib import Path
from decimal import Decimal as D, ROUND_DOWN
from datetime import datetime,timezone
import csv,gzip,json,hashlib,bisect,collections
ROOT=Path(__file__).resolve().parents[2];S=ROOT/'reports/sol-conditional-hedge-btc-band-20261023';P=Path(__file__).parent
spec=json.loads((S/'owner-BTC_REGIME_REENTRY_BAND_05-receipt.json').read_text());d=json.loads(Path(spec['artifact']).read_text());fills=d['fill_audit'];native=list(csv.DictReader(Path(d['execution_artifacts']['fills']['path']).open()));assert len(fills)==len(native)
def ns(s):return int(datetime.fromisoformat(s).timestamp()*1e9)
def iso(n):return datetime.fromtimestamp(int(n)/1e9,timezone.utc).isoformat() if n is not None else ''
native_by_key=collections.defaultdict(list)
for n in native:native_by_key[(n['instrument_id'],ns(n['ts_last']),D(n['filled_qty']),D(n['avg_px']).quantize(D('.0001')))].append(n)
cycles=[];byasset={};active={};q={};counts={'BTC':0,'SOL':0}
for f in fills:
 n=native_by_key[(f['instrument'],int(f['fill_ns']),D(f['qty']),D(f['px']).quantize(D('.0001')))].pop(0)
 assert D(f['qty'])==D(n['filled_qty']) and abs(D(f['px'])-D(n['avg_px']))<D('.000001') and int(f['fill_ns'])==ns(n['ts_last'])
 a=f['instrument'][:3];t=int(f['fill_ns']);sgn=1 if n['side']=='BUY' else -1
 if a not in active:
  assert f['action'] in ('BTC_ENTRY','SOL_ADD');counts[a]+=1;c=dict(asset=a,cycle=counts[a],start_ns=t,side=sgn,events=[],native_net_winner='UNKNOWN_NATIVE_PER_CYCLE_PNL_NOT_EXPORTED',signed_asset_funding='UNKNOWN',phases=[],max_phase_favorable_percent='0',guard=None,first_profitable_ordinary_reduce_ns=None,final_close_price_label='UNKNOWN');active[a]=c;q[a]=D(0);cycles.append(c)
 c=active[a];c['events'].append(dict(f,native_side=n['side'],native_status=n['status'],native_requested=n['quantity']))
 q[a]+=D(f['qty'])*sgn
 if q[a]==0:c['end_ns']=t;del active[a]
for c in cycles:
 if c['asset']=='BTC':
  parent=next(p for p in d['split_cover_audit']['parents'] if p['start_ns']==c['start_ns']);assert D(parent['quantity'])==D(parent['filled']);c['completion_ns']=max(int(f['fill_ns']) for f in c['events'] if f['action']=='BTC_ENTRY');c['parent_mapping']='EXACT_FULL_BTC_PARENT';c['episode_id']=parent['episode_id']
 else:c['completion_ns']=c['start_ns'];c['parent_mapping']='NATIVE_TERMINAL_SOL_INCREASE_PHASES_STRATEGY_PARENT_SEMANTICS_UNKNOWN'
 byasset.setdefault(c['asset'],[]).append(c)
idx={'BTC':0,'SOL':0};lastpos={};nrows=0
for r in csv.DictReader(gzip.open(d['minute_risk_observations']['settled_native_close_receipts']['trace_path'],'rt')):
 nrows+=1;t=int(r['source_quote_ns']);positions={z['instrument_id'][:3]:z for z in json.loads(r['native_positions_and_mark_ohlc_json'])}
 for a,cs in byasset.items():
  while idx[a]<len(cs) and t>=cs[idx[a]].get('end_ns',1788220800000000001):
   c=cs[idx[a]];z=lastpos.get(a)
   if z:
    f=c['events'][-1];prof=(D(f['px'])-D(z['avg_px_open']))*c['side'];c['final_close_price_label']='FAVORABLE_GROSS' if prof>0 else 'ADVERSE_OR_FLAT_GROSS';c['final_close_reference_native_vwap']=z['avg_px_open']
   idx[a]+=1
  if idx[a]>=len(cs):continue
  c=cs[idx[a]]
  if not c['start_ns']<=t<c.get('end_ns',1788220800000000001):continue
  # Discover ordinary reductions causally against previous native VWAP.
  zprev=lastpos.get(a)
  if zprev and c['first_profitable_ordinary_reduce_ns'] is None:
   for f in c['events']:
    ft=int(f['fill_ns'])
    if int(r['source_quote_ns'])-60000000000<ft<=t and f['action'] in ('BTC_REDUCE','SOL_EXIT','SOL_HALF_EXIT') and (D(f['px'])-D(zprev['avg_px_open']))*c['side']>0:c['first_profitable_ordinary_reduce_ns']=ft;break
  z=positions.get(a)
  if not z or t<c['completion_ns']:continue
  avg=D(z['avg_px_open']);mark=D(z['mark_ohlc']['close']).quantize(D('.1') if a=='BTC' else D('.01'));phasekey=(z['avg_px_open'],z['side'])
  if not c['phases'] or tuple(c['phases'][-1]['key'])!=phasekey:
   c['phases'].append(dict(key=list(phasekey),start_ns=t,actual_vwap=str(avg),max_favorable_percent='0',armed_ns=None));ph=c['phases'][-1]
  ph=c['phases'][-1];ret=(mark/avg-1)*c['side']*100
  ph['max_favorable_percent']=str(max(D(ph['max_favorable_percent']),ret));c['max_phase_favorable_percent']=str(max(D(c['max_phase_favorable_percent']),ret))
  eligible=c['first_profitable_ordinary_reduce_ns'] is None
  if eligible and ph['armed_ns'] is None and ret>=1:ph['armed_ns']=t
  if eligible and c['guard'] is None and ph['armed_ns'] is not None and t>ph['armed_ns'] and ret<=0:
   step=D('.001') if a=='BTC' else D('.1');trim=(D(z['quantity'])*D('.2')/step).to_integral_value(rounding=ROUND_DOWN)*step;tick=D('.1') if a=='BTC' else D('.01');wire=avg.quantize(tick)
   c['guard']=dict(source_ns=t,source_utc=iso(t),receipt_ns=r['receipt_ns'],receipt_utc=iso(r['receipt_ns']),armed_ns=ph['armed_ns'],armed_utc=iso(ph['armed_ns']),native_vwap=str(avg),gross_vwap_normalized_tick=str(wire),actual_first_closed_return_mark=str(mark),actual_remaining_qty=z['quantity'],trim20_lot_normalized=str(trim),hypothetical_fee055_at_normalized_vwap=str(trim*wire*D('.00055')),native_equity=r['paired_close_equity'],phase_index=len(c['phases'])-1,causal_closed_minute_does_not_guarantee_vwap_fill=True)
 lastpos=positions
assert nrows==1051199
# Final terminal native close remains outside interval receipt scan; label against last actual native snapshot.
for a,cs in byasset.items():
 if idx[a]<len(cs):
  c=cs[idx[a]];z=lastpos.get(a)
  if z and c.get('end_ns')==1788220800000000000:
   f=c['events'][-1];c['final_close_price_label']='FAVORABLE_GROSS' if (D(f['px'])-D(z['avg_px_open']))*c['side']>0 else 'ADVERSE_OR_FLAT_GROSS';c['final_close_reference_native_vwap']=z['avg_px_open']
# Endpoint-oracle scale using only cached top3 actual trough state, never altered native cash.
x=json.loads((P/'risk-native-extract.json').read_text())['BTC_REGIME_REENTRY_BAND_05'];oracle=[]
for i,e in enumerate(x['top3'],1):
 tr=int(e['trough']['timestamp_ns']);pos=json.loads(x['snapshots'][e['trough']['timestamp_ns']]['native_positions_and_mark_ohlc_json']);gap=D(e['peak']['equity'])*D('.5')-D(e['trough']['equity'])
 for z in pos:
  a=z['instrument_id'][:3];c=next(c for c in byasset[a] if c['start_ns']<=tr<c.get('end_ns',1788220800000000001));g=c['guard'];row=dict(interval=i,asset=a,cycle=c['cycle'],guard_opportunity_before_trough=bool(g and g['source_ns']<=int(x['snapshots'][e['trough']['timestamp_ns']]['source_quote_ns'])),DD50_endpoint_gap=str(gap),basis='CONDITIONAL_FIXED_STATE_GROSS_VWAP_EXIT_NOT_NATIVE_TOTAL_OR_POLICY_REPLAY')
  if row['guard_opportunity_before_trough']:
   qty=D(g['trim20_lot_normalized']);exitpx=D(g['gross_vwap_normalized_tick']);mark=D(z['mark_ohlc']['close']).quantize(D('.1') if a=='BTC' else D('.01'));contribution=qty*(exitpx-mark)*c['side'];fee=qty*exitpx*D('.00055');row.update(trim_qty=str(qty),gross_fixed_trough_difference=str(contribution),hypothetical_exit_fee=str(fee),net_fixed_trough_difference=str(contribution-fee),fraction_of50gap=str((contribution-fee)/gap),requires_trim_inventory_survival_and_no_readds=True)
  oracle.append(row)
def write(n,rs):
 keys=sorted(set().union(*(r.keys() for r in rs)))
 with (P/n).open('w',newline='') as f:
  w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rs)
rows=[]
for c in cycles:
 row={k:v for k,v in c.items() if k not in ('events','phases','guard')};row.update(start_utc=iso(c['start_ns']),end_utc=iso(c.get('end_ns')),phase_count=len(c['phases']),armed_phase_count=sum(p['armed_ns'] is not None for p in c['phases']),profitable_ordinary_reduce_utc=iso(c['first_profitable_ordinary_reduce_ns']),guard_opportunity=c['guard'] is not None,events_json=json.dumps(c['events'],separators=(',',':')))
 if c['guard']:row.update({'guard_'+k:v for k,v in c['guard'].items()})
 rows.append(row)
write('risk-profit-guard-cycles.csv',rows);write('risk-profit-guard-oracle-trough.csv',oracle)
summary={a:dict(cycles=len(cs),armed_cycles=sum(any(p['armed_ns'] is not None for p in c['phases']) for c in cs),guard_opportunities=sum(c['guard'] is not None for c in cs),opportunity_final_favorable_gross=sum(c['guard'] is not None and c['final_close_price_label']=='FAVORABLE_GROSS' for c in cs),opportunity_later_profitable_ordinary_reduce=sum(c['guard'] is not None and c['first_profitable_ordinary_reduce_ns'] is not None for c in cs),net_winners='UNKNOWN_NATIVE_PER_CYCLE_PNL_NOT_EXPORTED') for a,cs in byasset.items()}
(P/'risk-profit-guard-native-cache.json').write_text(json.dumps(dict(summary=summary,cycles=cycles,oracle=oracle,rows=nrows,artifact_sha256=hashlib.sha256(Path(spec['artifact']).read_bytes()).hexdigest(),trace_sha256=hashlib.sha256(Path(d['minute_risk_observations']['settled_native_close_receipts']['trace_path']).read_bytes()).hexdigest(),proposal='Fixed >=1% favorable after completion, later closed-minute grossVWAP return,20% remaining trim once per cycle; no readd. SOL VWAP phase reset avoids pooling different actual average entries; strategy parent semantics UNKNOWN.'),indent=2)+'\n')
print(json.dumps(summary,indent=2));print(json.dumps(oracle,indent=2))
