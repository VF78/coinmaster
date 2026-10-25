"""Targeted saved native orders/audits/account snapshots and quote reconstruction; engine imports0."""
import json,csv,gzip,hashlib
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import pyarrow.parquet as pq
ROOT=Path('/Users/vf/Documents/ChatGPT/Coinmaster');OUT=Path(__file__).resolve().parent
BASE=ROOT/'runtime/var/research-jobs/paired-lot-corridor-20261025';P=BASE/'B2_F0_PHYSICAL7/result';SRC=BASE/'source-7d513ca1e0ec0fadd67167661a3173f105b19ba7/runtime/coinmaster'
FIRST_SHA='8c73956feb44ae1786d7ffdb043a2fbdc8996f57d65f5a8247568d8a74890174'
assert hashlib.sha256((OUT/'causal-admission-results.json').read_bytes()).hexdigest()==FIRST_SHA
pins={}
def pin(p):pins[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def load(p):return json.loads(pin(p).read_text())
def utc(t):return datetime.fromtimestamp(int(t)/1e9,timezone.utc).isoformat()
r=load(OUT/'causal-admission-results.json');a=load(P/'paired-prefix-B2_F0-raw-native.json');orders=list(csv.DictReader(pin(P/'paired-prefix-B2_F0-orders.csv').open()));md=a['market_redesign_audit']['events'];ev=a['paired_prefix_audit']['events'];fs=a['fill_audit'];parents={p['episode_id']:p for p in a['split_cover_audit']['parents']};ordered=sorted(parents.values(),key=lambda p:int(p['start_ns']))
for name in ['strategy/market_redesign.py','strategy/split_cover.py','strategy/wave_overlay.py','strategy/paired_prefix.py','research/native_baseline.py','research/native_fixture.py','venues/bybit_profile.py']:
 pin(SRC/name)
for name in ['bybit-BTCUSDT-risk-limit.json','bybit-SOLUSDT-risk-limit.json']:
 pin(SRC.parent/'var/raw/venues'/name)
cases=[];targets={}
for old in r['A_all_activations']:
 if old['activation'] not in [3,6,7,10]:continue
 p=parents[old['parent']];t=old['decision_ns'];start=int(p['start_ns']);nxt=min([int(z['start_ns']) for z in ordered if int(z['start_ns'])>start]+[10**30]);targets[t]=old['activation']
 oo=[o for o in orders if o['instrument_id'].startswith('BTC') and o['is_reduce_only']=='False' and start<=int(o['ts_init'])<nxt]
 children=[]
 for o in oo:
  meta=a['native_order_events'][o['client_order_id']];terms=[e for e in md if e.get('episode_id')==old['parent'] and e['event']=='SECOND_TERMINAL' and int(e['timestamp_ns'])==int(o['ts_last'])]
  children.append({'order_id':o['client_order_id'],'type':o['type'],'side':o['side'],'price':o['price'],'quantity':o['quantity'],'filled_qty':o['filled_qty'],'TIF':o['time_in_force'],'status':o['status'],'submit_ns':meta['submit_ns'],'accept_ns':meta['accept_ns'],'terminal_record_ts_last':o['ts_last'],'terminal_utc':utc(o['ts_last']),'terminal_before_riskOFF':int(o['ts_last'])<=t,'SECOND_TERMINAL_same_timestamp_proof':terms,'cancel_ACK_known_before_OFF':o['status']=='CANCELED' and int(o['ts_last'])<=t and bool(terms)})
 ordinary=[f for f in fs if start<=int(f['fill_ns'])<nxt and 'BTC' in f['instrument'] and f['action']!='BTC_ENTRY' and not f['reason'].startswith('PAIRED')]
 term=next((e for e in ev if e['event']=='PARENT_NATIVE_TERMINAL_FLAT' and e['parent']==old['parent']),None)
 rec={k:old[k] for k in ['activation','parent','decision_ns','decision_utc','original_Q0','F_ever','D_permanent','B_current','remaining_original_unfilled','original_cap_less_closed_and_held','prior_paired_protective_reductions']}
 rec.update(original_native_ENTRY_orders=children,ordinary_BTC_exit_timing=[{'reason':f['reason'],'ns':f['fill_ns'],'utc':utc(f['fill_ns']),'quantity':f['qty']} for f in ordinary],native_parent_terminal=term,effective_TIF='GTC, no generic 4h/day-end expiry in realU',eligibility_factors={'structural_original_right_potential':'YES_BEFORE_ORDINARY_TP_OR_FLAT_UNDER_NEW_LOCK_CONTRACT','old_child_cancel_ACK':'KNOWN' if any(c['cancel_ACK_known_before_OFF'] for c in children) else 'UNKNOWN','actual_quote':'PENDING_EXTRACTION','margin_model_availability':'CAPTURED_STOCK_POLICY_AND_NATIVE_ACCOUNT_FIELDS_PRESENT; exact prospective gate not replayed','current_legal_permission':'NO_CURRENT_PERMANENT_STOP; new reversible lock contract and explicit code budget required'})
 cases.append(rec)
# Only four riskOFF decision rows retained from existing captured native account CSV.
for z in csv.DictReader(gzip.open(pin(P/'minute-native-risk.csv.gz'),'rt')):
 t=int(z['close_available_ns'])
 if t in targets:
  rec=next(c for c in cases if c['activation']==targets[t]);rec['captured_native_account_at_riskOFF']={k:z[k] for k in ['close_available_ns','phase','cash','free_cash','native_initial_margin','native_maintenance_margin','paired_close_equity']};rec['account_input_limit']='Captured native free_cash/margins are actual values, not hand-derived. Per-instrument reserved/open-order-credit marks/state and _entries_enabled snapshot not fully exported; prospective _tier_allows_increase UNKNOWN until native gate.'
# Exact original execution source; saved native policy spread0, one-decimal wire bid/ask.
qpath=pin(ROOT/'runtime/var/data/normalized/bybit-BTCUSDT-execution-1m.parquet')
def quote_rows(lo,hi):
 tab=pq.read_table(qpath,columns=['open_time_ms','close'],filters=[('open_time_ms','>=',lo//10**6-60000),('open_time_ms','<=',hi//10**6-60000)])
 return [{'available_ns':(int(z['open_time_ms'])+60000)*10**6,'bid':f"{float(D(z['close'])):.1f}",'ask':f"{float(D(z['close'])):.1f}"} for z in tab.to_pylist()]
assert a['policy']['symmetric_adverse_spread_bps']=='0'
for c in cases:
 t=c['decision_ns'];qs=quote_rows(t,t+60*10**9);inv=next(e for e in ev if e['event']=='RISK_INVALID_OR_EXPIRED' and int(e['timestamp_ns'])==t);assert D(qs[0]['bid'])==D(inv['btc_close'])
 lim=next(o for o in c['original_native_ENTRY_orders'] if o['type']=='LIMIT');L=D(lim['price']);passive=(L<D(qs[0]['ask'])) if lim['side']=='BUY' else L>D(qs[0]['bid'])
 c['actual_quote_source_evidence']={'method':'Exact saved native_baseline.py938-940 synthetic L1 CLOSE quote mapping, saved spread0; validated against actual logged riskOFF BTC bid','quotes_at_OFF_and_next_minute':qs,'riskOFF_logged_btc_bid':inv['btc_close'],'original_limit_postonly_not_crossing_at_OFF':passive,'immediate_fill_required':False,'scope':'Same saved research execution assumptions; historical L2/latency UNKNOWN'};c['eligibility_factors']['actual_quote']='AVAILABLE_RECONSTRUCTED_EXACT_EXISTING_CLOSE_MODEL'
 assert c['captured_native_account_at_riskOFF']
# Oct25 market-only continuation under same fixed actual activation boundary/branch expiry.
act=next(e for e in ev if e['event']=='ACTIVATION_SELECTED' and '2024-10-25' in utc(e['timestamp_ns']));par=parents[act['parent']];signal=int(act['timestamp_ns']);entry=next(e for e in ev if e['event']=='ACTUAL_FILL' and e['kind']=='ENTRY' and signal<int(e['timestamp_ns'])<signal+120*10**9);entryns=int(entry['timestamp_ns']);expiry=entryns+8*3600*10**9;flat=next(e for e in ev if e['event']=='PARENT_NATIVE_TERMINAL_FLAT' and e['parent']==act['parent']);quotes=quote_rows(entryns,expiry);boundary=D(act['boundary']);side=par['side'];cross=next((q for q in quotes if q['available_ns']>entryns and side*(D(q['bid'])-boundary)>=0),None);off=min(expiry,cross['available_ns']) if cross else expiry
assert len(quotes)==481 and all(quotes[i]['available_ns']-quotes[i-1]['available_ns']==60*10**9 for i in range(1,len(quotes)))
firsttp=next(x for x in r['B_all_actual_TPs'] if x['activation']==8);deadline=(firsttp['TP_ns']//(4*3600*10**9)+1)*(4*3600*10**9)+60*10**9
kw=load(BASE/'lot-corridor-kwargs-B2_F0.json');feedrows=[x for x in kw['research_paired_signal_rows'] if signal<=int(x['decision_ns'])<=expiry]
oct25={'scope':'MARKET_ONLY_RECONSTRUCTION_NOT_ACTUAL_OWNER_EVENT_OR_CANDIDATE_WEALTH','boundary':str(boundary),'BTC_side':side,'first_entry_utc':utc(entryns),'actual_owner_flat_utc':utc(flat['timestamp_ns']),'branch_expiry_utc':utc(expiry),'first_boundary_cross_quote':cross,'market_risk_OFF_utc':utc(off),'OFF_reason':'BOUNDARY' if cross and cross['available_ns']<expiry else 'FIXED_F0_8H_EXPIRY','firstTP_nextH4_plus60_utc':utc(deadline),'market_OFF_before_firstTP_deadline':off<=deadline,'source_quote_rows':len(quotes),'closed_H4_feed_rows':feedrows,'critical_limit':'No continuing uncut equity/BTC/margin/ROI inferred; original rule market state only'}
out={'first_results_sha256_preserved':FIRST_SHA,'four_cases':cases,'Oct25_market_only':oct25,'new_native_conditional_gate':'If separately authorized: one native lifecycle fixture for reversible original-unfilled GTC lock; require cancel ACK and no other owned increase, original first-positiveTP/flat/parent terminal guard, exact original price/TIF/remaining cap, fresh quote+marks+entries-enabled+stock native margin gate, partial/late fill reconciliation. No candidate ROI or full run needed for this gate.','engines':0,'product_edits':0,'downloads':0,'pins':pins,'preserved_inspection_error':'Initial narrow schema inspection treated market_redesign_audit as list; TypeError/KeyError slice corrected to events key; no source mutation or calculation affected.'}
(OUT/'four-child-admission-details.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'cases':[{k:c[k] for k in ['activation','original_Q0','F_ever','D_permanent','B_current','remaining_original_unfilled','eligibility_factors']} for c in cases],'Oct25':{k:v for k,v in oct25.items() if k!='closed_H4_feed_rows'}},indent=2))
