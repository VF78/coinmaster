from decimal import Decimal as D
from types import SimpleNamespace
import json
import pytest
from nautilus_trader.model.enums import OrderSide, TimeInForce
from coinmaster.domain.wave_overlay import Episode, Candidate
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from coinmaster.strategy.split_cover import HOUR, DAY
from test_wave_native_integration import lifecycle_config, native_engine
from test_native_episode_risk import NativeProbe, tick, run_ticks, marks
from test_native_btc_sizing import prepare_day
from test_native_h1_b1 import confirmation_types, bar


def cfg(split=False, cover=None, **kw):
    return lifecycle_config(research_btc_split50=split,
        research_sol_cover=D(cover) if cover else None,
        candidate=Candidate(sol_overlay_enabled=not bool(cover),btc_tp_fractions_initial_qty=(.2125,.2125,.575)),
        research_confirmation_bars=confirmation_types() if cover else (),
        max_mark_age_ns=10*HOUR, **kw)


def setup(split=True, cover=None, qty=101.001, side=1, planref=False):
    s=NativeProbe(cfg(split,cover,research_btc_split_planref_v1=planref))
    e=native_engine(s)
    run_ticks(e,[tick(BTC_PERP,1)])
    prepare_day(s,2)
    s._domain.episode=Episode("split-cover",side,10000,1,
        wave_levels=(.01,.02,.03),h=10000)
    marks(s,2)
    ep=s._domain.episode
    intent=s._domain._intent(ep,"BTC_ENTRY",side,None,quantity=qty)
    s._submit_intent(intent,100,100,.01,0,ts_now=2)
    return s,e,ep


@pytest.mark.parametrize("side",[1,-1])
def test_split_exact_odd_lots_first_immediate_second_native_maker_and_fixed_targets(side):
    s,e,ep=setup(side=side)
    try:
        run_ticks(e,[tick(BTC_PERP,3)])
        p=s._split_parent
        assert p["quantity"]==D("101.001")
        assert p["first_quantity"]==D("50.5")
        assert ep.btc_initial_qty==50.5
        assert not any(i.action=="BTC_REDUCE" for i,_,_ in s._queued_intents)
        run_ticks(e,[tick(BTC_PERP,4)])
        orders=[o for o in e.cache.orders_open() if not o.is_reduce_only]
        assert len(orders)==1 and orders[0].is_post_only
        limit=orders[0].price.as_decimal()
        assert (limit<D(100)) if side==1 else (limit>D(100))
        run_ticks(e,[tick(BTC_PERP,5,"99" if side==1 else "101")])
        assert p["filled"]==p["quantity"]==D("101.001")
        assert p["closed"]
        assert ep.btc_initial_qty==101.001
        assert sum(ep.btc_tp_target_lots.values())==int(D("101.001")/BTC_PERP.size_increment.as_decimal())
        assert ep.btc_entry_vwap != 100
        json.dumps(s._split_cover_report())
    finally:
        e.end();e.dispose()


def test_split_partial_first_retries_only_first_and_unknown_ack_blocks_duplicate():
    s,e,ep=setup(qty=100)
    try:
        run_ticks(e,[tick(BTC_PERP,3,size="10")])
        assert s._split_parent["filled"]==D(10)
        run_ticks(e,[tick(BTC_PERP,4,size="10")])
        assert s._split_parent["filled"]==D(20)
        intent=s._split_parent["intent"]
        s._pending_by_order["UNKNOWN_ACK"]=intent
        before=len(e.cache.orders())
        run_ticks(e,[tick(BTC_PERP,5)])
        assert len(e.cache.orders())==before
        s._pending_by_order.pop("UNKNOWN_ACK")
        run_ticks(e,[tick(BTC_PERP,6)])
        assert s._split_parent["filled"]==D(50)
        run_ticks(e,[tick(BTC_PERP,7)])
        assert any(o.is_post_only for o in e.cache.orders_open())
    finally:
        e.end();e.dispose()


@pytest.mark.parametrize("trigger",["deadline","early_tp"])
def test_native_limit_cancel_ack_then_only_remaining_fallback_and_targets(trigger):
    s,e,ep=setup(qty=100)
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4)])
        p=s._split_parent
        when=p["deadline_ns"] if trigger=="deadline" else 5
        price="100" if trigger=="deadline" else "102"
        run_ticks(e,[tick(BTC_PERP,when,price)])
        # Cancel ACK can arrive synchronously, but fallback is a later quote.
        assert p["filled"]==50
        run_ticks(e,[tick(BTC_PERP,when+1,price)])
        assert p["filled"]==p["quantity"]==100
        assert p["completion_reason"]==("DEADLINE" if trigger=="deadline" else "EARLY_TP")
        assert len([o for o in e.cache.orders() if not o.is_reduce_only])==3
        assert sum(ep.btc_tp_target_lots.values())==int(D(100)/BTC_PERP.size_increment.as_decimal())
    finally:
        e.end();e.dispose()


def test_split_delayed_cancel_ack_and_racing_partial_never_exceeds_parent():
    class Delayed(NativeProbe):
        def cancel_order(self,order,*args,**kw):
            if not order.is_reduce_only:
                return
            return super().cancel_order(order,*args,**kw)
    s=Delayed(cfg(True))
    e=native_engine(s)
    try:
        run_ticks(e,[tick(BTC_PERP,1)])
        prepare_day(s,2);marks(s,2)
        ep=s._domain.episode=Episode("race",1,10000,1,wave_levels=(.01,.02,.03))
        i=s._domain._intent(ep,"BTC_ENTRY",1,None,quantity=100)
        s._submit_intent(i,100,100,.01,0,ts_now=2)
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4)])
        p=s._split_parent
        deadline=p["deadline_ns"]
        run_ticks(e,[tick(BTC_PERP,deadline),tick(BTC_PERP,deadline+1)])
        assert p["filled"]==50
        assert len([o for o in e.cache.orders() if not o.is_reduce_only])==2
        run_ticks(e,[tick(BTC_PERP,deadline+2,"99",size="10")])
        assert 50 < p["filled"] <= 100  # Native resting limit may fill beyond displayed quote size.
        run_ticks(e,[tick(BTC_PERP,deadline+3,"99")])
        assert p["filled"]==100
        assert p["closed"]
    finally:
        e.end();e.dispose()


def test_mandatory_close_preempts_second_and_cancels_parent_quantity():
    s,e,ep=setup(qty=100)
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4)])
        s._begin_forced_close("REGIME")
        run_ticks(e,[tick(BTC_PERP,5),tick(SOL_PERP,6),tick(BTC_PERP,7)])
        assert s._split_parent["cancelled"]==50
        assert s._split_parent["filled"]==50
        assert not e.cache.positions_open()
        assert not any(not o.is_reduce_only for o in e.cache.orders_open())
    finally:
        e.end();e.dispose()


def test_pause_stops_entry_remainder_and_fixed_target_basis_has_native_reduce_cap():
    s,e,ep=setup(qty=100)
    try:
        run_ticks(e,[tick(BTC_PERP,3)])
        s._entries_enabled=lambda **kw:False
        run_ticks(e,[tick(BTC_PERP,4)])
        assert s._split_parent["cancelled"]==50
        assert s._split_parent["stop_reason"]=="CLOSE_OR_PAUSE_OR_DP"
        s._domain._ensure_btc_targets(ep)
        assert sum(ep.btc_tp_target_lots.values())==int(D(100)/BTC_PERP.size_increment.as_decimal())
        i=s._domain._intent(ep,"BTC_REDUCE",-1,0,quantity=1000)
        s._submit_intent(i,100,100,.01,0,ts_now=5)
        run_ticks(e,[tick(BTC_PERP,5)])
        assert not e.cache.positions_open()
    finally:
        e.end();e.dispose()


def seed_beta(s,now=1):
    s._cover_returns.extend([(0.001,-.001),(-.001,.001)]*360)
    # Positive estimate required, use beta=1.5 and correlation=1.
    s._cover_returns.clear()
    s._cover_returns.extend([(0.001,.0015),(-.001,-.0015)]*360)
    s._cover_last_hour=now


def cover_setup(coverage="0.5"):
    s,e,ep=setup(split=False,cover=coverage,qty=100)
    seed_beta(s)
    run_ticks(e,[tick(BTC_PERP,3)])
    return s,e,ep


@pytest.mark.parametrize("coverage",["0.5","0.75","1"])
def test_native_base_on_actual_btc_fills_trims_after_tp_and_closes_flat(coverage):
    s,e,ep=cover_setup(coverage)
    try:
        run_ticks(e,[tick(SOL_PERP,4)])
        assert ep.sol_qty==pytest.approx(33.3)
        assert not e.cache.positions_open(instrument_id=SOL_PERP.id)[0].is_long
        assert ep.sol_rights==set()
        i=s._domain._intent(ep,"BTC_REDUCE",-1,0,quantity=50)
        s._submit_intent(i,100,100,.01,0,ts_now=5)
        run_ticks(e,[tick(BTC_PERP,5),tick(SOL_PERP,6)])
        assert ep.sol_qty==pytest.approx(16.6)
        i=s._domain._intent(ep,"BTC_REDUCE",-1,1,quantity=50)
        s._submit_intent(i,100,100,.01,0,ts_now=7)
        run_ticks(e,[tick(BTC_PERP,7),tick(SOL_PERP,8)])
        assert not e.cache.positions_open()
    finally:
        e.end();e.dispose()


def test_cover_partial_base_and_unknown_ack_no_duplicate_native_owner():
    s,e,ep=cover_setup()
    try:
        run_ticks(e,[tick(SOL_PERP,4,size="10")])
        assert ep.sol_qty==10
        i=s._domain._intent(ep,"SOL_ADD",-1,None,quantity=23.3)
        s._pending_by_order["UNKNOWN_ACK"]=i
        before=len(e.cache.orders())
        run_ticks(e,[tick(SOL_PERP,5)])
        assert len(e.cache.orders())==before
        s._pending_by_order.pop("UNKNOWN_ACK")
        run_ticks(e,[tick(SOL_PERP,6)])
        assert ep.sol_qty==pytest.approx(33.3)
        run_ticks(e,[tick(SOL_PERP,7,"105"),tick(SOL_PERP,8,"95")])
        assert ep.sol_qty==pytest.approx(33.3)  # No minute price churn.
    finally:
        e.end();e.dispose()


@pytest.mark.parametrize("coverage",["0.75","1"])
def test_tactical_later_closed_15m_then_future_quote_cap_and_expiry(coverage):
    s,e,ep=cover_setup(coverage)
    try:
        run_ticks(e,[tick(SOL_PERP,4)])
        kind=s.config.research_confirmation_bars[2]
        s.on_bar(bar(kind,5,100,100,100))
        run_ticks(e,[tick(SOL_PERP,6,"101")])  # adverse to short SOL, arms
        assert s._cover_cycle["armed_ns"]==6
        s.on_bar(bar(kind,6,99,101,99))  # same timestamp cannot confirm
        run_ticks(e,[tick(SOL_PERP,7,"100.5")])
        assert not s._cover_cycle["used"]
        s.on_bar(bar(kind,8,98,99,98))
        # Fixture clock is still7; closed bar timestamp8 received on later clock.
        s._cover_confirm=(8,8,s._cover_quote_sequence+1)
        run_ticks(e,[tick(SOL_PERP,9,"100.5")])
        assert s._cover_cycle["used"] and s._cover_cycle["tactical"]
        btc=e.cache.positions_open(instrument_id=BTC_PERP.id)[0]
        sol=e.cache.positions_open(instrument_id=SOL_PERP.id)[0]
        actual=sol.quantity.as_decimal()*D("100.5")*D("1.5")/(btc.quantity.as_decimal()*D(100))
        assert actual<=D(coverage) and actual>D(coverage)-D(".005")
        expiry=s._cover_cycle["expiry_ns"]
        marks(s,expiry)
        run_ticks(e,[tick(SOL_PERP,expiry,"102")])
        assert not s._cover_cycle["tactical"]
        assert ep.sol_qty==pytest.approx(32.6)
    finally:
        e.end();e.dispose()


def test_beta_exact_720_closed_returns_gap_and_no_future_confirmation():
    s=NativeProbe(cfg(False,"0.75"))
    seed_beta(s,10)
    assert s._cover_beta(9) is None
    assert s._cover_beta(10)[0]==pytest.approx(D("1.5"))
    s._cover_returns.pop()
    assert s._cover_beta(10) is None
    with pytest.raises(ValueError,match="GAP"):
        s._cover_seed(((HOUR,100,100),(3*HOUR,101,102)))


def test_default_off_and_single_sol_owner_validation():
    assert not lifecycle_config().research_btc_split50
    assert lifecycle_config().research_sol_cover is None
    with pytest.raises(ValueError,match="SINGLE_OWNER"):
        NativeProbe(lifecycle_config(research_sol_cover=D(".75")))



def test_native_closed_bar_pipeline_tactical_uses_first_future_quote(tmp_path):
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.cache.config import CacheConfig
    from nautilus_trader.data.config import DataEngineConfig
    from nautilus_trader.model.data import BarType, BarSpecification
    from nautilus_trader.model.enums import AccountType, OmsType, AggregationSource, BarAggregation, PriceType
    from nautilus_trader.model.objects import Money
    from nautilus_trader.model.identifiers import ClientId
    from coinmaster.research.native_fixture import SIM
    from coinmaster.venues.marks import venue_mark
    base=1725148800*1_000_000_000
    minute=60_000_000_000
    class Probe(NativeProbe):
        def __init__(self,c):
            super().__init__(c);self.started=False;self.timeline=[]
            seed_beta(self,base)
        def on_quote_tick(self,q):
            if not self.started and q.instrument_id==BTC_PERP.id:
                self.started=True;prepare_day(self,q.ts_event)
                ep=self._domain.episode=Episode("pipeline-cover",1,10000,1,wave_levels=(.5,.6,.7))
                i=self._domain._intent(ep,"BTC_ENTRY",1,None,requested_notional=10000)
                self._queued_intents.append((i,.01,0))
                self._queued_intent_ready_ns[i.id]=q.ts_event
            if q.instrument_id==SOL_PERP.id:
                self.timeline.append(("QUOTE",q.ts_event,self._cover_quote_sequence+1))
            super().on_quote_tick(q)
        def on_bar(self,b):
            if b.bar_type.instrument_id==SOL_PERP.id:
                self.timeline.append(("BAR",b.ts_event,self.clock.timestamp_ns()))
            super().on_bar(b)
    s=Probe(cfg(False,"0.75"))
    e=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR"),
        cache=CacheConfig(bar_capacity=128),data_engine=DataEngineConfig(time_bars_build_with_no_updates=False)))
    e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,
        starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,bar_execution=False)
    e.add_instrument(BTC_PERP);e.add_instrument(SOL_PERP);e.add_strategy(s)
    source=[];mark_rows=[];quotes=[]
    for m in range(1,62):
        ts=base+m*minute
        sp=D(100) if m<=15 or m>=50 else D(101) if m<=30 else D("100.5")
        for inst,price in ((BTC_PERP,D(100)),(SOL_PERP,sp)):
            kind=BarType(inst.id,BarSpecification(1,BarAggregation.MINUTE,PriceType.LAST),AggregationSource.EXTERNAL)
            source.append(bar(kind,ts,price,price,price))
            mark_rows.append(venue_mark(inst.id,price,ts))
            quotes.append(tick(inst,ts,str(price)))
    try:
        e.add_data(source,sort=False);e.add_data(mark_rows,client_id=ClientId("TEST_MARKS"),sort=False)
        e.add_data(quotes,sort=False);e.sort_data();e.run(streaming=True);e.clear_data()
        tactical=[r for r in s.cover_audit if r["event"]=="COVER_TARGET" and r["tactical"]]
        assert len(tactical)==1, (s.cover_audit,s._cover_cycle,s._cover_confirm,s.timeline)
        assert tactical[0]["timestamp_ns"]==base+46*minute
        assert tactical[0]["confirmation_ns"]==base+45*minute
        assert tactical[0]["confirmation_receipt_ns"]==base+45*minute
        assert not s._cover_cycle["tactical"] and s._cover_cycle["used"]
        adds=[r for r in s.fill_audit if r["action"]=="SOL_ADD"]
        assert len(adds)==2
        assert s._domain.episode.sol_qty==pytest.approx(33.3)
        (tmp_path/"native-cover-proof.json").write_text(json.dumps(s._split_cover_report(),indent=2))
    finally:
        e.end();e.dispose()


def test_split_denied_child_cancels_accepted_remainder_without_extra_orders():
    s,e,ep=setup(qty=100)
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4)])
        oid=next(oid for oid,i in s._pending_by_order.items() if i.action=="BTC_ENTRY")
        s._terminal_without_fill(oid)
        assert s._split_parent["stop_reason"]=="NATIVE_DENIED_OR_REJECTED_OR_EXPIRED"
        assert s._split_parent["filled"]+s._split_parent["cancelled"]==100
        run_ticks(e,[tick(BTC_PERP,5)])
        assert s._split_parent["filled"]==50
    finally:
        e.end();e.dispose()


def test_split_dp_latch_cancels_waiting_parent_before_next_quote():
    # Existing deposit executor owns actual flatten; this test isolates the
    # same parent cancellation boundary it invokes.
    s,e,ep=setup(qty=100)
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4)])
        s._split_stop("DP")
        run_ticks(e,[tick(BTC_PERP,5)])
        assert s._split_parent["filled"]==50
        assert s._split_parent["cancelled"]==50
        assert not any(not o.is_reduce_only for o in e.cache.orders_open())
    finally:
        e.end();e.dispose()


def test_joint_margin_reserves_full_btc_plan_and_mandatory_sol_not_double_child():
    s,e,ep=setup(split=True,cover="0.5",qty=100)
    try:
        seed_beta(s,1)
        ep.btc_net_planned_qty=100
        assert s._split_cover_margin_reserve(BTC_PERP.id,D(50),2)==100
        sol=s._split_cover_margin_reserve(SOL_PERP.id,D(0),2)
        assert float(sol)==pytest.approx(-100/3)
        run_ticks(e,[tick(BTC_PERP,3)])
        assert s._split_cover_margin_reserve(BTC_PERP.id,D(100),4)==100
        assert float(s._split_cover_margin_reserve(SOL_PERP.id,D("-16"),4))==pytest.approx(-100/3)
    finally:
        e.end();e.dispose()



@pytest.mark.parametrize("selection",["deferred","zero_net"])
def test_native_omitted_zero_parent_exact_q_two_children_reference_h_and_causal_rights(selection):
    from nautilus_trader.model.data import QuoteTick
    conf=cfg(True)
    if selection=="zero_net":
        conf=conf.__replace__(research_v0_zero_tp_netting=True,research_v0_deferred_selective_zero_tp=False)
    s=NativeProbe(conf)
    e=native_engine(s)
    def spread(ts):
        return QuoteTick(BTC_PERP.id,BTC_PERP.make_price(D(99)),BTC_PERP.make_price(D(100)),
            BTC_PERP.make_qty(D(1000)),BTC_PERP.make_qty(D(1000)),ts,ts)
    try:
        run_ticks(e,[tick(BTC_PERP,1)])
        prepare_day(s,2);marks(s,2)
        ep=s._domain.episode=Episode("omitted",1,10000,1,wave_levels=(0,.02,.03))
        i=s._domain._intent(ep,"BTC_ENTRY",1,None,requested_notional=10000)
        if selection=="deferred":
            s._queued_intents.append((i,.01,0));s._queued_intent_ready_ns[i.id]=2
            run_ticks(e,[spread(2),spread(3)])
        else:
            s._submit_intent(i,100,100,.01,0,ts_now=2)
            run_ticks(e,[tick(BTC_PERP,3)])
        p=s._split_parent
        assert p["quantity"]==D("78.750")
        assert p["filled"]==D("39.375")
        reference=dict(ep.btc_reference_target_lots)
        h=ep.h
        assert ep.btc_reference_qty==100
        assert ep.btc_net_planned_qty==78.75
        assert ep.sol_right_fraction[0]==.5
        assert 0 not in ep.sol_rights if selection=="deferred" else 0 in ep.sol_rights
        run_ticks(e,[spread(4),tick(BTC_PERP,5,"99")])
        assert p["filled"]==p["quantity"]==D("78.750")
        assert ep.btc_initial_qty==78.75
        assert ep.btc_reference_qty==100
        assert ep.btc_net_planned_qty==78.75
        assert ep.btc_reference_target_lots==reference
        assert ep.h==pytest.approx(ep.btc_reference_qty*ep.btc_entry_vwap/ep.beta_entry)
        assert ep.h<h  # Same V3 formula; actual discounted VWAP changes the monetary H.
        assert ep.sol_right_fraction[0]==1
        assert sum(ep.btc_tp_target_lots.values())==78750
        assert len([o for o in e.cache.orders() if not o.is_reduce_only])==2
    finally:
        e.end();e.dispose()


@pytest.mark.parametrize("reason",["REGIME","TRAIL"])
def test_daily_mandatory_close_preempts_unfinished_split_parent(reason):
    s,e,ep=setup(qty=100)
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4)])
        prepare_day(s,5,-1 if reason=="REGIME" else 1)
        ep.best_f=.2 if reason=="TRAIL" else 0
        WaveOverlayStrategy._advance_current_day(s)
        assert s._forced_close_reason==reason
        assert s._split_parent["closed"]
        assert s._split_parent["cancelled"]==50
        run_ticks(e,[tick(BTC_PERP,6),tick(SOL_PERP,7),tick(BTC_PERP,8)])
        assert not e.cache.positions_open()
        assert s._split_parent["filled"]==50
    finally:
        e.end();e.dispose()


def test_permanent_cover_has_no_legacy_sol_hard_timeout_owner():
    from datetime import datetime, UTC, timedelta
    s,e,ep=cover_setup()
    try:
        run_ticks(e,[tick(SOL_PERP,4)])
        ep.sol_first_fill_at=datetime(1970,1,1,tzinfo=UTC)-timedelta(days=100)
        WaveOverlayStrategy._advance_current_day(s)
        assert not s._mandatory_sol_exit
        run_ticks(e,[tick(SOL_PERP,5)])
        assert ep.sol_qty==pytest.approx(33.3)
        assert not any(i.reason=="SOL_HARD_TIMEOUT" for i in ep.pending.values())
    finally:
        e.end();e.dispose()


def test_paused_base_retries_on_first_resumed_quote():
    s,e,ep=cover_setup()
    try:
        s._entries_enabled=lambda **kw:False
        run_ticks(e,[tick(SOL_PERP,4)])
        assert ep.sol_qty==0
        s._entries_enabled=lambda **kw:True
        run_ticks(e,[tick(SOL_PERP,5)])
        assert ep.sol_qty==pytest.approx(33.3)
        run_ticks(e,[tick(SOL_PERP,6)])
        assert ep.sol_qty==pytest.approx(33.3)
    finally:
        e.end();e.dispose()


def test_denied_base_retries_after_explicit_one_hour_admission_cooldown():
    s,e,ep=cover_setup()
    try:
        s._tier_allows_increase=lambda *args:False
        run_ticks(e,[tick(SOL_PERP,4)])
        assert ep.sol_qty==0
        s._tier_allows_increase=lambda *args:True
        run_ticks(e,[tick(SOL_PERP,5)])
        assert ep.sol_qty==0
        when=4+HOUR
        marks(s,when)
        run_ticks(e,[tick(SOL_PERP,when)])
        assert ep.sol_qty==pytest.approx(33.3)
        assert s.pre_submit_gate_blocks[-1]["action"]=="SOL_ADD"
    finally:
        e.end();e.dispose()


def test_hourly_five_pp_drift_rebalances_on_future_quote_not_every_price_tick():
    s,e,ep=cover_setup()
    try:
        run_ticks(e,[tick(SOL_PERP,4)])
        marks(s,5,"100","200")
        run_ticks(e,[tick(SOL_PERP,5,"200")])
        assert ep.sol_qty==pytest.approx(33.3)
        for kind in (s.config.research_confirmation_bars[1],s.config.research_confirmation_bars[3]):
            s.on_bar(bar(kind,HOUR,100 if kind.instrument_id==BTC_PERP.id else 200))
        marks(s,HOUR+1,"100","200")
        run_ticks(e,[tick(SOL_PERP,HOUR+1,"200")])
        assert ep.sol_qty==pytest.approx(16.6)
        rows=[r for r in s.cover_audit if r["event"]=="COVER_HOURLY_DRIFT"]
        assert len(rows)==1 and D(rows[0]["actual"])==pytest.approx(D(".999"))
    finally:
        e.end();e.dispose()


def test_one_lot_parent_is_explicit_immediate_rounding_exception_with_exact_q():
    s,e,ep=setup(qty=.001)
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4)])
        p=s._split_parent
        assert p["single_lot_immediate"]
        assert p["filled"]==p["quantity"]==D(".001")
        assert p["cancelled"]==0
        assert len([o for o in e.cache.orders() if not o.is_reduce_only])==1
    finally:
        e.end();e.dispose()


def test_partial_tactical_rechecks_quality_and_does_not_buy_fallback():
    s,e,ep=cover_setup("0.75")
    try:
        run_ticks(e,[tick(SOL_PERP,4)])
        c=s._cover_cycle
        c["armed_ns"]=5
        s._cover_confirm=(6,6,s._cover_quote_sequence+1)
        run_ticks(e,[tick(SOL_PERP,7,"100.5",size="1")])
        assert c["tactical"] and c["tactical_fill_qty"]==1
        assert c["tactical_fill_notional"]==D("100.50")
        assert c["tactical_fill_fees"]==D("0.10050000")
        held=ep.sol_qty
        # Anchor is restored, but actual fee basis still forbids net-negative
        # fee exits. A bad-price quote cannot complete optional entry leaves.
        run_ticks(e,[tick(SOL_PERP,8,"100.1")])
        assert ep.sol_qty==held
        assert not any(i.action=="SOL_ADD" for i in s._pending_by_order.values())
        # Native actual basis, not stale submission quote, controls net gate.
        c["tactical_fill_notional"]=D("99")
        c["tactical_fill_fees"]=D("2")
        run_ticks(e,[tick(SOL_PERP,9,"100")])
        assert c["tactical"]
        after_window=c["start_ns"]+4*HOUR+1
        marks(s,after_window)
        run_ticks(e,[tick(SOL_PERP,after_window,"101")])
        assert ep.sol_qty==held  # Still a better price, but optional4h window is over.
        expiry=c["expiry_ns"]
        marks(s,expiry)
        run_ticks(e,[tick(SOL_PERP,expiry,"102")])
        assert not c["tactical"]
        assert ep.sol_qty==pytest.approx(32.6)
    finally:
        e.end();e.dispose()



def test_pending_btc_without_native_fill_does_not_start_sol_anchor_or_tactic_window():
    s=NativeProbe(cfg(False,"0.75"))
    e=native_engine(s)
    try:
        run_ticks(e,[tick(BTC_PERP,1)])
        prepare_day(s,2);seed_beta(s,1)
        ep=s._domain.episode=Episode("pending-no-anchor",1,10000,1,wave_levels=(.01,.02,.03))
        s._domain._intent(ep,"BTC_ENTRY",1,None,requested_notional=10000)
        run_ticks(e,[tick(SOL_PERP,3,"100"),tick(SOL_PERP,4,"110")])
        assert s._cover_cycle is None
        assert not s.cover_audit
        assert not e.cache.positions_open()
    finally:
        e.end();e.dispose()


def test_initial_base_anchor_is_actual_native_partial_fill_vwap_and_freezes():
    s,e,ep=cover_setup("0.75")
    try:
        # No SOL book is cached: the submit quote100 does not become a fill.
        s._cover_check(tick(SOL_PERP,4,"100"))
        c=s._cover_cycle
        assert c["anchor"] is None and not c["base_anchor_complete"]
        assert not c["used"]
        run_ticks(e,[tick(SOL_PERP,5,"101",size="1")])
        assert c["anchor"]==101 and not c["base_anchor_complete"]
        run_ticks(e,[tick(SOL_PERP,6,"102")])
        assert c["base_anchor_complete"]
        assert 101<c["anchor"]<102
        assert c["anchor"]==c["base_anchor_notional"]/c["base_anchor_qty"]
        assert c["base_anchor_qty"]==D("33.3")
        assert c["start_ns"]==5
        fixed=c["anchor"]
        # Later completed-hour rebalance changes core SOL without rewriting
        # the anchor of the initial native base budget.
        for kind in (s.config.research_confirmation_bars[1],s.config.research_confirmation_bars[3]):
            s.on_bar(bar(kind,HOUR,100 if kind.instrument_id==BTC_PERP.id else 200))
        marks(s,HOUR+1,"100","200")
        run_ticks(e,[tick(SOL_PERP,HOUR+1,"200")])
        assert c["anchor"]==fixed
    finally:
        e.end();e.dispose()


@pytest.mark.parametrize("side",[1,-1])
def test_planref_v1_freezes_completed_first_leg_but_native_vwap_h_and_targets_qty_stay_actual(side):
    from coinmaster.domain.wave_overlay import btc_management_price
    s,e,ep=setup(qty=100,side=side,planref=True)
    try:
        run_ticks(e,[tick(BTC_PERP,3)])
        p=s._split_parent
        assert ep.btc_planref_vwap==D(100)
        assert p["management_reference_frozen_ns"]==3
        run_ticks(e,[tick(BTC_PERP,4),tick(BTC_PERP,5,"99" if side==1 else "101")])
        assert p["filled"]==p["quantity"]==100
        assert ep.btc_entry_vwap!=100
        assert btc_management_price(ep)==100
        assert ep.h==pytest.approx((ep.btc_reference_qty or ep.btc_initial_qty)*ep.btc_entry_vwap/ep.beta_entry)
        assert ep.btc_entry_notional_exact/ep.btc_entry_qty_exact!=D(100)
        native=e.cache.positions_open()[0]
        fees=sum((D(str(fee).split()[0]) for fee in native.to_dict()["commissions"]),D(0))
        assert fees>0
        assert native.realized_pnl.as_decimal()==-fees
        assert native.avg_px_open==pytest.approx(ep.btc_entry_vwap)
        cash=e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()
        assert cash==D(10000)-fees
        targets=s._domain.plan_confirmed_btc_targets()
        queued=[i for i,_,_ in s._queued_intents if i.action=="BTC_REDUCE"]
        all_targets=targets+queued
        assert all_targets
        for i in all_targets:
            assert i.limit_price==pytest.approx(100*(1+side*ep.wave_levels[i.level]))
        assert sum(ep.btc_tp_target_lots.values())==100000
    finally:
        e.end();e.dispose()


def test_planref_v1_partial_first_leg_cannot_freeze_or_invent_completion():
    s,e,ep=setup(qty=100,planref=True)
    try:
        run_ticks(e,[tick(BTC_PERP,3,size="10"),tick(BTC_PERP,4,"100.2",size="10")])
        assert ep.btc_planref_vwap is None
        assert s._split_parent["first_filled"]==20
        run_ticks(e,[tick(BTC_PERP,5,"100.4")])
        p=s._split_parent
        expected=(D(10)*100+D(10)*D("100.2")+D(30)*D("100.4"))/50
        assert ep.btc_planref_vwap==expected==p["first_vwap"]
        assert p["management_reference_frozen_ns"]==5
        run_ticks(e,[tick(BTC_PERP,6,"100.4"),tick(BTC_PERP,7,"99")])
        assert ep.btc_planref_vwap==expected
        assert p["filled"]==p["quantity"]
    finally:
        e.end();e.dispose()


def test_planref_v1_daily_trail_uses_planref_and_unmodified_strict_three_percent_rule():
    from dataclasses import replace
    s,e,ep=setup(qty=100,side=-1,planref=True)
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,5,"101")])
        assert ep.btc_entry_vwap>100 and ep.btc_planref_vwap==100
        prepare_day(s,6,-1)
        for feature in s._current_signals:
            feature.z=None
        s._bars[-1]=replace(s._bars[-1],btc_close=96.99)
        WaveOverlayStrategy._advance_current_day(s)
        assert ep.best_f==pytest.approx(.0301)
        prepare_day(s,7,-1)
        for feature in s._current_signals:
            feature.z=None
        s._bars[-1]=replace(s._bars[-1],btc_close=100)
        WaveOverlayStrategy._advance_current_day(s)
        assert s._forced_close_reason=="TRAIL"
    finally:
        e.end();e.dispose()


def test_planref_v1_early_tp_accelerates_cancel_ack_path_and_keeps_reference():
    s,e,ep=setup(qty=100,planref=True)
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,5,"102")])
        assert s._split_parent["completion_reason"]=="EARLY_TP"
        assert s._split_parent["filled"]==50
        run_ticks(e,[tick(BTC_PERP,6,"102")])
        assert s._split_parent["filled"]==100
        assert ep.btc_entry_vwap==101 and ep.btc_planref_vwap==100
    finally:
        e.end();e.dispose()


def test_planref_v1_default_off_retains_actual_blended_management_reference():
    from coinmaster.domain.wave_overlay import btc_management_price
    s,e,ep=setup(qty=100)
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,5,"99")])
        assert ep.btc_planref_vwap is None
        assert btc_management_price(ep)==ep.btc_entry_vwap!=100
    finally:
        e.end();e.dispose()


@pytest.mark.parametrize("split,discount",[(False,"0.0025"),(True,"0.005")])
def test_planref_v1_requires_explicit_btc025_split(split,discount):
    with pytest.raises(ValueError,match="PLANREF_V1_REQUIRES_BTC025_SPLIT"):
        NativeProbe(cfg(split,research_btc_split_discount=D(discount),research_btc_split_planref_v1=True))


def test_planref_v1_mandatory_close_before_first_leg_complete_cancels_truthful_leaves():
    from coinmaster.domain.wave_overlay import btc_management_price
    s,e,ep=setup(qty=100,planref=True)
    try:
        run_ticks(e,[tick(BTC_PERP,3,size="10")])
        assert ep.btc_planref_vwap is None
        assert btc_management_price(ep)==ep.btc_entry_vwap==100
        prepare_day(s,4,-1)
        WaveOverlayStrategy._advance_current_day(s)
        assert s._forced_close_reason=="REGIME"
        assert s._split_parent["filled"]==10
        assert s._split_parent["cancelled"]==90
        run_ticks(e,[tick(BTC_PERP,5),tick(SOL_PERP,6),tick(BTC_PERP,7)])
        assert not e.cache.positions_open()
        assert ep.btc_planref_vwap is None
        assert s._split_parent["filled"]+s._split_parent["cancelled"]==100
    finally:
        e.end();e.dispose()


def test_planref_v1_freeze_preserves_real_native_tp_and_sol_right():
    s,e,ep=setup(qty=100,planref=True)
    try:
        run_ticks(e,[tick(BTC_PERP,3,size="10")])
        reduction=s._domain._intent(ep,"BTC_REDUCE",-1,0,quantity=1,reason="BTC_TP1")
        s._submit_intent(reduction,100,100,.01,0,ts_now=3)
        run_ticks(e,[tick(BTC_PERP,4,"100",size="1")])
        assert 0 in ep.sol_rights
        before=(set(ep.btc_filled_tps),set(ep.sol_rights),dict(ep.sol_right_fraction))
        run_ticks(e,[tick(BTC_PERP,5,"100.4")])
        assert ep.btc_planref_vwap is not None
        assert (set(ep.btc_filled_tps),set(ep.sol_rights),dict(ep.sol_right_fraction))==before
        p=s._split_parent
        assert p["planref_v1_p0"]==ep.btc_planref_vwap
        assert p["planref_v1_actual_blended_vwap"]==ep.btc_entry_notional_exact/ep.btc_entry_qty_exact
        assert p["planref_v1_h_actual"]==pytest.approx(p["planref_v1_gross_reference_qty"]*ep.btc_entry_vwap/p["planref_v1_beta"])
    finally:
        e.end();e.dispose()
