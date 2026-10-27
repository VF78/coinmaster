"""Default-off TP-only execution. Raw E4 sizing, split and SOL policy stay native.

The only inventory authority is Cache; no fills or money are synthesized here.
"""
from decimal import Decimal as D
from nautilus_trader.model.identifiers import ClientOrderId
from coinmaster.strategy.market_redesign import u_prices


def cumulative_entitlement(entry_lots, filled, retired):
    """Cumulative grants minus irreversible consumption, in native integer lots."""
    if type(entry_lots) is not int or entry_lots < 0:
        raise ValueError("METHOD_A_UNKNOWN_ENTRY_LOTS")
    first = int(D(entry_lots)*D(".2125"))
    first_two = int(D(entry_lots)*D(".425"))
    grants = {0: first, 1: first_two-first, 2: entry_lots-first_two}
    for values in (filled, retired):
        if any(type(v) is not int or v < 0 for v in values.values()):
            raise ValueError("METHOD_A_UNKNOWN_CONSUMPTION")
    leaves = {i: grants[i] - filled.get(i, 0) - retired.get(i, 0) for i in range(3)}
    if any(v < 0 for v in leaves.values()):
        raise ValueError("METHOD_A_OVERCONSUMED_TARGET")
    return grants, leaves


def native_tp_prices(instrument, reference, d3, side):
    from coinmaster.strategy.wave_overlay import _native_limit_price
    fee = max(D(str(instrument.maker_fee)), D(str(instrument.taker_fee)))
    entry_fee = D(str(instrument.taker_fee))
    raw = u_prices(reference, d3, side, instrument.price_increment.as_decimal(), entry_fee, fee)
    wire = tuple(_native_limit_price(instrument, px).as_decimal() for px in raw)
    if not all(side*(b-a)>0 for a,b in zip((reference,)+wire, wire)) or any(side*(px-reference)-entry_fee*reference-fee*px <= 0 for px in wire):
        raise ValueError("METHOD_A_WIRE_TARGET_NOT_POSITIVE_ORDERED")
    return wire


class MethodATpResearch:
    def _ma_enabled(self):
        return bool(self.config.research_method_a_tp)

    def _ma_init(self):
        self.method_a_tp_audit = []
        self._ma_plans = {}

    def _ma_log(self, event, ts, **values):
        self.method_a_tp_audit.append(dict(event=event, timestamp_ns=str(ts), **values))

    def _ma_prepare(self, intent, quantity, instrument, price, ts):
        if not self._ma_enabled():
            return
        ep = self._domain.episode
        if ep is None or ep.wave_levels is None or ep.id in self._ma_plans:
            raise ValueError("METHOD_A_INVALID_OR_DUPLICATE_PLAN")
        d3 = D(str(ep.wave_levels[2]))
        # Validate geometry at the same causal quote, without changing raw levels.
        native_tp_prices(instrument, price, d3, ep.side)
        raw_targets = dict(ep.btc_reference_target_lots)
        if not raw_targets:
            n = int(quantity/instrument.size_increment.as_decimal())
            assigned = 0
            fractions = tuple(D(str(v)) for v in self._candidate.btc_tp_fractions_initial_qty)
            for i, fraction in enumerate(fractions):
                lots = n-assigned if i == 2 and sum(fractions) == 1 else int(D(n)*fraction)
                raw_targets[i] = lots
                assigned += lots
        self._ma_plans[ep.id] = dict(raw_levels=tuple(ep.wave_levels), d3=d3,
            raw_target_lots=raw_targets, quantity=quantity,
            signature=None, expected_cancels=set(), submitted={}, accepted=set())
        self._ma_log("PLAN", ts, episode_id=ep.id, raw_levels=list(ep.wave_levels),
                     parent_quantity=str(quantity), raw_target_lots=dict(ep.btc_reference_target_lots))

    def _ma_reconcile(self, ts):
        if not self._ma_enabled():
            return
        ep = self._domain.episode
        if ep is None or ep.id not in self._ma_plans or self._forced_close_reason or self._liquidating:
            return
        m = self._ma_plans[ep.id]
        inst = self.cache.instrument(self.config.btc_id)
        step = inst.size_increment.as_decimal()
        positions = [p for p in self.cache.positions_open() if p.instrument_id == inst.id]
        held = positions[0].quantity.as_decimal() if positions else D(0)
        if positions and positions[0].is_long != (ep.side == 1):
            raise ValueError("METHOD_A_NATIVE_WRONG_SIDE")
        if not ep.btc_entry_qty_exact:
            return
        grants, leaves = cumulative_entitlement(int(ep.btc_entry_qty_exact / step),
            ep.btc_tp_filled_lots, ep.btc_risk_retired_lots)
        if sum(leaves.values()) != int(held / step):
            raise ValueError("METHOD_A_NATIVE_INVENTORY_MISMATCH")
        # PLANREF remains the legacy completed-FIRST value. Before completion,
        # actual first VWAP supplies TP geometry only; it grants no entry right.
        parent = self._split_parent
        reference = ep.btc_planref_vwap if ep.btc_planref_vwap is not None else parent["first_vwap"]
        if reference is None:
            raise ValueError("METHOD_A_MISSING_ACTUAL_FIRST_REFERENCE")
        prices = native_tp_prices(inst, D(str(reference)), m["d3"], ep.side)
        initial = not ep.btc_tp_filled_lots and not ep.btc_risk_retired_lots
        if held and any((initial and leaves[i] <= 0) or
            (leaves[i] > 0 and ((inst.min_quantity and D(leaves[i])*step < inst.min_quantity.as_decimal()) or
             (inst.min_notional and D(leaves[i])*step*prices[i] < inst.min_notional.as_decimal()))) for i in range(3)):
            self._ma_log("TINY_PARTIAL_FAILCLOSED", ts, episode_id=ep.id, actual_inventory=str(held))
            self._begin_forced_close("METHOD_A_INSUFFICIENT_PARTIAL_PROTECTION")
            return
        signature = (D(str(reference)), tuple(grants.values()), tuple(leaves.values()))
        work = [(oid, i) for oid, i in self._pending_by_order.items()
                if i.action == "BTC_REDUCE" and i.episode_id == ep.id]
        desired = {i: lots for i, lots in leaves.items() if lots > 0}
        # Acknowledged cancel barrier: pending-cancel leaves still own inventory.
        wrong = []
        for oid, intent in work:
            order = self.cache.order(ClientOrderId(oid))
            if order is None:
                return  # Unknown native ACK is owned; never duplicate it.
            if not order.is_closed and (order.leaves_qty.as_decimal() != D(desired.get(intent.level, 0))*step or
                (getattr(order, "price", None) is not None and order.price.as_decimal() != prices[intent.level])):
                wrong.append(order)
        if wrong:
            m["expected_cancels"].update(str(order.client_order_id) for order in wrong)
            for order in wrong:
                if not order.is_pending_cancel:
                    self.cancel_order(order)
            self._ma_log("REPLACE_ACK_PENDING", ts, episode_id=ep.id)
            return
        if m["expected_cancels"]:
            return
        self._bind_native_lots()
        ep.btc_tp_target_lots = grants
        ep.btc_tp_target_qty = {i: float(D(v)*step) for i, v in grants.items()}
        for i, lots in leaves.items():
            if lots:
                ep.btc_filled_tps.discard(i)
            else:
                ep.btc_filled_tps.add(i)
        owned = {i.level for _, i in work}
        m["signature"] = signature
        for i, lots in desired.items():
            if i in owned:
                continue
            ep.btc_tps.add(i)
            intent = self._domain._intent(ep, "BTC_REDUCE", -ep.side, i,
                quantity=float(D(lots)*step), reason=f"BTC_TP{i+1}", limit_price=float(prices[i]))
            ep.resting_reductions.add(intent.id)
            self._submit_intent(intent, float(reference), float(reference), None, len(self._bars)-1, ts_now=ts)
        if m.get("logged_signature") == signature:
            return
        m["logged_signature"] = signature
        self._ma_log("ENTITLEMENT", ts, episode_id=ep.id,
            cumulative_entry_lots=int(ep.btc_entry_qty_exact/step), grants=grants,
            actual_tp_filled=dict(ep.btc_tp_filled_lots), risk_retired=dict(ep.btc_risk_retired_lots),
            leaves=leaves, actual_held_lots=int(held/step), tp_reference=str(reference),
            legacy_planref=None if ep.btc_planref_vwap is None else str(ep.btc_planref_vwap),
            original_deadline_ns=str(parent["deadline_ns"]), split_fallback=parent["fallback"])

    def _ma_after_fill(self, intent, event):
        if not self._ma_enabled() or intent is None or not intent.action.startswith("BTC"):
            return
        ep = self._domain.episode
        if ep is not None and intent.action == "BTC_REDUCE" and intent.level is not None:
            # Keep old alpha eligibility denominator separate from executable TP.
            m = self._ma_plans[ep.id]
            raw_lots = m["raw_target_lots"].get(intent.level, 0)
            if intent.level in ep.btc_omitted_zero_levels:
                ep.sol_right_fraction[intent.level] = min(1.0, ep.btc_initial_qty/ep.btc_net_planned_qty)
            elif raw_lots > 0:
                fraction = min(1.0, ep.btc_initial_qty/ep.btc_net_planned_qty) if ep.btc_net_planned_qty > 0 else 1.0
                ep.sol_right_fraction[intent.level] = min(1.0, ep.btc_tp_filled_lots.get(intent.level, 0)/raw_lots)*fraction
            self._ma_log("ACTUAL_TP_FILL", event.ts_event, episode_id=ep.id,
                trade_id=str(event.trade_id), order_id=str(event.client_order_id),
                level=intent.level, quantity=str(event.last_qty),
                old_sol_rights=sorted(ep.sol_rights), old_sol_fractions=dict(ep.sol_right_fraction))
        self._ma_reconcile(event.ts_event)

    def _ma_terminal(self, intent, event):
        if not self._ma_enabled() or intent is None:
            return
        m = self._ma_plans.get(intent.episode_id)
        if m is not None:
            m["expected_cancels"].discard(str(event.client_order_id))
        self._ma_reconcile(event.ts_event)
