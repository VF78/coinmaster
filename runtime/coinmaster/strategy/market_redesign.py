"""Default-off BTC U execution using the existing native order owner.

No matching or cash model: cache, fills, pending map and native ACKs are authority.
"""
from decimal import Decimal as D, ROUND_FLOOR, ROUND_CEILING
from nautilus_trader.model.identifiers import ClientOrderId

FRACTIONS = (D(".2125"), D(".2125"), D(".575"))
PHI = {1: D(".8551535379805835"), -1: D(".7977111237672364")}


def legacy_net_lots(gross_lots, target_lots, zero_levels, passive):
    """Pure q0/q1 control; creates neither fills nor rights."""
    omitted = set(zero_levels) if passive else set()
    return sum(lots for level, lots in target_lots.items() if level not in omitted)


def u_prices(p0, d3, side, tick, entry_fee, exit_fee):
    if not p0.is_finite() or not d3.is_finite() or p0 <= 0 or d3 <= 0:
        raise ValueError("REAL_U_INVALID_CAUSAL_D3")
    rounding = ROUND_CEILING if side == 1 else ROUND_FLOOR
    prices = tuple((p0*(1+side*d3*D(i)/3)/tick).to_integral_value(rounding=rounding)*tick for i in (1,2,3))
    if any(px <= 0 for px in prices) or not all(side*(b-a)>0 for a,b in zip((p0,)+prices,prices)):
        raise ValueError("REAL_U_UNORDERED_ROUNDED_PRICES")
    if any(side*(px-p0)-entry_fee*p0-exit_fee*px <= 0 for px in prices):
        raise ValueError("REAL_U_NONPOSITIVE_NET_TARGET")
    return prices


def target_lots(held_lots, consumed):
    levels = [i for i in range(3) if i not in consumed]
    if not levels:
        if held_lots:
            raise ValueError("REAL_U_INVENTORY_AFTER_ALL_TARGETS")
        return {}
    denominator = sum(FRACTIONS[i] for i in levels)
    assigned, result = 0, {}
    for i in levels:
        lots = held_lots-assigned if i == levels[-1] else int(D(held_lots)*FRACTIONS[i]/denominator)
        result[i] = lots
        assigned += lots
    return result


class MarketRedesignResearch:
    def _md_enabled(self):
        return bool(self.config.research_btc_real_u)

    def _md_init(self):
        self.market_redesign_audit = []
        self._md_plans = {}
        self._md_accepted_ids=set()
        self._md_missing_since = None
        self._md_missing_reason = None
        self._md_missing_total_ns = 0

    def _md_log(self, event, ts, **values):
        self.market_redesign_audit.append(dict(event=event, timestamp_ns=str(ts),
            **{k: str(v) if isinstance(v,D) else v for k,v in values.items()}))

    def _md_prepare(self, intent, quantity, instrument, price, ts):
        ep = self._domain.episode
        if ep is None or ep.wave_levels is None:
            raise ValueError("REAL_U_MISSING_WAVE_LEVELS")
        d3 = D(str(ep.wave_levels[2]))
        # First entry is IOC; a real limit may execute as taker on arrival.
        # Validate both classifications conservatively, without modifying d3.
        prices = u_prices(price,d3,ep.side,instrument.price_increment.as_decimal(),
            D(str(instrument.taker_fee)),max(D(str(instrument.maker_fee)),D(str(instrument.taker_fee))))
        first_lots = int(quantity/instrument.size_increment.as_decimal())//2
        allocations = target_lots(first_lots,set())
        for i,lots in allocations.items():
            qty=D(lots)*instrument.size_increment.as_decimal()
            if qty <= 0 or (instrument.min_quantity and qty<instrument.min_quantity.as_decimal()) or (instrument.min_notional and qty*prices[i]<instrument.min_notional.as_decimal()):
                raise ValueError("REAL_U_PLANNED_FIRST_HALF_CANNOT_PROTECT")
        self._md_plans[ep.id] = dict(raw_levels=ep.wave_levels,d3=d3,p0=None,
            prices=None,consumed=set(),touched=set(),accepted=set(),quantity=quantity,first_done=False,
            first_filled=D(0),first_notional=D(0),second_filled=D(0),first_order=None,
            generation=-1,generations={},intent_generation={},order_generation={})
        ep.wave_levels = tuple(float(d3*D(i)/3) for i in (1,2,3))
        ep.btc_omitted_zero_levels.clear()
        ep.btc_zero_resting_suppressed.clear()
        ep.btc_reference_target_lots.clear()
        ep.btc_deferred_right_reference_price=None
        ep.sol_rights.clear()
        ep.sol_right_fraction.clear()
        self._md_log("PLAN",ts,episode_id=ep.id,raw_causal_d3=d3,raw_levels=list(self._md_plans[ep.id]["raw_levels"]),
            sizing_mode=self.config.research_btc_q_mode,quantity=quantity)

    def _md_split_fill(self,intent,event):
        p=self._split_parent
        m=self._md_plans[intent.episode_id]
        qty,px=event.last_qty.as_decimal(),event.last_px.as_decimal()
        if p["filled"]+qty>p["quantity"]:
            raise ValueError("REAL_U_PARENT_OVERFILL")
        p["filled"]+=qty
        if not m["first_done"]:
            m["first_filled"]+=qty
            m["first_notional"]+=qty*px
            m["p0"]=m["first_notional"]/m["first_filled"]
            p["first_filled"]=m["first_filled"]
            p["first_notional"]=m["first_notional"]
            p["first_vwap"]=m["p0"]
        else:
            m["second_filled"]+=qty
        if p.get("stop_reason"):
            p["cancelled"]=p["quantity"]-p["filled"]
        if p["filled"]==p["quantity"]:
            p["closed"]=True

    def _md_first_terminal(self,intent,ts):
        if not self._md_enabled() or intent is None or intent.action!="BTC_ENTRY":
            return
        m=self._md_plans.get(intent.episode_id)
        if not m:
            return
        if m["first_done"]:
            if m.get("second_submitted"):
                self._split_parent["closed"]=True
                self._split_parent["cancelled"]=self._split_parent["quantity"]-self._split_parent["filled"]
                self._md_log("SECOND_TERMINAL",ts,episode_id=intent.episode_id,
                    actual_filled=self._split_parent["filled"],cancelled=self._split_parent["cancelled"])
            return
        m["first_done"]=True
        p=self._split_parent
        p["cancelled"]=p["first_quantity"]-m["first_filled"]
        ep=self._domain.episode
        if ep and m["p0"] is not None:
            ep.btc_planref_vwap=m["p0"]
            p["management_reference_frozen_ns"]=ts
            self._md_log("P0_FROZEN_FIRST_TERMINAL",ts,episode_id=ep.id,p0=m["p0"],first_filled=m["first_filled"])
        if not m["first_filled"]:
            self._split_stop("FIRST_TERMINAL_ZERO_FILL")

    def _md_check(self,tick):
        if not self._md_enabled() or tick.instrument_id!=self.config.btc_id:
            return
        self._md_reconcile(tick.ts_event)
        p=self._split_parent
        ep=self._domain.episode
        if not p or p["closed"]:
            return
        m=self._md_plans[p["episode_id"]]
        if not ep or ep.id!=p["episode_id"] or self._forced_close_reason or self._liquidating or not self._entries_enabled():
            self._split_stop("CLOSE_OR_PAUSE_OR_DP")
            return
        if m["touched"]:
            self._split_stop("FIRST_POSITIVE_TP_FILL")
            return
        if not m["first_done"] or m["p0"] is None:
            return
        # Existing/unknown native ACK owns this child. Never issue a third.
        owned=[i for i in self._pending_by_order.values() if i.action=="BTC_ENTRY" and i.episode_id==ep.id]
        if owned or m.get("second_submitted"):
            return
        if not m["accepted"]=={0,1,2}:
            return
        qty=p["quantity"]-p["first_quantity"]
        m["second_submitted"]=True
        if qty<=0:
            self._split_stop("NO_SECOND_LOTS")
            return
        ep.pending[p["intent"].id]=p["intent"]
        self._split_child_submit=True
        try:
            self._submit_intent(p["intent"],float(tick.bid_price),float(tick.ask_price),p["sigma"],p["decision_index"],ts_now=tick.ts_event,entry_override_qty=qty)
        finally:
            self._split_child_submit=False

    def _md_reconcile(self,ts):
        if self._pair_btc_tp_paused():
            return
        if not self._md_enabled():
            return
        ep=self._domain.episode
        if not ep or ep.id not in self._md_plans:
            return
        m=self._md_plans[ep.id]
        if m["p0"] is None or self._forced_close_reason or self._liquidating:
            return
        inst=self.cache.instrument(self.config.btc_id)
        step=inst.size_increment.as_decimal()
        positions=[p for p in self.cache.positions_open() if p.instrument_id==self.config.btc_id]
        held=positions[0].quantity.as_decimal() if positions else D(0)
        if positions and positions[0].is_long != (ep.side==1):
            raise ValueError("REAL_U_NATIVE_WRONG_SIDE")
        if not held:
            self._split_stop("BTC_FLAT")
        prices=u_prices(m["p0"],m["d3"],ep.side,inst.price_increment.as_decimal(),
            D(str(inst.taker_fee)),max(D(str(inst.maker_fee)),D(str(inst.taker_fee))))
        if m.get("allocated_entry") != ep.btc_entry_qty_exact:
            allocations=target_lots(int(held/step),m["consumed"])
            for i,lots in allocations.items():
                ep.btc_tp_target_lots[i]=ep.btc_tp_filled_lots.get(i,0)+lots
                ep.btc_tp_target_qty[i]=float(D(ep.btc_tp_target_lots[i])*step)
            m["allocated_entry"]=ep.btc_entry_qty_exact
        desired={i:ep.btc_tp_target_lots.get(i,0)-ep.btc_tp_filled_lots.get(i,0) for i in range(3) if i not in m["consumed"]}
        if sum(desired.values()) != int(held/step):
            raise ValueError("REAL_U_TARGET_INVENTORY_MISMATCH")
        signature=(m["p0"],ep.btc_entry_qty_exact)
        work=[(oid,i) for oid,i in self._pending_by_order.items() if i.action=="BTC_REDUCE" and i.episode_id==ep.id]
        # Cancel/ACK barrier: never overlap old and replacement leaves.
        if m.get("signature")!=signature and work:
            m["accepted"].clear()
            for oid,i in work:
                order=self.cache.order(ClientOrderId(oid))
                if order is not None and not order.is_closed and not order.is_pending_cancel:
                    self.cancel_order(order)
            self._md_coverage(ts,False,ep.id,"REPLACE_ACK_PENDING")
            return
        owned_levels={i.level for _,i in work}
        desired_to_submit={i:lots for i,lots in desired.items() if i not in owned_levels}
        if work and not desired_to_submit:
            return
        if not held:
            self._md_coverage(ts,True,ep.id,"FLAT")
            return
        if any(lots<=0 or (inst.min_quantity and D(lots)*step<inst.min_quantity.as_decimal()) or (inst.min_notional and D(lots)*step*prices[i]<inst.min_notional.as_decimal()) for i,lots in desired.items()):
            self._md_coverage(ts,False,ep.id,"PARTIAL_BELOW_THREE_VALID_LOTS")
            if m["first_done"]:
                self._md_log("UNDERSIZED_TERMINAL_FIRST_FAILCLOSED",ts,episode_id=ep.id,actual_inventory=held)
                self._begin_forced_close("REAL_U_INSUFFICIENT_PARTIAL_PROTECTION")
            return
        if m.get("signature")!=signature:
            m["generation"]+=1
            m["generations"][m["generation"]]=dict(required=set(desired),accepted=set(),authorized=False)
        m["signature"]=signature
        m["prices"]=prices
        self._bind_native_lots()
        self._md_coverage(ts,False,ep.id,"AWAITING_TARGET_ACCEPTANCE")
        for i,lots in desired_to_submit.items():
            # Domain quantities agree with native inventory; consumed levels
            # never receive new leaves, including late entry cancel-race fills.
            ep.btc_tp_target_lots[i]=ep.btc_tp_filled_lots.get(i,0)+lots
            ep.btc_tp_target_qty[i]=float(D(ep.btc_tp_target_lots[i])*step)
            ep.btc_tps.add(i)
            intent=self._domain._intent(ep,"BTC_REDUCE",-ep.side,i,
                quantity=float(D(lots)*step),reason=f"BTC_TP{i+1}",limit_price=float(prices[i]))
            ep.resting_reductions.add(intent.id)
            m["intent_generation"][intent.id]=m["generation"]
            self._submit_intent(intent,float(m["p0"]),float(m["p0"]),None,len(self._bars)-1,ts_now=ts)
        self._md_log("TARGETS_SUBMITTED",ts,episode_id=ep.id,p0=m["p0"],
            raw_causal_d3=m["d3"],prices=[str(x) for x in prices],
            actual_inventory=held,level_lots=desired)

    def _md_coverage(self,ts,complete,episode,reason):
        if complete and self._md_missing_since is not None:
            duration=max(0,ts-self._md_missing_since)
            self._md_missing_total_ns+=duration
            self._md_log("PROTECTION_RESTORED",ts,episode_id=episode,duration_ns=str(duration),reason=reason)
            self._md_missing_since=None
            self._md_missing_reason=None
        elif not complete and self._md_missing_since is None:
            self._md_missing_since=ts
            self._md_missing_reason=reason
            self._md_log("PROTECTION_EXCEPTION",ts,episode_id=episode,reason=reason)
        elif not complete and self._md_missing_reason!=reason:
            self._md_missing_reason=reason
            self._md_log("PROTECTION_EXCEPTION",ts,episode_id=episode,reason=reason,continuing_interval=True)

    def _md_cancel_terminal(self,intent,ts):
        if not self._md_enabled() or not intent or intent.action!="BTC_REDUCE":
            return
        m=self._md_plans.get(intent.episode_id)
        if m and intent.level not in m["consumed"]:
            m["accepted"].discard(intent.level)
            self._md_coverage(ts,False,intent.episode_id,"TARGET_CANCEL_ACK")

    def _md_reject(self,intent,ts):
        if self._md_enabled() and intent and intent.action=="BTC_REDUCE":
            self._md_log("TARGET_REJECT_STOP",ts,episode_id=intent.episode_id,level=intent.level)
            raise ValueError("REAL_U_NATIVE_TARGET_REJECT_STOP")

    def _md_accept(self,event):
        if not self._md_enabled():
            return
        intent=self._pending_by_order.get(str(event.client_order_id))
        if not intent or intent.action!="BTC_REDUCE":
            return
        m=self._md_plans.get(intent.episode_id)
        if not m:
            return
        oid=str(event.client_order_id)
        if oid in self._md_accepted_ids:
            return
        self._md_accepted_ids.add(oid)
        generation=m["intent_generation"][intent.id]
        m["order_generation"][oid]=generation
        historic=m["generations"][generation]
        historic["accepted"].add(intent.level)
        if historic["accepted"]>=historic["required"]:
            historic["authorized"]=True
        if generation==m["generation"]:
            m["accepted"].add(intent.level)
        audit=self._order_audit.get(str(event.client_order_id),{})
        submit=int(audit.get("submit_ns") or event.ts_event)
        self._md_log("TARGET_ACCEPTED",event.ts_event,episode_id=intent.episode_id,
            level=intent.level,generation=generation,order_id=str(event.client_order_id),ack_latency_ns=str(event.ts_event-submit))
        if m["accepted"]==set(range(3))-m["consumed"]:
            self._md_coverage(event.ts_event,True,intent.episode_id,"ALL_REMAINING_ACCEPTED")

    def _md_after_fill(self,intent,event):
        if not self._md_enabled() or not intent or not intent.action.startswith("BTC"):
            return
        m=self._md_plans.get(intent.episode_id)
        if not m:
            return
        if intent.action=="BTC_REDUCE":
            generation=m["order_generation"].get(str(event.client_order_id))
            historic=m["generations"].get(generation)
            if not historic or not historic["authorized"]:
                raise ValueError("REAL_U_TP_FILLED_BEFORE_THREE_ACCEPTED")
            m["touched"].add(intent.level)
            order=self.cache.order(event.client_order_id)
            if self._domain.episode and (intent.level in self._domain.episode.btc_filled_tps or (order is not None and order.status.name=="FILLED")):
                m["consumed"].add(intent.level)
                self._domain.episode.btc_filled_tps.add(intent.level)
                # A terminal old target during replacement cannot be restored
                # merely because the newer inventory allocation is larger.
                m["allocated_entry"]=None
            self._split_stop("FIRST_POSITIVE_TP_FILL")
            ep=self._domain.episode
            if ep:
                ep.sol_rights.clear()
                ep.sol_right_fraction.clear()
        if intent.action=="BTC_ENTRY":
            if m["accepted"]!=set(range(3))-m["consumed"]:
                self._md_coverage(event.ts_event,False,intent.episode_id,"ENTRY_FILL_REQUIRES_PROTECTION")
        self._md_reconcile(event.ts_event)

    def _md_report(self):
        return dict(events=self.market_redesign_audit,missing_three_tp_ns=str(self._md_missing_total_ns),
            open_protection_exception_since_ns=str(self._md_missing_since) if self._md_missing_since is not None else None)
