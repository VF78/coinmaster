"""Report-only native artifact adapter. Never starts an engine or edits input artifacts.
Inherited lot-corridor financial reader; only completed immutable results are admissible.
All supplied paths are explicit; no polling, process launch or data download.
"""
import argparse,json,gzip,csv,sqlite3,hashlib,sys
from decimal import Decimal as D,getcontext
from pathlib import Path
from datetime import datetime,timezone,timedelta
getcontext().prec=50
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--label',required=True,choices=['R2_OFF','R2_C0','R2_A0'])
ap.add_argument('--report',required=True,type=Path)
ap.add_argument('--ledger',required=True,type=Path,help='Actual A0 physical prefix ledger with immutable report linkage')
ap.add_argument('--completion',required=True,type=Path,help='Completed-artifact path/sha256 manifest, including report and all consumed files')
ap.add_argument('--supervisor',required=True,type=Path)
ap.add_argument('--evidence',required=True,type=Path,help='Root acceptance evidence: gates and immutable receipt references; see metric-contract.json')
ap.add_argument('--output',required=True,type=Path)
args=ap.parse_args();variant=args.label;rp=args.report.resolve();p=rp.parent;stem=rp.stem
assert args.output.resolve().parent==Path(__file__).resolve().parent, 'OUTPUT_MUST_STAY_IN_ACCEPTANCE'
assert args.output.resolve()!=rp, 'INPUT_IS_IMMUTABLE'
a=json.loads(rp.read_text());o=a['coherent_native_observer']
completion=json.loads(args.completion.read_text())
artifact_checks={x['path']:hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()==x['sha256'] for x in completion['artifacts']}
required={str(x.resolve()) for x in [rp,p/f'{stem}-orders.csv',p/f'{stem}-funding.sqlite',p/'coherent-native-events.jsonl.gz']}
assert required <= {str(Path(x).resolve()) for x in artifact_checks}, 'INCOMPLETE_ARTIFACT_MANIFEST'
assert all(artifact_checks.values()), 'COMPLETION_ARTIFACT_HASH_MISMATCH'
supervisor=json.loads(args.supervisor.read_text())
assert supervisor['actual_returncode']==0 and supervisor['ledger_status']=='COMPLETED'
ledger=json.loads(args.ledger.read_text())
report_digest=hashlib.sha256(rp.read_bytes()).hexdigest()
linked=[]
for candidate in ledger['attempts']:
 detail=candidate.get('detail',{})
 if candidate.get('attempt_id')==a['physical_prefix_attempt']['attempt_id'] and candidate.get('status')=='COMPLETED' and detail.get('report_sha256')==report_digest:
  linked.append(candidate)
assert len(linked)==1, 'UNIQUE_PHYSICAL_LEDGER_REPORT_BINDING_REQUIRED'
entry=linked[0]
assert entry['status']=='COMPLETED', 'LEDGER_ATTEMPT_NOT_COMPLETED'
if a.get('physical_prefix_attempt'):
 assert entry['attempt_id']==a['physical_prefix_attempt']['attempt_id'], 'REPORT_ATTEMPT_MISMATCH'
assert entry['variant']==variant, 'LEDGER_VARIANT_MISMATCH'
assert len(completion['artifacts'])==4 and {x['role'] for x in completion['artifacts']}=={'report','orders','funding','coherent'}, 'EXACT_FOUR_ARTIFACT_ROLES_REQUIRED'
expected_paths={'report':rp,'orders':p/f'{stem}-orders.csv','funding':p/f'{stem}-funding.sqlite','coherent':p/'coherent-native-events.jsonl.gz'}
assert all(Path(x['path']).resolve()==expected_paths[x['role']] for x in completion['artifacts']), 'ARTIFACT_ROLE_PATH_MISMATCH'
assert rp.name==variant+'.json' and p.name=='result' and p.parent.name==variant, 'FROZEN_RESULT_LAYOUT_REQUIRED'
assert completion['status']=='NATIVE_PROCESS_EXPORTED_ACTUAL_OS_ZERO' and completion['actual_returncode']==0, 'ACTUAL_OS_ZERO_COMPLETION_REQUIRED'
assert entry['detail']['actual_returncode']==0, 'LEDGER_ACTUAL_OS_ZERO_REQUIRED'
assert a['physical_prefix_attempt']['variant']==variant and Path(a['physical_prefix_attempt']['ledger']).resolve()==args.ledger.resolve(), 'REPORT_LEDGER_IDENTITY_MISMATCH'
assert all(x['attempt_id']==entry['attempt_id'] and x['variant']==variant for x in [supervisor,completion]), 'RECEIPT_ATTEMPT_IDENTITY_MISMATCH'
source='763d985617abd7a7afef5eec13912303983d8837'
assert all(x['source_commit']==source for x in [entry,supervisor,completion,a['physical_prefix_attempt']]), 'SAME_FROZEN_SOURCE_REQUIRED'
assert entry['freeze_sha256']==supervisor['freeze_sha256']==completion['freeze_sha256'], 'FREEZE_BINDING_MISMATCH'
assert Path(entry['namespace']).resolve()==p.parent, 'LEDGER_NAMESPACE_MISMATCH'
assert Path(entry['detail']['report']).resolve()==rp, 'LEDGER_REPORT_PATH_MISMATCH'
completion_digest=hashlib.sha256(args.completion.read_bytes()).hexdigest()
assert all(x['completion_manifest_sha256']==completion_digest and Path(x['completion_manifest']).resolve()==args.completion.resolve() for x in [entry['detail'],supervisor]), 'COMPLETION_RECEIPT_LEDGER_HASH_BINDING_MISMATCH'
orders=list(csv.DictReader((p/f'{stem}-orders.csv').open()))
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
con=sqlite3.connect('file:'+str((p/f'{stem}-funding.sqlite').resolve())+'?mode=ro&immutable=1',uri=True)
frows=con.execute('select event_id,instrument_id,ts_event,before_total,after_total,signed_delta from funding_cash').fetchall()
fdb={x[0]:x for x in frows};fproof=all(before==fdb[e][3] and after==fdb[e][4] and D(after)-D(before)==D(fdb[e][5]) for e,before,after in funding) and len(funding)==len(frows)==a['funding']['count']
fees=sum((D(x['commission']) for x in a['fill_audit']),D(0));signed=sum((D(x[5]) for x in frows),D(0))
out={'variant':variant,'report_sha256':hashlib.sha256(rp.read_bytes()).hexdigest(),'terminal_total':a['terminal_total'],'prefix_only':True,'observer_status':o['status'],'observer_unknown':o['unknown'],'stream_rows':n,'stream_checks':sorted(set(bad)),'settled_source_gaps':settled_source_gaps,'settled_receipts':kinds.get('SETTLED_PRE_NEXT_SOURCE_WATERMARK',0),'settled_DD_percent':o['settled_drawdown']['top3_distinct_excursions'][0]['drawdown_peak_percent'],'event_DD_percent':o['event_drawdown']['top3_distinct_excursions'][0]['drawdown_peak_percent'],'native_fills':a['fills'],'fees':str(fees),'fee_match':fees==D(a['native_fees']),'signed_funding':str(signed),'funding_db_actual_observer_match':fproof,'funding_report_match':signed==D(a['funding']['signed_amount']),'terminal_flat_orders0':a['terminal_open_positions']==0 and all(x['status'] in terminal for x in orders) and bool(terminalrow) and not terminalrow['positions'],'liquidations':a['liquidation_count'],'daily_count':len(dreturns),'daily_missing':missing,'daily_ES20':es([D(x['loss']) for x in dreturns]) if not missing else 'UNKNOWN','parent_count':len(cycles),'parent_proven_count':len(pl),'parent_ES20':es(pl) if len(pl)==len(cycles) else 'UNKNOWN','daily':dreturns,'parents':cycles,'limits':'Actual prefix native observer endpoints only; no intraminute price path guarantee. Parent endpoint chosen earliest actual flat snapshot after all associated native orders terminal, before next actual parent fill.'}
out.update(mutation_snapshots=mutation_snapshots,fill_snapshot_pair_proof=prefill_ids==postfill_ids and len(prefill_ids)==a['fills'],engine_instances_created=0, artifact_checks=artifact_checks,actual_returncode=supervisor['actual_returncode'],ledger_report_hash_match=True,first_settled_ns=first_settled_ns,last_settled_ns=last_settled_ns,last_epoch=last_epoch,settled_receipt_lags_ns=lag_counts,computed_DD_percent={k:str(v) for k,v in dds.items()},funding_by_asset={asset:str(sum((D(x[5]) for x in frows if x[1]==asset),D(0))) for asset in sorted({x[1] for x in frows})},native_fee_classification={side:{'fills':sum(x['native_liquidity_side']==side for x in a['fill_audit']),'fees':str(sum((D(x['commission']) for x in a['fill_audit'] if x['native_liquidity_side']==side),D(0)))} for side in sorted({x['native_liquidity_side'] for x in a['fill_audit']})},paired_event_counts={event:sum(x['event']==event for x in a['paired_prefix_audit']['events']) for event in sorted({x['event'] for x in a['paired_prefix_audit']['events']})},paired_failures=a['paired_prefix_audit']['failures'])

# Extra contract evidence is never inferred from a numeric TOTAL.
evidence=json.loads(args.evidence.read_text())
assert evidence['label']==variant and evidence['report_sha256']==out['report_sha256'], 'EVIDENCE_REPORT_MISMATCH'
proofs=evidence.get('proof_artifacts',[])
assert proofs and all(hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()==x['sha256'] for x in proofs), 'EVIDENCE_PROOF_HASH_MISMATCH'
required_gates=['complete_cash_reconciliation','signed_asset_funding_reconciliation','native_3TP','ownership','continuous_settled_coverage','coherent_prefill_preopen_event_coverage','source_config_data_comparable','rights_audit_complete']
gates={k:evidence.get('gates',{}).get(k,'UNKNOWN') for k in required_gates}
checks={
 'exit_complete':supervisor['actual_returncode']==0 and supervisor['ledger_status']=='COMPLETED',
 'native_observer':o['status']=='PASS' and not o['unknown'],
 'stream_integrity':not bad and settled_source_gaps==0,
 'cash_upnl_native_bridge':not any(x=='cash_upnl_bridge' for x in bad),
 'fees_match':out['fee_match'], 'signed_funding':fproof and out['funding_report_match'],
 'terminal_flat_orders0':out['terminal_flat_orders0'] and evidence.get('terminal_open_orders')==0,
 'zero_liquidations':out['liquidations']==0,
 'all_136_daily_endpoints':len(dreturns)==136 and not missing,
 'native_fill_pairs':out['fill_snapshot_pair_proof'],
}
# ES20 remains a fractional return; comparison/output percentages must multiply by 100.
out['daily_ES20_percent']=str(D(out['daily_ES20'])*100) if out['daily_ES20']!='UNKNOWN' else 'UNKNOWN'
out['parent_ES20_percent']=str(D(out['parent_ES20'])*100) if out['parent_ES20'] not in (None,'UNKNOWN') else 'UNKNOWN'
out['contract_gates']=gates;out['accounting_checks']=checks
out['accounting_qualified']=all(checks.values()) and all(v=='PASS' for v in gates.values())
out['qualification']='VALID_ACCOUNTED_PREFIX' if out['accounting_qualified'] else 'UNKNOWN_OR_FAILED_BLOCKS_ACCEPTANCE'
import importlib.util
_rights_spec=importlib.util.spec_from_file_location('a0_rights_proof',Path(__file__).parent/'rights-proof.py')
_rights_module=importlib.util.module_from_spec(_rights_spec);_rights_spec.loader.exec_module(_rights_module)
raw_rights=a.get('market_redesign_audit',{}).get('a0_release_audit')
if isinstance(raw_rights,dict):
 normalized=dict(raw_rights)
 normalized['status']='PASS' if gates.get('rights_audit_complete')=='PASS' else 'UNKNOWN'
 for key in ['grants','submits','accepted','denials']:
  if isinstance(normalized.get(key),list):normalized[key]=len(normalized[key])
 if isinstance(normalized.get('native_release_fills'),list):
  normalized['native_release_fills']=[dict(f,instrument_id=f.get('instrument_id',f.get('BTCinstrument_id'))) for f in normalized['native_release_fills']]
 out['rights']=_rights_module.rights_proof(normalized)
 out['rights']['source_json_path']='$.market_redesign_audit.a0_release_audit'
else:
 out['rights']={'status':'UNKNOWN','reason':'Missing frozen producer a0_release_audit'}
if out['rights']['status']!='PASS':
 out['accounting_qualified']=False
 out['qualification']='UNKNOWN_OR_FAILED_BLOCKS_ACCEPTANCE'
out['metric_contract_sha256']=hashlib.sha256((Path(__file__).parent/'metric-contract.json').read_bytes()).hexdigest()
out['physical_binding']={
 'attempt_id':entry['attempt_id'],'label':variant,'source_commit':source,'report_path':str(rp),'report_sha256':report_digest,
 'native_ledger_path':str(args.ledger.resolve()),'native_ledger_sha256_at_analysis':hashlib.sha256(args.ledger.read_bytes()).hexdigest(),
 'completed_attempt_sha256':hashlib.sha256(json.dumps(entry,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest(),
 'completion_manifest_path':str(args.completion.resolve()),'completion_manifest_sha256':completion_digest,
 'supervisor_path':str(args.supervisor.resolve()),'supervisor_sha256':hashlib.sha256(args.supervisor.read_bytes()).hexdigest()}
out['prelaunch_binding_sha256']=hashlib.sha256((Path(__file__).parent/'prelaunch-binding.json').read_bytes()).hexdigest()
out['evidence_sha256']=hashlib.sha256(args.evidence.read_bytes()).hexdigest()
out['reader_reused_from_sha256']='a357f9a4b22ccb221610166d23aaa6e01c0770f801e04e1335e25bc3b4cc78a1'
out['engine_instances_created']=0
args.output.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ['variant','qualification','terminal_total','actual_returncode','settled_DD_percent','event_DD_percent','daily_count','daily_ES20_percent','parent_count','parent_proven_count','parent_ES20_percent','engine_instances_created']},indent=2))
