"""CM137 stdlib-only single attempt supervisor; no import of native drivers.

--prepare does not claim/spawn. --launch consumes a durable attempt BEFORE
child Popen/imports. Each signed root GO permits one fresh namespace only.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, errno, fcntl, hashlib, json, os, subprocess, sys, uuid

PROTOCOL='faa392477050d3c33f54b837edd6e0d9dca536eef4e740730d64ca52b7a5d0ea'
APPROVAL='6b8625d810878d0ef0a959687cc14f43b4a3adc85ac79e078c65eafc3e3be6d1'
BASE='7f38278257624b321c9d88d9df962505b6f5bab0'
AMENDMENT='c4ee6b54366edc880b7c42a98dff094f8e757f4bda7e412b8493fb5441004ab6'
AMENDMENT_PROTOCOL='53f6d79a2c1be4164e9f298b9f8c58d5246d74f0e064708b2942d8914a189b37'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def write(path,value):
    p=Path(path);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    with tmp.open('rb')as f:os.fsync(f.fileno())
    os.replace(tmp,p)
    fd=os.open(p.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def case_identity(g):
    logical=g["fixture_id"];scenario=g.get("scenario",logical);repeat=g.get("repeat_of")
    assert logical in("E1","E2","E3","E4","E5","E6","E7")
    if logical in("E6","E7"):
        assert scenario=="E1"and isinstance(repeat,str)and str(uuid.UUID(repeat))==repeat
    else:assert scenario==logical and repeat is None
    return dict(fixture_id=logical,scenario=scenario,repeat_of=repeat)

def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def validate_reserved_repeat(g,l,launch=False):
    identity=case_identity(g)
    if identity["fixture_id"]!="E6":return identity
    assert 1<=l["physical_started"]<l["physical_max"]==6
    assert not any(row.get("reserved_repeat")or row["fixture_id"]=="E6"for row in l["attempts"]),"RESERVED_REPEAT_ALREADY_SPENT"
    failed=[row for row in l["attempts"]if row["attempt_id"]==identity["repeat_of"]]
    assert len(failed)==1
    failed=failed[0]
    assert failed["status"]=="FAILED"and failed["fixture_id"]=="E1"and failed.get("scenario","E1")=="E1"
    assert failed["source_commit"]==g["repeat_of_source_commit"]and failed["source_commit"]!=g["source_commit"]
    assert canonical(failed)==g["failed_entry_canonical_sha256"],"FIRST_FAILED_ENTRY_CHANGED"
    saved=g["failed_ledger_snapshot"];assert sha(saved["path"])==saved["sha256"]
    snapshot=json.loads(Path(saved["path"]).read_text())
    old=[row for row in snapshot["attempts"]if row["attempt_id"]==identity["repeat_of"]]
    assert len(old)==1 and canonical(old[0])==canonical(failed)
    if launch or g.get("consolidated_correction_reviewed"):
        assert g.get("consolidated_correction_reviewed")is True
        assert g["reviewed_source_commit"]==g["source_commit"]
        review=g["correction_review"];assert sha(review["path"])==review["sha256"]
        assert json.loads(Path(review["path"]).read_text())["source_commit"]==g["source_commit"]
    return identity

def validate_amendment7(g,l,launch=False):
    pin=g["amendment_approval"]
    assert pin["sha256"]==AMENDMENT and sha(pin["path"])==AMENDMENT
    assert l["amendment_approval"]==pin
    a=json.loads(Path(pin["path"]).read_text())
    assert a["status"]=="APPROVED_BY_OWNER"and a["engineering_physical_max"]==7
    assert a["original_approval"]["sha256"]==APPROVAL and a["original_protocol_sha256"]==PROTOCOL
    protocol=g["amendment_protocol"]
    assert a["amendment_protocol"]["sha256"]==protocol["sha256"]==AMENDMENT_PROTOCOL and sha(protocol["path"])==AMENDMENT_PROTOCOL
    return amendment7_identity(g,l,a,launch)

def amendment7_identity(g,l,a,launch=False):
    assert l["physical_max"]==7 and l["physical_started"]<7 and l["active"]==0
    for saved in a["preserved_failed_rows"]:
        matches=[row for row in l["attempts"]if row["attempt_id"]==saved["attempt_id"]]
        assert len(matches)==1 and matches[0]["status"]=="FAILED"
        assert canonical(matches[0])==saved["canonical_sha256"],"PRESERVED_FAILED_ROW_CHANGED"
    assert len(l["attempts"])==l["physical_started"]
    assert [row["attempt_id"]for row in l["attempts"][:2]]==[row["attempt_id"]for row in a["preserved_failed_rows"]]
    for index,row in enumerate(l["attempts"][2:],3):
        # The two preserved failures are the ONLY exceptions. A new failure,
        # unknown OS exit, or unqualified completion cannot spend a next slot.
        expected=next(x for x in a["physical_schedule"]if x["physical_index"]==index)
        assert row["physical_index"]==index and row["fixture_id"]==expected["fixture_id"]and row["scenario"]==expected["scenario"]
        assert row.get("repeat_of")==expected.get("repeat_of")
        assert row["status"]=="COMPLETED","ANY_NEW_FAILURE_STOP"
        for key in("actual_process_exit_code","actual_supervisor_exit_code","actual_external_dispatcher_exit_code"):
            assert type(row.get(key))is int and row[key]==0,"OBSERVED_ZERO_OS_EXITS_REQUIRED"
        assert row["supervisor_exit_authority"]=="EXTERNAL_DISPATCHER_AFTER_EXIT"
        pin=row["external_dispatcher_exit_receipt"]
        assert sha(pin["path"])==pin["sha256"],"EXTERNAL_OS_RECEIPT_PIN_CHANGED"
        receipt=json.loads(Path(pin["path"]).read_text())
        assert receipt["schema"]=="CM137_ROOT_ACTUAL_EXTERNAL_OS_EXIT_V1"
        assert receipt["authority"]=="OBSERVED_EXEC_SESSION_COMPLETION_NOT_WRAPPER_GUESS"
        assert receipt["attempt_id"]==row["attempt_id"]and receipt["fixture_id"]==row["fixture_id"]and receipt["scenario"]==row["scenario"]
        assert receipt.get("repeat_of")==row.get("repeat_of")
        for key in("external_dispatcher_pid","actual_supervisor_pid","actual_native_child_pid"):
            assert type(receipt.get(key))is int and receipt[key]>0,"OBSERVED_PID_REQUIRED"
        assert receipt["actual_supervisor_pid"]==row["supervisor_pid"]and receipt["actual_native_child_pid"]==row["child_pid"]
        for key in("actual_native_child_os_exit_code","actual_supervisor_os_exit_code","actual_external_dispatcher_os_exit_code"):
            assert type(receipt.get(key))is int and receipt[key]==0,"EXTERNAL_OBSERVED_ZERO_REQUIRED"
    identity=case_identity(g)
    schedule=next(row for row in a["physical_schedule"]if row["physical_index"]==l["physical_started"]+1)
    assert identity["fixture_id"]==schedule["fixture_id"]and identity["scenario"]==schedule["scenario"]
    assert identity["repeat_of"]==schedule.get("repeat_of")
    if identity["fixture_id"]=="E7":
        assert l["physical_started"]==2 and not any(row["fixture_id"]=="E7"for row in l["attempts"])
        failed=next(row for row in l["attempts"]if row["attempt_id"]==identity["repeat_of"])
        assert failed["fixture_id"]=="E6"and failed["scenario"]=="E1"and failed["status"]=="FAILED"
        assert failed["source_commit"]!=g["source_commit"]
    if launch or g.get("consolidated_correction_reviewed"):
        assert g.get("consolidated_correction_reviewed")is True
        assert g["reviewed_source_commit"]==g["source_commit"]
        review=g["correction_review"];assert sha(review["path"])==review["sha256"]
        assert json.loads(Path(review["path"]).read_text())["source_commit"]==g["source_commit"]
    return identity

def verify(gate_path,ledger_path,launch=False):
    g=json.loads(Path(gate_path).read_text());l=json.loads(Path(ledger_path).read_text())
    assert g['protocol_sha256']==PROTOCOL and g['source_base']==BASE
    case_identity(g)
    assert g['owner_approval']['sha256']==APPROVAL and sha(g['owner_approval']['path'])==APPROVAL
    approval=json.loads(Path(g['owner_approval']['path']).read_text())
    assert approval['status']=='APPROVED_BY_OWNER'and approval['engineering_physical_max']==6
    assert approval['protocol_sha256']==PROTOCOL
    assert l['physical_max']==7 and l['physical_started']==g['expected_before'] and l['active']==0
    assert l['physical_started']<7 and len(l['attempts'])==l['physical_started']
    assert not any(x['status']=='STARTED'for x in l['attempts'])
    assert sha(ledger_path)==g['ledger_before_sha256'],'LEDGER_PIN_CHANGED'
    assert type(g['root_go'])is bool
    if launch:assert g['root_go']is True,'ROOT_GO_REQUIRED'
    assert g['immutable_pins'],'EMPTY_IMMUTABLE_PINS'
    for pin in g['immutable_pins']:assert sha(pin['path'])==pin['sha256'],pin['path']
    root=Path(g['source_root']).resolve();driver=root/'tests/run_sol_standing_fixture.py'
    pinned={str(Path(p['path']).resolve())for p in g['immutable_pins']}
    assert str(driver)in pinned and str(root/'coinmaster/strategy/paired_prefix.py')in pinned
    assert str(root/'coinmaster/strategy/wave_overlay.py')in pinned
    seal=json.loads(Path(g['source_seal']['path']).read_text())
    assert sha(g['source_seal']['path'])==g['source_seal']['sha256']and seal['source_commit']==g['source_commit']
    preflight=g['preflight_receipt']
    assert sha(preflight['path'])==preflight['sha256'],'PREFLIGHT_RECEIPT_PIN_CHANGED'
    proof=json.loads(Path(preflight['path']).read_text())
    assert proof['engine_constructors']==0 and proof['source_commit']==g['source_commit']
    case=g.get('scenario',g['fixture_id']);frozen=proof['configs'][case]
    assert frozen['config']['sha256']==g['native_config_sha256']
    assert frozen['registered_kwargs']['sha256']==g['registered_kwargs_sha256']
    assert frozen['transport']==g['transport'],'STATIC_TRANSPORT_PIN_CHANGED'
    assert Path(g['python']).is_absolute()and Path(g['python']).is_file()
    assert not Path(g['namespace']).exists(),'FRESH_NAMESPACE_REQUIRED'
    validate_amendment7(g,l,launch)
    return g,l,driver


def dispatch_once(command,*,cwd,env,namespace,before_spawn=None,on_started=None,shutdown_timeout=5):
    """One owned OS child, nullable observed exit; never guess exit authority."""
    p=None;attempted=False;observed_rc=None;errors=[];not_spawned=False
    try:
        if before_spawn is not None:before_spawn()
        with (Path(namespace)/'stdout.log').open('wb')as out,(Path(namespace)/'stderr.log').open('wb')as err:
            attempted=True
            try:p=subprocess.Popen(command,cwd=cwd,env=env,stdout=out,stderr=err)
            except OSError as exc:
                # Popen's documented exec/fork failure has no returned child;
                # these errors are positively failed execs, not unknown signals.
                not_spawned=exc.errno in {errno.ENOENT,errno.EACCES,errno.ENOEXEC,errno.ENOTDIR}
                raise
            if on_started is not None:on_started(p)
            observed_rc=p.wait()
    except BaseException as exc:
        errors.append(dict(stage='DISPATCH',type=type(exc).__name__,error=repr(exc)))
        if p is None:
            not_spawned=not_spawned or not attempted
        else:
            try:observed_rc=p.poll()
            except BaseException as exc:errors.append(dict(stage='POLL',error=repr(exc)))
            if type(observed_rc)is not int:
                try:p.terminate()
                except ProcessLookupError:pass
                except BaseException as exc:errors.append(dict(stage='TERMINATE_OWN_CHILD',error=repr(exc)))
                try:observed_rc=p.wait(timeout=shutdown_timeout)
                except subprocess.TimeoutExpired:
                    try:p.kill()
                    except ProcessLookupError:pass
                    except BaseException as exc:errors.append(dict(stage='KILL_OWN_CHILD',error=repr(exc)))
                    try:observed_rc=p.wait(timeout=shutdown_timeout)
                    except BaseException as exc:errors.append(dict(stage='REAP_OWN_CHILD',error=repr(exc)))
                except BaseException as exc:errors.append(dict(stage='WAIT_OWN_CHILD',error=repr(exc)))
    observed_rc=observed_rc if type(observed_rc)is int else None
    terminal=not_spawned or observed_rc is not None
    state='NOT_SPAWNED'if not_spawned else'EXIT_OBSERVED'if observed_rc is not None else'SPAWN_OR_EXIT_UNKNOWN'
    return dict(child_pid=None if p is None else p.pid,spawn_attempted=attempted,
        child_state=state,child_not_spawned_confirmed=not_spawned,
        child_actual_process_exit_code=observed_rc,terminal_confirmed=terminal,errors=errors,
        supervisor_return_code=0 if observed_rc==0 and not errors else 1,
        actual_supervisor_exit_code=None,supervisor_exit_authority='EXTERNAL_DISPATCHER_AFTER_EXIT')


def outcome_state(result):
    terminal=result['terminal_confirmed']
    if not terminal:return dict(status='UNKNOWN_REQUIRES_RECONCILIATION',active=1,ledger_status='ACTIVE_UNKNOWN_RECONCILIATION_REQUIRED')
    status='FAILED_NOT_SPAWNED'if result['child_not_spawned_confirmed']else'COMPLETED'if result['child_actual_process_exit_code']==0 and result['supervisor_return_code']==0 else'FAILED'
    return dict(status=status,active=0,ledger_status='AWAITING_ROOT_DISPOSITION_NO_AUTONEXT')


def launch(gate_path,ledger_path):
    with Path(str(ledger_path)+'.lock').open('a')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        g,l,driver=verify(gate_path,ledger_path,True)
        identity=case_identity(g)
        ns=Path(g['namespace']);before=Path(ledger_path).read_bytes()
        attempt=str(uuid.uuid4());row=dict(attempt_id=attempt,physical_index=l['physical_started']+1,
            fixture_id=identity['fixture_id'],scenario=identity['scenario'],repeat_of=identity['repeat_of'],
            reserved_repeat=identity['fixture_id']=='E6',amended_repeat=identity['fixture_id']=='E7',status='STARTED',
            started_utc=now(),supervisor_pid=os.getpid(),source_commit=g['source_commit'],
            gate_sha256=sha(gate_path),namespace=str(ns),protocol_sha256=PROTOCOL,
            ledger_before_sha256=hashlib.sha256(before).hexdigest(),amendment_approval=g['amendment_approval'],amendment_protocol=g['amendment_protocol'],
            engine_constructor_claimed=False,child_pid=None,actual_process_exit_code=None,
            actual_supervisor_exit_code=None)
        # Every valid dispatch is spent before namespace creation/Popen/import.
        l['attempts'].append(row);l.update(physical_started=len(l['attempts']),active=1,
            authorized_remaining=7-len(l['attempts']),status='RUNNING',root_go=False)
        write(ledger_path,l)
        def before_spawn():
            ns.mkdir(parents=True,exist_ok=False)
            (ns/'LEDGER_BEFORE_CLAIM.json').write_bytes(before)
            with (ns/'LEDGER_BEFORE_CLAIM.json').open('rb')as f:os.fsync(f.fileno())
            write(ns/'CLAIM.json',row)
        def started(p):
            write(ns/'PROCESS_STARTED.json',dict(attempt_id=attempt,pid=p.pid,source_commit=g['source_commit'],**identity))
        env=dict(PATH='/usr/bin:/bin',LANG='en_US.UTF-8',PYTHONNOUSERSITE='1',
            PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(g['source_root'])+os.pathsep+str(driver.parent),OPENBLAS_NUM_THREADS='1')
        result=dispatch_once([g['python'],str(driver),'--gate',str(gate_path),'--ledger',str(ledger_path),
            '--attempt',attempt],cwd=g['source_root'],env=env,namespace=ns,before_spawn=before_spawn,on_started=started)
        state=outcome_state(result)
        actual=json.loads(Path(ledger_path).read_text());entry=actual['attempts'][-1]
        assert entry['attempt_id']==attempt
        entry.update(status=state['status'],last_observed_utc=now(),
            actual_process_exit_code=result['child_actual_process_exit_code'],
            child_pid=result['child_pid'],child_state=result['child_state'],
            child_not_spawned_confirmed=result['child_not_spawned_confirmed'],
            supervisor_return_code=result['supervisor_return_code'],
            actual_supervisor_exit_code=None,supervisor_exit_authority=result['supervisor_exit_authority'],
            supervision_errors=result['errors'])
        if result['terminal_confirmed']:entry['finished_utc']=now()
        if (ns/'result.json').exists():entry.update(result_path=str(ns/'result.json'),result_sha256=sha(ns/'result.json'))
        file='PROCESS_EXIT.json'if result['child_actual_process_exit_code']is not None else'NOT_SPAWNED.json'if result['child_not_spawned_confirmed']else'PROCESS_STATE_UNKNOWN.json'
        try:write(ns/file,dict(attempt_id=attempt,**identity,**result))
        except BaseException as exc:
            entry['terminal_receipt_write_error']=repr(exc);entry['supervisor_return_code']=1
            if state['status']=='COMPLETED':entry['status']='FAILED'
        actual.update(active=state['active'],status=state['ledger_status'],root_go=False)
        write(ledger_path,actual)
        return entry['supervisor_return_code']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--gate',required=True);p.add_argument('--ledger',required=True)
    mode=p.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare',action='store_true');mode.add_argument('--launch',action='store_true');a=p.parse_args()
    if a.prepare:
        g,l,_=verify(a.gate,a.ledger);print(json.dumps(dict(status='PREPARED_ENGINE0_NO_ATTEMPT',
            root_go=g['root_go'],physical_started=l['physical_started'],engine_constructors=0,
            identity=case_identity(g),correction_reviewed=g.get('consolidated_correction_reviewed',False))));raise SystemExit(0)
    raise SystemExit(launch(a.gate,a.ledger))
