from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from types import SimpleNamespace

import pytest
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.objects import Quantity
from coinmaster.domain.wave_overlay import Episode, DailyBar, Features
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from coinmaster.venues.marks import VenueMark
from test_wave_native_integration import lifecycle_config, native_engine


def tick(instrument, timestamp, price="100", size="1000"):
    return QuoteTick(instrument.id, instrument.make_price(D(price)), instrument.make_price(D(price)),
                     instrument.make_qty(D(size)), instrument.make_qty(D(size)), timestamp, timestamp)


def run_ticks(engine, ticks):
    engine.add_data(ticks); engine.run(streaming=True); engine.clear_data()


def marks(strategy, timestamp, btc="100", sol="100"):
    strategy._latest_marks = {BTC_PERP.id: VenueMark(BTC_PERP.id, D(btc), timestamp),
                              SOL_PERP.id: VenueMark(SOL_PERP.id, D(sol), timestamp)}


class NativeProbe(WaveOverlayStrategy):
    def _advance_current_day(self):
        pass

    def _tier_allows_increase(self, *args):
        return True


@pytest.mark.parametrize("reason", ["REGIME", "TRAIL"])
@pytest.mark.parametrize("mode", ["accepted_canceled", "partial_late_fill", "rejected", "denied"])
def test_native_ordinary_close_waits_opening_terminal_and_closes_late_actual_fill(reason, mode):
    class Probe(NativeProbe):
        def __init__(self, config):
            super().__init__(config)
            self.once = False
            self.submitted_wait = None
            self.native_events = []

        def cancel_order(self, order, *args, **kwargs):
            if mode == "partial_late_fill" and not order.is_reduce_only:
                return  # Delayed venue cancel receipt, native matching still owns fill.
            return super().cancel_order(order, *args, **kwargs)

        def on_quote_tick(self, quote):
            if self.once:
                return super().on_quote_tick(quote)
            self.once = True
            self._domain.episode = Episode("ordinary", 1, 10000, 1.0)
            intent = self._domain._intent(self._domain.episode, "SOL_ADD", 1, 0, quantity=1)
            if mode in {"partial_late_fill", "denied"}:
                order = self.order_factory.market(SOL_PERP.id, OrderSide.BUY,
                    Quantity.from_str("1.01") if mode == "denied" else SOL_PERP.make_qty(D("1")), time_in_force=TimeInForce.IOC)
            else:
                order = self.order_factory.limit(SOL_PERP.id, OrderSide.BUY, SOL_PERP.make_qty(D("1")),
                    SOL_PERP.make_price(D("100" if mode == "rejected" else "1")),
                    time_in_force=TimeInForce.GTC, post_only=mode == "rejected")
            self._pending_by_order[str(order.client_order_id)] = intent
            self._sigma_by_order[str(order.client_order_id)] = None
            self._decision_index_by_order[str(order.client_order_id)] = 0
            # Seed an already-completed group exit before the native opening ACK.
            self._domain.episode.close_reason = reason
            self._forced_close_reason = reason
            self._group_close_reconciliation_pending = True
            self.submit_order(order)

        def on_order_event(self, event):
            self.native_events.append(type(event).__name__)
            if type(event).__name__ == "OrderSubmitted":
                assert not self.cache.orders_open()
                self._reconcile_group_flat()
                self.submitted_wait = self._domain.episode.id
            super().on_order_event(event)

    strategy = Probe(lifecycle_config())
    engine = native_engine(strategy)
    try:
        run_ticks(engine, [tick(SOL_PERP, 1, size="0.5")])
        for timestamp in (2, 3, 4):
            run_ticks(engine, [tick(SOL_PERP, timestamp)])
        if mode != "denied":
            assert strategy.submitted_wait == "ordinary"
        assert not strategy._pending_by_order
        assert not strategy._queued_intents
        assert not engine.cache.positions_open() and not engine.cache.orders_open()
        assert strategy._domain.episode is None and strategy._forced_close_reason is None
        expected = {"accepted_canceled": "OrderCanceled", "partial_late_fill": "OrderFilled",
                    "rejected": "OrderRejected", "denied": "OrderDenied"}[mode]
        assert expected in strategy.native_events
        fills = engine.trader.generate_order_fills_report()
        if mode == "partial_late_fill":
            assert len(fills) == 2
            assert [D(r["qty"]) for r in strategy.fill_audit] == [D(".5"), D(".5")]
    finally:
        engine.end(); engine.dispose()


def test_native_half_completion_day_is_followed_by_later_daily_full_only():
    class Probe(NativeProbe):
        def __init__(self, config):
            super().__init__(config)
            self.n = 0
        def on_quote_tick(self, quote):
            self.n += 1
            if self.n == 1:
                self._domain.episode = Episode("half", 1, 10000, 1.0, btc_entry_vwap=100, btc_initial_qty=1)
                intent = self._domain._intent(self._domain.episode, "SOL_ADD", 1, 0, quantity=1000)
                self._submit_intent(intent, 1, 1, None, 0, ts_now=quote.ts_event)
            elif self.n == 2:
                self._domain.episode.sol_half_target_lots = 5000
                intent = self._domain._intent(self._domain.episode, "SOL_HALF_EXIT", -1, None, quantity=500, reason="SOL_Z_HALF_EXIT")
                self._submit_intent(intent, 1, 1, None, 0, ts_now=quote.ts_event)
            else:
                super().on_quote_tick(quote)
    strategy = Probe(lifecycle_config())
    engine = native_engine(strategy)
    now = datetime(1970, 1, 1, tzinfo=UTC)
    bars = [DailyBar(now + timedelta(days=i), now + timedelta(days=i+1),
                    now + timedelta(days=i+1), 100, 100, 1) for i in range(3)]
    try:
        run_ticks(engine, [tick(SOL_PERP, 1, "1"), tick(SOL_PERP, 2, "1", "250")])
        assert not strategy._domain.episode.sol_half_done
        strategy._bars = bars[:2]
        run_ticks(engine, [tick(SOL_PERP, 61000000002, "1")])
        episode = strategy._domain.episode
        assert episode.sol_half_done and episode.sol_half_decision_index == 1, (episode, strategy._queued_intents, strategy.fill_audit)
        assert [D(r["qty"]) for r in strategy.fill_audit if r["action"] == "SOL_HALF_EXIT"] == [D("250"), D("250")]
        feature = Features(1, 1, 1, 0, 0, 1, 0.1)
        assert strategy._domain._sol_exits(episode, feature, bars[1], 1, z=0.1) == []
        assert [i.action for i in strategy._domain._sol_exits(episode, feature, bars[2], 2, z=0.1)] == ["SOL_EXIT"]
    finally:
        engine.end(); engine.dispose()


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("side", [1, -1])
def test_native_btc_episode_guard_exact_fees_partial_profit_immutable_basis_two_episodes(enabled, side):
    strategy = NativeProbe(lifecycle_config(research_btc_episode_loss_20=enabled, max_mark_age_ns=100))
    engine = native_engine(strategy)
    run_ticks(engine, [tick(BTC_PERP, 0)])
    def entry(episode_id, timestamp, price, qty):
        marks(strategy, timestamp, price)
        strategy._domain.episode = Episode(episode_id, side, 10000, 1.0)
        intent = strategy._domain._intent(strategy._domain.episode, "BTC_ENTRY", side, None, quantity=qty)
        strategy._submit_intent(intent, float(price), float(price), None, 0, ts_now=timestamp)
        run_ticks(engine, [tick(BTC_PERP, timestamp, price)])
    try:
        entry("first", 1, "100", 90)
        native = engine.cache.positions_open()[0]
        cash = engine.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()
        assert native.realized_pnl.as_decimal() == D("-9")
        assert cash == D("10000") + native.realized_pnl.as_decimal()
        reference = strategy._btc_loss_reference
        if enabled:
            assert reference == D("9991")
        # Native partial profitable TP: net position PnL contains entry and exit fees.
        strategy.submit_order(strategy.order_factory.market(BTC_PERP.id,
            OrderSide.SELL if side == 1 else OrderSide.BUY, BTC_PERP.make_qty(D("30")),
            time_in_force=TimeInForce.IOC, reduce_only=True))
        profit_price = "110" if side == 1 else "90"
        run_ticks(engine, [tick(BTC_PERP, 2, profit_price)])
        native = engine.cache.positions_open()[0]
        expected = D("300") - D("9") - D("30") * D(profit_price) * D(".001")
        assert native.realized_pnl.as_decimal() == expected
        assert engine.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal() == D("10000") + expected
        if enabled:
            assert sum(strategy._btc_loss_realized.values()) == expected
            assert strategy._btc_loss_reference == reference
        # Realized TP offsets held loss: 60*(70-100)+net300 remains above -20%.
        safe = "70" if side == 1 else "130"
        marks(strategy, 3, safe)
        strategy._research_check_btc_episode_loss(3)
        assert strategy._research_protect_latch is None
        loss = "60" if side == 1 else "140"
        marks(strategy, 4, loss)
        strategy._latest_marks[SOL_PERP.id] = VenueMark(SOL_PERP.id, D("100"), 3)
        strategy._research_check_btc_episode_loss(4)
        assert strategy._research_protect_latch is None
        strategy._latest_marks[SOL_PERP.id] = VenueMark(SOL_PERP.id, D("100"), 4)
        strategy._research_check_btc_episode_loss(4)
        if not enabled:
            assert strategy._research_protect_latch is None and not strategy.btc_episode_loss_audit
            return
        breach = strategy.btc_episode_loss_audit[-1]
        assert D(breach["native_btc_episode_net_pnl"]) == expected - D("2400")
        assert not strategy._entries_enabled()
        # Existing IOC forced executor closes partial actual quantities.
        for timestamp in (5, 6):
            run_ticks(engine, [tick(BTC_PERP, timestamp, loss, "30")])
        assert not engine.cache.positions_open() and not engine.cache.orders_open()
        assert not strategy._pending_by_order and strategy._domain.episode is None
        assert strategy._research_protect_latch is not None
        assert not strategy._research_protection_next_decision_eligible()
        # Genuine later decision re-arms, using existing domain UUID generation.
        from coinmaster.domain import wave_overlay
        original = wave_overlay.completed_wave_levels
        wave_overlay.completed_wave_levels = lambda *args: (.01, .02, .03)
        try:
            now = datetime(2024, 1, 1, tzinfo=UTC)
            strategy._bars = [DailyBar(now + timedelta(days=i), now + timedelta(days=i+1),
                             now + timedelta(days=i+1), 100, 100, 100) for i in range(3)]
            strategy._current_signals = [SimpleNamespace(side=side, beta=1., sigma=.01)] * 3
            strategy._current_btc = SimpleNamespace(ts_event=10)
            strategy._current_sol = SimpleNamespace(ts_event=10)
            strategy._current_btc_mark = VenueMark(BTC_PERP.id, D(loss), 10)
            strategy._current_sol_mark = VenueMark(SOL_PERP.id, D("100"), 10)
            WaveOverlayStrategy._advance_current_day(strategy)
        finally:
            wave_overlay.completed_wave_levels = original
        assert strategy._research_protect_latch is None
        new_id = strategy._domain.episode.id
        assert new_id != "first"
        strategy._discard_queued_intents(lambda _: True)
        entry(new_id, 11, loss, 40)
        assert strategy._btc_loss_reference != reference
        assert strategy._btc_loss_episode_id == new_id
        assert len(strategy._btc_loss_realized) == 1
        assert sum(strategy._btc_loss_realized.values()) == -D("40") * D(loss) * D(".001")
        second_loss = "10" if side == 1 else "190"
        marks(strategy, 12, second_loss)
        strategy._research_check_btc_episode_loss(12)
        assert strategy._research_protect_latch is not None
        run_ticks(engine, [tick(BTC_PERP, 13, second_loss)])
        assert not engine.cache.positions_open() and not strategy._pending_by_order
        assert [r["event"] for r in strategy.btc_episode_loss_audit] == ["REFERENCE", "BREACH", "REARM_NEXT_EPISODE", "REFERENCE", "BREACH"]
    finally:
        engine.end(); engine.dispose()


@pytest.mark.parametrize("side", [1, -1])
@pytest.mark.parametrize("enabled", [False, True])
def test_native_sol_hedge_partial_admission_pending_and_btc_flat_zero(side, enabled):
    strategy = NativeProbe(lifecycle_config(research_sol_remaining_btc_hedge=enabled, max_mark_age_ns=100))
    engine = native_engine(strategy)
    run_ticks(engine, [tick(BTC_PERP, 0)])
    try:
        strategy._domain.episode = Episode("hedge", side, 10000, 2.0)
        strategy.submit_order(strategy.order_factory.market(BTC_PERP.id, OrderSide.BUY if side == 1 else OrderSide.SELL,
                             BTC_PERP.make_qty(D("10")), time_in_force=TimeInForce.IOC))
        run_ticks(engine, [tick(BTC_PERP, 1)])
        marks(strategy, 2)
        for timestamp in (2, 3):
            intent = strategy._domain._intent(strategy._domain.episode, "SOL_ADD", -side, 0, requested_notional=1000)
            strategy._submit_intent(intent, 100, 100, .01, 0, ts_now=timestamp)
            if timestamp == 2:
                duplicate = strategy._domain._intent(strategy._domain.episode, "SOL_ADD", -side, 1, requested_notional=1000)
                strategy._submit_intent(duplicate, 100, 100, .01, 0, ts_now=timestamp)
            run_ticks(engine, [tick(SOL_PERP, timestamp, size="2.5")])
        sol = next(p for p in engine.cache.positions_open() if p.instrument_id == SOL_PERP.id)
        if enabled:
            assert sol.quantity.as_decimal() == 5
            assert any(r.get("reason") == "SOL_OPENING_OWNERSHIP_PENDING" for r in strategy.sol_hedge_admission_audit)
            marks(strategy, 4)
            assert strategy._research_sol_hedge_quantity(D("10"), D("100"), 4) == 0
        else:
            assert not strategy.sol_hedge_admission_audit
        strategy.submit_order(strategy.order_factory.market(BTC_PERP.id, OrderSide.SELL if side == 1 else OrderSide.BUY,
                             BTC_PERP.make_qty(D("10")), time_in_force=TimeInForce.IOC, reduce_only=True))
        run_ticks(engine, [tick(BTC_PERP, 5)])
        marks(strategy, 6)
        if enabled:
            assert strategy._research_sol_hedge_quantity(D("10"), D("100"), 6) == 0
        strategy._begin_forced_close("TERMINAL_BOUNDARY_SETTLEMENT")
        run_ticks(engine, [tick(SOL_PERP, 7)])
        assert not engine.cache.positions_open() and not engine.cache.orders_open() and not strategy._pending_by_order
    finally:
        engine.end(); engine.dispose()


@pytest.mark.parametrize("beta", [.2, 4., 0., float("nan")])
def test_hedge_invalid_beta_is_closed(beta):
    strategy = NativeProbe(lifecycle_config(research_sol_remaining_btc_hedge=True, max_mark_age_ns=10))
    engine = native_engine(strategy)
    try:
        strategy._domain.episode = Episode("invalid", 1, 10000, beta)
        assert strategy._research_sol_hedge_quantity(D("1"), D("100"), 1) == 0
    finally:
        engine.dispose()


@pytest.mark.parametrize("enabled", [False, True])
def test_btc_guard_observer_captures_before_native_group_close(tmp_path, monkeypatch, enabled):
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
    def scripted(self, quote):
        original(self, quote)
        if quote.ts_event != (start + MINUTE_MS) * 1_000_000:
            return
        instrument = self.cache.instrument(quote.instrument_id)
        if quote.instrument_id == self.config.btc_id:
            self._domain.episode = Episode("observed", 1, 10000, 1.)
            intent = self._domain._intent(self._domain.episode, "BTC_ENTRY", 1, None, quantity=90)
            self._submit_intent(intent, 100, 100, None, 0, ts_now=quote.ts_event)
            self.submit_order(self.order_factory.limit(quote.instrument_id, OrderSide.SELL,
                instrument.make_qty(D("1")), instrument.make_price(D("150")),
                time_in_force=TimeInForce.GTC, reduce_only=True))
        elif quote.instrument_id == self.config.sol_id:
            self.submit_order(self.order_factory.market(quote.instrument_id, OrderSide.SELL,
                instrument.make_qty(D("1")), time_in_force=TimeInForce.IOC))
    monkeypatch.setattr(WaveOverlayStrategy, "on_quote_tick", scripted)
    monkeypatch.setattr(WaveOverlayStrategy, "_tier_allows_increase", lambda *args: True)
    result = run_native_diagnostic(tmp_path, trading_start_ms=start, trading_end_ms=end, warmup_start_ms=0,
        artifact_dir=tmp_path/"observed", observe_minute_risk=True, research_btc_episode_loss_20=enabled)
    trace = list(csv.DictReader(gzip.open(tmp_path/"observed"/"minute-native-risk.csv.gz", "rt")))
    assert len(trace) == 4320
    if enabled:
        loss_pre = trace[3]
        assert len(json.loads(loss_pre["native_positions_and_mark_ohlc_json"])) == 2
        assert trace[4]["native_positions_and_mark_ohlc_json"] == "[]"
        assert [r["event"] for r in result["btc_episode_loss_audit"]] == ["REFERENCE", "BREACH"]
        assert D(result["btc_episode_loss_audit"][0]["native_equity_reference"]) == D("9995.05")
        assert result["fills"] == 4 and result["terminal_open_positions"] == 0
        assert D(result["minute_risk_observations"]["curves"]["all_native_close_samples"]["minimum"]["equity"]) < D("6000")
    else:
        assert "btc_episode_loss_audit" not in result
        assert "research_btc_episode_loss_20" not in result["config"]


def test_native_btc_final_realized_fee_persists_while_sol_keeps_episode_active():
    strategy = NativeProbe(lifecycle_config(research_btc_episode_loss_20=True, max_mark_age_ns=100))
    engine = native_engine(strategy)
    run_ticks(engine, [tick(BTC_PERP, 0)])
    try:
        marks(strategy, 1)
        episode = Episode("btc-flat-sol-held", 1, 10000, 1.)
        strategy._domain.episode = episode
        entry = strategy._domain._intent(episode, "BTC_ENTRY", 1, None, quantity=10)
        strategy._submit_intent(entry, 100, 100, None, 0, ts_now=1)
        run_ticks(engine, [tick(BTC_PERP, 1)])
        reference = strategy._btc_loss_reference
        assert reference == D("9999")
        btc_position_id = str(engine.cache.positions_open()[0].id)
        sol = strategy._domain._intent(episode, "SOL_ADD", -1, 0, quantity=10)
        strategy._submit_intent(sol, 100, 100, .01, 0, ts_now=2)
        run_ticks(engine, [tick(SOL_PERP, 2)])
        # One actual native full TP earns its right and removes BTC exposure.
        episode.btc_tp_target_lots = {0: 10000}
        episode.btc_tp_target_qty = {0: 10.0}
        tp = strategy._domain._intent(episode, "BTC_REDUCE", -1, 0, quantity=10)
        strategy._submit_intent(tp, 110, 110, .01, 0, ts_now=3)
        run_ticks(engine, [tick(BTC_PERP, 3, "110")])
        positions = engine.cache.positions_open()
        assert len(positions) == 1 and positions[0].instrument_id == SOL_PERP.id
        assert strategy._domain.episode is episode and episode.btc_open_qty == 0
        expected_btc_net = D("100") - D("1") - D("1.10")
        assert strategy._btc_loss_realized == {btc_position_id: expected_btc_net}
        assert strategy._btc_loss_reference == reference and strategy._btc_loss_episode_id == episode.id
        cash = engine.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()
        assert cash == D("10000") + expected_btc_net - D("1")  # SOL incurred entry fee.
        # SOL adversity does not rewrite the BTC contribution; absent BTC has zero unrealized.
        marks(strategy, 4, "1", "500")
        strategy._research_check_btc_episode_loss(4)
        assert strategy._research_protect_latch is None
        assert strategy._btc_loss_realized == {btc_position_id: expected_btc_net}
        assert strategy._btc_loss_reference == reference
        strategy._begin_forced_close("TRAIL")
        run_ticks(engine, [tick(SOL_PERP, 5)])
        assert not engine.cache.positions_open() and not strategy._pending_by_order
        assert strategy._domain.episode is None
    finally:
        engine.end(); engine.dispose()
