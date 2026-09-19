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
from nautilus_trader.model.events import OrderCanceled, OrderFilled
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
        self._day: dict[InstrumentId, Bar] = {}

    def on_start(self) -> None:
        self.subscribe_bars(self.config.btc_bar_type)
        self.subscribe_bars(self.config.sol_bar_type)

    def on_bar(self, bar: Bar) -> None:
        instrument_id = bar.bar_type.instrument_id
        if instrument_id not in (self.config.btc_id, self.config.sol_id):
            return
        self._day[instrument_id] = bar
        if self.config.btc_id not in self._day or self.config.sol_id not in self._day:
            return
        btc, sol = self._day.pop(self.config.btc_id), self._day.pop(self.config.sol_id)
        timestamp = datetime.fromtimestamp(btc.ts_event / 1_000_000_000, UTC)
        self._bars.append(DailyBar(timestamp, timestamp, timestamp, float(btc.open), float(btc.close), float(sol.close)))
        signals = features_for(self._bars, Candidate())
        for intent in self._domain.decide(self._bars, signals, len(self._bars) - 1, float(self.config.active_seed)):
            self._submit_intent(intent, float(btc.close), signals[-1].sigma)

    def _submit_intent(self, intent: Intent, btc_price: float, sigma: float | None) -> None:
        if intent.action == "CLOSE_ALL":
            # A full-group close is deferred until the adapter can prove both native
            # positions and reduce-only quantities; it must never guess/reverse size.
            self.log.warning("CLOSE_ALL requires native position reconciliation; no order submitted")
            return
        instrument_id = self.config.btc_id if intent.action.startswith("BTC") else self.config.sol_id
        instrument = self.cache.instrument(instrument_id)
        if instrument is None:
            return
        quantity = intent.quantity
        if intent.action == "BTC_ENTRY" and intent.requested_notional is not None:
            quantity = intent.requested_notional / btc_price
        if quantity is None or quantity <= 0:
            return
        side = OrderSide.BUY if intent.side == 1 else OrderSide.SELL
        order = self.order_factory.market(instrument_id=instrument_id, order_side=side, quantity=instrument.make_qty(Decimal(str(quantity))), time_in_force=TimeInForce.IOC)
        self._pending_by_order[str(order.client_order_id)] = intent
        # Preserve the sigma from the decision in the native order tag map, rather
        # than recalculating it after a later fill.
        self._sigma_by_order[str(order.client_order_id)] = sigma
        self.submit_order(order)

    def on_order_filled(self, event: OrderFilled) -> None:
        intent = self._pending_by_order.get(str(event.client_order_id))
        if intent is None:
            return
        sigma = self._sigma_by_order.get(str(event.client_order_id))
        when = datetime.fromtimestamp(event.ts_event / 1_000_000_000, UTC)
        self._domain.on_fill(intent.id, float(event.last_qty), float(event.last_px), when, sigma)

    def on_order_canceled(self, event: OrderCanceled) -> None:
        intent = self._pending_by_order.pop(str(event.client_order_id), None)
        self._sigma_by_order.pop(str(event.client_order_id), None)
        if intent is not None:
            self._domain.on_parent_cancelled(intent.id)
