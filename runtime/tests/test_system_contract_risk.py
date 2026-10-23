from decimal import Decimal as D
from types import SimpleNamespace as NS
import json
import pytest
from coinmaster.domain.wave_overlay import Episode
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
from coinmaster.strategy.system_contract import add_budget_quantity, repeat_sizing, q90, DAY, MINUTE
from coinmaster.venues.marks import VenueMark
from test_wave_native_integration import lifecycle_config, native_engine
from test_native_episode_risk import NativeProbe, tick, run_ticks, marks
from test_system_contract import submit


def budget(q=D(1000),**kw):
    state=dict(equity=D(10000),high_water=D(18000),btc_reserve=D(0),held_sol=D(0),pending_sol=D(0),pending_entry_fees=D(0),sol_atr=D(1),sol_mark=D(1),sol_fee=D('.001'),executable=D(1))
    state.update(kw)
    return add_budget_quantity(q,D('.1'),**state)


def test_add_lot_maximality_units_and_monotone_fixed_direction():
    allowed=budget()
    assert allowed==D('99.7')
    def post(q):return D(10000)-q*D('.001')-q*(D(1)+D('.001')*D(2))
    assert post(allowed)>=D('.55')*D(18000)
    assert post(allowed+D('.1'))<D('.55')*D(18000)
    assert all(post(D(n))>=post(D(n+1)) for n in range(1000))
    assert budget(held_sol=D(20),pending_sol=D(20),pending_entry_fees=D('.02'))<allowed
    assert budget(btc_reserve=D(100))==0
    assert budget(equity=D(8000))==0
    assert budget(D('.01'))==0
    for change in [dict(sol_fee=D('NaN')),dict(sol_atr=D(-1)),dict(sol_mark=D(0)),dict(sol_fee=D(0),sol_atr=D(0))]:
        with pytest.raises(ValueError):budget(**change)


class BudgetProbe(NativeProbe):
    def _sc_atrs(self):return D(1),D(1)


def setup_budget():
    s=BudgetProbe(lifecycle_config(research_sol_explicit_child=True,research_sol_add_budget=True));e=native_engine(s)
    run_ticks(e,[tick(SOL_PERP,1,'1')]);s._sc_peak=D(18000)
    ep=s._domain.episode=Episode('budget',1,10000,1,h=10000,btc_reference_qty=10000)
    s._last_accepted_session=0
    return s,e,ep


def test_second_level_sees_first_native_reservation_before_ack_and_partial_to_held():
    s,e,ep=setup_budget()
    try:
        marks(s,2,btc='1',sol='1')
        i=submit(s,ep,D(2500),0,2)
        first=s.sc_sol_budget_audit[-1]
        assert first['allowed_quantity']=='99.7'
        j=submit(s,ep,D(2500),1,2)
        second=s.sc_sol_budget_audit[-1]
        assert D(second['pending_sol'])==D('99.7')
        assert second['allowed_quantity']=='0.0'
        assert len(e.cache.orders())==1
        assert not ep.sol_add_filled_notional
        run_ticks(e,[tick(SOL_PERP,3,'1',size='50')])
        marks(s,4,btc='1',sol='1')
        submit(s,ep,D(2500),1,4)
        after=s.sc_sol_budget_audit[-1]
        assert D(after['held_sol'])==50 and after['pending_sol']=='0'
        assert D(after['allowed_quantity'])==D('49.7')
        assert all(not o.is_reduce_only for o in e.cache.orders())
        json.loads(json.dumps(s.reporting_state()))
    finally:e.end();e.dispose()


def test_unknown_pending_owner_and_missing_atr_fail_closed_without_right_spend():
    s,e,ep=setup_budget()
    try:
        marks(s,2,btc='1',sol='1')
        unknown=s._domain._intent(ep,'BTC_ENTRY',1,None,quantity=1)
        s._pending_by_order['UNKNOWN_ACK']=unknown
        submit(s,ep,D(2500),0,2)
        assert s.sc_sol_budget_audit[-1]['reason']=='UNRESOLVED_OPENING_SUBMISSION'
        assert not e.cache.orders() and not ep.sol_add_filled_notional
        s._pending_by_order.clear()
        s._sc_atrs=lambda:None
        submit(s,ep,D(2500),1,2)
        assert s.sc_sol_budget_audit[-1]['reason']=='UNKNOWN_CLOSED_ATR14'
    finally:e.end();e.dispose()


def labels():
    return [dict(status='VALID',label_ready_at=n+1,repeated=group,wave_id=str(n),u=str(n+1 if not group else 2*(n+1)))
            for group in (False,True) for n in range(8)]


def test_q90_linear_group_threshold_prefix_and_strict_availability():
    assert q90([D(1),D(3),D(8)])==D(7)
    data=labels();decision=repeat_sizing(data,9,True)
    assert decision['k']=='0.5' and decision['n_first']==8 and decision['n_repeat']==8
    assert repeat_sizing(data,8,True)['k']=='1'
    assert repeat_sizing(data,9,False)['fallback']=='FIRST_ENTRY'
    future=dict(status='VALID',label_ready_at=10,repeated=True,wave_id='future',u='100000')
    incomplete=dict(status='CENSORED_UNFINISHED_WAVE',label_ready_at=0,repeated=True,wave_id='current',u=None)
    assert repeat_sizing(data+[future,incomplete],9,True)==decision
    zero=[dict(x,u='0') if x['repeated'] else x for x in data]
    assert repeat_sizing(zero,9,True)['fallback']=='ZERO_REPEAT_Q90'
    for malformed in ('NaN','Infinity','-1','bad'):
        broken=data+[dict(data[-1],u=malformed)]
        result=repeat_sizing(broken,9,True)
        assert result['k']=='1' and result['fallback']=='INVALID_COMPLETED_LABEL'
        assert result['invalid_labels']==1


def test_actual_partial_parent_one_label_first_fill_reference_and_closed_wave_marks():
    class Probe(BudgetProbe):pass
    s=Probe(lifecycle_config(research_sol_explicit_child=True,research_btc_repeat_sizing=True));e=native_engine(s)
    try:
        run_ticks(e,[tick(BTC_PERP,1,'1')]);s._last_accepted_session=0
        s._current_signals=[NS(side=1,beta=1.,relative=0.,mu=0.,sigma=1.,z=0.)]
        bar=NS(high=1.,low=1.)
        s._sc_daily(0,0,bar,bar)
        ep=s._domain.episode=Episode('causal',1,10000,1,h=10000,wave_levels=(0,0,.03))
        i=s._domain._intent(ep,'BTC_ENTRY',1,None,requested_notional=1000)
        s._sc_btc_plan(i,NS(ts_event=MINUTE),D(1))
        s._submit_intent(i,1,1,None,0,ts_now=MINUTE)
        run_ticks(e,[tick(BTC_PERP,MINUTE+1,'1',size='100')])
        assert len(s._sc_btc_observations)==1
        # A second real fill of another physical child, same parent ID, is one case.
        extra=s.order_factory.market(BTC_PERP.id,__import__('nautilus_trader.model.enums',fromlist=['OrderSide']).OrderSide.BUY,BTC_PERP.make_qty(D(1)))
        oid=str(extra.client_order_id);ep.pending[i.id]=i;s._pending_by_order[oid]=i;s._sigma_by_order[oid]=None;s._decision_index_by_order[oid]=0
        s.submit_order(extra);run_ticks(e,[tick(BTC_PERP,MINUTE+2,'2')])
        assert len(s._sc_btc_observations)==1
        observation=s._sc_btc_observations[i.id]
        assert observation['label_reference_price']==1
        for minute,price in [(2,'.9'),(3,'.8'),(4,'.95')]:
            s._sc_mark(VenueMark(BTC_PERP.id,D(price),minute*MINUTE))
        assert s.reporting_state()['sc_btc_labels'][0]['status']=='CENSORED_UNFINISHED_WAVE'
        s._current_signals=[NS(side=-1)];s._sc_daily(4*MINUTE,4*MINUTE,bar,bar)
        label=s.sc_btc_labels[0]
        assert repeat_sizing(s.sc_btc_labels,MINUTE,False)['n_first']==0
        assert s._sc_btc_plan(i,NS(ts_event=MINUTE),D(1))==1000
        assert len(s.sc_btc_decisions)==1
        assert len(s.sc_btc_outcomes)==2
        assert label['status']=='VALID' and label['minute_mae']=='0.2'
        assert label['u']=='0.2' and D(label['label_reference_price'])==1
        assert len(s.sc_btc_labels)==1
        assert repeat_sizing(s.sc_btc_labels,4*MINUTE,True)['n_first']==0
        assert repeat_sizing(s.sc_btc_labels,4*MINUTE+1,True)['n_first']==1
        json.loads(json.dumps(s.reporting_state()))
    finally:e.end();e.dispose()


def test_k_once_before_zero_tp_cap_and_current_future_mae_not_feature():
    s=BudgetProbe(lifecycle_config(research_sol_explicit_child=True,research_btc_repeat_sizing=True));e=native_engine(s)
    try:
        run_ticks(e,[tick(BTC_PERP,1,'1')]);s._last_accepted_session=0
        s._sc_wave_id='current';s._sc_wave_parents={'past-actual-parent'};s.sc_btc_labels=labels()
        ep=s._domain.episode=Episode('sizing',1,10000,1,wave_levels=(0,0,.03))
        i=s._domain._intent(ep,'BTC_ENTRY',1,None,requested_notional=30000)
        q0=tick(BTC_PERP,10,'1')
        assert s._select_deferred_btc_entry(i,q0) is None
        row=s.sc_btc_decisions[0]
        assert row['before_k_notional']=='30000' and row['after_k_notional']=='15000.0'
        assert s._deferred_selective_entries[i.id]['gross_lots']==15000000
        assert len(s.sc_btc_decisions)==1
        assert s._sc_btc_plan(i,q0,D(1))==15000
        assert len(s.sc_btc_decisions)==1
    finally:e.end();e.dispose()


def test_pending_btc_sol_leaves_dedup_and_margin_reservations_are_native():
    from nautilus_trader.model.enums import OrderSide,TimeInForce
    s,e,ep=setup_budget()
    try:
        marks(s,2,btc='1',sol='1')
        i=s._domain._intent(ep,'BTC_ENTRY',1,None,quantity=20)
        s._submit_intent(i,1,1,None,0,ts_now=2)
        submit(s,ep,D(2500),0,2)
        row=s.sc_sol_budget_audit[-1]
        assert D(row['pending_btc'])==20 and D(row['held_btc'])==0
        assert D(row['btc_reserve'])==D('20.06')
        held,pending,fees=s._sc_opening_inventory(2)
        assert pending[BTC_PERP.id]==20
        assert pending[SOL_PERP.id]==D(row['allowed_quantity'])
        snapshot=s._sc_prefix_snapshot(2,s._sc_atrs())
        assert len(snapshot['native_open_orders'])==2
        assert all(x['side'] in ('BUY','SELL') and D(x['leaves_quantity'])>0 for x in snapshot['native_open_orders'])
        assert snapshot['closed_btc_atr14_price']=='1'
        assert snapshot['gate_witness']['status']=='PASSED_TO_Q0_NOT_FULL_INTERNAL_GATE_VECTOR'
        json.loads(json.dumps(snapshot))
        run_ticks(e,[tick(BTC_PERP,3,'1',size='10')])
        held,pending,fees=s._sc_opening_inventory(3)
        assert held[BTC_PERP.id]==10 and pending[BTC_PERP.id]==0
        account=e.cache.account_for_venue(BTC_PERP.id.venue)
        assert account.margin_init(BTC_PERP.id).as_decimal()==0
        assert account.margin_maint(BTC_PERP.id).as_decimal()>0
    finally:e.end();e.dispose()


def test_missing_minutes_never_mints_zero_mae_label():
    s=BudgetProbe(lifecycle_config(research_sol_explicit_child=True));e=native_engine(s)
    try:
        run_ticks(e,[tick(BTC_PERP,1,'1')]);s._sc_wave_id='old';s._sc_wave_side=1
        s._sc_btc_observations['p']=dict(parent_id='p',wave_id='old',repeated=False,
            first_fill_ns=MINUTE,label_reference_price=D(1),frozen_atr_fraction=D('.1'),side=1,
            mae=D(0),mark_count=0,last_mark_ns=MINUTE,gap=False,label_ready_at=None)
        s._sc_mark(VenueMark(BTC_PERP.id,D(1),3*MINUTE))
        s._current_signals=[NS(side=-1)];bar=NS(high=1.,low=1.)
        s._sc_daily(3*MINUTE,3*MINUTE,bar,bar)
        assert s.sc_btc_labels[0]['status']=='INCOMPLETE_MINUTE_MARKS_OR_ATR'
        assert s.sc_btc_labels[0]['u'] is None
        assert repeat_sizing(s.sc_btc_labels,4*MINUTE,True)['n_first']==0
    finally:e.end();e.dispose()


def test_closed_wilder14_price_units_seed_and_no_current_partial_bar():
    from datetime import datetime,timedelta,UTC
    from coinmaster.domain.wave_overlay import DailyBar
    s=NativeProbe(lifecycle_config(research_sol_explicit_child=True));e=native_engine(s)
    try:
        run_ticks(e,[tick(BTC_PERP,1,'1')])
        start=datetime(2024,1,1,tzinfo=UTC)
        s._bars=[]
        for n in range(16):
            close=start+timedelta(days=n+1);ns=int(close.timestamp()*1_000_000_000)
            s._bars.append(DailyBar(close-timedelta(days=1),close,close,100.,100.,10.))
            s._sc_ohlc[BTC_PERP.id][ns]=(101.,99.)
            s._sc_ohlc[SOL_PERP.id][ns]=(11.,9.)
        s._last_accepted_session=ns
        assert s._sc_atrs()==(D(2),D(2))
        s._current_signals=[NS(side=-1)]*16
        snapshot=s._sc_prefix_snapshot(ns,s._sc_atrs())
        assert D(snapshot['closed_btc_ema'])==100
        assert snapshot['current_ema_wave_closed_bar_count']==16
        assert D(snapshot['signed_ema_distance_atr'])==0
        # A future unaccepted OHLC row never enters the already-closed ATR.
        s._sc_ohlc[BTC_PERP.id][ns+DAY]=(1000000.,1.)
        assert s._sc_atrs()==(D(2),D(2))
    finally:e.end();e.dispose()
