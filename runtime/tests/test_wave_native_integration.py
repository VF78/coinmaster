from decimal import Decimal
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.data import Bar, BarSpecification, BarType
from nautilus_trader.model.enums import AccountType, AggregationSource, BarAggregation, OmsType, OrderSide, PriceType, TimeInForce
from nautilus_trader.model.objects import Money, Price, Quantity

from coinmaster.research.native_fixture import BTC_PERP, SIM, SOL_PERP, MarkPriceUpdate, TierMarginPolicy, quote
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig
from coinmaster.domain.wave_overlay import Candidate, DailyBar, Episode
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


class ControlAExitProbe(WaveOverlayStrategy):
    """Opens one SOL leg, then exercises the production SOL exit path."""

    def __init__(self, config: WaveOverlayStrategyConfig) -> None:
        super().__init__(config)
        self.phase = "OPEN"
        self.entry_order_id: str | None = None
        self.entry_filled = False

    def on_quote_tick(self, tick) -> None:
        if tick.instrument_id != self.config.sol_id:
            return
        instrument = self.cache.instrument(tick.instrument_id)
        assert instrument is not None
        if self.phase == "OPEN":
            order = self.order_factory.market(instrument_id=tick.instrument_id, order_side=OrderSide.BUY, quantity=instrument.make_qty(Decimal("1")), time_in_force=TimeInForce.IOC)
            self.entry_order_id = str(order.client_order_id)
            self.phase = "ENTRY_SUBMITTED"
            self.submit_order(order)
        elif self.phase == "EXIT_READY":
            self.phase = "EXIT_SUBMITTED"
            self._submit_intent(Intent("sol-exit", "probe", "SOL_EXIT", None, -1, quantity=1, reason="SOL_Z_FULL_EXIT"), float(tick.bid_price), float(tick.ask_price), None, 0, ts_now=tick.ts_event)

    def on_order_filled(self, event) -> None:
        super().on_order_filled(event)
        if str(event.client_order_id) == self.entry_order_id:
            self.entry_filled = True

    def on_position_event(self, event) -> None:
        super().on_position_event(event)
        if self.entry_filled and self.cache.positions_open():
            self.phase = "EXIT_READY"


class QueuedPauseProbe(WaveOverlayStrategy):
    """A queued entry sees the gate again at the later executable quote."""

    def __init__(self, config: WaveOverlayStrategyConfig) -> None:
        super().__init__(config)
        self.phase = "QUEUE"
        self.allow_increase = True

    def on_quote_tick(self, tick) -> None:
        if tick.instrument_id != self.config.btc_id:
            return
        if self.phase == "QUEUE":
            intent = Intent("queued-entry", "probe", "BTC_ENTRY", None, 1, requested_notional=100)
            self._queued_intents.append((intent, None, 0))
            self._queued_intent_ready_ns[intent.id] = tick.ts_event + 1
            self.allow_increase = False
            self.phase = "BLOCKED"
            return
        super().on_quote_tick(tick)

    def _entries_enabled(self) -> bool:
        return self.allow_increase

    def _tier_allows_increase(self, instrument_id, side, quantity, ts_now: int) -> bool:
        return True


class SideAwareSizingProbe(WaveOverlayStrategy):
    """Submits a buy and a sell with deliberately asymmetric executable books."""

    def __init__(self, config: WaveOverlayStrategyConfig) -> None:
        super().__init__(config)
        self.btc_sent = False
        self.sol_sent = False

    def on_quote_tick(self, tick) -> None:
        if tick.instrument_id == self.config.btc_id and not self.btc_sent:
            self.btc_sent = True
            self._submit_intent(Intent("buy", "probe", "BTC_ENTRY", None, 1, requested_notional=100), float(tick.bid_price), float(tick.ask_price), None, 0, ts_now=tick.ts_event)
        if tick.instrument_id == self.config.sol_id and not self.sol_sent:
            self.sol_sent = True
            self._submit_intent(Intent("sell", "probe", "SOL_ADD", None, -1, requested_notional=100), float(tick.bid_price), float(tick.ask_price), None, 0, ts_now=tick.ts_event)

    def _tier_allows_increase(self, instrument_id, side, quantity, ts_now: int) -> bool:
        return True


class TimeoutLiquidationPreemptionProbe(WaveOverlayStrategy):
    """Arms an oversized queued timeout before a native forced liquidation."""

    def __init__(self, config: WaveOverlayStrategyConfig) -> None:
        super().__init__(config)
        self.btc_opened = False
        self.sol_opened = False
        self.forced_timeout_cleared = False
        self.timeout_id = "timeout-before-liquidation"

    def on_quote_tick(self, tick) -> None:
        instrument = self.cache.instrument(tick.instrument_id)
        assert instrument is not None
        if tick.instrument_id == self.config.btc_id and not self.btc_opened:
            self.btc_opened = True
            self.submit_order(self.order_factory.market(
                instrument_id=tick.instrument_id, order_side=OrderSide.BUY,
                quantity=instrument.make_qty(Decimal("1")), time_in_force=TimeInForce.IOC,
            ))
            return
        if tick.instrument_id == self.config.sol_id and not self.sol_opened:
            self.sol_opened = True
            self.submit_order(self.order_factory.market(
                instrument_id=tick.instrument_id, order_side=OrderSide.BUY,
                quantity=instrument.make_qty(Decimal("1")), time_in_force=TimeInForce.IOC,
            ))
            return
        super().on_quote_tick(tick)

    def on_position_event(self, event) -> None:
        super().on_position_event(event)
        open_ids = {position.instrument_id for position in self.cache.positions_open()}
        if self.forced_timeout_cleared or open_ids != {self.config.btc_id, self.config.sol_id}:
            return
        timeout = Intent(self.timeout_id, "probe", "SOL_EXIT", None, -1, quantity=10, reason="SOL_HARD_TIMEOUT")
        self._domain.episode = Episode("probe", 1, 10_000, 1.0, btc_initial_qty=1, btc_open_qty=1, btc_entry_vwap=100, h=100)
        self._domain.episode.pending[timeout.id] = timeout
        self._mandatory_sol_exit = (timeout, None, 0)
        self._liquidating = True
        self._liquidation_waiting = {self.config.btc_id, self.config.sol_id}
        self._begin_forced_close("LIQUIDATION")
        self.forced_timeout_cleared = self._mandatory_sol_exit is None and timeout.id not in self._domain.episode.pending


def make_bar_type(instrument_id, price_type):
    return BarType(instrument_id, BarSpecification(1, BarAggregation.DAY, price_type), AggregationSource.EXTERNAL)


def make_bar(kind, open_price: float, close_price: float, timestamp: int) -> Bar:
    volume = "1000.000" if kind.instrument_id == BTC_PERP.id else "1000.0"
    precision = 1 if kind.instrument_id == BTC_PERP.id else 2
    price = lambda value: Price.from_str(f"{value:.{precision}f}")
    return Bar(kind, price(open_price), price(max(open_price, close_price)), price(min(open_price, close_price)), price(close_price), Quantity.from_str(volume), timestamp, timestamp)


def native_engine(strategy: WaveOverlayStrategy) -> BacktestEngine:
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(10_000, BTC_PERP.quote_currency)], base_currency=BTC_PERP.quote_currency, default_leverage=Decimal("1"))
    engine.add_instrument(BTC_PERP)
    engine.add_instrument(SOL_PERP)
    engine.add_strategy(strategy)
    return engine


def probe_config() -> WaveOverlayStrategyConfig:
    from nautilus_trader.model.identifiers import ClientId
    return WaveOverlayStrategyConfig(
        btc_id=BTC_PERP.id, sol_id=SOL_PERP.id,
        btc_bar_type=make_bar_type(BTC_PERP.id, PriceType.LAST), sol_bar_type=make_bar_type(SOL_PERP.id, PriceType.LAST),
        btc_mark_data_type=venue_mark_data_type(BTC_PERP.id), sol_mark_data_type=venue_mark_data_type(SOL_PERP.id),
        mark_client_id=ClientId("TEST_MARKS"), active_seed=Decimal("10000"),
    )


def test_native_mark_callback_runs_the_existing_mark_first_liquidation_gate() -> None:
    # This is Nautilus 1.231's actual callback type, rather than the separate
    # research fixture that uses a different mark representation.
    from nautilus_trader.model.data import MarkPriceUpdate as NativeMarkPriceUpdate

    strategy = WaveOverlayStrategy(probe_config())
    observed: list[int] = []
    strategy._check_mark_first_liquidation = observed.append
    update = NativeMarkPriceUpdate(BTC_PERP.id, Price.from_str("100.0"), 123, 124)
    strategy.on_mark_price(update)
    assert update.value == Price.from_str("100.0")
    assert observed == [123]


def test_consecutive_timeout_preserves_first_mandatory_intent() -> None:
    strategy = WaveOverlayStrategy(probe_config())
    first = Intent("timeout-1", "episode", "SOL_EXIT", None, -1, quantity=1, reason="SOL_HARD_TIMEOUT")
    duplicate = Intent("timeout-2", "episode", "SOL_EXIT", None, -1, quantity=1, reason="SOL_HARD_TIMEOUT")
    strategy._domain.episode = Episode("episode", 1, 10_000, 1.0, sol_qty=1)
    strategy._domain.episode.pending[first.id] = first
    strategy._domain.episode.pending[duplicate.id] = duplicate
    strategy._mandatory_sol_exit = (first, None, 0)
    strategy._preempt_with_mandatory_sol_exit(duplicate, None, 1)
    assert strategy._mandatory_sol_exit[0].id == first.id
    assert first.id in strategy._domain.episode.pending
    assert duplicate.id not in strategy._domain.episode.pending


def test_native_partial_btc_callbacks_requeue_targets_and_only_unsold_tp_leaves() -> None:
    strategy = WaveOverlayStrategy(probe_config())
    episode = Episode(
        "episode", 1, 10_000, 1.0, wave_levels=(0.01, 0.02, 0.03),
    )
    strategy._domain.episode = episode
    entry = Intent("entry", "episode", "BTC_ENTRY", None, 1, quantity=1)
    episode.pending[entry.id] = entry
    strategy._pending_by_order["entry-order"] = entry
    strategy._sigma_by_order["entry-order"] = None
    strategy._decision_index_by_order["entry-order"] = 7
    strategy._apply_confirmed_domain_fill(entry, "entry-order", 0.5, 100, 1, False)
    strategy.on_order_canceled(SimpleNamespace(client_order_id="entry-order", ts_event=2))
    assert {item[0].level for item in strategy._queued_intents} == {0, 1, 2}

    target = strategy._queued_intents.pop(0)[0]
    strategy._queued_intent_ready_ns.pop(target.id)
    strategy._pending_by_order["tp-order"] = target
    strategy._sigma_by_order["tp-order"] = None
    strategy._decision_index_by_order["tp-order"] = 8
    strategy._apply_confirmed_domain_fill(target, "tp-order", target.quantity / 2, 101, 3, False)
    strategy.on_order_canceled(SimpleNamespace(client_order_id="tp-order", ts_event=4))
    replacement = next(item[0] for item in strategy._queued_intents if item[0].level == target.level)
    assert replacement.quantity == target.quantity / 2
    strategy._queued_intents.remove(next(item for item in strategy._queued_intents if item[0].id == replacement.id))
    strategy._queued_intent_ready_ns.pop(replacement.id)
    strategy._pending_by_order["tp-order-2"] = replacement
    strategy._sigma_by_order["tp-order-2"] = None
    strategy._decision_index_by_order["tp-order-2"] = 9
    strategy._apply_confirmed_domain_fill(replacement, "tp-order-2", replacement.quantity / 2, 102, 5, False)
    strategy.on_order_canceled(SimpleNamespace(client_order_id="tp-order-2", ts_event=6))
    final = next(item[0] for item in strategy._queued_intents if item[0].level == target.level)
    strategy._apply_confirmed_domain_fill(final, "tp-order-3", final.quantity, 103, 7, True)
    assert target.level in strategy._domain.episode.btc_filled_tps
    assert strategy._domain.episode.sol_right_fraction[target.level] == 1.0


def test_control_a_sol_exit_is_taker_ioc_at_zero_spread() -> None:
    strategy = ControlAExitProbe(probe_config())
    engine = native_engine(strategy)
    engine.add_data([quote(SOL_PERP.id, f"{price:.2f}", f"{price:.2f}", ts) for ts, price in enumerate((100, 101, 102, 103, 104), start=1)], sort=False)
    engine.sort_data(); engine.run()
    try:
        fills = engine.trader.generate_order_fills_report()
        assert len(fills) == 2
        assert list(fills["is_reduce_only"]) == [False, True]
        sol_exit = next(item for item in strategy.fill_audit if item["action"] == "SOL_EXIT")
        assert sol_exit["post_only"] == "false"
        assert sol_exit["native_liquidity_side"] == "TAKER"
    finally:
        engine.dispose()


def test_native_order_submission_hook_receives_enum_names_not_numeric_values() -> None:
    class Capture:
        def __init__(self): self.calls = []; self.strategy = None
        def __call__(self, **kwargs):
            order_id = kwargs["client_order_id"]
            assert order_id in self.strategy._pending_by_order
            assert order_id in self.strategy._sigma_by_order
            assert order_id in self.strategy._decision_index_by_order
            self.calls.append(kwargs)
            return True
        def acknowledge(self, _client_order_id): pass
        def terminal(self, _client_order_id): pass

    capture = Capture()
    strategy = ControlAExitProbe(probe_config().__replace__(submission_sink=capture))
    capture.strategy = strategy
    engine = native_engine(strategy)
    engine.add_data([quote(SOL_PERP.id, f"{price:.2f}", f"{price:.2f}", ts) for ts, price in enumerate((100, 101, 102, 103, 104), start=1)], sort=False)
    engine.sort_data(); engine.run()
    try:
        assert capture.calls
        assert capture.calls[-1]["order_kind"] == "MARKET"
        assert capture.calls[-1]["time_in_force"] == "IOC"
    finally:
        engine.dispose()


def test_queued_increase_is_rejected_after_pause_gate_transition() -> None:
    strategy = QueuedPauseProbe(probe_config())
    engine = native_engine(strategy)
    engine.add_data([quote(BTC_PERP.id, "100.0", "100.1", ts) for ts in (1, 2)], sort=False)
    engine.sort_data(); engine.run()
    try:
        assert engine.trader.generate_order_fills_report().empty
        assert strategy.pre_submit_gate_blocks == [{"timestamp": "2", "intent_id": "queued-entry", "action": "BTC_ENTRY", "reason": "PRE_SUBMIT_INCREASE_GATE_OR_MINIMUM"}]
    finally:
        engine.dispose()


def test_notional_sizing_uses_buy_ask_and_sell_bid_before_rounding() -> None:
    strategy = SideAwareSizingProbe(probe_config())
    engine = native_engine(strategy)
    engine.add_data([
        quote(BTC_PERP.id, "100.0", "110.0", 1),
        quote(SOL_PERP.id, "30.00", "40.00", 2),
    ], sort=False)
    engine.sort_data(); engine.run()
    try:
        fills = engine.trader.generate_order_fills_report()
        quantities = {row.instrument_id: Decimal(str(row.filled_qty)) for row in fills.itertuples()}
        assert quantities[str(BTC_PERP.id)] == Decimal("0.909")  # 100 / ask 110, then 0.001 step.
        assert quantities[str(SOL_PERP.id)] == Decimal("3.3")  # 100 / bid 30, then 0.1 step.
    finally:
        engine.dispose()


def test_forced_liquidation_supersedes_timeout_and_closes_native_remaining_leaves() -> None:
    strategy = TimeoutLiquidationPreemptionProbe(probe_config())
    engine = native_engine(strategy)
    engine.add_data([
        quote(BTC_PERP.id, "100.0", "100.1", 1),  # open BTC
        quote(SOL_PERP.id, "30.00", "30.01", 2),  # open SOL, arm timeout then liquidation
        quote(BTC_PERP.id, "99.0", "99.1", 3),    # must not wait for a SOL quote
        quote(SOL_PERP.id, "29.00", "29.01", 4),  # close actual 1 SOL, not timeout's 10
    ], sort=False)
    engine.sort_data(); engine.run()
    try:
        fills = engine.trader.generate_order_fills_report()
        btc_reduction = fills[(fills["instrument_id"] == str(BTC_PERP.id)) & fills["is_reduce_only"]].iloc[0]
        sol_reduction = fills[(fills["instrument_id"] == str(SOL_PERP.id)) & fills["is_reduce_only"]].iloc[0]
        assert btc_reduction["ts_last"].value == 3
        assert Decimal(str(sol_reduction["filled_qty"])) == Decimal("1")
        assert strategy.forced_timeout_cleared
        assert all(item["action"] != "SOL_EXIT" for item in strategy.fill_audit)
    finally:
        engine.dispose()


def test_resting_btc_tp_uses_current_confirmed_fill_cycle_not_target_creation() -> None:
    strategy = WaveOverlayStrategy(probe_config())
    strategy._bars = [object(), object(), object()]  # Only current cycle length is relevant here.
    resting_target = Intent("resting-tp", "probe", "BTC_REDUCE", 0, -1, quantity=1, decision_index=0)
    strategy._decision_index_by_order["resting-order"] = 0
    assert strategy._confirmed_fill_cycle(resting_target, "resting-order") == 2


def test_native_wave_strategy_submits_and_confirms_fills_from_four_causal_bar_streams() -> None:
    btc_last, sol_last = make_bar_type(BTC_PERP.id, PriceType.LAST), make_bar_type(SOL_PERP.id, PriceType.LAST)
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(10_000, BTC_PERP.quote_currency)], base_currency=BTC_PERP.quote_currency, default_leverage=Decimal("1"))
    engine.add_instrument(BTC_PERP)
    engine.add_instrument(SOL_PERP)
    from nautilus_trader.model.identifiers import ClientId
    marks = tuple(MarkPriceUpdate(BTC_PERP.id, Decimal("100"), day * 86_400_000_000_000) for day in range(1, 851)) + tuple(MarkPriceUpdate(SOL_PERP.id, Decimal("30"), day * 86_400_000_000_000) for day in range(1, 851))
    strategy = WaveOverlayStrategy(WaveOverlayStrategyConfig(btc_id=BTC_PERP.id, sol_id=SOL_PERP.id, btc_bar_type=btc_last, sol_bar_type=sol_last, btc_mark_data_type=venue_mark_data_type(BTC_PERP.id), sol_mark_data_type=venue_mark_data_type(SOL_PERP.id), mark_client_id=ClientId("TEST_MARKS"), active_seed=Decimal("10000"), margin_policy=TierMarginPolicy(marks, {BTC_PERP.id: Decimal("40"), SOL_PERP.id: Decimal("20")}, 86_400_000_000_000)))
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
        # v3 can intentionally retain a genuine post-only reduce-only target
        # until a later quote reaches it; it must not convert that target to an
        # eager market close merely to make this fixture flat.
        open_orders = engine.trader._cache.orders_open()
        assert all(order.is_reduce_only and order.is_post_only for order in open_orders)
        assert not engine.trader.generate_account_report(SIM).empty
        assert len(strategy._latest_marks) <= 2
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
        margin_policy=TierMarginPolicy(marks, {BTC_PERP.id: Decimal("40"), SOL_PERP.id: Decimal("20")}, 86_400_000_000_000),
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
        margin_policy=TierMarginPolicy((), {BTC_PERP.id: Decimal("40"), SOL_PERP.id: Decimal("20")}, day),
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
        assert audit["lockout"] == "true"
        # Hand reconciliation uses native fills/commissions only; no shadow
        # liquidation or PnL model is introduced by this fixture.
        btc_quantity = Decimal(str(fills.iloc[0]["filled_qty"]))
        sol_quantity = Decimal(str(fills.iloc[1]["filled_qty"]))
        btc_pnl = (Decimal(str(fills.iloc[2]["avg_px"])) - Decimal(str(fills.iloc[0]["avg_px"]))) * btc_quantity
        sol_pnl = (Decimal(str(fills.iloc[1]["avg_px"])) - Decimal(str(fills.iloc[3]["avg_px"]))) * sol_quantity
        fees = sum((Decimal(str(item).split()[0]) for row in fills["commissions"] for item in row), Decimal("0"))
        close_fees = sum((Decimal(str(item).split()[0]) for row in fills.iloc[2:]["commissions"] for item in row), Decimal("0"))
        final_cash = Decimal(engine.trader.generate_account_report(SIM)["total"].iloc[-1].split()[0])
        assert final_cash == Decimal("10000") + btc_pnl + sol_pnl - fees
        # Entry sizing now uses the executable ask, not the prior bid. The
        # native liquidation remains reduce-only and reconciles identically.
        assert close_fees == Decimal("50.86743800")
        assert Decimal(audit["close_value"]) == btc_quantity * Decimal("1.0") + sol_quantity * Decimal("100.1")
        assert Decimal(audit["marked_equity"]) <= Decimal(audit["tier_maintenance_margin"])
        assert engine.trader.generate_positions_report()["closing_order_id"].notna().all()
        assert engine.trader.generate_orders_report()["status"].eq("FILLED").all()
        assert engine.trader._cache.positions_open() == []
        assert engine.trader._cache.orders_open() == []
        assert not engine.trader.generate_account_report(SIM).empty
    finally:
        engine.dispose()



def test_btc_entry_local_denial_and_native_zero_terminal_are_distinct() -> None:
    class MissingInstrumentProbe(WaveOverlayStrategy):
        @property
        def cache(self):
            return SimpleNamespace(instrument=lambda _instrument_id: None)

    strategy = MissingInstrumentProbe(probe_config())
    entry = Intent("local-entry", "episode", "BTC_ENTRY", None, 1, requested_notional=100)
    strategy._domain.episode = Episode("episode", 1, 10_000, 1.0)
    strategy._domain.episode.pending[entry.id] = entry
    strategy._submit_intent(entry, 99, 100, None, 0, ts_now=1)
    assert strategy._domain.episode is None
    assert strategy.daily_decision_status()["reason"] == "LOCAL_ENTRY_DENIED:INSTRUMENT_MISSING"

    rejected = WaveOverlayStrategy(probe_config())
    entry = Intent("native-entry", "episode-2", "BTC_ENTRY", None, 1, requested_notional=100)
    rejected._domain.episode = Episode("episode-2", 1, 10_000, 1.0)
    rejected._domain.episode.pending[entry.id] = entry
    rejected._pending_by_order["order-1"] = entry
    rejected.on_order_rejected(SimpleNamespace(client_order_id="order-1"))
    assert rejected._domain.episode is None
    assert rejected.daily_decision_status()["reason"] == "NATIVE_ENTRY_ZERO_FILL_TERMINAL"


def test_unknown_ack_stays_pending_until_proven_zero_or_partial_terminal() -> None:
    strategy = WaveOverlayStrategy(probe_config())
    entry = Intent("unknown-entry", "episode", "BTC_ENTRY", None, 1, requested_notional=100)
    strategy._domain.episode = Episode("episode", 1, 10_000, 1.0)
    strategy._domain.episode.pending[entry.id] = entry
    strategy._pending_by_order["order-unknown"] = entry
    # A delayed ACK, even after the next daily signal, is no fill evidence.
    strategy.on_order_event(SimpleNamespace(client_order_id="order-unknown", ts_event=1))
    assert strategy._domain.episode is not None
    assert entry.id in strategy._domain.episode.pending
    strategy.on_order_expired(SimpleNamespace(client_order_id="order-unknown"))
    assert strategy._domain.episode is None

    partial = WaveOverlayStrategy(probe_config())
    entry = Intent("partial-entry", "episode-2", "BTC_ENTRY", None, 1, requested_notional=100)
    partial._domain.episode = Episode("episode-2", 1, 10_000, 1.0)
    partial._domain.episode.pending[entry.id] = entry
    partial._pending_by_order["order-partial"] = entry
    partial._domain.on_fill(entry.id, 0.25, 100, datetime(2023, 1, 1, tzinfo=UTC))
    partial.on_order_canceled(SimpleNamespace(client_order_id="order-partial", ts_event=2))
    assert partial._domain.episode is not None
    assert partial._domain.episode.btc_open_qty == 0.25
    assert partial.daily_decision_status()["reason"] == "PARTIAL_ENTRY_RETAINED"


def test_short_native_replay_completes_two_episodes_with_sol_exits_and_flat_cash(tmp_path) -> None:
    """Feature-only seed; one accelerated native engine closes two episodes."""
    from nautilus_trader.model.identifiers import ClientId
    from coinmaster.ops.paper import PaperRuntime

    journal = PaperRuntime(tmp_path / "two-episodes.sqlite", "native-replay", 10**20)
    journal.acquire()

    class JournalSink:
        def __call__(self, **item) -> bool:
            return journal.record_submission(
                client_order_id=item["client_order_id"], intent_id=item["intent_id"],
                episode_id=item["episode_id"], action=item["action"],
                instrument_id=item["instrument_id"], quantity=item["quantity"],
                reduce_only=item["reduce_only"],
            )

        def acknowledge(self, client_order_id: str) -> None:
            journal.acknowledge_submission(client_order_id)

        def terminal(self, client_order_id: str) -> None:
            journal.terminal_submission(client_order_id)

    class ReplayTrace(WaveOverlayStrategy):
        def __init__(self, config: WaveOverlayStrategyConfig) -> None:
            super().__init__(config)
            self.entry_episodes: list[str] = []
            self.flat_accounts: list[tuple[Decimal, Decimal, Decimal]] = []

        def on_order_filled(self, event) -> None:
            intent = self._pending_by_order.get(str(event.client_order_id))
            if intent is not None and intent.action == "BTC_ENTRY" and intent.episode_id not in self.entry_episodes:
                self.entry_episodes.append(intent.episode_id)
            super().on_order_filled(event)

        def on_position_event(self, event) -> None:
            super().on_position_event(event)
            if not self.cache.positions_open() and self.fill_audit:
                account = self.cache.account_for_venue(SIM)
                if account is not None:
                    currency = BTC_PERP.quote_currency
                    self.flat_accounts.append((
                        account.balance_total(currency).as_decimal(),
                        account.balance_free(currency).as_decimal(),
                        account.balance_locked(currency).as_decimal(),
                    ))

    day_ns = 86_400_000_000_000
    btc_type = make_bar_type(BTC_PERP.id, PriceType.LAST)
    sol_type = make_bar_type(SOL_PERP.id, PriceType.LAST)
    policy_marks = tuple(
        MarkPriceUpdate(instrument.id, Decimal("100" if instrument.id == BTC_PERP.id else "30"), day * day_ns)
        for instrument in (BTC_PERP, SOL_PERP) for day in range(1, 846)
    )
    seed: list[DailyBar] = []
    live, marks = [], []
    for day in range(845):
        ts = (day + 1) * day_ns
        btc = 100 + day * 0.04 + (6 if (day // 20) % 2 else -6) + (day % 5) * 0.1
        sol = 30 + day * 0.02 + (btc - 100) * 0.30 + (3 if (day // 17) % 2 else -3) + (day % 7) * 0.1
        if day == 807:
            # The first episode is BTC short: a one-day negative SOL residual
            # earns its confirmed-TP SOL right, then reverts through both exits.
            sol -= 6
        if day < 800:
            close = datetime.fromtimestamp(ts / 1_000_000_000, UTC)
            seed.append(DailyBar(close - timedelta(days=1), close, close, btc - 0.2, btc, sol))
            continue
        live.extend((
            make_bar(btc_type, btc - 0.2, btc, ts),
            make_bar(sol_type, sol - 0.1, sol, ts),
            quote(BTC_PERP.id, f"{btc - 0.05:.1f}", f"{btc + 0.05:.1f}", ts + 1),
            quote(SOL_PERP.id, f"{sol - 0.05:.2f}", f"{sol + 0.05:.2f}", ts + 1),
        ))
        marks.extend((
            venue_mark(BTC_PERP.id, Decimal(str(btc)), ts),
            venue_mark(SOL_PERP.id, Decimal(str(sol)), ts),
        ))
    strategy = ReplayTrace(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP.id, sol_id=SOL_PERP.id, btc_bar_type=btc_type, sol_bar_type=sol_type,
        btc_mark_data_type=venue_mark_data_type(BTC_PERP.id),
        sol_mark_data_type=venue_mark_data_type(SOL_PERP.id),
        mark_client_id=ClientId("TEST_MARKS"), active_seed=Decimal("10000"),
        margin_policy=TierMarginPolicy(
            policy_marks, {BTC_PERP.id: Decimal("40"), SOL_PERP.id: Decimal("20")}, day_ns,
        ),
        seed_bars=tuple(seed), trading_start_open_ns=800 * day_ns,
        event_sink=journal.record_native_event, submission_sink=JournalSink(),
        # Bound this acceptance to two entries while preserving all strategy rules.
        entries_gate=lambda: len(strategy.entry_episodes) < 2,
    ))
    engine = native_engine(strategy)
    engine.add_data(live, sort=False)
    engine.add_data(marks, client_id=ClientId("TEST_MARKS"), sort=False)
    engine.sort_data()
    engine.run()
    try:
        fills = strategy.fill_audit
        assert [(row["action"], int(row["fill_ns"]) // day_ns) for row in fills] == [
            ("BTC_ENTRY", 801),
            ("BTC_REDUCE", 806), ("BTC_REDUCE", 806), ("BTC_REDUCE", 806),
            ("SOL_ADD", 808), ("SOL_HALF_EXIT", 809), ("SOL_EXIT", 810),
            ("FORCED_CLOSE", 821), ("BTC_ENTRY", 822),
            ("FORCED_CLOSE", 841), ("FORCED_CLOSE", 841),
            ("FORCED_CLOSE", 841), ("FORCED_CLOSE", 841),
        ]
        assert len(strategy.entry_episodes) == 2
        assert strategy.entry_episodes[0] != strategy.entry_episodes[1]
        first_entry = Decimal(fills[0]["qty"])
        tps = fills[1:4]
        assert [row["reason"] for row in tps] == ["BTC_TP1", "BTC_TP2", "BTC_TP3"]
        assert all(row["post_only"] == "true" and row["native_liquidity_side"] == "MAKER" for row in tps)
        for row, fraction in zip(tps, (Decimal("0.15"), Decimal("0.25"), Decimal("0.35"))):
            assert 0 <= first_entry * fraction - Decimal(row["qty"]) < Decimal("0.001")
        assert Decimal(fills[4]["qty"]) == Decimal(fills[5]["qty"]) + Decimal(fills[6]["qty"])
        assert first_entry == sum((Decimal(row["qty"]) for row in tps), Decimal("0")) + Decimal(fills[7]["qty"])
        assert all(Decimal(row["commission"]) > 0 for row in fills)
        assert all(row["commission_currency"] == str(BTC_PERP.quote_currency) for row in fills)
        second_entry = Decimal(fills[8]["qty"])
        assert second_entry == sum((Decimal(row["qty"]) for row in fills[9:]), Decimal("0"))
        assert len(strategy.flat_accounts) >= 2
        first_flat_total, first_flat_free, first_flat_locked = strategy.flat_accounts[0]
        assert first_flat_total == first_flat_free and first_flat_locked == 0
        assert first_flat_total != Decimal("10000")
        flat_total, flat_free, flat_locked = strategy.flat_accounts[-1]
        assert flat_total == flat_free and flat_locked == 0
        native_fills = engine.trader.generate_order_fills_report()
        assert len(native_fills) == len(fills)
        native_positions = engine.trader.generate_positions_report().to_dict("records")
        assert len(native_positions) == 3 and all(row["side"] == "FLAT" for row in native_positions)
        native_fees = sum((Decimal(str(fee).split()[0]) for row in native_positions for fee in row["commissions"]), Decimal("0"))
        assert native_fees == sum((Decimal(row["commission"]) for row in fills), Decimal("0"))
        assert flat_total == Decimal("10000") + sum((Decimal(str(row["realized_pnl"]).split()[0]) for row in native_positions), Decimal("0"))
        assert strategy._domain.episode is None
        assert engine.trader._cache.positions_open() == []
        assert engine.trader._cache.orders_open() == []
        assert journal.pending_submissions() == []
        fill_events = [item for item in journal.events() if item["kind"] == "fill"]
        assert len(fill_events) == len(fills)
        assert len({item["event_id"] for item in fill_events}) == len(fills)
    finally:
        engine.dispose()
        journal.close()


def test_pinned_market_exit_calls_python_submit_hook_for_tagged_reduce_only_ioc():
    """Native Cython path must remain interceptable before DP journals orders."""
    from nautilus_trader.model.identifiers import ClientId

    class MarketExitHookProbe(WaveOverlayStrategy):
        def __init__(self, config):
            super().__init__(config)
            self.quotes = 0
            self.seen = []
            self.exit_started = False

        def submit_order(self, order, *args, **kwargs):
            self.seen.append((str(order.client_order_id), tuple(order.tags or ()), order.is_reduce_only, order.time_in_force))
            return super().submit_order(order, *args, **kwargs)

        def on_quote_tick(self, tick):
            if tick.instrument_id != self.config.btc_id:
                return
            self.quotes += 1
            if self.quotes == 1:
                instrument = self.cache.instrument(tick.instrument_id)
                self.submit_order(self.order_factory.market(
                    instrument_id=tick.instrument_id, order_side=OrderSide.BUY,
                    quantity=instrument.make_qty(Decimal("1")), time_in_force=TimeInForce.IOC,
                ))
            elif self.quotes == 2:
                self.exit_started = True
                self.market_exit()

    config = WaveOverlayStrategyConfig(
        btc_id=BTC_PERP.id, sol_id=SOL_PERP.id,
        btc_bar_type=make_bar_type(BTC_PERP.id, PriceType.LAST),
        sol_bar_type=make_bar_type(SOL_PERP.id, PriceType.LAST),
        btc_mark_data_type=venue_mark_data_type(BTC_PERP.id),
        sol_mark_data_type=venue_mark_data_type(SOL_PERP.id),
        mark_client_id=ClientId("TEST_MARKS"), active_seed=Decimal("10000"),
        market_exit_time_in_force=TimeInForce.IOC, market_exit_reduce_only=True,
    )
    strategy = MarketExitHookProbe(config)
    engine = native_engine(strategy)
    engine.add_data([
        quote(BTC_PERP.id, "100.0", "100.1", 1),
        quote(BTC_PERP.id, "101.0", "101.1", 2),
        quote(BTC_PERP.id, "102.0", "102.1", 3),
    ], sort=False)
    engine.sort_data(); engine.run()
    try:
        assert strategy.exit_started
        tagged = [item for item in strategy.seen if "MARKET_EXIT" in item[1]]
        assert len(tagged) == 1
        assert tagged[0][2:] == (True, TimeInForce.IOC)
        fills = engine.trader.generate_order_fills_report()
        assert len(fills) == 2
        assert list(fills["is_reduce_only"]) == [False, True]
    finally:
        engine.dispose()


@pytest.mark.parametrize("fail_exit", [False, True])
def test_deposit_protection_native_market_exit_journals_once_and_stays_latched(tmp_path, fail_exit):
    """Actual native quote, position, cash and fill callbacks drive a durable exit."""
    from nautilus_trader.model.identifiers import ClientId
    from coinmaster.ops.paper import PaperRuntime

    journal = PaperRuntime(tmp_path / "deposit-native.sqlite", "deposit-native", 10**20)
    journal.acquire()

    class SubmissionSink:
        def __call__(self, **item):
            return journal.record_submission(
                client_order_id=item["client_order_id"], intent_id=item["intent_id"],
                episode_id=item["episode_id"], action=item["action"],
                instrument_id=item["instrument_id"], quantity=item["quantity"],
                reduce_only=item["reduce_only"],
            )

        def acknowledge(self, oid):
            journal.acknowledge_submission(oid)

        def terminal(self, oid):
            journal.terminal_submission(oid)

    def native_current_equity(strategy):
        account = strategy.cache.account_for_venue(SIM)
        if account is None:
            return None
        total = account.balance_total(BTC_PERP.quote_currency).as_decimal()
        for position in strategy.cache.positions_open():
            latest = strategy.cache.quote_tick(position.instrument_id)
            if latest is None:
                return None
            total += position.unrealized_pnl(latest.bid_price).as_decimal()
        return total

    class DepositNativeProbe(WaveOverlayStrategy):
        def __init__(self, config):
            super().__init__(config)
            self.quotes = 0
            self.rejected_increase = False
            self.exit_attempts = 0

        def market_exit(self):
            self.exit_attempts += 1
            if fail_exit:
                raise RuntimeError("NATIVE_EXIT_FAILED")
            return super().market_exit()

        def on_quote_tick(self, tick):
            if tick.instrument_id != self.config.btc_id:
                return
            self.quotes += 1
            if self.quotes == 1:
                assert self._deposit_check()
                instrument = self.cache.instrument(tick.instrument_id)
                self.submit_order(self.order_factory.market(
                    instrument_id=tick.instrument_id, order_side=OrderSide.BUY,
                    quantity=instrument.make_qty(Decimal("75")),
                    time_in_force=TimeInForce.IOC,
                ))
            elif self.quotes >= 2:
                self.rejected_increase = not self._deposit_check()
                if self.quotes == 3:
                    instrument = self.cache.instrument(tick.instrument_id)
                    self.submit_order(self.order_factory.market(
                        instrument_id=tick.instrument_id, order_side=OrderSide.BUY,
                        quantity=instrument.make_qty(Decimal("1")),
                        time_in_force=TimeInForce.IOC,
                    ))

    config = WaveOverlayStrategyConfig(
        btc_id=BTC_PERP.id, sol_id=SOL_PERP.id,
        btc_bar_type=make_bar_type(BTC_PERP.id, PriceType.LAST),
        sol_bar_type=make_bar_type(SOL_PERP.id, PriceType.LAST),
        btc_mark_data_type=venue_mark_data_type(BTC_PERP.id),
        sol_mark_data_type=venue_mark_data_type(SOL_PERP.id),
        mark_client_id=ClientId("TEST_MARKS"), active_seed=Decimal("10000"),
        market_exit_time_in_force=TimeInForce.IOC, market_exit_reduce_only=True,
        deposit_runtime=journal, deposit_instance_id="native-test",
        deposit_account_id="SIM-001", deposit_equity_reader=native_current_equity,
        deposit_initialization_allowed=lambda: True,
        submission_sink=SubmissionSink(), event_sink=journal.record_native_event,
    )
    strategy = DepositNativeProbe(config)
    engine = native_engine(strategy)
    engine.add_data([
        quote(BTC_PERP.id, "100.0", "100.1", 1),
        quote(BTC_PERP.id, "1.0", "1.1", 2),
        quote(BTC_PERP.id, "1.0", "1.1", 2_000_000_000),
    ], sort=False)
    engine.sort_data(); engine.run()
    try:
        fills = engine.trader.generate_order_fills_report()
        assert len(fills) == (1 if fail_exit else 2)
        assert strategy.rejected_increase
        assert strategy._deposit.latched
        assert strategy.exit_attempts == 1
        assert strategy.deposit_projection()["state"] == ("EXIT_INCOMPLETE" if fail_exit else "TRIPPED_FLAT")
        assert bool(engine.trader._cache.positions_open()) == fail_exit
        assert not journal.pending_submissions()
        if not fail_exit:
            assert [item["action"] for item in strategy.fill_audit][-1] == "MARKET_EXIT"
        assert len([item for item in journal.events() if item["kind"] == "fill"]) == len(fills)
        saved = journal.deposit_protection_state(
            instance_id="native-test", account_id="SIM-001",
        )
        assert saved["latched"] and saved["exit_state"] == ("EXIT_INCOMPLETE" if fail_exit else "TRIPPED_FLAT")
        journal.entry_control_command("resume-new-entries", "resume-keeps-latch")
        assert strategy.deposit_projection()["state"] != "ARMED"
        with pytest.raises(ValueError, match="DEPOSIT_CONTROL_REQUIRES_PAUSED_CONFIRMED_FLAT"):
            strategy.apply_deposit_control("reset-deposit-protection", "reset-before-pause", confirm=True)
        journal.entry_control_command("pause-new-entries", "pause-for-dp")
        if fail_exit:
            with pytest.raises(ValueError, match="DEPOSIT_CONTROL_REQUIRES_PAUSED_CONFIRMED_FLAT"):
                strategy.apply_deposit_control("reset-deposit-protection", "reset-open", confirm=True)
        else:
            # A flat process cache alone is insufficient: only a current,
            # reconciled, account-bearing flat journal may authorize control.
            with pytest.raises(ValueError, match="DEPOSIT_CONTROL_REQUIRES_PAUSED_CONFIRMED_FLAT"):
                strategy.apply_deposit_control(
                    "set-deposit-protection", "before-flat-checkpoint", drawdown_limit_percent=40,
                )
            journal.snapshot(
                ts_ns=strategy.clock.timestamp_ns(), positions=[], orders=[], funding_event_ids=[],
                native_account_total=str(native_current_equity(strategy)), strategy_restartable=True,
            )
            assert journal.coherent_snapshot() and journal.recovery_state() == "FLAT_RESTART"
            changed = strategy.apply_deposit_control(
                "set-deposit-protection", "limit-40", drawdown_limit_percent=40,
            )
            assert changed["drawdown_limit_percent"] == 40
            assert journal.deposit_audit_action("deposit:control:limit-40") == "set-deposit-protection:40"
            assert strategy.apply_deposit_control(
                "set-deposit-protection", "limit-40", drawdown_limit_percent=40,
            )["drawdown_limit_percent"] == 40
            reset = strategy.apply_deposit_control(
                "reset-deposit-protection", "reset-flat", confirm=True,
            )
            assert reset["state"] == "ARMED" and reset["high_water_equity"] == reset["equity"]
            assert not journal.deposit_protection_state(
                instance_id="native-test", account_id="SIM-001",
            )["latched"]
    finally:
        engine.dispose()
        journal.close()


def test_latched_deposit_exit_suppresses_late_btc_tp_partial_cancel_and_sol_reductions():
    """Late native callbacks update confirmed leaves but cannot launch legacy closes."""
    import msgspec
    from nautilus_trader.model.enums import LiquiditySide, OrderType
    from coinmaster.domain.deposit_protection import DepositProtection

    class FakeCache:
        def instrument(self, instrument_id):
            return {BTC_PERP.id: BTC_PERP, SOL_PERP.id: SOL_PERP}.get(instrument_id)

        def order(self, _order_id):
            return SimpleNamespace(is_closed=False, instrument_id=BTC_PERP.id)

        def orders_open(self):
            return []

    class RaceProbe(WaveOverlayStrategy):
        @property
        def cache(self):
            return self.fake_cache

    config = msgspec.structs.replace(
        probe_config(), deposit_runtime=SimpleNamespace(deposit_protection_state=lambda **_kwargs: None),
    )
    strategy = RaceProbe(config)
    strategy.fake_cache = FakeCache()
    strategy._deposit = DepositProtection()
    strategy._deposit.initialize(Decimal("20000"), 1)
    assert strategy._deposit.observe(Decimal("10000"), 2) == (True, True)
    episode = Episode(
        "two-leg", 1, 20000, 1.0, btc_initial_qty=1.0, btc_open_qty=1.0,
        btc_entry_vwap=100.0, wave_levels=(0.1, 0.2, 0.3), sol_qty=2.0,
    )
    tp = Intent("tp-late", "two-leg", "BTC_REDUCE", 0, -1, quantity=0.5)
    sol = Intent("sol-late", "two-leg", "SOL_EXIT", None, -1, quantity=2.0)
    episode.pending[tp.id] = tp
    episode.pending[sol.id] = sol
    episode.btc_tps.add(0)
    episode.resting_reductions.add(tp.id)
    strategy._domain.episode = episode
    strategy._pending_by_order["tp-order"] = tp
    strategy._sigma_by_order["tp-order"] = None
    strategy._decision_index_by_order["tp-order"] = 0
    strategy._queued_intents.append((sol, None, 0))
    strategy._mandatory_sol_exit = (sol, None, 0)
    strategy._forced_close_reason = "LIQUIDATION"
    attempted = []
    strategy._submit_intent = lambda *args, **kwargs: attempted.append("legacy-intent")
    strategy.on_quote_tick(quote(BTC_PERP.id, "100.0", "100.1", 3))
    strategy.on_quote_tick(quote(SOL_PERP.id, "30.0", "30.1", 4))
    strategy._check_mark_first_liquidation(5)
    assert strategy.submit_order(SimpleNamespace(is_reduce_only=True, tags=())) is None
    assert not attempted and not strategy._liquidating
    # One late native partial TP fill is still applied to the existing domain
    # leaves. Its later cancel must not queue a replacement TP under the latch.
    late = SimpleNamespace(
        trade_id="late-partial", client_order_id="tp-order",
        instrument_id=BTC_PERP.id, last_qty=Quantity.from_str("0.10"),
        last_px=Price.from_str("110.0"), ts_init=1, ts_event=6,
        commission=Money(Decimal("0.01"), BTC_PERP.quote_currency),
        liquidity_side=LiquiditySide.MAKER, order_type=OrderType.LIMIT,
    )
    strategy.on_order_filled(late)
    assert episode.btc_open_qty == pytest.approx(0.9)
    strategy.on_order_canceled(SimpleNamespace(client_order_id="tp-order", ts_event=7))
    assert strategy._queued_intents == [(sol, None, 0)]
    assert episode.sol_qty == 2.0
    assert not attempted


def test_deposit_reset_rejects_durable_open_snapshot_with_empty_new_cache(tmp_path):
    import msgspec
    from coinmaster.domain.deposit_protection import DepositProtection
    from coinmaster.ops.paper import PaperRuntime

    path = tmp_path / "restarted-open.sqlite"
    first = PaperRuntime(path, "same-account", 10**20)
    first.acquire()
    state = DepositProtection()
    state.initialize(Decimal("20000"), 1)
    state.observe(Decimal("10000"), 2)
    state.exit_state = "TRIPPED_FLAT"  # A stale local claim is not restart proof.
    first.save_deposit_protection(
        instance_id="native-test", account_id="SIM-001", action="TRIGGER",
        event_key="deposit:trigger:2", state=state.durable(), ts_ns=2,
    )
    first.snapshot(
        ts_ns=3, positions=[{"instrument_id": str(BTC_PERP.id), "signed_quantity": "1"}],
        orders=[], funding_event_ids=[], native_account_total="10000", strategy_restartable=True,
    )
    first.close()
    restarted = PaperRuntime(path, "same-account", 10**20)
    restarted.acquire()
    restarted.entry_control_command("pause-new-entries", "paused-open")
    assert restarted.recovery_state() == "MANAGE_ONLY_DURABLE_OPEN_STATE"

    class EmptyCacheProbe(WaveOverlayStrategy):
        @property
        def cache(self):
            return SimpleNamespace(
                positions_open=lambda: [], orders_open=lambda: [], orders_inflight=lambda: [],
            )

    config = msgspec.structs.replace(
        probe_config(), deposit_runtime=restarted, deposit_instance_id="native-test",
        deposit_account_id="SIM-001", deposit_equity_reader=lambda _strategy: Decimal("10000"),
    )
    strategy = EmptyCacheProbe(config)
    for command, kwargs in (
        ("set-deposit-protection", {"drawdown_limit_percent": 40}),
        ("reset-deposit-protection", {"confirm": True}),
    ):
        with pytest.raises(ValueError, match="DEPOSIT_CONTROL_REQUIRES_PAUSED_CONFIRMED_FLAT"):
            strategy.apply_deposit_control(command, command, **kwargs)
    saved = restarted.deposit_protection_state(
        instance_id="native-test", account_id="SIM-001",
    )
    assert saved["high_water_equity"] == "20000" and saved["latched"]
    restarted.close()


def test_deposit_control_on_initial_confirmed_flat_native_run(tmp_path):
    """A pristine account can configure p after a coherent flat checkpoint."""
    import msgspec
    from coinmaster.ops.paper import PaperRuntime

    journal = PaperRuntime(tmp_path / "first-run.sqlite", "first-run", 10**20)
    journal.acquire()
    assert journal.snapshot(
        ts_ns=1, positions=[], orders=[], funding_event_ids=[],
        native_account_total="10000", strategy_restartable=True,
    )
    assert journal.recovery_state() == "FLAT_RESTART" and journal.coherent_snapshot()

    class Passive(WaveOverlayStrategy):
        def on_quote_tick(self, tick):
            pass

    def native_cash(strategy):
        account = strategy.cache.account_for_venue(SIM)
        return None if account is None else account.balance_total(BTC_PERP.quote_currency).as_decimal()

    config = msgspec.structs.replace(
        probe_config(), deposit_runtime=journal, deposit_instance_id="first-run",
        deposit_account_id="SIM-001", deposit_equity_reader=native_cash,
        deposit_initialization_allowed=lambda: True,
    )
    strategy = Passive(config)
    engine = native_engine(strategy)
    engine.add_data([
        quote(BTC_PERP.id, "100.0", "100.1", 1),
        quote(BTC_PERP.id, "100.0", "100.1", 2_000_000_000),
    ], sort=False)
    engine.sort_data(); engine.run()
    try:
        assert strategy.deposit_projection()["state"] == "ARMED"
        assert Decimal(strategy.deposit_projection()["high_water_equity"]) == Decimal("10000")
        journal.entry_control_command("pause-new-entries", "initial-pause")
        assert strategy.apply_deposit_control(
            "set-deposit-protection", "initial-p40", drawdown_limit_percent=40,
        )["drawdown_limit_percent"] == 40
        view = strategy.apply_deposit_control(
            "reset-deposit-protection", "initial-reset", confirm=True,
        )
        assert view["state"] == "ARMED" and view["drawdown_limit_percent"] == 40
        assert journal.deposit_audit_action("deposit:control:initial-reset") == "reset-deposit-protection"
    finally:
        engine.dispose()
        journal.close()


def test_fee_floor_v1_native_entry_and_resting_tp_fill() -> None:
    class FeeFloorProbe(WaveOverlayStrategy):
        def __init__(self, config):
            super().__init__(config)
            self.opened = False
            self.rights_before_fill = None

        def on_quote_tick(self, tick):
            if tick.instrument_id != self.config.btc_id:
                return
            if not self.opened:
                self.opened = True
                episode = Episode("fee-floor", 1, 10_000, 1.0, wave_levels=(0, 0.01, 0.03))
                self._domain.episode = episode
                intent = Intent("fee-entry", episode.id, "BTC_ENTRY", None, 1, requested_notional=100)
                episode.pending[intent.id] = intent
                self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), None, 0, ts_now=tick.ts_event)
                return
            if tick.ts_event == 2:
                self.rights_before_fill = set(self._domain.episode.sol_rights)
            super().on_quote_tick(tick)

        def _tier_allows_increase(self, instrument_id, side, quantity, ts_now):
            return True

    strategy = FeeFloorProbe(probe_config().__replace__(tp_fee_floor_v1=True))
    engine = native_engine(strategy)
    engine.add_data([quote(BTC_PERP.id, f"{px:.1f}", f"{px:.1f}", ts)
                     for ts, px in enumerate((100.0, 100.0, 100.3, 100.4), start=1)], sort=False)
    engine.sort_data(); engine.run()
    try:
        episode = strategy._domain.episode
        assert strategy.rights_before_fill == set()
        assert episode is not None
        assert episode.btc_entry_fee_fill_count == episode.btc_entry_fill_count == 1
        assert episode.btc_entry_fees_exact > 0
        tp_fills = [row for row in strategy.fill_audit if row["action"] == "BTC_REDUCE"]
        assert tp_fills
        assert all(Decimal(row["px"]) >= Decimal("100.3") for row in tp_fills)
        assert any(order.has_price and order.price.as_decimal() == Decimal("103.0") for order in engine.cache.orders_open())
        assert 0 in episode.sol_rights
    finally:
        engine.dispose()


def test_fee_floor_v1_native_taker_fallback_waits_for_executable_quote() -> None:
    class FallbackProbe(WaveOverlayStrategy):
        def __init__(self, config):
            super().__init__(config)
            self.phase = 0
            self.rights_after_block = None

        def on_quote_tick(self, tick):
            if tick.instrument_id != self.config.btc_id:
                return
            if self.phase == 0:
                self.phase = 1
                episode = Episode("fallback", 1, 10_000, 1.0, wave_levels=())
                self._domain.episode = episode
                intent = Intent("fallback-entry", episode.id, "BTC_ENTRY", None, 1, requested_notional=100)
                episode.pending[intent.id] = intent
                self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), None, 0, ts_now=tick.ts_event)
            elif self.phase in (1, 2):
                episode = self._domain.episode
                assert episode is not None
                intent = Intent(f"fallback-{self.phase}", episode.id, "BTC_REDUCE", 0, -1, quantity=0.1)
                episode.pending[intent.id] = intent
                self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), None, 0, ts_now=tick.ts_event)
                if self.phase == 1:
                    self.rights_after_block = set(episode.sol_rights)
                self.phase += 1

        def _tier_allows_increase(self, instrument_id, side, quantity, ts_now):
            return True

    strategy = FallbackProbe(probe_config().__replace__(tp_fee_floor_v1=True))
    engine = native_engine(strategy)
    engine.add_data([quote(BTC_PERP.id, f"{px:.1f}", f"{px:.1f}", ts)
                     for ts, px in enumerate((100.0, 100.1, 100.4), start=1)], sort=False)
    engine.sort_data(); engine.run()
    try:
        assert strategy.rights_after_block == set()
        tp_fills = [row for row in strategy.fill_audit if row["action"] == "BTC_REDUCE"]
        assert len(tp_fills) == 1
        assert tp_fills[0]["native_liquidity_side"] == "TAKER"
        assert tp_fills[0]["post_only"] == "false"
        assert Decimal(tp_fills[0]["px"]) >= Decimal("100.3")
        assert 0 in strategy._domain.episode.sol_rights
    finally:
        engine.dispose()


def test_fee_floor_v1_marketable_post_only_does_not_grant_right_or_bypass_fallback() -> None:
    class RejectProbe(WaveOverlayStrategy):
        def __init__(self, config):
            super().__init__(config)
            self.phase = 0
            self.rights_after_reject = None

        def on_quote_tick(self, tick):
            if tick.instrument_id != self.config.btc_id:
                return
            if self.phase == 0:
                self.phase = 1
                episode = Episode("reject", 1, 10_000, 1.0, wave_levels=(0, 0.01, 0.03))
                self._domain.episode = episode
                intent = Intent("reject-entry", episode.id, "BTC_ENTRY", None, 1, requested_notional=100)
                episode.pending[intent.id] = intent
                self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), None, 0, ts_now=tick.ts_event)
                return
            if self.phase == 1:
                self.phase = 2
                super().on_quote_tick(tick)
                self.rights_after_reject = set(self._domain.episode.sol_rights)
                return
            if self.phase == 2:
                self.phase = 3
                episode = self._domain.episode
                intent = Intent("reject-fallback", episode.id, "BTC_REDUCE", 0, -1, quantity=0.1)
                episode.pending[intent.id] = intent
                self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), None, 0, ts_now=tick.ts_event)

        def _tier_allows_increase(self, instrument_id, side, quantity, ts_now):
            return True

    strategy = RejectProbe(probe_config().__replace__(tp_fee_floor_v1=True))
    engine = native_engine(strategy)
    engine.add_data([quote(BTC_PERP.id, f"{px:.1f}", f"{px:.1f}", ts)
                     for ts, px in enumerate((100.0, 100.5, 100.5), start=1)], sort=False)
    engine.sort_data(); engine.run()
    try:
        assert strategy.rights_after_reject == set()
        tp_fills = [row for row in strategy.fill_audit if row["action"] == "BTC_REDUCE"]
        assert len(tp_fills) == 1
        assert tp_fills[0]["native_liquidity_side"] == "TAKER"
        assert Decimal(tp_fills[0]["px"]) >= Decimal("100.3")
    finally:
        engine.dispose()


def test_fee_floor_v1_does_not_delay_native_emergency_close_below_break_even() -> None:
    class EmergencyProbe(WaveOverlayStrategy):
        def __init__(self, config):
            super().__init__(config)
            self.phase = 0

        def on_quote_tick(self, tick):
            if tick.instrument_id != self.config.btc_id:
                return
            if self.phase == 0:
                self.phase = 1
                episode = Episode("emergency", 1, 10_000, 1.0, wave_levels=())
                self._domain.episode = episode
                intent = Intent("emergency-entry", episode.id, "BTC_ENTRY", None, 1, requested_notional=100)
                episode.pending[intent.id] = intent
                self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), None, 0, ts_now=tick.ts_event)
            elif self.phase == 1:
                self.phase = 2
                episode = self._domain.episode
                intent = Intent("emergency-close", episode.id, "CLOSE_ALL", None, -1, reason="REGIME")
                episode.pending[intent.id] = intent
                self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), None, 0, ts_now=tick.ts_event)

        def _tier_allows_increase(self, instrument_id, side, quantity, ts_now):
            return True

    strategy = EmergencyProbe(probe_config().__replace__(tp_fee_floor_v1=True))
    engine = native_engine(strategy)
    engine.add_data([quote(BTC_PERP.id, f"{px:.1f}", f"{px:.1f}", ts)
                     for ts, px in enumerate((100.0, 99.0), start=1)], sort=False)
    engine.sort_data(); engine.run()
    try:
        close = [row for row in strategy.fill_audit if row["action"] == "CLOSE_ALL"]
        assert len(close) == 1
        assert Decimal(close[0]["px"]) == Decimal("99.0")
        assert close[0]["native_liquidity_side"] == "TAKER"
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("levels", "expected_net", "zero_tp_netting"),
    [
        ((0.0, 0.0, 0.03), Decimal("0.576"), True),
        ((0.0, 0.02, 0.03), Decimal("0.788"), True),
        ((0.0, 0.0, 0.0), Decimal("0"), True),
        ((0.0, 0.0, 0.03), Decimal("1"), False),
        ((0.0, 0.0, 0.0), Decimal("1"), False),
    ],
)
def test_zero_wave_research_variant_native_entry_size_and_no_synthetic_tp(levels, expected_net, zero_tp_netting) -> None:
    class ZeroWaveProbe(WaveOverlayStrategy):
        def __init__(self, config):
            super().__init__(config)
            self.opened = False
            self.same_day_rights = []

        def _advance_current_day(self):
            self.same_day_rights.append(set(self._domain.episode.sol_rights) if self._domain.episode else set())

        def on_quote_tick(self, tick):
            if tick.instrument_id != self.config.btc_id:
                return
            if not self.opened:
                self.opened = True
                episode = Episode("zero-wave", 1, 10_000, 1.0, wave_levels=levels)
                self._domain.episode = episode
                intent = Intent("entry", episode.id, "BTC_ENTRY", None, 1, requested_notional=100)
                episode.pending[intent.id] = intent
                self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), None, 0, ts_now=tick.ts_event)
                return
            super().on_quote_tick(tick)

        def _tier_allows_increase(self, instrument_id, side, quantity, ts_now):
            return True

    candidate = Candidate(btc_tp_fractions_initial_qty=(0.2125, 0.2125, 0.575))
    strategy = ZeroWaveProbe(probe_config().__replace__(
        candidate=candidate, research_v0_execution_repairs=True, research_v0_zero_tp_netting=zero_tp_netting,
    ))
    engine = native_engine(strategy)
    ticks = (1, 2, 3) if zero_tp_netting else (1, 2)
    engine.add_data([quote(BTC_PERP.id, "100.0", "100.0", ts) for ts in ticks], sort=False)
    engine.sort_data(); engine.run()
    try:
        fills = [row for row in strategy.fill_audit if row["action"] == "BTC_ENTRY"]
        if expected_net == 0:
            assert not fills
            assert strategy._domain.episode is None
            assert strategy.pre_submit_gate_blocks[-1]["reason"] == "ZERO_TP_NO_NET_ENTRY"
            return
        assert len(fills) == 1
        assert Decimal(fills[0]["qty"]) == expected_net
        episode = strategy._domain.episode
        assert episode is not None
        if not zero_tp_netting:
            assert strategy.entry_sizing_audit == []
            assert episode.btc_omitted_zero_levels == set()
            assert episode.btc_net_planned_qty == 0
            assert episode.btc_initial_qty == pytest.approx(1.0)
            assert episode.btc_tp_target_lots == {0: 212, 1: 212, 2: 576}
            assert episode.sol_rights == set()
            assert strategy.same_day_rights == []
            assert episode.btc_tp_filled_qty == {}
            return
        audit = strategy.entry_sizing_audit[0]
        assert Decimal(audit["reference_btc_qty"]) == Decimal("1")
        assert Decimal(audit["net_submitted_btc_qty"]) == expected_net
        assert Decimal(audit["confirmed_native_entry_qty"]) == expected_net
        episode = strategy._domain.episode
        assert episode is not None
        assert episode.h == pytest.approx(100.0)
        assert episode.sol_rights == {i for i, level in enumerate(levels) if level == 0}
        assert strategy.same_day_rights == [episode.sol_rights]
        assert episode.btc_tp_filled_qty == {}
        assert all(int(order.quantity.as_decimal() / BTC_PERP.size_increment.as_decimal()) > 0 for order in engine.cache.orders_open())
        assert {int(row["level"]) for row in strategy._order_audit.values() if row["action"] == "BTC_REDUCE"} == {i for i, level in enumerate(levels) if level > 0}
    finally:
        engine.dispose()


def test_research_timeout_cancel_rearms_native_sol_residual_with_cadence() -> None:
    class CacheProbe(WaveOverlayStrategy):
        @property
        def cache(self):
            return self.fake_cache

    position = SimpleNamespace(instrument_id=SOL_PERP.id, quantity=Quantity.from_str("1.00"))
    strategy = CacheProbe(probe_config().__replace__(research_v0_execution_repairs=True))
    strategy.fake_cache = SimpleNamespace(
        positions_open=lambda: [position], orders_open=lambda: [],
    )
    episode = Episode("timeout", 1, 100, 1.0, sol_qty=1.0)
    strategy._domain.episode = episode
    first = Intent("first", episode.id, "SOL_EXIT", None, 1, quantity=2.0, reason="SOL_HARD_TIMEOUT")
    episode.pending[first.id] = first
    strategy._pending_by_order["first-order"] = first
    strategy.on_order_canceled(SimpleNamespace(client_order_id="first-order", ts_event=1_000_000_000))
    retry = strategy._mandatory_sol_exit
    assert retry is not None and retry[0].id != first.id
    assert retry[0].quantity == 1.0
    assert first.id not in episode.pending
    submitted = []
    strategy._submit_intent = lambda *args, **kwargs: submitted.append(args[0].id)
    strategy.on_quote_tick(quote(SOL_PERP.id, "100.0", "100.0", 2_000_000_000))
    assert not submitted and strategy._mandatory_sol_exit == retry
    strategy.on_quote_tick(quote(SOL_PERP.id, "100.0", "100.0", 62_000_000_000))
    assert submitted == [retry[0].id]
    assert strategy._mandatory_sol_exit is None


def test_research_stale_queued_sol_add_is_terminal_before_submit() -> None:
    class CacheProbe(WaveOverlayStrategy):
        @property
        def cache(self):
            return self.fake_cache

        def _active_marked(self, _btc_mark, _sol_mark):
            return 100.0

    strategy = CacheProbe(probe_config().__replace__(research_v0_execution_repairs=True))
    strategy.fake_cache = SimpleNamespace(positions_open=lambda: [], orders_open=lambda: [], instrument=lambda item: {BTC_PERP.id: BTC_PERP, SOL_PERP.id: SOL_PERP}.get(item))
    start = datetime(2024, 1, 1, tzinfo=UTC)
    old = DailyBar(start, start + timedelta(days=1), start + timedelta(days=1), 100, 100, 100)
    new = DailyBar(start + timedelta(days=1), start + timedelta(days=2), start + timedelta(days=2), 100, 100, 100)
    from coinmaster.domain.wave_overlay import Features
    old_feature = Features(0, 1, 1.0, 0.0, 0.0, 1.0, 2.0)
    new_feature = Features(1, 1, 1.0, 0.0, 0.0, 1.0, 0.1)
    strategy._bars = [old]
    strategy._current_signals = [old_feature]
    old_session = int(old.close_time.timestamp() * 1_000_000_000)
    new_session = int(new.close_time.timestamp() * 1_000_000_000)
    strategy._current_btc = make_bar(strategy.config.btc_bar_type, 100, 100, old_session)
    strategy._current_sol = make_bar(strategy.config.sol_bar_type, 100, 100, old_session)
    strategy._last_accepted_session = old_session
    strategy._latest_seen_session = new_session
    episode = Episode("stale", 1, 100, 1.0, btc_initial_qty=1.0, btc_open_qty=1.0, btc_entry_vwap=100.0, h=100.0, wave_levels=(0.01, 0.02, 0.03), sol_qty=1.0, sol_first_fill_at=start)
    strategy._domain.episode = episode
    add = Intent("stale-add", episode.id, "SOL_ADD", 1, -1, requested_notional=100, decision_index=0)
    episode.pending[add.id] = add
    strategy._queued_intents = [(add, None, 0)]
    strategy._current_btc_mark = SimpleNamespace(price=Decimal("100"))
    strategy._current_sol_mark = SimpleNamespace(price=Decimal("100"))
    submitted = []
    strategy._submit_intent = lambda *args, **kwargs: submitted.append(True)
    strategy.on_quote_tick(quote(SOL_PERP.id, "100.0", "100.0", 3_000_000_000))
    assert not submitted and add.id in episode.pending
    assert strategy._queued_intents == [(add, None, 0)]
    assert not any(item[0].action == "SOL_HALF_EXIT" for item in strategy._queued_intents)
    # An older paired row is still historical when a newer signal is seen.
    strategy._bars = [old, new]
    strategy._current_signals = [old_feature, new_feature]
    strategy.on_quote_tick(quote(SOL_PERP.id, "100.0", "100.0", 3_500_000_000))
    assert not submitted and add.id in episode.pending
    assert strategy._queued_intents == [(add, None, 0)]
    strategy._current_btc = make_bar(strategy.config.btc_bar_type, 100, 100, new_session)
    strategy._current_sol = make_bar(strategy.config.sol_bar_type, 100, 100, new_session)
    strategy._last_accepted_session = new_session
    strategy.on_quote_tick(quote(SOL_PERP.id, "100.0", "100.0", 4_000_000_000))
    assert not submitted
    assert add.id not in episode.pending
    assert len(strategy._queued_intents) == 1
    assert strategy._queued_intents[0][0].action == "SOL_HALF_EXIT"
    assert strategy._queued_intents[0][0].quantity == 0.5


def test_research_mm_guard_accepts_fresh_async_exposure_marks_and_rejects_stale_future() -> None:
    from coinmaster.venues.marks import VenueMark

    class CacheProbe(WaveOverlayStrategy):
        @property
        def cache(self):
            return self.fake_cache

    class FakeCache:
        def __init__(self):
            self.positions = []
            self.account = SimpleNamespace(
                base_currency=BTC_PERP.quote_currency,
                balance_total=lambda _currency: SimpleNamespace(as_decimal=lambda: Decimal("-100")),
            )

        def positions_open(self):
            return self.positions

        def orders_open(self):
            return []

        def account_for_venue(self, _venue):
            return self.account

        def instrument(self, instrument_id):
            return {BTC_PERP.id: BTC_PERP, SOL_PERP.id: SOL_PERP}.get(instrument_id)

    policy = TierMarginPolicy((), {BTC_PERP.id: Decimal("40"), SOL_PERP.id: Decimal("20")}, 30)
    strategy = CacheProbe(probe_config().__replace__(
        research_v0_execution_repairs=True, max_mark_age_ns=30, margin_policy=policy,
    ))
    strategy.fake_cache = FakeCache()
    btc = SimpleNamespace(
        instrument_id=BTC_PERP.id, quantity=Quantity.from_str("1.000"), is_long=True,
        unrealized_pnl=lambda _price: SimpleNamespace(as_decimal=lambda: Decimal("0")),
    )
    sol = SimpleNamespace(
        instrument_id=SOL_PERP.id, quantity=Quantity.from_str("1.0"), is_long=False,
        unrealized_pnl=lambda _price: SimpleNamespace(as_decimal=lambda: Decimal("0")),
    )
    strategy._latest_marks = {
        BTC_PERP.id: VenueMark(BTC_PERP.id, Decimal("100"), 100, 100),
        SOL_PERP.id: VenueMark(SOL_PERP.id, Decimal("100"), 1, 1),
    }
    policy.update_mark(SimpleNamespace(instrument_id=BTC_PERP.id, price=Decimal("100"), ts_event=100))
    policy.update_mark(SimpleNamespace(instrument_id=SOL_PERP.id, price=Decimal("100"), ts_event=1))
    strategy.fake_cache.positions = [btc]
    strategy._check_mark_first_liquidation(110)
    assert strategy._liquidating  # BTC-only exposure; SOL's old mark is irrelevant.
    strategy._liquidating = False
    strategy._forced_close_reason = None
    strategy.fake_cache.positions = [btc, sol]
    strategy._check_mark_first_liquidation(110)
    assert not strategy._liquidating  # Exposed SOL is stale for the venue policy.
    strategy._latest_marks[SOL_PERP.id] = VenueMark(SOL_PERP.id, Decimal("100"), 105, 105)
    policy.update_mark(SimpleNamespace(instrument_id=SOL_PERP.id, price=Decimal("100"), ts_event=105))
    strategy._check_mark_first_liquidation(110)
    assert strategy._liquidating and strategy.liquidation_audit[-1]["marked_equity"] == "-100"
    strategy._liquidating = False
    strategy._forced_close_reason = None
    strategy._latest_marks[SOL_PERP.id] = VenueMark(SOL_PERP.id, Decimal("100"), 200, 200)
    strategy._check_mark_first_liquidation(110)
    assert not strategy._liquidating  # Future mark is not causal.

@pytest.mark.parametrize(
    ("q1", "tail", "expected_branch", "expected_qty", "activated"),
    [
        ("99.0", ("99.0",), "PASSIVE_NET_ZERO_LEVELS", Decimal("0.576"), False),
        ("99.0", ("99.0", "100.0"), "PASSIVE_NET_ZERO_LEVELS", Decimal("0.576"), False),
        ("101.0", ("101.0",), "MARKETABLE_FULL_ENTRY_FALLBACK", Decimal("1"), False),
    ],
)
def test_deferred_selective_zero_tp_uses_only_q0_q1_and_real_entry_rights(
    q1, tail, expected_branch, expected_qty, activated,
) -> None:
    class DeferredProbe(WaveOverlayStrategy):
        def _tier_allows_increase(self, instrument_id, side, quantity, ts_now):
            return True

    candidate = Candidate(btc_tp_fractions_initial_qty=(0.2125, 0.2125, 0.575))
    strategy = DeferredProbe(probe_config().__replace__(
        candidate=candidate, research_v0_execution_repairs=True,
        research_v0_zero_tp_netting=False, research_v0_deferred_selective_zero_tp=True,
        max_mark_age_ns=30,
    ))
    episode = Episode("deferred", 1, 10_000, 1.0, wave_levels=(0.0, 0.0, 0.03))
    strategy._domain.episode = episode
    intent = Intent("deferred-entry", episode.id, "BTC_ENTRY", None, 1, requested_notional=100)
    episode.pending[intent.id] = intent
    strategy._queued_intents.append((intent, None, 0))
    strategy._queued_intent_ready_ns[intent.id] = 0
    engine = native_engine(strategy)
    prices = ("100.0", q1, *tail)
    engine.add_data([quote(BTC_PERP.id, price, price, ts) for ts, price in enumerate(prices, start=1)], sort=False)
    engine.sort_data(); engine.run()
    try:
        fills = [row for row in strategy.fill_audit if row["action"] == "BTC_ENTRY"]
        assert len(fills) == 1, (strategy.pre_submit_gate_blocks, strategy._daily_decision_reason, strategy._deferred_selective_entries, strategy._queued_intents, episode.pending)
        assert Decimal(fills[0]["qty"]) == expected_qty
        audit = strategy.entry_sizing_audit[0]
        assert audit["q0_ns"] == "1" and audit["q1_ns"] == "2"
        assert audit["branch"] == expected_branch
        assert Decimal(audit["reference_btc_qty"]) == Decimal("1")
        assert Decimal(audit["confirmed_native_entry_qty"]) == expected_qty
        assert episode.h == pytest.approx(float(expected_qty * Decimal(q1)) if expected_branch == "MARKETABLE_FULL_ENTRY_FALLBACK" else float(Decimal(q1)))
        assert not episode.btc_tp_filled_qty
        if expected_branch == "PASSIVE_NET_ZERO_LEVELS":
            assert episode.btc_omitted_zero_levels == {0, 1}
            assert episode.sol_right_fraction == {0: 1.0, 1: 1.0}
            assert episode.sol_rights == ({0, 1} if activated else set())
            assert len(audit["sol_right_activations"]) == (1 if activated else 0)
            assert episode.btc_tp_target_lots == {0: 0, 1: 0, 2: 576}
        else:
            assert episode.btc_omitted_zero_levels == set()
            assert episode.btc_zero_resting_suppressed == {0, 1}
            assert episode.sol_rights == set()
            assert episode.btc_tp_target_lots == {0: 212, 1: 212, 2: 576}
            assert {int(row["level"]) for row in strategy._order_audit.values() if row["action"] == "BTC_REDUCE"} == {2}
    finally:
        engine.dispose()


def test_deferred_selective_entry_expires_without_fresh_q1() -> None:
    class DeferredProbe(WaveOverlayStrategy):
        def _tier_allows_increase(self, instrument_id, side, quantity, ts_now):
            return True

    strategy = DeferredProbe(probe_config().__replace__(
        research_v0_execution_repairs=True, research_v0_zero_tp_netting=False,
        research_v0_deferred_selective_zero_tp=True, max_mark_age_ns=30,
    ))
    episode = Episode("stale", 1, 10_000, 1.0, wave_levels=(0.0, 0.0, 0.03))
    strategy._domain.episode = episode
    intent = Intent("stale-entry", episode.id, "BTC_ENTRY", None, 1, requested_notional=100)
    episode.pending[intent.id] = intent
    strategy._queued_intents.append((intent, None, 0))
    strategy._queued_intent_ready_ns[intent.id] = 0
    engine = native_engine(strategy)
    engine.add_data([quote(BTC_PERP.id, "100.0", "100.0", 1), quote(BTC_PERP.id, "99.0", "99.0", 40)], sort=False)
    engine.sort_data(); engine.run()
    try:
        assert not [row for row in strategy.fill_audit if row["action"] == "BTC_ENTRY"]
        assert strategy._domain.episode is None
        assert strategy._deferred_selective_entries == {}
        assert strategy._queued_intents == []
    finally:
        engine.dispose()


def test_deferred_touch_waits_for_current_paired_executable_session() -> None:
    strategy = WaveOverlayStrategy(probe_config().__replace__(
        research_v0_execution_repairs=True, research_v0_zero_tp_netting=False,
        research_v0_deferred_selective_zero_tp=True,
    ))
    new_close = datetime(2024, 9, 2, tzinfo=UTC)
    current = DailyBar(new_close - timedelta(days=1), new_close, new_close, 100, 100, 100)
    session = int(new_close.timestamp() * 1_000_000_000)
    strategy._bars = [current]
    strategy._domain.episode = Episode(
        "earned", 1, 100, 1.0, btc_initial_qty=0.288, btc_open_qty=0.288,
        btc_net_planned_qty=0.576, btc_omitted_zero_levels={0},
        btc_deferred_right_reference_price=Decimal("100"),
        sol_right_fraction={0: 0.5},
    )
    strategy.entry_sizing_audit.append({"sol_right_activations": []})
    calls = []
    strategy._advance_current_day = lambda: calls.append("advance")
    strategy._current_btc = SimpleNamespace(ts_event=session - 86_400_000_000_000)
    strategy._current_sol = SimpleNamespace(ts_event=session - 86_400_000_000_000)
    strategy._last_accepted_session = session - 86_400_000_000_000
    strategy._latest_seen_session = session
    strategy._activate_selective_sol_rights(quote(BTC_PERP.id, "100.0", "100.0", 10))
    episode = strategy._domain.episode
    assert episode.btc_deferred_right_touched
    assert episode.sol_rights == set()
    assert calls == []
    strategy._current_btc = SimpleNamespace(ts_event=session)
    strategy._current_sol = SimpleNamespace(ts_event=session)
    strategy._last_accepted_session = session
    strategy._activate_selective_sol_rights(quote(BTC_PERP.id, "99.0", "99.0", 11))
    assert episode.sol_rights == {0}
    assert episode.sol_right_fraction[0] == 0.5
    assert episode.sol_right_decision_index[0] == 0
    assert calls == ["advance"]
    assert strategy.entry_sizing_audit[-1]["sol_right_activations"][0]["timestamp_ns"] == "11"


def lifecycle_config(**kwargs):
    return probe_config().__replace__(
        research_v0_execution_repairs=True, research_v0_zero_tp_netting=False,
        research_v0_deferred_selective_zero_tp=True,
        research_v0_selective_lifecycle_repairs=True, **kwargs,
    )


@pytest.mark.parametrize("action,target", [("SOL_HALF_EXIT", 1000), ("SOL_EXIT", 2000)])
def test_lifecycle_native_sol_ioc_target_survives_partial_cancel_two_episodes(action, target):
    from nautilus_trader.model.data import QuoteTick

    class Probe(WaveOverlayStrategy):
        def __init__(self, config):
            super().__init__(config)
            self.stage = 0
            self.episode_count = 0
            self.snapshots = []

        def on_quote_tick(self, tick):
            if tick.instrument_id != self.config.sol_id:
                return
            if tick.ts_event % 300_000_000_000 == 1:
                self.stage = 0
            if self.stage == 4:
                return
            if self.stage in (0, 1):
                if self.stage == 0:
                    self.episode_count += 1
                    self._domain.episode = Episode(f"sol-{self.episode_count}", 1, 10000, 1.0)
                intent = self._domain._intent(self._domain.episode, "SOL_ADD", 1, 0, quantity=1000)
                self.stage += 1
                self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), None, 0, ts_now=tick.ts_event)
            elif self.stage == 2:
                episode = self._domain.episode
                episode.sol_half_target_lots = target * 10
                intent = self._domain._intent(episode, action, -1, None, quantity=target, reason="SOL_Z_HALF_EXIT" if action == "SOL_HALF_EXIT" else "SOL_Z_FULL_EXIT")
                self.stage = 3
                self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), None, 0, ts_now=tick.ts_event)
            else:
                super().on_quote_tick(tick)
                self.snapshots.append((tick.ts_event, self._domain.episode.sol_qty))
                if not self._accepted_reductions and not self._queued_intents and not self._pending_by_order:
                    expected = 2000 - target
                    assert self._domain.episode.sol_qty == expected
                    if action == "SOL_HALF_EXIT":
                        assert self._domain.episode.sol_half_done
                        # Close remaining native half to make the next episode clean.
                        self._begin_forced_close("TEST_GROUP")
                        self._submit_forced_close_on_quote(tick)
                    self.stage = 4

        def _tier_allows_increase(self, *args):
            return True

    strategy = Probe(lifecycle_config())
    engine = native_engine(strategy)
    ticks = []
    for episode in range(2):
        offset = episode * 300_000_000_000
        for ts, size in [(1, 1000), (2, 1000), (3, 250), (30_000_000_003, 1000), (61_000_000_003, 1000), (122_000_000_003, 1000), (183_000_000_003, 1000)]:
            ticks.append(QuoteTick(SOL_PERP.id, Price.from_str("1.00"), Price.from_str("1.00"), Quantity.from_str(f"{size}.0"), Quantity.from_str(f"{size}.0"), offset + ts, offset + ts))
    engine.add_data(ticks, sort=False)
    engine.sort_data(); engine.run()
    try:
        assert strategy.episode_count == 2
        assert not strategy._accepted_reductions
        assert not strategy._pending_by_order
        assert not engine.cache.positions_open()
        fills = [row for row in strategy.fill_audit if row["action"] == action]
        assert len(fills) >= 4
        assert sum(Decimal(row["qty"]) for row in fills) == target * 2
    finally:
        engine.dispose()


def test_lifecycle_native_zero_fallback_retries_profitable_leaves_not_adverse_quotes():
    from nautilus_trader.model.data import QuoteTick

    class Probe(WaveOverlayStrategy):
        def __init__(self, config):
            super().__init__(config)
            self.stage = 0
            self.rights_at_adverse = None

        def on_quote_tick(self, tick):
            if tick.instrument_id != self.config.btc_id:
                return
            if self.stage == 0:
                self._domain.episode = Episode("btc-fallback", 1, 10000, 1.0, wave_levels=(0.0, 0.01, 0.02), btc_zero_resting_suppressed={0})
                self.stage = 1
                intent = self._domain._intent(self._domain.episode, "BTC_ENTRY", 1, None, quantity=1)
                self._submit_intent(intent, 100, 100, None, 0, ts_now=tick.ts_event)
            elif self.stage == 1:
                self._discard_queued_intents(lambda queued: queued.action == "BTC_REDUCE")
                episode = self._domain.episode
                intent = self._domain._intent(episode, "BTC_REDUCE", -1, 0, quantity=self._domain._btc_target_leaves(episode, 0))
                self.stage = 2
                self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), None, 0, ts_now=tick.ts_event)
            else:
                super().on_quote_tick(tick)
                if tick.bid_price.as_decimal() < Decimal("100"):
                    self.rights_at_adverse = self._domain.episode.sol_right_fraction[0]

        def _tier_allows_increase(self, *args):
            return True

    strategy = Probe(lifecycle_config())
    engine = native_engine(strategy)
    ticks = []
    for ts, price, size in [(1, "100.0", "1000.000"), (2, "101.0", "0.100"), (61_000_000_002, "99.0", "1000.000"), (62_000_000_002, "102.0", "1000.000")]:
        ticks.append(QuoteTick(BTC_PERP.id, Price.from_str(price), Price.from_str(price), Quantity.from_str(size), Quantity.from_str(size), ts, ts))
    engine.add_data(ticks, sort=False); engine.sort_data(); engine.run()
    try:
        fills = [row for row in strategy.fill_audit if row["action"] == "BTC_REDUCE" and row["level"] == "0"]
        assert len(fills) == 2
        assert all(Decimal(row["px"]) > 100 for row in fills)
        assert 0 < strategy.rights_at_adverse < 1
        assert strategy._domain.episode.sol_right_fraction[0] == 1
        assert 0 in strategy._domain.episode.btc_filled_tps
        assert not strategy._accepted_reductions
    finally:
        engine.dispose()


def test_lifecycle_earned_fill_must_precede_touch_and_terminal_unknown_ack():
    class Probe(WaveOverlayStrategy):
        @property
        def cache(self):
            return self.fake_cache
    strategy = Probe(lifecycle_config())
    strategy.fake_cache = SimpleNamespace(positions_open=lambda: [], orders_open=lambda: [])
    episode = Episode("causal", 1, 100, 1.0, btc_net_planned_qty=1, btc_omitted_zero_levels={0}, btc_deferred_right_reference_price=Decimal("100"))
    strategy._domain.episode = episode
    strategy._activate_selective_sol_rights(quote(BTC_PERP.id, "101.0", "101.0", 1))
    assert not episode.btc_deferred_right_touched
    entry = strategy._domain._intent(episode, "BTC_ENTRY", 1, None, quantity=1)
    strategy._domain.on_fill(entry.id, 0.5, 100, datetime(2024, 1, 1, tzinfo=UTC))
    strategy._activate_selective_sol_rights(quote(BTC_PERP.id, "99.0", "99.0", 3))
    assert not episode.btc_deferred_right_touched
    assert episode.sol_right_fraction == {0: 0.5}
    strategy._activate_selective_sol_rights(quote(BTC_PERP.id, "100.0", "100.0", 4))
    assert episode.btc_deferred_right_touched
    # Queued q0 is locally terminal; submitted unknown ACK is still owned.
    strategy._queued_intents = [(entry, None, 0)]
    strategy._deferred_selective_entries[entry.id] = {"q0_ns": 1}
    strategy._submit_terminal_closes()
    assert strategy.terminal_lifecycle["status"] == "FLAT"
    assert not strategy._queued_intents and not strategy._deferred_selective_entries
    assert not episode.pending
    strategy._domain.episode = Episode("unknown", 1, 100, 1.0)
    unknown = strategy._domain._intent(strategy._domain.episode, "BTC_ENTRY", 1, None, quantity=1)
    strategy._pending_by_order["unknown-native"] = unknown
    strategy._submit_terminal_closes()
    assert strategy.terminal_lifecycle["status"] == "AWAITING_NATIVE_TERMINAL"
    assert unknown.id in strategy._domain.episode.pending
    assert not strategy._entries_enabled()
    strategy._reconcile_terminal_flat()
    assert strategy.terminal_lifecycle["status"] != "FLAT"
    strategy.on_order_canceled(SimpleNamespace(client_order_id="unknown-native", ts_event=10))
    assert strategy.terminal_lifecycle["status"] == "FLAT"


def test_lifecycle_native_locked_margin_increment_and_same_fresh_equity_marks():
    class Probe(WaveOverlayStrategy):
        def __init__(self, config):
            super().__init__(config)
            self.submitted = False
        def on_quote_tick(self, tick):
            if not self.submitted:
                self.submitted = True
                self.submit_order(self.order_factory.market(instrument_id=BTC_PERP.id, order_side=OrderSide.BUY, quantity=BTC_PERP.make_qty(Decimal("60")), time_in_force=TimeInForce.IOC))
    policy = TierMarginPolicy((), {BTC_PERP.id: Decimal("1"), SOL_PERP.id: Decimal("1")}, 30)
    strategy = Probe(lifecycle_config(margin_policy=policy, max_gross_to_active=Decimal("0.73")))
    engine = native_engine(strategy)
    engine.add_data([quote(BTC_PERP.id, "100.0", "100.0", 1)])
    engine.run()
    try:
        account = strategy.cache.account_for_venue(SIM)
        # Set known locks on the actual pinned native MarginAccount, whose
        # free recalculation deducts both IM and MM (including reservations).
        account.update_margin_init(BTC_PERP.id, Money(6000, BTC_PERP.quote_currency))
        account.update_margin_maint(BTC_PERP.id, Money(500, BTC_PERP.quote_currency))
        total = account.balance_total(BTC_PERP.quote_currency).as_decimal()
        free = account.balance_free(BTC_PERP.quote_currency).as_decimal()
        assert total > free and free < 4000
        policy.update_mark(SimpleNamespace(instrument_id=BTC_PERP.id, price=Decimal("110"), ts_event=100))
        policy.update_mark(SimpleNamespace(instrument_id=SOL_PERP.id, price=Decimal("100"), ts_event=100))
        # Stale daily 100 marks would lose the native 600 unrealized profit.
        strategy._current_btc_mark = SimpleNamespace(price=Decimal("100"))
        strategy._current_sol_mark = SimpleNamespace(price=Decimal("100"))
        assert strategy._tier_allows_increase(SOL_PERP.id, OrderSide.BUY, Decimal("10"), 110)
        assert not strategy._tier_allows_increase(SOL_PERP.id, OrderSide.BUY, Decimal("50"), 110)
        assert not strategy._tier_allows_increase(SOL_PERP.id, OrderSide.BUY, Decimal("10"), 131)
        assert not strategy._tier_allows_increase(SOL_PERP.id, OrderSide.BUY, Decimal("10"), 99)
    finally:
        engine.dispose()



@pytest.mark.parametrize("side", [1, -1])
def test_lifecycle_native_q1_cap30m_clamps_normalized_lots_preserving_reference(side):
    class Probe(WaveOverlayStrategy):
        def _tier_allows_increase(self, *args):
            return True
    candidate = Candidate(max_parent_notional=30_000_000.0, btc_tp_fractions_initial_qty=(0.2125, 0.2125, 0.575))
    strategy = Probe(lifecycle_config(candidate=candidate, max_mark_age_ns=30))
    episode = Episode("cap30m", side, 100_000_000, 1.0, wave_levels=(0.01, 0.02, 0.03))
    strategy._domain.episode = episode
    intent = strategy._domain._intent(episode, "BTC_ENTRY", side, None, requested_notional=30_000_000)
    strategy._queued_intents = [(intent, None, 0)]
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(100_000_000, BTC_PERP.quote_currency)], base_currency=BTC_PERP.quote_currency, default_leverage=Decimal("1"))
    engine.add_instrument(BTC_PERP); engine.add_instrument(SOL_PERP)
    engine.add_strategy(strategy)
    engine.add_data([quote(BTC_PERP.id, "30000.0", "30000.0", 1), quote(BTC_PERP.id, "30030.0", "30030.0", 2)], sort=False)
    engine.sort_data(); engine.run()
    try:
        fills = [row for row in strategy.fill_audit if row["action"] == "BTC_ENTRY"]
        assert len(fills) == 1
        qty = Decimal(fills[0]["qty"])
        assert qty == Decimal("999.000")
        assert qty * Decimal(fills[0]["px"]) <= Decimal("30000000")
        assert (qty + BTC_PERP.size_increment.as_decimal()) * Decimal("30030") > Decimal("30000000")
        assert episode.btc_reference_qty == 1000
        assert episode.btc_net_planned_qty == float(qty)
        assert episode.h == 1000 * 30030
        assert sum(episode.btc_tp_target_lots.values()) == 999000
        assert not strategy.pre_submit_gate_blocks
    finally:
        engine.dispose()


def test_lifecycle_rejected_owned_child_keeps_target_unknown_ack_blocks_duplicate():
    class Probe(WaveOverlayStrategy):
        @property
        def clock(self):
            return SimpleNamespace(timestamp_ns=lambda: 1)
        @property
        def cache(self):
            return self.fake_cache
    strategy = Probe(lifecycle_config())
    position = SimpleNamespace(instrument_id=SOL_PERP.id, quantity=Quantity.from_str("1000.0"))
    strategy.fake_cache = SimpleNamespace(positions_open=lambda: [position], orders_open=lambda: [])
    episode = Episode("denied-exit", 1, 10000, 1.0, sol_qty=1000)
    strategy._domain.episode = episode
    intent = strategy._domain._intent(episode, "SOL_EXIT", -1, None, quantity=1000, reason="SOL_Z_FULL_EXIT")
    strategy._own_accepted_reduction(intent, Decimal("1000"))
    strategy._pending_by_order["unknown"] = intent
    strategy._requeue_accepted_reduction(intent, None, 0, 1)
    assert not strategy._queued_intents
    strategy.on_order_denied(SimpleNamespace(client_order_id="unknown"))
    assert len(strategy._queued_intents) == 1
    child = strategy._queued_intents[0][0]
    assert child.quantity == 1000 and intent.id not in episode.pending
    strategy._begin_forced_close("REGIME")
    assert not strategy._accepted_reductions and not strategy._queued_intents
    assert child.id not in episode.pending



def test_lifecycle_native_immediate_q1_fill_then_reference_touch_earns_once():
    class Probe(WaveOverlayStrategy):
        def _tier_allows_increase(self, *args):
            return True
        def _advance_current_day(self):
            pass
    strategy = Probe(lifecycle_config(max_mark_age_ns=30))
    close = datetime(2024, 9, 2, tzinfo=UTC)
    session = int(close.timestamp() * 1_000_000_000)
    strategy._bars = [DailyBar(close - timedelta(days=1), close, close, 100, 100, 100)]
    strategy._current_btc = SimpleNamespace(ts_event=session)
    strategy._current_sol = SimpleNamespace(ts_event=session)
    strategy._last_accepted_session = session
    strategy._latest_seen_session = session
    episode = Episode("causal-native", 1, 10000, 1.0, wave_levels=(0.0, 0.0, 0.03))
    strategy._domain.episode = episode
    intent = strategy._domain._intent(episode, "BTC_ENTRY", 1, None, requested_notional=100)
    strategy._queued_intents = [(intent, None, 0)]
    engine = native_engine(strategy)
    engine.add_data([quote(BTC_PERP.id, price, price, session + delta) for delta, price in [(1, "100.0"), (2, "99.0"), (3, "100.0"), (4, "100.0")]], sort=False)
    engine.sort_data(); engine.run()
    try:
        assert episode.btc_initial_qty > 0
        assert episode.sol_rights == {0, 1}
        activation = strategy.entry_sizing_audit[0]["sol_right_activations"]
        assert len(activation) == 1 and activation[0]["timestamp_ns"] == str(session + 3)
        assert activation[0]["confirmed_native_entry_qty"] == str(episode.btc_initial_qty)
    finally:
        engine.dispose()



def test_lifecycle_canonical_customdata_native_empty_module_marks_admission_basis():
    from nautilus_trader.model.identifiers import ClientId
    from coinmaster.research.native_fixture import BybitTierMarginModule
    leverage = ((BTC_PERP.id, Decimal("1")), (SOL_PERP.id, Decimal("1")))
    module = BybitTierMarginModule((), leverage, 30)
    policy = TierMarginPolicy((), dict(leverage), 30)

    class Probe(WaveOverlayStrategy):
        def __init__(self, config):
            super().__init__(config)
            self.opened = False
            self.snapshot = None
        def on_quote_tick(self, tick):
            if tick.instrument_id == BTC_PERP.id and not self.opened:
                self.opened = True
                self.submit_order(self.order_factory.market(instrument_id=BTC_PERP.id, order_side=OrderSide.BUY, quantity=BTC_PERP.make_qty(Decimal("60")), time_in_force=TimeInForce.IOC))
            elif tick.instrument_id == SOL_PERP.id:
                account = self.cache.account_for_venue(SIM)
                self.snapshot = {
                    "total": str(account.balance_total(BTC_PERP.quote_currency)),
                    "free": str(account.balance_free(BTC_PERP.quote_currency)),
                    "native_im": str(account.total_margin_init(BTC_PERP.quote_currency)),
                    "native_mm": str(account.total_margin_maint(BTC_PERP.quote_currency)),
                    "current_policy": str(sum(policy.margin_for(BTC_PERP.id, Decimal("60"), tick.ts_event)[:2])),
                    "prospective_sol_policy": str(sum(policy.margin_for(SOL_PERP.id, Decimal("50"), tick.ts_event)[:2])),
                    "allows_sol50": self._tier_allows_increase(SOL_PERP.id, OrderSide.BUY, Decimal("50"), tick.ts_event),
                    "allows_sol10": self._tier_allows_increase(SOL_PERP.id, OrderSide.BUY, Decimal("10"), tick.ts_event),
                }
    strategy = Probe(lifecycle_config(margin_policy=policy))
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(10000, BTC_PERP.quote_currency)], base_currency=BTC_PERP.quote_currency, default_leverage=Decimal("1"), modules=[module])
    engine.add_instrument(BTC_PERP); engine.add_instrument(SOL_PERP); engine.add_strategy(strategy)
    engine.add_data([venue_mark(BTC_PERP.id, Decimal("100"), 1), venue_mark(SOL_PERP.id, Decimal("100"), 1)], client_id=ClientId("TEST_MARKS"), sort=False)
    engine.add_data([quote(BTC_PERP.id, "100.0", "100.0", 2), quote(SOL_PERP.id, "100.00", "100.00", 3)], sort=False)
    engine.sort_data(); engine.run()
    try:
        print("CANONICAL_NATIVE_MARGIN_PROOF", strategy.snapshot)
        assert module.observed == []
        assert module._dynamic_marks == {}
        assert Decimal(strategy.snapshot["native_im"].split()[0]) == 0
        assert Decimal(strategy.snapshot["native_mm"].split()[0]) == 0
        assert strategy.snapshot["free"] == strategy.snapshot["total"]
        # Fresh total policy requirement exceeds free; no nonexistent lock
        # may offset it. The pre-correction proof admitted this exact order.
        assert not strategy.snapshot["allows_sol50"]
        assert strategy.snapshot["allows_sol10"]
    finally:
        engine.dispose()



@pytest.mark.parametrize("reduce_only", [False, True])
def test_lifecycle_actual_native_order_reservations_and_reduce_only_target_credit(reduce_only):
    class Probe(WaveOverlayStrategy):
        def __init__(self, config):
            super().__init__(config)
            self.opened = False
            self.resting = False
        def on_quote_tick(self, tick):
            if not self.opened:
                self.opened = True
                self.submit_order(self.order_factory.market(instrument_id=BTC_PERP.id, order_side=OrderSide.BUY, quantity=BTC_PERP.make_qty(Decimal("60")), time_in_force=TimeInForce.IOC))
            elif not self.resting:
                self.resting = True
                self.submit_order(self.order_factory.limit(
                    instrument_id=BTC_PERP.id, order_side=OrderSide.SELL if reduce_only else OrderSide.BUY,
                    quantity=BTC_PERP.make_qty(Decimal("10")),
                    price=BTC_PERP.make_price(Decimal("130") if reduce_only else Decimal("90")),
                    time_in_force=TimeInForce.GTC, post_only=True, reduce_only=reduce_only,
                ))
    policy = TierMarginPolicy((), {BTC_PERP.id: Decimal("1"), SOL_PERP.id: Decimal("1")}, 30)
    strategy = Probe(lifecycle_config(margin_policy=policy))
    engine = native_engine(strategy)
    engine.add_data([quote(BTC_PERP.id, "100.0", "100.0", 1), quote(BTC_PERP.id, "100.0", "100.0", 2)])
    engine.run()
    try:
        orders = strategy.cache.orders_open()
        assert len(orders) == 1 and orders[0].is_reduce_only is reduce_only
        account = strategy.cache.account_for_venue(SIM)
        account.update_margin_init(BTC_PERP.id, Money(6000, BTC_PERP.quote_currency))
        account.update_margin_maint(BTC_PERP.id, Money(500, BTC_PERP.quote_currency))
        before = account.balance_free(BTC_PERP.quote_currency).as_decimal()
        policy.update_mark(SimpleNamespace(instrument_id=BTC_PERP.id, price=Decimal("100"), ts_event=100))
        policy.update_mark(SimpleNamespace(instrument_id=SOL_PERP.id, price=Decimal("100"), ts_event=100))
        allowed = strategy._tier_allows_increase(SOL_PERP.id, OrderSide.BUY, Decimal("10"), 110)
        print("NATIVE_ORDER_MARGIN_PROOF", {"reduce_only": reduce_only, "free": str(before), "allows_sol10": allowed})
        assert allowed is reduce_only
        assert account.balance_free(BTC_PERP.quote_currency).as_decimal() == before
        assert not strategy._tier_allows_increase(SOL_PERP.id, OrderSide.BUY, Decimal("50"), 110)
    finally:
        engine.dispose()
