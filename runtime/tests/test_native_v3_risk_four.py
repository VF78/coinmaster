from decimal import Decimal as D
from types import SimpleNamespace
import pytest
from nautilus_trader.model.enums import OrderSide, TimeInForce
from coinmaster.domain.wave_overlay import Candidate, Episode
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
from test_wave_native_integration import lifecycle_config, native_engine
from test_native_episode_risk import NativeProbe, tick, run_ticks, marks
from test_native_btc_sizing import prepare_day

def setup(mode, asset=BTC_PERP, qty="100"):
    strategy = NativeProbe(lifecycle_config(candidate=Candidate(btc_notional_multiplier=7.875), research_v3_risk=mode, max_mark_age_ns=1000000000000))
    engine = native_engine(strategy)
    run_ticks(engine, [tick(BTC_PERP, 0), tick(SOL_PERP, 1)])
    marks(strategy, 2)
    ep = Episode("v3-episode", 1, 10000, 1., btc_entry_vwap=100., btc_initial_qty=float(qty) if asset==BTC_PERP else 0., btc_open_qty=float(qty) if asset==BTC_PERP else 0., h=10000., wave_levels=(.01,.02,.03))
    if asset == SOL_PERP:
        ep.sol_qty = float(qty)
    strategy._domain.episode = ep
    strategy.submit_order(strategy.order_factory.market(asset.id, OrderSide.BUY, asset.make_qty(D(qty)), time_in_force=TimeInForce.IOC))
    run_ticks(engine, [tick(asset, 3)])
    if mode == "s10_15":
        strategy._v3_finalize_sol_anchor(3)
    return strategy, engine, ep

@pytest.mark.parametrize("mode", ["b25","s10_15","r2","t3"])
def test_v3_direction_sizing_and_mutual_exclusion(mode):
    s = NativeProbe(lifecycle_config(candidate=Candidate(btc_notional_multiplier=7.875), research_v3_risk=mode))
    s._current_signals=[SimpleNamespace(side=1)]
    assert s._research_btc_entry_multiplier()==5.5
    s._current_signals=[SimpleNamespace(side=-1)]
    assert s._research_btc_entry_multiplier()==7.875
    with pytest.raises(ValueError):
        NativeProbe(lifecycle_config(candidate=Candidate(btc_notional_multiplier=7.875), research_v3_risk=mode, research_btc_direction_sizing=True))

def test_b25_native_partial_current_quote_no_tp_right_and_hysteresis():
    s,e,ep=setup("b25")
    try:
        original_h=ep.h
        s._btc_sizing_peak=D("14000")
        marks(s, 10, "90")
        s._research_check_v3_risk(10)
        assert s._btc_sizing_reduced and s._v3_reduction is not None
        assert not ep.sol_right_fraction
        # No cached quote fill from cancellation callbacks.
        assert ep.btc_open_qty==100
        run_ticks(e,[tick(BTC_PERP,10,"89",size="10")])
        assert ep.btc_open_qty==90
        assert s._v3_reduction["remaining"]==D("40")
        run_ticks(e,[tick(BTC_PERP,60000000011,"88")])
        assert ep.btc_open_qty==50
        assert ep.h==original_h and not ep.btc_filled_tps and not ep.sol_right_fraction
        assert s._v3_reduction is None
        s._current_signals=[SimpleNamespace(side=1)]
        assert s._research_btc_entry_multiplier()==2.75
        marks(s,60000000012,"200")
        s._research_check_v3_risk(60000000012)
        assert not s._btc_sizing_reduced and ep.btc_open_qty==50
        assert s._btc_sizing_peak>=D("14000")
        fills=[r for r in s.v3_risk_audit if r["event"]=="PROTECTIVE_FILL"]
        assert [D(r["price"]) for r in fills]==[D("89"),D("88")]
    finally:
        e.end(); e.dispose()

@pytest.mark.parametrize("btc_price,trigger", [("100",False),("110",False),("90",True)])
def test_b25_native_losing_episode_required_even_global_sol_dd(btc_price,trigger):
    s,e,ep=setup("b25")
    try:
        s._btc_sizing_peak=D("20000")
        marks(s,10,btc_price)
        if btc_price=="100":
            # Fee-net native contribution at entry is negative, use profitable
            # contribution for exact zero boundary explicitly.
            s._btc_loss_realized={str(next(iter(s._btc_loss_realized))):D("0")}
        s._research_check_v3_risk(10)
        assert s._btc_sizing_reduced is trigger
    finally:
        e.end();e.dispose()

@pytest.mark.parametrize("price,stage,remaining", [("90.2",0,100),("90",1,50),("85",2,0)])
def test_sol_native_first_fill_anchor_fee_and_threshold_staging(price,stage,remaining):
    s,e,ep=setup("s10_15",SOL_PERP)
    try:
        anchor=s._v3_sol_cycle["anchor"]
        assert anchor==D("9990")
        marks(s,10,"100",price)
        s._research_check_v3_risk(10)
        assert s._v3_sol_cycle["stage"]==stage
        if stage:
            assert s._v3_sol_block_episode==ep.id
            run_ticks(e,[tick(SOL_PERP,10,price)])
            assert ep.sol_qty==remaining
        assert ep.h==10000
    finally:
        e.end();e.dispose()

def test_sol_native_upgrade_partial_half_to_full_and_no_add():
    s,e,ep=setup("s10_15",SOL_PERP)
    try:
        marks(s,10,"100","90")
        s._research_check_v3_risk(10)
        run_ticks(e,[tick(SOL_PERP,10,"90",size="10")])
        assert ep.sol_qty==90
        marks(s,60000000011,"100","83")
        s._research_check_v3_risk(60000000011)
        assert s._v3_reduction["reason"]=="S15"
        run_ticks(e,[tick(SOL_PERP,60000000011,"83")])
        assert ep.sol_qty==0
        intent=s._domain._intent(ep,"SOL_ADD",1,1,quantity=1)
        s._submit_intent(intent,100,100,None,0,ts_now=60000000012)
        assert intent.id not in ep.pending and not e.cache.orders_open()
        assert s._v3_sol_block_episode==ep.id
    finally:
        e.end();e.dispose()

@pytest.mark.parametrize("best,price,trigger", [(.03,"90",False),(.04,"102",False),(.05,"102",True),(.05,"100",True)])
def test_t3_native_daily_best_only_and_fresh_quote(best,price,trigger):
    s,e,ep=setup("t3")
    try:
        ep.best_f=best
        marks(s,10,price)
        s._research_check_v3_risk(10)
        assert ep.best_f==best
        assert (s._forced_close_reason is not None)==trigger
        if trigger:
            assert ep.btc_open_qty==100
            run_ticks(e,[tick(BTC_PERP,10,"98")])
            assert not e.cache.positions_open()
            fills=[r for r in s.fill_audit if r.get("reason")=="RESEARCH_V3_T3"]
            assert s._v3_trail_wait_ns==10
    finally:
        e.end();e.dispose()

def test_r2_native_flat_daily_count_reversal_flip_and_no_tp_delay(monkeypatch):
    from coinmaster.domain import wave_overlay
    monkeypatch.setattr(wave_overlay,"completed_wave_levels",lambda *a:(.01,.02,.03))
    s=NativeProbe(lifecycle_config(candidate=Candidate(btc_notional_multiplier=7.875),research_v3_risk="r2"))
    e=native_engine(s)
    run_ticks(e,[tick(BTC_PERP,0),tick(SOL_PERP,1)])
    try:
        s._v3_regime_wait=True
        prepare_day(s,10,1)
        WaveOverlayStrategy._advance_current_day(s)
        assert s._domain.episode is None and s._v3_daily_count==1
        WaveOverlayStrategy._advance_current_day(s)
        assert s._v3_daily_count==1
        prepare_day(s,20,-1)
        WaveOverlayStrategy._advance_current_day(s)
        assert s._domain.episode is None and s._v3_daily_count==1
        prepare_day(s,30,-1)
        WaveOverlayStrategy._advance_current_day(s)
        assert s._domain.episode is not None
        assert s._domain.episode.btc_sizing_multiplier==7.875
    finally:
        e.end();e.dispose()

def test_b25_exact_native_25_and_15_boundaries_no_buyback():
    s,e,ep=setup("b25")
    try:
        marks(s,10,"90.1")
        equity=s._v3_equity()
        assert equity == D("9000")
        s._btc_sizing_peak=D("12000")
        s._research_check_v3_risk(10)
        assert s._btc_sizing_dd==D(".25") and s._btc_sizing_reduced
        run_ticks(e,[tick(BTC_PERP,10,"90.1")])
        assert ep.btc_open_qty==50
        marks(s,11,"90")
        # Establish an exact 15% current E/P without resetting the stored peak.
        target_equity=s._btc_sizing_peak*D(".85")
        # Native marks shift remaining uPnL to this exact E.
        p=next(p for p in e.cache.positions_open() if p.instrument_id==BTC_PERP.id)
        account=s._v3_equity()-p.unrealized_pnl(BTC_PERP.make_price(D("90"))).as_decimal()
        price=(D("100")+(target_equity-account)/D("50")).quantize(D(".1"),rounding="ROUND_UP")
        marks(s,11,str(price))
        s._research_check_v3_risk(11)
        assert s._btc_sizing_dd<=D(".15")
        assert not s._btc_sizing_reduced and ep.btc_open_qty==50
    finally:
        e.end();e.dispose()

def test_native_protection_cancel_denied_retains_owner_until_later_quote():
    s,e,ep=setup("b25")
    try:
        order=s.order_factory.limit(BTC_PERP.id,OrderSide.SELL,BTC_PERP.make_qty(D("1")),BTC_PERP.make_price(D("1000")),time_in_force=TimeInForce.GTC,reduce_only=True)
        s.submit_order(order)
        run_ticks(e,[tick(BTC_PERP,4)])
        assert e.cache.orders_open()
        actual_cancel=s.cancel_order
        denied=[]
        def deny_once(o,*a,**kw):
            if not denied:
                denied.append(str(o.client_order_id))
                return
            return actual_cancel(o,*a,**kw)
        s.cancel_order=deny_once
        s._btc_sizing_peak=D("14000")
        marks(s,10,"90")
        s._research_check_v3_risk(10)
        assert e.cache.orders_open() and ep.btc_open_qty==100
        run_ticks(e,[tick(BTC_PERP,10,"89")])
        assert ep.btc_open_qty==100 # cancel ACK cannot match stale cached quote.
        run_ticks(e,[tick(BTC_PERP,11,"88")])
        assert ep.btc_open_qty==50
        assert s._v3_reduction is None
    finally:
        e.end();e.dispose()

def test_sol_anchor_immutable_after_native_add_and_profitable_cycle_no_guard():
    s,e,ep=setup("s10_15",SOL_PERP)
    try:
        anchor=s._v3_sol_cycle["anchor"]
        marks(s,10,"100","110")
        s.submit_order(s.order_factory.market(SOL_PERP.id,OrderSide.BUY,SOL_PERP.make_qty(D("10")),time_in_force=TimeInForce.IOC))
        run_ticks(e,[tick(SOL_PERP,10,"110")])
        s._v3_finalize_sol_anchor(10)
        assert s._v3_sol_cycle["anchor"]==anchor
        s._research_check_v3_risk(10)
        assert s._v3_reduction is None
    finally:
        e.end();e.dispose()

@pytest.mark.parametrize("action,reason,expected", [("SOL_HALF_EXIT","SOL_Z_HALF_EXIT",45),("SOL_EXIT","SOL_Z_FULL_EXIT",0),("SOL_EXIT","SOL_HARD_TIMEOUT",0)])
def test_sol_native_ordinary_exit_preempts_pending_protective_partial(action,reason,expected,monkeypatch):
    s,e,ep=setup("s10_15",SOL_PERP)
    try:
        marks(s,10,"100","90")
        s._research_check_v3_risk(10)
        run_ticks(e,[tick(SOL_PERP,10,"90",size="10")])
        assert ep.sol_qty==90 and s._v3_reduction["remaining"]==D("40")
        prepare_day(s,20,1)
        intent=s._domain._intent(ep,action,-1,None,quantity=45 if action=="SOL_HALF_EXIT" else 90,reason=reason)
        if action=="SOL_HALF_EXIT":
            ep.sol_half_target_lots=450
        monkeypatch.setattr(s._domain,"decide",lambda *a,**kw:[intent])
        WaveOverlayStrategy._advance_current_day(s)
        assert s._v3_reduction is None and s._mandatory_sol_exit[0].id==intent.id
        run_ticks(e,[tick(SOL_PERP,20,"89")])
        assert ep.sol_qty==expected
        assert not s._v3_orders
        if action=="SOL_HALF_EXIT":
            assert ep.sol_half_done
        assert s._v3_sol_block_episode==ep.id
    finally:
        e.end();e.dispose()

def test_sol_native_guard_defers_to_already_owned_ordinary_exit():
    s,e,ep=setup("s10_15",SOL_PERP)
    try:
        ordinary=s._domain._intent(ep,"SOL_EXIT",-1,None,quantity=100,reason="SOL_Z_FULL_EXIT")
        s._queued_intents.append((ordinary,None,0))
        marks(s,10,"100","85")
        s._research_check_v3_risk(10)
        assert s._v3_reduction is None and s._v3_sol_cycle["stage"]==0
        assert s._queued_intents[0][0].id==ordinary.id
        assert s._v3_sol_block_episode==ep.id
        run_ticks(e,[tick(SOL_PERP,10,"85")])
        assert ep.sol_qty==0
    finally:
        e.end();e.dispose()

def test_sol_native_unknown_opening_ack_blocks_protective_child_until_terminal():
    s,e,ep=setup("s10_15",SOL_PERP)
    try:
        intent=s._domain._intent(ep,"SOL_ADD",1,1,quantity=1)
        order=s.order_factory.limit(SOL_PERP.id,OrderSide.BUY,SOL_PERP.make_qty(D("1")),SOL_PERP.make_price(D("1")),time_in_force=TimeInForce.GTC)
        oid=str(order.client_order_id)
        s._pending_by_order[oid]=intent
        s._sigma_by_order[oid]=None
        s._decision_index_by_order[oid]=0
        s.submit_order(order)
        marks(s,10,"100","90")
        s._research_check_v3_risk(10)
        assert oid in s._pending_by_order and ep.sol_qty==100
        run_ticks(e,[tick(SOL_PERP,10,"90")])
        assert ep.sol_qty==100 and oid not in s._pending_by_order
        run_ticks(e,[tick(SOL_PERP,11,"89")])
        assert ep.sol_qty==50 and not s._v3_orders
    finally:
        e.end();e.dispose()

@pytest.mark.parametrize("mode,asset,qty,price,remaining", [("b25",BTC_PERP,".003","90",".001"),("s10_15",SOL_PERP,"1.1","90",".5")])
def test_native_half_protection_odd_lot_remaining_rounds_down(mode,asset,qty,price,remaining):
    s,e,ep=setup(mode,asset,qty)
    try:
        if mode=="b25":
            s._btc_sizing_peak=D("14000")
            marks(s,10,price)
            s._research_check_v3_risk(10)
        else:
            marks(s,10,"100",price)
            # Force a valid threshold-scale anchor in this tiny-lot money proof.
            s._v3_sol_cycle["anchor"]=D("100")
            s._research_check_v3_risk(10)
        assert s._v3_reduction is not None
        run_ticks(e,[tick(asset,10,price)])
        held=next(p for p in e.cache.positions_open() if p.instrument_id==asset.id)
        assert held.quantity.as_decimal()==D(remaining)
        assert (ep.btc_open_qty if asset==BTC_PERP else ep.sol_qty)==pytest.approx(float(remaining))
    finally:
        e.end();e.dispose()
