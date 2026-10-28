"""Existing FIRST_FRESH native-output extraction only; no engine or economic simulation."""
from pathlib import Path
import json,csv,gzip,hashlib,sqlite3,collections,itertools
from decimal import Decimal as D
from datetime import datetime,timezone
B=Path('/Users/vf/Documents/ChatGPT/Coinmaster');O=B/'research-worktrees/btc-pattern-pilot-m2-20261021/reports/e4-c1-fast-pilot-20261028/evidence'
Q=B/'runtime/var/research-jobs/e4-c1-fast-pilot-20261028/FIRST_FRESH_COMBO/result';C=B/'runtime/var/research-jobs/e4-c1-fast-pilot-20261028/COMBO/result'
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
prefix=dict(first_mismatched_fill_projection=dict(R={k:first_mismatch[0].get(k) for k in fillfields},C1={k:first_mismatch[1].get(k) for k in fillfields}),before_first_economic_delta_ns=cut0,before_first_economic_delta_utc=utc(cut0),fill_economic_projection_equal=qprefix==cprefix,fill_count_FIRST_FRESH=len(qprefix),fill_count_R=len(cprefix),projection_fields=fillfields,settled_rows_compared=0,settled_projection_equal=True,first_settled_difference=None)
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
   prefix['first_post_treatment_difference']={'receipt_ns':t,'receipt_UTC':utc(t),'FIRST_FRESH_cash':qr['cash'],'R_cash':cr['cash'],'FIRST_FRESH_E':qr['paired_close_equity'],'R_E':cr['paired_close_equity']}
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
write('FIRST_FRESH-months.csv',list(months.values()));write('FIRST_FRESH-windows.csv',list(wins.values()))
# Native cash transitions: actual pre/post cash, never reconstructed fill PnL.
obs=q['coherent_native_observer'];seqs={int(v['timestamp_ns']) for e in obs['event_drawdown']['top3_distinct_excursions'] for v in e.values() if isinstance(v,dict) and 'timestamp_ns' in v};seqs.add(int(obs['event_drawdown']['minimum']['timestamp_ns']))
kinds=collections.Counter();joined={};pre={};postcounts=collections.Counter();pair_errors=[];fill_delta=D(0);fund_delta=D(0);cash_changes=[];lastcash=None;lastseq=0;pairrows=[]
with gzip.open(Q/'coherent-native-events.jsonl.gz','rt') as f:
 for line in f:
  x=json.loads(line);s=x['sequence'];kind=x['kind'];kinds[kind]+=1
  if s!=lastseq+1:raise ValueError('sequence gap')
  lastseq=s
  if s in seqs:joined[s]={k:x[k] for k in ('sequence','kind','event_ns','receipt_ns','mark_available_ns','cash','equity','native_id')};joined[s]['event_UTC']=utc(x['event_ns']);joined[s]['receipt_UTC']=utc(x['receipt_ns'])
  cash=D(x['cash'])
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
write('FIRST_FRESH-native-cash-transitions.csv',pairrows)
attempts=[x for x in q['c1_audit'] if x['event']=='ATTEMPT_SUBMIT'];fills=[x for x in q['fill_audit'] if x['reason'] in ('C1_RESIDUAL_CUT','C1_RESIDUAL_RESTORE')];group_rows=[]
for a in attempts:
 g=a['group'];kind=a['kind'];actual=next(x for x in q['c1_audit'] if x.get('group')==g and x['event']=='ACTUAL_FILL' and x['kind']==kind);native=next(x for x in q['c1_audit'] if x.get('group')==g and x['event']=='NATIVE_FILL_RECEIPT' and x['intent_id']==a['intent_id']);group_rows.append(dict(group=g,kind=kind,instrument=a['instrument'],submit_UTC=utc(a['timestamp_ns']),requested_lots=a['lots'],actual_lots=actual['lots'],step=a['step'],actual_quantity=native['quantity'],actual_price=native['price'],actual_fee=native['commission'],native_order_id=native['order_id'],native_trade_id=native['trade_id'],E=a['E'],H=a['H'],DD=a['DD']))
write('FIRST_FRESH-c1-actions.csv',group_rows)
fees=sum((D(x['commission']) for x in fills),D(0));turnover=sum((D(x['notional']) for x in fills),D(0))
result=dict(status='FIRST_FRESH_COMPLETED_NOT_SELECTED_FINANCIAL_OBSERVATION',TOTAL=q['terminal_total'],TOTAL_minus_C1=str(D(q['terminal_total'])-D(c['terminal_total'])),TOTAL_minus_E4=str(D(q['terminal_total'])-D('5631617.35953723')),gap_to_floor=str(D('5470396.514987347')-D(q['terminal_total'])),config_hash=q['config_hash'],data_hash=q['data_hash'],policy_hash=q['policy_hash'],settled_receipts_streamed=n,prefix=prefix,coherent_observer=obs,event_endpoint_sequence_join=joined,event_kind_counts=dict(kinds),event_sequence_count=lastseq,native_cash_transition_reconciliation=cashrecon,funding=dict(rows=len(fundrows),unique_event_instrument_ids=len(set(fundids)),actual_signed_sum=str(fundsum),bad_arithmetic_rows=badfund,JSON_matches_SQLite=fundmap==sqlmap,sqlite_funding_events_rows=len(sqlorig),sqlite_funding_cash_rows=len(sqlfund),unique_original_event_ids=len({x[0] for x in sqlorig}),event_stream_pair_delta_match=fundjoinok,bridge_is_funding=False),C1_interventions=dict(cuts=sum(x['kind']=='CUT' for x in attempts),restores=sum(x['kind']=='RESTORE' for x in attempts),revocations=sum(x['event']=='TOKEN_REVOKED' for x in q['c1_audit']),native_intervention_fees=str(fees),native_intervention_turnover=str(turnover),fee_change_vs_C1=str(fees-D('17006.92024796')),all_fills=q['fills'],native_total_fees=q['native_fees']),liquidations=q['liquidation_count'],terminal=q['terminal_lifecycle'],original_incomplete_cash_reconciliation=q['native_cash_reconciliation'],source_mode_actual_native=True,new_runs=0,tests=0)
result['funding']['original_journal_cash_after_matches']=all((x[0],x[1]) in fundmap and D(x[3])==D(fundmap[(x[0],x[1])][4]) for x in sqlorig)
(O/'FIRST_FRESH-analysis.json').write_text(json.dumps(result,indent=2))
inputs=[qfile,cfile,Q/'coherent-native-events.jsonl.gz',Q/'minute-native-settled-receipts.csv.gz',C/'minute-native-settled-receipts.csv.gz',next(Q.glob('*funding.sqlite'))];pins={}
for p in inputs:
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 pins[str(p)]=h.hexdigest()
(O/'FIRST_FRESH-analysis-input-hashes.json').write_text(json.dumps(pins,indent=2))
print(json.dumps(dict(TOTAL=result['TOTAL'],prefix_equal=prefix['settled_projection_equal'],fill_prefix_equal=prefix['fill_economic_projection_equal'],cash_transition_status=cashrecon['status'],cash_residual=cashrecon['residual'],funding_sum=str(fundsum),interventions=result['C1_interventions']),indent=2))
