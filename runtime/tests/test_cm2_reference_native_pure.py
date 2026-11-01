"""Actual adapter methods and real order objects; NO native Strategy/Engine instances."""
from dataclasses import asdict,replace
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as N
import json
import pytest
from coinmaster.strategy.cm2_native import CM2Strategy
from coinmaster.strategy.cm2_execution import NativeExposure,SafetyState,ExecutionLimits
from coinmaster.strategy.cm2_reference_policy import ReferenceConfig,ReferenceFlags,selected_btc_candidate
from coinmaster.strategy.cm2_order_contract import FRESH_NS,MODEL_ID
from coinmaster.research import cm2_runner as runner


def config():return ReferenceConfig('cm2-btc-reference-v1',selected_btc_candidate(),ReferenceFlags(True,True))


class ID(str):venue='V'


def collateral(equity='100',held='3000',locked='0',order_im='0',position_mm='0'):
    btc,sol=ID('BTC'),ID('SOL');prices={btc:True,sol:False}
    current=[NativeExposure(D(equity),D(held),D(0),D(1),D(0),False,True,prices)]
    balances=N(total=D(equity),locked=D(locked));margins={btc:(D(order_im),D(position_mm)),sol:(D(0),D(0))}
    money=lambda x:N(currency='USDC',as_decimal=lambda:x)
    account=N(id='account',base_currency='USDC',balance_total=lambda c:money(balances.total),
        balance_free=lambda c:money(balances.total-balances.locked),balance_locked=lambda c:money(balances.locked),
        margin_init=lambda i:money(margins[i][0]),margin_maint=lambda i:money(margins[i][1]),
        total_margin_init=lambda c:money(sum((v[0] for v in margins.values()),D(0))),
        total_margin_maint=lambda c:money(sum((v[1] for v in margins.values()),D(0))))
    calls=[]
    def snapshot(now):calls.append(now);return current[0]
    fake=N(clock=N(timestamp_ns=lambda:100),safety=SafetyState(),reference=N(parent=None,c1=None),
        config=N(policy=config(),btc_id=btc,sol_id=sol,exit_fee_rate=D('.000432'),btc_step=D('.01'),
            active_seed=D(10000),limits=ExecutionLimits(D('1e100')),
            margin_policy=N(margin_for=lambda i,q,t:(q/40,q/80,D(1)))),
        cache=N(account_for_venue=lambda v:account,instrument=lambda i:N(settlement_currency='USDC')),
        _snapshot=snapshot,_latest_marks={btc:N(ts_event=100)},_orders=lambda i:[],pre_submit_gate_blocks=[])
    return fake,btc,sol,current,balances,margins,calls


def admit(f,btc,q):return CM2Strategy._admit(f,btc,D(q),D(1),None,-999)


def test_fresh_snapshot_and_aggregate_held_im_without_native_lock_credit():
    f,b,_,s,balances,_,calls=collateral()
    assert not admit(f,b,2000)
    assert f.pre_submit_gate_blocks[-1]['reason']=='NATIVE_AGGREGATE_COLLATERAL'
    assert calls==[100]
    s[0]=replace(s[0],equity=D(200),btc_qty=D(0));balances.total=D(200)
    assert admit(f,b,2000)


def test_inactive_sol_mark_not_required_but_reachable_sol_is_unknown():
    f,b,sol,s,_,_,_=collateral(equity='1000',held='0')
    assert admit(f,b,1)
    s[0]=replace(s[0],sol_qty=D(1))
    assert not admit(f,b,1)
    assert f.pre_submit_gate_blocks[-1]['reason']=='REACHABLE_COLLATERAL_MARK_UNKNOWN'


def test_parent_reserves_full_future_btc_before_subordinate_sol_growth():
    f,b,sol,s,_,_,_=collateral(equity='100',held='0')
    s[0]=replace(s[0],sol_mark=D(1),price_known={b:True,sol:True})
    assert admit(f,sol,1)
    f.reference.parent=N(selected_quantity=D(5000),filled_quantity=D(0),split_terminal=False)
    assert not admit(f,sol,1)
    assert f.pre_submit_gate_blocks[-1]['reason'] in ('NATIVE_FREE_MARGIN','NATIVE_AGGREGATE_COLLATERAL')
    f.reference.parent=None;f.reference.c1=N(revoked=False,credit=500000)
    assert not admit(f,sol,1)


def test_aggregate_fee_exact_boundary_and_one_satoshi_failure():
    needed=D(125)+D(2000)*D('.000432')
    f,b,sol,s,balances,_,_=collateral(equity=str(needed),held='1500')
    s[0]=replace(s[0],sol_qty=D(1500),sol_mark=D(1),price_known={b:True,sol:True})
    assert admit(f,b,2000)
    s[0]=replace(s[0],equity=needed-D('.00000001'));balances.total=s[0].equity
    assert not admit(f,b,2000)
    assert f.pre_submit_gate_blocks[-1]['reason']=='NATIVE_AGGREGATE_COLLATERAL'


@pytest.mark.parametrize('kind',['currency','balance','margin','fee','unknown','ownmark'])
def test_unknown_collateral_cannot_authorize_growth(kind):
    f,b,_,s,_,margins,_=collateral(equity='1000',held='0')
    if kind=='currency':f.cache.instrument=lambda i:N(settlement_currency='OTHER')
    if kind=='balance':f.cache.account_for_venue('V').balance_locked=lambda c:N(currency='OTHER',as_decimal=lambda:D(0))
    if kind=='margin':margins[b]=(D(1),D(0))
    if kind=='fee':f.config.exit_fee_rate=D('NaN')
    if kind=='unknown':s[0]=replace(s[0],unknown_orders=True)
    if kind=='ownmark':s[0]=replace(s[0],price_known={})
    assert not admit(f,b,1)


def order_boundary(qty=D(1)):
    from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
    from nautilus_trader.common.factories import OrderFactory
    from nautilus_trader.common.component import TestClock
    from nautilus_trader.model.identifiers import TraderId,StrategyId
    profile=load_current_hl_diagnostic(Path(__file__).parent/'fixtures/hl-current-20261029')
    btc,sol=profile.instruments;now=100;sent=[]
    money=lambda x:N(as_decimal=lambda:x)
    quote=N(ts_event=now,bid_price=money(D(10000)),ask_price=money(D(10020)))
    snap=NativeExposure(D('1e9'),qty,D(0),D(10000),D(0),False,True,{btc.id:True,sol.id:False})
    f=N(config=N(policy=config(),btc_id=btc.id,sol_id=sol.id,btc_step=btc.size_increment.as_decimal(),
        limits=ExecutionLimits(D('1e100')),margin_policy=profile.margin_policy(FRESH_NS)),
        reference=N(parent=None,signals=[]),cache=N(instrument=lambda i:btc if i==btc.id else sol),
        _snapshot=lambda t:snap,_orders=lambda i:[],_owned={},_order_audit={},target_blockers={},
        pre_submit_gate_blocks=[],_admit=lambda *a:True,_persist_checkpoint=lambda:None,
        _chain_audit=lambda *a:None,submit_order=sent.append,
        order_factory=OrderFactory(TraderId('TEST-001'),StrategyId('TEST-001'),TestClock()))
    f._contract_spec=lambda i,o:CM2Strategy._contract_spec(f,i,o)
    f._reference_limit=lambda i,r:CM2Strategy._reference_limit(f,i,r)
    return f,btc,quote,sent


def test_real_native_gtc_half_even_and_market_ioc_have_distinct_terms():
    f,b,t,sent=order_boundary()
    assert CM2Strategy._send(f,b.id,D('.1'),1,'ENTRY_DISCOUNT',100,t,raw_limit=D('10000.5'))
    limit=sent[-1]
    assert limit.price.as_decimal()==D(10000)  # half-even; not BUY ceil
    assert limit.time_in_force.name=='GTC' and limit.is_post_only
    assert CM2Strategy._send(f,b.id,D('.1'),-1,'TP_IOC',100,t,reduce_only=True)
    market=sent[-1]
    assert market.time_in_force.name=='IOC' and market.is_reduce_only and market.order_type.name=='MARKET'
    assert json.loads(json.dumps(f._order_audit))


def test_actual_ro_leaves_and_venue_cap_prevent_overcommit():
    f,b,t,sent=order_boundary(D(500))
    f._orders=lambda i:[N(is_reduce_only=True,leaves_qty=N(as_decimal=lambda:D(200)))]
    f._admit=lambda *a:(_ for _ in ()).throw(AssertionError('RO_MUST_NOT_CALL_GROWTH'))
    assert CM2Strategy._send(f,b.id,D(500),-1,'DRAIN',100,t,reduce_only=True)
    assert sent[-1].quantity.as_decimal()<=D(300)
    assert sent[-1].quantity.as_decimal()*D(10020)<=D(30000000)


def test_final_factory_mutation_rejected_before_owner_or_submission():
    f,b,t,sent=order_boundary();real=f.order_factory
    def bad(**kwargs):
        kwargs['reduce_only']=False
        return real.market(**kwargs)
    f.order_factory=N(market=bad)
    assert not CM2Strategy._send(f,b.id,D('.1'),-1,'TP_IOC',100,t,reduce_only=True)
    assert not sent and not f._owned and not f._order_audit
    assert 'FINAL_NATIVE_REQUEST_MISMATCH' in f.pre_submit_gate_blocks[-1]['reason']


def test_btc_economic_flat_releases_only_btc_scope_while_sol_drains():
    b,sol=ID('BTC'),ID('SOL');confirmed=[]
    p=N(id='p');ref=N(parent=p,confirm_btc_close=lambda *a,**k:confirmed.append((a,k)))
    f=N(id='x',reference=ref,config=N(btc_id=b,sol_id=sol),_owned={},_queued_tp={1:'old'},
        _drain={'BTC_ECONOMIC':{'state':{'scoped_zero_ids':[str(b)]},'parent_id':'p','reason':'REGIME'},
                'SOL_SUBORDINATE':{'state':{'scoped_zero_ids':[str(sol)]},'parent_id':'p','reason':'SOL'}},
        _position=lambda i:None if i==b else N(),_orders=lambda i:[],clock=N(timer_names=[]),drain_audit=[])
    CM2Strategy._reconcile_drains(f,100)
    assert confirmed and 'BTC_ECONOMIC' not in f._drain and 'SOL_SUBORDINATE' in f._drain
    assert CM2Strategy._scope_for(f,b) is None and f._needs_daily
    f._drain['GLOBAL']={'state':{'scoped_zero_ids':[str(b),str(sol)]}}
    assert CM2Strategy._scope_for(f,b)=='GLOBAL'


def test_total_actual_equity_sizing_and_attribution_audit_do_not_create_sleeve():
    f,b,sol,s,balances,_,_=collateral(equity='12345',held='0')
    f.config.funding_reader=lambda i:D(0)
    f.config.funding_reader.journal=object()
    f.reference.note_btc_funding=lambda x:None;f.reference.btc_revision=1
    f._position=lambda i:None
    account=f.cache.account_for_venue('V')
    f.portfolio=N(realized_pnl=lambda *a,**k:N(currency='USDC',as_decimal=lambda:D(0)))
    result=CM2Strategy._native_btc_capital(f,100)
    assert result['equity']==D(12345) and result['btc_attribution_audit']['status']=='DEFERRED_TO_NATIVE_TERMINAL_RECONCILIATION'
    assert result['btc_attribution_audit']['trading_input'] is False
    f.config.funding_reader.journal=None
    with pytest.raises(ValueError,match='FUNDING_UNKNOWN'):CM2Strategy._native_btc_capital(f,100)


def test_money_receipt_strictly_later_no_extra_minute():
    observed=[];base=dict(equity=D(100),open_pnl=D(-10),position_id='p',position_open_ns=1,
        native_qty=D(1),funding=D(0),revision=2)
    f=N(_btc_source_frame={**base,'source_ns':100},_native_btc_capital=lambda now:base,
        reference=N(observe_committed_btc=lambda **k:observed.append(k)),_btc_competing_owner=lambda:False)
    CM2Strategy._finalize_btc_receipt(f,100);assert not observed
    CM2Strategy._finalize_btc_receipt(f,101);assert observed[0]['receipt_ns']==101


def test_new_strict_config_and_explicit_interval_reject_old_route():
    payload=asdict(config());assert runner.reference_config(payload)==config()
    payload['flags']['c1_btc_postcut_d1']=False
    with pytest.raises(ValueError):runner.reference_config(payload)
    with pytest.raises(ValueError):runner.reference_config({'version':'cm2-v2'})
    request={'start_ns':1725148800000000000,'end_ns':1733011200000000000,'request_execution_model_id':MODEL_ID}
    assert runner.request_interval(request)==(request['start_ns'],request['end_ns'])
    request['start_ns']+=1
    with pytest.raises(ValueError):runner.request_interval(request)


def test_actual_fixture_pre_engine_boundary_and_plan(tmp_path,monkeypatch):
    from coinmaster.research import cm2_reference_fixture as fixture
    plan=fixture.prepare_plan();assert len(plan['seed'])==730 and plan['levels'][0]==0
    request={'fixture_id':fixture.FIXTURE_ID,'policy':asdict(config()),'start_ns':fixture.START_NS,
        'end_ns':fixture.END_NS,'current_hl_execution_inputs':str(Path(__file__).parent/'fixtures/hl-current-20261029')}
    monkeypatch.setattr(CM2Strategy,'__init__',lambda *a,**k:(_ for _ in ()).throw(AssertionError('STRATEGY_CTOR_FORBIDDEN')))
    proof=runner.fixture_api_boundary_probe(request,tmp_path/'probe')
    assert proof['native_engine_constructions']==0 and proof['boundary_calls']==1
    assert fixture.fixture_protocol()['missing_component_policy'].startswith('NOT_OBSERVED_IS_NOT_PASS')


def test_actual_h4_subclass_dispatch_does_not_become_daily_input():
    from coinmaster.strategy.next_band import NextClosedBar
    from nautilus_trader.model.identifiers import InstrumentId
    b=InstrumentId.from_str('BTCUSDT.HYPERLIQUID');accepted=[]
    ref=N(parent=None,_wait_regime=False,signals=[],accept_closed_btc_h4=lambda **kw:accepted.append(kw))
    f=N(clock=N(timestamp_ns=lambda:4*3_600_000_000_000),reference=ref,config=N(btc_id=b,sol_id=None),
        _finalize_btc_receipt=lambda now:None,_days_pending={})
    item=NextClosedBar(b,4,D(100),D(102),D(98),D(101),4*3_600_000_000_000)
    CM2Strategy.on_data(f,item)
    assert len(accepted)==1 and not f._days_pending
    assert accepted[0]['open_ns']==0


def test_snapshot_native_shared_equity_inactive_sol_and_held_unknown_sol():
    f,b,sol,_,balances,_,_=collateral(equity='10000',held='0')
    positions=[];account=f.cache.account_for_venue('V')
    f._owned={};f.cache.orders_open=lambda:[];f.cache.orders_inflight=lambda:[]
    f._position=lambda iid:next((p for p in positions if p.instrument_id==iid),None)
    f.cache.instrument=lambda i:N(make_price=lambda p:p)
    f._latest_marks[b].price=D(10000)
    assert CM2Strategy._snapshot(f,100).data_known  # flat SOL needs no fake mark
    p=N(instrument_id=sol,quantity=N(as_decimal=lambda:D(2)),is_long=True,
        unrealized_pnl=lambda price:N(currency='USDC',as_decimal=lambda:D(234)))
    positions.append(p)
    unknown=CM2Strategy._snapshot(f,100)
    assert not unknown.data_known and not unknown.price_known[sol]
    f._latest_marks[sol]=N(price=D(150),ts_event=100);f._latest_marks[b].price=D(10000)
    shared=CM2Strategy._snapshot(f,100)
    assert shared.data_known and shared.equity==D(10234)


def test_worker_routes_use_separate_frozen_execution_root_and_absolute_bootstrap(tmp_path):
    request={'source_family':'REFERENCE_BTC_ONLY','artifact_dir':str(tmp_path/'case'),
        '_request_path':str(tmp_path/'request.json'),'orchestrator_source_root':str(Path(runner.__file__).parents[3]),
        'execution_source_root':str(tmp_path/'frozen5b')}
    argv,env,cwd=runner.worker_process_spec(request,7,'digest')
    assert '--worker' in argv and '-m' not in argv
    assert Path(argv[3]).is_absolute() and argv[3].endswith('cm2_reference_control_worker.py')
    assert env['PYTHONPATH']==str(tmp_path/'frozen5b/runtime')
    assert set(env).isdisjoint({'AWS_SECRET_ACCESS_KEY','SSH_AUTH_SOCK'})
    request['source_family']='CM2BTCREF'
    argv,env,_=runner.worker_process_spec(request,7,'digest')
    assert 'coinmaster.research.cm2_runner' in argv and env['PYTHONPATH']==str(Path(runner.__file__).parents[2])
    request['source_family']='legacy'
    with pytest.raises(ValueError,match='SOURCE_FAMILY'):runner.worker_process_spec(request,7,'digest')


def test_preflight_rejects_unbound_old_go_before_any_native_import():
    request={'source_family':'CM2BTCREF','policy':asdict(config()),'stage':'qualification',
        'run_id':'SYNTHETIC_NO_NATIVE','start_ns':1725148800000000000,'end_ns':1733011200000000000,'request_execution_model_id':MODEL_ID}
    receipt={'status':'R2_RELEASED','stage':'qualification',**{k:True for k in
        ('source_config_data_binary_freeze','independent_money_causality_review','own_stage_root_GO','fresh_resource_check','secretless_environment')}}
    with pytest.raises(ValueError,match='EXACT_REQUEST_GO_BINDING'):runner.preflight(request,receipt)


@pytest.mark.parametrize('field,value',[('sol_overlay_enabled',0),('ema_period',34.0),('max_parent_notional',30000000)])
def test_frozen_candidate_rejects_python_equal_wrong_types(field,value):
    from dataclasses import replace
    with pytest.raises(ValueError):ReferenceConfig('cm2-btc-reference-v1',replace(selected_btc_candidate(),**{field:value}),ReferenceFlags(True,True))


def test_actual_runner_api_signature_has_new_single_owner_kwargs_only(tmp_path):
    import inspect
    from coinmaster.research.native_baseline import run_native_diagnostic
    request={'policy':asdict(config()),'data_root':str(tmp_path),'artifact_dir':str(tmp_path/'case'),
        'current_hl_execution_inputs':str(tmp_path/'profile'),'run_id':'SYNTHETIC_API_NO_ENGINE','initial_active_seed':'10000',
        'start_ns':1725148800000000000,'end_ns':1733011200000000000,'request_execution_model_id':MODEL_ID}
    kwargs=runner.full_native_kwargs(request)
    inspect.signature(run_native_diagnostic).bind(**kwargs)
    assert kwargs['research_cm2'].policy==config() and kwargs['candidate'].sol_overlay_enabled is False
    assert kwargs['trading_end_ms']==1733011200000 and kwargs['warmup_start_ms']==1662076800000
    assert all(not key.startswith('research_btc_') and not key.startswith('research_sol_') for key in kwargs)


def test_existing_durable_cas_idempotence_conflict_and_reopen(tmp_path):
    import sqlite3
    from coinmaster.strategy.cm2_checkpoint import NativeCheckpointStore
    path=tmp_path/'synthetic-checkpoint.sqlite';db=sqlite3.connect(path);store=NativeCheckpointStore(N(db=db))
    assert store.persist(b'one',0)==1;changes=db.total_changes
    assert store.persist(b'one',1)==1 and db.total_changes==changes
    assert store.persist(b'two',0) is None and store.read()==(1,b'one')
    assert store.persist(b'two',1)==2;db.close();db=sqlite3.connect(path)
    assert NativeCheckpointStore(N(db=db)).read()==(2,b'two');db.close()


def test_existing_durable_integrity_and_foreign_transaction_fail_closed():
    import sqlite3
    from coinmaster.strategy.cm2_checkpoint import NativeCheckpointStore
    db=sqlite3.connect(':memory:');store=NativeCheckpointStore(N(db=db));store.persist(b'one',0)
    db.execute('UPDATE cm2_domain_checkpoint SET body=?',(b'corrupt',));db.commit()
    with pytest.raises(ValueError,match='INTEGRITY'):store.read()
    db.execute('BEGIN')
    with pytest.raises(ValueError,match='FOREIGN_TRANSACTION'):store.persist(b'two',1)
    db.rollback();db.close()
