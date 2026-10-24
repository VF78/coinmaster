#!/usr/bin/env python3
"""Single arithmetic verification of the one saved-receipt analysis output."""
import csv,json,collections
from pathlib import Path
from decimal import Decimal as D,getcontext
getcontext().prec=60
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
def read(n):
 with (OUT/n).open() as f:return list(csv.DictReader(f))
rows=read('btc-participation-parents.csv');summ=read('btc-participation-summary.csv');matched=read('btc-participation-matched-diagnostics.csv');comp=json.load(open(ROOT/'reports/market-redesign-20261024/comparison.json'));meta=json.load(open(OUT/'btc-participation-verification.json'))
assert len(rows)==332 and len(matched)==249
checks={};diagnostics={}
for v in ['E4','R1','R2','R3']:
 rr=[r for r in rows if r['variant']==v];ss=next(s for s in summ if s['variant']==v and s['cohort']=='all');assert len(rr)==83
 assert sum(D(r['actual_fill_net_ex_funding']) for r in rr)==D(ss['BTC_fill_net_ex_funding']);assert sum(D(r['actual_fees']) for r in rr)==D(ss['BTC_fees']);assert sum(D(r['actual_entry_notional']) for r in rr)==D(ss['entry_notional_sum'])
 assert sum(r['requested_gross_budget'].startswith('UNKNOWN') for r in rr)==29
 assert all(D(r['initial_child_planned_qty'])+D(r['initial_planned_second_qty'])==D(r['planned_parent_qty']) for r in rr)
 assert all(D(r['actual_filled_entry_qty'])<=D(r['planned_parent_qty']) for r in rr)
 if v!='E4':
  c=next(c for c in comp['candidate_rows'] if c['variant']==v);calc=sum(D(r['actual_fill_net_ex_funding'])+D(r['signed_BTC_funding']) for r in rr);res=D(c['TOTAL'])-D(10000)-calc;assert abs(res)<=D('.00000004');checks[v]={'native_minus_sum_cash_rounding_residual':str(res)}
 else:assert D(ss['BTC_fill_net_ex_funding'])==D('4858451.83533031')
 if v!='E4':
  z=[r for r in matched if r['variant']==v]
  diagnostics[v]={outcome:{'parents':len([r for r in z if r['E4_outcome_diagnostic']==outcome]),'mean_own_equity_ratio_to_E4':str(sum(D(r['own_equity_ratio_to_E4']) for r in z if r['E4_outcome_diagnostic']==outcome)/len([r for r in z if r['E4_outcome_diagnostic']==outcome])),'mean_actual_qty_ratio_to_E4':str(sum(D(r['actual_qty_ratio_to_E4']) for r in z if r['E4_outcome_diagnostic']==outcome)/len([r for r in z if r['E4_outcome_diagnostic']==outcome]))} for outcome in ['WIN','LOSS']}
# Verify actual first-P0 ownership in runtime audit, independently of comments.
anchors={}
for v in ['R2','R3']:
 a=json.load(open(ROOT/f'reports/market-redesign-20261024/native-analysis-{v}.json'));raw=json.load(open(next(p for p in a['input_sha256'] if p.endswith('-raw-native.json'))));ev=raw['market_redesign_audit']['events'];plans={x['episode_id']:x for x in ev if x['event']=='PLAN'};freeze={x['episode_id']:x for x in ev if x['event']=='P0_FROZEN_FIRST_TERMINAL'};parents=raw['split_cover_audit']['parents'];assert len(plans)==len(freeze)==83
 targets=[x for x in ev if x['event']=='TARGETS_SUBMITTED']
 assert all(D(x['p0'])==D(freeze[x['episode_id']]['p0']) for x in targets)
 assert all(D(p['first_vwap'])==D(freeze[p['episode_id']]['p0']) for p in parents)
 anchors[v]={'plans':len(plans),'frozen_firstP0':len(freeze),'all_actual_target_reprices_keep_firstP0':True,'parents_blended_VWAP_differs_from_firstP0':sum(D(p['planref_v1_actual_blended_vwap'])!=D(p['first_vwap']) for p in parents)}
meta['arithmetic_file_verification']='PASS';meta['native_cash_residual_checks']=checks;meta['actual_firstP0_verification']=anchors;meta['matched_outcomes_diagnostics_only']=diagnostics;meta['analysis_passes']=1;meta['arithmetic_verification_passes']=1
(OUT/'btc-participation-verification.json').write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps({'status':'PASS','cash_checks':checks,'anchors':anchors,'matched_outcome_diagnostics':diagnostics},indent=2))
