"""Frozen-review counterexamples. No Engine/Strategy construction or financial run."""
from dataclasses import asdict,replace
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as N
import io,json,time,hashlib
import pytest
from coinmaster.research import cm2_batch as batch,cm2_runner as runner
from coinmaster.strategy.cm2_native import CM2Strategy
from coinmaster.strategy.cm2_order_contract import MODEL_ID,FRESH_NS
from test_cm2_reference_native_pure import order_boundary,collateral,config
from test_cm2_reference_policy_pure import hand_parent,split,fill,T0,DAY


@pytest.mark.parametrize('scope,reduce,expected',[
    ('SOL',True,True),('SOL',False,False),('BTC',True,False),('UNSCOPED',True,False)])
def test_known_btc_ro_independent_of_only_identified_sol_ack(scope,reduce,expected):
    f,b,t,sent=order_boundary();snapshot=f._snapshot(100)
    assets=frozenset({f.config.sol_id if scope=='SOL' else b.id}) if scope!='UNSCOPED' else frozenset()
    f._snapshot=lambda now:replace(snapshot,unknown_orders=True,unknown_order_assets=assets,data_known=False)
    f._admit=lambda *a:(_ for _ in ()).throw(AssertionError('UNKNOWN_GROWTH_MUST_NOT_ADMIT'))
    assert CM2Strategy._send(f,b.id,D('.1'),-1 if reduce else 1,'DRAIN' if reduce else 'ENTRY_IOC',100,t,reduce_only=reduce) is expected
    assert bool(sent) is expected
    if expected:assert sent[0].is_reduce_only


def test_unknown_sol_cannot_make_stale_btc_bbo_reducible():
    f,b,t,sent=order_boundary();snapshot=f._snapshot(100)
    f._snapshot=lambda now:replace(snapshot,unknown_orders=True,unknown_order_assets=frozenset({f.config.sol_id}))
    t.ts_event=100-FRESH_NS-1
    assert not CM2Strategy._send(f,b.id,D('.1'),-1,'DRAIN',100,t,reduce_only=True)
    assert not sent and f.pre_submit_gate_blocks[-1]['reason']=='BBO_NATIVE_CLOCK_AGE'


def test_actual_snapshot_retains_unknown_owner_asset_identity():
    f,b,sol,_,_,_,_=collateral(equity='10000',held='0')
    f._latest_marks[b].price=D(10000);f._position=lambda i:None
    f._owned={'sol-unacked':{'client_order_id':'sol-unacked','instrument_id':sol,'submit_ns':100,'acked':False}}
    f.cache.orders_open=lambda:[];f.cache.orders_inflight=lambda:[];f.cache.order=lambda oid:None
    snapshot=CM2Strategy._snapshot(f,100)
    assert snapshot.unknown_orders and snapshot.unknown_order_assets==frozenset({sol})
    external=N(client_order_id='btc-foreign',instrument_id=b,is_reduce_only=False)
    f.cache.orders_open=lambda:[external]
    assert CM2Strategy._snapshot(f,100).unknown_order_assets==frozenset({b,sol})


def terminal_fixture(p,*,level,decision_index,failed=False):
    now=T0+DAY+120_000_000_000
    info={'instrument_id':'BTC','purpose':'TP_IOC','parent_id':'hand','level':level,
        'accepted_retry':True,'decision_index':decision_index}
    f=N(reference=p,_owned={'tp':info},cache=N(order=lambda oid:N(is_closed=True)),clock=N(timestamp_ns=lambda:now),
        _queued_tp={},_needs_daily=False,_persist_checkpoint=lambda:None,_reconcile_drains=lambda now:None)
    f._queue_confirmed_targets=lambda ready:CM2Strategy._queue_confirmed_targets(f,ready)
    f.config=N(btc_id='BTC')
    event=N(client_order_id='tp',ts_event=now)
    return f,event


def test_partial_zero_ioc_cancel_preserves_actual_remaining_and_original_clock():
    p=hand_parent(side=-1,levels=(0,.01,.03),notional=10000);split(p);fill(p,'entry',100)
    ordinary=p.ordinary_tp_permissions('hand',decision_ns=T0+DAY+90_000_000_000,
        native_resting_levels=frozenset(),native_pending_levels=frozenset())
    permission=next(x for x in ordinary if x.level==0)
    fill(p,'actual-supplied-pure-tp',1,kind='TP',level=0)
    f,event=terminal_fixture(p,level=0,decision_index=permission.decision_index)
    CM2Strategy._terminal_event(f,event)
    retry=f._queued_tp[0]
    assert retry.conditional_ioc and retry.quantity==D('20.25')
    assert retry.decision_index==permission.decision_index==0
    assert retry.ready_ns==event.ts_event+60_000_000_000
    assert p.parent.tp_filled_lots[0]==100 and p.parent.ordinary_attempted_index[0]==0
    before=dict(f._queued_tp);CM2Strategy._terminal_event(f,event)
    assert f._queued_tp==before  # duplicate terminal cannot mint another right


def test_positive_zero_fill_terminal_uses_genuine_confirmed_plan_clock():
    p=hand_parent(notional=10000);split(p);fill(p,'entry',100)
    target=p.confirmed_targets('hand')[0]
    assert target.positive_ioc_candidate and target.decision_index==0
    f,event=terminal_fixture(p,level=target.level,decision_index=target.decision_index)
    CM2Strategy._terminal_event(f,event,failed=True)
    assert f._queued_tp[target.level].quantity==target.quantity
    assert f._queued_tp[target.level].decision_index==target.decision_index
    assert not p.parent.tp_filled_lots


def collector_record(tmp_path,stage='qualification'):
    output=tmp_path/'case';output.mkdir();ledger=tmp_path/'ledger.jsonl'
    request={'artifact_dir':str(output),'run_id':'SYNTHETIC_NO_NATIVE','stage':stage,'source_family':'CM2BTCREF'}
    entry={'run_id':request['run_id'],'stage':stage,'status':'STARTED'}
    log=io.StringIO();child=N(returncode=None)
    return (child,entry,output,time.monotonic(),{'native_child_pid':123},log,str(ledger),request),ledger


def test_actual_collector_os_zero_missing_raw_is_failed_durably(tmp_path):
    record,ledger=collector_record(tmp_path)
    code=batch.collect_child(123,0,N(ru_maxrss=1),record)
    terminal=json.loads((record[2]/'native-child-terminal.json').read_text())
    assert code==1 and record[0].returncode==0
    assert terminal['status']=='FAILED' and terminal['exit_code']==0 and terminal['collection_exit_code']==1
    assert terminal['failure_phase']=='POST_CHILD_PERSISTED_QUALIFICATION'
    assert terminal['error_type']=='FileNotFoundError'
    assert json.loads(ledger.read_text())['status']=='FAILED'


def test_actual_collector_calls_checker_once_before_complete(tmp_path,monkeypatch):
    record,ledger=collector_record(tmp_path);calls=[]
    def checked(request):
        assert not ledger.exists() and not (record[2]/'native-child-terminal.json').exists()
        calls.append(request);return {'test_only':'CALL_ORDER_SPY_NOT_FINANCIAL_QUALIFICATION'}
    monkeypatch.setattr(runner,'postchild_validation',checked)
    assert batch.collect_child(123,0,N(ru_maxrss=1),record)==0
    assert calls==[record[7]] and json.loads(ledger.read_text())['status']=='COMPLETED'


def test_nonzero_child_does_not_try_to_qualify(tmp_path,monkeypatch):
    record,ledger=collector_record(tmp_path);calls=[]
    monkeypatch.setattr(runner,'postchild_validation',lambda r:calls.append(r))
    assert batch.collect_child(123,2<<8,N(ru_maxrss=1),record)==2
    assert not calls and json.loads(ledger.read_text())['exit_code']==2


def test_engineering_missing_actual_result_never_completes(tmp_path):
    record,ledger=collector_record(tmp_path,stage='engineering')
    record[7]['fixture_id']='cm2-btc-reference-cycle-native-v1'
    assert batch.collect_child(123,0,N(ru_maxrss=1),record)==1
    assert json.loads(ledger.read_text())['status']=='FAILED'


def test_exact_per_case_shared_receipt_map_keeps_all_bindings(tmp_path):
    source_root=Path(runner.__file__).parents[1]
    paths=[source_root/name for name in ('strategy/cm2_reference_policy.py','domain/wave_overlay.py','strategy/cm2_policy.py',
        'strategy/cm2_native.py','strategy/cm2_execution.py','strategy/cm2_order_contract.py','strategy/cm2_checkpoint.py',
        'research/cm2_runner.py','research/cm2_committed_validation.py','research/native_baseline.py','research/cm2_batch.py',
        'research/cm2_funding_reader.py','research/minute_risk.py','research/paired_observer.py')]
    freeze=[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
    requests=[{'run_id':name,'stage':'qualification','source_family':'CM2BTCREF','policy':asdict(config()),
        'start_ns':1725148800000000000,'end_ns':1733011200000000000,'request_execution_model_id':MODEL_ID,
        'initial_active_seed':'10000','freeze_files':freeze} for name in ('CASE_A','CASE_B')]
    receipt={'status':'R2_RELEASED','stage':'qualification',**{k:True for k in ('source_config_data_binary_freeze',
        'independent_money_causality_review','own_stage_root_GO','fresh_resource_check','secretless_environment')},'case_bindings':{}}
    for r in requests:
        receipt['case_bindings'][r['run_id']]={'source_family':r['source_family'],'policy_sha256':batch.policy_digest(r['policy']),
            'request_content_sha256':batch.policy_digest(r)}
    for r in requests:assert runner.preflight(r,receipt).policy==config()
    receipt['case_bindings']['CASE_B']['request_content_sha256']='0'*64
    with pytest.raises(ValueError,match='EXACT_REQUEST_GO_BINDING'):runner.preflight(requests[1],receipt)
    # CASE_A remains bound, not globally downgraded or overwritten by B.
    assert runner.preflight(requests[0],receipt).policy==config()


def test_external_control_identity_is_not_a_duplicate_policy_salt():
    descriptor={'version':'reference-btc-only-public5b-v1','source_commit':'5b56f7d02e09d4495ac018ec1ce701f6f0dfb737',
        'prepared_kwargs_sha256':'a'*64}
    assert batch.policy_digest(descriptor)!=batch.policy_digest(asdict(config()))
    request={'stage':'qualification','source_family':'REFERENCE_BTC_ONLY','policy':{**descriptor,'salt':'not-allowed'},
        'prepared_control_kwargs_sha256':'a'*64,'start_ns':1725148800000000000,'end_ns':1733011200000000000,
        'request_execution_model_id':MODEL_ID}
    with pytest.raises(ValueError,match='EXTERNAL_POLICY_DESCRIPTOR'):runner.preflight(request,{'status':'R2_RELEASED','stage':'qualification',
        **{k:True for k in ('source_config_data_binary_freeze','independent_money_causality_review','own_stage_root_GO','fresh_resource_check','secretless_environment')}})


def test_c1_competing_owner_is_btc_scoped_not_sol_order_feedback():
    f,b,t,_=order_boundary();foreign=N(instrument_id=f.config.sol_id,client_order_id='foreign-sol')
    f._quotes={};f._queued_tp={};f.cache.orders_open=lambda:[foreign];f.cache.orders_inflight=lambda:[]
    assert CM2Strategy._btc_competing_owner(f) is False
    foreign.instrument_id=b.id
    assert CM2Strategy._btc_competing_owner(f) is True


def test_partial_positive_ioc_cancel_keeps_confirmed_gtc_before_retry():
    p=hand_parent(side=-1,notional=10000);split(p);fill(p,'entry',100)
    target=p.confirmed_targets('hand')[0];fill(p,'supplied-pure-partial',1,kind='TP',level=target.level)
    f,event=terminal_fixture(p,level=target.level,decision_index=target.decision_index)
    CM2Strategy._terminal_event(f,event)
    plan=f._queued_tp[target.level]
    assert plan.quantity==target.quantity-D(1) and not plan.conditional_ioc
    assert plan.ready_ns==event.ts_event+1  # confirmed GTC, not +1m conditional overwrite
    before=dict(f._queued_tp);CM2Strategy._terminal_event(f,event);assert f._queued_tp==before
