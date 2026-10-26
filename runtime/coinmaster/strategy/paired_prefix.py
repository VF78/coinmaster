"""Default-off native paired exit owner; no fill, funding or cash simulator.

All obligations derive from native cache positions. A submitted trim earns zero
capacity. The two caps are absolute quantities, never fractional cut counters.
"""
from dataclasses import dataclass, field
from decimal import Decimal as D, ROUND_CEILING, ROUND_FLOOR
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.identifiers import ClientOrderId
from coinmaster.strategy.native_account_snapshot import native_account_snapshot

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
        self._pair_sol_events = set()
        self._pair_predecisions = []
        self._pair_observed_rights = {}
        self._pair_observed_marks = {}
        self._pair_predecision_counts = dict(checks=0,records=0,coalesced=0)
        self._pair_sol_boundary_counts = dict(checks=0,strict=0,unknown=0)
        self._pair_feed_index = 0
        self._pair_failures = []
        if self.config.research_paired_prefix not in (None, "B2", "B2_F0"):
            raise ValueError("PAIRED_INVALID_VARIANT")
        exact_a0 = self.config.research_a0_family == "R2_A0_V1" and self.config.research_paired_prefix in (None, "B2_F0") and self.config.research_btc_real_u and self.config.research_btc_q_mode == "LEGACY_Q_CONTROL" and self.config.research_sol_off
        if self.config.research_a0_family is not None and not exact_a0:
            raise ValueError("A0_EXACT_R2_FAMILY_REQUIRED")
        if self.config.research_a0_original_second and (not exact_a0 or self.config.research_paired_prefix != "B2_F0"):
            raise ValueError("A0_EXACT_R2_FAMILY_REQUIRED")
        if self.config.research_paired_prefix and not exact_a0 and not (self.config.research_btc_real_u and self.config.research_btc_q_mode == "CLEAN_Q" and self.config.research_sol_off):
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
        return bool(self.config.research_paired_prefix and self._pair and not getattr(self, "_a0_submitting", False))

    def _pair_btc_tp_paused(self):
        p = self._pair
        return bool(p and (self._pair_qty(self.config.btc_id) > p["caps"].bmax or
                           self._pair_work(instrument=self.config.btc_id)))

    def _pair_cancel_btc_increases(self, ns):
        self._pair_observe_lock(ns)
        self._a0_lock(ns)
        self._discard_queued_intents(lambda i: i.action == "BTC_ENTRY")
        self._split_stop("PAIRED_MONOTONE_PARENT_CEILING")
        for order in self.cache.orders_open() + self.cache.orders_inflight():
            if order.instrument_id == self.config.btc_id and not order.is_reduce_only and not order.is_closed and not order.is_pending_cancel and not self._a0_keep_order(order):
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
                    if intent.action == "BTC_ENTRY" or (not self._tp_enabled() and intent.action.startswith("BTC"))]
            self._pair_cancel(work)
        if self._tp_enabled(): self._tp_debt_observe(ns, "NATIVE_INVENTORY_OR_TERMINAL")

    def _pair_release_if_terminal(self, ns):
        p = self._pair
        if p and not self._pair_qty(self.config.btc_id) and not self._pair_qty(self.config.sol_id) and not self._pair_work() and not self.cache.orders_open() and not self.cache.orders_inflight() and not (getattr(self.config, "research_sol_standing_protection", False) and any(o.get("pending") is not None and o.get("parent") == p["parent"] for o in self._pair_orders.values())):
            self._pair_predecision(ns,"PARENT_NATIVE_TERMINAL")
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
        if getattr(self.config,"research_btc_trim_control",False):
            self._pair_trim_start(signal,ep,position,branch,ns)
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
            generation=self._pair["generation"], submit_ns=ns, parent=self._pair["parent"],
            initial_oid=oid, initialized_event_id=str(order.init_event.id), pending=None, ack=None, command_sequence=0)
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
        if owner["kind"]=="STOP" and getattr(self.config,"research_sol_standing_protection",False):
            # A partial STOP callback can precede IOC terminal cancellation.
            # Any genuine STOP fill closes protection ownership immediately.
            p["close_sol"]=True
            self._pair_log("SOL_STOP_FILL_CLOSING_BARRIER",event.ts_event,order_id=oid,trade_id=str(event.trade_id),qty=qty)
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
                    if self._tp_enabled():
                        witness=self._tp_book()
                        if witness != getattr(self,"_tp_debt_witness",None): raise ValueError("STANDING_INTERPOSED_BTC_INPUT_BEFORE_DEBT_FILL")
                        m["standing_inventory_dirty"]=True
                        self._tp_debt_observe(event.ts_event, "BTC_DEBT_ACTUAL_FILL")
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
        elif getattr(self.config, "research_sol_standing_protection", False):
            self._pair_protect(event.ts_event)
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
        if getattr(self.config, "research_sol_standing_protection", False):
            return self._pair_sol_protect(ns)
        return self._pair_legacy_protect(ns)

    def _pair_legacy_protect(self, ns):
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
            if p and p.get("role")=="BTC_TRIM":
                self._pair_trim_quote(tick)
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
        standing_safe = None
        debt_deadline_since = p.get("standing_safe_since") if self._tp_enabled() else p["debt_since"]
        if self._tp_enabled() and p["debt_since"] is not None and tick.instrument_id == self.config.btc_id:
            standing_safe = self._tp_debt_safe(ns)
            debt_deadline_since = self._tp_debt_clock(ns, standing_safe)
        if debt_deadline_since is not None and ns > debt_deadline_since + MINUTE and not (self._tp_enabled() and p.get("standing_debt_deferred")):
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
                ordinary = [(oid, {}, self.cache.order(ClientOrderId(oid))) for oid, intent in self._pending_by_order.items() if intent.action == "BTC_ENTRY" or (not self._tp_enabled() and intent.action.startswith("BTC"))]
                safe = not self._tp_enabled() or standing_safe is True
                p["standing_debt_deferred"] = not safe
                if safe and not self._pair_cancel(ordinary):
                    self._pair_submit(self.config.btc_id, -p["side"], debt, "BTC_DEBT", ns)
        else:
            p["debt_since"] = None
            p["standing_debt_deferred"] = False
            p["standing_safe_since"] = None
        excess = sol if p["close_sol"] else max(D(0), sol - p["caps"].solmax) if p["caps"].initialized else D(0)
        if excess:
            if not self._pair_cancel(self._pair_work(instrument=self.config.sol_id, kinds={"ENTRY", "TP", "STOP"})) and tick.instrument_id == self.config.sol_id and not self._pair_work(instrument=self.config.sol_id):
                self._pair_submit(self.config.sol_id, p["side"], excess, "SOL_CLOSE" if p["close_sol"] else "SOL_CAP", ns)
        else:
            self._pair_protect(ns)
        self._pair_release_if_terminal(ns)

    def _pair_report(self):
        return dict(control_role="BTC_TRIM"if getattr(self.config,"research_btc_trim_control",False)else"A0_FIXED"if getattr(self.config,"research_sol_standing_protection",False)and self._a0_enabled()else"C0_FIXED"if getattr(self.config,"research_sol_standing_protection",False)else"LEGACY_OR_OFF",
                    events=self.paired_prefix_audit, predecision_records=self._pair_predecisions,
                    predecision_coverage=dict(parent_count=len(self._pair_observed_rights),
                        parents=[dict(parent=k,risk_off_ns=v["off_ns"],first_off60_quote_observed=v.get("off60_recorded",False),
                            original_right_lock_eligible=v["lock_eligible"],original_second_orders=list(v.get("original_second_orders",())))
                            for k,v in self._pair_observed_rights.items()],
                        counts=self._pair_predecision_counts,account_capture_complete=self._pair_predecision_counts.get("capture_errors",0)==0,
                        incomplete_capture_blocks_financial_coverage=self._pair_predecision_counts.get("capture_errors",0)>0,truncated=False),
                    sol_boundary_counts=self._pair_sol_boundary_counts, failures=list(self._pair_failures),
                    open_owner=self._pair is not None, physical_budget_authority="EXTERNAL_SINGLE_SOURCE_RUN_LEDGER")


    def _pair_sol_native_event(self, event, route):
        """Typed/generic routes share actual UUID dedup; public return is no ACK."""
        if not getattr(self.config, "research_sol_standing_protection", False):
            return
        oid = str(event.client_order_id)
        owner = self._pair_orders.get(oid)
        if not owner or owner["instrument"] != self.config.sol_id or owner["kind"] not in {"TP", "STOP"}:
            return
        event_id = getattr(event, "id", None)
        if event_id is None:
            self._pair_fail("SOL_UNKNOWN_NATIVE_EVENT_ID", event.ts_event)
            return
        key = str(event_id)
        if key in self._pair_sol_events:
            return
        self._pair_sol_events.add(key)
        name = type(event).__name__
        order = self.cache.order(event.client_order_id)
        if name == "OrderInitialized":
            if key != owner["initialized_event_id"] or event.strategy_id != self.id or event.instrument_id != self.config.sol_id:
                self._pair_fail("SOL_UNKNOWN_PRE_CACHE_INITIALIZATION", event.ts_event)
            return
        if (order is None or event.strategy_id != self.id or event.instrument_id != self.config.sol_id
                or not any(str(item.id) == key for item in order.events)):
            self._pair_fail("SOL_NATIVE_EVENT_OWNERSHIP_OR_HISTORY_UNKNOWN", event.ts_event)
            return
        self._pair_log("SOL_NATIVE_EVENT", event.ts_event, order_id=oid,
            native_event_id=key, event_type=name, route=route,
            observed_ns=self.clock.timestamp_ns(), status=None if order is None else order.status.name)
        if name not in {"OrderUpdated", "OrderModifyRejected"}:
            return
        pending = owner.get("pending")
        if pending is None:
            self._pair_fail("SOL_UNOWNED_MODIFY_ACK", event.ts_event)
            return
        owner["pending"] = None
        if name == "OrderModifyRejected":
            owner["ack"] = None
            owner["rejected_desired"] = pending["desired"]
            self._pair_log("SOL_MODIFY_REJECTED", event.ts_event, order_id=oid,
                sequence=pending["sequence"], reason=str(event.reason))
        elif order is None or not self._pair_sol_payload_matches(order, pending["payload"]):
            owner["ack"] = None
            self._pair_fail("SOL_MODIFY_ACK_PAYLOAD_UNKNOWN", event.ts_event)
        else:
            owner["ack"] = pending["payload"]
            owner.pop("rejected_desired", None)
            self._pair_log("SOL_LATEST_MODIFY_ACK", event.ts_event, order_id=oid,
                sequence=pending["sequence"], native_event_id=key, generation=pending["generation"])
        self._pair_protect(event.ts_event)

    @staticmethod
    def _pair_sol_payload_matches(order, payload):
        total, price, trigger = payload
        return (order.quantity.as_decimal() == total
            and (price is None or order.price.as_decimal() == price)
            and (trigger is None or order.trigger_price.as_decimal() == trigger))

    def _pair_sol_protect(self, ns):
        p = self._pair
        if p is None or p["p0"] is None or p.get("sol_reconciling"):
            return
        held = self._pair_qty(self.config.sol_id)
        if not held or p["close_sol"]:
            # Keep owner registries until native cancellation/terminal is observed.
            if not held:
                p["protection_since"] = None
                self._pair_cancel(self._pair_work(instrument=self.config.sol_id, kinds={"TP", "STOP"}))
            return
        p["sol_reconciling"] = True
        try:
            inst = self.cache.instrument(self.config.sol_id)
            step = inst.size_increment.as_decimal()
            prices, stop = sol_prices(p["p0"], p["atr"], -p["side"], inst.price_increment.as_decimal())
            lots = dict(p["tp_lots"])
            if sum(lots.values())*step != held:
                # Native cache can already contain the next same-stack fill.
                # No fabricated entitlement/quantity; wait for its real callback.
                p["protection_since"] = p["protection_since"] if p["protection_since"] is not None else ns
                return
            if not any(lots.values()):
                raise ValueError("PAIRED_INVENTORY_WITHOUT_TP_RIGHTS")
            for level, count in lots.items():
                q = D(count)*step
                if q < 0 or (q and ((inst.min_quantity and q < inst.min_quantity.as_decimal())
                    or (inst.min_notional and q*min(prices[level], stop) < inst.min_notional.as_decimal()))):
                    raise ValueError("PAIRED_INVALID_NATIVE_TP_OR_STOP_ALLOCATION")
            prior_protection=any(o.get("parent")==p["parent"]and o["kind"]in {"TP","STOP"}for o in self._pair_orders.values())
            if not prior_protection and not p["consumed"]and {level for level,count in lots.items()if count>0}!={0,1,2}:
                raise ValueError("PAIRED_INVALID_NATIVE_TP_OR_STOP_ALLOCATION")
            desired = {("TP", level): (D(count)*step, prices[level], None)
                       for level, count in lots.items() if count > 0}
            desired[("STOP", None)] = (held, None, stop)
            signature = (p["p0"], held, tuple(sorted(p["tp_lots"].items())))
            if signature != p["signature"]:
                p["generation"] += 1
                p["signature"] = signature
                p["protection_since"] = p["protection_since"] if p["protection_since"] is not None else ns
            work = self._pair_work(instrument=self.config.sol_id, kinds={"TP", "STOP"})
            indexed = {}
            for oid, owner, order in work:
                key = owner["kind"], owner["level"]
                if key in indexed or owner.get("parent") != p["parent"] or order is None or order.strategy_id != self.id or order.instrument_id != self.config.sol_id or not order.is_reduce_only or order.side != (OrderSide.BUY if p["side"]==1 else OrderSide.SELL):
                    raise ValueError("SOL_UNKNOWN_NATIVE_ORDER_OWNERSHIP")
                indexed[key] = oid, owner, order
                if key not in desired:
                    self._pair_cancel([(oid, owner, order)])
            for key, target in desired.items():
                leaves, price, trigger = target
                if key not in indexed:
                    # A consumed/terminal TP cannot be resurrected from stale rights.
                    history = [(oid, owner) for oid, owner in self._pair_orders.items()
                        if owner.get("parent") == p["parent"] and (owner["kind"], owner["level"]) == key]
                    if history:
                        raise ValueError("SOL_TERMINAL_PROTECTION_WITH_POSITIVE_RIGHT")
                    self._pair_submit(self.config.sol_id, p["side"], leaves, key[0], ns,
                        price=price, stop=trigger, level=key[1])
                    continue
                oid, owner, order = indexed[key]
                total = order.filled_qty.as_decimal() + leaves
                payload = total, price, trigger
                owner["desired"] = leaves, price, trigger
                if owner.get("pending") is not None or order.is_pending_cancel or order.is_closed:
                    continue
                if self._pair_sol_payload_matches(order, payload):
                    if owner["accepted"] and order.status.name in {"ACCEPTED", "PARTIALLY_FILLED", "TRIGGERED"}:
                        owner["ack"] = payload
                    continue
                if owner.get("rejected_desired") == owner["desired"]:
                    continue  # No retry storm; original protection clock remains open.
                if not owner["accepted"] or order.status.name not in {"ACCEPTED", "PARTIALLY_FILLED", "TRIGGERED"}:
                    continue
                owner["command_sequence"] += 1
                pending = dict(sequence=owner["command_sequence"], generation=p["generation"],
                    desired=owner["desired"], payload=payload, sent_ns=self.clock.timestamp_ns())
                owner["pending"] = pending  # Install before reentrant native callback.
                owner["ack"] = None
                self._pair_log("SOL_MODIFY_SUBMIT", ns, order_id=oid, kind=key[0], level=key[1],
                    sequence=pending["sequence"], generation=p["generation"], total=total,
                    filled=order.filled_qty.as_decimal(), desired_leaves=leaves)
                kwargs = dict(quantity=inst.make_qty(total))
                if price is not None and order.price.as_decimal() != price:
                    kwargs["price"] = inst.make_price(price)
                if trigger is not None and order.trigger_price.as_decimal() != trigger:
                    kwargs["trigger_price"] = inst.make_price(trigger)
                self.modify_order(order, **kwargs)
                self._pair_log("SOL_PUBLIC_MODIFY_RETURN", ns, order_id=oid, sequence=pending["sequence"],
                    status=order.status.name, pending=owner.get("pending") is not None)
            work = self._pair_work(instrument=self.config.sol_id, kinds={"TP", "STOP"})
            exact = len(work) == len(desired)
            for oid, owner, order in work:
                target = desired.get((owner["kind"], owner["level"]))
                exact = exact and target is not None and order is not None
                if target is None or order is None:
                    continue
                leaves, price, trigger = target
                payload = order.filled_qty.as_decimal() + leaves, price, trigger
                exact = (exact and owner["accepted"] and owner.get("pending") is None
                    and order.status.name in {"ACCEPTED", "PARTIALLY_FILLED", "TRIGGERED"}
                    and order.leaves_qty.as_decimal() == leaves and self._pair_sol_payload_matches(order, payload))
            if exact:
                p["protection_since"] = None
            elif p["protection_since"] is None:
                p["protection_since"] = ns
        except ValueError as error:
            self._pair_fail(str(error), ns)
        finally:
            p["sol_reconciling"] = False

    def _pair_observe_lock(self, ns):
        """Independent shadow record only: never create m[a0] or grant a right."""
        if not self.config.research_paired_prefix or not self._pair or not self._split_parent:
            return
        p, pair = self._split_parent, self._pair
        if p["episode_id"] != pair["parent"] or p["episode_id"] in self._pair_observed_rights:
            return
        m = self._md_plans.get(p["episode_id"], {})
        second = [oid for oid, role in m.get("entry_orders", {}).items() if role == "SECOND"]
        inst = self.cache.instrument(self.config.btc_id)
        tick = inst.price_increment.as_decimal()
        if m.get("p0") is None:
            price = None
        else:
            raw = m["p0"] * (1 - self.config.research_btc_split_discount * p["side"])
            price = (raw / tick).to_integral_value(rounding=ROUND_FLOOR if p["side"] == 1 else ROUND_CEILING) * tick
        self._pair_observed_rights[p["episode_id"]] = dict(lock_ns=ns,
            original_second=p["quantity"]-p["first_quantity"], first_terminal=m.get("first_filled"),
            price=price, old_orders=tuple(m.get("entry_orders", {})), off_ns=None, last_record=None,
            lock_eligible=(p.get("stop_reason") in (None,"PAIRED_MONOTONE_PARENT_CEILING")
                and not m.get("touched") and m.get("first_done",False) and m.get("p0")is not None
                and any((o:=self.cache.order(ClientOrderId(oid)))is None or not o.is_closed for oid in second)),
            locked_cap=None,off60_recorded=False,original_second_orders=tuple(second))
        self._pair_predecision(ns, "RISK_CANCEL")

    def _pair_predecision(self, ns, reason, tick=None):
        if not self.config.research_paired_prefix or not self._pair:
            return
        pair = self._pair
        a = self._pair_observed_rights.get(pair["parent"])
        if a is None:
            return
        m = self._md_plans.get(pair["parent"], {})
        if pair["risk"] == "INACTIVE_RISK" and a["off_ns"] is None:
            a["off_ns"] = ns
            reason = "RISK_OFF"
        if tick is not None and tick.instrument_id != self.config.btc_id:
            return
        counts=getattr(self,"_pair_predecision_counts",None)
        if counts is None:self._pair_predecision_counts=counts=dict(checks=0,records=0,coalesced=0)
        counts["checks"]+=1
        first_ready=(tick is not None and a["off_ns"]is not None and ns>=a["off_ns"]+MINUTE and not a.get("off60_recorded",False))
        if first_ready:
            reason="FIRST_BTC_QUOTE_AFTER_RISK_OFF_PLUS60";a["off60_recorded"]=True
        def order_row(oid):
            o = self.cache.order(ClientOrderId(oid))
            return dict(order_id=oid, status="UNKNOWN" if o is None else o.status.name,
                filled="UNKNOWN" if o is None else str(o.filled_qty),
                leaves="UNKNOWN" if o is None else str(o.leaves_qty),
                generation=m.get("order_generation", {}).get(oid, "UNKNOWN"))
        account_error=None
        try:account=self.cache.account_for_venue(self.config.btc_id.venue)
        except Exception as exc:
            account=None;account_error=dict(field="cache.account_for_venue",type=type(exc).__name__,message=str(exc))
        account_facts=native_account_snapshot(account,(self.config.btc_id,self.config.sol_id))
        if account_error:account_facts["errors"].append(account_error)
        if not account_facts["complete"]:counts["capture_errors"]=counts.get("capture_errors",0)+1
        native_margin={}
        for instrument in(self.config.btc_id,self.config.sol_id):
            values=account_facts["instruments"].get(str(instrument),{})
            native_margin[str(instrument)]={name:(value.get("text",value.get("status","UNKNOWN"))if isinstance(value,dict)else value)
                for name in("margin_init","margin_maint")for value in(values.get(name,"UNKNOWN"),)}
        quote = self._pair_last_quote.get(self.config.btc_id) if tick is None else tick
        marks = {};margin_fact_reads={}
        policy = self.config.margin_policy
        # Public margin_for gives current policy validity; no hypothetical order/credit.
        for instrument in (self.config.btc_id, self.config.sol_id):
            margin_fact_reads[str(instrument)]=callable(getattr(policy,"margin_for",None))
            try:
                _, _, mark = policy.margin_for(instrument, self._pair_qty(instrument), ns)
                observed = self._pair_observed_marks.get(instrument)
                marks[str(instrument)] = dict(price=str(mark),
                    age_ns="UNKNOWN" if observed is None else str(ns-observed[1]),
                    mark_ns="UNKNOWN" if observed is None else str(observed[1]), policy_current=True)
            except (ValueError, AttributeError):
                marks[str(instrument)] = dict(price="UNKNOWN", age_ns="UNKNOWN", policy_current=False)
        held = self._pair_qty(self.config.btc_id)
        remaining = None if m.get("second_filled") is None else max(D(0), a["original_second"]-m["second_filled"])
        book="UNKNOWN"
        if tick is not None and self.config.research_native_book is not None:
            try:book=self.config.research_native_book.matching(tick.instrument_id)
            except ValueError:pass
        row = dict(reason=reason, phase="CAUSE_"+reason if tick is None else"AFTER_PAIR_RISK_AND_MD_RECONCILE_BEFORE_A0_CHECK",
            native_input_identity="UNKNOWN"if tick is None else str(id(tick)),
            native_event_uuid="UNKNOWN_NO_EVENT_UUID_IN_CAUSE"if tick is None else"NOT_PROVIDED_BY_NATIVE_QUOTE_TICK",
            instrument="UNKNOWN"if tick is None else str(tick.instrument_id),book=book,
            parent=pair["parent"], timestamp_ns=str(ns), side=pair["side"],
            a0_trading_enabled=self._a0_enabled(), original_second=str(a["original_second"]),
            original_first_allocation="UNKNOWN"if self._split_parent is None else str(self._split_parent["first_quantity"]),
            first_filled_ever=str(m.get("first_filled","UNKNOWN")),
            first_terminal=str(a["first_terminal"]), second_filled_ever=str(m.get("second_filled", "UNKNOWN")),
            remaining="UNKNOWN" if remaining is None else str(remaining), original_price=str(a["price"]),
            original_second_orders=list(a.get("original_second_orders",())),
            original_tif="GTC_POST_ONLY", lock_ns=str(a["lock_ns"]), off_ns=None if a["off_ns"] is None else str(a["off_ns"]),
            off_plus60_ready=a["off_ns"] is not None and ns >= a["off_ns"]+MINUTE,
            held=str(held), sol_held=str(self._pair_qty(self.config.sol_id)), cap=str(pair["caps"].bmax),
            debt_since=pair["debt_since"], risk=pair["risk"], entry_terminal=pair["entry_terminal"],
            ordinary_tp_touched=bool(m.get("touched")), entries_enabled=self._entries_enabled(ignore_paired_lock=True),
            old_orders=[order_row(oid) for oid in a["old_orders"]],
            open_inflight=[order_row(str(o.client_order_id)) for o in self.cache.orders_open()+self.cache.orders_inflight()
                if o.instrument_id in (self.config.btc_id, self.config.sol_id)],
            current_btc_tp=[order_row(oid) for oid, intent in self._pending_by_order.items()
                if intent.action == "BTC_REDUCE" and intent.episode_id == pair["parent"]],
            sol_protection_gap=pair["protection_since"], marks=marks, native_margin=native_margin,
            native_account="UNKNOWN"if account is None else account_facts,
            native_account_capture=dict(complete=account_facts["complete"],errors=account_facts["errors"]),
            stock_guard_invoked=False,stock_margin_invoked=False,stock_margin_invocation_scope="PROSPECTIVE_STRATEGY_GUARD_ONLY",
            read_only_current_fact_margin_for_attempts=margin_fact_reads,stock_margin_result="UNKNOWN_NOT_EXECUTED_OBSERVER", admission="UNKNOWN_OBSERVATION_ONLY",
            bid="UNKNOWN" if quote is None else str(quote.bid_price), ask="UNKNOWN" if quote is None else str(quote.ask_price),
            quote_ns="UNKNOWN" if quote is None else str(quote.ts_event),
            post_only_cross="UNKNOWN" if quote is None or a["price"] is None else not (a["price"] < quote.ask_price.as_decimal() if pair["side"] == 1 else a["price"] > quote.bid_price.as_decimal()))
        old_unknown=any(o["status"]=="UNKNOWN"for o in row["old_orders"])
        old_live=any(o["status"]not in {"CANCELED","FILLED","EXPIRED","REJECTED","DENIED"}for o in row["old_orders"])
        pending_increase=any(not o.is_reduce_only for o in self.cache.orders_open()+self.cache.orders_inflight()
            if o.instrument_id in (self.config.btc_id,self.config.sol_id))
        if not a["lock_eligible"]:wait="ORIGINAL_RIGHT_NOT_ESTABLISHED"
        elif not held or not self._domain.episode or self._domain.episode.id!=pair["parent"]or row["ordinary_tp_touched"]or not row["entries_enabled"]:wait="PARENT_TP_FLAT_CLOSE_OR_PAUSE"
        elif pair["risk"]!="INACTIVE_RISK"or pair["failed"]or not pair["entry_terminal"]:wait="WAIT_RISK_OFF"
        elif not row["off_plus60_ready"]:wait="WAIT_60_SECONDS"
        elif old_unknown or old_live:wait="WAIT_OLD_NATIVE_TERMINAL"
        elif pending_increase or self._pair_work(kinds={"ENTRY"})or self._pair_work(instrument=self.config.btc_id):wait="WAIT_PENDING"
        elif pair["debt_since"]is not None or held>pair["caps"].bmax:wait="WAIT_DEBT"
        elif not self._a0_targets_ready(self._domain.episode,m,held):wait="CURRENT_THREE_TP_ACK_UNKNOWN"
        elif remaining is None:wait="SECOND_BUDGET_UNKNOWN"
        elif not remaining:wait="SECOND_BUDGET_EXHAUSTED"
        elif row["post_only_cross"]is True:wait="POST_ONLY_CROSS"
        elif row["post_only_cross"]=="UNKNOWN":wait="QUOTE_UNKNOWN"
        else:wait="READY_FOR_ACTUAL_STOCK_GUARD"
        declared="UNKNOWN"
        if wait in {"POST_ONLY_CROSS","QUOTE_UNKNOWN","READY_FOR_ACTUAL_STOCK_GUARD"}:
            from coinmaster.strategy.a0_rights import release_cap
            if a["locked_cap"]is None:a["locked_cap"]=pair["caps"].bmax
            cap=min(release_cap(a["first_terminal"],a["original_second"],a["locked_cap"],remaining),pair["caps"].bmax+remaining)
            declared=str(min(remaining,max(D(0),cap-held)))
        row.update(observer_reason=wait,original_right_lock_eligible=a["lock_eligible"],
            declared_quantity=declared,observer_locked_cap="UNKNOWN"if a["locked_cap"]is None else str(a["locked_cap"]))
        # Snapshot native values only on causal stage/WAIT-state changes. Price
        # movement without changed eligibility cannot manufacture opportunities.
        signature=repr((wait,held,row["sol_held"],row["cap"],remaining,
            row["old_orders"],row["open_inflight"],row["current_btc_tp"],
            row["sol_protection_gap"],account_facts["complete"],[(e["field"],e["type"])for e in account_facts["errors"]],[(k,v["policy_current"])for k,v in marks.items()]))
        if reason in {"RISK_CANCEL", "RISK_OFF","FIRST_BTC_QUOTE_AFTER_RISK_OFF_PLUS60"} or signature != a["last_record"]:
            if len(self._pair_predecisions)>=10000:raise ValueError("PREDECISION_OBSERVER_CAPACITY_EXCEEDED_NO_TRUNCATION")
            self._pair_predecisions.append(row);counts["records"]+=1
            a["last_record"] = signature
        else:counts["coalesced"]+=1


    def _a0_targets_ready(self, ep, m, held):
        # Runs after the original off_ns/+60 initialization, preserving clocks.
        # Same original right/clock; unknown SOL ACK or a draining STOP blocks
        # increases until actual terminal state, never grants synthetic coverage.
        if getattr(self.config, "research_sol_standing_protection", False) and self._pair:
            if self._pair["protection_since"] is not None or any(
                order is None or order.is_pending_cancel or owner.get("pending") is not None
                for _, owner, order in self._pair_work(instrument=self.config.sol_id)):
                return
        return super()._a0_targets_ready(ep,m,held)


    def _pair_sol_boundary(self, label, ns, strict=False):
        """Read-only observation at native matching barriers, no pumping/mutation."""
        if not getattr(self.config, "research_sol_standing_protection", False) or not self._pair:
            return
        p=self._pair;held=self._pair_qty(self.config.sol_id)
        rows=[];exact=True;expected={}
        if held and p["p0"] is not None:
            inst=self.cache.instrument(self.config.sol_id)
            prices,stop=sol_prices(p["p0"],p["atr"],-p["side"],inst.price_increment.as_decimal())
            expected={("TP",level):(D(count)*inst.size_increment.as_decimal(),prices[level],None)
                for level,count in p["tp_lots"].items()if count>0}
            expected[("STOP",None)]=(held,None,stop)
        work=self._pair_work(instrument=self.config.sol_id,kinds={"TP","STOP"})
        for oid,owner,order in work:
            target=expected.get((owner["kind"],owner["level"]))
            matches=(order is not None and target is not None and owner.get("parent")==p["parent"]
                and order.strategy_id==self.id and order.instrument_id==self.config.sol_id and order.is_reduce_only
                and order.side==(OrderSide.BUY if p["side"]==1 else OrderSide.SELL)and owner["accepted"] and owner.get("pending")is None
                and order.status.name in {"ACCEPTED","PARTIALLY_FILLED","TRIGGERED"}
                and order.leaves_qty.as_decimal()==target[0]
                and self._pair_sol_payload_matches(order,(order.filled_qty.as_decimal()+target[0],target[1],target[2])))
            exact=exact and matches
            rows.append(dict(order_id=oid,kind=owner["kind"],level=owner["level"],exact=matches,
                status="UNKNOWN"if order is None else order.status.name,
                leaves="UNKNOWN"if order is None else str(order.leaves_qty),
                total="UNKNOWN"if order is None else str(order.quantity),
                filled="UNKNOWN"if order is None else str(order.filled_qty),
                price="UNKNOWN"if order is None else str(getattr(order,"price",None)),
                trigger="UNKNOWN"if order is None else str(getattr(order,"trigger_price",None)),
                desired="UNKNOWN"if target is None else [str(v)for v in target],
                desired_generation=p["generation"],pending=owner.get("pending")is not None))
        exact=exact and len(work)==len(expected)and sum(p["tp_lots"].values())*self.cache.instrument(self.config.sol_id).size_increment.as_decimal()==held
        pending_commands=any(o.get("pending")is not None and o.get("parent")==p["parent"]for o in self._pair_orders.values())
        state="CLOSING"if p["close_sol"]else"DRAINING"if not held and (work or pending_commands) else"FLAT"if not held else"PROTECTED"if exact else"UNKNOWN"
        counts=getattr(self,"_pair_sol_boundary_counts",None)
        if counts is None:self._pair_sol_boundary_counts=counts=dict(checks=0,strict=0,unknown=0)
        counts["checks"]+=1;counts["strict"]+=int(strict);counts["unknown"]+=int(held and not p["close_sol"]and not exact)
        signature=repr((held,state,exact,rows,p["protection_since"]))
        detailed=bool(getattr(getattr(self.config,"research_native_book",None),"detailed",False))
        if detailed or signature!=p.get("sol_boundary_signature"):
            self._pair_log("SOL_NATIVE_BOUNDARY",ns,label=label,parent=p["parent"],actual_sol=held,
                state=state,exact=exact,orders=rows,protection_since=p["protection_since"])
            p["sol_boundary_signature"]=signature
        if strict and held and not p["close_sol"] and not exact:
            raise ValueError("SOL_BEFORE_MATCHING_EXACT_COVERAGE_UNKNOWN")


    def _pair_trim_start(self,signal,ep,position,branch,ns):
        from coinmaster.strategy.btc_trim import BTCTrimCap
        qref=position.quantity.as_decimal()
        self._pair=dict(role="BTC_TRIM",parent=ep.id,side=ep.side,branch=branch,signal_ns=ns,
            eligible_ns=ns+MINUTE,nominal_deadline_ns=ns+MINUTE+(4 if branch=="B2"else 8)*60*MINUTE,
            boundary=D(str(signal[("K_"+str(ep.side))if branch=="B2"else"O"])),
            signal=dict(signal),caps=BTCTrimCap(qref,qref),risk="ACTIVE_RISK",trim_activated=False,
            first_fill_ns=None,deadline_ns=None,entry_terminal=True,entry_sent=True,p0=None,
            entry_qty=D(0),entry_notional=D(0),quantity=D(0),atr=None,consumed=set(),tp_lots={},
            signature=None,protection_since=None,debt_since=None,close_sol=False,failed=False,
            last_btc=qref,last_sol=D(0),generation=0)
        self._pair_cancel_btc_increases(ns)
        self._pair_log("TRIM_CAUSAL_SELECTED",ns,parent=ep.id,branch=branch,eligible_ns=ns+MINUTE,
            nominal_deadline_ns=self._pair["nominal_deadline_ns"],C0_clock="UNCHANGED_FIRST_ACTUAL_SOL_FILL")

    def _pair_trim_quote(self,tick):
        from coinmaster.strategy.btc_trim import variance_target
        p=self._pair;ns=tick.ts_event
        if p["risk"]!="ACTIVE_RISK":return
        if p["side"]*(tick.bid_price.as_decimal()-p["boundary"])>=0 or ns>=p["nominal_deadline_ns"]:
            p["risk"]="INACTIVE_RISK";p["close_sol"]=True
            self._pair_log("TRIM_RISK_OFF_NO_RESTORE",ns,nominal_deadline_ns=p["nominal_deadline_ns"])
            return
        if p["trim_activated"]or ns<p["eligible_ns"]:return
        position=self._pair_position(self.config.btc_id);ep=self._domain.episode
        actual=position.quantity.as_decimal()if position is not None else None
        if (not ep or ep.id!=p["parent"]or ep.side!=p["side"]or position is None
                or position.is_long!=(p["side"]==1)or actual!=p["caps"].qref):
            reason="TRIM_INCOMPARABLE_CHANGED_NATIVE_PARENT_SIDE_OR_QUANTITY"
            if reason not in self._pair_failures:self._pair_failures.append(reason)
            p["failed"]=True;p["risk"]="UNKNOWN_RISK";p["close_sol"]=True
            self._pair_log("QUALIFICATION_NO_GO",ns,reason=reason,parent=p["parent"],
                actual_parent=None if not ep else ep.id,selected_qref=p["caps"].qref,actual_btc=actual)
            # Stop before sizing/cap mutation/native trim command. Actual leaves
            # are captured by the caller before native end/dispose.
            raise ValueError(reason)
        qref=p["caps"].qref
        signal=p["signal"];last=signal.get("coefficient_last_ns");available=signal.get("coefficient_available_ns")
        if last is None or available is None or last>p["signal_ns"]-1440*MINUTE or available>p["signal_ns"]:
            self._pair_fail("TRIM_INCOMPARABLE_CAUSAL_COEFFICIENTS",ns);return
        btc=self.cache.instrument(self.config.btc_id);sol=self.cache.instrument(self.config.sol_id)
        try:
            result=variance_target(qref,btc.size_increment.as_decimal(),sol.size_increment.as_decimal(),
                D(str(signal["PB"])),D(str(signal["PS"])),signal.get("sigma_btc"),signal.get("sigma_sol"),signal.get("rho"),D(str(signal["a"])))
        except ValueError as error:
            self._pair_fail(str(error),ns);return
        p["trim_activated"]=True;p["caps"].bmax=min(p["caps"].bmax,result["target_btc"])
        self._pair_log("TRIM_NATIVE_ABSOLUTE_CAP",ns,**result,coefficient_last_ns=last,
            coefficient_available_ns=available,eligible_ns=p["eligible_ns"],nominal_deadline_ns=p["nominal_deadline_ns"],
            bid=tick.bid_price.as_decimal(),ask=tick.ask_price.as_decimal(),PB=signal["PB"],PS=signal["PS"],
            sigma_btc=signal["sigma_btc"],sigma_sol=signal["sigma_sol"],rho=signal["rho"],
            actual_C0_SOL_fills="NOT_USED",native_SOL_credit="ZERO_NO_SOL_ORDERS")
        self._pair_arm_btc_debt(ns)
