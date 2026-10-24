"""Default-off native paired exit owner; no fill, funding or cash simulator.

All obligations derive from native cache positions. A submitted trim earns zero
capacity. The two caps are absolute quantities, never fractional cut counters.
"""
from dataclasses import dataclass, field
from decimal import Decimal as D, ROUND_CEILING, ROUND_FLOOR
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.identifiers import ClientOrderId

MINUTE = 60_000_000_000


def floor_lot(value, lot):
    if not value.is_finite() or value < 0 or lot <= 0:
        raise ValueError("PAIRED_INVALID_QUANTITY")
    return (value / lot).to_integral_value(rounding=ROUND_FLOOR) * lot


def sol_prices(p0, atr, side, tick):
    if side not in (-1, 1) or any(not x.is_finite() or x <= 0 for x in (p0, atr, tick)):
        raise ValueError("PAIRED_INVALID_PRICE_INPUT")
    rounding = ROUND_CEILING if side == 1 else ROUND_FLOOR
    outward = lambda x: (x / tick).to_integral_value(rounding=rounding) * tick
    fee = D(".00055")
    breakeven = p0 * (1 + fee) / (1 - fee) if side == 1 else p0 * (1 - fee) / (1 + fee)
    fee_floor = outward(breakeven) + side * tick
    previous = p0
    prices = []
    for distance in (D(".5"), D(1), D(2)):
        choices = (outward(p0 + side * distance * atr), fee_floor, previous + side * tick)
        price = max(choices) if side == 1 else min(choices)
        if price <= 0 or side * (price - previous) <= 0:
            raise ValueError("PAIRED_INVALID_TARGET")
        prices.append(price); previous = price
    stop_rounding = ROUND_FLOOR if side == 1 else ROUND_CEILING
    stop = ((p0 - side * atr) / tick).to_integral_value(rounding=stop_rounding) * tick
    if stop <= 0 or side * (p0 - stop) <= 0:
        raise ValueError("PAIRED_INVALID_STOP")
    return tuple(prices), stop


def sol_allocations(held_lots, consumed):
    rights = [i for i in range(3) if i not in consumed]
    if not rights:
        if held_lots:
            raise ValueError("PAIRED_INVENTORY_WITHOUT_TP_RIGHTS")
        return {}
    weights = (D(".25"), D(".25"), D(".50"))
    denominator = sum(weights[i] for i in rights)
    assigned, result = 0, {}
    for i in rights:
        result[i] = held_lots - assigned if i == rights[-1] else int(D(held_lots) * weights[i] / denominator)
        assigned += result[i]
    return result


def exact_lots(value, lot):
    """Exact native Decimal lattice membership, independent of Decimal context."""
    if not isinstance(value, D) or not isinstance(lot, D) or not value.is_finite() or not lot.is_finite() or value < 0 or lot <= 0:
        raise ValueError("PAIRED_UNKNOWN_NATIVE_LOTS")
    vn, vd = value.as_integer_ratio(); ln, ld = lot.as_integer_ratio()
    count, remainder = divmod(vn * ld, vd * ln)
    if remainder:
        raise ValueError("PAIRED_UNKNOWN_NONINTEGRAL_NATIVE_LOTS")
    return count


@dataclass
class PairedCaps:
    qref: D
    k: D  # Display only; never an input to cap arithmetic.
    btc_lot: D
    sol_lot: D
    intended_sol: D
    bmax: D = field(init=False)
    u: int = field(init=False)
    v: int = field(init=False)
    initialized: bool = False

    def __post_init__(self):
        self.u = exact_lots(self.intended_sol, self.sol_lot)
        self.v = exact_lots(self.qref, self.btc_lot)
        if not self.u or not self.v:
            raise ValueError("PAIRED_INVALID_RATIO")
        self.bmax = self.qref

    def coverage(self, actual_sol):
        return D(self.v * exact_lots(actual_sol, self.sol_lot) // self.u) * self.btc_lot

    def entry_terminal(self, actual_sol):
        self.bmax = min(self.bmax, self.coverage(actual_sol))
        self.initialized = True

    def reconcile(self, actual_btc, actual_sol, *, sol_reduced, btc_reduced, active_risk):
        exact_lots(actual_btc, self.btc_lot)
        exact_lots(actual_sol, self.sol_lot)
        if self.initialized and sol_reduced and active_risk:
            self.bmax = min(self.bmax, self.coverage(actual_sol))
        if btc_reduced:
            self.bmax = min(self.bmax, actual_btc)
        return max(D(0), actual_btc - self.bmax), max(D(0), actual_sol - self.solmax)

    @property
    def solmax(self):
        numerator = self.u * exact_lots(self.bmax, self.btc_lot)
        return D((numerator + self.v - 1) // self.v) * self.sol_lot


class PairedPrefixResearch:
    def _pair_init(self):
        self._pair = None
        self._pair_orders = {}
        self._pair_used = set()
        self.paired_prefix_audit = []
        self._pair_last_quote = {}
        self._pair_seen_fills = set()
        self._pair_feed_index = 0
        self._pair_failures = []
        if self.config.research_paired_prefix not in (None, "B2", "B2_F0"):
            raise ValueError("PAIRED_INVALID_VARIANT")
        if self.config.research_paired_prefix and not (self.config.research_btc_real_u and self.config.research_btc_q_mode == "CLEAN_Q" and self.config.research_sol_off):
            raise ValueError("PAIRED_REQUIRES_R3_CLEAN_Q_SOL_OFF")

    def _pair_log(self, event, ns, **values):
        self.paired_prefix_audit.append(dict(event=event, timestamp_ns=str(ns),
            **{k: str(v) if isinstance(v, D) else v for k, v in values.items()}))

    def _pair_position(self, instrument_id):
        positions = [p for p in self.cache.positions_open() if p.instrument_id == instrument_id]
        if len(positions) > 1:
            raise ValueError("PAIRED_UNKNOWN_MULTIPLE_NATIVE_POSITIONS")
        return positions[0] if positions else None

    def _pair_qty(self, instrument_id):
        p = self._pair_position(instrument_id)
        return p.quantity.as_decimal() if p else D(0)

    def _pair_work(self, *, instrument=None, kinds=None):
        return [(oid, owner, self.cache.order(ClientOrderId(oid))) for oid, owner in self._pair_orders.items()
                if (instrument is None or owner["instrument"] == instrument) and
                (kinds is None or owner["kind"] in kinds) and
                (self.cache.order(ClientOrderId(oid)) is None or not self.cache.order(ClientOrderId(oid)).is_closed)]

    def _pair_cancel(self, work):
        for oid, owner, order in work:
            if order is not None and not order.is_closed and not order.is_pending_cancel:
                self.cancel_order(order)
        return bool(work)

    def _pair_fail(self, reason, ns):
        if reason not in self._pair_failures:
            self._pair_failures.append(reason)
            self._pair_log("QUALIFICATION_NO_GO", ns, reason=reason)
        if self._pair:
            self._pair["failed"] = True
            self._pair["risk"] = "UNKNOWN_RISK"
            self._pair["close_sol"] = True
            self._pair["caps"].bmax = D(0)
            self._pair_arm_btc_debt(ns)

    def _pair_no_increase(self):
        return bool(self.config.research_paired_prefix and self._pair)

    def _pair_btc_tp_paused(self):
        p = self._pair
        return bool(p and (self._pair_qty(self.config.btc_id) > p["caps"].bmax or
                           self._pair_work(instrument=self.config.btc_id)))

    def _pair_cancel_btc_increases(self, ns):
        self._discard_queued_intents(lambda i: i.action == "BTC_ENTRY")
        self._split_stop("PAIRED_MONOTONE_PARENT_CEILING")
        for order in self.cache.orders_open() + self.cache.orders_inflight():
            if order.instrument_id == self.config.btc_id and not order.is_reduce_only and not order.is_closed and not order.is_pending_cancel:
                self.cancel_order(order)

    def _pair_arm_btc_debt(self, ns):
        p = self._pair
        if p and self._pair_qty(self.config.btc_id) > p["caps"].bmax:
            if p["debt_since"] is None:
                p["debt_since"] = ns
                self._pair_log("ACTUAL_BTC_DEBT_OPEN", ns, actual_btc=self._pair_qty(self.config.btc_id), bmax=p["caps"].bmax)
            # Cancel at the actual causal fill/terminal timestamp, so ACK can
            # precede the next distinct executable BTC quote, not one quote later.
            work = [(oid, {}, self.cache.order(ClientOrderId(oid))) for oid, intent in self._pending_by_order.items()
                    if intent.action.startswith("BTC")]
            self._pair_cancel(work)

    def _pair_release_if_terminal(self, ns):
        p = self._pair
        if p and not self._pair_qty(self.config.btc_id) and not self._pair_qty(self.config.sol_id) and not self._pair_work() and not self.cache.orders_open() and not self.cache.orders_inflight():
            self._pair_log("PARENT_NATIVE_TERMINAL_FLAT", ns, parent=p["parent"])
            self._pair = None

    def _pair_start(self, signal, ns):
        if self._forced_close_reason or self._liquidating:
            return
        signal = signal.owner_row() if hasattr(signal, "owner_row") else signal
        ep = self._domain.episode
        position = self._pair_position(self.config.btc_id)
        if not ep or not position or ep.id in self._pair_used:
            return
        side = 1 if position.is_long else -1
        branch = "B2" if signal.get("B2_" + str(side)) else "F0" if self.config.research_paired_prefix == "B2_F0" and signal.get("F0_" + str(side)) else None
        if branch is None:
            return
        self._pair_used.add(ep.id)
        if not signal.get("valid"):
            self._pair_fail("UNHEDGEABLE_UNAVAILABLE_CAUSAL_FEATURE", ns)
            self._begin_forced_close("PAIRED_UNHEDGEABLE_CAUSAL_FEATURE")
            return
        if self._pair_qty(self.config.sol_id) or any(o.instrument_id == self.config.sol_id for o in self.cache.orders_open() + self.cache.orders_inflight()):
            self._pair_fail("UNKNOWN_UNRELATED_SOL_OWNERSHIP", ns)
            self._begin_forced_close("PAIRED_UNKNOWN_SOL_OWNERSHIP")
            return
        btc = self.cache.instrument(self.config.btc_id); sol = self.cache.instrument(self.config.sol_id)
        qref = position.quantity.as_decimal()
        quantity = floor_lot(D(str(signal["a"])) * qref * D(str(signal["PB"])) / D(str(signal["PS"])), sol.size_increment.as_decimal())
        k = quantity / qref if quantity > 0 else D(0)
        if not k:
            # Actual held position cannot be called protected by zero admission.
            self._pair_fail("UNHEDGEABLE_ZERO_INTENDED", ns)
            self._begin_forced_close("PAIRED_UNHEDGEABLE_ZERO_INTENDED")
            return
        try:
            caps = PairedCaps(qref, k, btc.size_increment.as_decimal(), sol.size_increment.as_decimal(), quantity)
        except ValueError as error:
            self._pair_fail(str(error), ns)
            self._begin_forced_close("PAIRED_UNKNOWN_NATIVE_LOTS")
            return
        self._pair = dict(parent=ep.id, side=side, branch=branch, signal_ns=ns,
            eligible_ns=ns + MINUTE, quantity=quantity, caps=caps,
            boundary=D(str(signal[("K_" + str(side)) if branch == "B2" else "O"])), atr=D(str(signal["ATR_SOL"])),
            risk="ACTIVE_RISK", first_fill_ns=None, deadline_ns=None, entry_terminal=False,
            entry_qty=D(0), entry_notional=D(0), p0=None, consumed=set(), signature=None,
            protection_since=None, debt_since=None, close_sol=False, failed=False,
            last_btc=qref, last_sol=D(0), entry_sent=False, generation=0, tp_lots={})
        self._pair_cancel_btc_increases(ns)
        self._pair_log("ACTIVATION_SELECTED", ns, parent=ep.id, branch=branch, qref=qref,
                       intended_sol=quantity, k=k, boundary=self._pair["boundary"], atr=self._pair["atr"])
        try:
            self._pair_valid_allocations(quantity, D(str(signal["PS"])))
        except ValueError as error:
            self._pair_fail(str(error), ns)

    def _pair_valid_allocations(self, held, p0):
        p = self._pair; inst = self.cache.instrument(self.config.sol_id)
        prices, stop = sol_prices(p0, p["atr"], -p["side"], inst.price_increment.as_decimal())
        lots = dict(p["tp_lots"]) if p["tp_lots"] else sol_allocations(int(held / inst.size_increment.as_decimal()), p["consumed"])
        for level, count in lots.items():
            q = count * inst.size_increment.as_decimal()
            if q <= 0 or (inst.min_quantity and q < inst.min_quantity.as_decimal()) or (inst.min_notional and q * min(prices[level], stop) < inst.min_notional.as_decimal()):
                raise ValueError("PAIRED_INVALID_NATIVE_TP_OR_STOP_ALLOCATION")
        return prices, stop, lots

    def _pair_submit(self, instrument, side, qty, kind, ns, *, price=None, stop=None, level=None):
        inst = self.cache.instrument(instrument)
        if kind == "ENTRY" and not self._tier_allows_increase(instrument, side, qty, ns):
            self._pair_fail("NATIVE_MARGIN_ENTRY_DENIED", ns)
            self._pair["entry_terminal"] = True
            self._pair["caps"].entry_terminal(D(0))
            return
        if qty <= 0 or floor_lot(qty, inst.size_increment.as_decimal()) != qty:
            self._pair_fail("UNEXECUTABLE_DUST", ns); return
        kw = dict(instrument_id=instrument, order_side=OrderSide.BUY if side == 1 else OrderSide.SELL,
                  quantity=inst.make_qty(qty), reduce_only=kind != "ENTRY")
        if stop is not None:
            # IOC is mandatory: GTC stock L1 synthesizes exhausted-book remainder.
            order = self.order_factory.stop_market(**kw, trigger_price=inst.make_price(stop), time_in_force=TimeInForce.IOC)
        elif price is not None:
            order = self.order_factory.limit(**kw, price=inst.make_price(price), time_in_force=TimeInForce.GTC)
        else:
            order = self.order_factory.market(**kw, time_in_force=TimeInForce.IOC)
        oid = str(order.client_order_id)
        self._pair_orders[oid] = dict(instrument=instrument, kind=kind, level=level, accepted=False,
            generation=self._pair["generation"], submit_ns=ns)
        if not self._record_submission(order, "paired:" + oid, self._pair["parent"],
                                       "PAIRED_" + kind, "PAIRED_" + kind, level):
            self._pair_fail("DURABLE_SUBMIT_DENIED", ns); return
        self._pair_log("SUBMIT", ns, order_id=oid, kind=kind, level=level, quantity=qty,
                       price=price, stop=stop, generation=self._pair["generation"])
        self.submit_order(order)

    def _pair_accept(self, event):
        o = self._pair_orders.get(str(event.client_order_id))
        if o and not o["accepted"]:
            o["accepted"] = True
            self._pair_log("ACCEPTED", event.ts_event, order_id=str(event.client_order_id), kind=o["kind"], level=o["level"])
            self._pair_protect(event.ts_event)

    def _pair_terminal(self, oid, ns, rejected=False):
        owner = self._pair_orders.get(oid)
        if owner is None:
            return False
        p = self._pair
        self._terminal_submission(oid)
        if p and owner["kind"] == "ENTRY" and not p["entry_terminal"]:
            p["entry_terminal"] = True
            try:
                p["caps"].entry_terminal(p["entry_qty"])
            except ValueError as error:
                self._pair_fail(str(error), ns)
            self._pair_log("ENTRY_TERMINAL_P0_FROZEN", ns, actual_sol=p["entry_qty"], p0=p["p0"], bmax=p["caps"].bmax)
            self._pair_arm_btc_debt(ns)
        if p and owner["kind"] == "STOP":
            order = self.cache.order(ClientOrderId(oid))
            if order is not None and order.filled_qty.as_decimal() > 0 and order.filled_qty.as_decimal() < order.quantity.as_decimal():
                self._pair_fail("PARTIAL_NATIVE_STOP", ns)
        if rejected and p:
            self._pair_fail("NATIVE_" + owner["kind"] + "_REJECTED", ns)
        if p and owner["kind"] in {"TP", "STOP"}:
            self._pair_protect(ns)
        self._pair_release_if_terminal(ns)
        return True

    def _pair_fill(self, event):
        oid = str(event.client_order_id); owner = self._pair_orders.get(oid)
        if owner is None:
            return False
        if str(event.trade_id) in self._pair_seen_fills:
            return True
        self._pair_seen_fills.add(str(event.trade_id))
        p = self._pair
        if p is None:
            raise ValueError("PAIRED_LATE_FILL_WITHOUT_OWNER")
        qty = event.last_qty.as_decimal(); px = event.last_px.as_decimal()
        if owner["kind"] == "ENTRY":
            step = self.cache.instrument(self.config.sol_id).size_increment.as_decimal()
            added = sol_allocations(int(qty / step), p["consumed"])
            for level, lots in added.items():
                p["tp_lots"][level] = p["tp_lots"].get(level, 0) + lots
            p["entry_qty"] += qty; p["entry_notional"] += qty * px
            if p["entry_terminal"]:
                p["close_sol"] = True
                self._pair_log("LATE_ENTRY_FILL_NO_REANCHOR", event.ts_event, frozen_p0=p["p0"])
            else:
                p["p0"] = p["entry_notional"] / p["entry_qty"]
            if p["first_fill_ns"] is None:
                p["first_fill_ns"] = event.ts_event
                p["deadline_ns"] = event.ts_event + (4 if p["branch"] == "B2" else 8) * 60 * MINUTE
            if self._pair_qty(self.config.btc_id) == 0 or p["close_sol"]:
                p["close_sol"] = True
        if owner["kind"] == "BTC_DEBT":
            ep = self._domain.episode
            if ep:
                ep.btc_open_qty = max(0., ep.btc_open_qty - float(qty))
                m = self._md_plans.get(ep.id)
                if m:
                    m["allocated_entry"] = None; m["signature"] = None
        if owner["instrument"] == self.config.sol_id and owner["kind"] != "ENTRY":
            step = self.cache.instrument(self.config.sol_id).size_increment.as_decimal()
            removed = int(qty / step)
            if owner["kind"] == "TP":
                level = owner["level"]
                p["tp_lots"][level] = max(0, p["tp_lots"].get(level, 0) - removed)
            else:
                old = dict(p["tp_lots"]); total = sum(old.values()); remaining = max(0, total - removed)
                levels = sorted(old); assigned = 0
                for level in levels:
                    count = remaining - assigned if level == levels[-1] else int(D(old[level]) * remaining / total) if total else 0
                    p["tp_lots"][level] = count; assigned += count
        order = self.cache.order(event.client_order_id)
        if owner["kind"] == "TP" and order is not None and order.status.name == "FILLED":
            p["consumed"].add(owner["level"])
            p["tp_lots"].pop(owner["level"], None)
        # Fill callbacks use pre-event risk, before completed quote invalidation.
        if owner["instrument"] == self.config.sol_id and owner["kind"] != "ENTRY" and p["caps"].initialized and p["risk"] != "INACTIVE_RISK":
            # Stock execution engine commits cache/account before strategy
            # fill delivery. Read that same actual native state, never pending relief.
            after = self._pair_qty(self.config.sol_id)
            try:
                p["caps"].reconcile(p["last_btc"], after, sol_reduced=True,
                                    btc_reduced=False, active_risk=True)
            except ValueError as error:
                self._pair_fail(str(error), event.ts_event)
        self._pair_arm_btc_debt(event.ts_event)
        self._pair_log("ACTUAL_FILL", event.ts_event, order_id=oid, kind=owner["kind"],
                       level=owner["level"], qty=qty, price=px, risk=p["risk"], bmax=p["caps"].bmax)
        if order is not None and order.is_closed:
            self._pair_terminal(oid, event.ts_event)
        return True

    def _pair_position_event(self, ns):
        if not self._pair:
            return
        p = self._pair
        btc = self._pair_qty(self.config.btc_id); sol = self._pair_qty(self.config.sol_id)
        try:
            p["caps"].reconcile(btc, sol, sol_reduced=sol < p["last_sol"],
                btc_reduced=btc < p["last_btc"], active_risk=p["risk"] != "INACTIVE_RISK")
        except ValueError as error:
            self._pair_fail(str(error), ns)
        p["last_btc"], p["last_sol"] = btc, sol
        if not btc:
            p["close_sol"] = True
            self._pair_cancel(self._pair_work(instrument=self.config.sol_id, kinds={"ENTRY", "TP", "STOP"}))
        self._pair_log("CACHE_POSITION", ns, btc=btc, sol=sol, bmax=p["caps"].bmax, solmax=p["caps"].solmax)
        self._pair_arm_btc_debt(ns)
        self._pair_protect(ns)
        self._md_reconcile(ns)
        self._pair_release_if_terminal(ns)

    def _pair_protect(self, ns):
        p = self._pair
        if p is None or p["p0"] is None:
            return
        held = self._pair_qty(self.config.sol_id)
        if not held or p["close_sol"]:
            return
        work = self._pair_work(instrument=self.config.sol_id, kinds={"TP", "STOP"})
        signature = (p["p0"], held, tuple(sorted(p["tp_lots"].items())))
        if signature != p["signature"]:
            p["protection_since"] = p["protection_since"] or ns
            if self._pair_cancel(work):
                return
            try:
                prices, stop, lots = self._pair_valid_allocations(held, p["p0"])
            except ValueError as error:
                self._pair_fail(str(error), ns); return
            p["generation"] += 1; p["signature"] = signature
            p["protection_since"] = p["protection_since"] or ns
            for level, count in lots.items():
                self._pair_submit(self.config.sol_id, p["side"], D(count) * self.cache.instrument(self.config.sol_id).size_increment.as_decimal(), "TP", ns, price=prices[level], level=level)
            self._pair_submit(self.config.sol_id, p["side"], held, "STOP", ns, stop=stop)
        work = self._pair_work(instrument=self.config.sol_id, kinds={"TP", "STOP"})
        required = 1 + 3 - len(p["consumed"])
        if len(work) == required and all(owner["accepted"] and order is not None and order.status.name in {"ACCEPTED", "PARTIALLY_FILLED", "TRIGGERED"} for _, owner, order in work):
            p["protection_since"] = None
        elif p["protection_since"] is None:
            p["protection_since"] = ns

    def _pair_quote(self, tick):
        if not self.config.research_paired_prefix:
            return
        ns = tick.ts_event
        self._pair_last_quote[tick.instrument_id] = tick
        if tick.instrument_id == self.config.btc_id:
            # Native matching/fill delivery precedes strategy quote callback.
            p = self._pair
            if p and not p["entry_sent"] and ns > p["signal_ns"] and p["side"] * (tick.bid_price.as_decimal() - p["boundary"]) >= 0:
                p["risk"] = "INACTIVE_RISK"; p["close_sol"] = True
                p["entry_sent"] = True; p["entry_terminal"] = True
                self._pair_log("ADMISSION_CANCELLED_ALREADY_INACTIVE", ns)
            if p and p["risk"] != "INACTIVE_RISK" and p["first_fill_ns"] is not None and ns > p["first_fill_ns"]:
                if p["side"] * (tick.bid_price.as_decimal() - p["boundary"]) >= 0 or ns >= p["deadline_ns"]:
                    p["risk"] = "INACTIVE_RISK"; p["close_sol"] = True
                    self._pair_log("RISK_INVALID_OR_EXPIRED", ns, btc_close=tick.bid_price.as_decimal())
            feed = self.config.research_paired_signal_rows
            while self._pair_feed_index < len(feed) and feed[self._pair_feed_index].decision_ns <= ns:
                signal = feed[self._pair_feed_index]; self._pair_feed_index += 1
                if signal.decision_ns == ns and self._pair is None:
                    self._pair_start(signal, ns)
        p = self._pair
        if p is None:
            return
        btc_quote = self._pair_last_quote.get(self.config.btc_id)
        if p["first_fill_ns"] is not None and (btc_quote is None or ns - btc_quote.ts_event > MINUTE):
            self._pair_fail("UNKNOWN_RISK_MISSING_FRESH_BTC_CLOSE", ns)
        self._pair_cancel_btc_increases(ns)
        if self._forced_close_reason or self._liquidating or self.terminal_lifecycle.get("lockout"):
            p["close_sol"] = True
            self._pair_cancel(self._pair_work())
            if p["debt_since"] is not None and ns > p["debt_since"] + MINUTE:
                self._pair_fail("TRIM_DEBT_OVERDUE_DURING_HIGHER_NATIVE_CLOSE", ns)
            self._pair_release_if_terminal(ns)
            return  # Existing native forced/terminal owner serializes all closure.
        btc = self._pair_qty(self.config.btc_id); sol = self._pair_qty(self.config.sol_id)
        if p["protection_since"] is not None and ns > p["protection_since"]:
            self._pair_fail("PROTECTION_OVERDUE_NEXT_QUOTE", ns)
        if p["debt_since"] is not None and ns > p["debt_since"] + MINUTE:
            self._pair_fail("TRIM_DEBT_OVERDUE", ns)
        if not p["entry_sent"] and ns >= p["eligible_ns"] and tick.instrument_id == self.config.sol_id:
            ep = self._domain.episode; pos = self._pair_position(self.config.btc_id)
            if not ep or ep.id != p["parent"] or not pos or pos.is_long != (p["side"] == 1) or btc != p["caps"].qref or sol or self._pair_work():
                self._pair_fail("UNKNOWN_CHANGED_POSITION", ns); p["entry_terminal"] = True
                p["caps"].entry_terminal(D(0))
            elif not p["failed"]:
                p["entry_sent"] = True
                self._pair_submit(self.config.sol_id, -p["side"], p["quantity"], "ENTRY", ns)
        if p["entry_sent"] and not p["entry_terminal"] and ns > p["eligible_ns"] + MINUTE:
            self._pair_fail("ENTRY_TERMINAL_TIMEOUT", ns)
            self._pair_cancel(self._pair_work(kinds={"ENTRY"}))
        if not btc:
            p["close_sol"] = True
        debt = max(D(0), btc - p["caps"].bmax)
        if debt:
            p["debt_since"] = p["debt_since"] or ns
            if tick.instrument_id == self.config.btc_id and not self._pair_work(instrument=self.config.btc_id):
                ordinary = [(oid, {}, self.cache.order(ClientOrderId(oid))) for oid, intent in self._pending_by_order.items() if intent.action.startswith("BTC")]
                if not self._pair_cancel(ordinary):
                    self._pair_submit(self.config.btc_id, -p["side"], debt, "BTC_DEBT", ns)
        else:
            p["debt_since"] = None
        excess = sol if p["close_sol"] else max(D(0), sol - p["caps"].solmax) if p["caps"].initialized else D(0)
        if excess:
            if not self._pair_cancel(self._pair_work(instrument=self.config.sol_id, kinds={"ENTRY", "TP", "STOP"})) and tick.instrument_id == self.config.sol_id and not self._pair_work(instrument=self.config.sol_id):
                self._pair_submit(self.config.sol_id, p["side"], excess, "SOL_CLOSE" if p["close_sol"] else "SOL_CAP", ns)
        else:
            self._pair_protect(ns)
        self._pair_release_if_terminal(ns)

    def _pair_report(self):
        return dict(events=self.paired_prefix_audit, failures=list(self._pair_failures),
                    open_owner=self._pair is not None, physical_budget_authority="EXTERNAL_SINGLE_SOURCE_RUN_LEDGER")
