from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import json,csv,hashlib
R=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021/reports/system-contract-repair-20261023');J=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/system-contract-repair-20261023')
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
s0=D('6482334.93387961');legacy=D('6077107.23887483');floor=D('10000')+D('.9')*(s0-10000);rows=[]
for name in ['S0_EXPLICIT_CONTROL','E4_EXPLICIT_CONTROL','H_SOL','H_BTC']:
 a=read(R/f'data-native-acceptance-{name}.json');e=read(R/f'execution-{name}.json');assert a['status']=='VALID_COMPLETED_CHANGED_EXECUTION_MODEL' and e['native_process_exit_code']==0 and not a['failed_checks']
 p=read(R/('owner-control-preparation.json' if name=='E4_EXPLICIT_CONTROL' else f'owner-{name}-preparation.json'));x=read(Path(e['artifact']));fee=x['fee_attribution'];risk=read(R/f'data-attribution-{name}.json');total=D(a['TOTAL']);dd=D(a['global_settled_DD_percent']);ret=(total-10000)/(s0-10000);assets={z['asset']:z for z in a['assets']}
 row={'recipe':name,'terminal_ACTIVE':str(total),'RESERVE':'0','TOTAL':str(total),'ROI_percent':str((total/10000-1)*100),'matched_profit_retention_percent':str(ret*100),'legacy_profit_retention_percent':str((total-10000)/(legacy-10000)*100),'global_settled_DD_percent':str(dd),'liquidations':x['liquidation_count'],'maker_notional':fee['maker']['notional'],'taker_notional':fee['taker']['notional'],'maker_fees':fee['maker']['fees'],'taker_fees':fee['taker']['fees'],'total_fees':fee['native_total'],'funding':'SIGNED_ASSET_ATTRIBUTION_UNKNOWN; native journal included unchanged','unallocated_cash_bridge':a['unallocated_native_cash_bridge'],'BTC_fills':assets['BTC']['filled_order_rows'],'SOL_fills':assets['SOL']['filled_order_rows'],'BTC_confirmed_fill_net_ex_funding':assets['BTC']['confirmed_fill_net_ex_funding'],'SOL_confirmed_fill_net_ex_funding':assets['SOL']['confirmed_fill_net_ex_funding'],'total_fills':a['fills'],'matched_goal_pass':bool(dd<=50 and ret>=D('.9') and x['liquidation_count']==0),'legacy_absolute_pass':bool(total>=D('5470396.514987347')),'native_account_acceptance':'PASS60/60','source_commit':p['source_commit'],'config_sha256':p['expected_config_sha256'],'elapsed_seconds':e['elapsed_monotonic_seconds'],'artifact':e['artifact'],'artifact_sha256':sha(Path(e['artifact'])),'terminal_flat':x['terminal_lifecycle']['status']=='FLAT','receipt_count':a['receipts']}
 assert row['total_fees']==a['native_fees'] and row['total_fills']==x['fills'];rows.append(row)
base=next(r for r in rows if r['recipe']=='E4_EXPLICIT_CONTROL')
for r in rows:
 r['TOTAL_delta_vs_explicit_E4']=str(D(r['TOTAL'])-D(base['TOTAL']));r['BTC_fill_net_delta_vs_explicit_E4']=str(D(r['BTC_confirmed_fill_net_ex_funding'])-D(base['BTC_confirmed_fill_net_ex_funding']));r['SOL_fill_net_delta_vs_explicit_E4']=str(D(r['SOL_confirmed_fill_net_ex_funding'])-D(base['SOL_confirmed_fill_net_ex_funding']))
p={'status':'COMPLETE_NATIVE_NEGATIVE_NO_PASSING_CANDIDATE','utc':datetime.now(timezone.utc).isoformat(),'matched_S0_TOTAL':str(s0),'matched90_profit_floor':str(floor),'legacy_S0_TOTAL':str(legacy),'legacy90_absolute_floor':'5470396.514987347','comparison_basis':'Same explicit-child execution model; archive model distinct and not silently mixed','rows':rows,'archives':[{'recipe':'S0_ARCHIVE','TOTAL':str(legacy),'global_DD_percent':'66.25691486468686414439256686','execution_model':'LEGACY_IMPLICIT_L1_GOVERNOR'},{'recipe':'E4_ARCHIVE','TOTAL':'5631617.35953723','global_DD_percent':'57.58541045962226379114466259','execution_model':'LEGACY_IMPLICIT_L1_GOVERNOR'}],'NOT_RUN':[{'recipe':'COMBINED','reason':'Actual H_SOL and H_BTC prefixes have k1 through Jan13; combined retains irreversible H_SOL DD65.69477083251083711659723613. No combinedTOTAL inferred.','proof':'owner-combination-prefix-futility.json'},{'recipe':'FRESH_REPEAT','reason':'No full passing candidate to repeat; no reproducibility or OOS claim.'}],'goal_status':'NOT_MET','selected_policy':None,'pilot_changes':False}
(R/'comparison.json').write_text(json.dumps(p,indent=2)+'\n')
with (R/'comparison.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
all_ep=[];all_month=[]
for name in ['S0_EXPLICIT_CONTROL','E4_EXPLICIT_CONTROL','H_SOL','H_BTC']:
 for suffix,target in [('seven-windows',all_ep),('months',all_month)]:
  with (R/f'data-attribution-{name}-{suffix}.csv').open() as f:
   for v in csv.DictReader(f):target.append(dict(recipe=name,**v))
for name,values in [('episode-attribution.csv',all_ep),('monthly-attribution.csv',all_month)]:
 with (R/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(values[0]));w.writeheader();w.writerows(values)
assert len(all_ep)==28 and len(all_month)==96
selection={'status':'NO_GO','economic_goal':'NOT_MET','selected_variant':None,'reason':'Neither H_SOL nor H_BTC passes simultaneous DD50 and matched90profit; combination provably retains prior DD>50','full_native_attempts':4,'unused_slots':2,'unused_slots_status':'CLOSED_NOT_SPENT_NOT_AUTOMATIC_NEXT_AUTHORIZATION','physical_cap':6,'fresh_repeat':'NOT_RUN_NO_PASSING_CANDIDATE','COMBINED':'NOT_RUN_ACTUAL_PREFIX_FUTILITY','engineering_work':'implemented+tested, defaultOFF research flags; separate from economic acceptance','source':'8f2f78005325776d1f600297a0c2d39e29c48bdd','live_or_deploy':'NOT_AUTHORIZED_OR_PERFORMED','S0_old_archive':'UNCHANGED','pilot':'UNCHANGED'}
(R/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
print(json.dumps({'rows':[{k:r[k] for k in ['recipe','TOTAL','global_settled_DD_percent','matched_profit_retention_percent','BTC_fills','SOL_fills','matched_goal_pass']} for r in rows],'episodes':len(all_ep),'months':len(all_month),'goal':'NOT_MET'},indent=2))
