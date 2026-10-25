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
def verify_scope(g,variant,namespace,require_go=False):
    if g.get('source_commit')!=SOURCE or g.get('protocol_sha256')!=PROTOCOL or g.get('variant')!=variant or variant not in ORDER:
        raise ValueError('EXACT_A0_PREFIX_SOURCE_SCOPE_REQUIRED')
    if Path(namespace).resolve()!=JOB/variant or g.get('physical_prefix_max')!=3 or g.get('full')!=0 or g.get('training')!=0 or g.get('downloads')!=0:
        raise ValueError('EXACT_PREFIX_NAMESPACE_BUDGET_REQUIRED')
    if g.get('calendar')!='[2024-09-01T00:00:00Z,2025-01-15T00:00:00Z)' or g.get('seed')!='10000' or g.get('reserve')!='0':
        raise ValueError('EXACT_PREFIX_WINDOW_SEED_REQUIRED')
    if require_go:
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
    return restored
def claim(path,g,variant,namespace):
    verify_scope(g,variant,namespace,require_go=True)
    with transaction(path) as ledger:
        if ledger.get('physical_max')!=3 or ledger.get('protocol_sha256')!=PROTOCOL or ledger.get('physical_started',0)>=3:
            raise ValueError('PREFIX_BUDGET_EXHAUSTED_OR_DIFFERENT')
        prior=ledger.get('attempts',[]);n=ledger['physical_started']
        if len(prior)!=n or any(a['status']!='COMPLETED' for a in prior) or variant!=ORDER[n]:raise ValueError('STRICT_OFF_C0_A0_STOP_AFTER_FAILURE')
        if g.get('previous_accepted_attempt_ids')!=[a['attempt_id'] for a in prior]:raise ValueError('ROOT_PREVIOUS_ACCEPTANCE_LINK_REQUIRED')
        if any(a['source_commit']!=SOURCE for a in prior):raise ValueError('SAME_MATCHED_SOURCE_REQUIRED')
        aid=str(uuid.uuid4());ledger['physical_started']=n+1;ledger['active']=1;ledger['status']='PREFIX_PROCESS_ATTEMPT_RUNNING'
        ledger['attempts'].append(dict(attempt_id=aid,physical_index=n+1,variant=variant,source_commit=SOURCE,status='STARTED',started_utc=utc(),namespace=str(namespace),freeze_sha256=g['_freeze_sha256']))
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
