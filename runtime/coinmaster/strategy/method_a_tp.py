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
        self._ma_owners = {}
        self._ma_commands = {}
        self._ma_seen_events = set()
        self._ma_sequence = 0
        self._ma_busy = False

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
        # Same raw legacy target denominator as domain._ensure_btc_targets;
        # reference buckets remain metadata, never executable/fake exits.
        n = int(quantity/instrument.size_increment.as_decimal())
        references = ep.btc_reference_target_lots
        retained = [i for i in range(3) if i not in ep.btc_omitted_zero_levels]
        denominator = sum(references.get(i,0) for i in retained)
        fractions = tuple(D(str(v)) for v in self._candidate.btc_tp_fractions_initial_qty)
        raw_targets = {}; assigned = 0
        for i,fraction in enumerate(fractions):
            if i in ep.btc_omitted_zero_levels:
                lots = 0
            elif denominator:
                lots = n-assigned if i==retained[-1] else int(D(n)*D(references[i])/D(denominator))
            else:
                lots = n-assigned if i==2 and sum(fractions)==1 else int(D(n)*fraction)
            raw_targets[i]=lots;assigned+=lots
        self._ma_plans[ep.id] = dict(raw_levels=tuple(ep.wave_levels), d3=d3,
            raw_target_lots=raw_targets, quantity=quantity,
            signature=None, expected_cancels=set(), submitted={}, accepted=set())
        self._ma_log("PLAN", ts, episode_id=ep.id, raw_levels=list(ep.wave_levels),
                     parent_quantity=str(quantity), raw_target_lots=dict(ep.btc_reference_target_lots))

    def _ma_wire_prices(self, ep, inst, reference, d3):
        from coinmaster.strategy.wave_overlay import _fee_floor_price
        prices = native_tp_prices(inst, reference, d3, ep.side)
        if self.config.tp_fee_floor_v1:
            floor = _fee_floor_price(inst, ep, maker=True).as_decimal()
            prices = tuple(max(px, floor) if ep.side == 1 else min(px, floor) for px in prices)
        return prices

    def _ma_bind_order(self, order, intent):
        if not self._ma_enabled() or intent.action != "BTC_REDUCE":
            return
        self._ma_owners[str(order.client_order_id)] = dict(parent=intent.episode_id,
            intent_id=intent.id, level=intent.level, side=order.side.name,
            strategy_id=str(order.strategy_id), ack=False, terminal=None)

    def _ma_native_event(self, event):
        if not self._ma_enabled():
            return
        oid = str(event.client_order_id)
        owner = self._ma_owners.get(oid)
        if owner is None:
            return
        eid = str(event.id)
        if eid in self._ma_seen_events:
            return
        name = type(event).__name__
        if name == "OrderInitialized":
            return  # No cache/ACK credit before public submit registration.
        order = self.cache.order(event.client_order_id)
        if order is None or str(event.strategy_id) != owner["strategy_id"] or event.instrument_id != self.config.btc_id or not any(str(e.id) == eid for e in order.events):
            raise ValueError("METHOD_A_NATIVE_EVENT_HISTORY_UNKNOWN")
        self._ma_seen_events.add(eid)
        if order.is_closed:
            owner["terminal"] = eid
            self._ma_commands.pop(oid, None)
            m = self._ma_plans.get(owner["parent"])
            if m:
                m["expected_cancels"].discard(oid)
            return  # Typed after-fill/cancel applies domain state before reconcile.
        if name == "OrderUpdated":
            command = self._ma_commands.get(oid)
            if command is None or order.quantity.as_decimal() != command["total"] or order.price.as_decimal() != command["price"]:
                raise ValueError("METHOD_A_MODIFY_ACK_NOT_LATEST_SUBMITTED")
            self._ma_commands.pop(oid)
            owner["ack"] = True
            self._ma_log("LATEST_MODIFY_ACK", event.ts_event, order_id=oid,
                sequence=command["sequence"], native_event_id=eid,
                total=str(order.quantity), filled=str(order.filled_qty), leaves=str(order.leaves_qty), price=str(order.price))
        elif name == "OrderAccepted":
            owner["ack"] = True
        elif name == "OrderModifyRejected":
            raise ValueError("METHOD_A_VALID_MODIFY_REJECTED")
        else:
            return
        self._ma_reconcile(event.ts_event)

    def _ma_before_fill(self, event):
        if not self._ma_enabled():
            return
        owner = self._ma_owners.get(str(event.client_order_id))
        if owner is None:
            return
        self._ma_native_event(event)
        # Genuine full fill retires pending modification/cancel ownership even
        # when no subsequent cancel ACK exists. Partial fill keeps the owner.

    def _ma_entry_ready(self):
        if not self._ma_enabled():
            return True
        ep = self._domain.episode
        if ep is None or not ep.btc_entry_qty_exact:
            return True
        m = self._ma_plans.get(ep.id)
        return bool(m and m.get("coverage_ready"))

    def _ma_reconcile(self, ts):
        if not self._ma_enabled() or self._ma_busy:
            return
        ep = self._domain.episode
        if ep is None or ep.id not in self._ma_plans or self._forced_close_reason or self._liquidating:
            return
        self._ma_busy = True
        try:
            m = self._ma_plans[ep.id]
            inst = self.cache.instrument(self.config.btc_id)
            step = inst.size_increment.as_decimal()
            positions = [p for p in self.cache.positions_open() if p.instrument_id == inst.id]
            if len(positions)>1 or (positions and positions[0].is_long != (ep.side == 1)):
                raise ValueError("METHOD_A_NATIVE_WRONG_SIDE")
            held = positions[0].quantity.as_decimal() if positions else D(0)
            if held/step != (held/step).to_integral_value() or ep.btc_entry_qty_exact/step != (ep.btc_entry_qty_exact/step).to_integral_value():
                raise ValueError("METHOD_A_NONINTEGER_NATIVE_LOTS")
            if not ep.btc_entry_qty_exact:
                return
            grants, leaves = cumulative_entitlement(int(ep.btc_entry_qty_exact/step), ep.btc_tp_filled_lots, ep.btc_risk_retired_lots)
            if sum(leaves.values()) != int(held/step):
                raise ValueError("METHOD_A_NATIVE_INVENTORY_MISMATCH")
            parent = self._split_parent
            reference = ep.btc_planref_vwap if ep.btc_planref_vwap is not None else parent["first_vwap"]
            if reference is None:
                raise ValueError("METHOD_A_MISSING_ACTUAL_FIRST_REFERENCE")
            prices = self._ma_wire_prices(ep, inst, D(str(reference)), m["d3"])
            initial = not ep.btc_tp_filled_lots and not ep.btc_risk_retired_lots
            if held and any((initial and leaves[i]<=0) or (leaves[i]>0 and
                ((inst.min_quantity and D(leaves[i])*step<inst.min_quantity.as_decimal()) or
                 (inst.min_notional and D(leaves[i])*step*prices[i]<inst.min_notional.as_decimal()))) for i in range(3)):
                self._ma_log("TINY_PARTIAL_FAILCLOSED",ts,episode_id=ep.id,actual_inventory=str(held))
                self._begin_forced_close("METHOD_A_INSUFFICIENT_PARTIAL_PROTECTION")
                return
            self._bind_native_lots()
            ep.btc_tp_target_lots=grants
            ep.btc_tp_target_qty={i:float(D(v)*step) for i,v in grants.items()}
            for i,lots in leaves.items():
                if lots: ep.btc_filled_tps.discard(i)
                else: ep.btc_filled_tps.add(i)
            live={}
            for oid,owner in self._ma_owners.items():
                if owner["parent"]!=ep.id:
                    continue
                order=self.cache.order(ClientOrderId(oid))
                if order is None:
                    raise ValueError("METHOD_A_OWNED_ORDER_UNKNOWN")
                if order.is_closed:
                    continue
                intent=self._pending_by_order.get(oid)
                if intent is None or intent.id!=owner["intent_id"] or order.strategy_id!=self.id or not order.is_reduce_only or order.side.name!=owner["side"]:
                    raise ValueError("METHOD_A_NATIVE_ORDER_OWNERSHIP_UNKNOWN")
                if owner["level"] in live:
                    raise ValueError("METHOD_A_DUPLICATE_LIVE_TARGET")
                live[owner["level"]]=(oid,owner,order)
            m["coverage_ready"]=False
            for i,lots in leaves.items():
                current=live.get(i)
                if current is None:
                    if not lots: continue
                    ep.btc_tps.add(i)
                    intent=self._domain._intent(ep,"BTC_REDUCE",-ep.side,i,
                        quantity=float(D(lots)*step),reason=f"BTC_TP{i+1}",limit_price=float(prices[i]))
                    ep.resting_reductions.add(intent.id)
                    self._submit_intent(intent,float(reference),float(reference),None,len(self._bars)-1,ts_now=ts)
                    continue
                oid,owner,order=current
                if not lots:
                    # Only zero entitlement retires a live owner. Positive
                    # working protection always survives inventory changes.
                    m["expected_cancels"].add(oid)
                    if not order.is_pending_cancel: self.cancel_order(order)
                    continue
                if order.is_pending_cancel:
                    continue  # Retiring native leaves remain owned until terminal.
                wanted=D(lots)*step
                if oid in self._ma_commands:
                    continue  # Actual late entry/fill coalesces after latest ACK.
                if order.leaves_qty.as_decimal()==wanted and order.price.as_decimal()==prices[i]:
                    continue
                total=order.filled_qty.as_decimal()+wanted
                self._ma_sequence+=1
                command=dict(sequence=self._ma_sequence,total=total,price=prices[i])
                self._ma_commands[oid]=command
                self._ma_log("MODIFY_SUBMIT",ts,episode_id=ep.id,order_id=oid,
                    sequence=command["sequence"],total=str(total),filled=str(order.filled_qty),
                    desired_leaves=str(wanted),price=str(prices[i]),old_working_price=str(order.price))
                self.modify_order(order,quantity=inst.make_qty(total),price=inst.make_price(prices[i]))
            actual={};old_working=0
            for i,(oid,owner,order) in live.items():
                if order.is_closed: continue
                old_working+=int(order.leaves_qty.as_decimal()/step)
                if owner["ack"] and oid not in self._ma_commands and not order.is_pending_cancel and order.status.name in ("ACCEPTED","PARTIALLY_FILLED") and order.price.as_decimal()==prices[i]:
                    actual[i]=int(order.leaves_qty.as_decimal()/step)
            desired={i:n for i,n in leaves.items() if n}
            ready=actual==desired and not m["expected_cancels"]
            m["coverage_ready"]=ready
            signature=(tuple(grants.values()),tuple(leaves.values()),tuple(prices),ready,tuple(sorted(self._ma_commands)))
            if m.get("logged_signature")!=signature:
                m["logged_signature"]=signature
                self._ma_log("ENTITLEMENT",ts,episode_id=ep.id,cumulative_entry_lots=int(ep.btc_entry_qty_exact/step),
                    grants=grants,actual_tp_filled=dict(ep.btc_tp_filled_lots),risk_retired=dict(ep.btc_risk_retired_lots),
                    leaves=leaves,actual_held_lots=int(held/step),acknowledged_current_lots=actual,
                    old_working_lots=old_working,coverage_ready=ready,pending_modify_sequences={oid:c["sequence"] for oid,c in self._ma_commands.items()},
                    tp_reference=str(reference),legacy_planref=None if ep.btc_planref_vwap is None else str(ep.btc_planref_vwap),
                    original_deadline_ns=str(parent["deadline_ns"]),split_fallback=parent["fallback"])
        finally:
            self._ma_busy=False

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
