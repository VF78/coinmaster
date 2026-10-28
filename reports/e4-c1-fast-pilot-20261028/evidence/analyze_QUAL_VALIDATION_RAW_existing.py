"""Independent financial evidence from failed qualification raw artifact. No engine imports/runs."""
from pathlib import Path
import json,csv,gzip,hashlib,sqlite3,collections,zlib,io
from decimal import Decimal as D
from datetime import datetime,timezone
B=Path('/Users/vf/Documents/ChatGPT/Coinmaster');P=B/'research-worktrees/btc-pattern-pilot-m2-20261021/reports/e4-c1-fast-pilot-20261028';O=P/'evidence';J=B/'runtime/var/research-jobs/e4-c1-fast-pilot-20261028';Q=J/'QUAL_VALIDATION/result';qfile=next(Q.glob('*-raw-native.json'));q=json.load(open(qfile))
def utc(n):return datetime.fromtimestamp(int(n)/1e9,timezone.utc).isoformat()
def write(name,rows):
 if not rows:return
 with open(O/name,'w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
trace_integrity={}
def trace(path):
 d=zlib.decompressobj(16+zlib.MAX_WBITS);chunks=[]
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):chunks.append(d.decompress(b))
 chunks.append(d.flush());payload=b''.join(chunks);last=payload.rfind(b'\n');tail=payload[last+1:]
 trace_integrity[path.name]=dict(gzip_eof_marker_present=d.eof,decoded_bytes=len(payload),complete_newline_records=payload.count(b'\n'),trailing_incomplete_record_bytes=len(tail),original_unchanged=True,method='READ_ONLY_ZLIB_COMPLETE_NEWLINE_RECORDS_NO_RAW_REPAIR')
 return io.StringIO(payload[:last+1].decode())

months={};H=D(10000);settled_maxdd=D(0);n=0;previous=None;gaps=[];retained_receipts={}
with trace(Q/'minute-native-settled-receipts.csv.gz') as f:
 for r in csv.DictReader(f):
  n+=1;t=int(r['source_quote_ns']);e=D(r['paired_close_equity']);H=max(H,e);dd=1-e/H;settled_maxdd=max(settled_maxdd,dd)
  if previous is not None and t-previous!=60000000000:gaps.append((previous,t))
  previous=t;retained_receipts[t]=(int(r['receipt_ns']),D(r['cash']),e);m=utc(t)[:7]
  if m not in months:months[m]=dict(month=m,rows=0,first_source_UTC=utc(t),first_E=str(e),max_global_DD='0')
  x=months[m];x.update(rows=x['rows']+1,last_source_UTC=utc(t),last_E=str(e),last_cash=r['cash'],max_global_DD=str(max(D(x['max_global_DD']),dd)))
write('QUAL_VALIDATION_RAW-months.csv',list(months.values()))
# Native cash transitions: actual pre/post cash, never reconstructed fill PnL.
obs=q['coherent_native_observer'];seqs={int(v['timestamp_ns']) for e in obs['event_drawdown']['top3_distinct_excursions'] for v in e.values() if isinstance(v,dict) and 'timestamp_ns' in v};seqs.add(int(obs['event_drawdown']['minimum']['timestamp_ns']))
kinds=collections.Counter();joined={};pre={};postcounts=collections.Counter();pair_errors=[];fill_delta=D(0);fund_delta=D(0);cash_changes=[];lastcash=None;lastseq=0;pairrows=[];markH=D(10000);markDD=D(0);markcount=0;markprevious=None;markgaps=[];markprefixmatch=True;markprefixcount=0;markmonths={};eventH=D(10000);eventmax=D(0);eventsamples=1;boundary_seen=False;eventpeak=0;eventworst=None
with trace(Q/'coherent-native-events.jsonl.gz') as f:
 for line in f:
  x=json.loads(line);s=x['sequence'];kind=x['kind'];kinds[kind]+=1
  if kind=='SETTLED_PRE_NEXT_SOURCE_WATERMARK':
   mt=int(x['event_ns']);me=D(x['equity']);markH=max(markH,me);markDD=max(markDD,1-me/markH);markcount+=1
   if markprevious is not None and mt-markprevious!=60000000000:markgaps.append((markprevious,mt))
   markprevious=mt
   if mt in retained_receipts:markprefixcount+=1;markprefixmatch=markprefixmatch and retained_receipts[mt]==(int(x['receipt_ns']),D(x['cash']),me)
   mm=utc(mt)[:7]
   if mm not in markmonths:markmonths[mm]=dict(month=mm,rows=0,first_source_UTC=utc(mt),first_E=str(me),max_global_DD='0')
   mz=markmonths[mm];mz.update(rows=mz['rows']+1,last_source_UTC=utc(mt),last_E=str(me),last_cash=x['cash'],max_global_DD=str(max(D(mz['max_global_DD']),1-me/markH)))
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
db=sqlite3.connect('file:'+str(next(Q.glob('*funding.sqlite*')))+'?mode=ro',uri=True);sqlfund=db.execute('select event_id,instrument_id,ts_event,before_total,after_total,signed_delta from funding_cash order by ts_event,event_id').fetchall();sqlorig=db.execute('select event_id,instrument_id,ts_event,account_total_after from funding_events').fetchall()
fundmap={(x[0],x[1]):x for x in fundrows};sqlmap={(x[0],x[1]):list(x) for x in sqlfund};fundpostmap={x['native_id']:x for x in pairrows if x['kind']=='FUNDING'}
fundjoinok=all(x[0] in fundpostmap and D(fundpostmap[x[0]]['actual_cash_delta'])==D(x[5]) for x in fundrows)
recon_residual=D(q['terminal_total'])-D(10000)-fill_delta-fund_delta
cashrecon=dict(method='SUM_ACTUAL_NATIVE_PRE_POST_CASH_TRANSITIONS_BY_UNIQUE_FILL_OR_FUNDING_ID;NO_DERIVED_TRADE_PNL',seed='10000',actual_native_fill_cash_delta=str(fill_delta),actual_native_funding_cash_delta=str(fund_delta),terminal=str(q['terminal_total']),residual=str(recon_residual),native_fill_pairs=sum(1 for x in pairrows if x['kind']=='FILL'),native_funding_pairs=sum(1 for x in pairrows if x['kind']=='FUNDING'),unmatched_pre_count=len(pre),duplicate_post_ids=sum(v-1 for v in postcounts.values()),pair_errors=pair_errors,cash_change_count=len(cash_changes),cash_changes_outside_post_fill_or_funding=[x for x in cash_changes if x['kind'] not in ('POST_FILL_COMMITTED_NATIVE','POST_FUNDING_ACCOUNT_NATIVE')],fees='Nativecashdeltasalreadyincludefees;NOfee subtractionagain',original_JSON_reconciliation='R_ORIGINAL_COMPLETE_NATIVE_LIFECYCLES_PRESERVED',independent_native_position_lifecycle_PNL_reconciliation='INDEPENDENT_SUM_PENDING')
cashrecon['status']='PASS_NATIVE_CASH_TRANSITION_IDENTITY' if recon_residual==0 and not pair_errors and not pre and not cashrecon['duplicate_post_ids'] and not cashrecon['cash_changes_outside_post_fill_or_funding'] else 'UNKNOWN_UNCLOSED_NATIVE_TRANSITIONS'
write('QUAL_VALIDATION_RAW-native-cash-transitions.csv',pairrows)

positions=q['native_cash_reconciliation']['native_position_lifecycle_export']['positions'];keys=[tuple(x[k] for k in ('position_id','opened_ns','closed_ns','opening_order_id','native_fill_lifecycle_sha256')) for x in positions];pnlsum=sum((D(x['realized_pnl']) for x in positions),D(0));posbridge=D(q['terminal_total'])-D(10000)-pnlsum-fundsum
write('QUAL_VALIDATION_RAW-native-position-lifecycles.csv',positions)
ordersfile=next(Q.glob('*-orders.csv'));orders=list(csv.DictReader(open(ordersfile)));active=[x for x in orders if x['status'] not in ('FILLED','CANCELED','EXPIRED','REJECTED','DENIED')]
exfile=Q.parent/'execution.json';ex=json.load(open(exfile));src=J/'source-QUAL-HARNESS-299197a7140a/runtime/coinmaster/research/native_baseline.py';cfg=json.load(open(P/'config-QUAL-VALIDATION.json'));hashjson=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest();missing={k:v for k,v in cfg.items() if k not in q['config']};mismatch={k:[v,cfg.get(k)] for k,v in q['config'].items() if v!=cfg.get(k)}
rawconfigok=hashjson(q['config'])==q['config_hash'];reconstructed=hashjson({**q['config'],**missing});manifest=B/'runtime/var/research-jobs/e4-c1-qualification-data-20260901-20261028/inputs/data/bybit-1m/manifest.json'
checks=dict(raw_config_selfhash=rawconfigok,existing_config_keys_match_expected=not mismatch,config_metadata_reconstruction=reconstructed==ex['config_sha256']=='9c7e16e4bee8ab6c91dae5009b083b1509ffe6053d36c5c38af929964a78d1db',data_hash=hashjson(json.load(open(manifest)))==q['data_hash']=='1714540d189ce5dbc45489ea007f2fb16a5dafb9a451c13010ceee208639171b',source_code_hash=hashlib.sha256(src.read_bytes()).hexdigest()==q['code_hash'],execution_identity=hashlib.sha256(exfile.read_bytes()).hexdigest()=='61546762847d41b2e9eb26bef146b87827bb908c526fdfdaba35056f5a110392' and ex['actual_native_child_pid']==75889 and ex['actual_native_child_exit']==1 and ex['attempt_uuid']=='c441e4fe-8a0d-43f0-8a83-62de3e14f1cf',position_PnL=all(x['closed'] for x in positions) and len(keys)==len(set(keys)) and posbridge==0 and pnlsum==fill_delta,cash_reconciled=cashrecon['status']=='PASS_NATIVE_CASH_TRANSITION_IDENTITY',funding_reconciled=fundmap==sqlmap and fundjoinok and not badfund and fund_delta==fundsum,settled_event_watermarks_complete=not markgaps and markcount==82079 and len(markmonths)==2 and markprefixmatch and markprefixcount==n,settled_DD_exact=100*markDD==D(obs['settled_drawdown']['top3_distinct_excursions'][0]['drawdown_peak_percent']),event_DD_exact=100*eventmax==D(obs['event_drawdown']['top3_distinct_excursions'][0]['drawdown_peak_percent']),event_samples_match=eventsamples==obs['event_drawdown']['samples'],risk_cap=100*max(settled_maxdd,eventmax)<=D('51.80315157406654834417870238'),terminal_flat=q['terminal_open_positions']==0 and q['terminal_lifecycle']['status']=='FLAT' and q['terminal_lifecycle']['lockout'],terminal_orders_closed=not active and len({x['client_order_id'] for x in orders})==len(orders),zero_liquidations=q['liquidation_count']==0,observer_known=obs['status']=='PASS' and not obs['unknown'])
lines=src.read_text().splitlines();out=dict(status='PROCESS_FAILED_FINANCIAL_EVIDENCE_INDEPENDENTLY_RECONCILED' if all(checks.values()) else 'PROCESS_FAILED_FINANCIAL_EVIDENCE_INCOMPLETE',normal_qualification_PASS=False,process_status=ex['status'],actual_exit=ex['actual_native_child_exit'],TOTAL=q['terminal_total'],net_profit=str(D(q['terminal_total'])-D(10000)),return_percent=str((D(q['terminal_total'])/D(10000)-1)*100),raw_sha256=hashlib.sha256(qfile.read_bytes()).hexdigest(),raw_audit_state=q['raw_audit_state'],raw_report_status=q['status'],run_interval=q['run_interval'],warmup=q['warmup'],data_hash=q['data_hash'],raw_config_hash=q['config_hash'],intended_final_config_hash=ex['config_sha256'],raw_config_missing_final_metadata=missing,existing_config_mismatches=mismatch,reconstructed_metadata_hash=reconstructed,config_explanation='Raw snapshot saved at source1208 before split/cover metadata additions1213-1243; raw preserved unchanged. Reconstruction is analysis-only, not a normal exported report.',source_code_hash=q['code_hash'],source_commit=ex['source_commit'],retained_settled_csv_rows=n,settled_event_watermark_rows=markcount,retained_csv_matches_event_watermark_prefix=markprefixmatch,retained_prefix_rows_compared=markprefixcount,months=list(markmonths),event_sequence_count=lastseq,event_DD_samples=eventsamples,truncated_settled_csv_DD_percent=str(100*settled_maxdd),settled_DD_percent=str(100*markDD),settled_DD_basis='COMPLETE_IMMUTABLE_SETTLED_PRE_NEXT_SOURCE_WATERMARK_ROWS_IN_COMPLETE_NATIVE_EVENT_TRACE',event_DD_percent=str(100*eventmax),event_worst=eventworst,event_endpoint_sequence_join=joined,native_cash_transition_reconciliation=cashrecon,native_position_lifecycle=dict(count=len(positions),unique_closed=len(set(keys)),realized_pnl=str(pnlsum),actual_funding=str(fundsum),terminal_bridge=str(posbridge),fees_already_in_native_pnl=True),funding=dict(rows=len(fundrows),signed_sum=str(fundsum),JSON_matches_SQLite=fundmap==sqlmap,event_pair_match=fundjoinok,bad_arithmetic_rows=badfund),terminal=q['terminal_lifecycle'],orders=dict(count=len(orders),status_counts=dict(collections.Counter(x['status'] for x in orders)),active=len(active)),fills=q['fills'],native_fees=q['native_fees'],liquidations=q['liquidation_count'],native_cash_monthly_returns=q['summary']['monthly_returns'],checks=checks,boundary_failure=dict(source_lines_324_327=lines[323:327],actual_months=2,computed_expected_months=1,explanation='Month-count formula excludes partial final October: Sep1 to Oct28 yields1, but actual Sep and Oct rows are correct2. Not a hardcoded24 assertion.',process_gate='FAIL; no waiver'),limits=['Failed standard export/receipt preserved; no normal PASS report created','No engine/tests/source changes/retry','No matched benchmark comparison or absolute 2-year profit-floor decision for 57-day interval','No fresh untouched OOS or live readiness claim'])
write('QUAL_VALIDATION_RAW-event-watermark-months.csv',list(markmonths.values()))
out['trace_integrity']=trace_integrity
out['settled_csv_availability']='TRUNCATED; complete retained rows exactly match full immutable event watermark prefix; full event watermarks used for independent settled DD, not a regenerated standard report'
out['trace_footer_status']='INCOMPLETE_GZIP_FOOTER_PRESERVED' if any(not x['gzip_eof_marker_present'] for x in trace_integrity.values()) else 'COMPLETE'
(O/'QUAL_VALIDATION_RAW-analysis.json').write_text(json.dumps(out,indent=2))
inputs=[qfile,exfile,src,manifest,P/'config-QUAL-VALIDATION.json',ordersfile,next(Q.glob('*-fills.csv')),Q/'coherent-native-events.jsonl.gz',Q/'minute-native-settled-receipts.csv.gz',next(Q.glob('*funding.sqlite*')),O/'analyze_QUAL_VALIDATION_RAW_existing.py'];pins={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs};(O/'QUAL_VALIDATION_RAW-input-hashes.json').write_text(json.dumps(pins,indent=2))
print(json.dumps(dict(status=out['status'],TOTAL=out['TOTAL'],return_percent=out['return_percent'],bothDD=out['event_DD_percent'],checks=checks,position=out['native_position_lifecycle'],orders=out['orders'],raw_sha256=out['raw_sha256']),indent=2))
