"""Single native Strategy adapter for the BTC/SOL wave-overlay domain.

Orders are made by Nautilus; this adapter never simulates fills, balance, fees,
or funding.  It is deliberately not declared a research baseline until a
finer execution/settlement-mark dataset and liquidation validation exist.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType, CustomData, DataType, MarkPriceUpdate, QuoteTick
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.events import OrderCanceled, OrderExpired, OrderFilled, OrderRejected
from nautilus_trader.model.identifiers import ClientId, InstrumentId
from nautilus_trader.trading.strategy import Strategy

from coinmaster.domain.wave_overlay import Candidate, DailyBar, Intent, WaveOverlayState, features_for
from coinmaster.research.native_fixture import MarkPriceUpdate as FixtureMarkPriceUpdate, TierMarginPolicy
from coinmaster.venues.marks import VenueMark
from coinmaster.venues.signals import DailySignalBar


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
    # A verified history is supplied before native start.  It is feature state
    # only: it never replays old decisions or orders.
    seed_bars: tuple[DailyBar, ...] = ()
    entries_enabled: bool = True
    entries_gate: object | None = None
    event_sink: object | None = None
    submission_sink: object | None = None
    live_mark_client_id: ClientId | None = None
    btc_signal_data_type: DataType | None = None
    sol_signal_data_type: DataType | None = None
    signal_client_id: ClientId | None = None
    # Optional, sparse reporting checkpoints.  They use the same native
    # account/cache and paired CustomData marks as the strategy, never a
    # second PnL or matching model.
    reporting_checkpoint_ns: tuple[int, ...] = ()
    execution_delay_ns: int = 0
    # Immutable execution-policy identity written into every native fill audit.
    execution_policy_hash: str = ""
    execution_policy_version: str = ""


class WaveOverlayStrategy(Strategy):
    """Turns completed native daily bars into later native market orders."""
    def __init__(self, config: WaveOverlayStrategyConfig) -> None:
        super().__init__(config)
        self._candidate = config.candidate
        self._domain = WaveOverlayState(self._candidate)
        self._bars: list[DailyBar] = list(config.seed_bars)
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
        self._current_signals = features_for(self._bars, self._candidate)
        self._latest_marks: dict[InstrumentId, VenueMark] = {}
        self._latest_tier_marks: dict[InstrumentId, FixtureMarkPriceUpdate] = {}
        for update in config.tier_marks:
            previous = self._latest_tier_marks.get(update.instrument_id)
            if previous is None or update.ts_event > previous.ts_event:
                self._latest_tier_marks[update.instrument_id] = update
        self._queued_intents: list[tuple[Intent, float | None, int]] = []
        self._queued_intent_ready_ns: dict[str, int] = {}
        self._mandatory_sol_exit: tuple[Intent, float | None, int] | None = None
        self._queued_close_submitted: dict[str, set[InstrumentId]] = {}
        self._group_close_reconciliation_pending = False
        self._liquidating = False
        self._liquidation_waiting: set[InstrumentId] = set()
        self._liquidation_orders: set[str] = set()
        self._liquidation_submitted: set[InstrumentId] = set()
        self.liquidation_audit: list[dict[str, str]] = []
        self.pre_submit_gate_blocks: list[dict[str, str]] = []
        self.marked_equity_checkpoints: dict[int, dict[str, str]] = {}
        self._terminal_order_ids: set[str] = set()
        self._order_audit: dict[str, dict[str, object]] = {}
        self.fill_audit: list[dict[str, str]] = []
        self._forced_close_reason: str | None = None
        self._forced_close_intent: Intent | None = None
        self._forced_close_submitted: set[InstrumentId] = set()
        self._forced_close_orders: set[str] = set()
        self.terminal_lifecycle: dict[str, object] = {
            "reason": "NOT_TRIGGERED",
            "status": "NOT_TRIGGERED",
            "trigger_ts": None,
            "close_fills": [],
            "lockout": False,
        }

    def on_start(self) -> None:
        self.subscribe_bars(self.config.btc_bar_type)
        self.subscribe_bars(self.config.sol_bar_type)
        # Research feeds explicit VenueMark CustomData.  The live Bybit data
        # adapter publishes MarkPriceUpdate, which is converted below into the
        # same non-matching domain input rather than using MID/quote prices.
        if self.config.live_mark_client_id is None:
            self.subscribe_data(self.config.btc_mark_data_type, client_id=self.config.mark_client_id)
            self.subscribe_data(self.config.sol_mark_data_type, client_id=self.config.mark_client_id)
        else:
            self.subscribe_mark_prices(self.config.btc_id, client_id=self.config.live_mark_client_id)
            self.subscribe_mark_prices(self.config.sol_id, client_id=self.config.live_mark_client_id)
        if self.config.signal_client_id is not None and self.config.btc_signal_data_type is not None and self.config.sol_signal_data_type is not None:
            self.subscribe_data(self.config.btc_signal_data_type, client_id=self.config.signal_client_id)
            self.subscribe_data(self.config.sol_signal_data_type, client_id=self.config.signal_client_id)
        self.subscribe_quote_ticks(self.config.btc_id)
        self.subscribe_quote_ticks(self.config.sol_id)

    def on_bar(self, bar: Bar) -> None:
        if bar.bar_type not in (self.config.btc_bar_type, self.config.sol_bar_type):
            return
        session = bar.ts_event
        paired = self._day.setdefault(session, {})
        paired[bar.bar_type] = bar
        self._try_advance_session(session)

    def on_data(self, data) -> None:
        """Receive explicit marks without ever making them execution data."""
        # Native fill and position events are not guaranteed to reach strategy
        # callbacks in cache-finalized order. The next public data event is a
        # causal reconciliation point before any new daily decision.
        if self._group_close_reconciliation_pending:
            self._reconcile_group_flat()
        # The DataEngine unwraps ``CustomData`` before strategy delivery in
        # Nautilus 1.231.  Accept the wrapper too so the routing contract is
        # explicit at this boundary and remains compatible with direct calls.
        mark = data.data if isinstance(data, CustomData) else data
        if isinstance(mark, DailySignalBar):
            if mark.instrument_id not in (self.config.btc_id, self.config.sol_id):
                return
            bar_type = self.config.btc_bar_type if mark.instrument_id == self.config.btc_id else self.config.sol_bar_type
            self._day.setdefault(mark.ts_event, {})[bar_type] = mark
            # Input ordering is mark -> signal -> quote.  Retain only the two
            # latest marks and pair them here at the daily boundary.
            latest = self._latest_marks.get(mark.instrument_id)
            if latest is not None and latest.ts_event == mark.ts_event:
                self._on_venue_mark(latest)
            self._try_advance_session(mark.ts_event)
            return
        if not isinstance(mark, VenueMark):
            return
        if mark.instrument_id not in (self.config.btc_id, self.config.sol_id):
            return
        self._latest_marks[mark.instrument_id] = mark
        self._latest_tier_marks[mark.instrument_id] = FixtureMarkPriceUpdate(mark.instrument_id, mark.price, mark.ts_event)
        self._check_mark_first_liquidation(mark.ts_event)
        # Avoid a per-minute session map: only a daily signal can make a mark
        # actionable for features, and it will re-pair the retained mark.
        if mark.ts_event in self._day:
            self._on_venue_mark(mark)

    def on_mark_price(self, update: MarkPriceUpdate) -> None:
        """Bridge a public venue mark into the existing non-matching input.

        The mark remains a strategy/risk value only.  It is never published as
        a quote, trade, bar, MID, or execution price.
        """
        if update.instrument_id not in (self.config.btc_id, self.config.sol_id):
            return
        self._latest_tier_marks[update.instrument_id] = FixtureMarkPriceUpdate(update.instrument_id, update.value.as_decimal(), update.ts_event)
        mark = VenueMark(
            update.instrument_id,
            update.value.as_decimal(),
            update.ts_event,
            update.ts_init,
        )
        # Public updates are intraday while Bybit daily bars close at UTC day
        # boundaries.  Keep the last causal mark for that day's close rather
        # than requiring an impossible timestamp equality.
        session = ((update.ts_event + 86_400_000_000_000 - 1) // 86_400_000_000_000) * 86_400_000_000_000
        self._on_venue_mark(mark, session=session)

    def _on_venue_mark(self, mark: VenueMark, *, session: int | None = None) -> None:
        session = mark.ts_event if session is None else session
        self._marks_by_session.setdefault(session, {})[mark.instrument_id] = mark
        if (
            mark.ts_event in self.config.reporting_checkpoint_ns
            and mark.ts_event not in self.marked_equity_checkpoints
            and all(item in self._latest_marks and self._latest_marks[item].ts_event == mark.ts_event for item in (self.config.btc_id, self.config.sol_id))
        ):
            self.marked_equity_checkpoints[mark.ts_event] = {
                "timestamp": str(mark.ts_event),
                "marked_total": str(self._active_marked(self._latest_marks[self.config.btc_id], self._latest_marks[self.config.sol_id])),
                "basis": "NATIVE_CASH_PLUS_OPEN_POSITION_UNREALIZED_AT_PAIRED_VENUE_MARK",
            }
        self._try_advance_session(session)

    def _check_mark_first_liquidation(self, ts_now: int) -> None:
        if self._liquidating or any(item not in self._latest_marks for item in (self.config.btc_id, self.config.sol_id)):
            return
        if self._latest_marks[self.config.btc_id].ts_event != ts_now or self._latest_marks[self.config.sol_id].ts_event != ts_now:
            return
        positions = [item for item in self.cache.positions_open() if item.instrument_id in (self.config.btc_id, self.config.sol_id)]
        if not positions or not self.config.tier_selected_leverage:
            return
        account = self.cache.account_for_venue(self.config.btc_id.venue)
        base = self.cache.instrument(self.config.btc_id)
        if account is None or base is None:
            return
        try:
            policy = TierMarginPolicy(tuple(self._latest_tier_marks.values()), dict(self.config.tier_selected_leverage), 0)
            equity, maintenance = account.balance_total(base.quote_currency).as_decimal(), Decimal("0")
            for position in positions:
                instrument = self.cache.instrument(position.instrument_id)
                if instrument is None:
                    return
                mark = self._latest_marks[position.instrument_id].price
                equity += position.unrealized_pnl(instrument.make_price(mark)).as_decimal()
                maintenance += policy.margin_for(position.instrument_id, position.quantity.as_decimal(), ts_now)[1]
        except ValueError:
            return
        if equity > maintenance:
            return
        self._liquidating = True
        self._queued_intents.clear()
        self._queued_intent_ready_ns.clear()
        self._liquidation_waiting = {position.instrument_id for position in positions}
        self.liquidation_audit.append({
            "trigger_ts": str(ts_now),
            "marked_equity": str(equity),
            "tier_maintenance_margin": str(maintenance),
            "status": "ARMED",
            "close_fills": [],
            "close_value": "0",
            "lockout": "true",
        })
        self._begin_forced_close("LIQUIDATION")

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
        # A mark observed before the close is causal, but the paired daily bar
        # is not usable until its UTC close.  A late bar/mark delays the tuple.
        available_at = datetime.fromtimestamp(max(btc.ts_init, sol.ts_init, btc_mark.ts_init, sol_mark.ts_init, btc.ts_event) / 1_000_000_000, UTC)
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
        if self._liquidating or (not self._entries_enabled() and not self.cache.positions_open()):
            return
        for intent in self._domain.decide(self._bars, self._current_signals, len(self._bars) - 1, self._active_marked(self._current_btc_mark, self._current_sol_mark)):
            if intent.action == "CLOSE_ALL":
                # A mandatory group exit owns the next executable quotes.  It
                # must not wait behind an older queued SOL add or planned exit.
                self._discard_queued_intents(lambda queued: queued.id != intent.id)
                self._begin_forced_close(intent.reason or "CLOSE_ALL", intent)
                return
            if intent.action == "SOL_EXIT" and intent.reason == "SOL_HARD_TIMEOUT":
                self._preempt_with_mandatory_sol_exit(intent, self._current_signals[-1].sigma, len(self._bars) - 1)
                return
            self._queued_intents.append((intent, self._current_signals[-1].sigma, len(self._bars) - 1))
            self._queued_intent_ready_ns[intent.id] = self._current_btc.ts_event + self.config.execution_delay_ns

    def on_quote_tick(self, tick: QuoteTick) -> None:
        """Only quotes can execute queued daily decisions or liquidations."""
        if self._mandatory_sol_exit is not None:
            # A timeout is allowed to cancel a stale/resting SOL reduction,
            # then uses the actual native position leaves on the next SOL
            # quote. No queued increase may pass while this is in progress.
            if tick.instrument_id != self.config.sol_id or any(order.instrument_id == self.config.sol_id for order in self.cache.orders_open()):
                return
            intent, sigma, index = self._mandatory_sol_exit
            self._mandatory_sol_exit = None
            self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), sigma, index, ts_now=tick.ts_event)
            return
        if self._forced_close_reason is not None:
            self._submit_forced_close_on_quote(tick)
            return
        if self._liquidating:
            if tick.instrument_id in self._liquidation_waiting and tick.instrument_id not in self._liquidation_submitted:
                position = next((item for item in self.cache.positions_open() if item.instrument_id == tick.instrument_id), None)
                instrument = self.cache.instrument(tick.instrument_id)
                if position is not None and instrument is not None:
                    order = self.order_factory.market(instrument_id=tick.instrument_id, order_side=OrderSide.SELL if position.is_long else OrderSide.BUY, quantity=instrument.make_qty(position.quantity.as_decimal()), time_in_force=TimeInForce.IOC, reduce_only=True)
                    if self._record_submission(order, f"liquidation:{order.client_order_id}", "liquidation", "LIQUIDATION_CLOSE"):
                        self._liquidation_submitted.add(tick.instrument_id); self._liquidation_orders.add(str(order.client_order_id)); self.submit_order(order)
            return
        for item in list(self._queued_intents):
            intent, sigma, index = item
            if tick.ts_event < self._queued_intent_ready_ns.get(intent.id, 0):
                continue
            target = self.config.btc_id if intent.action.startswith("BTC") else self.config.sol_id
            if intent.action == "CLOSE_ALL":
                self._queued_intents.remove(item)
                self._queued_intent_ready_ns.pop(intent.id, None)
                self._begin_forced_close(intent.reason or "CLOSE_ALL", intent)
                continue
            if target == tick.instrument_id:
                self._queued_intents.remove(item)
                self._queued_intent_ready_ns.pop(intent.id, None)
                self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), sigma, index, ts_now=tick.ts_event)

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

    def _submit_intent(self, intent: Intent, bid_price: float, ask_price: float, sigma: float | None, decision_index: int, only_instrument: InstrumentId | None = None, ts_now: int | None = None) -> None:
        if intent.action == "CLOSE_ALL":
            for position in self.cache.positions_open():
                if position.instrument_id not in (self.config.btc_id, self.config.sol_id):
                    continue
                if only_instrument is not None and position.instrument_id != only_instrument:
                    continue
                instrument = self.cache.instrument(position.instrument_id)
                if instrument is None:
                    continue
                side = OrderSide.SELL if position.is_long else OrderSide.BUY
                order = self.order_factory.market(instrument_id=position.instrument_id, order_side=side, quantity=instrument.make_qty(position.quantity.as_decimal()), time_in_force=TimeInForce.IOC, reduce_only=True)
                if not self._record_submission(order, intent.id, intent.episode_id, intent.action):
                    continue
                self._pending_by_order[str(order.client_order_id)] = intent
                self._sigma_by_order[str(order.client_order_id)] = sigma
                self._decision_index_by_order[str(order.client_order_id)] = decision_index
                self.submit_order(order)
            return
        instrument_id = self.config.btc_id if intent.action.startswith("BTC") else self.config.sol_id
        instrument = self.cache.instrument(instrument_id)
        if instrument is None:
            return
        side = OrderSide.BUY if intent.side == 1 else OrderSide.SELL
        executable_price = Decimal(str(ask_price if side == OrderSide.BUY else bid_price))
        quantity = intent.quantity
        if intent.action == "BTC_ENTRY" and intent.requested_notional is not None:
            quantity = float(Decimal(str(intent.requested_notional)) / executable_price)
        if intent.action == "SOL_ADD" and intent.requested_notional is not None:
            quantity = float(Decimal(str(min(intent.requested_notional, self._candidate.max_parent_notional))) / executable_price)
        if quantity is None or quantity <= 0:
            return
        reduce_only = intent.action in {"BTC_REDUCE", "SOL_HALF_EXIT", "SOL_EXIT"}
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
        # Increases are gated at the last safe point, after executable-price
        # sizing/normalization and immediately before native order creation.
        # Reductions deliberately bypass both the pause/stale and margin gates.
        if not reduce_only:
            now = ts_now if ts_now is not None else self._current_btc.ts_event if self._current_btc else 0
            min_quantity = instrument.min_quantity.as_decimal() if instrument.min_quantity is not None else None
            min_notional = instrument.min_notional.as_decimal() if instrument.min_notional is not None else None
            meets_minimum = (min_quantity is None or rounded >= min_quantity) and (min_notional is None or rounded * executable_price >= min_notional)
            if not meets_minimum or not self._entries_enabled() or not self._tier_allows_increase(instrument_id, side, rounded, now):
                self.log.warning(f"Rejecting {intent.action}: pre-submit increase gate or minimum failed")
                self.pre_submit_gate_blocks.append({
                    "timestamp": str(now),
                    "intent_id": intent.id,
                    "action": intent.action,
                    "reason": "PRE_SUBMIT_INCREASE_GATE_OR_MINIMUM",
                })
                self._domain.on_parent_terminal(intent.id)
                return
        # Control A makes every planned SOL exit a native taker IOC.  Resting
        # post-only liquidity remains only for explicit BTC TP targets.
        passive_reduction = intent.action == "BTC_REDUCE" and intent.limit_price is not None
        if passive_reduction:
            raw_price = Decimal(str(intent.limit_price)) if intent.limit_price is not None else (
                executable_price
            )
            # For a planned SOL z exit, quote at the passive side.  A target
            # BTC price is supplied by the confirmed-entry plan above.
            if intent.limit_price is None:
                quote_tick = self.cache.quote_tick(instrument_id)
                if quote_tick is None:
                    self._domain.on_parent_cancelled(intent.id)
                    return
                raw_price = quote_tick.ask_price.as_decimal() if side == OrderSide.SELL else quote_tick.bid_price.as_decimal()
            quote_tick = self.cache.quote_tick(instrument_id)
            if quote_tick is not None:
                # Reject marketable post-only requests locally; do not turn
                # them into a taker order or fabricate a maker classification.
                if (side == OrderSide.BUY and raw_price >= quote_tick.ask_price.as_decimal()) or (side == OrderSide.SELL and raw_price <= quote_tick.bid_price.as_decimal()):
                    self._domain.on_parent_cancelled(intent.id)
                    return
            order = self.order_factory.limit(
                instrument_id=instrument_id, order_side=side, quantity=instrument.make_qty(rounded),
                price=instrument.make_price(raw_price), time_in_force=TimeInForce.GTC,
                post_only=True, reduce_only=True,
            )
        else:
            order = self.order_factory.market(instrument_id=instrument_id, order_side=side, quantity=instrument.make_qty(rounded), time_in_force=TimeInForce.IOC, reduce_only=reduce_only)
        if not self._record_submission(order, intent.id, intent.episode_id, intent.action, intent.reason, intent.level):
            self._domain.on_parent_terminal(intent.id)
            return
        self._pending_by_order[str(order.client_order_id)] = intent
        # Preserve the sigma from the decision in the native order tag map, rather
        # than recalculating it after a later fill.
        self._sigma_by_order[str(order.client_order_id)] = sigma
        self._decision_index_by_order[str(order.client_order_id)] = decision_index
        self.submit_order(order)

    def _discard_queued_intents(self, predicate) -> None:
        """Terminally remove queued work that a mandatory exit supersedes."""
        retained: list[tuple[Intent, float | None, int]] = []
        for queued in self._queued_intents:
            intent, _, _ = queued
            if predicate(intent):
                self._queued_intent_ready_ns.pop(intent.id, None)
                self._domain.on_parent_terminal(intent.id)
            else:
                retained.append(queued)
        self._queued_intents = retained

    def _preempt_with_mandatory_sol_exit(self, intent: Intent, sigma: float | None, index: int) -> None:
        """Cancel SOL leaves before a timeout reduces the reconciled remainder."""
        self._discard_queued_intents(lambda queued: queued.action.startswith("SOL") and queued.id != intent.id)
        for order in list(self.cache.orders_open()):
            if order.instrument_id == self.config.sol_id:
                self.cancel_order(order)
        self._mandatory_sol_exit = (intent, sigma, index)

    def _begin_forced_close(self, reason: str, intent: Intent | None = None) -> None:
        """Cancel every resting order before closing actual cache leaves taker."""
        # Terminal settlement is the final authority: it may supersede an
        # earlier liquidation-close attempt whose native leaves remain open.
        # A liquidation likewise supersedes a prior ordinary regime/trail
        # close; only an already-active liquidation remains idempotent.
        supersedes = reason == "TERMINAL_BOUNDARY_SETTLEMENT" or (
            reason == "LIQUIDATION" and self._forced_close_reason not in {None, "LIQUIDATION"}
        )
        if self._forced_close_reason is not None and not supersedes:
            return
        # A forced group close owns both instruments. A queued timeout has no
        # authority to wait for a SOL quote ahead of liquidation, regime,
        # trail, or terminal settlement. Clear its domain marker before the
        # cancellation callbacks race with a native fill; the forced path
        # always reads actual cache leaves for its reduce-only quantity.
        if self._mandatory_sol_exit is not None:
            timeout, _, _ = self._mandatory_sol_exit
            self._mandatory_sol_exit = None
            self._domain.on_parent_terminal(timeout.id)
        self._discard_queued_intents(lambda _queued: True)
        self._forced_close_reason = reason
        self._forced_close_intent = intent
        self._forced_close_submitted.clear()
        for order in list(self.cache.orders_open()):
            self.cancel_order(order)

    def _submit_forced_close_on_quote(self, tick: QuoteTick) -> None:
        # Cancel confirmation/reconciliation is authoritative: no market close
        # is submitted while a resting reduction can still consume leaves.
        if self.cache.orders_open():
            return
        position = next((item for item in self.cache.positions_open() if item.instrument_id == tick.instrument_id), None)
        if position is None or tick.instrument_id in self._forced_close_submitted:
            if not self.cache.positions_open() and self._forced_close_intent is not None:
                self._domain.on_parent_terminal(self._forced_close_intent.id)
                self._group_close_reconciliation_pending = True
                self._reconcile_group_flat()
            return
        instrument = self.cache.instrument(tick.instrument_id)
        if instrument is None:
            return
        order = self.order_factory.market(
            instrument_id=tick.instrument_id, order_side=OrderSide.SELL if position.is_long else OrderSide.BUY,
            quantity=instrument.make_qty(position.quantity.as_decimal()), time_in_force=TimeInForce.IOC, reduce_only=True,
        )
        forced_action = "TERMINAL_CLOSE" if self._forced_close_reason == "TERMINAL_BOUNDARY_SETTLEMENT" else "LIQUIDATION_CLOSE" if self._forced_close_reason == "LIQUIDATION" else "FORCED_CLOSE"
        if not self._record_submission(order, f"{self._forced_close_reason}:{order.client_order_id}", "forced", forced_action, self._forced_close_reason, None):
            return
        self._forced_close_submitted.add(tick.instrument_id)
        self._forced_close_orders.add(str(order.client_order_id))
        if self._forced_close_reason == "TERMINAL_BOUNDARY_SETTLEMENT":
            self._terminal_order_ids.add(str(order.client_order_id))
            self.terminal_lifecycle["status"] = "CLOSE_SUBMITTED"
        elif self._forced_close_reason == "LIQUIDATION":
            self._liquidation_orders.add(str(order.client_order_id))
        self.submit_order(order)

    def _submit_forced_closes_from_cache(self) -> None:
        """Continue a forced close after the final native cancel confirmation."""
        if self.cache.orders_open():
            return
        for position in list(self.cache.positions_open()):
            if position.instrument_id not in (self.config.btc_id, self.config.sol_id) or position.instrument_id in self._forced_close_submitted:
                continue
            # A market order remains native taker; this read only verifies a
            # current native book exists to match it against.
            if self.cache.quote_tick(position.instrument_id) is None:
                continue
            instrument = self.cache.instrument(position.instrument_id)
            if instrument is None:
                continue
            order = self.order_factory.market(
                instrument_id=position.instrument_id,
                order_side=OrderSide.SELL if position.is_long else OrderSide.BUY,
                quantity=instrument.make_qty(position.quantity.as_decimal()),
                time_in_force=TimeInForce.IOC, reduce_only=True,
            )
            forced_action = "TERMINAL_CLOSE" if self._forced_close_reason == "TERMINAL_BOUNDARY_SETTLEMENT" else "LIQUIDATION_CLOSE" if self._forced_close_reason == "LIQUIDATION" else "FORCED_CLOSE"
            if not self._record_submission(order, f"{self._forced_close_reason}:{order.client_order_id}", "forced", forced_action, self._forced_close_reason, None):
                continue
            self._forced_close_submitted.add(position.instrument_id)
            self._forced_close_orders.add(str(order.client_order_id))
            if self._forced_close_reason == "TERMINAL_BOUNDARY_SETTLEMENT":
                self._terminal_order_ids.add(str(order.client_order_id))
                self.terminal_lifecycle["status"] = "CLOSE_SUBMITTED"
            elif self._forced_close_reason == "LIQUIDATION":
                self._liquidation_orders.add(str(order.client_order_id))
            self.submit_order(order)

    def _submit_terminal_closes(self) -> None:
        """Realize all remaining native positions on the terminal quote only."""
        trigger_ts = self._current_btc.ts_event if self._current_btc is not None else None
        self.terminal_lifecycle = {
            "reason": "TERMINAL_BOUNDARY_SETTLEMENT",
            "status": "NO_OPEN_POSITION",
            "trigger_ts": str(trigger_ts) if trigger_ts is not None else None,
            "close_fills": [],
            "lockout": True,
        }
        if not any(position.instrument_id in (self.config.btc_id, self.config.sol_id) for position in self.cache.positions_open()):
            self.terminal_lifecycle["status"] = "FLAT"
            return
        self._begin_forced_close("TERMINAL_BOUNDARY_SETTLEMENT")

    def _tier_allows_increase(self, instrument_id: InstrumentId, side: OrderSide, quantity: Decimal, ts_now: int) -> bool:
        """Fail closed on missing/stale public marks; reductions bypass this gate."""
        if not self._latest_tier_marks or not self.config.tier_selected_leverage:
            return False
        try:
            policy = TierMarginPolicy(tuple(self._latest_tier_marks.values()), dict(self.config.tier_selected_leverage), self.config.max_mark_age_ns)
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
        self._record_native_event(str(event.trade_id), "fill")
        self._record_fill_audit(event)
        if str(event.client_order_id) in self._liquidation_orders:
            if self.liquidation_audit:
                audit = self.liquidation_audit[-1]
                fills = audit["close_fills"]
                assert isinstance(fills, list)
                fills.append({"instrument_id": str(event.instrument_id), "timestamp": str(event.ts_event), "value": str(event.last_qty.as_decimal() * event.last_px.as_decimal())})
                audit["close_value"] = str(sum((Decimal(item["value"]) for item in fills), Decimal("0")))
            order = self.cache.order(event.client_order_id)
            if order is not None and order.is_closed:
                self._terminal_submission(str(event.client_order_id))
            self._reconcile_liquidation_flat()
            return
        if str(event.client_order_id) in self._terminal_order_ids:
            fills = self.terminal_lifecycle["close_fills"]
            assert isinstance(fills, list)
            fills.append({"instrument_id": str(event.instrument_id), "timestamp": str(event.ts_event), "value": str(event.last_qty.as_decimal() * event.last_px.as_decimal())})
            order = self.cache.order(event.client_order_id)
            if order is not None and order.is_closed:
                self._terminal_submission(str(event.client_order_id))
            self._reconcile_terminal_flat()
            return
        if str(event.client_order_id) in self._forced_close_orders:
            order = self.cache.order(event.client_order_id)
            if order is not None and order.is_closed and self._forced_close_intent is not None:
                self._domain.on_parent_terminal(self._forced_close_intent.id)
                self._group_close_reconciliation_pending = True
                self._reconcile_group_flat()
            return
        intent = self._pending_by_order.get(str(event.client_order_id))
        if intent is None:
            return
        sigma = self._sigma_by_order.get(str(event.client_order_id))
        when = datetime.fromtimestamp(event.ts_event / 1_000_000_000, UTC)
        self._domain.on_fill(
            intent.id, float(event.last_qty), float(event.last_px), when, sigma,
            decision_index=self._confirmed_fill_cycle(intent, str(event.client_order_id)),
        )
        if intent.action == "SOL_HALF_EXIT":
            self._domain.on_half_exit_decision(self._decision_index_by_order[str(event.client_order_id)])
        order = self.cache.order(event.client_order_id)
        if order is not None and order.is_closed:
            self._terminal_submission(str(event.client_order_id))
            self._domain.on_parent_terminal(intent.id)
            self._pending_by_order.pop(str(event.client_order_id), None)
            self._sigma_by_order.pop(str(event.client_order_id), None)
            self._decision_index_by_order.pop(str(event.client_order_id), None)
            if intent.action == "BTC_ENTRY":
                # TP rights are derived from the native entry fill only.  They
                # are submitted as passive limits and must fill on a later
                # quote to receive native MAKER liquidity attribution.
                for target in self._domain.plan_confirmed_btc_targets():
                    self._queued_intents.append((target, sigma, intent.decision_index))
                    self._queued_intent_ready_ns[target.id] = event.ts_event + 1
            if intent.action == "CLOSE_ALL":
                self._group_close_reconciliation_pending = True
                self._reconcile_group_flat()
                return
            # An entry fills at the next executable event, not at the former
            # signal close; only reduction -> add -> exit phases may continue.
            if intent.action != "BTC_ENTRY":
                self._advance_current_day()

    def on_order_canceled(self, event: OrderCanceled) -> None:
        self._terminal_submission(str(event.client_order_id))
        client_order_id = str(event.client_order_id)
        if client_order_id in self._forced_close_orders:
            order = self.cache.order(event.client_order_id)
            if order is not None:
                self._forced_close_submitted.discard(order.instrument_id)
            self._forced_close_orders.discard(client_order_id)
        intent = self._pending_by_order.pop(str(event.client_order_id), None)
        self._sigma_by_order.pop(str(event.client_order_id), None)
        self._decision_index_by_order.pop(str(event.client_order_id), None)
        if intent is not None:
            self._domain.on_parent_cancelled(intent.id)
        if self._forced_close_reason is not None and not self.cache.orders_open():
            self._submit_forced_closes_from_cache()

    def on_order_event(self, event) -> None:
        self._record_native_event(str(event.client_order_id), "order")
        context = self._order_audit.get(str(event.client_order_id))
        if context is not None and context.get("accept_ns") is None:
            context["accept_ns"] = str(getattr(event, "ts_event", getattr(event, "ts_init", "")))
        self._acknowledge_submission(str(event.client_order_id))

    def on_position_event(self, event) -> None:
        self._record_native_event(f"{event.position_id}:{event.ts_init}", "position")
        self._reconcile_group_flat()
        self._reconcile_liquidation_flat()
        self._reconcile_terminal_flat()

    def _reconcile_group_flat(self) -> None:
        """Clear a completed close group after the native cache is actually flat."""
        if not self._group_close_reconciliation_pending or self.cache.positions_open() or self.cache.orders_open():
            return
        self._group_close_reconciliation_pending = False
        reason = self._domain.on_group_flat()
        if self._forced_close_reason not in {"LIQUIDATION", "TERMINAL_BOUNDARY_SETTLEMENT"}:
            self._forced_close_reason = None
            self._forced_close_intent = None
            self._forced_close_orders.clear()
        if reason == "REGIME":
            self._advance_current_day()

    def _reconcile_liquidation_flat(self) -> None:
        if not self._liquidating or self.cache.positions_open() or self.cache.orders_open():
            return
        if self.liquidation_audit and self.liquidation_audit[-1]["status"] == "FLAT_LOCKED":
            return
        self._domain.on_liquidation()
        if self.liquidation_audit:
            self.liquidation_audit[-1]["status"] = "FLAT_LOCKED"

    def _reconcile_terminal_flat(self) -> None:
        if self.terminal_lifecycle["status"] != "CLOSE_SUBMITTED" or self.cache.positions_open() or self.cache.orders_open():
            return
        self.terminal_lifecycle["status"] = "FLAT"

    def reporting_state(self) -> dict[str, object]:
        """Authoritative native adapter state for diagnostic-only exports."""
        self._reconcile_liquidation_flat()
        self._reconcile_terminal_flat()
        return {
            "liquidations": self.liquidation_audit,
            "liquidation_lockout": self._liquidating,
            "terminal_lifecycle": self.terminal_lifecycle,
            "terminal_open_orders": len(self.cache.orders_open()),
            "pre_submit_tier_margin_gate_blocks": self.pre_submit_gate_blocks,
            "marked_equity_checkpoints": [self.marked_equity_checkpoints[key] for key in sorted(self.marked_equity_checkpoints)],
            "fill_audit": self.fill_audit,
        }

    def on_order_rejected(self, event: OrderRejected) -> None:
        self._terminal_without_fill(str(event.client_order_id))

    def on_order_expired(self, event: OrderExpired) -> None:
        self._terminal_without_fill(str(event.client_order_id))

    def _terminal_without_fill(self, client_order_id: str) -> None:
        self._terminal_submission(client_order_id)
        if client_order_id in self._forced_close_orders:
            order = self.cache.order(client_order_id)
            if order is not None:
                self._forced_close_submitted.discard(order.instrument_id)
            self._forced_close_orders.discard(client_order_id)
        intent = self._pending_by_order.pop(client_order_id, None)
        self._sigma_by_order.pop(client_order_id, None)
        self._decision_index_by_order.pop(client_order_id, None)
        if intent is not None:
            self._domain.on_parent_terminal(intent.id)
        if self._forced_close_reason is not None and not self.cache.orders_open():
            self._submit_forced_closes_from_cache()

    def _entries_enabled(self) -> bool:
        gate = self.config.entries_gate
        return self.config.entries_enabled and (bool(gate()) if callable(gate) else True)

    def _confirmed_fill_cycle(self, intent: Intent, client_order_id: str) -> int:
        """Map a confirmed TP fill to the current causal decision cycle.

        A BTC target may rest across daily decisions. Strict H3 rights must
        use the cycle in which Nautilus confirms that fill, not its old target
        creation/submission index. Other intents retain their own decision
        context for audit and exit ordering.
        """
        if intent.action == "BTC_REDUCE":
            return max(0, len(self._bars) - 1)
        return self._decision_index_by_order.get(client_order_id, max(0, len(self._bars) - 1))

    def _record_native_event(self, event_id: str, kind: str) -> None:
        sink = self.config.event_sink
        if callable(sink):
            sink(event_id, kind)

    def _record_submission(self, order, intent_id: str, episode_id: str, action: str, reason: str | None = None, level: int | None = None) -> bool:
        self._order_audit[str(order.client_order_id)] = {
            "venue": str(order.instrument_id.venue), "instrument": str(order.instrument_id),
            "action": action, "reason": reason or action, "level": "" if level is None else str(level),
            "order_type": str(order.order_type), "post_only": str(bool(order.is_post_only)).lower(),
            "submit_ns": str(order.ts_init), "accept_ns": None,
        }
        sink = self.config.submission_sink
        if not callable(sink):
            return True
        return bool(sink(
            client_order_id=str(order.client_order_id), intent_id=intent_id, episode_id=episode_id,
            action=action, instrument_id=str(order.instrument_id), quantity=str(order.quantity), reduce_only=bool(order.is_reduce_only),
        ))

    def _record_fill_audit(self, event: OrderFilled) -> None:
        """Preserve native fill facts; classification is never inferred."""
        context = self._order_audit.get(str(event.client_order_id), {})
        liquidity = getattr(event.liquidity_side, "name", str(event.liquidity_side))
        commission = event.commission.as_decimal()
        self.fill_audit.append({
            "venue": str(context.get("venue", event.instrument_id.venue)),
            "instrument": str(event.instrument_id),
            "action": str(context.get("action", "UNKNOWN")),
            "reason": str(context.get("reason", "UNKNOWN")),
            "level": str(context.get("level", "")),
            "order_type": str(event.order_type),
            "post_only": str(context.get("post_only", "false")),
            "submit_ns": str(context.get("submit_ns", event.ts_init)),
            "accept_ns": str(context.get("accept_ns") or event.ts_init),
            "fill_ns": str(event.ts_event),
            "qty": str(event.last_qty.as_decimal()),
            "px": str(event.last_px.as_decimal()),
            "native_liquidity_side": str(liquidity),
            "notional": str(event.last_qty.as_decimal() * event.last_px.as_decimal()),
            "commission": str(commission),
            "commission_currency": str(event.commission.currency),
            "policy_hash": self.config.execution_policy_hash,
        })

    def _acknowledge_submission(self, client_order_id: str) -> None:
        sink = self.config.submission_sink
        if callable(sink):
            acknowledge = getattr(sink, "acknowledge", None)
            if callable(acknowledge):
                acknowledge(client_order_id)

    def _terminal_submission(self, client_order_id: str) -> None:
        sink = self.config.submission_sink
        if callable(sink):
            terminal = getattr(sink, "terminal", None)
            if callable(terminal):
                terminal(client_order_id)
