"""One original-second right; existing native order owner and margin gates only."""
from decimal import Decimal as D, ROUND_FLOOR, ROUND_CEILING
from nautilus_trader.model.identifiers import ClientOrderId
from nautilus_trader.model.enums import OrderSide

MINUTE = 60_000_000_000


def release_cap(first_terminal, original_second, locked_cap, remaining):
    if any(not x.is_finite() or x < 0 for x in (first_terminal, original_second, locked_cap, remaining)) or remaining > original_second:
        raise ValueError("A0_UNKNOWN_CAP")
    return min(first_terminal + original_second, locked_cap + remaining)


class A0RightsResearch:
    def _a0_enabled(self):
        return bool(self.config.research_a0_original_second)

    def _a0_bind_entry(self, oid, intent):
        m = self._md_plans.get(intent.episode_id)
        if not m:
            return
        role = "SECOND" if m["first_done"] else "FIRST"
        m.setdefault("entry_orders", {})[oid] = role

    def _a0_note_submit(self, oid, ts):
        if not getattr(self, "_a0_submitting", False):
            return
        p = self._split_parent
        a = self._md_plans[p["episode_id"]]["a0"]
        a["submitted"], a["order_id"] = True, oid
        self._md_log("A0_SUBMIT", ts, episode_id=p["episode_id"], order_id=oid,
                     generation=1, price=a["price"], quantity=a["submit_qty"])

    def _a0_deny(self, a, reason, ns, **values):
        a["denial_counts"][reason] = a["denial_counts"].get(reason, 0) + 1
        if a.get("last_denial") != reason:
            self._md_log("A0_DENY", ns, reason=reason, **values)
            a["last_denial"] = reason

    def _a0_stop(self, reason):
        if not self._a0_enabled() or not self._split_parent:
            return
        m = self._md_plans.get(self._split_parent["episode_id"], {})
        a = m.get("a0")
        if a and reason != "PAIRED_MONOTONE_PARENT_CEILING":
            a["dead"] = reason

    def _a0_lock(self, ns):
        if not self._a0_enabled():
            return
        p, pair = self._split_parent, self._pair
        if not p or not pair or p["episode_id"] != pair["parent"]:
            return
        m = self._md_plans[p["episode_id"]]
        # A normal closed second child, missing P0 or ordinary TP never creates rights.
        if "a0" in m or p.get("stop_reason") not in (None, "PAIRED_MONOTONE_PARENT_CEILING") or m["touched"] or not m["first_done"] or m["p0"] is None:
            return
        old = m.get("entry_orders", {})
        second = [oid for oid, role in old.items() if role == "SECOND"]
        work = [self.cache.order(ClientOrderId(oid)) for oid in second]
        if not work or not any(o is None or not o.is_closed for o in work):
            return  # Only a risk-cancelled actual old child owns an A0 right.
        inst = self.cache.instrument(self.config.btc_id)
        tick = inst.price_increment.as_decimal()
        raw = m["p0"] * (1 - self.config.research_btc_split_discount * p["side"])
        px = (raw / tick).to_integral_value(rounding=ROUND_FLOOR if p["side"] == 1 else ROUND_CEILING) * tick
        m["a0"] = dict(original_second=p["quantity"] - p["first_quantity"],
            first_terminal=m["first_filled"], price=px, old_orders=tuple(old),
            off_ns=None, locked_cap=None, granted_cap=None, submitted=False, attempted=False,
            dead=None, order_id=None, submit_qty=D(0), denial_counts={}, last_denial=None)
        self._md_log("A0_RIGHT_LOCKED", ns, episode_id=p["episode_id"],
                     original_second=m["a0"]["original_second"], price=px, old_orders=list(old))

    def _a0_keep_order(self, order):
        if not self._a0_enabled() or not self._pair or self._pair["risk"] != "INACTIVE_RISK":
            return False
        m = self._md_plans.get(self._pair["parent"], {})
        a = m.get("a0")
        return bool(a and a["submitted"] and not a["dead"] and a["order_id"] == str(order.client_order_id))

    def _a0_check(self, tick):
        if not self._a0_enabled() or tick.instrument_id != self.config.btc_id:
            return
        p, pair, ep = self._split_parent, self._pair, self._domain.episode
        if not p:
            return
        m = self._md_plans.get(p["episode_id"], {})
        a = m.get("a0")
        if not a or a["dead"] or a["attempted"]:
            return
        ns = tick.ts_event
        if not ep or ep.id != p["episode_id"] or ep.side != p["side"] or (self._pair_position(self.config.btc_id) is not None and self._pair_position(self.config.btc_id).is_long != (p["side"] == 1)) or not self._pair_qty(self.config.btc_id) or m["touched"] or self._forced_close_reason or self._liquidating or not self._entries_enabled(ignore_paired_lock=True):
            a["dead"] = "PARENT_TP_FLAT_CLOSE_OR_PAUSE"
            return
        if not pair or pair["parent"] != ep.id or pair["risk"] != "INACTIVE_RISK" or pair["failed"] or not pair["entry_terminal"]:
            return
        if a["off_ns"] is None:
            a["off_ns"] = ns
        if ns < a["off_ns"] + MINUTE:
            return
        # Cache absence and owned unknown ACK both block. Never infer terminal from no open list.
        if any((o := self.cache.order(ClientOrderId(oid))) is None or not o.is_closed for oid in a["old_orders"]):
            return
        increases = [o for o in self.cache.orders_open() + self.cache.orders_inflight()
                     if o.instrument_id in (self.config.btc_id, self.config.sol_id) and not o.is_reduce_only]
        owned = [i for i in self._pending_by_order.values() if i.action in ("BTC_ENTRY", "SOL_ADD")]
        held = self._pair_qty(self.config.btc_id)
        if increases or owned or self._pair_work(kinds={"ENTRY"}) or pair["debt_since"] is not None or self._pair_work(instrument=self.config.btc_id) or held > pair["caps"].bmax:
            return
        step = self.cache.instrument(self.config.btc_id).size_increment.as_decimal()
        from coinmaster.strategy.paired_prefix import exact_lots
        remaining = D(max(0, exact_lots(a["original_second"], step) - exact_lots(m["second_filled"], step))) * step
        if not remaining:
            a["dead"] = "SECOND_BUDGET_EXHAUSTED"
            return
        # Freeze the reconciled old absolute ceiling before any WAIT or release.
        if a["locked_cap"] is None:
            a["locked_cap"] = pair["caps"].bmax
        cap = min(release_cap(a["first_terminal"], a["original_second"], a["locked_cap"], remaining), pair["caps"].bmax + remaining)
        qty = min(remaining, max(D(0), cap - held))
        if qty <= 0:
            return
        if not (a["price"] < tick.ask_price.as_decimal() if ep.side == 1 else a["price"] > tick.bid_price.as_decimal()):
            self._a0_deny(a, "POST_ONLY_CROSS", ns, episode_id=ep.id, price=a["price"], locked_cap=a["locked_cap"])
            return
        side = OrderSide.BUY if ep.side == 1 else OrderSide.SELL
        # Actual stock strategy/account/tier/free-funds gate, no fixture override.
        if not self._tier_allows_increase(self.config.btc_id, side, qty, ns):
            self._a0_deny(a, "NATIVE_MARGIN", ns, episode_id=ep.id, quantity=qty)
            return
        a["attempted"] = True
        a["granted_cap"], a["submit_qty"] = cap, qty
        pair["caps"].bmax = cap
        ep.pending[p["intent"].id] = p["intent"]
        self._split_child_submit = self._a0_submitting = True
        try:
            self._submit_intent(p["intent"], float(tick.bid_price), float(tick.ask_price), p["sigma"], p["decision_index"], ts_now=ns, entry_override_qty=qty)
        finally:
            self._split_child_submit = self._a0_submitting = False
        self._md_log("A0_GRANT_ONCE", ns, episode_id=ep.id, locked_cap=a["locked_cap"],
                     cap=cap, remaining=remaining, submitted=a["submitted"])
