"""No BacktestEngine: exact family plus immutable original-second arithmetic."""
from decimal import Decimal as D
from inspect import signature
from pathlib import Path
import pytest
from coinmaster.research.a0_family import build_a0_kwargs, validate_native_a0
from coinmaster.research.native_baseline import run_native_diagnostic
from coinmaster.research.registered_control import native_kwargs_json_roundtrip
from coinmaster.strategy.a0_rights import release_cap

@pytest.mark.parametrize('variant',['R2_OFF','R2_C0','R2_A0'])
def test_actual_kwargs_exact_roundtrip(variant):
    kwargs=build_a0_kwargs(Path('.'),Path('out'),variant,())
    payload,restored=native_kwargs_json_roundtrip(kwargs)
    assert restored==kwargs
    bound=signature(run_native_diagnostic).bind(**restored);bound.apply_defaults()
    validate_native_a0(bound.arguments)
    for name,value in [('research_btc_q_mode','CLEAN_Q'),('research_paired_prefix','B2'),('research_btc_split_discount','0.006'),('research_paired_policy',False),('research_registered_control','R2')]:
        bad=dict(bound.arguments);bad[name]=value
        with pytest.raises(ValueError):validate_native_a0(bad)


def test_c0_a0_differ_only_flag_and_artifact_label():
    c=build_a0_kwargs(Path('.'),Path('out'),'R2_C0',())
    a=build_a0_kwargs(Path('.'),Path('out'),'R2_A0',())
    assert {k for k in c if c[k]!=a[k]}=={'research_a0_original_second','artifact_label'}

@pytest.mark.parametrize('first,second,locked,remaining,expected',[
 ('0.5','0.5','0.257','0.5','0.757'),
 ('0.1','0.5','0.1','0.5','0.6'),  # partial first never creates .9 second
 ('0.5','0.5','0.257','0.4','0.657'),
 ('0.5','0.5','0.257','0','0.257'),
])
def test_original_budget_and_closed_btc_never_refunded(first,second,locked,remaining,expected):
    args=tuple(map(D,(first,second,locked,remaining)))
    assert release_cap(*args)==D(expected)
    # Repeated WAIT quotes use original locked cap; never pass raised result back.
    assert [release_cap(*args) for _ in range(10)]==[D(expected)]*10

@pytest.mark.parametrize('remaining',['-1','0.501','NaN'])
def test_unknown_cap_blocks(remaining):
    with pytest.raises(ValueError):release_cap(D('.5'),D('.5'),D('.257'),D(remaining))


def test_old_r3_guard_unchanged_new_r2_only_exact_selector():
    from run_continuous_hedge_preflight import registered_fixture_context
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
    cfg,_,_=registered_fixture_context('R2')
    with pytest.raises(ValueError,match='R3_CLEAN'):WaveOverlayStrategy(cfg.__replace__(research_paired_prefix='B2_F0'))
    for prefix in ('B2',):
        with pytest.raises(ValueError,match='EXACT_R2'):WaveOverlayStrategy(cfg.__replace__(research_a0_family='R2_A0_V1',research_paired_prefix=prefix))
    WaveOverlayStrategy(cfg.__replace__(research_a0_family='R2_A0_V1',research_paired_prefix='B2_F0',research_a0_original_second=True))
    assert cfg.research_a0_family is None and cfg.research_a0_original_second is False


def test_a0_preflight_excludes_only_paired_lock_and_preserves_native_pause():
    from run_continuous_hedge_preflight import registered_fixture_context
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
    cfg,_,_=registered_fixture_context('R2')
    s=WaveOverlayStrategy(cfg.__replace__(research_a0_family='R2_A0_V1',research_paired_prefix='B2_F0',research_a0_original_second=True))
    s._pair={'native':'held-owner'}
    assert not s._entries_enabled()
    assert s._entries_enabled(ignore_paired_lock=True)
    s._research_protect_latch='PAUSE'
    assert not s._entries_enabled(ignore_paired_lock=True)


def guarded_owner():
    """Engine-free state/ACK adversaries; stock monetary proof is native-only."""
    from types import SimpleNamespace as S
    from coinmaster.strategy.a0_rights import A0RightsResearch
    owner=A0RightsResearch();owner.config=S(research_a0_original_second=True,btc_id='BTC',sol_id='SOL')
    ep=S(id='p',side=1,pending={});owner._domain=S(episode=ep)
    owner._split_parent=dict(episode_id='p',side=1,closed=True,intent=S(id='i'),sigma=None,decision_index=0)
    a=dict(dead=None,attempted=False,submitted=False,off_ns=0,old_orders=('old',),original_second=D(5),first_terminal=D(5),locked_cap=None,granted_cap=None,submit_qty=D(0),price=D('98.5'),order_id=None,denial_counts={},last_denial=None)
    m=dict(a0=a,touched=set(),accepted={0,1,2},generation=0,generations={0:dict(authorized=True,required={0,1,2},accepted={0,1,2})},order_generation={f'tp{i}':0 for i in range(3)},second_filled=D(0))
    owner._md_plans={'p':m};owner._pair=dict(parent='p',risk='INACTIVE_RISK',failed=False,entry_terminal=True,debt_since=None,caps=S(bmax=D(5)))
    owner._pending_by_order={f'tp{i}':S(action='BTC_REDUCE',episode_id='p',level=i) for i in range(3)}
    def order(status,qty=0,reduce=True):return S(status=S(name=status),is_closed=status=='CANCELED',is_pending_cancel=status=='PENDING_CANCEL',is_reduce_only=reduce,leaves_qty=S(as_decimal=lambda:D(qty)))
    orders={'old':order('CANCELED'),**{f'tp{i}':order('ACCEPTED',qty) for i,qty in enumerate((1,1,3))}}
    owner.cache=S(order=lambda oid:orders.get(str(oid)),orders_open=lambda:[],orders_inflight=lambda:[],instrument=lambda _:S(size_increment=S(as_decimal=lambda:D(1))))
    owner._forced_close_reason=None;owner._liquidating=False;owner._entries_enabled=lambda **kw:True
    owner._pair_position=lambda _:S(is_long=True);owner._pair_qty=lambda _:D(5);owner._pair_work=lambda **kw:[]
    owner._tier_allows_increase=lambda *args:True
    owner.events=[];owner._md_log=lambda event,ts,**kw:owner.events.append((event,kw));owner.cancelled=[];owner.cancel_order=lambda o:owner.cancelled.append(o)
    owner._submit_intent=lambda *args,**kw:owner._a0_note_submit('new',kw['ts_now'])
    owner.clock=S(timestamp_ns=lambda:60_000_000_000)
    from nautilus_trader.model.objects import Price
    quote=S(instrument_id='BTC',ts_event=60_000_000_000,bid_price=Price.from_str('100'),ask_price=Price.from_str('100'))
    return owner,ep,m,a,orders,quote


@pytest.mark.parametrize('fault',['accepted','generation','authorization','missing_native','pending_cancel','wrong_generation','leaves'])
def test_current_generation_native_three_target_ack_blocks(fault):
    from types import SimpleNamespace as S
    o,ep,m,a,orders,q=guarded_owner()
    if fault=='accepted':m['accepted']={0,1}
    elif fault=='generation':m['generation']=1
    elif fault=='authorization':m['generations'][0]['authorized']=False
    elif fault=='missing_native':orders.pop('tp1')
    elif fault=='pending_cancel':orders['tp1'].status=S(name='PENDING_CANCEL')
    elif fault=='wrong_generation':m['order_generation']['tp1']=-1
    elif fault=='leaves':orders['tp1'].leaves_qty=S(as_decimal=lambda:D(0))
    o._a0_check(q)
    assert not a['attempted'] and not a['submitted'] and o._pair['caps'].bmax==D(5)
    assert a['denial_counts']['CURRENT_THREE_TP_ACK_UNKNOWN']==1


def test_current_native_live_tp_are_protection_not_debt_and_one_grant():
    o,ep,m,a,orders,q=guarded_owner();o._a0_check(q)
    assert a['submitted'] and a['attempted'] and a['granted_cap']==D(10)
    assert a['locked_cap']==D(5) and a['submit_qty']==D(5)
    o._a0_check(q)
    assert len([e for e in o.events if e[0]=='A0_SUBMIT'])==1 and a['locked_cap']==D(5)


@pytest.mark.parametrize('fault',['pause','parent_flip','held_flip','flat','ordinary_tp','unknown_entry','owned_increase','debt'])
def test_pause_flip_flat_unknown_and_debt_never_increase(fault):
    from types import SimpleNamespace as S
    o,ep,m,a,orders,q=guarded_owner()
    if fault=='pause':o._entries_enabled=lambda **kw:False
    elif fault=='parent_flip':ep.side=-1
    elif fault=='held_flip':o._pair_position=lambda _:S(is_long=False)
    elif fault=='flat':o._pair_qty=lambda _:D(0)
    elif fault=='ordinary_tp':m['touched']={0}
    elif fault=='unknown_entry':orders.pop('old')
    elif fault=='owned_increase':o._pending_by_order['x']=S(action='BTC_ENTRY')
    elif fault=='debt':o._pair['debt_since']=1
    o._a0_check(q)
    assert not a['attempted'] and not a['submitted'] and o._pair['caps'].bmax==D(5)


@pytest.mark.parametrize('status',['ACCEPTED','SUBMITTED','PENDING_CANCEL','CANCELED'])
def test_ordinary_stop_immediate_cancels_replacement_despite_historical_closed(status):
    from types import SimpleNamespace as S
    o,ep,m,a,orders,q=guarded_owner()
    a.update(attempted=True,submitted=True,order_id='new')
    release=S(is_closed=status=='CANCELED',is_pending_cancel=status=='PENDING_CANCEL')
    orders['new']=release
    o._a0_stop('FIRST_POSITIVE_TP_FILL')
    assert a['dead']=='FIRST_POSITIVE_TP_FILL' and o._split_parent['closed'] and orders['old'].is_closed
    assert o.cancelled==([release] if status in ('ACCEPTED','SUBMITTED') else [])
    o._a0_check(q);assert a['attempted'] and a['locked_cap'] is None


@pytest.mark.parametrize('case',['A02_PARTIAL_FIRST_CLOSED_CAP','A03_ORDINARY_TP_KILLS','A04_CANCEL_RACE_LATE_FILL','A05_CROSS_MARGIN_UNKNOWN','A06_C0_NO_RELEASE'])
def test_fixture_actual_stock_daily_open_and_causal_seed_precondition(case):
    import ast,inspect,textwrap
    from run_a0_engineering import fixture_configuration,StockProbe,assert_daily_fixture_preconditions
    from run_continuous_hedge_preflight import prepare_completed_day
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
    s=StockProbe(fixture_configuration(case));prepare_completed_day(s,2)
    assert s.config.trading_start_open_ns==-86_400_000_000_000
    assert s.config.terminal_close_at_ns==3600_000_000_000
    assert_daily_fixture_preconditions(s)
    # Evaluate the actual stock source guard expression, engine-free. It
    # returned True in failed340f; revised fixture must make it False.
    tree=ast.parse(textwrap.dedent(inspect.getsource(WaveOverlayStrategy._advance_current_day)))
    guard=next(n.test for n in ast.walk(tree) if isinstance(n,ast.If) and 'trading_start_open_ns' in ast.unparse(n.test))
    assert eval(compile(ast.Expression(guard),'actual-stock-daily-guard','eval'),{'self':s}) is False
    assert s._current_btc.ts_event==2 and max(int(b.available_at.timestamp()*10**9) for b in s._bars)==0


@pytest.mark.parametrize('end_error',[False,True])
def test_fixture_streaming_cleanup_sequence_records_actual_component_lifecycle(tmp_path,monkeypatch,end_error):
    """No native engine: exercise only the wrapper's public API sequencing."""
    from types import SimpleNamespace as S
    import json
    import run_a0_engineering as fixture
    components={name:S(state=S(name='RUNNING'),is_running=True,is_disposed=False) for name in ('trader','data_engine','risk_engine','exec_engine','emulator')}
    calls=[]
    def end():
        calls.append('native.end')
        if end_error:raise RuntimeError('original-end-error')
        for c in components.values():c.state=S(name='STOPPED');c.is_running=False
    def dispose():
        calls.append('native.dispose')
        for c in components.values():c.state=S(name='DISPOSED');c.is_running=False;c.is_disposed=True
    path=tmp_path/'ledger.json';path.write_text(json.dumps({'attempts':[{}]}))
    rec=S(path=path,write=lambda d:path.write_text(json.dumps(d)))
    monkeypatch.setattr(fixture.pre,'REC',rec)
    engine=object.__new__(fixture.CountedEngine);engine.native=S(kernel=S(**components),end=end,dispose=dispose)
    engine.number=1;engine.disposed=False
    engine.capture=lambda stage:calls.append(stage)
    engine.dispose()
    assert calls==['BEFORE_TERMINAL','BEFORE_END','native.end','AFTER_END','BEFORE_DISPOSE','native.dispose']
    actual=json.loads(path.read_text())['attempts'][0]['cleanup_lifecycle']
    assert actual['clean'] is (not end_error) and all(c['disposed'] for c in actual['after_dispose'].values())
    if end_error:assert 'original-end-error' in actual['errors'][0]['error']
    else:assert all(not c['running'] for c in actual['after_end'].values())


def test_combined_fixture_three_distinct_real_depths_qualify_fresh_l1_consumption():
    from run_a0_engineering import COMBINED_DEPTHS,CASES
    from coinmaster.research.native_fixture import BTC_PERP
    depths=[BTC_PERP.make_qty(D(COMBINED_DEPTHS[k])).as_decimal() for k in ('old_late','release_partial','release_late')]
    assert depths==[D(1),D(2),D(3)] and all(a!=b for a,b in zip(depths,depths[1:]))
    assert CASES==['A03_A04_COMBINED_CANCEL_RACES','A05_CROSS_MARGIN_UNKNOWN','A06_C0_NO_RELEASE']
    # Each distinct displayed size is fresh per the pinned stock size-change
    # condition; no timestamp-only replenishment or generated fill is asserted.
