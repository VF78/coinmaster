"""Pure supervisor OS-child tests: stdlib children only, no Nautilus/engine."""
from pathlib import Path
import os,signal,sys,time
import pytest
import sol_standing_supervisor as sup

def command(code):return [sys.executable,'-I','-c',code]
def run(tmp_path,code='pass',**kw):
    return sup.dispatch_once(command(code),cwd=tmp_path,env=dict(PATH='/usr/bin:/bin',PYTHONNOUSERSITE='1'),
        namespace=tmp_path,shutdown_timeout=.1,**kw)

def test_actual_zero_child_exit_is_distinct_from_supervisor_exit(tmp_path):
    r=run(tmp_path)
    assert r['child_actual_process_exit_code']==0 and r['terminal_confirmed']
    assert r['supervisor_return_code']==0 and r['actual_supervisor_exit_code']is None
    assert sup.outcome_state(r)==dict(status='COMPLETED',active=0,ledger_status='AWAITING_ROOT_DISPOSITION_NO_AUTONEXT')

def test_actual_nonzero_child_exit_is_not_default_error_code(tmp_path):
    r=run(tmp_path,'raise SystemExit(7)')
    assert r['child_actual_process_exit_code']==7 and r['supervisor_return_code']==1
    assert sup.outcome_state(r)['active']==0 and sup.outcome_state(r)['status']=='FAILED'

def test_failed_popen_positively_not_spawned_child_rc_is_null(tmp_path):
    r=sup.dispatch_once([str(tmp_path/'nonexistent-python')],cwd=tmp_path,env={},namespace=tmp_path)
    assert r['child_actual_process_exit_code']is None and r['child_not_spawned_confirmed']
    assert r['child_pid']is None and r['supervisor_return_code']==1
    assert sup.outcome_state(r)['status']=='FAILED_NOT_SPAWNED'and sup.outcome_state(r)['active']==0

def test_before_spawn_failure_has_positive_no_child_authority(tmp_path):
    def failure():raise OSError('UNIT namespace/claim write failure')
    r=run(tmp_path,before_spawn=failure)
    assert not r['spawn_attempted']and r['child_not_spawned_confirmed']
    assert r['child_actual_process_exit_code']is None and sup.outcome_state(r)['active']==0

def test_write_failure_after_spawn_shuts_down_only_owned_child_and_reaps(tmp_path):
    def failure(p):raise OSError('UNIT started-receipt write failure')
    r=run(tmp_path,'import time;time.sleep(30)',on_started=failure)
    assert r['child_pid']>0 and type(r['child_actual_process_exit_code'])is int
    assert r['terminal_confirmed']and not r['child_not_spawned_confirmed']
    assert r['supervisor_return_code']==1 and sup.outcome_state(r)['active']==0

def test_ignored_terminate_escalates_to_owned_kill_and_observed_exit(tmp_path):
    ready=tmp_path/'ready'
    code="import signal,time;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path("+repr(str(ready))+").write_text('ready');time.sleep(30)"
    def failure(p):
        until=time.monotonic()+3
        while not ready.exists()and time.monotonic()<until:time.sleep(.01)
        assert ready.exists()
        raise KeyboardInterrupt('UNIT supervisor interrupted after started')
    r=run(tmp_path,code,on_started=failure)
    assert r['child_actual_process_exit_code']==-signal.SIGKILL and r['terminal_confirmed']
    assert r['supervisor_return_code']==1 and sup.outcome_state(r)['active']==0

def test_popen_interrupt_without_returned_handle_stays_unknown_active(tmp_path,monkeypatch):
    def interrupted(*a,**kw):raise KeyboardInterrupt('UNIT ambiguous constructor interruption')
    monkeypatch.setattr(sup.subprocess,'Popen',interrupted)
    r=run(tmp_path)
    assert r['spawn_attempted']and not r['child_not_spawned_confirmed']
    assert r['child_actual_process_exit_code']is None and not r['terminal_confirmed']
    assert sup.outcome_state(r)['active']==1 and sup.outcome_state(r)['status']=='UNKNOWN_REQUIRES_RECONCILIATION'

def test_unobservable_started_child_never_gets_false_terminal_authority(tmp_path,monkeypatch):
    real=sup.subprocess.Popen;owned=[]
    def factory(*a,**kw):
        p=real(*a,**kw);wait=p.wait;owned.append((p,wait))
        def unknown(*a,**kw):raise RuntimeError('UNIT OS wait/poll observation unavailable')
        p.wait=unknown;p.poll=unknown
        return p
    monkeypatch.setattr(sup.subprocess,'Popen',factory)
    try:
        def failure(p):raise OSError('UNIT after-start receipt failure')
        r=run(tmp_path,'import time;time.sleep(30)',on_started=failure)
        assert r['child_pid']>0 and r['child_actual_process_exit_code']is None
        assert not r['terminal_confirmed']and sup.outcome_state(r)['active']==1
    finally:
        for p,wait in owned:
            # Dispose only this unit's stdlib child; this is not native recovery.
            try:os.kill(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            wait(timeout=3)
