from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from types import SimpleNamespace
import pytest
from nautilus_trader.model.data import BarType, BarSpecification
from nautilus_trader.model.enums import AggregationSource, BarAggregation, PriceType
from coinmaster.domain.wave_overlay import Candidate, DailyBar, Episode
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from coinmaster.strategy.hedge_band import H4_NS
from test_wave_native_integration import lifecycle_config, native_engine
from test_native_episode_risk import NativeProbe, tick, run_ticks, marks
from test_native_btc_sizing import prepare_day
from test_native_h1_b1 import bar


def config(**kw):
    return lifecycle_config(research_h4_ema=34,
        research_h4_seed=tuple((i*H4_NS,90. if i == 0 else 100.) for i in range(-729,1)),
        max_mark_age_ns=10*H4_NS, **kw)


def setup(c0=False, cls=NativeProbe):
    s=cls(lifecycle_config(research_sol_btc_open_only=True) if c0 else config())
    e=native_engine(s)
    run_ticks(e,[tick(BTC_PERP,1)])
    prepare_day(s,2)
    ep=s._domain.episode=Episode('hedge',1,10000,1,wave_levels=(.01,.02,.03),h=10000)
    i=s._domain._intent(ep,'BTC_ENTRY',1,None,quantity=100)
    s._submit_intent(i,100,100,None,0,ts_now=2)
    run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4)])
    return s,e,ep


def test_default_off_h4_separate_bar_branch_and_no_early_signal():
    assert lifecycle_config().research_h4_ema is None
    kind=BarType(SOL_PERP.id,BarSpecification(4,BarAggregation.HOUR,PriceType.LAST),AggregationSource.EXTERNAL)
    s=NativeProbe(config(research_h4_bar_type=kind));e=native_engine(s)
    try:
        run_ticks(e,[tick(BTC_PERP,H4_NS-1)])
        assert s._hb_bar_ns==0
        s.on_bar(bar(kind,H4_NS,101))
        assert s._hb_bar_ns==H4_NS and s._hb_side==1
        assert not s._confirmation_state and not s._confirmation_events
    finally:e.end();e.dispose()


def test_h4_native_partial_children_target_reduction_expiry_and_no_liquidity_reuse():
    s,e,ep=setup()
    try:
        c=s._hb_cycle
        assert c['target']==50 and c['deadline_ns']==3+H4_NS
        run_ticks(e,[tick(SOL_PERP,4,size='10')])
        first=len(e.cache.orders()); qty=ep.sol_qty
        assert 0<qty<=10
        # Explicit same-receipt call cannot mint another child/liquidity.
        s._hedge_refresh(4)
        assert len(e.cache.orders())==first
        run_ticks(e,[tick(SOL_PERP,5,size='10')])
        assert ep.sol_qty<=20
        # Confirmed actual BTC TP lowers target; no previous quantity restoration.
        i=s._domain._intent(ep,'BTC_REDUCE',-1,0,quantity=80)
        s._submit_intent(i,100,100,None,0,ts_now=6)
        run_ticks(e,[tick(BTC_PERP,7),tick(SOL_PERP,8),tick(SOL_PERP,9)])
        assert s._hb_cycle['target']==10
        assert ep.sol_qty<=10
        frozen=c['ratio']; deadline=c['deadline_ns']
        marks(s,10,'200','50');s._hedge_refresh(10)
        assert c['ratio']==frozen and c['deadline_ns']==deadline and c['target']==10
        run_ticks(e,[tick(SOL_PERP,deadline),tick(SOL_PERP,deadline+1)])
        assert c['deadline_ns']==deadline
        assert not any(i.action=='SOL_ADD' for i in s._pending_by_order.values())
    finally:e.end();e.dispose()


def test_h4_signal_reversal_native_exit_and_second_activation_keeps_new_deadline():
    s,e,ep=setup()
    try:
        run_ticks(e,[tick(SOL_PERP,4),tick(SOL_PERP,5)])
        s._hedge_h4_close(H4_NS,200);s._hedge_refresh(H4_NS)
        run_ticks(e,[tick(SOL_PERP,H4_NS+1),tick(SOL_PERP,H4_NS+2)])
        assert ep.sol_qty==0
        s._hedge_h4_close(2*H4_NS,1);s._hedge_refresh(2*H4_NS)
        c=s._hb_cycle
        assert c['activation_ns']==2*H4_NS and c['deadline_ns']==3*H4_NS
        run_ticks(e,[tick(SOL_PERP,2*H4_NS+1),tick(SOL_PERP,2*H4_NS+2)])
        assert ep.sol_qty>0
        assert len([a for a in s.hedge_band_audit if a['event']=='H4_ACTIVATION'])==2
    finally:e.end();e.dispose()


@pytest.mark.parametrize('c0',[True,False])
def test_final_btc_tp_invalidates_unused_rights_and_native_group_flat(c0):
    s,e,ep=setup(c0)
    try:
        ep.sol_rights.update((0,1,2))
        if c0:
            i=s._domain._intent(ep,'SOL_ADD',-1,0,quantity=5)
            s._submit_intent(i,100,100,None,0,ts_now=4)
        run_ticks(e,[tick(SOL_PERP,5),tick(SOL_PERP,6)])
        i=s._domain._intent(ep,'BTC_REDUCE',-1,2,quantity=100)
        s._submit_intent(i,100,100,None,0,ts_now=7)
        run_ticks(e,[tick(BTC_PERP,8),tick(SOL_PERP,9),tick(BTC_PERP,10),tick(SOL_PERP,11)])
        assert not ep.sol_rights
        assert not e.cache.positions_open() and not s._pending_by_order
        assert s._domain.episode is None
        assert not s._hb_wait_regime
        assert [a for a in s.hedge_band_audit if a['event']=='BTC_FLAT_INVALIDATE_RIGHTS'][-1]['reason']!='REGIME'
    finally:e.end();e.dispose()


def test_b_initial_permissions_weak_strong_and_latest_side_with_wilder_seed():
    s=NativeProbe(lifecycle_config(research_regime_reentry_band=D('.5'),candidate=Candidate(ema_period=34)))
    assert s._hedge_band_allowed()  # initial opening is unfiltered
    now=datetime(2020,1,1,tzinfo=UTC)
    s._bars=[DailyBar(now+timedelta(days=i),now+timedelta(days=i+1),now+timedelta(days=i+1),100,100,100) for i in range(20)]
    s._hb_daily_ohlc={int(r.close_time.timestamp()*1e9):(110,90) for r in s._bars}
    s._hb_wait_regime=True
    assert not s._hedge_band_allowed()
    last=s._bars[-1]
    s._bars[-1]=DailyBar(last.open_time,last.close_time,last.available_at,100,130,100)
    s._hb_daily_ohlc[int(last.close_time.timestamp()*1e9)]=(135,90)
    assert s._hedge_band_allowed() and s._hb_wait_regime
    s._bars[-1]=DailyBar(last.open_time,last.close_time,last.available_at,100,70,100)
    s._hb_daily_ohlc[int(last.close_time.timestamp()*1e9)]=(110,65)
    assert s._hedge_band_allowed() and s.hedge_band_audit[-1]['side']==-1
    zero=NativeProbe(lifecycle_config(research_regime_reentry_band=D('0')))
    zero._hb_wait_regime=True
    assert zero._hedge_band_allowed()


def test_h4_final_btc_flat_waits_cancel_ack_and_native_late_fill_then_closes():
    from nautilus_trader.model.enums import OrderSide, TimeInForce
    class Delayed(NativeProbe):
        def cancel_order(self, order, *a, **kw):
            if not order.is_reduce_only:
                return  # Venue cancellation pending; matching may still fill.
            return super().cancel_order(order,*a,**kw)
    s,e,ep=setup(cls=Delayed)
    try:
        # Genuine resting native SOL opening order, owned by the same executor.
        i=s._domain._intent(ep,'SOL_ADD',-1,None,quantity=5,reason='H4_INCREASE')
        order=s.order_factory.limit(SOL_PERP.id,OrderSide.SELL,SOL_PERP.make_qty(D(5)),
            SOL_PERP.make_price(D(110)),time_in_force=TimeInForce.GTC)
        oid=str(order.client_order_id)
        s._pending_by_order[oid]=i;s._sigma_by_order[oid]=None;s._decision_index_by_order[oid]=0
        assert s._record_submission(order,i.id,i.episode_id,i.action,i.reason)
        s.submit_order(order)
        final=s._domain._intent(ep,'BTC_REDUCE',-1,2,quantity=100)
        s._submit_intent(final,100,100,None,0,ts_now=6)
        run_ticks(e,[tick(BTC_PERP,7),tick(SOL_PERP,8)])
        assert s._domain.episode is ep and s._group_close_reconciliation_pending
        assert not ep.sol_rights and s._forced_close_reason!='REGIME'
        run_ticks(e,[tick(SOL_PERP,9,'111'),tick(SOL_PERP,10,'111'),tick(BTC_PERP,11),tick(SOL_PERP,12,'111')])
        assert not e.cache.positions_open() and not s._pending_by_order
        assert s._domain.episode is None and not s._hb_wait_regime
        fills=[r for r in s.fill_audit if r['instrument']==str(SOL_PERP.id)]
        assert [r['action'] for r in fills]==['SOL_ADD','FORCED_CLOSE']
        assert fills[-1]['reason']=='BTC_TP_FLAT'
    finally:e.end();e.dispose()


def test_b_latch_only_after_actual_regime_group_terminal_and_only_fill_clears():
    s=NativeProbe(lifecycle_config(research_regime_reentry_band=D('.5')))
    e=native_engine(s)
    try:
        run_ticks(e,[tick(BTC_PERP,1)])
        prepare_day(s,2)
        ep=s._domain.episode=Episode('regime',1,10000,1,close_reason='REGIME')
        s._group_close_reconciliation_pending=True
        # An unresolved opening ACK forbids completed group/latch transition.
        old=s._domain._intent(ep,'BTC_ENTRY',1,None,quantity=1)
        s._pending_by_order['awaiting-ack']=old
        s._reconcile_group_flat()
        assert not s._hb_wait_regime and s._domain.episode is ep
        s._pending_by_order.clear();ep.pending.clear()
        s._reconcile_group_flat()
        assert s._hb_wait_regime and s._domain.episode is None
        # Zero-fill local denial is not an entry fill and retains the latch.
        ep=s._domain.episode=Episode('zero-reject',-1,10000,1,wave_levels=(.01,.02,.03))
        i=s._domain._intent(ep,'BTC_ENTRY',-1,None,quantity=.00001)
        s._submit_intent(i,100,100,None,0,ts_now=3)
        assert s._hb_wait_regime
        ep=s._domain.episode=Episode('confirmed',-1,10000,1,wave_levels=(.01,.02,.03))
        i=s._domain._intent(ep,'BTC_ENTRY',-1,None,quantity=1)
        s._submit_intent(i,100,100,None,0,ts_now=4)
        assert s._hb_wait_regime
        run_ticks(e,[tick(BTC_PERP,5)])
        assert not s._hb_wait_regime and ep.btc_open_qty==1
    finally:e.end();e.dispose()


def test_h4_pending_activation_keeps_original_deadline_through_partial_old_exit():
    s,e,ep=setup()
    try:
        run_ticks(e,[tick(SOL_PERP,5),tick(SOL_PERP,6)])
        assert ep.sol_qty==50
        s._hedge_h4_close(H4_NS,200);s._hedge_refresh(H4_NS)
        run_ticks(e,[tick(SOL_PERP,H4_NS+1,size='10')])
        assert ep.sol_qty==40 and s._hb_exit_pending
        s._hedge_h4_close(2*H4_NS,1);s._hedge_refresh(2*H4_NS)
        c=s._hb_cycle
        assert c['activation_ns']==2*H4_NS and c['deadline_ns']==3*H4_NS
        run_ticks(e,[tick(SOL_PERP,2*H4_NS+1,size='10')])
        assert ep.sol_qty==30 and s._hb_exit_pending
        # Completion after original pending deadline cannot restart the clock.
        run_ticks(e,[tick(SOL_PERP,3*H4_NS+1),tick(SOL_PERP,3*H4_NS+2),tick(SOL_PERP,3*H4_NS+3)])
        assert ep.sol_qty==0 and c['deadline_ns']==3*H4_NS
        assert not any(i.action=='SOL_ADD' for i in s._pending_by_order.values())
    finally:e.end();e.dispose()


def test_h4_native_composite_receipt_uses_only_delivered_complete_minutes():
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.cache.config import CacheConfig
    from nautilus_trader.data.config import DataEngineConfig
    from nautilus_trader.model.enums import AccountType, OmsType
    from nautilus_trader.model.objects import Money
    from coinmaster.research.native_fixture import SIM
    base=1725148800*1_000_000_000
    kind=BarType.new_composite(SOL_PERP.id,BarSpecification(4,BarAggregation.HOUR,PriceType.LAST),AggregationSource.INTERNAL,1,BarAggregation.MINUTE,AggregationSource.EXTERNAL)
    s=NativeProbe(lifecycle_config(research_h4_ema=34,research_h4_bar_type=kind,
        research_h4_seed=tuple((base+i*H4_NS,100.) for i in range(-729,1))))
    e=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR'),cache=CacheConfig(bar_capacity=128),data_engine=DataEngineConfig(time_bars_build_with_no_updates=False)))
    e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,bar_execution=False)
    e.add_instrument(BTC_PERP);e.add_instrument(SOL_PERP);e.add_strategy(s)
    minute=BarType(SOL_PERP.id,BarSpecification(1,BarAggregation.MINUTE,PriceType.LAST),AggregationSource.EXTERNAL)
    try:
        e.add_data([bar(minute,base+m*60_000_000_000,100+m) for m in range(1,240)])
        e.run(streaming=True);e.clear_data()
        assert s._hb_bar_ns==base and not s.hedge_band_audit
        e.add_data([bar(minute,base+m*60_000_000_000,100+m) for m in (240,241)])
        e.run(streaming=True);e.clear_data()
        assert s._hb_bar_ns==base+H4_NS
        assert s.hedge_band_audit[-1]['ema']==pytest.approx(2/35*340+(1-2/35)*100)
        assert not s._confirmation_state and not s._confirmation_events
    finally:e.end();e.dispose()


def test_c0_intermediate_btc_tp_preserves_original_sol_quantity():
    s,e,ep=setup(c0=True)
    try:
        i=s._domain._intent(ep,'SOL_ADD',-1,0,quantity=5)
        s._submit_intent(i,100,100,None,0,ts_now=5)
        run_ticks(e,[tick(SOL_PERP,6)])
        assert ep.sol_qty==5
        i=s._domain._intent(ep,'BTC_REDUCE',-1,0,quantity=40)
        s._submit_intent(i,100,100,None,0,ts_now=7)
        run_ticks(e,[tick(BTC_PERP,8),tick(SOL_PERP,9)])
        assert ep.btc_open_qty==60 and ep.sol_qty==5
        assert s._forced_close_reason is None
    finally:e.end();e.dispose()
