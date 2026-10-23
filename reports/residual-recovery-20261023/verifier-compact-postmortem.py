"""Compact saved outputs/event/cache arithmetic only; never opens full traces."""
import json,csv,pathlib,collections
from decimal import Decimal as D
from datetime import datetime,timezone
P=pathlib.Path(__file__).resolve().parent;O=P/'verifier-C1_CORRECTED-audit'
freeze=json.loads((P/'verifier-C1_CORRECTED-completed-freeze.json').read_text());d=json.loads(pathlib.Path(freeze['artifact']).read_text());audit=json.loads((O/'verifier-C1_CORRECTED-audit.json').read_text());base=json.loads((P.parent/'e4-budget-tp3-20261023/verifier-control-windows.json').read_text());cycles=list(csv.DictReader((O/'verifier-C1_CORRECTED-closed-cycle-ledger.csv').open()))
def iso(ns):return datetime.fromtimestamp(int(ns)/1e9,timezone.utc).isoformat()
def ns(s):return int(datetime.fromisoformat(s).timestamp()*1e9)
groups={};proposal=None
for r in d['c1_audit']:
 ev=r['event'];g=r['group'];t=int(r['timestamp_ns'])
 if ev=='PROPOSED_DECISION':proposal=r
 elif ev=='CLAIM':groups[g]={'group':g,'claim_ns':t,'claim_utc':iso(t),'asset':proposal['selected'].split('USDT')[0],'side':1 if proposal['positions'][next(i for i,p in enumerate(proposal['positions']) if p['instrument_id']==proposal['selected'])]['side']=='2' else -1,'trigger_DD':proposal['DD'],'selected_loss':proposal['selected_loss'],'cushion':proposal['cushion'],'held_lots':r['frozen_held_lots'],'target_lots':r['frozen_target_lots'],'cut_qty':D(0),'restore_qty':D(0),'actual_fee':D(0),'turnover':D(0),'blocked_increases':0,'restore_ns':None,'revocation_ns':None,'restore_gap_native_price_cost':None}
 elif g in groups:
  z=groups[g]
  if ev=='ATTEMPT_SUBMIT':z['step']=D(r['step']);z[r['kind'].lower()+'_submitted_lots']=int(r['lots'])
  elif ev=='NATIVE_FILL_RECEIPT':
   kind=next(x['kind'] for x in d['c1_audit'] if x['event']=='ATTEMPT_SUBMIT' and x['intent_id']==r['intent_id']);qty=D(r['quantity']);price=D(r['price']);z[kind.lower()+'_qty']+=qty;z['actual_fee']+=D(r['commission'].rsplit(' ',1)[0]);z['turnover']+=qty*price;z[kind.lower()+'_native_price']=price;z[kind.lower()+'_fill_ns']=t
   if kind=='RESTORE':z['restore_ns']=t;z['restore_gap_native_price_cost']=z['side']*(price-z['cut_native_price'])*qty
  elif ev=='TOKEN_REVOKED':z['revocation_ns']=t;z['revocation_reason']=r['reason']
  elif ev in ('QUEUED_INCREASE_BLOCKED','NORMAL_INCREASE_BLOCKED'):z['blocked_increases']+=1
rows=[]
for z in groups.values():
 end=z['restore_ns'] or z['revocation_ns'];z['credit_hold_hours']=(D(end-z['cut_fill_ns'])/D(3600*10**9)) if end else None;z['cut_partial']=z['cut_qty']<D(z['cut_submitted_lots'])*z['step'];z['cut_fill_utc']=iso(z['cut_fill_ns']);z['restore_utc']=iso(z['restore_ns']) if z['restore_ns'] else None;z['revocation_utc']=iso(z['revocation_ns']) if z['revocation_ns'] else None
 cyc=next((c for c in cycles if c['asset']==z['asset'] and ns(c['start'])<=z['cut_fill_ns']<=ns(c['end'])),None)
 z['candidate_actual_cycle_net_ex_funding']=cyc['confirmed_fill_net_ex_funding'] if cyc else 'UNKNOWN';z['candidate_actual_cycle_positive_context']=D(cyc['confirmed_fill_net_ex_funding'])>0 if cyc else None;z['context_not_counterfactual']='Positive candidate cycle contextualizes recovery cost; not proof cut was false-positive or that removing it improves nativeTOTAL.';rows.append(z)
with (P/'verifier-C1_CORRECTED-claim-attribution.csv').open('w') as f:
 w=csv.DictWriter(f,list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
windows={k:{'E4_DD':old['continuous_global_peak_DD_inside_window_percent'],'C1_DD':audit['risk']['fixed_protocol_windows'][k]['continuous_global_peak_DD_inside_window_percent'],'delta_pp':D(audit['risk']['fixed_protocol_windows'][k]['continuous_global_peak_DD_inside_window_percent'])-D(old['continuous_global_peak_DD_inside_window_percent'])} for k,old in base['windows'].items()}
episodes=[]
for e in audit['risk']['excursions_ge_30percent']:
 episodes.append({'peak_utc':e['peak_utc'],'trough_utc':e['trough_utc'],'DD_percent':D(e['drawdown_fraction'])*100,'recovery_utc':e['recovery_utc'],'peak_to_recovery_hours':D(ns(e['recovery_utc'])-ns(e['peak_utc']))/D(3600*10**9) if e['recovery_utc'] else None,'trough_to_recovery_hours':D(ns(e['recovery_utc'])-ns(e['trough_utc']))/D(3600*10**9) if e['recovery_utc'] else None})
summary={'status':'VALID_NATIVE_NEGATIVE_COMPACT_POSTMORTEM','TOTAL':audit['TOTAL'],'retention_percent':audit['retention_percent'],'global_DD':audit['risk']['global_settled_DD_percent'],'E4_TOTAL_difference':D(audit['TOTAL'])-D('5631617.35953723'),'profit_floor_shortfall':D('5470396.514987347')-D(audit['TOTAL']),'claims':len(rows),'cut_orders':len(rows),'restore_orders':sum(r['restore_ns'] is not None for r in rows),'credit_revoked':sum(r['revocation_ns'] is not None for r in rows),'late_Aug_claims':sum(r['claim_utc'].startswith('2026-08') for r in rows),'partial_cut_count':sum(r['cut_partial'] for r in rows),'actual_C1_fees':sum((r['actual_fee'] for r in rows),D(0)),'actual_C1_turnover':sum((r['turnover'] for r in rows),D(0)),'blocked_increase_intents':sum(r['blocked_increases'] for r in rows),'positive_candidate_cycle_contexts':sum(r['candidate_actual_cycle_positive_context'] is True for r in rows),'paired_cut_restore_native_price_gap_cost':sum((r['restore_gap_native_price_cost'] for r in rows if r['restore_gap_native_price_cost'] is not None),D(0)),'fixed_windows':windows,'recovery_episodes':episodes,'funding':'SIGNED_ASSET_UNKNOWN;unallocated bridge not called funding','missed_false_positive_scope':'Exact missed-benefit/false-positive PnL UNKNOWN without native counterfactual; report native percycle positive contexts/3completedrestores/6creditrevocations/4blockedincreases, not syntheticTOTAL. DD35 minima/crossings betweenclaims are NOT cached; no fulltrace reread in this postmortem.','wrapper_exit_code':1,'native_child_exact_exit':'UNKNOWN','engines_added':0,'fulltrace_passes_added':0}
(P/'verifier-C1_CORRECTED-postmortem.json').write_text(json.dumps(summary,indent=2,default=str)+'\n');print(json.dumps(summary,indent=2,default=str))
