"""Default-OFF native S0 remainder management; no independent money ledger."""
from decimal import Decimal as D
from nautilus_trader.model.enums import OrderSide, TimeInForce

class S0ManagementResearch:
    def _s0_init(self):
        self._s0_previous = {}
        self._s0_claimed = set()
        self._s0_targets = {}
        self._s0_orders = {}
        self._s0_last_increase = {}
        self.s0_management_audit = []

    @staticmethod
    def _s0_cycle(position):
        return (str(position.instrument_id), str(position.id), str(position.opening_order_id), int(position.ts_opened))

    def _s0_position(self, instrument_id):
        return next((p for p in self.cache.positions_open() if p.instrument_id == instrument_id), None)

    def _s0_emergency(self):
        return bool(self._forced_close_reason or self._liquidating or
                    (self.config.deposit_runtime is not None and self._deposit.latched))

    def _s0_intent_asset(self, intent, instrument_id):
        return intent.action == 'CLOSE_ALL' or (intent.action.startswith('BTC') if instrument_id == self.config.btc_id else intent.action.startswith('SOL'))

    def _s0_eligible(self, position, mark, source, *, executing=False):
        instrument_id = position.instrument_id
        if self._s0_emergency() or (self.config.terminal_close_at_ns is not None and source >= self.config.terminal_close_at_ns):
            return False
        if self._domain.episode is None or (instrument_id == self.config.btc_id and self._split_unfinished()):
            return False
        if instrument_id == self.config.sol_id and self._mandatory_sol_exit is not None:
            return False
        if source <= max(position.ts_opened, self._s0_last_increase.get(instrument_id, 0)):
            return False
        ep = self._domain.episode
        for intent in self._pending_by_order.values():
            if self._s0_intent_asset(intent, instrument_id) and intent.id not in ep.resting_reductions:
                return False
        if any(self._s0_intent_asset(i, instrument_id) for i, _, _ in self._queued_intents):
            return False
        if any(o.instrument_id == instrument_id and str(o.client_order_id) not in self._s0_orders for o in self.cache.orders_inflight()):
            return False
        for order in self.cache.orders_open():
            if order.instrument_id != instrument_id or str(order.client_order_id) in self._s0_orders:
                continue
            # Only acknowledged, nonmarketable resting post-only BTC TP is cancelable.
            if instrument_id != self.config.btc_id or not order.is_reduce_only or not order.is_post_only:
                return False
            if order.price is None or (position.is_long and order.price.as_decimal() <= mark) or (not position.is_long and order.price.as_decimal() >= mark):
                return False
        return True

    def _s0_receipt(self, source, receipt, equity, peak, epoch, account_ns, marks):
        fraction = self.config.research_s0_management_fraction
        if fraction is None:
            return
        dd = max(D(0), (peak-equity)/peak) if peak > 0 else D(0)
        live = set()
        for instrument_id in (self.config.btc_id, self.config.sol_id):
            position = self._s0_position(instrument_id)
            if position is None:
                self._s0_previous.pop(instrument_id, None)
                continue
            cycle = self._s0_cycle(position)
            live.add(cycle)
            mark = dict(marks).get(str(instrument_id))
            if mark is None or not self._s0_eligible(position, mark, source):
                self._s0_previous.pop(instrument_id, None)
                continue
            previous = self._s0_previous.get(instrument_id)
            self._s0_previous[instrument_id] = (cycle, dd)
            if cycle in self._s0_claimed or previous is None or previous[0] != cycle or not previous[1] < D('.25') <= dd:
                continue
            pnl = position.unrealized_pnl(self.cache.instrument(instrument_id).make_price(mark)).as_decimal()
            if pnl >= 0:
                continue
            instrument = self.cache.instrument(instrument_id)
            step = instrument.size_increment.as_decimal()
            held = position.quantity.as_decimal()
            reduction = (held*fraction//step)*step
            self._s0_claimed.add(cycle)  # Before cancellation/submission: callbacks may be synchronous.
            owner = dict(cycle=cycle, instrument_id=instrument_id, target=held-reduction,
                         source=source, receipt=receipt, epoch=epoch, account_ns=account_ns,
                         orders=set(), phase='CANCEL', episode_id=self._domain.episode.id)
            self.s0_management_audit.append(dict(event='CLAIM' if reduction > 0 else 'LOT_SKIP', cycle=list(cycle), source_ns=str(source), receipt_ns=str(receipt), fill_epoch=epoch, account_ns=str(account_ns), dd=str(dd), native_pnl=str(pnl), held=str(held), target=str(owner['target']), fraction=str(fraction)))
            if reduction <= 0:
                continue
            self._s0_targets[instrument_id] = owner
            self._discard_queued_intents(lambda i: self._s0_intent_asset(i, instrument_id))
            for order in list(self.cache.orders_open()):
                if order.instrument_id == instrument_id:
                    self.cancel_order(order)
        self._s0_claimed.intersection_update(live | {o['cycle'] for o in self._s0_orders.values()})

    def _s0_on_quote(self, tick):
        if self.config.research_s0_management_fraction is None:
            return False
        owner = self._s0_targets.get(tick.instrument_id)
        if owner is None:
            return False
        position = self._s0_position(tick.instrument_id)
        if self._s0_emergency() or position is None or self._s0_cycle(position) != owner['cycle']:
            self._s0_finish(owner, 'PREEMPTED', tick.ts_event, restore=False)
            return False
        # Queued native exits must own handoff even while a cancel ACK/child is pending.
        if any(self._s0_intent_asset(i, tick.instrument_id) for i, _, _ in self._queued_intents):
            self._s0_finish(owner, 'PRIORITY_OR_BUSY', tick.ts_event, restore=False)
            return False
        if owner['orders']:
            return True
        if tick.ts_event < owner['receipt'] or owner['source'] >= owner['receipt']:
            return True
        if any(o.instrument_id == tick.instrument_id for o in self.cache.orders_open()) or any(o.instrument_id == tick.instrument_id for o in self.cache.orders_inflight()):
            return True
        # Ordinary newly queued exits own priority; do not postpone a missed crossing.
        mark = tick.bid_price.as_decimal() if position.is_long else tick.ask_price.as_decimal()
        if not self._s0_eligible(position, mark, tick.ts_event):
            self._s0_finish(owner, 'PRIORITY_OR_BUSY', tick.ts_event, restore=False)
            return False
        instrument = self.cache.instrument(tick.instrument_id)
        step = instrument.size_increment.as_decimal()
        quantity = (max(D(0), position.quantity.as_decimal()-owner['target'])//step)*step
        if quantity <= 0:
            self._s0_finish(owner, 'TARGET_ALREADY_REACHED', tick.ts_event)
            return False
        order = self.order_factory.market(tick.instrument_id, OrderSide.SELL if position.is_long else OrderSide.BUY, instrument.make_qty(quantity), time_in_force=TimeInForce.IOC, reduce_only=True)
        oid = str(order.client_order_id)
        owner['phase'] = 'SUBMIT'
        owner['orders'].add(oid)
        self._s0_orders[oid] = owner
        if not self._record_submission(order, 's0:'+oid, 's0_management', 'PROTECTIVE_REDUCTION', 'S0_FRESH_DD25', None):
            self._s0_terminal(oid, tick.ts_event, 'LOCAL_DENIED')
            return True
        self.s0_management_audit.append(dict(event='SUBMIT', cycle=list(owner['cycle']), order_id=oid, source_ns=str(owner['source']), receipt_ns=str(owner['receipt']), quote_ns=str(tick.ts_event), quantity=str(quantity), executable_price=str(mark)))
        self.submit_order(order)
        return True

    def _s0_fill(self, event):
        owner = self._s0_orders[str(event.client_order_id)]
        ep = self._domain.episode
        current = self._s0_position(event.instrument_id)
        same_cycle = current is None or self._s0_cycle(current) == owner['cycle']
        if ep is not None and ep.id == owner['episode_id'] and same_cycle:
            if event.instrument_id == self.config.btc_id:
                ep.btc_open_qty = max(0., ep.btc_open_qty-float(event.last_qty))
            else:
                ep.sol_qty = max(0., ep.sol_qty-float(event.last_qty))
                # Retain consumed add notional and rights; protective fills earn no TP rights.
        self.s0_management_audit.append(dict(event='FILL', cycle=list(owner['cycle']), order_id=str(event.client_order_id), fill_ns=str(event.ts_event), quantity=str(event.last_qty), price=str(event.last_px), commission=str(event.commission)))
        order = self.cache.order(event.client_order_id)
        if order is not None and order.is_closed:
            self._terminal_submission(str(event.client_order_id))
            self._s0_terminal(str(event.client_order_id), event.ts_event, 'FILLED')

    def _s0_terminal(self, oid, timestamp, reason):
        owner = self._s0_orders.pop(oid, None)
        if owner is None:
            return
        owner['orders'].discard(oid)
        self._s0_finish(owner, reason, timestamp)

    def _s0_abort(self, reason):
        for owner in list(self._s0_targets.values()):
            self._s0_finish(owner, reason, self.clock.timestamp_ns(), restore=False)
        self._s0_previous.clear()

    def _s0_finish(self, owner, reason, timestamp, *, restore=True):
        if self._s0_targets.get(owner['instrument_id']) is not owner:
            return
        self._s0_targets.pop(owner['instrument_id'], None)
        if owner['orders']:
            for oid in list(owner['orders']):
                from nautilus_trader.model.identifiers import ClientOrderId
                order = self.cache.order(ClientOrderId(oid))
                if order is not None and not order.is_closed:
                    self.cancel_order(order)
        self._s0_previous.pop(owner['instrument_id'], None)
        self.s0_management_audit.append(dict(event='TERMINAL', cycle=list(owner['cycle']), timestamp_ns=str(timestamp), reason=reason))
        position = self._s0_position(owner['instrument_id'])
        if restore and not self._s0_emergency() and position is not None and self._s0_cycle(position) == owner['cycle'] and owner['instrument_id'] == self.config.btc_id:
            self._queue_confirmed_btc_targets(None, len(self._bars)-1, timestamp)
