from decimal import Decimal as D
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import pytest
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.objects import Price, Quantity
from coinmaster.domain.wave_overlay import Episode, DailyBar
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from coinmaster.venues.marks import VenueMark
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
from test_wave_native_integration import lifecycle_config, native_engine


@pytest.mark.parametrize("enabled", [False, True])
def test_native_portfolio_partial_exit_next_same_regime_episode_and_two_epochs(monkeypatch, enabled):
    from coinmaster.domain import wave_overlay
    monkeypatch.setattr(wave_overlay, "completed_wave_levels", lambda *args: (0.01, 0.02, 0.03))
    class Probe(WaveOverlayStrategy):
        def __init__(self, config):
            super().__init__(config)
            self.opened = False
            self.exit_quantities = []
        def on_quote_tick(self, tick):
            if tick.instrument_id == self.config.btc_id and not self.opened:
                self.opened = True
                self._domain.episode = Episode("old", 1, 10000, 1.0)
                self.submit_order(self.order_factory.market(tick.instrument_id, OrderSide.BUY,
                    self.cache.instrument(tick.instrument_id).make_qty(D("90")), time_in_force=TimeInForce.IOC))
                return
            super().on_quote_tick(tick)
        def _advance_current_day(self):
            # Test explicitly advances fresh daily decisions after native close.
            pass
    strategy = Probe(lifecycle_config(research_portfolio_protect_45=enabled))
    engine = native_engine(strategy)
    def tick(t, size=1000, price="100.0"):
        return QuoteTick(BTC_PERP.id, Price.from_str(price), Price.from_str(price),
                         Quantity.from_str(f"{size}.000"), Quantity.from_str(f"{size}.000"), t, t)
    engine.add_data([tick(1)]); engine.run(streaming=True); engine.clear_data()
    try:
        assert engine.cache.positions_open()[0].quantity.as_decimal() == 90
        strategy._latest_marks = {BTC_PERP.id: VenueMark(BTC_PERP.id, D("49"), 2),
                                  SOL_PERP.id: VenueMark(SOL_PERP.id, D("1"), 1)}
        strategy._research_check_portfolio_protection(2)
        assert strategy._research_protect_latch is None  # mixed timestamps cannot trigger
        strategy._latest_marks[SOL_PERP.id] = VenueMark(SOL_PERP.id, D("1"), 2)
        strategy._research_check_portfolio_protection(2)
        if not enabled:
            assert strategy._research_protect_latch is None
            assert strategy.research_protection_audit == []
            return
        assert D(strategy.research_protection_audit[0]["native_equity"]) == D("5401")
        assert not strategy._entries_enabled()
        # Partial native close leaves require successive native IOC retries.
        for t in (3, 4, 5):
            engine.add_data([tick(t, 30, "49.0")]); engine.run(streaming=True); engine.clear_data()
            assert not strategy._research_protection_next_decision_eligible()
        assert not engine.cache.positions_open() and not engine.cache.orders_open()
        assert strategy._domain.episode is None
        assert strategy._forced_close_reason is None
        assert not strategy._entries_enabled()
        # Same callback/daily index cannot unlock the old episode.
        strategy._current_btc = SimpleNamespace(ts_event=2)
        assert not strategy._research_protection_next_decision_eligible()
        # Next actual daily decision creates a new domain UUID in SAME regime.
        now = datetime(2024, 1, 1, tzinfo=UTC)
        strategy._bars = [DailyBar(now + timedelta(days=i), now + timedelta(days=i+1),
                         now + timedelta(days=i+1), 100, 100, 1) for i in range(3)]
        strategy._current_signals = [SimpleNamespace(side=1, beta=1.0, sigma=0.01)] * 3
        strategy._current_btc = SimpleNamespace(ts_event=10)
        strategy._current_sol = SimpleNamespace(ts_event=10)
        strategy._current_btc_mark = VenueMark(BTC_PERP.id, D("49"), 10)
        strategy._current_sol_mark = VenueMark(SOL_PERP.id, D("1"), 10)
        assert strategy._research_protection_next_decision_eligible()
        WaveOverlayStrategy._advance_current_day(strategy)
        assert strategy._research_protect_latch is None
        assert strategy._domain.episode.id != "old" and strategy._domain.episode.side == 1
        assert len(strategy._queued_intents) == 1
        cash = engine.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()
        assert strategy._research_protect_peak == cash == D("5401") - D("4.41")
        assert strategy.research_protection_audit[-1]["global_observer_peak_reset"] is False
        # Native exposure and fees in a second protective epoch.
        strategy._discard_queued_intents(lambda _: True)
        strategy.submit_order(strategy.order_factory.market(BTC_PERP.id, OrderSide.BUY,
            BTC_PERP.make_qty(D("80")), time_in_force=TimeInForce.IOC))
        engine.add_data([tick(11, 1000, "49.0")]); engine.run(streaming=True); engine.clear_data()
        strategy._latest_marks = {BTC_PERP.id: VenueMark(BTC_PERP.id, D("18"), 12),
                                  SOL_PERP.id: VenueMark(SOL_PERP.id, D("1"), 12)}
        strategy._research_check_portfolio_protection(12)
        assert strategy._research_protect_latch is not None
        for t in (13, 14):
            engine.add_data([tick(t, 40, "18.0")]); engine.run(streaming=True); engine.clear_data()
        assert not engine.cache.positions_open()
        assert [r["event"] for r in strategy.research_protection_audit] == ["BREACH", "REARM_NEXT_EPISODE", "BREACH"]
        fills = engine.trader.generate_order_fills_report()
        assert len(fills) == 7  # both opens and five actual partial close fills
    finally:
        engine.end(); engine.dispose()


def test_risk_variants_cannot_be_combined():
    with pytest.raises(ValueError, match="MUTUALLY_EXCLUSIVE"):
        WaveOverlayStrategy(lifecycle_config(research_portfolio_protect_45=True, research_sol_notional_cap_multiple=D("6")))


def test_guard_observer_retains_loss_bar_before_cancel_previous_book_fill(tmp_path, monkeypatch):
    import csv, gzip, json
    import pyarrow as pa
    import pyarrow.parquet as pq
    from coinmaster.research.native_baseline import run_native_diagnostic, MINUTE_MS
    from test_native_baseline import write_streaming_fixture
    start, end = write_streaming_fixture(tmp_path, trading_days=1)
    path = tmp_path / "normalized" / "bybit-BTCUSDT-mark-1m.parquet"
    rows = pq.read_table(path).to_pylist()
    rows[1].update(open="100", high="101", low="48", close="49")
    pq.write_table(pa.Table.from_pylist(rows), path)
    original = WaveOverlayStrategy.on_quote_tick
    def open_with_resting_target(self, tick):
        original(self, tick)
        if tick.instrument_id == self.config.btc_id and tick.ts_event == (start + MINUTE_MS) * 1_000_000:
            instrument = self.cache.instrument(tick.instrument_id)
            self.submit_order(self.order_factory.market(tick.instrument_id, OrderSide.BUY,
                instrument.make_qty(D("90")), time_in_force=TimeInForce.IOC))
            self.submit_order(self.order_factory.limit(tick.instrument_id, OrderSide.SELL,
                instrument.make_qty(D("1")), instrument.make_price(D("150")),
                time_in_force=TimeInForce.GTC, reduce_only=True))
    monkeypatch.setattr(WaveOverlayStrategy, "on_quote_tick", open_with_resting_target)
    result = run_native_diagnostic(tmp_path, trading_start_ms=start, trading_end_ms=end, warmup_start_ms=0,
        artifact_dir=tmp_path/"risk", observe_minute_risk=True, research_portfolio_protect_45=True)
    trace = list(csv.DictReader(gzip.open(tmp_path/"risk"/"minute-native-risk.csv.gz", "rt")))
    assert len(trace) == 4320
    loss_pre = trace[3]
    assert loss_pre["phase"] == "pre_quote_paired_close"
    assert len(json.loads(loss_pre["native_positions_and_mark_ohlc_json"])) == 1
    assert D(loss_pre["paired_close_equity"]) == D("5405.05")
    assert D(loss_pre["conditional_adverse_equity"]) == D("5315.05")
    # Cancel confirmation can close against the previous cached 100 book.
    assert trace[4]["native_positions_and_mark_ohlc_json"] == "[]"
    assert result["fills"] == 2 and result["terminal_open_positions"] == 0
    curve = result["minute_risk_observations"]["curves"]["all_native_close_samples"]
    assert D(curve["minimum"]["equity"]) == D("5405.05")
    assert D(result["research_protection_audit"][0]["native_equity"]) == D("5405.05")

def test_protection_waits_for_late_native_opening_ack_and_cancels_it():
    from coinmaster.domain.wave_overlay import Intent
    class Probe(WaveOverlayStrategy):
        def __init__(self, config):
            super().__init__(config)
            self.opened = False
        def on_quote_tick(self, tick):
            if tick.instrument_id == self.config.btc_id and not self.opened:
                self.opened = True
                self._domain.episode = Episode("old", 1, 10000, 1.0)
                self.submit_order(self.order_factory.market(tick.instrument_id, OrderSide.BUY,
                    BTC_PERP.make_qty(D("90")), time_in_force=TimeInForce.IOC))
            else:
                super().on_quote_tick(tick)
        def _advance_current_day(self):
            pass
    strategy = Probe(lifecycle_config(research_portfolio_protect_45=True))
    engine = native_engine(strategy)
    def quote_at(instrument, t, px):
        return QuoteTick(instrument.id, instrument.make_price(D(px)), instrument.make_price(D(px)),
                         instrument.make_qty(D("1000")), instrument.make_qty(D("1000")), t, t)
    engine.add_data([quote_at(BTC_PERP, 1, "100"), quote_at(SOL_PERP, 1, "100")])
    engine.run(streaming=True); engine.clear_data()
    try:
        late = strategy.order_factory.limit(SOL_PERP.id, OrderSide.BUY, SOL_PERP.make_qty(D("1")),
            SOL_PERP.make_price(D("1")), time_in_force=TimeInForce.GTC)
        oid = str(late.client_order_id)
        intent = strategy._domain._intent(strategy._domain.episode, "SOL_ADD", -1, 0, quantity=1)
        strategy._pending_by_order[oid] = intent  # durable submit-to-ACK window
        strategy._sigma_by_order[oid] = 0.01
        strategy._decision_index_by_order[oid] = 0
        strategy._latest_marks = {BTC_PERP.id: VenueMark(BTC_PERP.id, D("49"), 2),
                                  SOL_PERP.id: VenueMark(SOL_PERP.id, D("100"), 2)}
        strategy._research_check_portfolio_protection(2)
        engine.add_data([quote_at(BTC_PERP, 3, "49")]); engine.run(streaming=True); engine.clear_data()
        assert not engine.cache.positions_open()
        assert strategy._forced_close_reason == "RESEARCH_PORTFOLIO_45"
        assert strategy._domain.episode.id == "old"
        assert not strategy._research_protection_next_decision_eligible()
        strategy.submit_order(late)  # actual native ACK arrives after the close
        engine.add_data([quote_at(SOL_PERP, 4, "100")]); engine.run(streaming=True); engine.clear_data()
        assert engine.cache.order(late.client_order_id).is_canceled
        assert not strategy._pending_by_order and not engine.cache.orders_open()
        assert strategy._domain.episode is None and strategy._forced_close_reason is None
        assert strategy._research_protect_latch is not None
        assert len(engine.trader.generate_order_fills_report()) == 2
    finally:
        engine.end(); engine.dispose()
