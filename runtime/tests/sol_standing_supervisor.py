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


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def write(path,value):
    p=Path(path);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    with tmp.open('rb')as f:os.fsync(f.fileno())
    os.replace(tmp,p)
    fd=os.open(p.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def verify(gate_path,ledger_path,launch=False):
    g=json.loads(Path(gate_path).read_text());l=json.loads(Path(ledger_path).read_text())
    assert g['protocol_sha256']==PROTOCOL and g['source_base']==BASE
    assert g['fixture_id']in('E1','E2','E3','E4','E5','E6')
    assert g['owner_approval']['sha256']==APPROVAL and sha(g['owner_approval']['path'])==APPROVAL
    approval=json.loads(Path(g['owner_approval']['path']).read_text())
    assert approval['status']=='APPROVED_BY_OWNER'and approval['engineering_physical_max']==6
    assert approval['protocol_sha256']==PROTOCOL
    assert l['physical_max']==6 and l['physical_started']==g['expected_before'] and l['active']==0
    assert l['physical_started']<6 and len(l['attempts'])==l['physical_started']
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
    if g['fixture_id']=='E6':
        assert l['physical_started']==5 and g.get('repeat_of')and g['scenario']in('E1','E2','E3','E4','E5')
        assert g.get('consolidated_correction_reviewed')is True
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
        ns=Path(g['namespace']);before=Path(ledger_path).read_bytes()
        attempt=str(uuid.uuid4());row=dict(attempt_id=attempt,physical_index=l['physical_started']+1,
            fixture_id=g['fixture_id'],scenario=g.get('scenario',g['fixture_id']),status='STARTED',
            started_utc=now(),supervisor_pid=os.getpid(),source_commit=g['source_commit'],
            gate_sha256=sha(gate_path),namespace=str(ns),protocol_sha256=PROTOCOL,
            ledger_before_sha256=hashlib.sha256(before).hexdigest(),
            engine_constructor_claimed=False,child_pid=None,actual_process_exit_code=None,
            actual_supervisor_exit_code=None)
        # Every valid dispatch is spent before namespace creation/Popen/import.
        l['attempts'].append(row);l.update(physical_started=len(l['attempts']),active=1,
            authorized_remaining=6-len(l['attempts']),status='RUNNING',root_go=False)
        write(ledger_path,l)
        def before_spawn():
            ns.mkdir(parents=True,exist_ok=False)
            (ns/'LEDGER_BEFORE_CLAIM.json').write_bytes(before)
            with (ns/'LEDGER_BEFORE_CLAIM.json').open('rb')as f:os.fsync(f.fileno())
            write(ns/'CLAIM.json',row)
        def started(p):
            write(ns/'PROCESS_STARTED.json',dict(attempt_id=attempt,pid=p.pid,source_commit=g['source_commit']))
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
        try:write(ns/file,dict(attempt_id=attempt,**result))
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
            root_go=g['root_go'],physical_started=l['physical_started'],engine_constructors=0)));raise SystemExit(0)
    raise SystemExit(launch(a.gate,a.ledger))
