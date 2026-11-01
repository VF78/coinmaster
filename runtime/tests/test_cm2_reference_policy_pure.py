"""Synthetic source/behavior checks only: no engine, native Strategy or money."""
import ast
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from inspect import signature
from math import sin
from pathlib import Path

import pytest

from coinmaster.domain.wave_overlay import Candidate, DailyBar, Episode, WaveOverlayState, batch_features_for
from coinmaster.strategy.cm2_reference_policy import (
    ReferenceBtcPolicy, ReferenceFlags, BtcParent, DAY, HOUR)

UTC = timezone.utc
START = datetime(2023,1,1,tzinfo=UTC)
T0 = int(START.timestamp()*1e9)
FLAGS = ReferenceFlags(True,True)


def selected(**changes):
    return replace(Candidate(ema_period=34,btc_tp_fractions_initial_qty=(.2125,.2125,.575),
        btc_notional_multiplier=7.875,max_parent_notional=30_000_000.),**changes)


def rows(count):
    result = []
    for i in range(count):
        btc = 100+8*sin(i/9)+i*.002
        sol = 30+.4*(btc-100)+.2*sin(i/11)
        opened = START+timedelta(days=i)
        result.append(DailyBar(opened,opened+timedelta(days=1),opened+timedelta(days=1),btc-.1,btc,sol))
    return result


def policy(candidate=None, *, step=D('.01'), trading_start_ns=T0):
    return ReferenceBtcPolicy(candidate or selected(),flags=FLAGS,btc_step=step,
        trading_start_ns=trading_start_ns,terminal_ns=T0+2000*DAY,max_quote_age_ns=120_000_000_000)


def accept(p, data):
    for row in data:
        p.accept_closed_day(row,receipt_ns=int(row.available_at.timestamp()*1e9))


def hand_parent(*, side=1, levels=(.01,.02,.03), notional=1000, btc_close=None):
    p = policy();data=rows(1)
    if btc_close is not None:data[0]=replace(data[0],btc_open=btc_close,btc_close=btc_close)
    accept(p,data)
    p._parent = BtcParent('hand',side,0,1.25,levels,notional)
    return p


def split(p, *, q0_price=D(100), wire=D(100), bid=D(100), ask=D(100)):
    p.observe_entry_q0('hand',quote_ns=T0+DAY+1,executable_price=q0_price,canonical_wire_price=wire)
    qty = p.select_entry_q1('hand',quote_ns=T0+DAY+60_000_000_001,bid=bid,ask=ask)
    p.begin_split('hand',now_ns=T0+DAY+60_000_000_001)
    return qty


def fill(p, trade, qty, price=100, kind='ENTRY', level=None):
    return p.apply_fill('hand',trade_id=trade,kind=kind,quantity=D(str(qty)),
        price=D(str(price)),event_ns=T0+DAY+60_000_000_002,level=level)


def test_component_has_no_native_or_legacy_strategy_dependency():
    source=Path(__file__).parents[1]/'coinmaster/strategy/cm2_reference_policy.py'
    tree=ast.parse(source.read_text())
    imports=[n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    assert not any(x.startswith('nautilus') or x.startswith('coinmaster.strategy.wave_overlay') for x in imports)
    assert not any(isinstance(n,ast.Name) and n.id in {'BacktestEngine','WaveOverlayStrategy','WaveOverlayState'} for n in ast.walk(tree))
    assert not any('sol' in x.lower() for x in BtcParent.__dataclass_fields__)
    assert set(signature(ReferenceBtcPolicy.decide_on_day).parameters)=={'self','native_btc_marked_equity','decision_ns'}


def test_feature_identity_is_shared_batch_bit_exact_and_first_close_seeded():
    p=policy();data=rows(500);accept(p,data)
    oracle=batch_features_for(data,p.candidate)
    for got,want in zip(p.signals,oracle):
        assert got.index==want.index and got.side==want.side
        for name in ('beta','relative','mu','sigma','z'):
            a,b=getattr(got,name),getattr(want,name)
            assert a is b if a is None or b is None else a.hex()==b.hex()
    assert p.signals[0].side == -1  # Equality with first close is SHORT.
    prefix=p.signals;accept(p,rows(501)[500:])
    assert p.signals[:500]==prefix


@pytest.mark.parametrize('fault',['future','gap','duplicate','nan','not_day'])
def test_reject_bad_causal_pair_before_mutating_state(fault):
    p=policy();data=rows(3);accept(p,data[:1]);before=p.signals
    row=data[1];receipt=T0+2*DAY
    if fault=='future':receipt-=1
    elif fault=='gap':row=data[2];receipt=T0+3*DAY
    elif fault=='duplicate':row=data[0]
    elif fault=='nan':row=replace(row,sol_close=float('nan'))
    elif fault=='not_day':row=replace(row,open_time=row.open_time+timedelta(seconds=1))
    with pytest.raises(ValueError):p.accept_closed_day(row,receipt_ns=receipt)
    assert p.signals==before


def test_entry_uses_reference_beta_waves_and_native_btc_scalar_only():
    p=policy(trading_start_ns=T0+730*DAY);data=rows(800);accept(p,data)
    now=int(data[-1].available_at.timestamp()*1e9)
    decision=p.decide_on_day(native_btc_marked_equity=D(10000),decision_ns=now)
    oracle=WaveOverlayState(p.candidate)
    intents=oracle.decide(data,list(p.signals),799,10000,
        btc_notional_multiplier=5.5 if p.signals[-1].side==1 else 7.875)
    assert decision.action=='BTC_ENTRY' and len(intents)==1
    assert decision.requested_notional==intents[0].requested_notional
    assert p.parent.levels==oracle.episode.wave_levels
    assert p.parent.beta==oracle.episode.beta_entry
    assert p.decide_on_day(native_btc_marked_equity=D(20000),decision_ns=now).action=='HOLD'
    assert p.parent.requested_notional==decision.requested_notional  # freeze, no pyramiding


def test_required_flags_beta_warmup_and_unknown_capital_fail_closed():
    with pytest.raises(TypeError):ReferenceFlags()
    with pytest.raises(ValueError):ReferenceFlags(None,True)
    with pytest.raises(ValueError):ReferenceBtcPolicy(selected(),flags=None,btc_step=D('.01'),trading_start_ns=T0,terminal_ns=T0+DAY,max_quote_age_ns=1)
    p=policy();accept(p,rows(20))
    assert p.decide_on_day(native_btc_marked_equity=D(10000),decision_ns=T0+20*DAY).reason=='GENUINE_730_DAY_FEATURE_SEED_REQUIRED'
    p=policy(trading_start_ns=T0+730*DAY);accept(p,rows(800))
    assert p.decide_on_day(native_btc_marked_equity=D('NaN'),decision_ns=T0+800*DAY).reason=='BTC_NATIVE_CAPITAL_UNKNOWN'


@pytest.mark.parametrize('side',[1,-1])
def test_q0_q1_omits_only_passive_zero_levels_and_has_fixed_parent_lots(side):
    p=hand_parent(side=side,levels=(0,.02,.04))
    bid,ask=(D(99),D(99)) if side==1 else (D(101),D(101))
    assert split(p,bid=bid,ask=ask)==D('7.88')
    assert p.parent.gross_lots==1000 and p.parent.omitted_levels==frozenset({0})
    assert p.parent.reference_targets==(212,212,576)
    assert p.parent.first_quantity==D('3.94')
    with pytest.raises(ValueError):p.select_entry_q1('hand',quote_ns=T0+DAY+60_000_000_002,bid=bid,ask=ask)


def test_same_quote_stale_quote_and_future_split_cannot_claim_q1_permission():
    p=hand_parent();p.observe_entry_q0('hand',quote_ns=T0+DAY+1,executable_price=D(100),canonical_wire_price=D(100))
    for q in (T0+DAY+1,T0+DAY+120_000_000_002):
        with pytest.raises(ValueError):p.select_entry_q1('hand',quote_ns=q,bid=D(100),ask=D(100))
    p.select_entry_q1('hand',quote_ns=T0+DAY+60_000_000_001,bid=D(100),ask=D(100))
    with pytest.raises(ValueError):p.begin_split('hand',now_ns=T0+DAY+2)
    with pytest.raises(ValueError):p.begin_split('hand',now_ns=T0+DAY+60_000_000_002)


def test_marketable_zero_fallback_keeps_full_entry_but_suppresses_zero_resting_target():
    p=hand_parent(levels=(0,.02,.04));assert split(p)==D(10)
    assert p.parent.omitted_levels==frozenset() and p.parent.suppressed_zero_levels==frozenset({0})
    fill(p,'full',10)
    assert [x.level for x in p.confirmed_targets('hand')]==[1,2]


def test_q1_reapplies_full_parent_cap_before_first_child():
    p=hand_parent();p.candidate=replace(p.candidate,max_parent_notional=1000)
    assert split(p,bid=D(200),ask=D(200))==D(5)
    assert p.parent.first_quantity==D('2.5')


def test_odd_lots_partial_first_cannot_freeze_planref_or_earn_targets():
    p=hand_parent(notional=11);assert split(p)==D('.11')
    assert p.parent.first_quantity==D('.05')
    fill(p,'first-part',.02,100)
    assert p.parent.planref is None
    with pytest.raises(ValueError):p.confirmed_targets('hand')
    plan=p.entry_plan('hand',now_ns=T0+DAY+60_000_000_003,bid=D(100),ask=D(100),pending_kind='NONE')
    assert (plan.action,plan.quantity)==('IOC',D('.03'))
    fill(p,'first-complete',.03,102)
    assert p.parent.planref==D('101.2')
    plan=p.entry_plan('hand',now_ns=T0+DAY+60_000_000_003,bid=D(100),ask=D(100),pending_kind='NONE')
    assert (plan.action,plan.quantity,plan.raw_limit_price)==('DISCOUNT_GTC',D('.06'),D('100.94700'))
    fill(p,'second',.06,99)
    assert p.parent.planref==D('101.2')
    assert p.parent.entry_notional==D('11')  # .02*100+.03*102+.06*99
    assert [x.quantity for x in p.confirmed_targets('hand')]==[D('.02'),D('.02'),D('.07')]


@pytest.mark.parametrize('trigger',['deadline','early_tp'])
def test_completion_waits_for_native_terminal_then_only_remaining_quantity(trigger):
    p=hand_parent();split(p);fill(p,'first',5)
    now=p.parent.split_deadline_ns if trigger=='deadline' else T0+DAY+60_000_000_003
    px=D(100) if trigger=='deadline' else D(101)
    assert p.entry_plan('hand',now_ns=now,bid=px,ask=px,pending_kind='DISCOUNT_GTC').action=='CANCEL_RESTING_LIMIT'
    assert p.entry_plan('hand',now_ns=now,bid=px,ask=px,pending_kind='DISCOUNT_GTC').action=='CANCEL_RESTING_LIMIT'
    fill(p,'racing-second-part',1,99)
    plan=p.entry_plan('hand',now_ns=now,bid=px,ask=px,pending_kind='NONE')
    assert (plan.action,plan.quantity)==('IOC',D(4))
    fill(p,'completion',4,101)
    assert p.entry_plan('hand',now_ns=now,bid=px,ask=px,pending_kind='NONE').action=='HOLD'
    assert p.parent.filled_quantity==D(10)


def test_stop_does_not_forge_native_cancel_or_erase_real_late_fill():
    p=hand_parent();split(p);fill(p,'first',5)
    p.stop_entry_remainder('hand',reason='MANDATORY_CLOSE')
    assert p.entry_plan('hand',now_ns=T0+DAY+60_000_000_003,bid=D(100),ask=D(100),pending_kind='IOC').action=='CANCEL'
    fill(p,'late',1,99)
    assert p.parent.filled_quantity==D(6) and p.parent.stop_reason=='MANDATORY_CLOSE'
    assert p.entry_plan('hand',now_ns=T0+DAY+60_000_000_003,bid=D(100),ask=D(100),pending_kind='NONE').action=='HOLD'
    with pytest.raises(ValueError):fill(p,'overfill',5)
    assert p.parent.filled_quantity==D(6)


def test_utc_boundary_revokes_remainder_without_fabricating_fill():
    p=hand_parent();split(p);fill(p,'part',2)
    now=T0+2*DAY
    assert p.entry_plan('hand',now_ns=now,bid=D(100),ask=D(100),pending_kind='IOC').action=='CANCEL'
    assert p.parent.filled_quantity==D(2) and p.parent.split_terminal


def test_confirmed_tp_lots_partial_and_duplicate_fill_are_conserved():
    p=hand_parent();split(p)
    with pytest.raises(ValueError):p.confirmed_targets('hand')
    fill(p,'entry',10)
    assert [x.quantity for x in p.confirmed_targets('hand')]==[D('2.12'),D('2.12'),D('5.76')]
    assert all(x.positive_ioc_candidate for x in p.confirmed_targets('hand'))
    assert fill(p,'tp-part',.5,101,kind='TP',level=0)
    before=p.parent
    assert not fill(p,'tp-part',.5,101,kind='TP',level=0)
    assert p.parent==before
    with pytest.raises(ValueError):fill(p,'tp-part',.6,101,kind='TP',level=0)
    assert p.confirmed_targets('hand')[0].quantity==D('1.62')
    with pytest.raises(ValueError):fill(p,'bad-level',3,101,kind='TP',level=0)
    with pytest.raises(ValueError):fill(p,'unknown-level',1,101,kind='TP',level=3)


def test_tp_flat_does_not_reset_btc_economic_episode_and_copy_cannot_mutate_it():
    p=hand_parent(side=-1);split(p);fill(p,'entry',10)
    for level,qty in enumerate(('2.12','2.12','5.76')):
        fill(p,'tp'+str(level),qty,103,kind='TP',level=level)
    assert p.confirmed_targets('hand')==()
    assert p.parent is not None
    snapshot=p.parent;snapshot.side=1
    assert p.parent.side==-1
    assert p.decide_on_day(native_btc_marked_equity=D(20000),decision_ns=T0+DAY+120_000_000_000).action=='HOLD'
    accept(p,rows(2)[1:])
    assert p.decide_on_day(native_btc_marked_equity=D(20000),decision_ns=T0+2*DAY).action=='BTC_CLOSE'
    # Next closed D1 turns LONG, so the retained short latches REGIME;
    # even now it remains until a later native-flat close receipt integration.
    assert p.parent.close_reason=='REGIME'


def test_empty_terminal_requires_native_ownership_clear_and_no_fill():
    p=hand_parent();split(p)
    with pytest.raises(ValueError):p.confirm_empty_entry_terminal('hand',native_pending=True)
    p.confirm_empty_entry_terminal('hand',native_pending=False)
    assert p.parent is None
    p=hand_parent();split(p);fill(p,'part',1)
    with pytest.raises(ValueError):p.confirm_empty_entry_terminal('hand',native_pending=False)


def test_partial_management_fallback_preserves_reference_float_accumulation_order():
    p=hand_parent();split(p)
    old=WaveOverlayState(p.candidate)
    old.episode=Episode('old',1,10000,1.25,wave_levels=(.01,.02,.03))
    intent=old._intent(old.episode,'BTC_ENTRY',1,None,requested_notional=1000)
    for i,(qty,price) in enumerate((('.1','100.1'),('.2','100.2'),('.3','100.3'),('.4','100.4'))):
        fill(p,'part'+str(i),qty,price)
        old.on_fill(intent.id,float(qty),float(price),START,
            entry_qty=D(qty),entry_price=D(price))
    assert p.parent.planref is None
    assert p.parent.entry_vwap.hex()==old.episode.btc_entry_vwap.hex()
    assert p.parent.entry_quantity_float.hex()==old.episode.btc_initial_qty.hex()
    assert p.parent.filled_quantity==D('1.0')


def test_unknown_pending_cannot_implicitly_become_permission_to_submit_or_release():
    p=hand_parent();split(p)
    with pytest.raises(ValueError):
        p.entry_plan('hand',now_ns=T0+DAY+60_000_000_003,bid=D(100),ask=D(100),pending_kind=None)
    with pytest.raises(ValueError):p.confirm_empty_entry_terminal('hand',native_pending=None)


def test_exact_seed_boundary_is_feature_only_and_cannot_be_replaced_by_late_history():
    p=policy(trading_start_ns=T0+730*DAY);data=rows(731);accept(p,data[:730])
    assert p.decide_on_day(native_btc_marked_equity=D(10000),decision_ns=T0+730*DAY).reason=='FEATURE_ONLY_WARMUP'
    accept(p,data[730:])
    assert p.decide_on_day(native_btc_marked_equity=D(10000),decision_ns=T0+731*DAY).action=='BTC_ENTRY'
    late=policy(trading_start_ns=T0+730*DAY);accept(late,data[1:])
    assert late.decide_on_day(native_btc_marked_equity=D(10000),decision_ns=T0+731*DAY).reason=='GENUINE_730_DAY_FEATURE_SEED_REQUIRED'


def test_passive_reference_weights_survive_no_zero_levels_and_q1_cap():
    # Explicit synthetic 1000 -> 999 lot cap, without financial/history inputs.
    p=hand_parent();p.candidate=replace(p.candidate,max_parent_notional=1000)
    assert split(p,bid=D('99.99'),ask=D('100.01'))==D('9.99')
    assert p.parent.passive_selection and not p.parent.omitted_levels
    fill(p,'capped',D('9.99'))
    assert [x.quantity for x in p.confirmed_targets('hand')]==[D('2.11'),D('2.11'),D('5.77')]
    marketable=hand_parent();marketable.candidate=replace(marketable.candidate,max_parent_notional=1000)
    assert split(marketable,bid=D('100.01'),ask=D('100.01'))==D('9.99')
    assert not marketable.parent.passive_selection
    fill(marketable,'capped',D('9.99'))
    assert [x.quantity for x in marketable.confirmed_targets('hand')]==[D('2.12'),D('2.12'),D('5.75')]


def test_marketable_zero_has_d1_taker_permission_current_quote_guard_and_actual_leaves():
    p=hand_parent(side=-1,levels=(0,.02,.04));split(p);fill(p,'entry',10)
    assert [x.level for x in p.confirmed_targets('hand')]==[1,2]
    now=T0+DAY+120_000_000_000
    assert not p.ordinary_tp_permissions('hand',decision_ns=now,
        native_resting_levels=frozenset({1,2}),native_pending_levels=frozenset({0}))
    permissions=p.ordinary_tp_permissions('hand',decision_ns=now,
        native_resting_levels=frozenset({1,2}),native_pending_levels=frozenset())
    assert len(permissions)==1 and permissions[0].level==0 and permissions[0].quantity==D('2.12')
    plan=permissions[0]
    assert plan.conditional_ioc and not plan.positive_ioc_candidate
    assert not p.ordinary_tp_permissions('hand',decision_ns=now,
        native_resting_levels=frozenset({1,2}),native_pending_levels=frozenset())
    args=dict(quote_ns=now,bid=D(101),ask=D(101),native_pending_levels=frozenset())
    assert p.executable_tp_quantity(plan,**args)==0  # Adverse current ask.
    args.update(bid=D(100),ask=D(100),native_pending_levels=frozenset({0}))
    assert p.executable_tp_quantity(plan,**args)==0  # Native IOC still owned.
    args['native_pending_levels']=frozenset()
    assert p.executable_tp_quantity(plan,**args)==D('2.12')
    assert p.parent.tp_filled_lots=={}  # Permission does not consume real lots.
    fill(p,'zero-part',1,100,kind='TP',level=0)
    assert p.executable_tp_quantity(plan,**args)==D('1.12')
    fill(p,'zero-rest',D('1.12'),100,kind='TP',level=0)
    assert p.executable_tp_quantity(plan,**args)==0


def test_omitted_zero_never_gets_ordinary_taker_permission():
    p=hand_parent(side=-1,levels=(0,.02,.04));split(p,bid=D(101),ask=D(101));fill(p,'entry',D('7.88'))
    assert not p.ordinary_tp_permissions('hand',decision_ns=T0+DAY+120_000_000_000,
        native_resting_levels=frozenset({1,2}),native_pending_levels=frozenset())


def test_deadline_does_not_cancel_an_owned_ioc_or_submit_over_unknown_owner():
    p=hand_parent();split(p);fill(p,'first',5)
    args=dict(now_ns=p.parent.split_deadline_ns,bid=D(100),ask=D(100))
    assert p.entry_plan('hand',**args,pending_kind='IOC').action=='HOLD'
    assert p.entry_plan('hand',**args,pending_kind='UNKNOWN').action=='HOLD'
    assert p.entry_plan('hand',**args,pending_kind='DISCOUNT_GTC').action=='CANCEL_RESTING_LIMIT'
    assert p.entry_plan('hand',**args,pending_kind='NONE').quantity==D(5)


@pytest.mark.parametrize('side',[1,-1])
def test_conditional_ioc_uses_owned_raw_decimal_threshold_not_rounded_gtc_wire(side):
    p=hand_parent(side=side,levels=(.001,.02,.03),btc_close=10000.1)
    qty=split(p,q0_price=D('10000.1'),wire=D(10000),bid=D('10000.1'),ask=D('10000.1'))
    fill(p,'entry',qty,D('10000.1'))
    row=rows(2)[1]
    close=10040 if side==1 else 9960
    accept(p,[replace(row,btc_open=close,btc_close=close)])
    plans=p.ordinary_tp_permissions('hand',decision_ns=T0+2*DAY,
        native_resting_levels=frozenset(),native_pending_levels=frozenset())
    assert len(plans)==1 and plans[0].level==0
    # Native GTC five-significant-figure rounding could make these quotes
    # appear crossed. Raw owned reference is10010.1001 /9990.0999 instead.
    near=D('10010') if side==1 else D('9990.1')
    assert p.executable_tp_quantity(plans[0],quote_ns=T0+2*DAY,bid=near,ask=near,
        native_pending_levels=frozenset())==0
    crossed=D('10010.2') if side==1 else D('9990.0')
    assert p.executable_tp_quantity(plans[0],quote_ns=T0+2*DAY,bid=crossed,ask=crossed,
        native_pending_levels=frozenset())==plans[0].quantity
