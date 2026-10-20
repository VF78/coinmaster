from datetime import datetime, UTC, timedelta
from decimal import Decimal as D
from types import SimpleNamespace
import pytest
from nautilus_trader.model.enums import OrderSide, TimeInForce, BarAggregation
from coinmaster.domain.wave_overlay import DailyBar, Episode
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
from coinmaster.strategy.carry_pair import chop_snapshot, DAY, HOUR
from test_native_split_cover import cfg
from test_native_h1_b1 import confirmation_types, bar
from test_native_episode_risk import NativeProbe, tick, run_ticks, marks
from test_wave_native_integration import native_engine

T=100*DAY

def history(ts=T, future=False):
    end=datetime.fromtimestamp(ts/1e9,UTC)
    rows=[]
    for i in range(100):
        close=end-timedelta(days=99-i)
        px=100+(2 if i%2 else -2)
        rows.append(DailyBar(close-timedelta(days=1),close,close,100,px,px))
    if future:
        close=end+timedelta(days=1)
        rows.append(DailyBar(end,close,close,100,10000,1))
    return rows

def setup(side=1, enabled=True, probe=NativeProbe, sol=0, rate=None, funding=None):
    s=probe(cfg(True).__replace__(research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,
        research_chop_pair=enabled,research_confirmation_bars=confirmation_types()))
    if funding:
        from nautilus_trader.backtest.engine import BacktestEngine
        from nautilus_trader.backtest.config import BacktestEngineConfig
        from nautilus_trader.config import LoggingConfig
        from nautilus_trader.model.enums import AccountType, OmsType
        from nautilus_trader.model.objects import Money
        from coinmaster.research.native_fixture import PerpetualFundingModule, SIM
        e=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
        e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,
            starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,
            default_leverage=D(1),modules=[PerpetualFundingModule(*funding)],bar_execution=False)
        e.add_instrument(BTC_PERP);e.add_instrument(SOL_PERP);e.add_strategy(s)
    elif rate:
        from test_native_sol_risk_first import engine
        e=engine(s,rate=rate)
    else:
        e=native_engine(s)
    run_ticks(e,[tick(BTC_PERP,1)])
    s._bars=history()
    s._carry_ohlc={int(b.close_time.timestamp()*1e9):(105,95) for b in s._bars}
    s._current_signals=[SimpleNamespace(side=-side,beta=1.,sigma=.01)]*100
    s._current_btc=s._current_sol=SimpleNamespace(ts_event=T)
    s._last_accepted_session=s._latest_seen_session=T
    ep=s._domain.episode=Episode("carry-one",side,10000,1,wave_levels=(.5,.6,.7),h=10000)
    marks(s,T-10)
    i=s._domain._intent(ep,"BTC_ENTRY",side,None,quantity=100)
    s._submit_intent(i,100,100,.01,0,ts_now=T-10)
    run_ticks(e,[tick(BTC_PERP,T-9),tick(BTC_PERP,T-8),tick(BTC_PERP,T-7,"99" if side==1 else "101"),tick(SOL_PERP,T-6)])
    if sol:
        i=s._domain._intent(ep,"SOL_ADD",-side,0,quantity=sol,reason="ORIGINAL_ALPHA")
        s._submit_intent(i,100,100,.01,0,ts_now=T-5)
        run_ticks(e,[tick(SOL_PERP,T-4)])
    return s,e,ep

def arm(s,e,price="96",ts=T):
    marks(s,ts,price,"100")
    assert s._carry_daily(ts)
    run_ticks(e,[tick(BTC_PERP,ts+1,price),tick(SOL_PERP,ts+2),tick(SOL_PERP,ts+3)])
    return s._carry

def close(s,e,ts=T+100):
    s._carry_close("CHOP_PAIR_TEST",ts)
    run_ticks(e,[tick(BTC_PERP,ts+1,"96"),tick(SOL_PERP,ts+2),tick(BTC_PERP,ts+3),tick(SOL_PERP,ts+4)])
    for n in range(5,20):
        if not e.cache.positions_open() and not e.cache.orders_open():break
        run_ticks(e,[tick(BTC_PERP,ts+n*2_000_000_000,"96"),tick(SOL_PERP,ts+n*2_000_000_000+1)])
    s._reconcile_group_flat()
    assert not e.cache.positions_open() and not e.cache.orders_open(), dict(forced=s._forced_close_reason,submitted=list(map(str,s._forced_close_submitted)),orders=[str(o) for o in e.cache.orders()[-8:]],pending=list(s._pending_by_order))
    assert not e.cache.orders_inflight() and not s._pending_by_order and s._domain.episode is None

def test_causal_raw_flips_beta_ema_atr_range():
    rows=history();ohlc={int(b.close_time.timestamp()*1e9):(105,95) for b in rows}
    f=chop_snapshot(rows,ohlc,T)
    assert f["beta"]==D(1) and f["flips"]==7 and f["high"]==105 and f["low"]==95
    assert chop_snapshot(history(future=True),ohlc,T)==f
    assert chop_snapshot(rows,ohlc,T-1) is None
    del ohlc[T-DAY]
    assert chop_snapshot(rows,ohlc,T) is None

@pytest.mark.parametrize("side",[1,-1])
def test_native_actual_basis_single_grant_fee_benchmark_and_no_old_targets(side):
    s,e,ep=setup(side)
    try:
        basis=(ep.btc_entry_vwap,ep.btc_entry_notional_exact,ep.btc_initial_qty)
        c=arm(s,e,price="96" if side==1 else "104")
        assert c["phase"]=="ACTIVE" and c["grant"] and c["filled"]==c["quantity"]
        assert c["benchmark"]==c["E0"]-c["U0"]+c["oldfees"]+D(".001")*c["btc_notional"]
        assert c["oldfees"]>0
        assert basis==(ep.btc_entry_vwap,ep.btc_entry_notional_exact,ep.btc_initial_qty)
        assert not any(o.is_reduce_only for o in e.cache.orders_open())
        n=len(e.cache.orders());target=c["sol_target"];benchmark=c["benchmark"]
        marks(s,T+10,"90","80")
        run_ticks(e,[tick(BTC_PERP,T+11,"90"),tick(SOL_PERP,T+12,"80")])
        s._carry_daily(T+DAY)
        s._queue_confirmed_btc_targets(None,0,T+12)
        assert len(e.cache.orders())==n and c["sol_target"]==target and c["benchmark"]==benchmark
        assert len([r for r in s.carry_pair_audit if r["event"]=="GRANT"])==1
        assert not s._queued_intents
        close(s,e)
    finally:e.end();e.dispose()

def test_existing_sol_netted_and_fees_prorated_by_actual_remaining():
    s,e,ep=setup(sol=10)
    try:
        before=s._carry_fees[BTC_PERP.id]["fees"]
        s.submit_order(s.order_factory.market(BTC_PERP.id,OrderSide.SELL,BTC_PERP.make_qty(20),time_in_force=TimeInForce.IOC,reduce_only=True))
        run_ticks(e,[tick(BTC_PERP,T-1,"96")])
        assert s._carry_fees[BTC_PERP.id]["fees"]==before*D(".8")
        c=arm(s,e)
        assert c["sol_initial"]==10 and c["quantity"]==c["sol_target"]-10
        assert len([r for r in s.carry_pair_audit if r["event"]=="GRANT"])==1
        close(s,e)
    finally:e.end();e.dispose()

@pytest.mark.parametrize("case",["wrongside","abovefull","unknownfee","unknownmark","margin"])
def test_native_invalid_admission_closes_without_grant(case):
    s,e,ep=setup(sol=200 if case=="abovefull" else 0)
    try:
        if case=="wrongside":
            s.submit_order(s.order_factory.market(SOL_PERP.id,OrderSide.BUY,SOL_PERP.make_qty(1),time_in_force=TimeInForce.IOC))
            run_ticks(e,[tick(SOL_PERP,T-1)])
        if case=="unknownfee":s._carry_fees[BTC_PERP.id]["known"]=False
        if case=="margin":s._tier_allows_increase=lambda *a:False
        marks(s,T,"96","100")
        assert s._carry_daily(T)
        if case=="unknownmark":s._latest_marks.pop(SOL_PERP.id)
        run_ticks(e,[tick(BTC_PERP,T+1,"96"),tick(SOL_PERP,T+2),tick(BTC_PERP,T+3,"96"),tick(SOL_PERP,T+4)])
        assert not any(r["event"]=="GRANT" for r in s.carry_pair_audit)
        assert not e.cache.positions_open()
    finally:e.end();e.dispose()

def test_unknown_ack_blocks_arming_and_late_actual_reconciles():
    s,e,ep=setup()
    try:
        unknown=s._domain._intent(ep,"SOL_ADD",-1,0,quantity=1)
        s._pending_by_order["UNKNOWN_ACK"]=unknown
        marks(s,T,"96","100");assert s._carry_daily(T)
        run_ticks(e,[tick(SOL_PERP,T+1)])
        assert s._carry["phase"]=="ARMING"
        assert not any(r["event"]=="GRANT" for r in s.carry_pair_audit)
        s._pending_by_order.pop("UNKNOWN_ACK");s._domain.on_parent_terminal(unknown.id)
        run_ticks(e,[tick(BTC_PERP,T+2,"96"),tick(SOL_PERP,T+3)])
        assert s._carry["grant"]
        close(s,e)
    finally:e.end();e.dispose()

def test_external_partial_reduction_closes_both_without_refill():
    s,e,ep=setup()
    try:
        c=arm(s,e);n=len([r for r in s.carry_pair_audit if r["event"]=="GRANT"])
        s.submit_order(s.order_factory.market(SOL_PERP.id,OrderSide.BUY,SOL_PERP.make_qty(1),time_in_force=TimeInForce.IOC,reduce_only=True))
        run_ticks(e,[tick(SOL_PERP,T+10),tick(BTC_PERP,T+11,"96"),tick(SOL_PERP,T+12),tick(BTC_PERP,T+13,"96")])
        s._reconcile_group_flat()
        assert not e.cache.positions_open() and s._carry is None
        assert len([r for r in s.carry_pair_audit if r["event"]=="GRANT"])==n
    finally:e.end();e.dispose()

def test_range_requires_two_consecutive_closed_same_boundary_and_exits_at_loss():
    s,e,ep=setup()
    try:
        c=arm(s,e)
        kind=next(k for k in s.config.research_confirmation_bars if k.instrument_id==BTC_PERP.id and k.spec.aggregation==BarAggregation.HOUR)
        for offset,px in [(1,106),(2,94),(3,106)]:
            marks(s,T+offset*HOUR,"96","100")
            run_ticks(e,[tick(BTC_PERP,T+offset*HOUR,"96")])
            s.on_bar(bar(kind,T+offset*HOUR,px))
            assert c["phase"]=="ACTIVE"
        s.on_bar(bar(kind,T+4*HOUR,106)) # Future close must not count.
        assert c["hour_count"]==1
        marks(s,T+4*HOUR,"96","100")
        run_ticks(e,[tick(BTC_PERP,T+4*HOUR,"96")])
        money=s._carry_money(T+4*HOUR)
        assert money["equity"]-money["closefees"]<c["benchmark"]
        s.on_bar(bar(kind,T+4*HOUR,106))
        assert c["phase"]=="CLOSING" and s._forced_close_reason=="CHOP_PAIR_RANGE_INVALIDATION"
        run_ticks(e,[tick(BTC_PERP,T+4*HOUR+1,"96"),tick(SOL_PERP,T+4*HOUR+2)])
        assert not e.cache.positions_open()
        assert not any(r["event"]=="RECOVERY" for r in s.carry_pair_audit)
    finally:e.end();e.dispose()

def test_default_off_does_not_arm_or_change_baseline_native_targets():
    s,e,ep=setup(enabled=False)
    try:
        assert not s._carry_daily(T)
        assert s._carry is None and s._carry_fees=={} and s.carry_pair_audit==[]
        assert any(o.is_reduce_only for o in e.cache.orders_open())
    finally:e.end();e.dispose()

def test_two_sequential_native_episodes_reset_only_after_terminal_flat(tmp_path):
    import sqlite3
    from coinmaster.ledger.journal import NativeEventJournal
    from coinmaster.research.native_fixture import FundingInstruction
    path=tmp_path/"carry-two-episodes.sqlite"
    journal=NativeEventJournal(str(path))
    events=tuple(FundingInstruction("carry-"+str(n)+"-"+str(inst.id),inst.id,D(".001"),ts+10,D(mark))
        for n,ts,bmark in ((1,T,"96"),(2,T+DAY,"104"))
        for inst,mark in ((BTC_PERP,bmark),(SOL_PERP,"100")))
    s,e,ep=setup(funding=(events,journal))
    evidence=[]
    def post(ts,bmark):
        c=s._carry;benchmark=c["benchmark"]
        before=s._carry_money(ts)
        cash=e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()
        expected=sum(((-1 if p.is_long else 1)*p.quantity.as_decimal()*D(bmark if p.instrument_id==BTC_PERP.id else "100")*D(".001") for p in e.cache.positions_open()),D(0))
        run_ticks(e,[tick(BTC_PERP,ts+10,bmark),tick(SOL_PERP,ts+11)])
        after=s._carry_money(ts+11)
        new_cash=e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()
        assert after["equity"]-before["equity"]==new_cash-cash==expected
        assert s._carry is c and c["phase"]=="ACTIVE" and c["benchmark"]==benchmark
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT COUNT(*) FROM funding_events").fetchone()[0]==2*len(evidence)+2
        evidence.append(dict(episode=c["episode_id"],native_cash_delta=str(new_cash-cash),native_equity_delta=str(after["equity"]-before["equity"]),benchmark=str(benchmark),expected_signed_posting=str(expected)))

    try:
        arm(s,e);first=s._carry["episode_id"];post(T,"96");close(s,e)
        ts=T+DAY
        s._bars=history(ts);s._carry_ohlc={int(b.close_time.timestamp()*1e9):(105,95) for b in s._bars}
        s._current_signals=[SimpleNamespace(side=1,beta=1.,sigma=.01)]*100
        second=s._domain.episode=Episode("carry-two",-1,10000,1,wave_levels=(.5,.6,.7),h=10000)
        marks(s,ts-10)
        i=s._domain._intent(second,"BTC_ENTRY",-1,None,quantity=10)
        s._submit_intent(i,100,100,.01,0,ts_now=ts-10)
        run_ticks(e,[tick(BTC_PERP,ts-9),tick(BTC_PERP,ts-8),tick(BTC_PERP,ts-7,"101")])
        c=arm(s,e,price="104",ts=ts)
        assert c["episode_id"]!=first and c["grant"] and c["filled"]==c["quantity"]
        post(ts,"104")
        close(s,e,ts+100)
        assert len([r for r in s.carry_pair_audit if r["event"]=="GRANT"])==2
        assert len([r for r in s.carry_pair_audit if r["event"]=="NATIVE_TERMINAL_FLAT"])==2
        assert not s._queued_intents
        with sqlite3.connect(path) as db:
            rows=db.execute("SELECT event_id,instrument_id,rate,settlement_mark,account_total_after FROM funding_events ORDER BY ts_event,event_id").fetchall()
            assert len(rows)==4
        import json
        print("CARRY_NATIVE_SQLITE_2EP="+json.dumps(dict(funding_rows=rows,episodes=evidence,terminal_flat=True)))
    finally:e.end();e.dispose();journal.close()

def test_recovery_uses_native_equity_and_taker_close_fees_before_new_sol():
    s,e,ep=setup()
    try:
        marks(s,T,"101","100")
        assert s._carry_daily(T)
        run_ticks(e,[tick(BTC_PERP,T+1,"101"),tick(SOL_PERP,T+2),tick(BTC_PERP,T+3,"101"),tick(SOL_PERP,T+4)])
        rows=[r for r in s.carry_pair_audit if r["event"]=="RECOVERY"]
        assert rows and D(rows[0]["equity"])-D(rows[0]["closefees"])>=D(rows[0]["benchmark"])
        assert not any(r["event"]=="GRANT" for r in s.carry_pair_audit)
        assert not e.cache.positions_open()
        closes=[r for r in s.fill_audit if r["action"]=="FORCED_CLOSE"]
        assert closes and all(r["native_liquidity_side"]=="TAKER" for r in closes)
    finally:e.end();e.dispose()

def test_native_hedge_partials_retry_same_intent_only():
    s,e,ep=setup()
    try:
        marks(s,T,"96","100");assert s._carry_daily(T)
        run_ticks(e,[tick(BTC_PERP,T+1,"96"),tick(SOL_PERP,T+2,size="1"),tick(SOL_PERP,T+3,size="1")])
        c=s._carry
        assert c["filled"]>0 and c["filled"]<c["quantity"]
        intent=c["intent"].id
        submitted=[]
        original=s._record_submission
        def capture(order,intent_id,*args,**kw):
            submitted.append(intent_id)
            return original(order,intent_id,*args,**kw)
        s._record_submission=capture
        for n in range(4,60):
            run_ticks(e,[tick(SOL_PERP,T+n,size="1")])
            if c["filled"]==c["quantity"]:break
        assert c["filled"]==c["quantity"]
        assert c["intent"].id==intent
        assert len([r for r in s.carry_pair_audit if r["event"]=="GRANT"])==1
        assert submitted and set(submitted)=={intent}
        close(s,e)
    finally:e.end();e.dispose()

def test_native_arming_cancel_late_fill_changes_freeze_not_original_basis():
    class Delayed(NativeProbe):
        delay=False
        def cancel_order(self,o,*a,**kw):
            if self.delay and not o.is_reduce_only:return
            return super().cancel_order(o,*a,**kw)
    s,e,ep=setup(probe=Delayed)
    try:
        # Real resting original SOL add races its cancellation, not a fake fill.
        logical=s._domain._intent(ep,"SOL_ADD",-1,0,quantity=10,reason="ORIGINAL_ALPHA")
        order=s.order_factory.limit(SOL_PERP.id,OrderSide.SELL,SOL_PERP.make_qty(10),SOL_PERP.make_price(101),time_in_force=TimeInForce.GTC)
        s._pending_by_order[str(order.client_order_id)]=logical
        s._sigma_by_order[str(order.client_order_id)]=.01
        s._decision_index_by_order[str(order.client_order_id)]=0
        s.submit_order(order);run_ticks(e,[tick(SOL_PERP,T-1)])
        s.delay=True;marks(s,T,"96","100");assert s._carry_daily(T)
        run_ticks(e,[tick(SOL_PERP,T+1,"101",size="1")])
        actual=order.filled_qty.as_decimal()
        assert 0<actual<10 and s._carry["phase"]=="ARMING"
        assert D(str(ep.sol_qty))==actual and D(str(ep.sol_add_filled_notional[0]))==actual*101
        s.delay=False;s.cancel_order(order)
        marks(s,T+2,"96","101")
        run_ticks(e,[tick(BTC_PERP,T+3,"96"),tick(SOL_PERP,T+4,"101")])
        assert s._carry["sol_initial"]==actual and s._carry["oldfees"]>0
        assert D(str(ep.sol_add_filled_notional[0]))==actual*101
        close(s,e)
    finally:e.end();e.dispose()

def test_native_trail_group_stop_dominates_carry():
    s,e,ep=setup()
    try:
        arm(s,e)
        ep.best_f=.2
        s._carry_daily(T+DAY)
        assert s._forced_close_reason=="TRAIL"
        run_ticks(e,[tick(BTC_PERP,T+DAY+1,"96"),tick(SOL_PERP,T+DAY+2)])
        assert not e.cache.positions_open()
    finally:e.end();e.dispose()

def test_production_tiny_carry_runner_observer_fresh_journal_and_serialization(tmp_path):
    from test_native_baseline import write_streaming_fixture
    from coinmaster.research.native_baseline import run_native_diagnostic,TRADING_START_MS,MINUTE_MS
    from coinmaster.domain.wave_overlay import Candidate
    import pyarrow as pa
    import pyarrow.parquet as pq
    import json
    start,end=write_streaming_fixture(tmp_path,trading_days=1);shift=TRADING_START_MS-start
    for path in (tmp_path/"normalized").glob("*.parquet"):
        rows=pq.read_table(path).to_pylist()
        for row in rows:row["open_time_ms"]+=shift
        pq.write_table(pa.Table.from_pylist(rows),path)
    result=run_native_diagnostic(tmp_path,candidate=Candidate(btc_notional_multiplier=7.875,max_parent_notional=30_000_000),trading_start_ms=TRADING_START_MS,trading_end_ms=TRADING_START_MS+2*MINUTE_MS,warmup_start_ms=shift,
        research_v0_execution_repairs=True,research_v0_deferred_selective_zero_tp=True,research_v0_selective_lifecycle_repairs=True,research_btc_direction_sizing=True,research_btc_split50=True,research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,
        research_chop_pair=True,observe_minute_risk=True,artifact_dir=tmp_path/"production")
    assert result["config"]["research_chop_pair"] and result["config"]["candidate"]["sol_overlay_enabled"]
    assert isinstance(result["carry_pair_audit"],list) and "carry_pair" in result["source_hashes"]
    assert result["minute_risk_observations"]["curves"]["pre_quote_paired_close"]["samples"]==3
    assert result["terminal_open_positions"]==0
    json.dumps(result)

def test_opt_in_bar_feed_no_eligible_chop_preserves_native_fill_cash_fee_identity(tmp_path,monkeypatch):
    """New indicator bars never execute orders; native quote matching remains identical."""
    from test_native_baseline import write_streaming_fixture
    from coinmaster.research.native_baseline import run_native_diagnostic,TRADING_START_MS,MINUTE_MS
    from coinmaster.domain.wave_overlay import Candidate
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
    import pyarrow as pa
    import pyarrow.parquet as pq
    import json
    start,end=write_streaming_fixture(tmp_path,trading_days=1);shift=TRADING_START_MS-start
    for path in (tmp_path/"normalized").glob("*.parquet"):
        rows=pq.read_table(path).to_pylist()
        for row in rows:row["open_time_ms"]+=shift
        pq.write_table(pa.Table.from_pylist(rows),path)
    original=WaveOverlayStrategy.on_quote_tick
    def script(s,q):
        original(s,q)
        if q.instrument_id!=s.config.btc_id:return
        minute=(q.ts_event//1_000_000-TRADING_START_MS)//MINUTE_MS
        if minute==1:
            assert s._domain.episode is None
            ep=s._domain.episode=Episode("quote-parity",1,10000,1,wave_levels=(.5,.6,.7),h=10000)
            i=s._domain._intent(ep,"BTC_ENTRY",1,None,quantity=1)
            s._submit_intent(i,float(q.bid_price),float(q.ask_price),.01,len(s._bars)-1,ts_now=q.ts_event)
        if minute==110:s._begin_forced_close("PARITY_TEST")
    monkeypatch.setattr(WaveOverlayStrategy,"on_quote_tick",script)
    common=dict(candidate=Candidate(btc_notional_multiplier=7.875,max_parent_notional=30_000_000),
        trading_start_ms=TRADING_START_MS,trading_end_ms=TRADING_START_MS+121*MINUTE_MS,warmup_start_ms=shift,
        research_v0_execution_repairs=True,research_v0_deferred_selective_zero_tp=True,research_v0_selective_lifecycle_repairs=True,research_btc_direction_sizing=True,research_btc_split50=True,research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,observe_minute_risk=True)
    results=[run_native_diagnostic(tmp_path,research_chop_pair=enabled,artifact_dir=tmp_path/str(enabled),**common) for enabled in (False,True)]
    assert results[1]["carry_pair_audit"]==[]
    assert results[0]["fills"]>=2
    for key in ("terminal_total","native_fees","fills","fill_audit","cash_account_series","interval_cash_account_series","terminal_open_positions","funding","native_order_rejections"):
        assert results[0][key]==results[1][key],key
    delta={k:v for k,v in results[1]["config"].items() if results[0]["config"].get(k)!=v}
    assert delta=={"research_chop_pair":True}
    assert {k:v for k,v in results[0]["minute_risk_observations"].items() if not k.endswith("_path")}=={k:v for k,v in results[1]["minute_risk_observations"].items() if not k.endswith("_path")}


def test_real_native_denied_grant_retry_keeps_same_economic_authority():
    class Denied(NativeProbe):
        denied=None
        def on_order_denied(self,event):
            if self.denied is None:self.denied=[]
            self.denied.append(event)
            super().on_order_denied(event)
    s,e,ep=setup(probe=Denied,rate="2/00:00:01")
    try:
        s.denied=[]
        marks(s,T,"96","100");assert s._carry_daily(T)
        run_ticks(e,[tick(BTC_PERP,T+1,"96"),tick(SOL_PERP,T+2)])
        c=s._carry
        assert c["grant"] and s.denied
        original=c["intent"].id
        assert c["filled"]==0
        ts=T+2_000_000_000;marks(s,ts,"96","100")
        run_ticks(e,[tick(SOL_PERP,ts),tick(SOL_PERP,ts+1)])
        assert c["intent"].id==original and c["filled"]==c["quantity"]
        assert len([r for r in s.carry_pair_audit if r["event"]=="GRANT"])==1
        close(s,e,ts+2_000_000_000)
    finally:e.end();e.dispose()

@pytest.mark.parametrize("instrument",[BTC_PERP,SOL_PERP],ids=["BTC","SOL"])
def test_unowned_actual_native_increase_immediately_closes_frozen_pair(instrument):
    s,e,ep=setup()
    try:
        c=arm(s,e);target=c["sol_target"];bqty=c["btc_qty"]
        side=OrderSide.BUY if instrument.id==BTC_PERP.id else OrderSide.SELL
        s.submit_order(s.order_factory.market(instrument.id,side,instrument.make_qty(1),time_in_force=TimeInForce.IOC))
        run_ticks(e,[tick(instrument,T+10,"96" if instrument.id==BTC_PERP.id else "100")])
        assert c["phase"]=="CLOSING"
        assert any(r["event"]=="GROUP_EXIT" and r["reason"]=="CHOP_PAIR_UNOWNED_INCREASE" for r in s.carry_pair_audit)
        assert s._forced_close_reason=="CHOP_PAIR_UNOWNED_INCREASE" or not e.cache.positions_open()
        assert c["btc_qty"]==bqty and c["sol_target"]==target
        close(s,e,T+20)
        assert len([r for r in s.carry_pair_audit if r["event"]=="GRANT"])==1
    finally:e.end();e.dispose()
