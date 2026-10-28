"""Existing QUAL_STRESS native-output extraction only; no engine or economic simulation."""
from pathlib import Path
import json,csv,gzip,hashlib,sqlite3,collections,itertools
from decimal import Decimal as D
from datetime import datetime,timezone
B=Path('/Users/vf/Documents/ChatGPT/Coinmaster');O=B/'research-worktrees/btc-pattern-pilot-m2-20261021/reports/e4-c1-fast-pilot-20261028/evidence'
Q=B/'runtime/var/research-jobs/e4-c1-fast-pilot-20261028/QUAL_STRESS/result';C=B/'runtime/var/research-jobs/e4-c1-fast-pilot-20261028/BTC_POSTCUT_D1/result'
qfile=next(Q.glob('*-direction.json'));cfile=next(C.glob('*-direction.json'));q=json.load(open(qfile));c=json.load(open(cfile))
def utc(n):return datetime.fromtimestamp(int(n)/1e9,timezone.utc).isoformat()
def ns(s):return int(datetime.fromisoformat(s).timestamp())*1000000000
def write(name,rows):
 with open(O/name,'w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
fillfields=('accept_ns','action','commission','commission_currency','fill_ns','instrument','level','native_liquidity_side','notional','order_type','policy_hash','post_only','px','qty','reason','submit_ns','venue')
def proj(x):return tuple(x.get(k) for k in fillfields)
first_mismatch=next(((qa,ca) for qa,ca in zip(q['fill_audit'],c['fill_audit']) if proj(qa)!=proj(ca)),None)
cut0=min(int(x['fill_ns']) for x in first_mismatch)

qprefix=[proj(x) for x in q['fill_audit'] if int(x['fill_ns'])<cut0];cprefix=[proj(x) for x in c['fill_audit'] if int(x['fill_ns'])<cut0]
prefix=dict(first_mismatched_fill_projection=dict(QUAL_STRESS={k:first_mismatch[0].get(k) for k in fillfields},BTC_POSTCUT_D1={k:first_mismatch[1].get(k) for k in fillfields}),before_first_economic_delta_ns=cut0,before_first_economic_delta_utc=utc(cut0),fill_economic_projection_equal=qprefix==cprefix,fill_count_QUAL_STRESS=len(qprefix),fill_count_benchmark=len(cprefix),projection_fields=fillfields,settled_rows_compared=0,settled_projection_equal=True,first_settled_difference=None)
windows={'OCT':('2024-10-03T00:00:00+00:00','2024-10-06T00:00:00+00:00'),'JAN':('2025-01-10T00:00:00+00:00','2025-01-22T00:00:00+00:00'),'NOV':('2025-10-22T00:00:00+00:00','2025-12-03T00:00:00+00:00'),'FINAL':('2026-07-06T00:00:00+00:00','2026-09-01T00:00:00+00:00')}
months={};wins={k:dict(window=k,start_UTC=v[0],end_exclusive_UTC=v[1],rows=0,maximum_global_DD=D(0)) for k,v in windows.items()};H=D(10000);n=0
with gzip.open(Q/'minute-native-settled-receipts.csv.gz','rt') as fq,gzip.open(C/'minute-native-settled-receipts.csv.gz','rt') as fc:
 cq=csv.DictReader(fq);cc=csv.DictReader(fc)
 for qr,cr in itertools.zip_longest(cq,cc):
  if qr is None:raise ValueError('Q receipts short')
  n+=1;t=int(qr['receipt_ns']);source=int(qr['source_quote_ns']);e=D(qr['paired_close_equity']);H=max(H,e);dd=1-e/H
  if t<cut0:
   prefix['settled_rows_compared']+=1
   if qr!=cr:
    prefix['settled_projection_equal']=False
    if prefix['first_settled_difference'] is None:prefix['first_settled_difference']={'Q':qr,'R':cr}
  elif prefix.get('first_post_treatment_difference') is None and qr!=cr:
   prefix['first_post_treatment_difference']={'receipt_ns':t,'receipt_UTC':utc(t),'QUAL_STRESS_cash':qr['cash'],'benchmark_cash':cr['cash'],'QUAL_STRESS_E':qr['paired_close_equity'],'benchmark_E':cr['paired_close_equity']}
  m=utc(source)[:7]
  if m not in months:months[m]=dict(month=m,rows=0,first_source_UTC=utc(source),first_receipt_UTC=utc(t),first_E=e,first_cash=D(qr['cash']),max_global_DD=D(0))
  z=months[m];z.update(rows=z['rows']+1,last_source_UTC=utc(source),last_receipt_UTC=utc(t),last_E=e,last_cash=D(qr['cash']),max_global_DD=max(z['max_global_DD'],dd))
  for key,(lo,hi) in windows.items():
   if ns(lo)<=t<ns(hi):
    z=wins[key];z['rows']+=1
    if 'first_E' not in z:z.update(first_E=e,first_receipt_UTC=utc(t))
    z.update(last_E=e,last_receipt_UTC=utc(t),maximum_global_DD=max(z['maximum_global_DD'],dd))
cashmonths={x['month']:x for x in q['summary']['monthly_returns']}
for m,x in months.items():
 x.update(first_to_last_settled_return=x['last_E']/x['first_E']-1,actual_report_cash_month_end=cashmonths[m]['total'],actual_report_cash_month_return=cashmonths[m]['return'],settled_month_basis='SOURCE_QUOTE_UTC_FIRST_TO_LAST_RECEIPT;GLOBAL_H_NEVER_RESET',cash_month_basis=q['summary']['monthly_returns_basis'])
write('QUAL_STRESS-months.csv',list(months.values()));write('QUAL_STRESS-windows.csv',list(wins.values()))
settled_H=H;settled_maxdd=max(x['max_global_DD'] for x in months.values())
# Native cash transitions: actual pre/post cash, never reconstructed fill PnL.
obs=q['coherent_native_observer'];seqs={int(v['timestamp_ns']) for e in obs['event_drawdown']['top3_distinct_excursions'] for v in e.values() if isinstance(v,dict) and 'timestamp_ns' in v};seqs.add(int(obs['event_drawdown']['minimum']['timestamp_ns']))
kinds=collections.Counter();joined={};pre={};postcounts=collections.Counter();pair_errors=[];fill_delta=D(0);fund_delta=D(0);cash_changes=[];lastcash=None;lastseq=0;pairrows=[];eventH=D(10000);eventmax=D(0);eventsamples=1;boundary_seen=False;eventpeak=0;eventworst=None
with gzip.open(Q/'coherent-native-events.jsonl.gz','rt') as f:
 for line in f:
  x=json.loads(line);s=x['sequence'];kind=x['kind'];kinds[kind]+=1
  if s!=lastseq+1:raise ValueError('sequence gap')
  lastseq=s
  if s in seqs:joined[s]={k:x[k] for k in ('sequence','kind','event_ns','receipt_ns','mark_available_ns','cash','equity','native_id')};joined[s]['event_UTC']=utc(x['event_ns']);joined[s]['receipt_UTC']=utc(x['receipt_ns'])
  cash=D(x['cash'])
  boundary_left=(int(x['event_ns'])==int(obs['end_exclusive_ns']) and not boundary_seen and kind in ('PREQUOTE_DIRECT_NATIVE','PRE_FILL_LAST_COMMITTED_NATIVE_COPY','PRE_FUNDING_COMMITTED_NATIVE_COPY'))
  if kind!='SETTLED_PRE_NEXT_SOURCE_WATERMARK' and (int(x['event_ns'])<int(obs['end_exclusive_ns']) or boundary_left):
   if boundary_left:boundary_seen=True
   eq=D(x['equity']);eventsamples+=1
   if eq>=eventH:eventH=eq;eventpeak=s
   dd=1-eq/eventH
   if dd>eventmax:eventmax=dd;eventworst=dict(peak_sequence=eventpeak,trough_sequence=s,event_ns=x['event_ns'],event_UTC=utc(x['event_ns']),peak_equity=str(eventH),trough_equity=str(eq))
  # A settled watermark is a retrospective immutable copy, not a new
  # physical account transition. Do not count its backward cash snapshot.
  if kind!='SETTLED_PRE_NEXT_SOURCE_WATERMARK':
   if lastcash is not None and cash!=lastcash:cash_changes.append(dict(sequence=s,kind=kind,native_id=x['native_id'],event_ns=x['event_ns'],delta=str(cash-lastcash)))
   lastcash=cash
  if kind.startswith('PRE_FILL_') or kind.startswith('PRE_FUNDING_'):
   key=('FILL' if kind.startswith('PRE_FILL') else 'FUNDING',x['native_id'])
   if key in pre:pair_errors.append(['duplicate_pre',key])
   pre[key]=x
  if kind in ('POST_FILL_COMMITTED_NATIVE','POST_FUNDING_ACCOUNT_NATIVE'):
   typ='FILL' if kind.startswith('POST_FILL') else 'FUNDING';key=(typ,x['native_id']);postcounts[key]+=1;p=pre.pop(key,None)
   if p is None:pair_errors.append(['missing_pre',key]);continue
   delta=cash-D(p['cash'])
   if typ=='FILL':fill_delta+=delta
   else:fund_delta+=delta
   pairrows.append(dict(kind=typ,native_id=x['native_id'],event_ns=x['event_ns'],event_UTC=utc(x['event_ns']),pre_sequence=p['sequence'],post_sequence=s,native_cash_before=p['cash'],native_cash_after=x['cash'],actual_cash_delta=str(delta)))
fundrows=q['funding_cash_audit'];fundids=[(x[0],x[1]) for x in fundrows];fundsum=sum((D(x[5]) for x in fundrows),D(0));badfund=[x for x in fundrows if D(x[4])-D(x[3])!=D(x[5])]
db=sqlite3.connect('file:'+str(next(Q.glob('*funding.sqlite')))+'?mode=ro',uri=True);sqlfund=db.execute('select event_id,instrument_id,ts_event,before_total,after_total,signed_delta from funding_cash order by ts_event,event_id').fetchall();sqlorig=db.execute('select event_id,instrument_id,ts_event,account_total_after from funding_events').fetchall()
fundmap={(x[0],x[1]):x for x in fundrows};sqlmap={(x[0],x[1]):list(x) for x in sqlfund};fundpostmap={x['native_id']:x for x in pairrows if x['kind']=='FUNDING'}
fundjoinok=all(x[0] in fundpostmap and D(fundpostmap[x[0]]['actual_cash_delta'])==D(x[5]) for x in fundrows)
recon_residual=D(q['terminal_total'])-D(10000)-fill_delta-fund_delta
cashrecon=dict(method='SUM_ACTUAL_NATIVE_PRE_POST_CASH_TRANSITIONS_BY_UNIQUE_FILL_OR_FUNDING_ID;NO_DERIVED_TRADE_PNL',seed='10000',actual_native_fill_cash_delta=str(fill_delta),actual_native_funding_cash_delta=str(fund_delta),terminal=str(q['terminal_total']),residual=str(recon_residual),native_fill_pairs=sum(1 for x in pairrows if x['kind']=='FILL'),native_funding_pairs=sum(1 for x in pairrows if x['kind']=='FUNDING'),unmatched_pre_count=len(pre),duplicate_post_ids=sum(v-1 for v in postcounts.values()),pair_errors=pair_errors,cash_change_count=len(cash_changes),cash_changes_outside_post_fill_or_funding=[x for x in cash_changes if x['kind'] not in ('POST_FILL_COMMITTED_NATIVE','POST_FUNDING_ACCOUNT_NATIVE')],fees='Nativecashdeltasalreadyincludefees;NOfee subtractionagain',original_JSON_reconciliation='R_ORIGINAL_COMPLETE_NATIVE_LIFECYCLES_PRESERVED',independent_native_position_lifecycle_PNL_reconciliation='INDEPENDENT_SUM_PENDING')
cashrecon['status']='PASS_NATIVE_CASH_TRANSITION_IDENTITY' if recon_residual==0 and not pair_errors and not pre and not cashrecon['duplicate_post_ids'] and not cashrecon['cash_changes_outside_post_fill_or_funding'] else 'UNKNOWN_UNCLOSED_NATIVE_TRANSITIONS'
write('QUAL_STRESS-native-cash-transitions.csv',pairrows)
attempts=[x for x in q['c1_audit'] if x['event']=='ATTEMPT_SUBMIT'];fills=[x for x in q['fill_audit'] if x['reason'] in ('C1_RESIDUAL_CUT','C1_RESIDUAL_RESTORE')];group_rows=[]
for a in attempts:
 g=a['group'];kind=a['kind'];actual=next(x for x in q['c1_audit'] if x.get('group')==g and x['event']=='ACTUAL_FILL' and x['kind']==kind);native=next(x for x in q['c1_audit'] if x.get('group')==g and x['event']=='NATIVE_FILL_RECEIPT' and x['intent_id']==a['intent_id']);group_rows.append(dict(group=g,kind=kind,instrument=a['instrument'],submit_UTC=utc(a['timestamp_ns']),requested_lots=a['lots'],actual_lots=actual['lots'],step=a['step'],actual_quantity=native['quantity'],actual_price=native['price'],actual_fee=native['commission'],native_order_id=native['order_id'],native_trade_id=native['trade_id'],E=a['E'],H=a['H'],DD=a['DD']))
write('QUAL_STRESS-c1-actions.csv',group_rows)
fees=sum((D(x['commission']) for x in fills),D(0));turnover=sum((D(x['notional']) for x in fills),D(0))
result=dict(status='QUAL_STRESS_COMPLETED_NOT_SELECTED_FINANCIAL_OBSERVATION',TOTAL=q['terminal_total'],TOTAL_minus_C1=str(D(q['terminal_total'])-D(c['terminal_total'])),TOTAL_minus_E4=str(D(q['terminal_total'])-D('5631617.35953723')),gap_to_floor=str(D('5470396.514987347')-D(q['terminal_total'])),config_hash=q['config_hash'],data_hash=q['data_hash'],policy_hash=q['policy_hash'],settled_receipts_streamed=n,prefix=prefix,coherent_observer=obs,event_endpoint_sequence_join=joined,event_kind_counts=dict(kinds),event_sequence_count=lastseq,native_cash_transition_reconciliation=cashrecon,funding=dict(rows=len(fundrows),unique_event_instrument_ids=len(set(fundids)),actual_signed_sum=str(fundsum),bad_arithmetic_rows=badfund,JSON_matches_SQLite=fundmap==sqlmap,sqlite_funding_events_rows=len(sqlorig),sqlite_funding_cash_rows=len(sqlfund),unique_original_event_ids=len({x[0] for x in sqlorig}),event_stream_pair_delta_match=fundjoinok,bridge_is_funding=False),C1_interventions=dict(cuts=sum(x['kind']=='CUT' for x in attempts),restores=sum(x['kind']=='RESTORE' for x in attempts),revocations=sum(x['event']=='TOKEN_REVOKED' for x in q['c1_audit']),native_intervention_fees=str(fees),native_intervention_turnover=str(turnover),fee_change_vs_benchmark=str(fees-sum((D(x['commission']) for x in c['fill_audit'] if x['reason'] in ('C1_RESIDUAL_CUT','C1_RESIDUAL_RESTORE')),D(0))),all_fills=q['fills'],native_total_fees=q['native_fees']),liquidations=q['liquidation_count'],terminal=q['terminal_lifecycle'],original_incomplete_cash_reconciliation=q['native_cash_reconciliation'],source_mode_actual_native=True,new_runs=0,tests=0)
result['funding']['original_journal_cash_after_matches']=all((x[0],x[1]) in fundmap and D(x[3])==D(fundmap[(x[0],x[1])][4]) for x in sqlorig)

lif=q['native_cash_reconciliation']['native_position_lifecycle_export'];positions=lif['positions']
keys=[tuple(x[k] for k in ('position_id','opened_ns','closed_ns','opening_order_id','native_fill_lifecycle_sha256')) for x in positions]
pnlsum=sum((D(x['realized_pnl']) for x in positions),D(0));posbridge=D(q['terminal_total'])-D(10000)-pnlsum-fundsum
closed=all(x['closed'] and int(x['closed_ns'])>=int(x['opened_ns']) for x in positions)
result['native_position_lifecycle_reconciliation']=dict(count=len(positions),all_closed=closed,unique_lifecycle_identities=len(set(keys)),native_realized_pnl_sum=str(pnlsum),actual_funding_sum=str(fundsum),terminal_bridge=str(posbridge),fees_already_in_native_realized_pnl=True,duplicate_native_copies=lif['duplicate_native_copies'])
result['native_cash_transition_reconciliation']['independent_native_position_lifecycle_PNL_reconciliation']='PASS_EXACT' if closed and len(set(keys))==len(keys) and posbridge==0 and pnlsum==fill_delta else 'FAIL'
result['independent_drawdown']=dict(settled_maximum_percent=str(100*settled_maxdd),event_maximum_percent=str(100*eventmax),event_samples=eventsamples,event_worst=eventworst,settled_initial_seed_included=True,event_initial_seed_included=True,one_terminal_boundary_left_limit_included=boundary_seen,retrospective_watermarks_excluded=True,event_order='sequence; endpoints joined using event_ns')
execution=Q.parent/'execution.json';ex=json.load(open(execution));receiptsha=hashlib.sha256(execution.read_bytes()).hexdigest()
result['execution_verification']=dict(receipt_sha256=receiptsha,attempt_uuid=ex['attempt_uuid'],source_commit=ex['source_commit'],config_sha256=ex['config_sha256'],actual_native_child_pid=ex['actual_native_child_pid'],actual_native_child_exit=ex['actual_native_child_exit'])
cap=D('51.80315157406654834417870238');floor=D('5470396.514987347')
checks=dict(execution_receipt=receiptsha=='bcc3d3acd665a7af6d514d79e1568da2df7eb35466911650d265201a71b98857',child_exit=ex['actual_native_child_pid']==74342 and ex['actual_native_child_exit']==0,uuid=ex['attempt_uuid']=='e98fc3db-6497-47f8-84c0-1e2fdf81b9d3',source=ex['source_commit']=='fccd60c01e8cae5e8258748b046f43f88a16bb79',config=q['config_hash']==ex['config_sha256']=='5a1aab4a8e0c75711869fd886aa80c08052874f38e3d107f6d2bea925ac62883',floor=D(q['terminal_total'])>=floor,settled_DD=100*settled_maxdd<=cap,event_DD=100*eventmax<=cap,settled_report_exact=100*settled_maxdd==D(obs['settled_drawdown']['top3_distinct_excursions'][0]['drawdown_peak_percent']),event_report_exact=100*eventmax==D(obs['event_drawdown']['top3_distinct_excursions'][0]['drawdown_peak_percent']),event_samples_match=eventsamples==obs['event_drawdown']['samples'],cash_reconciled=cashrecon['status']=='PASS_NATIVE_CASH_TRANSITION_IDENTITY',position_reconciled=closed and len(set(keys))==len(keys) and posbridge==0 and pnlsum==fill_delta,funding_reconciled=fundmap==sqlmap and fundjoinok and not badfund and fund_delta==fundsum,zero_liquidations=q['liquidation_count']==0,terminal_flat=q['terminal_open_positions']==0,months24=len(months)==24,prefix_equal=prefix['settled_projection_equal'] and prefix['fill_economic_projection_equal'])
checks['native_report_identity']=hashlib.sha256(qfile.read_bytes()).hexdigest()=='061b23b19c2bd97242642c5ededf19442f33aa5e97312d27c6889c4035cc841e'
checks['stress_argv']='--qualification-stress' in ex['argv']
checks['terminal_flat']=checks['terminal_flat'] and q['terminal_lifecycle']['status']=='FLAT' and q['terminal_lifecycle']['lockout']
result['acceptance_checks']=checks
technical={k:v for k,v in checks.items() if k not in ('floor','settled_DD','event_DD')}
result['technical_status']='PASS' if all(technical.values()) else 'FAIL_OR_UNKNOWN'
result['risk_status']='PASS' if checks['settled_DD'] and checks['event_DD'] else 'FAIL_OR_UNKNOWN'
result['stress_profit_floor_status']='PASS' if checks['floor'] else 'FAIL_DIAGNOSTIC'
result['status']='PASS_TECHNICAL_AND_RISK_STRESS_PROFIT_FLOOR_FAIL_DIAGNOSTIC' if all(technical.values()) and result['risk_status']=='PASS' and not checks['floor'] else 'FAIL_OR_UNKNOWN'
result['profit_retention_vs_benchmark_percent']=str(D(q['terminal_total'])/D(c['terminal_total'])*100)
result['net_profit_retention_vs_benchmark_percent']=str((D(q['terminal_total'])-D(10000))/(D(c['terminal_total'])-D(10000))*100)
result['stress_cost_vs_benchmark']=str(D(q['terminal_total'])-D(c['terminal_total']))
result['native_report_sha256']=hashlib.sha256(qfile.read_bytes()).hexdigest()
result['TOTAL_minus_benchmark']=result.pop('TOTAL_minus_C1');result['comparison_reference']='BTC_POSTCUT_D1';result['limits']=['Existing native outputs only; no new native runs, tests, optimization, deployment or live qualification','Synthetic minute-close L1 and historical fees/depth assumptions; no intraminute path or venue capacity guarantee','Current campaign DD cap passes; strict 50 percent target is not met']
(O/'QUAL_STRESS-analysis.json').write_text(json.dumps(result,indent=2))
write('QUAL_STRESS-native-position-lifecycles.csv',positions)

inputs=[B/'runtime/var/research-jobs/e4-c1-fast-pilot-20261028/source-BTC-POSTCUT-D1-fccd60c01e8c/runtime/coinmaster/research/paired_observer.py',execution,O/'analyze_QUAL_STRESS_existing.py',O/'analyze_FIRST_FRESH_existing.py',O/'BTC_POSTCUT_D1-analysis.json',qfile,cfile,Q/'coherent-native-events.jsonl.gz',Q/'minute-native-settled-receipts.csv.gz',C/'minute-native-settled-receipts.csv.gz',next(Q.glob('*funding.sqlite'))];pins={}
for p in inputs:
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 pins[str(p)]=h.hexdigest()
(O/'QUAL_STRESS-analysis-input-hashes.json').write_text(json.dumps(pins,indent=2))
print(json.dumps(dict(status=result['status'],checks=checks,dd=result['independent_drawdown'],position=result['native_position_lifecycle_reconciliation'],TOTAL=result['TOTAL'],prefix_equal=prefix['settled_projection_equal'],fill_prefix_equal=prefix['fill_economic_projection_equal'],cash_transition_status=cashrecon['status'],cash_residual=cashrecon['residual'],funding_sum=str(fundsum),interventions=result['C1_interventions']),indent=2))
