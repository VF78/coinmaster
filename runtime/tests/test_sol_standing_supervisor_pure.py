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


import copy,json,hashlib
FAILED_UUID='11111111-1111-4111-8111-111111111111'

def reserve_state(tmp_path):
    failed=dict(attempt_id=FAILED_UUID,fixture_id='E1',scenario='E1',status='FAILED',source_commit='OLD',actual_process_exit_code=1)
    ledger=dict(physical_started=1,physical_max=6,attempts=[failed])
    path=tmp_path/'failed-ledger.json';path.write_text(json.dumps(ledger,indent=2))
    g=dict(fixture_id='E6',scenario='E1',repeat_of=FAILED_UUID,source_commit='NEW',
        repeat_of_source_commit='OLD',failed_entry_canonical_sha256=sup.canonical(failed),
        failed_ledger_snapshot=dict(path=str(path),sha256=sup.sha(path)),consolidated_correction_reviewed=False)
    return g,ledger,path

def test_logical_e6_physical2_is_valid_prepare_but_review_blocks_launch(tmp_path):
    g,l,_=reserve_state(tmp_path)
    assert sup.validate_reserved_repeat(g,l)==dict(fixture_id='E6',scenario='E1',repeat_of=FAILED_UUID)
    with pytest.raises(AssertionError):sup.validate_reserved_repeat(g,l,launch=True)
    review=tmp_path/'review.json';review.write_text(json.dumps(dict(source_commit='NEW')))
    g.update(consolidated_correction_reviewed=True,reviewed_source_commit='NEW',
        correction_review=dict(path=str(review),sha256=sup.sha(review)))
    assert sup.validate_reserved_repeat(g,l,launch=True)['scenario']=='E1'

@pytest.mark.parametrize('mutation',['repeat_used','not_failed','wrong_scenario','changed_failed','wrong_review_source','over_budget'])
def test_logical_reserve_invalid_binding_never_admits(tmp_path,mutation):
    g,l,_=reserve_state(tmp_path)
    if mutation=='repeat_used':l['attempts'].append(dict(fixture_id='E6',reserved_repeat=True))
    elif mutation=='not_failed':l['attempts'][0]['status']='COMPLETED'
    elif mutation=='wrong_scenario':g['scenario']='E2'
    elif mutation=='changed_failed':l['attempts'][0]['actual_process_exit_code']=0
    elif mutation=='over_budget':l['physical_started']=6
    else:g.update(consolidated_correction_reviewed=True,reviewed_source_commit='WRONG')
    with pytest.raises((AssertionError,KeyError)):sup.validate_reserved_repeat(g,l)

def test_logical_case_worker_config_result_and_external_metadata_match_without_engine(tmp_path):
    from run_sol_standing_fixture import fixture_binding,fixture_config,snapshot_config
    from coinmaster.research.native_book import NativeBookWitness
    g,l,path=reserve_state(tmp_path);before=path.read_bytes();canonical=sup.canonical(l['attempts'][0])
    identity=sup.validate_reserved_repeat(g,l)
    claim=dict(attempt_id='unit-new-attempt',physical_index=2,reserved_repeat=True,**identity)
    assert fixture_binding(g,claim)==identity
    cfg,kwargs=fixture_config(NativeBookWitness(),identity['scenario'])
    ordinary,ordinary_kwargs=fixture_config(NativeBookWitness(),'E1')
    assert snapshot_config(cfg)==snapshot_config(ordinary)and kwargs==ordinary_kwargs
    assert not cfg.research_a0_original_second and not cfg.research_btc_trim_control
    artifacts=[dict(kind=kind,**identity)for kind in('CLI_GATE','CLAIM_LEDGER','CONFIG','WORKER','RESULT','SUPERVISOR_RECEIPT','EXTERNAL_RECEIPT')]
    assert json.loads(json.dumps(artifacts))==artifacts
    assert all(a['fixture_id']=='E6'and a['scenario']=='E1'and a['repeat_of']==FAILED_UUID for a in artifacts)
    assert path.read_bytes()==before and sup.canonical(l['attempts'][0])==canonical
    wrong=dict(claim,fixture_id='E1')
    with pytest.raises(AssertionError,match='WORKER_CASE_IDENTITY_MISMATCH'):fixture_binding(g,wrong)


def amend_state():
    first=dict(attempt_id=FAILED_UUID,fixture_id="E1",scenario="E1",status="FAILED",source_commit="BEFORE")
    second=dict(attempt_id="22222222-2222-4222-8222-222222222222",fixture_id="E6",scenario="E1",status="FAILED",source_commit="OLD")
    l=dict(physical_started=2,physical_max=7,active=0,attempts=[first,second])
    a=dict(preserved_failed_rows=[dict(attempt_id=x["attempt_id"],canonical_sha256=sup.canonical(x))for x in l["attempts"]],physical_schedule=[dict(physical_index=3,fixture_id="E7",scenario="E1",repeat_of=second["attempt_id"])]+[dict(physical_index=i+2,fixture_id="E"+str(i),scenario="E"+str(i))for i in range(2,6)])
    g=dict(fixture_id="E7",scenario="E1",repeat_of=second["attempt_id"],source_commit="NEW",consolidated_correction_reviewed=False)
    return g,l,a

def test_amend7_physical3_is_same_e1_scenario_and_review_blocks_launch():
    g,l,a=amend_state();sup.amendment7_identity(g,l,a)
    assert sup.case_identity(g)==dict(fixture_id="E7",scenario="E1",repeat_of=g["repeat_of"])
    from run_sol_standing_fixture import fixture_binding,fixture_config
    assert fixture_binding(g,sup.case_identity(g))==sup.case_identity(g)
    assert fixture_config(None,"E1")[0].research_a0_original_second is False
    with pytest.raises(AssertionError):sup.amendment7_identity(g,l,a,launch=True)

@pytest.mark.parametrize("fault",["max6","wrong_repeat","rewritten_failure","duplicate_e7","wrong_physical","same_source"])
def test_amend7_rejects_identity_budget_or_failed_history_changes(fault):
    g,l,a=amend_state()
    if fault=="max6":l["physical_max"]=6
    elif fault=="wrong_repeat":g["repeat_of"]=FAILED_UUID
    elif fault=="rewritten_failure":l["attempts"][0]["status"]="COMPLETED"
    elif fault=="duplicate_e7":l["attempts"].append(dict(fixture_id="E7"))
    elif fault=="wrong_physical":l["physical_started"]=3
    else:g["source_commit"]="OLD"
    with pytest.raises((AssertionError,StopIteration,KeyError)):sup.amendment7_identity(g,l,a)


def completed_metadata(tmp_path,l,a):
    """Explicit stdlib-only metadata fixture, never native completion evidence."""
    index=len(l["attempts"])+1;entry=next(x for x in a["physical_schedule"]if x["physical_index"]==index)
    row=dict(entry,attempt_id="UNIT-COMPLETED-"+str(index),status="COMPLETED",child_pid=3100+index,supervisor_pid=2100+index,actual_process_exit_code=0,actual_supervisor_exit_code=0,actual_external_dispatcher_exit_code=0,supervisor_exit_authority="EXTERNAL_DISPATCHER_AFTER_EXIT")
    receipt=dict(schema="CM137_ROOT_ACTUAL_EXTERNAL_OS_EXIT_V1",external_dispatcher_pid=1100+index,actual_supervisor_pid=row["supervisor_pid"],actual_native_child_pid=row["child_pid"],authority="OBSERVED_EXEC_SESSION_COMPLETION_NOT_WRAPPER_GUESS",attempt_id=row["attempt_id"],fixture_id=row["fixture_id"],scenario=row["scenario"],repeat_of=row.get("repeat_of"),actual_native_child_os_exit_code=0,actual_supervisor_os_exit_code=0,actual_external_dispatcher_os_exit_code=0)
    p=tmp_path/("UNIT-NOT-NATIVE-OS-"+str(index)+".json");p.write_text(json.dumps(receipt));row["external_dispatcher_exit_receipt"]=dict(path=str(p),sha256=sup.sha(p))
    l["attempts"].append(row);l["physical_started"]=len(l["attempts"])
    return row

def test_amend7_remaining_e2_to_e5_schedule_no_extra_slot(tmp_path):
    g,l,a=amend_state()
    for physical in range(4,8):
        completed_metadata(tmp_path,l,a)
        case="E"+str(physical-2);g.update(fixture_id=case,scenario=case,repeat_of=None)
        sup.amendment7_identity(g,l,a)
    completed_metadata(tmp_path,l,a)
    with pytest.raises(AssertionError):sup.amendment7_identity(g,l,a)

@pytest.mark.parametrize("failed_physical",[3,4])
def test_any_new_failed_e7_to_e2_or_e2_to_e3_stops_before_claim_and_preserves_ledger(tmp_path,failed_physical):
    g,l,a=amend_state()
    for _ in range(3,failed_physical+1):row=completed_metadata(tmp_path,l,a)
    row["status"]="FAILED";row["actual_process_exit_code"]=1
    next_case="E"+str(failed_physical-1);g.update(fixture_id=next_case,scenario=next_case,repeat_of=None)
    path=tmp_path/"UNIT-ledger.json";path.write_text(json.dumps(l));before=path.read_bytes();memory=json.dumps(l,sort_keys=True)
    with pytest.raises(AssertionError,match="ANY_NEW_FAILURE_STOP"):sup.amendment7_identity(g,l,a)
    assert path.read_bytes()==before and json.dumps(l,sort_keys=True)==memory

@pytest.mark.parametrize("field",["actual_process_exit_code","actual_supervisor_exit_code","actual_external_dispatcher_exit_code"])
@pytest.mark.parametrize("value",[None,False,True,1,-1,"0"])
def test_completed_label_without_observed_integer_zero_is_blocked(tmp_path,field,value):
    g,l,a=amend_state();row=completed_metadata(tmp_path,l,a);row[field]=value
    g.update(fixture_id="E2",scenario="E2",repeat_of=None)
    with pytest.raises(AssertionError,match="OBSERVED_ZERO_OS_EXITS_REQUIRED"):sup.amendment7_identity(g,l,a)

@pytest.mark.parametrize("fault",["UNKNOWN","missing_child","wrong_schedule","unknown_authority","receipt_nonzero","receipt_pin","receipt_pid","receipt_schema","receipt_repeat"])
def test_unknown_incomplete_or_forged_post_amendment_history_blocks(tmp_path,fault):
    g,l,a=amend_state();row=completed_metadata(tmp_path,l,a);g.update(fixture_id="E2",scenario="E2",repeat_of=None)
    if fault=="UNKNOWN":row["status"]="UNKNOWN_REQUIRES_RECONCILIATION"
    elif fault=="missing_child":del row["actual_process_exit_code"]
    elif fault=="wrong_schedule":row["fixture_id"]="E4"
    elif fault=="unknown_authority":row["supervisor_exit_authority"]="GUESSED"
    else:
        p=Path(row["external_dispatcher_exit_receipt"]["path"]);receipt=json.loads(p.read_text());receipt["actual_native_child_os_exit_code"]=1
        if fault=="receipt_pid":receipt["actual_native_child_os_exit_code"]=0;receipt["actual_native_child_pid"]+=1
        if fault=="receipt_schema":receipt["actual_native_child_os_exit_code"]=0;receipt["schema"]="UNKNOWN"
        if fault=="receipt_repeat":receipt["actual_native_child_os_exit_code"]=0;receipt["repeat_of"]="OTHER"
        p.write_text(json.dumps(receipt))
        if fault!="receipt_pin":row["external_dispatcher_exit_receipt"]["sha256"]=sup.sha(p)
    with pytest.raises(AssertionError):sup.amendment7_identity(g,l,a)
