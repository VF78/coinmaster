import json,gzip,csv,sqlite3,hashlib,sys
from decimal import Decimal as D,getcontext
from pathlib import Path
from datetime import datetime,timezone,timedelta
getcontext().prec=50
base=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/paired-lot-corridor-20261025')
reportbase=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021/reports/broad-hedge-discovery-20261024')
variant=sys.argv[1]; name={'OFF':'MATCHED_OFF_PHYSICAL5','B2':'B2_PHYSICAL6','B2_F0':'B2_F0_PHYSICAL7'}[variant]
name=sys.argv[2] if len(sys.argv)>2 else name
p=base/name/'result';rp=p/f'paired-prefix-{variant}.json'; a=json.loads(rp.read_text()); o=a['coherent_native_observer']
completion=json.loads((reportbase/f'lot-corridor-{variant}-completion.json').read_text())
artifact_checks={x['path']:hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()==x['sha256'] for x in completion['artifacts']}
assert all(artifact_checks.values()), 'COMPLETION_ARTIFACT_HASH_MISMATCH'
supervisor=json.loads((base/name/'supervisor-receipt.json').read_text())
assert supervisor['actual_returncode']==0 and supervisor['ledger_status']=='COMPLETED'
ledger=json.loads(Path(a['physical_prefix_attempt']['ledger']).read_text())
entry=next(x for x in ledger['attempts'] if x['attempt_id']==a['physical_prefix_attempt']['attempt_id'])
assert entry['status']=='COMPLETED' and entry['detail']['report_sha256']==hashlib.sha256(rp.read_bytes()).hexdigest()
orders=list(csv.DictReader((p/f'paired-prefix-{variant}-orders.csv').open()))
terminal={'FILLED','CANCELED','EXPIRED','REJECTED','DENIED'}
parents=sorted(a['split_cover_audit']['parents'],key=lambda x:int(x['start_ns']))
cycles=[]
for i,v in enumerate(parents):
 st=int(v['start_ns']); nxt=int(parents[i+1]['start_ns']) if i+1<len(parents) else 10**30
 oo=[x for x in orders if st<=int(x['ts_init'])<nxt]
 cutoff=max([int(x['ts_last']) for x in oo]+[st])
 cycles.append(dict(episode_id=v['episode_id'],start_ns=st,next_start_ns=nxt,closed=v['closed'],orders_terminal=all(x['status'] in terminal for x in oo),order_quiescence_ns=cutoff,start=None,end=None))
daily={}; n=0; funding=[]; premutations={}; terminalrow=None; bad=[]; prevseq=0; kinds={}; last_settled_ns=None; settled_source_gaps=0
first_settled_ns=None; last_epoch=0; lag_counts={}; prefill_ids=set(); postfill_ids=set(); mutation_snapshots=[]; peaks={'settled':D(10000),'event':D(10000)}; dds={'settled':D(0),'event':D(0)}
for line in gzip.open(p/'coherent-native-events.jsonl.gz','rt'):
 r=json.loads(line); n+=1; k=r['kind']; kinds[k]=kinds.get(k,0)+1;ns=int(r['event_ns']);eq=r['equity'];pos=r['positions']
 if r['sequence']!=prevseq+1:bad.append('sequence_gap')
 prevseq=r['sequence']
 if r['epoch']<last_epoch or r['epoch']>last_epoch+1:bad.append('epoch_gap')
 last_epoch=r['epoch']
 if k=='PRE_FILL_LAST_COMMITTED_NATIVE_COPY':prefill_ids.add(r['native_id'])
 if k=='POST_FILL_COMMITTED_NATIVE':postfill_ids.add(r['native_id'])
 if k in {'PRE_FILL_LAST_COMMITTED_NATIVE_COPY','POST_FILL_COMMITTED_NATIVE'}:mutation_snapshots.append({key:r[key] for key in ['sequence','event_ns','native_id','kind','positions','cash','equity']})
 if eq is not None:
  bucket='settled' if k=='SETTLED_PRE_NEXT_SOURCE_WATERMARK' else 'event'; value=D(eq); peaks[bucket]=max(peaks[bucket],value); dds[bucket]=max(dds[bucket],(1-value/peaks[bucket])*100)
 if eq is None:bad.append('missing_equity')
 elif D(eq)!=D(r['cash'])+sum((D(x['native_upnl']) for x in pos),D(0)):bad.append('cash_upnl_bridge')
 if k=='SETTLED_PRE_NEXT_SOURCE_WATERMARK':
  if last_settled_ns is not None and ns-last_settled_ns!=60000000000:settled_source_gaps+=1
  last_settled_ns=ns
  if first_settled_ns is None:first_settled_ns=ns
  lag=int(r['receipt_ns'])-ns;lag_counts[str(lag)]=lag_counts.get(str(lag),0)+1
  retention=r.get('prior_source_retention')
  if retention and (int(retention['source_ns'])!=ns or retention['state_epoch']!=r['state_epoch'] or int(retention['first_new_mutation_ns'])<=ns):bad.append('retention_proof')
  day=datetime.fromtimestamp(ns//10**9,timezone.utc).date().isoformat()
  if '2024-09-01'<=day<='2025-01-14':
   if day not in daily or ns>daily[day]['source_ns']:daily[day]={'source_ns':ns,'equity':eq,'sequence':r['sequence']}
 if k=='DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED':terminalrow=r
 if k=='PRE_FUNDING_COMMITTED_NATIVE_COPY':premutations[r['native_id']]=r['cash']
 if k=='POST_FUNDING_ACCOUNT_NATIVE':funding.append((r['native_id'],premutations.get(r['native_id']),r['cash']))
 for c in cycles:
  if k=='PRE_FILL_LAST_COMMITTED_NATIVE_COPY' and ns==c['start_ns'] and c['start'] is None and not any('BTC' in x['instrument_id'] for x in pos):c['start']={'equity':eq,'sequence':r['sequence'],'event_ns':ns}
  if c['start'] and c['end'] is None and c['orders_terminal'] and c['closed'] and ns>=c['order_quiescence_ns'] and ns<=c['next_start_ns'] and not pos and r['sequence']>c['start']['sequence']:c['end']={'equity':eq,'sequence':r['sequence'],'event_ns':ns}
# Last-day fallback is solely actual terminal state; do not fill earlier gaps.
endday='2025-01-14';target=int(datetime(2025,1,14,23,59,tzinfo=timezone.utc).timestamp()*10**9)
if endday not in daily or daily[endday]['source_ns']<target:
 if terminalrow and not terminalrow['positions'] and all(x['status'] in terminal for x in orders) and a['terminal_open_positions']==0 and o['status']=='PASS' and D(terminalrow['cash'])==D(a['terminal_total']):daily[endday]={'source_ns':None,'equity':terminalrow['cash'],'sequence':terminalrow['sequence'],'basis':'VALIDATED_DIRECT_TERMINAL_NATIVE_CASH_FLAT_ORDERS0'}

def es(losses):
 if not losses:return None
 s=sorted(losses,reverse=True);q=D(len(s))/5;k=int(q);f=q-k
 return str((sum(s[:k],D(0))+(f*s[k] if f else D(0)))/q)
seed=D(10000);dreturns=[];missing=[]
for i in range(136):
 day=(datetime(2024,9,1)+timedelta(days=i)).date().isoformat()
 if day not in daily:missing.append(day);continue
 if seed<=0:missing.append(day+':nonpositive_start');continue
 v=D(daily[day]['equity']);loss=1-v/seed;dreturns.append(dict(date=day,start=str(seed),end=str(v),loss=str(loss),**daily[day]));seed=v
pl=[]
for c in cycles:
 if c['start'] and c['end'] and D(c['start']['equity'])>0:c['loss']=str(1-D(c['end']['equity'])/D(c['start']['equity']));pl.append(D(c['loss']))
con=sqlite3.connect('file:'+str((p/f'paired-prefix-{variant}-funding.sqlite').resolve())+'?mode=ro&immutable=1',uri=True)
frows=con.execute('select event_id,instrument_id,ts_event,before_total,after_total,signed_delta from funding_cash').fetchall()
fdb={x[0]:x for x in frows};fproof=all(before==fdb[e][3] and after==fdb[e][4] and D(after)-D(before)==D(fdb[e][5]) for e,before,after in funding) and len(funding)==len(frows)==a['funding']['count']
fees=sum((D(x['commission']) for x in a['fill_audit']),D(0));signed=sum((D(x[5]) for x in frows),D(0))
out={'variant':variant,'report_sha256':hashlib.sha256(rp.read_bytes()).hexdigest(),'terminal_total':a['terminal_total'],'prefix_only':True,'observer_status':o['status'],'observer_unknown':o['unknown'],'stream_rows':n,'stream_checks':sorted(set(bad)),'settled_source_gaps':settled_source_gaps,'settled_receipts':kinds.get('SETTLED_PRE_NEXT_SOURCE_WATERMARK',0),'settled_DD_percent':o['settled_drawdown']['top3_distinct_excursions'][0]['drawdown_peak_percent'],'event_DD_percent':o['event_drawdown']['top3_distinct_excursions'][0]['drawdown_peak_percent'],'native_fills':a['fills'],'fees':str(fees),'fee_match':fees==D(a['native_fees']),'signed_funding':str(signed),'funding_db_actual_observer_match':fproof,'funding_report_match':signed==D(a['funding']['signed_amount']),'terminal_flat_orders0':a['terminal_open_positions']==0 and all(x['status'] in terminal for x in orders) and bool(terminalrow) and not terminalrow['positions'],'liquidations':a['liquidation_count'],'daily_count':len(dreturns),'daily_missing':missing,'daily_ES20':es([D(x['loss']) for x in dreturns]) if not missing else 'UNKNOWN','parent_count':len(cycles),'parent_proven_count':len(pl),'parent_ES20':es(pl) if len(pl)==len(cycles) else 'UNKNOWN','daily':dreturns,'parents':cycles,'limits':'Actual prefix native observer endpoints only; no intraminute price path guarantee. Parent endpoint chosen earliest actual flat snapshot after all associated native orders terminal, before next actual parent fill.'}
out.update(mutation_snapshots=mutation_snapshots,fill_snapshot_pair_proof=prefill_ids==postfill_ids and len(prefill_ids)==a['fills'],engine_instances_created=0, artifact_checks=artifact_checks,actual_returncode=supervisor['actual_returncode'],ledger_report_hash_match=True,first_settled_ns=first_settled_ns,last_settled_ns=last_settled_ns,last_epoch=last_epoch,settled_receipt_lags_ns=lag_counts,computed_DD_percent={k:str(v) for k,v in dds.items()},funding_by_asset={asset:str(sum((D(x[5]) for x in frows if x[1]==asset),D(0))) for asset in sorted({x[1] for x in frows})},native_fee_classification={side:{'fills':sum(x['native_liquidity_side']==side for x in a['fill_audit']),'fees':str(sum((D(x['commission']) for x in a['fill_audit'] if x['native_liquidity_side']==side),D(0)))} for side in sorted({x['native_liquidity_side'] for x in a['fill_audit']})},paired_event_counts={event:sum(x['event']==event for x in a['paired_prefix_audit']['events']) for event in sorted({x['event'] for x in a['paired_prefix_audit']['events']})},paired_failures=a['paired_prefix_audit']['failures'])
(reportbase/f'lot-corridor-risk-{variant}.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ['daily','parents','mutation_snapshots']},indent=2))
