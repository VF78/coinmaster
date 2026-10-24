"""Connected native acceptance of paired state; no economic calendar replays."""
from decimal import Decimal as D
import json
import pytest
from coinmaster.strategy.paired_prefix import PairedCaps, sol_prices, sol_allocations
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
from test_native_split_cover import cfg
from test_native_btc_sizing import prepare_day
from test_native_episode_risk import marks
from coinmaster.domain.wave_overlay import Candidate, Episode
from coinmaster.research.native_fixture import SIM, perpetual
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.objects import Money
from test_native_episode_risk import tick, run_ticks, NativeProbe


@pytest.mark.parametrize("side", [1, -1])
def test_price_fee_floor_stop_and_exact_lot_rights(side):
    prices, stop = sol_prices(D(100), D(".01"), side, D(".01"))
    assert all(side * (b-a) > 0 for a, b in zip((D(100),) + prices, prices))
    assert all(side * (p-D(100)) - D(".00055") * (D(100) + p) > 0 for p in prices)
    assert side * (D(100)-stop) > 0
    assert sol_allocations(101, set()) == {0:25, 1:25, 2:51}
    assert sol_allocations(75, {0}) == {1:25, 2:50}


def test_absolute_caps_actual_partial_zero_unknown_inactive_and_no_recursion():
    c = PairedCaps(D(100), D(1), D(1), D(1)); c.entry_terminal(D(100))
    assert c.reconcile(D(100), D(75), sol_reduced=True, btc_reduced=False, active_risk=True) == (D(25), D(0))
    assert c.reconcile(D(75), D(75), sol_reduced=False, btc_reduced=True, active_risk=True) == (D(0), D(0))
    assert c.bmax == D(75) and c.solmax == D(75)
    assert c.reconcile(D(75), D(70), sol_reduced=True, btc_reduced=False, active_risk=True) == (D(5), D(0))
    assert c.reconcile(D(70), D(0), sol_reduced=True, btc_reduced=True, active_risk=False) == (D(0), D(0))
    assert c.bmax == D(70)  # Inactive close cannot forgive earlier debt or restore.
    for actual, expected in ((D(20), D(10)), (D(0), D(0))):
        partial = PairedCaps(D(100), D(2), D(1), D(1)); partial.entry_terminal(actual)
        assert partial.bmax == expected


def selected(s, ns=10, a="2", side=1):
    row={"t":ns,"valid":True,"B2_1":side==1,"B2_-1":side==-1,
         "F0_1":True,"F0_-1":True,"K_1":"110","K_-1":"90","O":"110",
         "ATR_SOL":"2","PB":"100","PS":"100","a":a}
    s._pair_start(row,ns)


class Probe(NativeProbe):
    def __init__(self, config):
        self.native_fill_events=[]
        self.native_cancel_events=[]
        super().__init__(config.__replace__(research_paired_prefix="B2_F0", research_btc_q_mode="CLEAN_Q"))

    def on_order_filled(self,event):
        self.native_fill_events.append(event)
        return super().on_order_filled(event)

    def on_order_canceled(self,event):
        self.native_cancel_events.append(event)
        return super().on_order_canceled(event)


def native_setup(side=1, a="2", probe=Probe, modules=()):
    config=cfg(True,research_btc_real_u=True,research_btc_q_mode="CLEAN_Q", research_sol_off=True,
        research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,research_btc_split_discount=D(".005"))
    config=config.__replace__(candidate=Candidate(sol_overlay_enabled=False,btc_tp_fractions_initial_qty=(.2125,.2125,.575)))
    s=probe(config)
    e=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,
        starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,
        default_leverage=D(1),liquidity_consumption=True,bar_execution=False,modules=list(modules))
    for inst in (BTC_PERP,SOL_PERP):
        e.add_instrument(perpetual(inst.raw_symbol.value,inst.base_currency,
            str(inst.price_increment),str(inst.size_increment),str(inst.margin_init),
            maker_fee=D(".00020"),taker_fee=D(".00055")))
    e.add_strategy(s)
    run_ticks(e,[tick(BTC_PERP,1)])
    prepare_day(s,2);marks(s,2)
    ep=s._domain.episode=Episode("paired",side,10000,1,wave_levels=(0,0,.03),h=10000)
    intent=s._domain._intent(ep,"BTC_ENTRY",side,None,quantity=100)
    s._submit_intent(intent,100,100,.01,0,ts_now=2)
    run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(SOL_PERP,5)])
    selected(s,a=a,side=side)
    return s,e,ep


def test_native_partial_ioc_entry_capacity_debt_real_tp_stop_and_no_increase():
    s,e,ep=native_setup()
    try:
        assert s._pair["branch"] == "B2"  # deterministic tie priority
        assert s._pair_no_increase()
        eligible=s._pair["eligible_ns"]
        run_ticks(e,[tick(BTC_PERP,eligible),tick(SOL_PERP,eligible,size="10")])
        run_ticks(e,[tick(BTC_PERP,eligible+1),tick(SOL_PERP,eligible+1,size="10")])
        p=s._pair
        assert p["entry_terminal"] and p["entry_qty"] == D(10), json.dumps(s._pair_report())
        assert p["caps"].bmax == D(5), json.dumps(s._pair_report())
        assert p["p0"] == D(100)
        assert not any(o.instrument_id == BTC_PERP.id and not o.is_reduce_only for o in e.cache.orders_open())
        for dt in (2,3,4):
            run_ticks(e,[tick(BTC_PERP,eligible+dt),tick(SOL_PERP,eligible+dt,size="10")])
        assert s._pair_qty(BTC_PERP.id) == D(5), json.dumps(s._pair_report())
        assert s._pair_qty(SOL_PERP.id) == D(10)
        native=[o for o in e.cache.orders_open() if o.instrument_id==SOL_PERP.id]
        assert len(native)==4 and all(o.is_reduce_only for o in native)
        assert sum((o.leaves_qty.as_decimal() for o in native if o.order_type.name=="LIMIT"),D(0))==D(10)
        assert len([o for o in native if o.order_type.name=="STOP_MARKET" and o.time_in_force.name=="IOC"])==1
        assert not s._pair_failures, json.dumps(s._pair_report())
        json.loads(json.dumps(s._pair_report()))
    finally:
        e.end();e.dispose()


def covered(s,e,size="1000"):
    t=s._pair["eligible_ns"]
    for dt in range(5):
        run_ticks(e,[tick(BTC_PERP,t+dt),tick(SOL_PERP,t+dt,size=size)])
    return t+5


@pytest.mark.parametrize("side",[1,-1])
def test_native_tp_permanent_btc_trim_no_recursive_sol_cut_and_consumed_right(side):
    s,e,ep=native_setup(side=side,a=".2")
    try:
        t=covered(s,e)
        p=s._pair; assert p["entry_qty"]==D(10)
        solprice="99" if side==1 else "101"
        for dt in range(4):
            run_ticks(e,[tick(BTC_PERP,t+dt),tick(SOL_PERP,t+dt,solprice,size="2.5")])
        assert p["caps"].bmax==D("37.5"),json.dumps(s._pair_report())
        assert s._pair_qty(BTC_PERP.id)==D("37.5"),json.dumps(s._pair_report())
        assert s._pair_qty(SOL_PERP.id)==D("7.5"),json.dumps(s._pair_report())
        assert p["consumed"]=={0}
        assert not any(o["kind"]=="TP" and o["level"]==0 for _,o,_ in s._pair_work())
        assert not s._pair_failures,json.dumps(s._pair_report())
    finally:
        e.end();e.dispose()


def test_native_invalidation_closes_sol_without_new_btc_debt_and_no_rearm():
    s,e,ep=native_setup(a=".2")
    try:
        t=covered(s,e);p=s._pair;p["boundary"]=D("100.2")
        for dt in range(4):
            run_ticks(e,[tick(BTC_PERP,t+dt,"100.2"),tick(SOL_PERP,t+dt)])
        assert p["risk"]=="INACTIVE_RISK"
        assert s._pair_qty(BTC_PERP.id)==D(50),json.dumps(s._pair_report())
        assert s._pair_qty(SOL_PERP.id)==0
        assert p["caps"].bmax==D(50)
        assert p["parent"] in s._pair_used and s._pair_no_increase()
    finally:
        e.end();e.dispose()


def test_native_zero_ioc_terminal_forces_full_btc_risk_close():
    s,e,ep=native_setup(a=".2")
    try:
        t=s._pair["eligible_ns"]
        for dt in (0,60_000_000_000,60_000_000_001,60_000_000_002,60_000_000_003):
            run_ticks(e,[tick(BTC_PERP,t+dt),tick(SOL_PERP,t+dt,size="0")])
        assert s._pair_qty(SOL_PERP.id)==0
        assert s._pair_qty(BTC_PERP.id)==0,json.dumps(s._pair_report())
        assert "ENTRY_TERMINAL_TIMEOUT" in s._pair_failures
        assert s._pair is not None  # Unconfirmed native cancel remains NO_GO, never hidden.
    finally:
        e.end();e.dispose()


def test_native_btc_e_callback_cannot_send_sol_entry_against_previous_quote():
    s,e,ep=native_setup(a=".2")
    try:
        t=s._pair["eligible_ns"]
        run_ticks(e,[tick(BTC_PERP,t)])
        assert not any(o["kind"]=="ENTRY" for o in s._pair_orders.values())
        assert s.cache.quote_tick(SOL_PERP.id).ts_event==5
        run_ticks(e,[tick(SOL_PERP,t)])
        assert len([o for o in s._pair_orders.values() if o["kind"]=="ENTRY"])==1
        assert any(r["event"]=="ACTUAL_FILL" and r["kind"]=="ENTRY" and int(r["timestamp_ns"])>=t for r in s.paired_prefix_audit)
    finally:e.end();e.dispose()


def test_native_risk_recovered_before_first_executable_sol_quote_consumes_no_entry():
    s,e,ep=native_setup(a=".2")
    try:
        p=s._pair;p["boundary"]=D("100.2");t=p["eligible_ns"]
        run_ticks(e,[tick(BTC_PERP,t,"100.2"),tick(SOL_PERP,t)])
        assert p["risk"]=="INACTIVE_RISK" and p["entry_terminal"]
        assert not s._pair_orders and s._pair_qty(SOL_PERP.id)==0
        assert p["caps"].bmax==D(50) and s._pair_qty(BTC_PERP.id)==D(50)
        assert p["parent"] in s._pair_used
    finally:e.end();e.dispose()


def test_native_actual_fill_debt_clock_and_first_next_minute_execution():
    s,e,ep=native_setup(a=".2")
    try:
        t=covered(s,e)
        run_ticks(e,[tick(BTC_PERP,t),tick(SOL_PERP,t,"99",size="2.5")])
        p=s._pair
        assert p["debt_since"]==t,json.dumps(s._pair_report())
        assert s._pair_qty(BTC_PERP.id)==D(50)
        # Cancel ACK was requested on the causal SOL fill, not on this quote.
        run_ticks(e,[tick(BTC_PERP,t+60_000_000_000),tick(SOL_PERP,t+60_000_000_000,"99",size="2.5")])
        assert s._pair_qty(BTC_PERP.id)==D("37.5"),json.dumps(s._pair_report())
        assert not s._pair_failures,json.dumps(s._pair_report())
        targets=[o for o in e.cache.orders_open() if o.instrument_id==BTC_PERP.id and o.is_reduce_only]
        assert len(targets)==3 and sum((o.leaves_qty.as_decimal() for o in targets),D(0))==D("37.5")
    finally:e.end();e.dispose()


def test_native_btc_tp_cap_trim_creates_only_absolute_rounding_deficit():
    s,e,ep=native_setup(a=".2")
    try:
        t=covered(s,e)
        for dt in range(5):
            run_ticks(e,[tick(BTC_PERP,t+dt,"101"),tick(SOL_PERP,t+dt)])
        p=s._pair
        assert s._pair_qty(BTC_PERP.id)==D(39),json.dumps(s._pair_report())
        assert s._pair_qty(SOL_PERP.id)==D("7.8"),json.dumps(s._pair_report())
        assert p["caps"].bmax==D(39) and p["caps"].solmax==D("7.8")
        assert not s._pair_failures,json.dumps(s._pair_report())
    finally:e.end();e.dispose()


def test_native_partial_ioc_stop_remains_no_go_and_closes_actual_both_legs():
    s,e,ep=native_setup(a=".2")
    try:
        t=covered(s,e)
        run_ticks(e,[tick(BTC_PERP,t),tick(SOL_PERP,t,"102",size="3")])
        assert "PARTIAL_NATIVE_STOP" in s._pair_failures
        for dt in range(1,5):
            run_ticks(e,[tick(BTC_PERP,t+dt),tick(SOL_PERP,t+dt,"102",size="7.1")])
        assert s._pair_qty(BTC_PERP.id)==0 and s._pair_qty(SOL_PERP.id)==0,json.dumps(s._pair_report())
        assert not s._pair_work() and s._pair is None,json.dumps(s._pair_report())
        assert not e.cache.orders_open() and not e.cache.orders_inflight()
    finally:e.end();e.dispose()


class HeldTransportProbe(Probe):
    def submit_order(self,order,*args,**kwargs):
        owner=self._pair_orders.get(str(order.client_order_id))
        if owner and owner["kind"]=="ENTRY" and not hasattr(self,"held_entry"):
            self.held_entry=order
            return
        return super().submit_order(order,*args,**kwargs)

    def release_native_entry_transport(self):
        return super().submit_order(self.held_entry)


def test_native_late_entry_after_btc_flat_cancel_request_never_recreates_btc():
    s,e,ep=native_setup(a=".2",probe=HeldTransportProbe)
    try:
        t=s._pair["eligible_ns"]
        run_ticks(e,[tick(BTC_PERP,t),tick(SOL_PERP,t)])
        assert hasattr(s,"held_entry") and s._pair_qty(SOL_PERP.id)==0
        for dt in (1,2,3):
            run_ticks(e,[tick(BTC_PERP,t+dt,"103")])
        assert s._pair_qty(BTC_PERP.id)==0 and s._pair is not None
        s.release_native_entry_transport()
        for dt in range(4,8):
            run_ticks(e,[tick(BTC_PERP,t+dt,"103"),tick(SOL_PERP,t+dt)])
        assert s._pair_qty(BTC_PERP.id)==0 and s._pair_qty(SOL_PERP.id)==0,json.dumps(s._pair_report())
        assert s._pair is None and not s._pair_work() and not e.cache.orders_inflight()
        fills=[r for r in s.paired_prefix_audit if r["event"]=="ACTUAL_FILL"]
        assert any(r["kind"]=="ENTRY" for r in fills) and any(r["kind"]=="SOL_CLOSE" for r in fills)
    finally:e.end();e.dispose()


class OversizeCapProbe(Probe):
    def _pair_submit(self,instrument,side,qty,kind,ns,**kwargs):
        if kind=="SOL_CAP" and not hasattr(self,"injected_oversize"):
            self.injected_oversize=True
            qty*=2  # Fault injection is an ACTUAL native order, never a fake fill.
        return super()._pair_submit(instrument,side,qty,kind,ns,**kwargs)


def test_native_late_oversize_btc_caused_cap_actual_deficit_is_not_deduplicated_away():
    s,e,ep=native_setup(a=".2",probe=OversizeCapProbe)
    try:
        t=covered(s,e)
        for dt in range(6):
            run_ticks(e,[tick(BTC_PERP,t+dt,"101"),tick(SOL_PERP,t+dt)])
        assert s.injected_oversize
        assert s._pair_qty(SOL_PERP.id)==D("5.6"),json.dumps(s._pair_report())
        assert s._pair_qty(BTC_PERP.id)==D(28),json.dumps(s._pair_report())
        assert s._pair["caps"].bmax==D(28)
        assert not s._pair_failures,json.dumps(s._pair_report())
        before=json.dumps(s._pair_report(),sort_keys=True);cash=e.cache.account_for_venue(SIM).balance_total().as_decimal()
        # Replay only genuine already-applied callbacks in reverse order. The
        # native engine/cache is not modified; duplicate callbacks earn no credit.
        for event in reversed(list(s.native_fill_events)):
            s.on_order_filled(event)
        for event in reversed(list(s.native_cancel_events)):
            s.on_order_canceled(event)
        assert json.dumps(s._pair_report(),sort_keys=True)==before
        assert e.cache.account_for_venue(SIM).balance_total().as_decimal()==cash
    finally:e.end();e.dispose()


@pytest.mark.parametrize("sol_first",[False,True])
def test_native_same_timestamp_fill_invalidation_replay_priority_audit(sol_first):
    s,e,ep=native_setup(a=".2")
    try:
        t=covered(s,e);p=s._pair;p["boundary"]=D("100.2")
        btc=tick(BTC_PERP,t,"100.2");sol=tick(SOL_PERP,t,"99")
        run_ticks(e,[sol,btc] if sol_first else [btc,sol])
        fills=[r for r in s.paired_prefix_audit if r["event"]=="ACTUAL_FILL" and r["kind"]=="TP" and int(r["timestamp_ns"])==t]
        if sol_first:
            assert fills and fills[0]["risk"]=="ACTIVE_RISK"
        else:
            assert not fills  # BTC invalidation cancel ACK precedes later same-ts SOL matching.
            assert any(r["event"]=="ACTUAL_FILL" and r["kind"]=="SOL_CLOSE" and r["risk"]=="INACTIVE_RISK" and int(r["timestamp_ns"])==t for r in s.paired_prefix_audit)
        expected=D("37.5") if sol_first else D(50)
        for dt in (1,2,3):
            run_ticks(e,[tick(BTC_PERP,t+dt,"100.2"),tick(SOL_PERP,t+dt,"99")])
        assert s._pair_qty(BTC_PERP.id)==expected,json.dumps(s._pair_report())
        assert p["caps"].bmax==expected
    finally:e.end();e.dispose()


class RejectedStopProbe(Probe):
    def _pair_submit(self,instrument,side,qty,kind,ns,**kwargs):
        if kind=="STOP":kwargs["stop"]=D(99)  # Actual native rejection: BUY stop below current ask.
        return super()._pair_submit(instrument,side,qty,kind,ns,**kwargs)


class LostProtectionAckProbe(Probe):
    def _pair_accept(self,event):
        return  # Real native working order, deliberately lost owner ACK callback.


@pytest.mark.parametrize("probe,reason",[(RejectedStopProbe,"NATIVE_STOP_REJECTED"),
    (LostProtectionAckProbe,"PROTECTION_OVERDUE_NEXT_QUOTE")])
def test_native_rejected_or_missing_protection_ack_fails_closed_without_fake_receipt(probe,reason):
    s,e,ep=native_setup(a=".2",probe=probe)
    try:
        t=s._pair["eligible_ns"]
        for dt in range(6):
            run_ticks(e,[tick(BTC_PERP,t+dt),tick(SOL_PERP,t+dt)])
        assert reason in s._pair_failures,json.dumps(s._pair_report())
        assert s._pair_qty(BTC_PERP.id)==0 and s._pair_qty(SOL_PERP.id)==0
        assert s._pair is None and not s._pair_work()
        assert not e.cache.orders_open() and not e.cache.orders_inflight()
    finally:e.end();e.dispose()
