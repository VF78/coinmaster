"""Single native Strategy adapter for the BTC/SOL wave-overlay domain.

Orders are made by Nautilus; this adapter never simulates fills, balance, fees,
or funding.  It is deliberately not declared a research baseline until a
finer execution/settlement-mark dataset and liquidation validation exist.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType, CustomData, DataType
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.events import OrderCanceled, OrderExpired, OrderFilled, OrderRejected
from nautilus_trader.model.identifiers import ClientId, InstrumentId
from nautilus_trader.trading.strategy import Strategy

from coinmaster.domain.wave_overlay import Candidate, DailyBar, Intent, WaveOverlayState, features_for
from coinmaster.research.native_fixture import TierMarginPolicy
from coinmaster.venues.marks import VenueMark


class WaveOverlayStrategyConfig(StrategyConfig, frozen=True):
    btc_id: InstrumentId
    sol_id: InstrumentId
    btc_bar_type: BarType
    sol_bar_type: BarType
    btc_mark_data_type: DataType
    sol_mark_data_type: DataType
    mark_client_id: ClientId
    active_seed: Decimal
    tier_marks: tuple["MarkPriceUpdate", ...] = ()
    tier_selected_leverage: tuple[tuple[InstrumentId, Decimal], ...] = ()
    max_mark_age_ns: int = 0
    trading_start_open_ns: int | None = None
    terminal_close_at_ns: int | None = None
    candidate: Candidate = Candidate()
    max_gross_to_active: Decimal = Decimal("50")


class WaveOverlayStrategy(Strategy):
    """Turns completed native daily bars into later native market orders."""
    def __init__(self, config: WaveOverlayStrategyConfig) -> None:
        super().__init__(config)
        self._candidate = config.candidate
        self._domain = WaveOverlayState(self._candidate)
        self._bars: list[DailyBar] = []
        self._pending_by_order: dict[str, Intent] = {}
        self._sigma_by_order: dict[str, float | None] = {}
        self._decision_index_by_order: dict[str, int] = {}
        self._last_sol_close: float | None = None
        self._day: dict[int, dict[BarType, Bar]] = {}
        self._marks_by_session: dict[int, dict[InstrumentId, VenueMark]] = {}
        self._current_btc: Bar | None = None
        self._current_sol: Bar | None = None
        self._current_btc_mark: VenueMark | None = None
        self._current_sol_mark: VenueMark | None = None
        self._current_signals = []

    def on_start(self) -> None:
        self.subscribe_bars(self.config.btc_bar_type)
        self.subscribe_bars(self.config.sol_bar_type)
        self.subscribe_data(self.config.btc_mark_data_type, client_id=self.config.mark_client_id)
        self.subscribe_data(self.config.sol_mark_data_type, client_id=self.config.mark_client_id)

    def on_bar(self, bar: Bar) -> None:
        if bar.bar_type not in (self.config.btc_bar_type, self.config.sol_bar_type):
            return
        session = bar.ts_event
        paired = self._day.setdefault(session, {})
        paired[bar.bar_type] = bar
        self._try_advance_session(session)

    def on_data(self, data) -> None:
        """Receive explicit marks without ever making them execution data."""
        # The DataEngine unwraps ``CustomData`` before strategy delivery in
        # Nautilus 1.231.  Accept the wrapper too so the routing contract is
        # explicit at this boundary and remains compatible with direct calls.
        mark = data.data if isinstance(data, CustomData) else data
        if not isinstance(mark, VenueMark):
            return
        if mark.instrument_id not in (self.config.btc_id, self.config.sol_id):
            return
        self._marks_by_session.setdefault(mark.ts_event, {})[mark.instrument_id] = mark
        self._try_advance_session(mark.ts_event)

    def _try_advance_session(self, session: int) -> None:
        paired = self._day.get(session)
        marks = self._marks_by_session.get(session)
        if paired is None or marks is None:
            return
        required = (self.config.btc_bar_type, self.config.sol_bar_type)
        if any(item not in paired for item in required) or self.config.btc_id not in marks or self.config.sol_id not in marks:
            return
        btc, sol = paired[self.config.btc_bar_type], paired[self.config.sol_bar_type]
        btc_mark, sol_mark = marks[self.config.btc_id], marks[self.config.sol_id]
        del self._day[session]
        del self._marks_by_session[session]
        close_time = datetime.fromtimestamp(btc.ts_event / 1_000_000_000, UTC)
        available_at = datetime.fromtimestamp(max(btc.ts_init, sol.ts_init, btc_mark.ts_init, sol_mark.ts_init) / 1_000_000_000, UTC)
        if available_at < close_time:
            self.log.warning("Discarding bars unavailable at their close timestamp")
            return
        self._bars.append(DailyBar(close_time - timedelta(days=1), close_time, available_at, float(btc.open), float(btc.close), float(sol.close)))
        self._last_sol_close = float(sol.close)
        self._current_btc, self._current_sol = btc, sol
        self._current_btc_mark, self._current_sol_mark = btc_mark, sol_mark
        self._current_signals = features_for(self._bars, self._candidate)
        if self.config.terminal_close_at_ns is not None and btc.ts_event >= self.config.terminal_close_at_ns:
            self._submit_terminal_closes()
            return
        self._advance_current_day()

    def _advance_current_day(self) -> None:
        if self._current_btc is None or self._current_sol is None or self._current_btc_mark is None or self._current_sol_mark is None:
            return
        # Bars are emitted at close.  Features may warm up beforehand, but no
        # domain decision (and therefore no order) may occur before the
        # configured interval's first daily open.
        if self.config.trading_start_open_ns is not None and self._current_btc.ts_event - 86_400_000_000_000 < self.config.trading_start_open_ns:
            return
        for intent in self._domain.decide(self._bars, self._current_signals, len(self._bars) - 1, self._active_marked(self._current_btc_mark, self._current_sol_mark)):
            self._submit_intent(intent, float(self._current_btc.close), float(self._current_sol.close), self._current_signals[-1].sigma, len(self._bars) - 1)

    def _active_marked(self, btc_mark: VenueMark, sol_mark: VenueMark) -> float:
        account = self.cache.account_for_venue(self.config.btc_id.venue)
        instrument = self.cache.instrument(self.config.btc_id)
        if account is None or instrument is None:
            return float(self.config.active_seed)
        # Native account is the monetary source; this does not fabricate a UI
        # balance.  Full marked-equity reconciliation is still a baseline gate.
        marked = account.balance_total(instrument.quote_currency).as_decimal()
        mark_by_instrument = {self.config.btc_id: btc_mark.price, self.config.sol_id: sol_mark.price}
        for position in self.cache.positions_open():
            mark = mark_by_instrument.get(position.instrument_id)
            position_instrument = self.cache.instrument(position.instrument_id)
            if mark is not None and position_instrument is not None:
                marked += position.unrealized_pnl(position_instrument.make_price(mark)).as_decimal()
        return float(marked)

    def _submit_intent(self, intent: Intent, btc_price: float, sol_price: float, sigma: float | None, decision_index: int) -> None:
        if intent.action == "CLOSE_ALL":
            for position in self.cache.positions_open():
                if position.instrument_id not in (self.config.btc_id, self.config.sol_id):
                    continue
                instrument = self.cache.instrument(position.instrument_id)
                if instrument is None:
                    continue
                side = OrderSide.SELL if position.is_long else OrderSide.BUY
                order = self.order_factory.market(instrument_id=position.instrument_id, order_side=side, quantity=instrument.make_qty(position.quantity.as_decimal()), time_in_force=TimeInForce.IOC, reduce_only=True)
                self._pending_by_order[str(order.client_order_id)] = intent
                self._sigma_by_order[str(order.client_order_id)] = sigma
                self._decision_index_by_order[str(order.client_order_id)] = decision_index
                self.submit_order(order)
            return
        instrument_id = self.config.btc_id if intent.action.startswith("BTC") else self.config.sol_id
        instrument = self.cache.instrument(instrument_id)
        if instrument is None:
            return
        quantity = intent.quantity
        if intent.action == "BTC_ENTRY" and intent.requested_notional is not None:
            quantity = intent.requested_notional / btc_price
        if intent.action == "SOL_ADD" and intent.requested_notional is not None:
            quantity = min(intent.requested_notional, self._candidate.max_parent_notional) / sol_price
        if quantity is None or quantity <= 0:
            return
        side = OrderSide.BUY if intent.side == 1 else OrderSide.SELL
        reduce_only = intent.action in {"BTC_REDUCE", "SOL_HALF_EXIT", "SOL_EXIT"}
        if not reduce_only and not self._tier_allows_increase(instrument_id, side, Decimal(str(quantity)), self._current_btc_mark.ts_event if self._current_btc_mark else 0):
            self.log.warning(f"Rejecting {intent.action}: missing/stale mark or insufficient public-tier margin")
            self._domain.on_parent_terminal(intent.id)
            return
        if reduce_only:
            position = next((item for item in self.cache.positions_open() if item.instrument_id == instrument_id), None)
            if position is None:
                self._domain.on_parent_terminal(intent.id)
                return
            quantity = min(quantity, float(position.quantity))
        step = instrument.size_increment.as_decimal()
        rounded = (Decimal(str(quantity)) // step) * step
        if rounded <= 0:
            # A sub-step request is a reject, never an implicit size increase.
            self._domain.on_parent_terminal(intent.id)
            return
        order = self.order_factory.market(instrument_id=instrument_id, order_side=side, quantity=instrument.make_qty(rounded), time_in_force=TimeInForce.IOC, reduce_only=reduce_only)
        self._pending_by_order[str(order.client_order_id)] = intent
        # Preserve the sigma from the decision in the native order tag map, rather
        # than recalculating it after a later fill.
        self._sigma_by_order[str(order.client_order_id)] = sigma
        self._decision_index_by_order[str(order.client_order_id)] = decision_index
        self.submit_order(order)

    def _submit_terminal_closes(self) -> None:
        """Realize all remaining native positions on the terminal quote only."""
        for position in self.cache.positions_open():
            if position.instrument_id not in (self.config.btc_id, self.config.sol_id):
                continue
            instrument = self.cache.instrument(position.instrument_id)
            if instrument is None:
                continue
            self.submit_order(self.order_factory.market(
                instrument_id=position.instrument_id,
                order_side=OrderSide.SELL if position.is_long else OrderSide.BUY,
                quantity=instrument.make_qty(position.quantity.as_decimal()),
                time_in_force=TimeInForce.IOC,
                reduce_only=True,
            ))

    def _tier_allows_increase(self, instrument_id: InstrumentId, side: OrderSide, quantity: Decimal, ts_now: int) -> bool:
        """Fail closed on missing/stale public marks; reductions bypass this gate."""
        if not self.config.tier_marks or not self.config.tier_selected_leverage:
            return False
        try:
            policy = TierMarginPolicy(self.config.tier_marks, dict(self.config.tier_selected_leverage), self.config.max_mark_age_ns)
            positions = {item.instrument_id: item for item in self.cache.positions_open()}
            required = Decimal("0")
            gross = Decimal("0")
            for current_id in (self.config.btc_id, self.config.sol_id):
                position = positions.get(current_id)
                current = (
                    position.quantity.as_decimal() if position is not None and position.is_long
                    else -position.quantity.as_decimal() if position is not None
                    else Decimal("0")
                )
                prospective = current + (quantity if side == OrderSide.BUY else -quantity) if current_id == instrument_id else current
                if prospective:
                    initial, _, mark = policy.margin_for(current_id, prospective, ts_now)
                    required += initial
                    gross += abs(prospective) * mark
            account = self.cache.account_for_venue(self.config.btc_id.venue)
            instrument = self.cache.instrument(self.config.btc_id)
            active = Decimal(str(self._active_marked(self._current_btc_mark, self._current_sol_mark))) if self._current_btc_mark and self._current_sol_mark else Decimal("0")
            return account is not None and instrument is not None and active > 0 and gross <= active * self.config.max_gross_to_active and required <= account.balance_free(instrument.quote_currency).as_decimal()
        except ValueError:
            return False

    def on_order_filled(self, event: OrderFilled) -> None:
        intent = self._pending_by_order.get(str(event.client_order_id))
        if intent is None:
            return
        sigma = self._sigma_by_order.get(str(event.client_order_id))
        when = datetime.fromtimestamp(event.ts_event / 1_000_000_000, UTC)
        self._domain.on_fill(intent.id, float(event.last_qty), float(event.last_px), when, sigma)
        if intent.action == "SOL_HALF_EXIT":
            self._domain.on_half_exit_decision(self._decision_index_by_order[str(event.client_order_id)])
        order = self.cache.order(event.client_order_id)
        if order is not None and order.is_closed:
            self._domain.on_parent_terminal(intent.id)
            self._pending_by_order.pop(str(event.client_order_id), None)
            self._sigma_by_order.pop(str(event.client_order_id), None)
            self._decision_index_by_order.pop(str(event.client_order_id), None)
            if intent.action == "CLOSE_ALL":
                if not self.cache.positions_open():
                    if self._domain.on_group_flat() == "REGIME":
                        self._advance_current_day()
                return
            # An entry fills at the next executable event, not at the former
            # signal close; only reduction -> add -> exit phases may continue.
            if intent.action != "BTC_ENTRY":
                self._advance_current_day()

    def on_order_canceled(self, event: OrderCanceled) -> None:
        intent = self._pending_by_order.pop(str(event.client_order_id), None)
        self._sigma_by_order.pop(str(event.client_order_id), None)
        self._decision_index_by_order.pop(str(event.client_order_id), None)
        if intent is not None:
            self._domain.on_parent_cancelled(intent.id)

    def on_order_rejected(self, event: OrderRejected) -> None:
        self._terminal_without_fill(str(event.client_order_id))

    def on_order_expired(self, event: OrderExpired) -> None:
        self._terminal_without_fill(str(event.client_order_id))

    def _terminal_without_fill(self, client_order_id: str) -> None:
        intent = self._pending_by_order.pop(client_order_id, None)
        self._sigma_by_order.pop(client_order_id, None)
        self._decision_index_by_order.pop(client_order_id, None)
        if intent is not None:
            self._domain.on_parent_terminal(intent.id)
