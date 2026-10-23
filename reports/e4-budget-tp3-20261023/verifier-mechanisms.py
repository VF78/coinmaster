"""Compact saved native policy/fill event audit, no engines or equity model."""
import json,importlib.util
from pathlib import Path
from decimal import Decimal as D, ROUND_FLOOR
from collections import Counter
OUT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('saved',OUT/'verifier-saved.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
def run(recipe,path):
 d=json.loads(Path(path).read_text());raw=json.loads(Path(path).with_name(Path(path).stem+'-raw-native.json').read_text());a=json.loads((OUT/f'verifier-{recipe}-audit.json').read_text());checks={};notes={};ev=raw['next_band_audit'];fills=d['fill_audit'];policy=d['config']['budget_tp3_research']
 def check(k,x):checks[k]=bool(x)
 check('enabled_SOL_only_or_BTC_only',policy['sol_budget']==(recipe=='SOL') and policy['btc_early_tp3']==recipe.startswith('BTC'))
 liq={}
 for side in ['MAKER','TAKER']:
  rows=[r for r in fills if r['native_liquidity_side']==side];liq[side]=dict(fills=len(rows),notional=str(sum((D(r['notional']) for r in rows),D(0))),fees=str(sum((D(r['commission']) for r in rows),D(0))))
 check('actual_native_liquidity_all_fills',sum(x['fills'] for x in liq.values())==len(fills))
 check('actual_native_liquidity_fees_exact',sum((D(x['fees']) for x in liq.values()),D(0))==D(d['native_fees']))
 check('market_fills_not_relabeled_maker',all(r['native_liquidity_side']=='TAKER' for r in fills if r['order_type']=='1'))
 if recipe=='SOL':
  quotes=json.loads((OUT/'verifier-SOL-admission-quotes.json').read_text());quote_by_ns={r['timestamp_ns']:D(r['executable_quote']) for r in quotes['rows']}
  check('all13_actual_execution_quote_rows_exact',quotes['all_exact'] and quotes['source_rows_returned']==13)
  tr=[r for r in ev if r.get('event')=='SB_TRIGGER'];adds=[r for r in ev if r.get('event')=='SB_ADD_ADMISSION'];riskfills=[r for r in fills if r['reason']=='SOL_ATR_BUDGET_RISK'];table=[]
  for i,r in enumerate(tr):
   E,H,B,Q,A,F,M=map(D,[r['equity'],r['peak'],r['btc_reserve'],r['sol_qty'],r['sol_atr'],r['sol_fee'],r['sol_mark']]);cap=(max(D(0),(E-D('.55')*H-B-F*M*Q)/(A*(1+F)))/D('.1')).to_integral_value(rounding=ROUND_FLOOR)*D('.1')
   end=tr[i+1]['timestamp_ns'] if i+1<len(tr) else 10**30
   rs=[x for x in riskfills if int(r['timestamp_ns'])<=int(x['fill_ns'])<end];actual=sum((D(x['qty']) for x in rs),D(0))
   check(f'trigger_{i}_numerical_cap',cap==D(r['cap']));check(f'trigger_{i}_DD_and_SOL_dominance',D(r['drawdown'])>=D('.35') and D(r['sol_stress'])>D(r['btc_stress']));check(f'trigger_{i}_actual_excess_only',actual==Q-cap)
   check(f'trigger_{i}_completed_D1',int(r['daily_ns'])<=int(r['timestamp_ns']))
   table.append(dict(timestamp_ns=r['timestamp_ns'],held=str(Q),cap=str(cap),expected_excess=str(Q-cap),actual_reduction=str(actual),native_risk_fill_count=len(rs)))
  for i,r in enumerate(adds):
   post=D(r['equity'])-D(r['sol_fee'])*quote_by_ns[r['timestamp_ns']]*D(r['requested'])-D(r['btc_reserve'])-(D(r['sol_qty'])+D(r['requested']))*(D(r['sol_atr'])+D(r['sol_fee'])*(D(r['sol_mark'])+D(r['sol_atr'])))
   check(f'add_{i}_stress_math',post==D(r['post_stress_equity']));check(f'add_{i}_entire_request_budget_decision',bool(r['allowed'])==(post>=D('.55')*D(r['peak'])))
  # Native fill inventory partitions zero-to-zero cycles and bounds trims to once per cycle.
  q=D(0);cycle=0;triggercycles=[];lasttrigger=None
  timeline=sorted([(int(r['fill_ns']),1,i,r) for i,r in enumerate(fills) if r['instrument'].startswith('SOL')]+[(int(r['timestamp_ns']),0,i,r) for i,r in enumerate(tr)])
  for _,kind,i,r in timeline:
   if kind==0:triggercycles.append(cycle)
   else:
    delta=D(r['qty'])*(1 if r['action']=='SOL_ADD' else -1)
    if q==0 and delta>0:cycle+=1
    q+=delta
  check('once_per_actual_SOL_native_cycle',len(triggercycles)==len(set(triggercycles)))
  check('no_unknown_budget_events',not any('UNKNOWN' in r.get('event','') for r in ev if r.get('event','').startswith('SB')))
  notes.update(trigger_table=table,SB_event_counts=dict(Counter(r['event'] for r in ev if r.get('event','').startswith('SB'))),actual_risk_fill_count=len(riskfills),fee_price_basis='Frozen source _submit_intent passes native executable quote price; _next_budget_admit charges qty*executable*fee, stress uses raw mark. All13saved poststress values exactly match independently read frozen execution parquet completed-minute close (open+60sec), distinct from saved rawmark where applicable.',right_semantics='Observed allow/deny events audit full requested quantity; preservation of unused entitlement and mandatory priority also require frozen source/native focused tests. No absence-of-event counterfactual claimed.')
 if recipe.startswith('BTC'):
  allocations=[r for r in ev if r.get('event')=='TP3_ALLOCATION'];tranches=[r for r in ev if r.get('event')=='TP3_TRANCHE'];entrymap={r['episode_id']:r for r in d['entry_sizing_audit']}
  ns=lambda x:int(v.datetime.fromisoformat(x).timestamp())*10**9 if '-' in x else int(x)
  orders=v.readcsv(d['execution_artifacts']['orders']['path']);nativefills=v.readcsv(d['execution_artifacts']['fills']['path']);cycles,_=v.native_closed_cycles(nativefills);btccycles=[c for c in cycles if c['asset']=='BTC'];table=[]
  for i,r in enumerate(allocations):
   ts=int(r['timestamp_ns']);ep=r['episode_id'];cy=next(c for c in btccycles if ns(c['start'])<=ts<=ns(c['end']))
   qty=D(cy['entry_Q']);actual_lots=int(qty/D('.001'));early=int(r['early_lots']);target=int(r['target_lots']);expected=int((D(actual_lots)*D('.20')).to_integral_value(rounding=ROUND_FLOOR))
   check(f'alloc_{i}_early20_actual_native_initial',early==expected)
   check(f'alloc_{i}_positive_within_original_budget',0<early<=target and r['eligible']=='True')
   ts_end=ns(cy['end']);f=[x for x in fills if ns(cy['start'])<=int(x['fill_ns'])<=ts_end and x['instrument'].startswith('BTC') and x['level']=='2' and x['action']=='BTC_REDUCE'];ef=[x for x in f if x['reason']=='BTC_TP3_EARLY'];of=[x for x in f if x['reason']=='BTC_TP3'];eq=sum((D(x['qty']) for x in ef),D(0));oq=sum((D(x['qty']) for x in of),D(0))
   check(f'alloc_{i}_actual_early_fill_budget',eq<=D(early)*D('.001'))
   check(f'alloc_{i}_actual_original_remaining_budget',oq<=D(target-early)*D('.001'))
   check(f'alloc_{i}_actual_aggregate_no_oversell',eq+oq<=D(target)*D('.001'))
   check(f'alloc_{i}_early_actual_wire_price',all(D(x['px'])==D(r['early_price']) or x['native_liquidity_side']=='TAKER' for x in ef))
   if of:
    check(f'alloc_{i}_original_requires_actual_early_complete',eq==D(early)*D('.001'))
    check(f'alloc_{i}_remaining_submit_next_quote',min(int(x['submit_ns']) for x in of)>max(int(x['fill_ns']) for x in ef))
   for j,t in enumerate(x for x in tranches if x['episode_id']==ep):
    aggregate=int(t['aggregate_filled_lots']);leaves=early-aggregate if t['early'] else target-aggregate
    check(f'alloc_{i}_tranche_{j}_actual_leaves',abs(D(str(t['quantity']))-D(leaves)*D('.001'))<D('1e-10') and t['original_target_lots']==target)
   table.append(dict(episode_id=ep,allocation_ns=ts,actual_initial_lots=actual_lots,early_target_lots=early,original_combined_target_lots=target,remaining_original_target_lots=target-early,actual_early_filled_lots=str(eq/D('.001')),actual_original_filled_lots=str(oq/D('.001')),early_price=r['early_price'],original_price=r['old_price']))
  levelorders=sorted([r for r in orders if d.get('native_order_events',{}).get(r['client_order_id'],{}).get('level')=='2'],key=lambda r:ns(r['ts_init']))
  check('single_level2_native_order_owner_no_overlap',all(ns(b['ts_init'])>=ns(a['ts_last']) for a,b in zip(levelorders,levelorders[1:])))
  earlyfills=[r for r in fills if r['reason']=='BTC_TP3_EARLY'];originalfills=[r for r in fills if r['reason']=='BTC_TP3']
  notes.update(allocation_count=len(allocations),eligible_count=sum(r['eligible']=='True' for r in allocations),tranche_event_count=len(tranches),actual_early_fill_rows=len(earlyfills),actual_original_fill_rows=len(originalfills),actual_early_liquidity_counts=dict(Counter(r['native_liquidity_side'] for r in earlyfills)),actual_original_liquidity_counts=dict(Counter(r['native_liquidity_side'] for r in originalfills)),allocation_table=table,split_parent_audit='UNKNOWN_NOT_EXPORTED',proportional_SOL_entitlement_state='UNKNOWN_NOT_EXPORTED; actual early partial and original target denominator contract require frozen source/native focused test proof; no invented receipt',exact_PLANREF_reference='UNKNOWN_NOT_EXPORTED; no reconstructed reference price claimed',forced_priority='Source/native focused tests supply untriggered branch qualification; saved output proves observed terminal/risk fills only')
 result=dict(recipe=recipe,status='PASS' if all(checks.values()) else 'FAIL',checks=checks,failed_checks=[k for k,x in checks.items() if not x],notes=notes,actual_native_liquidity=liq,signed_asset_funding='UNKNOWN',no_new_engine=True,no_receipt_rescan=True,artifact_sha256=v.digest(path),raw_sha256=v.digest(Path(path).with_name(Path(path).stem+'-raw-native.json')))
 (OUT/f'verifier-{recipe}-mechanisms.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 import sys
 r=run(sys.argv[1],sys.argv[2]);print(json.dumps({'status':r['status'],'failed_checks':r['failed_checks'],'notes':r['notes']},indent=2))
