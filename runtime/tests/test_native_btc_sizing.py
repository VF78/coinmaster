from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from types import SimpleNamespace
from dataclasses import replace
import pytest
from nautilus_trader.model.enums import OrderSide, TimeInForce
from coinmaster.domain.wave_overlay import Candidate, DailyBar
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
from coinmaster.research.minute_risk import ConditionalUpperToLaterLowerTracker
from test_wave_native_integration import lifecycle_config, native_engine
from test_native_episode_risk import NativeProbe, tick, run_ticks, marks


def prepare_day(strategy, timestamp=1, side=1):
    now = datetime(1970, 1, 1, tzinfo=UTC)
    strategy._bars = [DailyBar(now + timedelta(days=i), now + timedelta(days=i+1),
                     now + timedelta(days=i+1), 100, 100, 100) for i in range(3)]
    strategy._current_signals = [SimpleNamespace(side=side, beta=1., sigma=.01)] * 3
    strategy._current_btc = SimpleNamespace(ts_event=timestamp)
    strategy._current_sol = SimpleNamespace(ts_event=timestamp)
    marks(strategy, timestamp)
    strategy._current_btc_mark = strategy._latest_marks[BTC_PERP.id]
    strategy._current_sol_mark = strategy._latest_marks[SOL_PERP.id]
    strategy._last_accepted_session = timestamp
    strategy._latest_seen_session = timestamp


@pytest.mark.parametrize("mode,side,expected", [
    ("control", 1, "7.875"), ("control", -1, "7.875"),
    ("v1", 1, "6.3"), ("v2", -1, "5.5"),
    ("direction", 1, "5.5"), ("direction", -1, "7.875"),
    ("drawdown", 1, "3.9375"), ("drawdown", -1, "3.9375"),
])
def test_native_episode_frozen_multiplier_selective_q0_q1_partial_fill_initial_sol_h(monkeypatch, mode, side, expected):
    from coinmaster.domain import wave_overlay
    monkeypatch.setattr(wave_overlay, "completed_wave_levels", lambda *args: (.01, .02, .03))
    candidate = Candidate(btc_notional_multiplier=float(expected) if mode in {"v1", "v2"} else 7.875,
                          ema_period=34, btc_tp_fractions_initial_qty=(.2125, .2125, .575),
                          sol_size_multipliers_h=(1.75, 2.625, 3.5), max_parent_notional=30000000)
    strategy = NativeProbe(lifecycle_config(candidate=candidate, research_btc_direction_sizing=mode=="direction",
                            research_btc_drawdown_sizing=mode=="drawdown", max_mark_age_ns=100))
    engine = native_engine(strategy)
    run_ticks(engine, [tick(BTC_PERP, 0)])
    try:
        if mode == "drawdown":
            strategy.submit_order(strategy.order_factory.market(SOL_PERP.id, OrderSide.BUY,
                SOL_PERP.make_qty(D("10")), time_in_force=TimeInForce.IOC))
            run_ticks(engine, [tick(SOL_PERP, 1)])
        prepare_day(strategy, 3, side)
        if mode == "drawdown":
            # Seeded global peak is not the account's current cash.
            strategy._btc_sizing_peak = D("14000")
            strategy._research_sample_btc_sizing(3)
            assert strategy._btc_sizing_reduced
        WaveOverlayStrategy._advance_current_day(strategy)
        intent = strategy._queued_intents[0][0]
        episode = strategy._domain.episode
        assert D(str(intent.requested_notional)) == D(expected) * D(str(episode.active_entry))
        if mode in {"direction", "drawdown"}:
            assert D(str(episode.btc_sizing_multiplier)) == D(expected)
        run_ticks(engine, [tick(BTC_PERP, 4)])  # q0 stores fixed original gross lots.
        gross = strategy._deferred_selective_entries[intent.id]["gross_lots"]
        # Native whole-equity recovery changes V4 latch before q1, never this episode.
        if mode == "drawdown":
            marks(strategy, 5, "100", "600")
            strategy._research_sample_btc_sizing(5)
            assert not strategy._btc_sizing_reduced
        run_ticks(engine, [tick(BTC_PERP, 5, size="100")])  # Actual IOC partial entry.
        assert episode.btc_initial_qty == 100
        assert D(str(episode.btc_reference_qty)) == D(gross) * D(".001")
        assert episode.h == episode.btc_reference_qty * episode.btc_entry_vwap / episode.beta_entry
        assert D(str(episode.h)) == D(gross) * D(".001") * D("100")
        assert episode.btc_open_qty == 100
        assert episode.btc_reference_qty > episode.btc_initial_qty
        assert candidate.sol_size_multipliers_h == (1.75, 2.625, 3.5)
        assert episode.btc_tp_target_lots == {0: 21250, 1: 21250, 2: 57500}
        original_h = episode.h
        run_ticks(engine, [tick(BTC_PERP, 6), tick(BTC_PERP, 7, "101" if side == 1 else "99")])
        assert episode.btc_tp_filled_lots[0] == 21250
        assert episode.sol_right_fraction[0] == min(1., episode.btc_initial_qty / episode.btc_net_planned_qty)
        assert episode.h * episode.sol_right_fraction[0] == pytest.approx(10000.)
        assert episode.btc_open_qty == 78.75
        assert episode.h == original_h  # Native TP cannot shrink original SOL reference.
        assert episode.btc_sizing_multiplier == (float(expected) if mode in {"direction", "drawdown"} else None)
        if mode == "drawdown":
            assert D(str(episode.btc_sizing_multiplier)) == D("3.9375")
            assert len([r for r in strategy.btc_sizing_audit if r["event"]=="EPISODE_ENTRY_SIZING"]) == 1
        if mode in {"control", "v1", "v2"}:
            assert not strategy.btc_sizing_audit
    finally:
        engine.end(); engine.dispose()


def test_v4_native_whole_equity_peak_hysteresis_causal_marks_and_no_held_reduction():
    strategy = NativeProbe(lifecycle_config(candidate=Candidate(btc_notional_multiplier=7.875),
                            research_btc_drawdown_sizing=True, max_mark_age_ns=100))
    engine = native_engine(strategy)
    run_ticks(engine, [tick(BTC_PERP, 0)])
    try:
        strategy.submit_order(strategy.order_factory.market(BTC_PERP.id, OrderSide.BUY,
            BTC_PERP.make_qty(D("10")), time_in_force=TimeInForce.IOC))
        run_ticks(engine, [tick(BTC_PERP, 1)])
        strategy.submit_order(strategy.order_factory.market(SOL_PERP.id, OrderSide.SELL,
            SOL_PERP.make_qty(D("10")), time_in_force=TimeInForce.IOC))
        run_ticks(engine, [tick(SOL_PERP, 2)])
        # Native entry fees2; both held legs contribute:10000-2+5000+1000=15998.
        marks(strategy, 3, "600", "0")
        strategy._research_sample_btc_sizing(3)
        assert strategy._btc_sizing_peak == strategy._btc_sizing_equity == D("15998")
        assert not strategy._btc_sizing_reduced
        # 25% boundary exactly from native marks, with existing fees included.
        # BTC loss1000.5 + SOL profit1000 =>9997.5; nativeequity -> DD>25%.
        marks(strategy, 4, "300", "0")
        strategy._latest_marks[SOL_PERP.id] = strategy._latest_marks[SOL_PERP.id].__class__(SOL_PERP.id, D("0"), 3)
        strategy._research_sample_btc_sizing(4)
        assert strategy._btc_sizing_last_ns == 3  # Mixed timestamps cannot sample.
        marks(strategy, 5, "300", "100")
        strategy._research_sample_btc_sizing(5)  # 11998 /15998, just beyond25%.
        assert strategy._btc_sizing_reduced
        peak = strategy._btc_sizing_peak
        marks(strategy, 6, "400", "100")
        strategy._research_sample_btc_sizing(6)  # 12998 /15998: between15and25.
        assert strategy._btc_sizing_reduced and strategy._btc_sizing_peak == peak
        marks(strategy, 7, "460.1", "100")
        strategy._research_sample_btc_sizing(7)  # 13598 /15998 <=15%.
        assert not strategy._btc_sizing_reduced
        assert strategy._btc_sizing_peak == peak
        # Backdated callbacks and one-leg future marks cannot change sample/peak.
        marks(strategy, 6, "1000", "100")
        strategy._research_sample_btc_sizing(6)
        assert strategy._btc_sizing_last_ns == 7 and strategy._btc_sizing_peak == peak
        assert len(engine.cache.positions_open()) == 2
        assert len(engine.trader.generate_order_fills_report()) == 2
        assert [r["reduced"] for r in strategy.btc_sizing_audit] == [True, False]
        strategy._begin_forced_close("TRAIL")
        run_ticks(engine, [tick(BTC_PERP, 8), tick(SOL_PERP, 8)])
        assert not engine.cache.positions_open()
        marks(strategy, 9)
        strategy._research_sample_btc_sizing(9)
        assert strategy._btc_sizing_peak == peak  # Actual flat never resets global peak.
        assert strategy._btc_sizing_reduced
    finally:
        engine.end(); engine.dispose()


def test_v4_exact_seed_thresholds_from_native_cash_no_reset():
    class Probe(NativeProbe):
        @property
        def cache(self):
            return self.native_receipt
    strategy = Probe(lifecycle_config(candidate=Candidate(btc_notional_multiplier=7.875),
                            research_btc_drawdown_sizing=True, max_mark_age_ns=100))
    from nautilus_trader.model.objects import Money
    account = SimpleNamespace(base_currency=BTC_PERP.quote_currency,
                              balance_total=lambda *_: Money(strategy.cash, BTC_PERP.quote_currency))
    strategy.native_receipt = SimpleNamespace(account_for_venue=lambda *_: account, positions_open=lambda: [])
    for timestamp, equity, reduced in [(1,"10000",False),(2,"7500",True),(3,"8400",True),(4,"8500",False),
                                       (5,"20000",False),(6,"15000",True),(7,"16999",True),(8,"17000",False)]:
        strategy.cash = D(equity)
        marks(strategy, timestamp)
        strategy._research_sample_btc_sizing(timestamp)
        assert strategy._btc_sizing_reduced == reduced
    assert strategy._btc_sizing_peak == D("20000")


def test_conditional_bound_uses_only_prior_upper_and_preserves_seed():
    tracker = ConditionalUpperToLaterLowerTracker("100")
    tracker.add(1,"90","200")
    assert tracker.summary()["maximum"]["drawdown_peak_percent"] == "10.0"
    tracker.add(2,"80","150")
    tracker.add(3,"70","300")
    tracker.add(4,"150","200")
    summary = tracker.summary()
    assert D(summary["maximum"]["drawdown_peak_percent"]) == 65
    assert summary["maximum"]["peak"]["timestamp_ns"] == "1"
    assert summary["maximum"]["trough"]["timestamp_ns"] == "3"
    assert summary["same_bar_extrema_order_assumed"] is False
    assert tracker.count == 4


def test_research_sizing_modes_reject_combination_and_wrong_base():
    with pytest.raises(ValueError, match="SEPARATE"):
        WaveOverlayStrategy(lifecycle_config(candidate=Candidate(btc_notional_multiplier=7.875),
                            research_btc_direction_sizing=True, research_btc_drawdown_sizing=True))
    with pytest.raises(ValueError, match="SEPARATE"):
        WaveOverlayStrategy(lifecycle_config(candidate=Candidate(btc_notional_multiplier=5.5),
                            research_btc_direction_sizing=True))
