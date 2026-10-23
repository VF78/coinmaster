"""Saved native output cross-architecture parity only; no engine/import/rerun."""
import json,hashlib,runpy,csv
from pathlib import Path
from decimal import Decimal as D
BASE=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021')
OUT=BASE/'reports/sol-conditional-hedge-btc-band-20261023'
P0=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/P0/result')
STEM='v0-selective-lifecycle-cap30m-btc-split50-d0.0025-planref-v1-tp-ioc-btc-direction'
REF=Path('/private/tmp/btc-audit-exact-s0-direction.json')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(REF)=='e7854784dce9bcf27e77d45ebe12873d78a42a0ecb43b3686f2a0da810fb2bfa'
reference=json.loads(REF.read_text());actual=json.loads((P0/(STEM+'.json')).read_text())
completion=json.loads((BASE/'reports/fast-rnd-20261020/s0-completion.json').read_text())
manifest=json.loads((BASE/'reports/fast-rnd-20261020/s0-artifact-manifest.json').read_text())
validation=json.loads((BASE/'reports/s0-management-20261022/economic-validation-s0.json').read_text())
api=runpy.run_path(str(BASE/'scripts/verify_split_cover_repeat.py'));canonical=api['canonical'];economic_csv=api['economic_csv'];digest=api['digest']
# Both finalized journals are immutable: avoid WAL/shm writes while preserving
# the exact repeat-verifier SELECT and ordering contract.
def funding(path):
 import sqlite3
 c=sqlite3.connect('file:'+str(path.resolve())+'?mode=ro&immutable=1',uri=True,timeout=2)
 try:return c.execute('SELECT instrument_id,ts_event,rate,settlement_mark,account_total_after FROM funding_events ORDER BY ts_event,instrument_id').fetchall()
 finally:c.close()
checks={};inputs={}
def compare(name,left,right):
 checks[name]={'exact_equal':left==right,'reference_sha256':digest(left),'P0_sha256':digest(right)}
 if isinstance(left,(list,dict)):checks[name].update(reference_count=len(left),P0_count=len(right))
 if left!=right and not isinstance(left,(list,dict)):checks[name].update(reference=left,P0=right)
for suffix in ['fills.csv','orders.csv','funding.sqlite']:
 ref=OUT/('verifier-reference-'+suffix);p0=P0/(STEM+'-'+suffix)
 known=next(v for k,v in manifest['files'].items() if k.endswith(STEM+'-'+suffix))
 assert ref.stat().st_size==known['bytes'] and sha(ref)==known['sha256'],suffix+' reference immutable hash mismatch'
 inputs[str(ref)]={'sha256':sha(ref),'matches_original_manifest':True};inputs[str(p0)]={'sha256':sha(p0)}
for name in ('config','config_hash','data_hash','policy','policy_hash','native_fees','fills','native_order_rejections','terminal_total','terminal_active','terminal_reserve','terminal_open_positions','liquidation_count','liquidation_value','summary'):
 compare(name,reference[name],actual[name])
for name in ['fill_audit','entry_sizing_audit','minute_risk_observations','cash_account_series','interval_cash_account_series','fee_attribution','terminal_lifecycle','post_boundary_settlement','source_hashes']:
 compare(name+'_economic',canonical(reference[name]),canonical(actual[name]))
compare('parent_lots_planref',canonical(reference['split_cover_audit']['parents']),canonical(actual['split_cover_audit']['parents']))
compare('streaming_schedule',{k:v for k,v in reference['streaming'].items() if k!='peak_rss_bytes'},{k:v for k,v in actual['streaming'].items() if k!='peak_rss_bytes'})
for kind in ['fills','orders']:
 compare('native_'+kind+'_economic_signature',economic_csv(OUT/('verifier-reference-'+kind+'.csv')),economic_csv(P0/(STEM+'-'+kind+'.csv')))
fa=funding(OUT/'verifier-reference-funding.sqlite');fb=funding(P0/(STEM+'-funding.sqlite'))
compare('funding_canonical_instrument_time_rate_mark_account_total_after',fa,fb)
compare('funding_rows_expected1320',1320,len(fb));compare('fill_rows_expected621',621,len(actual['fill_audit']))
compare('fees_sum_equals_native_fees',actual['native_fees'],str(sum((D(r['commission']) for r in actual['fill_audit']),D(0))))
compare('native_account_cash_tail',completion['terminal_total'],actual['cash_account_series'][-1]['total'])
compare('native_flat_position_count',0,actual['terminal_open_positions']);compare('native_terminal_flat','FLAT',actual['terminal_lifecycle']['status'])
compare('ROI_fraction',completion['roi_fraction'],actual['summary']['roi'])
compare('signed_funding_unknown',completion['funding_signed_amount'],actual['funding']['signed_amount'])
compare('funding_count_summary',completion['funding_count'],actual['funding']['count'])
# Complete canonical risk object comparison above covers all three published DDs,
# settled coverage counts, unavailable/pending receipts and timestamp conventions.
risk=actual['minute_risk_observations']
settled_meta=risk['settled_native_close_receipts'];settled=settled_meta['curve']
compare('settled_receipts_expected1051199',1051199,settled_meta['receipts'])
compare('settled_samples_seed1051200',1051200,settled['samples'])
compare('settled_unavailable0',0,settled_meta['unavailable_intervening_native_mutation'])
compare('settled_no_pending_quote',None,settled_meta['pending_source_quote_ns'])
print('settled keys',settled.keys())
compare('settled_DD_exact',completion['settled_receipt_DD_percent'],settled['top3_distinct_excursions'][0]['drawdown_peak_percent'])
compare('callback_DD_exact',completion['legacy_callback_observed_DD_percent'],risk['curves']['all_native_close_samples']['top3_distinct_excursions'][0]['drawdown_peak_percent'])
compare('conditional_OHLC_bound_exact',validation['conditional_OHLC_upper_to_later_lower'],risk['conditional_upper_to_later_lower_bound'])
raw=json.loads((P0/(STEM+'-raw-native.json')).read_text())
compare('raw_wrapper_terminal_TOTAL',actual['terminal_total'],raw['terminal_total'])
for p in [REF,P0/(STEM+'.json'),P0/(STEM+'-raw-native.json'),BASE/'scripts/verify_split_cover_repeat.py']:
 inputs[str(p)]={'sha256':sha(p)}
failed=[name for name,row in checks.items() if not row['exact_equal']]
receipt={'status':'P0_SAVED_OUTPUT_EXACT_PARITY_PASS' if not failed else 'P0_PARITY_FAIL','decision':'GO_FOR_FIRST_CANDIDATE' if not failed else 'NO_GO','reference':'Immutable originalS0 remains authoritative; P0 validates Mac portability only.','checks':checks,'failed_checks':failed,'inputs':inputs,'metrics':{'TOTAL':actual['terminal_total'],'ROI_fraction':actual['summary']['roi'],'native_fees':actual['native_fees'],'fills':actual['fills'],'orders':len(economic_csv(P0/(STEM+'-orders.csv'))),'funding_rows':len(fb),'signed_funding':actual['funding']['signed_amount'],'settled_DD_percent':settled['top3_distinct_excursions'][0]['drawdown_peak_percent'],'callback_DD_percent':risk['curves']['all_native_close_samples']['top3_distinct_excursions'][0]['drawdown_peak_percent'],'conditional_OHLC_bound_percent':risk['conditional_upper_to_later_lower_bound']['maximum']['drawdown_peak_percent']},'identity_exclusions':sorted(api['IDS']),'path_exclusions':['summary_path','trace_path'],'performance_exclusion':'streaming.peak_rss_bytes','new_tolerances':0,'technical_note':'SQLite immutable=1 read-only URI avoids journal/shm writes; exact repeat-verifier SELECT/order reused unchanged. Initial saved-data attempt corrected missing settled metadata key; no engine was imported or run.','new_native_runs':0,'remote_giant_traces_read':0}
receipt['exact_economic_parity']={'status':'PASS' if not [k for k in failed if k!='parent_lots_planref'] else 'FAIL','basis':'Exact saved native fills/orders/funding/money/sizing/risk comparisons; no tolerances','localization':'verifier-float-localization.json'}
receipt['strict_repeat_contract']={'status':'PASS' if not failed else 'FAIL_UNRESOLVED','failed_checks':failed,'no_tolerance_or_exclusion_added':True}
receipt['decision']='ROOT_DECISION_REQUIRED_P0_ECONOMIC_PARITY_VERSUS_STRICT_R_CONTRACT'
(OUT/'P0-validation.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'status':receipt['status'],'checks':len(checks),'failed':failed,'metrics':receipt['metrics']},indent=2))

if failed:raise SystemExit(1)
