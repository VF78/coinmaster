"""Single native Strategy adapter for the BTC/SOL wave-overlay domain.

Orders are made by Nautilus; this adapter never simulates fills, balance, fees,
or funding.  It is deliberately not declared a research baseline until a
finer execution/settlement-mark dataset and liquidation validation exist.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.events import OrderCanceled, OrderExpired, OrderFilled, OrderRejected
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy

from coinmaster.domain.wave_overlay import Candidate, DailyBar, Intent, WaveOverlayState, features_for


class WaveOverlayStrategyConfig(StrategyConfig, frozen=True):
    btc_id: InstrumentId
    sol_id: InstrumentId
    btc_bar_type: BarType
    sol_bar_type: BarType
    active_seed: Decimal


class WaveOverlayStrategy(Strategy):
    """Turns completed native daily bars into later native market orders."""
    def __init__(self, config: WaveOverlayStrategyConfig) -> None:
        super().__init__(config)
        self._domain = WaveOverlayState(Candidate())
        self._bars: list[DailyBar] = []
        self._pending_by_order: dict[str, Intent] = {}
        self._sigma_by_order: dict[str, float | None] = {}
        self._decision_index_by_order: dict[str, int] = {}
        self._last_sol_close: float | None = None
        self._day: dict[int, dict[InstrumentId, Bar]] = {}

    def on_start(self) -> None:
        self.subscribe_bars(self.config.btc_bar_type)
        self.subscribe_bars(self.config.sol_bar_type)

    def on_bar(self, bar: Bar) -> None:
        instrument_id = bar.bar_type.instrument_id
        if instrument_id not in (self.config.btc_id, self.config.sol_id):
            return
        session = bar.ts_event
        paired = self._day.setdefault(session, {})
        paired[instrument_id] = bar
        if self.config.btc_id not in paired or self.config.sol_id not in paired:
            return
        btc, sol = paired[self.config.btc_id], paired[self.config.sol_id]
        del self._day[session]
        timestamp = datetime.fromtimestamp(btc.ts_event / 1_000_000_000, UTC)
        self._bars.append(DailyBar(timestamp, timestamp, timestamp, float(btc.open), float(btc.close), float(sol.close)))
        self._last_sol_close = float(sol.close)
        signals = features_for(self._bars, Candidate())
        for intent in self._domain.decide(self._bars, signals, len(self._bars) - 1, self._active_marked()):
            self._submit_intent(intent, float(btc.close), float(sol.close), signals[-1].sigma, len(self._bars) - 1)

    def _active_marked(self) -> float:
        account = self.cache.account_for_venue(self.config.btc_id.venue)
        instrument = self.cache.instrument(self.config.btc_id)
        if account is None or instrument is None:
            return float(self.config.active_seed)
        # Native account is the monetary source; this does not fabricate a UI
        # balance.  Full marked-equity reconciliation is still a baseline gate.
        return float(account.balance_total(instrument.quote_currency))

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
            quantity = intent.requested_notional / sol_price
        if quantity is None or quantity <= 0:
            return
        side = OrderSide.BUY if intent.side == 1 else OrderSide.SELL
        reduce_only = intent.action in {"BTC_REDUCE", "SOL_HALF_EXIT", "SOL_EXIT"}
        if reduce_only:
            position = next((item for item in self.cache.positions_open() if item.instrument_id == instrument_id), None)
            if position is None:
                self._domain.on_parent_terminal(intent.id)
                return
            quantity = min(quantity, float(position.quantity))
        order = self.order_factory.market(instrument_id=instrument_id, order_side=side, quantity=instrument.make_qty(Decimal(str(quantity))), time_in_force=TimeInForce.IOC, reduce_only=reduce_only)
        self._pending_by_order[str(order.client_order_id)] = intent
        # Preserve the sigma from the decision in the native order tag map, rather
        # than recalculating it after a later fill.
        self._sigma_by_order[str(order.client_order_id)] = sigma
        self._decision_index_by_order[str(order.client_order_id)] = decision_index
        self.submit_order(order)

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
        if intent.action == "CLOSE_ALL" and not self.cache.positions_open():
            self._domain.on_group_flat()

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
