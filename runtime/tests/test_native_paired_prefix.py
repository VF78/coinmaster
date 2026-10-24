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
        super().__init__(config.__replace__(research_paired_prefix="B2_F0", research_btc_q_mode="CLEAN_Q"))


def native_setup(side=1, a="2"):
    config=cfg(True,research_btc_real_u=True,research_btc_q_mode="CLEAN_Q", research_sol_off=True,
        research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,research_btc_split_discount=D(".005"))
    config=config.__replace__(candidate=Candidate(sol_overlay_enabled=False,btc_tp_fractions_initial_qty=(.2125,.2125,.575)))
    s=Probe(config)
    e=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,
        starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,
        default_leverage=D(1),liquidity_consumption=True,bar_execution=False)
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
        for dt in range(5):
            run_ticks(e,[tick(BTC_PERP,t+dt),tick(SOL_PERP,t+dt,size="0")])
        assert s._pair_qty(SOL_PERP.id)==0
        assert s._pair_qty(BTC_PERP.id)==0,json.dumps(s._pair_report())
        assert any(r["event"]=="ENTRY_TERMINAL_P0_FROZEN" and r["bmax"]=="0" for r in s.paired_prefix_audit)
    finally:
        e.end();e.dispose()
