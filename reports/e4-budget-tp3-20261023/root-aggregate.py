from pathlib import Path
import csv,json,hashlib
from decimal import Decimal as D
P=Path(__file__).resolve().parent
R=P.parent
read=lambda p:json.loads(Path(p).read_text())
controls={r['recipe']:r for r in csv.DictReader(open(R/'b-50-90-next-20261023/comparison.csv'))}
rows=[]
for name in ('S0','E4'):
 x=controls[name]; rows.append({k:x[k] for k in ['recipe','TOTAL','ROI_percent','net_profit_retention_percent','global_settled_DD_percent','fees','BTC_fills','SOL_fills','maker_notional','taker_notional','maker_fees','taker_fees','BTC_fill_net_ex_funding','SOL_fill_net_ex_funding','unallocated_cash_bridge']})
for name in ('SOL','BTC_CORRECTED'):
 a=read(P/f'verifier-{name}-audit.json');assert a['status']=='PASS' and not a['failed_checks']
 t={side:{'notional':D(0),'fees':D(0)} for side in ('MAKER','TAKER')}
 for f in csv.DictReader(open(P/f'owner-{name}-events/native-fill-audit.csv')):
  t[f['native_liquidity_side']]['notional']+=D(f['notional']);t[f['native_liquidity_side']]['fees']+=D(f['commission'])
 assert sum((x['fees'] for x in t.values()),D(0))==D(a['fees'])
 assets={r['asset']:r for r in a['assets']}
 row={'recipe':name,'TOTAL':a['TOTAL'],'ROI_percent':str((D(a['TOTAL'])/10000-1)*100),'net_profit_retention_percent':a['retention_percent'],'global_settled_DD_percent':a['risk']['global_settled_DD_percent'],'fees':a['fees'],'BTC_fills':a['BTC_fills'],'SOL_fills':a['SOL_fills'],'BTC_fill_net_ex_funding':assets['BTC']['confirmed_fill_net_ex_funding'],'SOL_fill_net_ex_funding':assets['SOL']['confirmed_fill_net_ex_funding'],'unallocated_cash_bridge':a['unallocated_cash_bridge']}
 for side in t:
  row[side.lower()+'_notional']=str(t[side]['notional']);row[side.lower()+'_fees']=str(t[side]['fees'])
 row['liquidations']=a['liquidations'];row['complete_native_receipts']=a['risk']['receipts'];row['global_peak_trough_recovery']=a['risk']['global_peak_trough_recovery']
 row['fixed_protocol_windows']={k:{q:v[q] for q in ['local_window_rebased_DD_percent','continuous_global_peak_DD_inside_window_percent']} for k,v in a['risk']['fixed_protocol_windows'].items()}
 row['source']=a.get('source_commit',read(P/f'owner-{name}-receipt.json')['source_commit'])
 row['config_sha256']=a['config_hash'];row['signed_asset_funding']='UNKNOWN'
 assert D(row['TOTAL'])==10000+sum(D(row[k]) for k in ['BTC_fill_net_ex_funding','SOL_fill_net_ex_funding','unallocated_cash_bridge'])
 for k in ['TOTAL','fees','BTC_fill_net_ex_funding','SOL_fill_net_ex_funding','unallocated_cash_bridge']:
  row[k+'_minus_E4']=str(D(row[k])-D(controls['E4'][k]))
 row['PASS_50_90']=D(row['TOTAL'])>=D('5470396.514987347') and D(row['global_settled_DD_percent'])<=50
 rows.append(row)
for r in rows:
 r['PASS_50_90']=D(r['TOTAL'])>=D('5470396.514987347') and D(r['global_settled_DD_percent'])<=50
 r['state']='REUSED_ARCHIVE_NOT_RERUN' if r['recipe'] in ('S0','E4') else 'VALID_NATIVE_INDEPENDENT_MONEY_AUDIT_PASS'
assert not any(r['PASS_50_90'] for r in rows)
(P/'comparison.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n')
cols=['recipe','TOTAL','ROI_percent','net_profit_retention_percent','global_settled_DD_percent','fees','BTC_fills','SOL_fills','maker_notional','taker_notional','maker_fees','taker_fees','BTC_fill_net_ex_funding','SOL_fill_net_ex_funding','unallocated_cash_bridge','TOTAL_minus_E4','PASS_50_90']
with open(P/'comparison.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(rows)
selection={'decision':'NO_GO_NO_50_90_CANDIDATE','required_TOTAL':'5470396.514987347','required_global_DD_percent':'50','selected_for_deploy':None,'S0_retained':True,'E4_research_control_retained':True,'COMBINED':'NOT_RUN_GATE_FAILED_BOTH_RECIPES_FAIL_RETENTION_AND_GLOBAL_DD','FRESH_REPEAT':'NOT_RUN_NO_PASSING_CANDIDATE','physical_attempts':3,'valid_recipes':2,'invalid_attempts':[{'recipe':'BTC','number':2,'source':'5dc17f0a8c6bc764746683f4d38bcf1fa9dcc77e','reason':'MONTHLY_COMPOUNDING_DECIMAL28_ASSERT_EXIT1_AND_INCOMPLETE_GZIP; originalexportsunmodified; no recoveryrepair'}],'remaining_unspent':1,'active':0,'launch_authorization_closed':True,'substantial_correction_count':1,'pilot_changes':0}
(P/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
for r in rows:print({k:r.get(k) for k in ['recipe','TOTAL','ROI_percent','net_profit_retention_percent','global_settled_DD_percent','fees','BTC_fills','SOL_fills','TOTAL_minus_E4','PASS_50_90']})
