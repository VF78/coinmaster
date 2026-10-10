"""Cached opportunity/coverage aggregates, reconciliation and hashes only."""
from pathlib import Path
from decimal import Decimal as D
import json,csv,hashlib
p=Path('reports/selective-lifecycle-cap30m-113/hedge-risk-audit');a=json.loads((p/'hedge-risk.json').read_text());c=a['counts'];overlap=D(c['BOTH']);a['overlap_percent']={'of_all_minutes':str(overlap/D(a['prequote_rows'])*100),'of_any_position_minutes':str(overlap/D(c['BOTH']+c['BTC_ONLY']+c['SOL_ONLY'])*100),'of_BTC_held_minutes':str(overlap/D(c['BOTH']+c['BTC_ONLY'])*100)}
times=sorted((int(x['first_original_held_fee_reserved_break_even']['timestamp_ns'])-x['trigger_ns'])//60000000000 for x in a['profit_split_cases']);a['first_original_break_even_minutes']={'min':min(times),'median':times[len(times)//2],'max':max(times)};a['maximum_further_adversity_before_first_BE']='UNKNOWN_not_separately_captured; to-actual-end extrema are not substituted.'
initial=final=D(0)
for x in a['profit_split_cases']:
 v=D(x['initial_snapshot']['legs'][x['winner']]['fee_reserved_pnl']);x['initial_winner_cumulative_fee_reserved_pnl']=str(v);x['original_winner_final_minus_initial_cumulative_fee_reserved']=str(D(x['winner_final_actual_net_ex_funding'])-v);initial+=v;final+=D(x['winner_final_actual_net_ex_funding'])
a['winner_original_outcome_evolution']={'initial_winner_cumulative_mark_fee_reserved_sum':str(initial),'eventual_original_winner_net_sum':str(final),'difference':str(final-initial),'basis':'Observed original episode paths at different times; not future profit lost or counterfactualROI; fees mark proxy at start, actual native fees at completed end.'};(p/'hedge-risk.json').write_text(json.dumps(a,indent=2)+'\n')
flat=[]
for x in a['profit_split_cases']:
 y={k:v for k,v in x.items() if k!='initial_snapshot'}
 for s,leg in x['initial_snapshot']['legs'].items():
  for k in ['notional','held_native_pnl','cumulative_pnl','fee_reserved_pnl','remaining_allocated_entry_fee','held_pnl_after_allocated_entry_fee_and_exit_reserve']:y[s+'_'+k]=leg[k]
 flat.append(y)
with (p/'profit-split-cases.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(flat[0]),lineterminator='\n');w.writeheader();w.writerows(flat)
assert sum(c.values())==a['prequote_rows']==1051200 and a['trace_rows']==3153600
for d in a['global_TOP3_state_account_changes']:assert sum((D(v) for v in d['bucket_equity_changes'].values()),D(0))==-D(d['drawdown_amount'])
for x in a['profit_split_cases']:
 assert x['first_original_held_fee_reserved_break_even']['timestamp_ns']>=x['trigger_ns']
 for s,z in x['initial_snapshot']['legs'].items():assert D(z['fee_reserved_pnl'])==D(z['cumulative_pnl'])-D(z['prospective_mark_exit_fee_reserve'])
for x in p.glob('*.csv'):
 assert b'\r' not in x.read_bytes();assert all(None not in y for y in csv.DictReader(x.open()))
for x in p.glob('*.json'):json.loads(x.read_text())
checks={'prequote_rows':1051200,'trace_rows':3153600,'state_counts_reconcile':True,'TOP3_all_sample_native_equity_changes_exact':True,'existing_fill_gross_minus_fees_reconcile_per_asset_episode':True,'initial_fee_reserve_identity_exact':True,'current_held_entry_fee_allocation_nonnegative':True,'cases':13,'historical_engines':0,'additional_existing_trace_passes':1,'trading_source_changes':0,'beta_current_entry_sigma':'UNKNOWN_not_archived','first_winner_cross_and_adversity_before_first_BE':'UNKNOWN_not_separately_captured','native_followup_TOTAL_DD':'UNKNOWN_not_run','JSON_CSV_LF_checks':True,'trace_path':a['trace'],'trace_SHA256_reused_prior_immutable_receipt':'37fc8c1e85bbc9e434e33bef3d3e3ae31e48b6502f3cc7332552941f269c71d1','control_result_SHA256':'669d5c951f0dbc88216385890b143b5bfd5bc8eeeff88cf968dd68346474c703','original_economic_source_result_SHA256':'8e4a387260688729563258b84befe34b0bef2479f2fbe369c621fab9cc3281e2','analysis_log_SHA256':hashlib.sha256(Path('/tmp/cm113-hedge-risk-analysis.log').read_bytes()).hexdigest()};(p/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
h={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(p.iterdir()) if x.is_file() and x.name!='artifact-hashes.json'};(p/'artifact-hashes.json').write_text(json.dumps(h,indent=2)+'\n');print(json.dumps(checks));print('README_SHA256',h['README.md'])
