"""Cached diagnostics only; never rereads receipt streams."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import json,csv,hashlib
P=Path(__file__).parent;x=json.loads((P/'risk-profit-guard-native-cache.json').read_text());risk=json.loads((P/'risk-native-extract.json').read_text())['BTC_REGIME_REENTRY_BAND_05'];cs=x['cycles']
def iso(t):return datetime.fromtimestamp(int(t)/1e9,timezone.utc).isoformat() if t else ''
def write(n,rs):
 keys=sorted(set().union(*(r.keys() for r in rs)))
 with (P/n).open('w',newline='') as f:w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rs)
for c in cs:
 f=c['events'][-1]
 if f['action'] in ('BTC_REDUCE','SOL_EXIT','SOL_HALF_EXIT') and c['final_close_price_label']=='FAVORABLE_GROSS':
  ft=int(f['fill_ns']);c['first_profitable_ordinary_reduce_ns']=min(c['first_profitable_ordinary_reduce_ns'] or ft,ft)
summary={}
for a in ['BTC','SOL']:
 ss=[c for c in cs if c['asset']==a];gs=[c for c in ss if c['guard']];summary[a]=dict(cycles=len(ss),armed_cycles=sum(any(p['armed_ns'] is not None for p in c['phases']) for c in ss),guard_opportunities=len(gs),opportunity_final_favorable_gross=sum(c['final_close_price_label']=='FAVORABLE_GROSS' for c in gs),opportunity_later_profitable_ordinary_reduce=sum(c['first_profitable_ordinary_reduce_ns'] is not None for c in gs),native_net_winners='UNKNOWN_PER_CYCLE_PNL_AND_SIGNED_FUNDING')
# Associate each opportunity with independently saved baseline excursions, without recomputing equity.
counters=[]
for c in cs:
 g=c['guard']
 if not g:continue
 ex=next((e for e in risk['excursions_ge20'] if e['peak_ns']<=g['source_ns']<=e.get('recovery_ns',1788220800000000000)),None)
 counters.append(dict(asset=c['asset'],cycle=c['cycle'],start_utc=iso(c['start_ns']),guard_source_utc=g['source_utc'],guard_receipt_utc=g['receipt_utc'],armed_utc=g['armed_utc'],actual_first_return_close=g['actual_first_closed_return_mark'],gross_vwap=g['native_vwap'],normalized_vwap=g['gross_vwap_normalized_tick'],trim_qty=g['trim20_lot_normalized'],final_close_price_label=c['final_close_price_label'],later_profitable_ordinary_reduce_utc=iso(c['first_profitable_ordinary_reduce_ns']),baseline_excursion_peak_utc=ex['peak_utc'] if ex else '',baseline_excursion_DD=ex['maxdd_percent'] if ex else '',baseline_excursion_recovered_utc=ex.get('recovery_utc','') if ex else '',native_net_winner='UNKNOWN',SOL_parent_mapping=c['parent_mapping']))
write('risk-profit-guard-counterexamples.csv',counters)
# All parent cycles overlapping D's actual full independent excursion, including parent entered before peak.
a=int(risk['top3'][2]['peak']['timestamp_ns']);b=int(risk['top3'][2]['trough']['timestamp_ns']);dr=[]
for c in cs:
 if c['asset']=='BTC' and c['start_ns']<=b and c.get('end_ns',1788220800000000000)>=a:
  dr.append(dict(cycle=c['cycle'],entry_utc=iso(c['start_ns']),completion_utc=iso(c['completion_ns']),end_utc=iso(c.get('end_ns')),side=c['side'],post_complete_entry_max_favorable_percent=c['max_phase_favorable_percent'],armed_before_any_profitable_ordinary_reduce=any(p['armed_ns'] is not None for p in c['phases']),guard_opportunity=c['guard'] is not None,guard_utc=c['guard']['source_utc'] if c['guard'] else '',final_close_price_label=c['final_close_price_label'],first_profitable_ordinary_reduce_utc=iso(c['first_profitable_ordinary_reduce_ns']),native_net_winner='UNKNOWN'))
write('risk-profit-guard-D-parents.csv',dr)
x['summary']=summary;x['finalization_note']='Final profitable ordinary close recognized against last actual native VWAP; closed-cycle net PnL UNKNOWN. No additional stream read.'
(P/'risk-profit-guard-native-cache.json').write_text(json.dumps(x,indent=2)+'\n')
# Fix compact existing cycle rows after closure classification without repeating stream.
p=P/'risk-profit-guard-cycles.csv';rs=list(csv.DictReader(p.open()))
for row in rs:
 c=next(c for c in cs if c['asset']==row['asset'] and c['cycle']==int(row['cycle']));row['first_profitable_ordinary_reduce_ns']=c['first_profitable_ordinary_reduce_ns'] or '';row['profitable_ordinary_reduce_utc']=iso(c['first_profitable_ordinary_reduce_ns'])
write(p.name,rs)
print(json.dumps(summary,indent=2));print(json.dumps(dr,indent=2));print('recovered opportunity counterexamples',sum(bool(r['baseline_excursion_recovered_utc']) for r in counters))
