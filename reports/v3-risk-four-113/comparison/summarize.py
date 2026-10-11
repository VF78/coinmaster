"""Cached JSON/native summaries only; no engine execution or raw trace scans."""
import json,csv,hashlib,collections,subprocess
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
OUT=Path(__file__).parent;ROOT=OUT.parents[2];BASE=Path('/var/lib/coinmaster-native-gui/data/runs/jobs')
contract=json.loads((OUT/'setup-contract.json').read_text());FROZEN=contract['source_commit'];BASELINE=ROOT/'reports/selective-lifecycle-cap30m-113/sizing-dd50-comparison/comparison.json'
v3package=json.loads(BASELINE.read_text())['variants']['v3'];v3receipt=v3package['receipt'];v3raw=Path(v3receipt['artifact']);v3=json.loads(v3raw.read_text())
assert hashlib.sha256(v3raw.read_bytes()).hexdigest()==v3receipt['artifact_sha256'];assert D(v3['terminal_total'])==D('5437208.56951095')
def utc(node):
 if isinstance(node,dict):
  if 'timestamp_ns' in node:node['timestamp_utc']=datetime.fromtimestamp(int(node['timestamp_ns'])/1e9,timezone.utc).isoformat()
  for v in list(node.values()):utc(v)
 elif isinstance(node,list):
  for v in node:utc(v)
def diff(a,b,path=''):
 if isinstance(a,dict) and isinstance(b,dict):
  out=[]
  for k in sorted(set(a)|set(b)):out.extend(diff(a.get(k),b.get(k),path+'.'+k))
  return out
 return [] if a==b else [{'path':path,'V3':a,'variant':b}]
rows=[];details={};funding_journals=[]
for name in ['b25','s10_15','r2','t3']:
 job=BASE/('cm113-v3-'+name+'-20261011');rawreceipt=json.loads((job/'native-run-receipt.json').read_text());art=Path(rawreceipt['artifact']);p=json.loads(art.read_text());m=json.loads((job/'result/minute-risk-summary.json').read_text())
 subprocess.run(['/usr/bin/python3',str(OUT/'validate_pack.py'),str(job)],check=True,capture_output=True,text=True)
 assert (job/'source-commit.txt').read_text().strip()==FROZEN
 journal_path=Path(p['funding_journal']);assert journal_path.is_file() and journal_path.parent==job/'result';assert str(journal_path) not in funding_journals;funding_journals.append(str(journal_path))
 assert p['streaming']['processed_rows_per_source']==1051200 and m['rows']==3153600
 assert p['data_hash']==v3['data_hash'] and p['policy']==v3['policy'] and p['policy_hash']==v3['policy_hash']
 assert p['config'].get('research_v3_risk',{}).get('variant')==name
 changed={k for k in set(p['config'])|set(v3['config']) if p['config'].get(k)!=v3['config'].get(k)};assert changed=={'research_btc_direction_sizing','research_v3_risk'},changed
 assert p['config']['candidate']==v3['config']['candidate'];assert p['config']['fixed_base_fee_policy']==v3['config']['fixed_base_fee_policy']
 assert p['config']['research_v0_zero_tp_netting'] is False and p['config']['tp_fee_floor_v1'] is False
 assert p['status']=='NOT_FAITHFUL_DIAGNOSTIC' and p['ranking_eligible'] is False and p['fee_attribution']['reconciled'] is True
 order_art=p['execution_artifacts']['orders'];order_file=Path(order_art['path']);assert hashlib.sha256(order_file.read_bytes()).hexdigest()==order_art['sha256']
 with order_file.open() as f:order_statuses=dict(collections.Counter(x['status'] for x in csv.DictReader(f)))
 unfinished=sum(v for k,v in order_statuses.items() if k not in {'FILLED','CANCELED','REJECTED','EXPIRED','DENIED'});assert unfinished==0,order_statuses
 assert sum(order_statuses.values())==order_art['rows']
 assert p['terminal_open_positions']==0 and p['terminal_lifecycle']['status']=='FLAT'
 c=m['curves']['all_native_close_samples'];b=m['conditional_upper_to_later_lower_bound'];assert b['samples']==1051200;utc(c);utc(b)
 total=D(p['terminal_total']);base=D(v3['terminal_total']);dd=D(c['top3_distinct_excursions'][0]['drawdown_peak_percent']);assets={}
 for asset in ['BTC','SOL']:
  fills=[x for x in p['fill_audit'] if x['instrument'].startswith(asset)]
  assets[asset]={'fills':len(fills),'fees':str(sum((D(x['commission']) for x in fills),D(0))),'notional':str(sum((D(x['notional']) for x in fills),D(0))),'actions':dict(collections.Counter(x['action'] for x in fills)),'reasons':dict(collections.Counter(x['reason'] for x in fills))}
 assert sum(x['fills'] for x in assets.values())==p['fills'];assert sum((D(x['fees']) for x in assets.values()),D(0))==D(p['native_fees'])
 row={'variant':name.upper(),'TOTAL':str(total),'ACTIVE':p['terminal_active'],'RESERVE':p['terminal_reserve'],'ROI_percent':str((total/D(10000)-1)*100),'delta_V3':str(total-base),'delta_V3_percent':str((total/base-1)*100),'TOTAL_loss_vs_V3_percent':str((base-total)/base*100),'native_global_minute_DD_percent':str(dd),'DD_eligible_le50':dd<=50,'seed_minimum':c['minimum']['equity'],'loss_below_seed_percent':c['maximum_loss_below_seed_percent'],'conditional_upper_to_later_lower_percent':b['maximum']['drawdown_peak_percent'],'fees':p['native_fees'],'maker_fees':p['fee_attribution']['maker']['fees'],'taker_fees':p['fee_attribution']['taker']['fees'],'maker_notional':p['fee_attribution']['maker']['notional'],'taker_notional':p['fee_attribution']['taker']['notional'],'BTC_fills':assets['BTC']['fills'],'SOL_fills':assets['SOL']['fills'],'fills':p['fills'],'orders':p['execution_artifacts']['orders']['rows'],'funding_events':p['funding']['count'],'signed_funding':p['funding']['signed_amount'],'liquidations':p['liquidation_count'],'open_positions':p['terminal_open_positions'],'unfinished_orders':unfinished};rows.append(row)
 before=(job/'pilot-before.txt').read_text();after=(job/'pilot-after.txt').read_text();assert before==after and 'MainPID=2009732' in after and 'NRestarts=0' in after
 receipt={'variant':name,'source_commit':FROZEN,'artifact':str(art),'artifact_sha256':hashlib.sha256(art.read_bytes()).hexdigest(),'exit_code':0,'launched_at':(job/'launched-at.txt').read_text().strip(),'completed_lines':[x for x in rawreceipt['unit_journal'].splitlines() if 'Deactivated successfully' in x or 'Consumed' in x],'pilot_before':before,'pilot_after':after,'resources_before':json.loads((job/'resource-before.json').read_text()),'source_guard_file':str(job/'source-input-hashes.sha256'),'immutable_source_hash_manifest_sha256':hashlib.sha256((job/'immutable-source-hashes.json').read_bytes()).hexdigest(),'immutable_files_verified':106,'data_hash':p['data_hash'],'policy_hash':p['policy_hash'],'config_hash':p['config_hash'],'source_hashes':p['source_hashes'],'streaming':p['streaming'],'minute_rows':m['rows'],'upper_bound_samples':b['samples'],'funding_journal':p['funding_journal'],'funding_journal_sha256':hashlib.sha256(journal_path.read_bytes()).hexdigest(),'terminal_lifecycle':p['terminal_lifecycle'],'terminal_order_status_counts':order_statuses,'unfinished_orders':unfinished,'execution_artifacts':p['execution_artifacts'],'post_boundary_settlement':p['post_boundary_settlement'],'boundary_samples_excluded':m['post_boundary_settlement_excluded_from_interval_curves']}
 (OUT/(name+'-receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n')
 audit={k:v for k,v in p.items() if k.endswith('_audit') or 'diagnostic' in k or k in ['native_order_rejections','pre_submit_tier_margin_gate_blocks','modeled_slippage','liquidation_lockout','liquidation_value']}
 risk=p.get('v3_risk_audit',[]);utc(risk)
 latencies={}
 for event in ['PROTECTIVE_SUBMIT','PROTECTIVE_FILL']:
  vals=[int(x['latency_ns']) for x in risk if x.get('event')==event and 'latency_ns' in x]
  latencies[event]={'count':len(vals),'minimum_ns':min(vals) if vals else None,'maximum_ns':max(vals) if vals else None,'mean_ns':str(sum(map(D,vals))/len(vals)) if vals else None}
 risk_summary={'event_counts':dict(collections.Counter(x.get('event','UNCLASSIFIED') for x in risk)),'event_reason_counts':dict(collections.Counter(x.get('event','UNCLASSIFIED')+':'+str(x.get('reason','')) for x in risk)),'latency':latencies,'full_actual_events':risk}
 audit_counts={k:dict(collections.Counter(x.get('event','UNCLASSIFIED') for x in v if isinstance(x,dict))) for k,v in audit.items() if isinstance(v,list)}
 details[name]={'metrics':row,'receipt':receipt,'config':p['config'],'config_diff_from_V3':diff(v3['config'],p['config']),'source_hashes':p['source_hashes'],'order_statuses':order_statuses,'interval':p['interval'],'run_interval':p['run_interval'],'warmup':p['warmup'],'native_minute_curve':c,'conditional_upper_to_later_lower_bound':b,'conditional_lower_envelope':m['curves']['conditional_ohlc_adverse'],'conditional_margin_breach_count':m['potential_conditional_intrabar_margin_breach_count'],'assets':assets,'fee_attribution':p['fee_attribution'],'v3_risk_summary':risk_summary,'native_audit_event_counts':audit_counts,'retained_native_audits_and_execution_diagnostics':audit,'funding':p['funding'],'status':p['status'],'ranking_eligible':p['ranking_eligible']}
eligible=[r for r in rows if r['DD_eligible_le50']];winner=max(eligible,key=lambda r:D(r['TOTAL']))['variant'] if eligible else None
limitations=['All outputs NOT_FAITHFUL_DIAGNOSTIC/ranking_eligible=false; no live or venue-faithful ranking.','Native minute equity global DD preserves all prior peaks; post-boundary settlement included in TOTAL but excluded from interval DD/seed minimum/TOP3.','Conditional upper-to-strictly-later-lower bound is separate from observed tick DD and does not guarantee an intrabar50% cap or venue survival.','Historical execution uses minute closes/cached books, no BBO/L2/tape; protective latency/quotes and audit counters remain diagnostic.','Signed funding remains UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA; native posting counts are actual, unknown signed amounts are not zero.','Exactly four individual native engines, separate funding journals, no control/repeat/refinement/grid; reusable V3 defaultOFF/source proof supplied by implementation review.','Shared900M/swap0, UID994, PrivateNetwork/env-i/read-only binds; original pilotPID2009732/NRestarts0/release81e6318 preserved, no orders/deploy/restarts.']
proof=ROOT/'reports/v3-risk-four-113/implementation/receipt.json';source_proof=json.loads(proof.read_text());assert source_proof['source_commit']==FROZEN and source_proof['default'] is None and source_proof['verification']['independent_review'].endswith(FROZEN)
package={'source_defaultOFF_and_review_proof':{'path':str(proof),'sha256':hashlib.sha256(proof.read_bytes()).hexdigest(),'default':source_proof['default'],'independent_review':source_proof['verification']['independent_review']},'source_commit':FROZEN,'economic_runs':4,'objective':'Maximum TOTAL among native global minuteDD<=50; none if none','winner_highest_TOTAL_native_DD_le50':winner,'reusable_V3':{'TOTAL':v3['terminal_total'],'ROI_percent':str((D(v3['terminal_total'])/10000-1)*100),'native_DD_percent':'67.2863064484','conditional_bound_percent':'68.4920098440','artifact':str(v3raw),'artifact_sha256':v3receipt['artifact_sha256'],'baseline_package_sha256':hashlib.sha256(BASELINE.read_bytes()).hexdigest(),'source_commit':v3receipt['source_commit']},'variants':details,'limitations':limitations}
(OUT/'comparison.json').write_text(json.dumps(package,indent=2)+'\n')
basecurve=v3package['native_minute_curve'];utc(basecurve)
base_metrics=v3package['metrics']
extract={'source_commit':FROZEN,'actual_fresh_engines':4,'baseline_reused_no_control_engine':True,'winner_native_DD_le50':winner,'identity_verification':{'all_four_immutable_packs106':True,'source_runtime_hashes_unchanged':True,'data_policy_candidate_fee_seed_interval_same_as_V3':True,'config_deltas_exactly_direction_selector_to_named_v3_selector':True,'each_source_rows1051200':True,'each_native_observations3153600':True,'each_bound_samples1051200':True,'separate_native_funding_journals':True,'all_terminal_flat_zero_unfinished_orders':True,'pilot_PID2009732_NRestarts0_unchanged':True,'defaultOFF_and_independent_source_review':package['source_defaultOFF_and_review_proof']},'limitations':{'eligibility':'Native global marked-minute equity DD only','B25_conditional_OHLC_bound_exceeds50':True,'intrabar_cap_guarantee':False,'signed_funding':'UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA','faithful_execution':False},'rows':[]}
keys=['TOTAL','ROI_percent','native_global_minute_DD_percent','conditional_upper_to_later_lower_percent','seed_minimum','fees','BTC_fills','SOL_fills','funding_events','signed_funding','liquidations','open_positions']
extract['rows'].append({'variant':'V3_REUSED',**{k:base_metrics[k] for k in keys},'seed_minimum_UTC':basecurve['minimum']['timestamp_utc'],'terminal_flat':v3['terminal_lifecycle']['status']=='FLAT','TOP3':basecurve['top3_distinct_excursions'],'config_diff_from_V3':[]})
for name,d in details.items():extract['rows'].append({'variant':name.upper(),**{k:d['metrics'][k] for k in keys},'ACTIVE':d['metrics']['ACTIVE'],'RESERVE':d['metrics']['RESERVE'],'TOTAL_loss_vs_V3_percent':d['metrics']['TOTAL_loss_vs_V3_percent'],'seed_minimum_UTC':d['native_minute_curve']['minimum']['timestamp_utc'],'terminal_flat':True,'unfinished_orders':0,'TOP3':d['native_minute_curve']['top3_distinct_excursions'],'config_diff_from_V3':d['config_diff_from_V3'],'native_risk_events':d['v3_risk_summary']['event_counts'],'native_protective_latency_ns':d['v3_risk_summary']['latency']})
(OUT/'root-review-extract.json').write_text(json.dumps(extract,indent=2)+'\n')

with (OUT/'comparison.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
md=['# CM113 four individual V3 risk comparisons','','Four sequential native24m engines B25 → S10_15 → R2 → T3 on source `'+FROZEN+'`. Reused V3 TOTAL5437208.56951095/nativeDD67.2863064484%/conditionalbound68.4920098440%. Seed10000/reserve0; identical genuine Bybit [2024-09-01,2026-09-01), fees/funding/margin/execution/cap30m/three repairs/V3direction/SOL H.','','**Eligible winner: '+(winner if winner else 'none')+'.** Greatest terminal TOTAL among candidates with native global minuteDD<=50. B25 sacrifices55.96152893% of V3 TOTAL; its nativeDD46.48498057% qualifies, while conditionalOHLC59.46109682% remains above50. This is not an intrabar cap guarantee.','','| Variant | TOTAL USDT | ROI % | Loss vs V3 % | Native DD % | Conditional bound % | Seed minimum | BTC/SOL fills |','|---|---:|---:|---:|---:|---:|---:|---:|']
for r in rows:md.append('| {} | {} | {} | {} | {} | {} | {} | {}/{} |'.format(r['variant'],r['TOTAL'],str(round(D(r['ROI_percent']),6)),str(round(D(r['TOTAL_loss_vs_V3_percent']),6)),str(round(D(r['native_global_minute_DD_percent']),6)),str(round(D(r['conditional_upper_to_later_lower_percent']),6)),r['seed_minimum'],r['BTC_fills'],r['SOL_fills']))
md.extend(['','All four processed1051200 rows per source/3153600 native observer rows/1051200 strict-later bound samples. Fees/native fills/terminal flat reconciled. JSON retains ACTIVE/reserve, maker/taker fees/notionals, BTC/SOL actual reasons, fundingUNKNOWN, guard/trigger/rearm/protective fill/latency audits and execution diagnostics, exact config differences, input/source hashes and receipts. No additional trace scans.','','| Variant | Rank | Native DD % | Peak UTC | Trough UTC | Recovery UTC |','|---|---:|---:|---|---|---|'])
for n,d in details.items():
 for i,x in enumerate(d['native_minute_curve']['top3_distinct_excursions'],1):
  md.append('| {} | {} | {} | {} | {} | {} |'.format(n.upper(),i,str(round(D(x['drawdown_peak_percent']),6)),x['peak']['timestamp_utc'],x['trough']['timestamp_utc'],(x.get('recovery') or {}).get('timestamp_utc','Not recovered by interval end')))
md.extend(['','Actual native risk event counts and trigger-to-execution latency (ns):',''])
for n,d in details.items():
 md.append('- '+n.upper()+': events '+json.dumps(d['v3_risk_summary']['event_counts'],separators=(',',':'))+'; latency '+json.dumps(d['v3_risk_summary']['latency'],separators=(',',':')))
md.extend(['','Public reports: [comparison JSON](https://github.com/VF78/coinmaster/blob/codex/nautilus-btc-sol-mvp/reports/v3-risk-four-113/comparison/comparison.json), [CSV](https://github.com/VF78/coinmaster/blob/codex/nautilus-btc-sol-mvp/reports/v3-risk-four-113/comparison/comparison.csv), [hashes](https://github.com/VF78/coinmaster/blob/codex/nautilus-btc-sol-mvp/reports/v3-risk-four-113/comparison/SHA256SUMS).'])
md.extend(['','Limitations:','']+['- '+x for x in limitations]);(OUT/'README.md').write_text('\n'.join(md)+'\n')
contract.update(status='FOUR_APPROVED_ECONOMIC_RUNS_COMPLETED',economic_runs=4,eligible_winner=winner,authoritative_report='comparison.json');(OUT/'setup-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
(OUT/'SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in sorted(OUT.iterdir()) if f.is_file() and f.name!='SHA256SUMS'))
print(json.dumps({'winner':winner,'rows':rows}))
