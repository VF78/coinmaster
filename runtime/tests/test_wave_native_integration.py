from decimal import Decimal
from datetime import UTC, datetime, timedelta

from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.data import Bar, BarSpecification, BarType
from nautilus_trader.model.enums import AccountType, AggregationSource, BarAggregation, OmsType, OrderSide, PriceType, TimeInForce
from nautilus_trader.model.objects import Money, Price, Quantity

from coinmaster.research.native_fixture import BTC_PERP, SIM, SOL_PERP, MarkPriceUpdate, quote
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig
from coinmaster.domain.wave_overlay import Candidate, DailyBar
from coinmaster.domain.wave_overlay import Intent
from coinmaster.venues.marks import venue_mark, venue_mark_data_type
from coinmaster.venues.signals import daily_signal, daily_signal_data_type


class WaveOverlayWithNativeSolShort(WaveOverlayStrategy):
    """Test-only second-leg intent, submitted by the adapter's quote callback."""

    def __init__(self, config: WaveOverlayStrategyConfig) -> None:
        super().__init__(config)
        self._sol_short_submitted = False

    def on_quote_tick(self, tick) -> None:
        super().on_quote_tick(tick)
        if self._sol_short_submitted or tick.instrument_id != self.config.sol_id:
            return
        instrument = self.cache.instrument(self.config.sol_id)
        assert instrument is not None
        self.submit_order(self.order_factory.market(
            instrument_id=self.config.sol_id,
            order_side=OrderSide.SELL,
            quantity=instrument.make_qty(Decimal("500")),
            time_in_force=TimeInForce.IOC,
        ))
        self._sol_short_submitted = True


class CallbackOrderedReentryProbe(WaveOverlayStrategy):
    """Exercises the real native fill/position callback order around a close."""

    def __init__(self, config: WaveOverlayStrategyConfig, reentry_quote_ts: int) -> None:
        super().__init__(config)
        self.phase = "OPEN"
        self.reentry_quote_ts = reentry_quote_ts
        self.entry_order_id: str | None = None
        self.close_order_id: str | None = None
        self.reentry_gate_times: list[int] = []
        self.reconciled_after_position_event = False

    def on_quote_tick(self, tick) -> None:
        if tick.instrument_id != self.config.btc_id:
            return
        instrument = self.cache.instrument(tick.instrument_id)
        assert instrument is not None
        if self.phase == "OPEN":
            order = self.order_factory.market(instrument_id=tick.instrument_id, order_side=OrderSide.BUY, quantity=instrument.make_qty(Decimal("1")), time_in_force=TimeInForce.IOC)
            self.entry_order_id = str(order.client_order_id)
            self.phase = "ENTRY_SUBMITTED"
            self.submit_order(order)
            return
        if self.phase == "CLOSE_WAITING_QUOTE":
            position = next(iter(self.cache.positions_open()))
            order = self.order_factory.market(instrument_id=tick.instrument_id, order_side=OrderSide.SELL, quantity=instrument.make_qty(position.quantity.as_decimal()), time_in_force=TimeInForce.IOC, reduce_only=True)
            self.close_order_id = str(order.client_order_id)
            self.phase = "CLOSE_SUBMITTED"
            self.submit_order(order)
            return
        if self.phase == "REENTRY_QUEUED":
            super().on_quote_tick(tick)

    def on_order_filled(self, event) -> None:
        order_id = str(event.client_order_id)
        if order_id == self.entry_order_id:
            self.phase = "CLOSE_WAITING_QUOTE"
            return
        if order_id == self.close_order_id:
            # The actual position cache is intentionally reconciled by the
            # subsequent native position callback, not assumed here.
            self.phase = "AWAITING_POSITION_CALLBACK"
            self._group_close_reconciliation_pending = True
            return
        if self.phase == "REENTRY_QUEUED":
            self.phase = "DONE"

    def _reconcile_group_flat(self) -> None:
        if self.phase != "AWAITING_POSITION_CALLBACK" or self.cache.positions_open():
            return
        self._group_close_reconciliation_pending = False
        self.reconciled_after_position_event = True
        self.phase = "REENTRY_QUEUED"
        self._queued_intents.append((Intent("reentry", "probe", "BTC_ENTRY", None, 1, requested_notional=100), None, 0))

    def _tier_allows_increase(self, instrument_id, side, quantity, ts_now: int) -> bool:
        self.reentry_gate_times.append(ts_now)
        return ts_now == self.reentry_quote_ts


def make_bar_type(instrument_id, price_type):
    return BarType(instrument_id, BarSpecification(1, BarAggregation.DAY, price_type), AggregationSource.EXTERNAL)


def make_bar(kind, open_price: float, close_price: float, timestamp: int) -> Bar:
    volume = "1000.000" if kind.instrument_id == BTC_PERP.id else "1000.0"
    precision = 1 if kind.instrument_id == BTC_PERP.id else 2
    price = lambda value: Price.from_str(f"{value:.{precision}f}")
    return Bar(kind, price(open_price), price(max(open_price, close_price)), price(min(open_price, close_price)), price(close_price), Quantity.from_str(volume), timestamp, timestamp)


def test_native_wave_strategy_submits_and_confirms_fills_from_four_causal_bar_streams() -> None:
    btc_last, sol_last = make_bar_type(BTC_PERP.id, PriceType.LAST), make_bar_type(SOL_PERP.id, PriceType.LAST)
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(10_000, BTC_PERP.quote_currency)], base_currency=BTC_PERP.quote_currency, default_leverage=Decimal("1"))
    engine.add_instrument(BTC_PERP)
    engine.add_instrument(SOL_PERP)
    from nautilus_trader.model.identifiers import ClientId
    strategy = WaveOverlayStrategy(WaveOverlayStrategyConfig(btc_id=BTC_PERP.id, sol_id=SOL_PERP.id, btc_bar_type=btc_last, sol_bar_type=sol_last, btc_mark_data_type=venue_mark_data_type(BTC_PERP.id), sol_mark_data_type=venue_mark_data_type(SOL_PERP.id), mark_client_id=ClientId("TEST_MARKS"), active_seed=Decimal("10000"), tier_marks=tuple(MarkPriceUpdate(BTC_PERP.id, Decimal("100"), day * 86_400_000_000_000) for day in range(1, 851)) + tuple(MarkPriceUpdate(SOL_PERP.id, Decimal("30"), day * 86_400_000_000_000) for day in range(1, 851)), tier_selected_leverage=((BTC_PERP.id, Decimal("40")), (SOL_PERP.id, Decimal("20"))), max_mark_age_ns=86_400_000_000_000))
    engine.add_strategy(strategy)
    data, marks = [], []
    for day in range(850):
        timestamp = (day + 1) * 86_400_000_000_000
        btc = 100 + day * 0.04 + (6 if (day // 20) % 2 else -6) + (day % 5) * 0.1
        sol = 30 + day * 0.02 + (btc - 100) * 0.30 + (3 if (day // 17) % 2 else -3) + (day % 7) * 0.1
        data.extend((make_bar(btc_last, btc - 0.2, btc, timestamp), make_bar(sol_last, sol - 0.1, sol, timestamp), quote(BTC_PERP.id, f"{btc - 0.05:.1f}", f"{btc + 0.05:.1f}", timestamp + 1), quote(SOL_PERP.id, f"{sol - 0.05:.2f}", f"{sol + 0.05:.2f}", timestamp + 1)))
        marks.extend((venue_mark(BTC_PERP.id, Decimal(str(btc)), timestamp), venue_mark(SOL_PERP.id, Decimal(str(sol)), timestamp)))
    engine.add_data(data, sort=False)
    engine.add_data(marks, client_id=ClientId("TEST_MARKS"), sort=False)
    engine.sort_data()
    engine.run()
    try:
        fills = engine.trader.generate_order_fills_report()
        assert not fills.empty
        assert set(fills["instrument_id"]) <= {str(BTC_PERP.id), str(SOL_PERP.id)}
        assert fills["ts_last"].is_monotonic_increasing
        assert not engine.trader.generate_positions_report()["closing_order_id"].isna().any()
        assert not engine.trader.generate_account_report(SIM).empty
        assert len(strategy._latest_marks) <= 2
        assert len(strategy._latest_tier_marks) <= 2
        assert not strategy._queued_intents
    finally:
        engine.dispose()


def test_seed_warmup_never_replays_orders_and_first_live_daily_close_can_fill() -> None:
    """The verified history seeds features only; the next causal close decides."""
    btc_last, sol_last = make_bar_type(BTC_PERP.id, PriceType.LAST), make_bar_type(SOL_PERP.id, PriceType.LAST)
    marks = tuple(MarkPriceUpdate(BTC_PERP.id, Decimal("100"), day * 86_400_000_000_000) for day in range(1, 851)) + tuple(MarkPriceUpdate(SOL_PERP.id, Decimal("30"), day * 86_400_000_000_000) for day in range(1, 851))
    seed: list[DailyBar] = []
    data, custom_marks = [], []
    for day in range(850):
        timestamp = (day + 1) * 86_400_000_000_000
        btc = 100 + day * 0.04 + (6 if (day // 20) % 2 else -6) + (day % 5) * 0.1
        sol = 30 + day * 0.02 + (btc - 100) * 0.30 + (3 if (day // 17) % 2 else -3) + (day % 7) * 0.1
        if day < 800:
            close = datetime.fromtimestamp(timestamp / 1_000_000_000, UTC)
            seed.append(DailyBar(close - timedelta(days=1), close, close, btc - 0.2, btc, sol))
        else:
            data.extend((make_bar(btc_last, btc - 0.2, btc, timestamp), make_bar(sol_last, sol - 0.1, sol, timestamp), quote(BTC_PERP.id, f"{btc - 0.05:.1f}", f"{btc + 0.05:.1f}", timestamp + 1), quote(SOL_PERP.id, f"{sol - 0.05:.2f}", f"{sol + 0.05:.2f}", timestamp + 1)))
            custom_marks.extend((venue_mark(BTC_PERP.id, Decimal(str(btc)), timestamp), venue_mark(SOL_PERP.id, Decimal(str(sol)), timestamp)))
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(10_000, BTC_PERP.quote_currency)], base_currency=BTC_PERP.quote_currency, default_leverage=Decimal("1"))
    engine.add_instrument(BTC_PERP); engine.add_instrument(SOL_PERP)
    from nautilus_trader.model.identifiers import ClientId
    engine.add_strategy(WaveOverlayStrategy(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP.id, sol_id=SOL_PERP.id, btc_bar_type=btc_last, sol_bar_type=sol_last,
        btc_mark_data_type=venue_mark_data_type(BTC_PERP.id), sol_mark_data_type=venue_mark_data_type(SOL_PERP.id), mark_client_id=ClientId("TEST_MARKS"), active_seed=Decimal("10000"),
        tier_marks=marks, tier_selected_leverage=((BTC_PERP.id, Decimal("40")), (SOL_PERP.id, Decimal("20"))), max_mark_age_ns=86_400_000_000_000,
        seed_bars=tuple(seed), trading_start_open_ns=800 * 86_400_000_000_000,
    )))
    engine.add_data(data, sort=False); engine.add_data(custom_marks, client_id=ClientId("TEST_MARKS"), sort=False); engine.sort_data(); engine.run()
    try:
        fills = engine.trader.generate_order_fills_report()
        assert not fills.empty
        # No seed bar went through on_bar: every fill follows the first live
        # daily session, never a warmup replay decision.
        assert fills["ts_last"].min().value >= 801 * 86_400_000_000_000
    finally:
        engine.dispose()


def test_warmup_only_has_no_native_orders() -> None:
    """Even valid history cannot create orders before the configured live open."""
    btc_last, sol_last = make_bar_type(BTC_PERP.id, PriceType.LAST), make_bar_type(SOL_PERP.id, PriceType.LAST)
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(10_000, BTC_PERP.quote_currency)], base_currency=BTC_PERP.quote_currency, default_leverage=Decimal("1"))
    engine.add_instrument(BTC_PERP); engine.add_instrument(SOL_PERP)
    from nautilus_trader.model.identifiers import ClientId
    engine.add_strategy(WaveOverlayStrategy(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP.id, sol_id=SOL_PERP.id, btc_bar_type=btc_last, sol_bar_type=sol_last,
        btc_mark_data_type=venue_mark_data_type(BTC_PERP.id), sol_mark_data_type=venue_mark_data_type(SOL_PERP.id), mark_client_id=ClientId("TEST_MARKS"), active_seed=Decimal("10000"),
        trading_start_open_ns=999 * 86_400_000_000_000,
    )))
    data, marks = [], []
    for day in range(10):
        timestamp = (day + 1) * 86_400_000_000_000
        data.extend((make_bar(btc_last, 100, 101, timestamp), make_bar(sol_last, 30, 31, timestamp), quote(BTC_PERP.id, "100.0", "100.1", timestamp + 1), quote(SOL_PERP.id, "30.00", "30.01", timestamp + 1)))
        marks.extend((venue_mark(BTC_PERP.id, Decimal("101"), timestamp), venue_mark(SOL_PERP.id, Decimal("31"), timestamp)))
    engine.add_data(data, sort=False); engine.add_data(marks, client_id=ClientId("TEST_MARKS"), sort=False); engine.sort_data(); engine.run()
    try:
        assert engine.trader.generate_order_fills_report().empty
    finally:
        engine.dispose()


def test_native_callback_cache_reconciliation_reenters_on_next_quote_timestamp() -> None:
    """A group close is cache-flat only on callback, then re-entry uses quote time."""
    day = 86_400_000_000_000
    reentry_quote_ts = 3 * day + 3
    btc_last, sol_last = make_bar_type(BTC_PERP.id, PriceType.LAST), make_bar_type(SOL_PERP.id, PriceType.LAST)
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(10_000, BTC_PERP.quote_currency)], base_currency=BTC_PERP.quote_currency, default_leverage=Decimal("1"))
    engine.add_instrument(BTC_PERP); engine.add_instrument(SOL_PERP)
    from nautilus_trader.model.identifiers import ClientId
    strategy = CallbackOrderedReentryProbe(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP.id, sol_id=SOL_PERP.id, btc_bar_type=btc_last, sol_bar_type=sol_last,
        btc_mark_data_type=venue_mark_data_type(BTC_PERP.id), sol_mark_data_type=venue_mark_data_type(SOL_PERP.id),
        mark_client_id=ClientId("TEST_MARKS"), active_seed=Decimal("10000"),
    ), reentry_quote_ts)
    engine.add_strategy(strategy)
    engine.add_data([
        quote(BTC_PERP.id, "100.0", "100.1", day + 1),       # entry fill
        quote(BTC_PERP.id, "101.0", "101.1", 2 * day + 1),   # close fill
        quote(BTC_PERP.id, "102.0", "102.1", reentry_quote_ts),  # queued re-entry
    ], sort=False)
    engine.sort_data(); engine.run()
    try:
        fills = engine.trader.generate_order_fills_report()
        assert len(fills) == 3
        assert list(fills["is_reduce_only"]) == [False, True, False]
        assert strategy.reconciled_after_position_event
        assert strategy.reentry_gate_times == [reentry_quote_ts]
    finally:
        engine.dispose()


def test_paired_marks_liquidate_each_native_leg_on_its_own_next_quote() -> None:
    """A same-minute mark breach is non-executable until each leg's own quote."""
    day = 86_400_000_000_000
    signal_ts = 9 * day
    candidate = Candidate(
        ema_period=2,
        beta_days=2,
        relative_days=2,
        z_history_days=2,
        wave_min_count=1,
        wave_history_days=30,
    )
    seed_values = (100, 110, 90, 110, 90, 110, 90, 110)
    seed = tuple(
        DailyBar(
            datetime.fromtimestamp((index - 1) * 86_400, UTC),
            datetime.fromtimestamp(index * 86_400, UTC),
            datetime.fromtimestamp(index * 86_400, UTC),
            seed_values[index - 2] if index > 1 else value,
            value,
            value * 0.3,
        )
        for index, value in enumerate(seed_values, start=1)
    )
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(10_000, BTC_PERP.quote_currency)], base_currency=BTC_PERP.quote_currency, default_leverage=Decimal("1"))
    engine.add_instrument(BTC_PERP)
    engine.add_instrument(SOL_PERP)
    from nautilus_trader.model.identifiers import ClientId
    marks_client, signals_client = ClientId("TEST_MARKS"), ClientId("TEST_SIGNALS")
    monitor = WaveOverlayWithNativeSolShort(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP.id,
        sol_id=SOL_PERP.id,
        btc_bar_type=make_bar_type(BTC_PERP.id, PriceType.LAST),
        sol_bar_type=make_bar_type(SOL_PERP.id, PriceType.LAST),
        btc_mark_data_type=venue_mark_data_type(BTC_PERP.id),
        sol_mark_data_type=venue_mark_data_type(SOL_PERP.id),
        mark_client_id=marks_client,
        btc_signal_data_type=daily_signal_data_type(BTC_PERP.id),
        sol_signal_data_type=daily_signal_data_type(SOL_PERP.id),
        signal_client_id=signals_client,
        active_seed=Decimal("10000"),
        candidate=candidate,
        seed_bars=seed,
        trading_start_open_ns=8 * day,
        tier_selected_leverage=((BTC_PERP.id, Decimal("40")), (SOL_PERP.id, Decimal("20"))),
        max_mark_age_ns=day,
    ))
    engine.add_strategy(monitor)
    marks = (
        venue_mark(BTC_PERP.id, Decimal("100"), signal_ts),
        venue_mark(SOL_PERP.id, Decimal("30"), signal_ts),
        # Both legs are above maintenance first; the only audit must be the
        # later adverse same-minute pair.
        venue_mark(BTC_PERP.id, Decimal("109"), signal_ts + 3),
        venue_mark(SOL_PERP.id, Decimal("31"), signal_ts + 3),
        venue_mark(BTC_PERP.id, Decimal("1"), signal_ts + 4),
        venue_mark(SOL_PERP.id, Decimal("100"), signal_ts + 4),
        # Duplicate delivery of the breach pair cannot arm twice or submit a
        # second set of liquidation orders.
        venue_mark(BTC_PERP.id, Decimal("1"), signal_ts + 4),
        venue_mark(SOL_PERP.id, Decimal("100"), signal_ts + 4),
        venue_mark(BTC_PERP.id, Decimal("1"), 10 * day),
        venue_mark(SOL_PERP.id, Decimal("100"), 10 * day),
    )
    signals = (
        daily_signal(BTC_PERP.id, Decimal("100"), Decimal("110"), Decimal("90"), Decimal("110"), signal_ts),
        daily_signal(SOL_PERP.id, Decimal("30"), Decimal("33"), Decimal("27"), Decimal("33"), signal_ts),
        # A subsequent valid pair cannot enter again after the fill-confirmed lock.
        daily_signal(BTC_PERP.id, Decimal("1"), Decimal("2"), Decimal("1"), Decimal("1"), 10 * day),
        daily_signal(SOL_PERP.id, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100"), 10 * day),
    )
    quotes = (
        # No quote accompanies the initial mark/signal pair, so no fill can
        # predate this BTC quote.
        quote(BTC_PERP.id, "110.0", "110.1", signal_ts + 1),
        quote(SOL_PERP.id, "30.00", "30.10", signal_ts + 2),
        quote(BTC_PERP.id, "1.0", "1.1", signal_ts + 5),
        quote(SOL_PERP.id, "100.00", "100.10", signal_ts + 6),
        quote(BTC_PERP.id, "1.0", "1.1", 10 * day + 1),
        quote(SOL_PERP.id, "100.00", "100.10", 10 * day + 2),
    )
    engine.add_data(list(marks), client_id=marks_client, sort=False)
    engine.add_data(list(signals), client_id=signals_client, sort=False)
    engine.add_data(list(quotes), sort=False)
    engine.sort_data()
    engine.run()
    try:
        fills = engine.trader.generate_order_fills_report()
        assert len(fills) == 4, (fills, monitor.liquidation_audit)
        assert list(fills["instrument_id"]) == [str(BTC_PERP.id), str(SOL_PERP.id), str(BTC_PERP.id), str(SOL_PERP.id)]
        assert [item.value for item in fills["ts_last"]] == [signal_ts + 1, signal_ts + 2, signal_ts + 5, signal_ts + 6]
        assert [Decimal(str(item)) for item in fills["avg_px"]] == [Decimal("110.1"), Decimal("30.0"), Decimal("1.0"), Decimal("100.1")]
        assert list(fills["is_reduce_only"]) == [False, False, True, True]
        assert len(monitor.liquidation_audit) == 1
        audit = monitor.liquidation_audit[0]
        assert set(audit) == {"trigger_ts", "marked_equity", "tier_maintenance_margin", "status", "close_fills", "close_value", "lockout"}
        assert audit["trigger_ts"] == str(signal_ts + 4)
        assert audit["status"] == "FLAT_LOCKED"
        assert [item["timestamp"] for item in audit["close_fills"]] == [str(signal_ts + 5), str(signal_ts + 6)]
        assert Decimal(audit["close_value"]) > 0
        assert audit["lockout"] == "true"
        assert Decimal(audit["marked_equity"]) <= Decimal(audit["tier_maintenance_margin"])
        assert engine.trader.generate_positions_report()["closing_order_id"].notna().all()
        assert engine.trader.generate_orders_report()["status"].eq("FILLED").all()
        assert not engine.trader.generate_account_report(SIM).empty
    finally:
        engine.dispose()
