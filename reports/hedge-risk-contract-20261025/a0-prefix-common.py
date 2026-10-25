"""A0 prefix authorization/artifact plumbing only; native source owns all money."""
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime,timezone
import json,hashlib,os,fcntl,tempfile,uuid
SOURCE='763d985617abd7a7afef5eec13912303983d8837'
PROTOCOL='5c5e2b41555ee4e5c1970c5c5dadd173cd10599e00158224b706cb0083f477a0'
ORDER=('R2_OFF','R2_C0','R2_A0')
JOB=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/hedge-rights-unlock-20261025')
def utc():return datetime.now(timezone.utc).isoformat()
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()
def write(path,value):
    path=Path(path)
    with tempfile.NamedTemporaryFile('w',dir=path.parent,prefix='.a0-write-',delete=False) as f:
        json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno());tmp=f.name
    os.replace(tmp,path)
@contextmanager
def transaction(path):
    path=Path(path)
    with path.with_suffix(path.suffix+'.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);data=json.loads(path.read_text());yield data;write(path,data)
FAILED_INITIAL_PARENT_SHA='699020d51179394b2684f161a4216bfd2c6cccce69d89d019d180f849df5cf0e'
def namespace_root(g):
    if g.get('physical_prefix_max')==3 and g.get('prefix_phase','INITIAL')=='INITIAL':return JOB
    if g.get('physical_prefix_max')==4 and g.get('prefix_phase')=='AMEND4' and g.get('phase_namespace_root')==str(JOB/'prefix-amend4'):return JOB/'prefix-amend4'
    raise ValueError('EXACT_PREFIX_PHASE_NAMESPACE_REQUIRED')
def phase_entries(g,ledger):
    if g.get('physical_prefix_max')==3:return ledger['attempts']
    ref=g.get('parent_prefix_ledger',{})
    if ref.get('sha256')!=FAILED_INITIAL_PARENT_SHA or not ref.get('path') or sha(ref['path'])!=FAILED_INITIAL_PARENT_SHA:raise ValueError('IMMUTABLE_FAILED_INITIAL_PREFIX_PARENT_REQUIRED')
    parent=json.loads(Path(ref['path']).read_text())
    if parent.get('physical_max')!=3 or parent.get('physical_started')!=1 or len(parent.get('attempts',[]))!=1 or parent['attempts'][0]['status']!='FAILED':raise ValueError('EXACT_ONE_FAILED_INITIAL_PARENT_REQUIRED')
    if ledger.get('physical_max')!=4 or ledger.get('parent_prefix_ledger_sha256')!=FAILED_INITIAL_PARENT_SHA or ledger['attempts'][:1]!=parent['attempts'] or ledger.get('physical_started')!=len(ledger['attempts']):raise ValueError('AMENDED_PREFIX_MUST_PRESERVE_FAILED_PARENT_ROW')
    rest=ledger['attempts'][1:]
    if any(e.get('prefix_phase')!='AMEND4' for e in rest):raise ValueError('MIXED_PREFIX_PHASE_HISTORY')
    return rest
def require_phase_approval(g):
    if g.get('physical_prefix_max')==3:return
    q=pinned_json(g.get('prefix_budget_amendment',{}))
    required=dict(status='APPROVED_BY_OWNER',source_commit=SOURCE,protocol_sha256=PROTOCOL,parent_prefix_ledger_sha256=FAILED_INITIAL_PARENT_SHA,authorized_prefix_total=4,additional_prefix_attempts=1,prefix_phase='AMEND4',new_phase_variants=list(ORDER),full=0,training=0,downloads=0)
    reply=q.get('exact_owner_reply')
    if any(type(q.get(k)) is not type(v) or q[k]!=v for k,v in required.items()) or type(reply) is not str or not reply.strip():raise ValueError('EXACT_DIRECT_OWNER_PREFIX_AMENDMENT_REQUIRED')
def verify_scope(g,variant,namespace,require_go=False):
    if g.get('source_commit')!=SOURCE or g.get('protocol_sha256')!=PROTOCOL or g.get('variant')!=variant or variant not in ORDER:
        raise ValueError('EXACT_A0_PREFIX_SOURCE_SCOPE_REQUIRED')
    if Path(namespace).resolve()!=namespace_root(g)/variant or g.get('physical_prefix_max') not in (3,4) or g.get('full')!=0 or g.get('training')!=0 or g.get('downloads')!=0:
        raise ValueError('EXACT_PREFIX_NAMESPACE_BUDGET_REQUIRED')
    if g.get('calendar')!='[2024-09-01T00:00:00Z,2025-01-15T00:00:00Z)' or g.get('seed')!='10000' or g.get('reserve')!='0':
        raise ValueError('EXACT_PREFIX_WINDOW_SEED_REQUIRED')
    if require_go:
        require_phase_approval(g)
        if g.get('root_go') is not True or g.get('independent_review')!='PASS' or g.get('engineering_acceptance')!='LIMITED_PASS' or g.get('launch_gates')!='PASS':
            raise ValueError('SEPARATE_EXACT_VARIANT_ROOT_GO_REQUIRED')
        for key in ('root_go_receipt','engineering_acceptance_receipt'):
            ref=g.get(key,{})
            if not ref.get('path') or not ref.get('sha256') or sha(ref['path'])!=ref['sha256']:raise ValueError('ROOT_RECEIPT_PIN_REQUIRED:'+key)
def verify_freeze(g,variant,namespace):
    verify_scope(g,variant,namespace)
    source=Path(g['source_root']);assert (source/'.source-commit').read_text().strip()==SOURCE
    for pin in g['source_files']:
        if sha(source/pin['path'])!=pin['sha256']:raise ValueError('SOURCE_PIN_MISMATCH:'+pin['path'])
    for pin in g['input_files']:
        if sha(pin['path'])!=pin['sha256']:raise ValueError('INPUT_PIN_MISMATCH:'+Path(pin['path']).name)
    if sha(g['feed_path'])!=g['new_feed_sha256']:raise ValueError('FEED_PIN_MISMATCH')
    for pin in g['script_pins']:
        if sha(pin['path'])!=pin['sha256']:raise ValueError('PREFIX_SCRIPT_PIN_MISMATCH')
    if sha(g['kwargs_payload']['path'])!=g['kwargs_payload']['sha256']:raise ValueError('KWARGS_PAYLOAD_PIN_MISMATCH')
    pinned_json(g['financial_qualification_schema'])
def stock_input_preflight(g,kwargs):
    # Invoke the actual stock consumer helpers, with no run_native_diagnostic
    # call, engine, journal, strategy/account, matching or PnL calculation.
    from coinmaster.research.native_baseline import coverage_blockers,_load_daily_seed,funding_with_prior_minute_marks,iter_minute_bundles,run_native_diagnostic
    from inspect import signature
    b=signature(run_native_diagnostic).bind(**kwargs);b.apply_defaults();a=b.arguments;root=Path(a['data_root']);start=a['trading_start_ms'];end=a['trading_end_ms']
    blockers=coverage_blockers(root)
    if blockers:raise ValueError('ACTUAL_STOCK_INPUT_BLOCKERS:'+','.join(blockers))
    consumed=[root/'bybit-1m/manifest.json']+[root/'normalized'/('bybit-'+asset+'-'+kind+'.parquet') for asset in ('BTCUSDT','SOLUSDT') for kind in ('daily','execution-1m','mark-1m','funding')]
    pins={Path(x['path']).resolve() for x in g['input_files']}
    if any(path.resolve() not in pins for path in consumed):raise ValueError('ACTUAL_NATIVE_INPUT_ROOT_NOT_BOUND_TO_PINNED_FILES')
    seed,daily=_load_daily_seed(root,a['warmup_start_ms'],start,end)
    events=funding_with_prior_minute_marks(root,start,end) if a['include_funding'] else ()
    count=0;first=last=None
    for bundle in iter_minute_bundles(root,start,end):
        count+=1;last=bundle.open_time_ms
        if first is None:first=last
    return dict(status='PASS_ACTUAL_STOCK_READERS_ENGINE_FREE',data_root=str(root),coverage_blockers=blockers,consumed_files_pinned=len(consumed),daily_seed_rows=len(seed),daily_rows={key:len(rows) for key,rows in daily.items()},feature_seed_last_available=str(seed[-1].available_at),funding_events=len(events),funding_by_asset={str(i):sum(e.instrument_id==i for e in events) for i in {e.instrument_id for e in events}},funding_prior_marks_basis=sorted({e.basis for e in events}),minute_bundles=count,first_minute_ms=first,last_minute_ms=last,engines_created=0)
def prepared_kwargs(g,variant,result):
    from coinmaster.research.a0_family import build_a0_kwargs,validate_native_a0,START_MS,END_MS
    from coinmaster.research.paired_signal_feed import load_paired_signal_feed
    from coinmaster.research.registered_control import native_kwargs_json_roundtrip
    from coinmaster.research.native_baseline import run_native_diagnostic
    from inspect import signature
    feed=load_paired_signal_feed(Path(g['feed_path']),g['new_feed_sha256'],START_MS*1000000,END_MS*1000000)
    kwargs=build_a0_kwargs(Path(g['data_root']),Path(result),variant,feed)
    payload,restored=native_kwargs_json_roundtrip(kwargs)
    if restored!=kwargs or payload+'\n'!=Path(g['kwargs_payload']['path']).read_text():raise ValueError('ACTUAL_PREFIX_KWARGS_DIFFER_FROM_FREEZE')
    bound=signature(run_native_diagnostic).bind(**restored);bound.apply_defaults();validate_native_a0(bound.arguments)
    g['_stock_input_preflight']=stock_input_preflight(g,restored)
    return restored
FINANCIAL_GATES=('actual_os_exit0','complete_cash_reconciliation','signed_asset_funding_reconciliation','native_3TP','ownership','continuous_settled_coverage','coherent_prefill_preopen_event_coverage','source_config_data_comparable','rights_audit_complete','terminal_positions0_orders0','zero_model_liquidations')
METRIC_CONTRACT='ca815cbe3b8e163b16ccca8e388c9299125f74f0e1dd10beaa3ee15e4fe31102'
def load_freeze(path):
    raw=Path(path).read_bytes();g=json.loads(raw);g['_freeze_sha256']=hashlib.sha256(raw).hexdigest();return g
def pinned_json(ref):
    if not isinstance(ref,dict) or not ref.get('path') or not ref.get('sha256') or sha(ref['path'])!=ref['sha256']:raise ValueError('PINNED_FINANCIAL_ARTIFACT_MISMATCH')
    return json.loads(Path(ref['path']).read_text())
def attempt_digest(entry):
    return hashlib.sha256(json.dumps(entry,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest()
def verify_financial_qualifications(g,ledger,ledger_path,variant):
    required=list(ORDER[:ORDER.index(variant)]);refs=g.get('previous_financial_qualifications')
    if type(refs) is not list or [r.get('label') for r in refs]!=required:raise ValueError('EXACT_PRIOR_FINANCIAL_QUALIFICATIONS_REQUIRED')
    for ref,label in zip(refs,required):
        q=pinned_json(ref)
        if q.get('schema')!='CM_A0_FINANCIAL_QUALIFICATION_V1' or q.get('decision')!='FINANCIAL_ACCEPTED_CONTROL' or q.get('qualification')!='FINANCIALLY_QUALIFIED' or q.get('accounting_qualified') is not True or q.get('label')!=label or q.get('source_commit')!=SOURCE or q.get('metric_contract_sha256')!=METRIC_CONTRACT:raise ValueError('PRIOR_CONTROL_FINANCIAL_PASS_REQUIRED')
        gates=q.get('financial_gates')
        if type(gates) is not dict or not set(FINANCIAL_GATES)<=set(gates) or any(type(v) is not str or v!='PASS' for v in gates.values()):raise ValueError('ALL_PRIOR_FINANCIAL_GATES_MUST_PASS')
        for key in ('actual_returncode','terminal_open_positions','terminal_open_orders','model_liquidations'):
            if type(q.get(key)) is not int or q[key]!=0:raise ValueError('PRIOR_FINANCIAL_ZERO_STATE_REQUIRED')
        if Path(q['native_ledger_path']).resolve()!=Path(ledger_path).resolve():raise ValueError('PRIOR_FINANCIAL_LEDGER_PATH_MISMATCH')
        entries=[a for a in ledger['attempts'] if a['attempt_id']==q['attempt_id']]
        if len(entries)!=1:raise ValueError('UNIQUE_PRIOR_COMPLETED_ATTEMPT_REQUIRED')
        e=entries[0];detail=e.get('detail',{});report=Path(q['report_path']);namespace=namespace_root(g)/label
        if e['status']!='COMPLETED' or e['variant']!=label or e['source_commit']!=SOURCE or Path(e['namespace']).resolve()!=namespace or report.resolve()!=namespace/'result'/(label+'.json') or Path(detail.get('report','')).resolve()!=report.resolve() or detail.get('report_sha256')!=q['report_sha256'] or sha(report)!=q['report_sha256'] or type(detail.get('actual_returncode')) is not int or detail['actual_returncode']!=0:raise ValueError('PRIOR_COMPLETED_REPORT_BINDING_MISMATCH')
        digest=attempt_digest(e)
        if digest!=q['completed_attempt_sha256']:raise ValueError('CURRENT_PRIOR_ATTEMPT_CHANGED')
        snapshot=pinned_json(q['ledger_snapshot']);old=[x for x in snapshot['attempts'] if x['attempt_id']==q['attempt_id']]
        if len(old)!=1 or old[0]['status']!='COMPLETED' or attempt_digest(old[0])!=digest:raise ValueError('IMMUTABLE_PRIOR_ATTEMPT_SNAPSHOT_MISMATCH')
        native=json.loads(report.read_text());link=native.get('physical_prefix_attempt',{})
        if link.get('attempt_id')!=q['attempt_id'] or link.get('variant')!=label or link.get('source_commit')!=SOURCE or Path(link.get('ledger','')).resolve()!=Path(ledger_path).resolve():raise ValueError('PRIOR_REPORT_PHYSICAL_IDENTITY_MISMATCH')
        risk=pinned_json(dict(path=q['risk_analysis_path'],sha256=q['risk_analysis_sha256']))
        if risk.get('qualification')!='VALID_ACCOUNTED_PREFIX' or risk.get('accounting_qualified') is not True or risk.get('metric_contract_sha256')!=METRIC_CONTRACT or type(risk.get('actual_returncode')) is not int or risk['actual_returncode']!=0:raise ValueError('ACTUAL_PRIOR_RISK_ANALYSIS_PASS_REQUIRED')
        binding=risk.get('physical_binding',{})
        for key in ('attempt_id','label','source_commit','report_path','report_sha256','native_ledger_path','completed_attempt_sha256','completion_manifest_path','completion_manifest_sha256','supervisor_path','supervisor_sha256'):
            if binding.get(key)!=q[key]:raise ValueError('PRIOR_RISK_PHYSICAL_BINDING_MISMATCH:'+key)
        manifest=pinned_json(dict(path=q['completion_manifest_path'],sha256=q['completion_manifest_sha256']));supervisor=pinned_json(dict(path=q['supervisor_path'],sha256=q['supervisor_sha256']))
        if Path(q['completion_manifest_path']).resolve()!=namespace/'completion-manifest.json' or Path(q['supervisor_path']).resolve()!=namespace/'supervisor-receipt.json' or Path(detail['completion_manifest']).resolve()!=Path(q['completion_manifest_path']).resolve() or detail['completion_manifest_sha256']!=q['completion_manifest_sha256']:raise ValueError('PRIOR_COMPLETION_PATH_SHA_MISMATCH')
        if manifest.get('status')!='NATIVE_PROCESS_EXPORTED_ACTUAL_OS_ZERO' or supervisor.get('ledger_status')!='COMPLETED':raise ValueError('PRIOR_COMPLETION_STATUS_MISMATCH')
        for obj in (manifest,supervisor):
            if obj.get('attempt_id')!=q['attempt_id'] or obj.get('variant')!=label or obj.get('source_commit')!=SOURCE or type(obj.get('actual_returncode')) is not int or obj['actual_returncode']!=0 or obj.get('freeze_sha256')!=e['freeze_sha256']:raise ValueError('PRIOR_OS_SOURCE_FREEZE_IDENTITY_MISMATCH')
        if supervisor.get('completion_manifest_sha256')!=q['completion_manifest_sha256']:raise ValueError('PRIOR_SUPERVISOR_MANIFEST_HASH_MISMATCH')
        verify_rows(manifest['artifacts'],namespace,label)
def verify_worker_claim(path,g,variant,namespace,attempt_id):
    verify_scope(g,variant,namespace,require_go=True);ledger=json.loads(Path(path).read_text());entries=[e for e in ledger['attempts'] if e['attempt_id']==attempt_id]
    if len(entries)!=1:raise ValueError('UNIQUE_ACTUAL_WORKER_CLAIM_REQUIRED')
    e=entries[0]
    if e['status']!='STARTED' or e['source_commit']!=SOURCE or e['variant']!=variant or e['namespace']!=str(namespace) or e.get('freeze_sha256')!=g['_freeze_sha256'] or e.get('prefix_phase','INITIAL')!=g.get('prefix_phase','INITIAL'):raise ValueError('ACTUAL_WORKER_CLAIM_FREEZE_IDENTITY_MISMATCH')
    phase_entries(g,ledger)
    if g.get('physical_prefix_max')==4 and (e.get('phase_index')!=ORDER.index(variant)+1 or e.get('physical_index')!=ORDER.index(variant)+2):raise ValueError('WORKER_EXACT_AMEND4_PHASE_INDEX_REQUIRED')
    verify_financial_qualifications(g,ledger,path,variant)
    return e
def claim(path,g,variant,namespace):
    verify_scope(g,variant,namespace,require_go=True)
    with transaction(path) as ledger:
        cap=g['physical_prefix_max']
        if ledger.get('physical_max')!=cap or ledger.get('protocol_sha256')!=PROTOCOL or ledger.get('physical_started',0)>=cap:raise ValueError('PREFIX_BUDGET_EXHAUSTED_OR_DIFFERENT')
        prior=phase_entries(g,ledger);n=len(prior)
        if ledger['physical_started']!=len(ledger['attempts']) or n>=3 or any(e['status']!='COMPLETED' for e in prior) or variant!=ORDER[n]:raise ValueError('STRICT_PHASE_OFF_C0_A0_STOP_AFTER_FAILURE')
        if g.get('previous_accepted_attempt_ids')!=[e['attempt_id'] for e in prior]:raise ValueError('ROOT_PREVIOUS_PHASE_ACCEPTANCE_LINK_REQUIRED')
        if any(e['source_commit']!=SOURCE for e in prior):raise ValueError('SAME_MATCHED_SOURCE_REQUIRED')
        verify_financial_qualifications(g,ledger,path,variant)
        aid=str(uuid.uuid4());physical=ledger['physical_started']+1;ledger['physical_started']=physical;ledger['active']=1;ledger['status']='PREFIX_PROCESS_ATTEMPT_RUNNING'
        ledger['attempts'].append(dict(attempt_id=aid,physical_index=physical,prefix_phase=g.get('prefix_phase','INITIAL'),phase_index=n+1,variant=variant,source_commit=SOURCE,status='STARTED',started_utc=utc(),namespace=str(namespace),freeze_sha256=g['_freeze_sha256']))
        return aid
def finish(path,aid,status,detail):
    with transaction(path) as ledger:
        entry=next(a for a in ledger['attempts'] if a['attempt_id']==aid)
        if entry['status']!='STARTED':raise ValueError('PREFIX_ATTEMPT_FINAL_ALREADY')
        entry.update(status=status,finished_utc=utc(),detail=detail);ledger['active']=0;ledger['status']='PREFIX_CHECKPOINT_ROOT_REVIEW_REQUIRED' if status=='COMPLETED' else 'PREFIX_FAILED_HOLD_NO_AUTOMATIC_RETRY'
def artifact_rows(namespace,variant):
    result=Path(namespace)/'result'
    names={'report':variant+'.json','orders':variant+'-orders.csv','funding':variant+'-funding.sqlite','coherent':'coherent-native-events.jsonl.gz'}
    return [dict(role=role,path=str(result/name),sha256=sha(result/name)) for role,name in names.items()]
def verify_rows(rows,namespace,variant):
    actual=artifact_rows(namespace,variant)
    if rows!=actual:raise ValueError('NATIVE_COMPLETION_FOUR_HASHES_MISMATCH')
    return actual
