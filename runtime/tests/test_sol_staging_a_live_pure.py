"""A live profile/epoch/actual native wrapper SQLite proofs; engine count zero."""
import ast,json,hashlib
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as N
import pytest
from coinmaster.strategy import live_recovery as REAL
from coinmaster.ops.hl_live_epoch import LiveEpochRuntime
from coinmaster.ops.hl_live_profile import STAGING_A_INPUT_FLAGS,STAGING_A_RESEARCH_SOURCE,ACTUAL_INITIAL_CAPITAL_POLICY,staging_a_epoch_seed
from test_e4_c1_manage_only_pure import code
from test_e4_c1_input_bridge_pure import fresh_init_fixture

ROOT=Path(__file__).parents[1]/'coinmaster'

@pytest.mark.parametrize('position_first',[False,True])
@pytest.mark.parametrize('crash',[False,True])
def test_actual_native_wrapper_never_continues_before_sqlite_applied_commit(tmp_path,position_first,crash):
    from test_sol_staging_all_paths_pure import forced
    c=forced('REGIME',4000);s=c.s;Base=type(s)
    tree=ast.parse((ROOT/'strategy/live_recovery.py').read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='RecoverableWaveOverlayStrategy')
    names={'on_order_filled','_after_domain_fill','_staging_a_forced_child_ready','_terminal_submission'}
    body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
    env=dict(WaveOverlayStrategy=Base,Decimal=D,_KEY=REAL._KEY)
    node=ast.ClassDef(name='Live',bases=[ast.Name(id='WaveOverlayStrategy',ctx=ast.Load())],keywords=[],body=body,decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'actual_live_wrapper','exec'),env)
    s.__class__=env['Live'];s.__dict__.pop('_terminal_submission');s._input_readiness_preparation=False;s._active_c1_authorized=False
    runtime=LiveEpochRuntime(tmp_path/'actual.sqlite','owner',10**20);runtime.acquire();s._recovery_runtime=runtime
    s.on_save=lambda:{REAL._KEY:json.dumps({'child':str(s._staging_a_forced_children.get(c.sol.id)),'seen':sorted(s._seen_trade_ids)}).encode()}
    def reserve(order):
        assert runtime.record_submission(client_order_id=str(order.client_order_id),intent_id='forced',episode_id='e',
            action='CLOSE_ALL',instrument_id=str(order.instrument_id),quantity=str(order.quantity),reduce_only=True)
    reserve(c.sent[0])
    original=s.submit_order
    def submit(order):
        # This callback is the actual next native API boundary in the fixture.
        assert runtime.has_applied_fill(str(event.trade_id))
        assert not runtime.db.in_transaction and runtime.strategy_checkpoint() is not None
        reserve(order);original(order)
    s.submit_order=submit
    def record(event):
        runtime.record_native_fill(trade_id=str(event.trade_id),native_event_id=str(event.id),
            client_order_id=str(event.client_order_id),venue_order_id=str(event.venue_order_id),
            instrument_id=str(event.instrument_id),order_side=str(event.order_side),quantity=str(event.last_qty),
            price=str(event.last_px),commission_amount=str(event.commission.as_decimal()),commission_currency=str(event.commission.currency),
            liquidity_side=str(event.liquidity_side),ts_event_ns=event.ts_event,ts_init_ns=event.ts_init)
    s._record_native_fill=record
    order=c.sent[0];event=c.fill(order,ts=100);order.apply(event)
    if crash:
        runtime.db.execute("CREATE TRIGGER fail_checkpoint BEFORE INSERT ON paper_strategy_checkpoint WHEN EXISTS(SELECT 1 FROM paper_recovered_fills) BEGIN SELECT RAISE(ABORT,'CRASH_BEFORE_DURABLE_COMMIT'); END")
        runtime.db.commit()
    try:
        if position_first:
            c.position.apply(event);s.on_position_event(c.event(100))
            assert len(c.sent)==1 and not runtime.has_applied_fill(str(event.trade_id))
        if crash:
            with pytest.raises(RuntimeError,match='RECOVERY_FILL_CHECKPOINT_CONFLICT'):s.on_order_filled(event)
        else:s.on_order_filled(event)
        if not position_first:c.position.apply(event);s.on_position_event(c.event(100))
        assert len(c.sent)==(1 if crash else 2)
        if crash:assert s.recovery_confirmed is False
        assert runtime.has_applied_fill(str(event.trade_id)) is (not crash)
        before=runtime.native_revision();s.on_order_filled(event);s.on_position_event(c.event(100))
        assert len(c.sent)==(1 if crash else 2) and runtime.native_revision()==before
        assert c.position.quantity.as_decimal()==3000
        assert runtime.db.execute('SELECT COUNT(*) FROM paper_native_fill_details').fetchone()[0]==1
        if not crash:
            assert c.sent[1].quantity.as_decimal()==1000 and c.sent[1].is_reduce_only
    finally:runtime.close()
    if crash:
        reopened=LiveEpochRuntime(tmp_path/'actual.sqlite','owner',10**20);reopened.acquire()
        try:assert not reopened.has_applied_fill(str(event.trade_id))
        finally:reopened.close()

@pytest.mark.parametrize('amount',['61.25','81.84','108.33'])
def test_actual_init_marker_fixes_a_seed_cap_and_restart_not_current_nav(code,tmp_path,amount):
    s,r,view,now=fresh_init_fixture(code,tmp_path)
    s.config.research_sol_capital_staging_a=True;s.config.research_sol_market_budget_b=False
    s.config.active_seed=D(10000);s._staging_a_initial_seed=D(10000);s._staging_a_forced_children={}
    s._domain.config=s._candidate;s.config.live_initial_capital_policy=ACTUAL_INITIAL_CAPITAL_POLICY
    s._active_c1_authorized=True
    account=s.cache.account_for_venue(s.config.btc_id.venue);account.balance_total=lambda c:N(as_decimal=lambda:D(amount))
    view=replace(view,equity=D(amount),raw_usd=D(0),free_collateral=D(amount))
    profile=dict(strategy_flags=STAGING_A_INPUT_FLAGS)
    try:
        s.initialize_clean_flat_c1_epoch(view,intent='INITIALIZE_FRESH_C1_EPOCH',now_ns=now,history_anchor_ms=0,
            cashflow_page=dict(rows=[],start_ms=0,end_ms=1,expected_cursor=None,complete=True))
        assert r.c1_initialization()['initial_equity']==amount
        assert s._staging_a_initial_seed==D(amount) and s._candidate.max_parent_notional==float(D(amount)*3000)
        checkpoint=r.strategy_checkpoint()[0]
        assert json.loads(checkpoint)['state']['_staging_a_initial_seed']==REAL._encode(D(amount))
        r.close();r=code.Runtime(tmp_path/'fresh.sqlite','fresh-owner',10**20);r.acquire()
        assert staging_a_epoch_seed(profile,r,D(999999))==D(amount)
        cfg=N(**vars(s.config));cfg.active_seed=D(amount)
        restored=code.Strategy(cfg);restored._candidate=s._candidate;restored._domain.config=s._candidate
        restored.on_load({REAL._KEY:checkpoint})
        assert restored._staging_a_initial_seed==D(amount) and restored._staging_a_forced_children=={}
        assert not restored.recovery_confirmed
        wrong=N(**vars(s.config));wrong.active_seed=D(amount)+1
        other=code.Strategy(wrong);other._candidate=s._candidate
        with pytest.raises(ValueError,match='STAGING_A_INITIAL_EPOCH_SEED_MISMATCH'):other.on_load({REAL._KEY:checkpoint})
    finally:r.close()

def test_a_profile_exact_flags_source_and_additional_helper_pin(tmp_path):
    from coinmaster.ops import hl_live_profile as p
    from coinmaster.domain.wave_overlay import Candidate
    from test_e4_c1_active_authorization_pure import profile_metadata
    from coinmaster.ops.stage_g_config import candidate_content_hash
    base=Candidate();pins={}
    names=('strategy/residual_recovery.py','strategy/wave_overlay.py','strategy/next_band.py','strategy/hedge_band.py',
        'domain/wave_overlay.py','strategy/c1_inputs.py','ops/hl_unified_account.py','ops/hl_unified_instruments.py',
        'ops/hl_live_execution.py','ops/hl_info_receipt.py','ops/hl_live_money.py','strategy/sol_capital_staging.py',
        'ops/venue_data.py','ops/hl_closed_bars.py','strategy/live_recovery.py')
    for name in names:
        path=tmp_path/'coinmaster'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((ROOT/name).read_bytes())
        pins['coinmaster/'+name]=hashlib.sha256(path.read_bytes()).hexdigest()
    profile=dict(schema='coinmaster-live-selected-c1-v1',profile_id='E4_C1_ACTIVE_SELECTED',initial_capital_policy=ACTUAL_INITIAL_CAPITAL_POLICY,
        candidate_sha256=candidate_content_hash(base),research_source=STAGING_A_RESEARCH_SOURCE,
        economic_config_sha256='61d8c8ae857b8830a31ae6a6bf679098d3eb27fbe456481b94731a0a6ca64e8d',strategy_flags=STAGING_A_INPUT_FLAGS,
        manage_only_readiness=False,input_readiness=True,live_order_capability=True,source_pins=pins,deposit_protection_percent=55,
        retained_equity_floor_fraction='0.45',initialization_intent=None,account_mode='unifiedAccount',
        equity_basis='HYPERLIQUID_UNIFIED_SPOT_USDC_REPORTED_TOTAL_V1',owner_start_required=True)
    assert p._validate_input_readiness_profile(tmp_path,profile,base)['strategy_flags']==STAGING_A_INPUT_FLAGS
    for change in ({'economic_config_sha256':'a2c7d88b5aff67399c0db849585bc5ad3625ce4e82068b3e29254d355c119253'},
                   {'research_source':'fccd60c01e8cae5e8258748b046f43f88a16bb79'},
                   {'strategy_flags':{**STAGING_A_INPUT_FLAGS,'research_sol_market_budget_b':True}},
                   {'strategy_flags':{**STAGING_A_INPUT_FLAGS,'research_sol_market_budget_b':0}},
                   {'source_pins':{k:v for k,v in pins.items() if not k.endswith('sol_capital_staging.py')}},
                   {'deposit_protection_percent':50}):
        with pytest.raises(RuntimeError):p._validate_input_readiness_profile(tmp_path,{**profile,**change},base)

def test_a_helper_and_domain_economics_identical_to_frozen_research_source():
    import subprocess
    work=Path(__file__).resolve().parents[2]
    for name in ('strategy/sol_capital_staging.py','domain/wave_overlay.py'):
        original=subprocess.check_output(['git','show',STAGING_A_RESEARCH_SOURCE+':runtime/coinmaster/'+name],cwd=work)
        assert (ROOT/name).read_bytes()==original


def test_staging_child_context_native_ids_roundtrips_without_recovery_authority():
    from nautilus_trader.model.identifiers import InstrumentId,ClientOrderId,PositionId
    child={InstrumentId.from_str('SOL.TEST'):dict(order_id=ClientOrderId('child'),position_id=PositionId('owned'),
        before_qty=D(3000),was_long=True,quote_ns=123)}
    assert REAL._decode(REAL._encode(child))==child


def test_unknown_epoch_marker_never_falls_back_to_restart_equity():
    profile=dict(strategy_flags=STAGING_A_INPUT_FLAGS)
    for marker in ({},{'initial_equity':'NaN'},{'initial_equity':'0'}):
        with pytest.raises((RuntimeError,ValueError)):
            staging_a_epoch_seed(profile,N(c1_initialization=lambda:marker,strategy_checkpoint=lambda:None),D(999))
    with pytest.raises(RuntimeError):
        staging_a_epoch_seed(profile,N(c1_initialization=lambda:None,strategy_checkpoint=lambda:b'unknown'),D(999))

def test_actual_child_uses_bound_epoch_seed_even_when_constructor_seed_differed():
    from test_sol_capital_staging_a_pure import dispatch
    c=dispatch('10000');s=c.s;s._staging_a_initial_seed=D('81.84')
    second=s._domain._intent(c.ep,'SOL_ADD',-1,0,requested_notional=200000)
    s._submit_intent(second,100,100,None,0,ts_now=100)
    assert c.sent[-1].quantity.as_decimal()==D('8.18')
    assert s.config.active_seed==10000

def test_actual_zero_fill_cancel_ack_waits_sqlite_terminal_then_reuses_fresh_quote(tmp_path):
    from test_sol_staging_all_paths_pure import forced
    from nautilus_trader.test_kit.stubs.events import TestEventStubs
    from coinmaster.research.native_fixture import instrument_quote
    c=forced('REGIME',4000);s=c.s;Base=type(s)
    cls=next(n for n in ast.parse((ROOT/'strategy/live_recovery.py').read_text()).body if isinstance(n,ast.ClassDef) and n.name=='RecoverableWaveOverlayStrategy')
    names={'on_order_canceled','_terminal_submission','_staging_a_forced_child_ready'}
    body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
    node=ast.ClassDef(name='Live',bases=[ast.Name(id='WaveOverlayStrategy',ctx=ast.Load())],keywords=[],body=body,decorator_list=[])
    env=dict(WaveOverlayStrategy=Base,Decimal=D,_KEY=REAL._KEY)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'actual_live_cancel_wrapper','exec'),env)
    s.__class__=env['Live'];s.__dict__.pop('_terminal_submission')
    r=LiveEpochRuntime(tmp_path/'cancel.sqlite','owner',10**20);r.acquire();s._recovery_runtime=r
    s.on_save=lambda:{REAL._KEY:b'{"native_cancel_checkpoint":true}'}
    first=c.sent[0]
    r.record_submission(client_order_id=str(first.client_order_id),intent_id='force',episode_id='e',action='CLOSE_ALL',
        instrument_id=str(c.sol.id),quantity=str(first.quantity),reduce_only=True)
    original=s.submit_order
    def submit(order):
        assert r.db.execute('SELECT state FROM paper_intents WHERE client_order_id=?',(str(first.client_order_id),)).fetchone()[0]=='TERMINAL'
        assert not r.db.in_transaction and r.strategy_checkpoint()[0]==s.on_save()[REAL._KEY]
        original(order)
    s.submit_order=submit
    event=TestEventStubs.order_canceled(first,ts_event=101);first.apply(event)
    c.latest[c.sol.id]=instrument_quote(c.sol,'100','100',101)
    try:
        assert not s._staging_a_forced_child_ready(c.sol.id,101)
        assert len(c.sent)==1
        s.on_order_canceled(event)
        assert len(c.sent)==2 and c.sent[1].quantity.as_decimal()==1000
        assert c.position.quantity.as_decimal()==4000 and not r.applied_fill_ids()
        s.on_order_canceled(event)
        assert len(c.sent)==2
    finally:r.close()
