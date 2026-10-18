"""Opt-in split/coverage research state on the existing native strategy.

No matching, money ledger, or parallel order owner lives here. Native cache,
existing pending mappings and callbacks remain authoritative.
"""
from collections import deque
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from math import isfinite, sqrt

from nautilus_trader.model.identifiers import ClientOrderId
from nautilus_trader.model.enums import BarAggregation, OrderSide, TimeInForce

D = Decimal
HOUR = 3_600_000_000_000
DAY = 24 * HOUR


class SplitCoverResearch:
    def _split_cover_init(self):
        self._split_parent = None
        self.split_parent_audit = []
        self.cover_audit = []
        self._cover_cycle = None
        self._cover_hours = {}
        self._cover_returns = deque(maxlen=720)
        self._cover_last_hour = None
        self._cover_previous_closes = None
        self._cover_sol_bar = None
        self._cover_confirm = None
        self._cover_quote_sequence = 0
        self._split_child_submit = False

    def _cover_seed(self, rows):
        for ts, btc, sol in rows:
            if self._cover_last_hour is not None and ts != self._cover_last_hour+HOUR:
                raise ValueError("COVER_HOURLY_SEED_GAP")
            closes=(btc,sol)
            if self._cover_previous_closes is not None:
                self._cover_returns.append(tuple(a/b-1 for a,b in zip(closes,self._cover_previous_closes)))
            self._cover_last_hour,self._cover_previous_closes=ts,closes

    def _split_cover_report(self):
        return {
            "parents": [{k:(str(v) if isinstance(v,D) else v) for k,v in p.items() if k!="intent"} for p in self.split_parent_audit],
            "cover": [{k:(str(v) if isinstance(v,D) else v) for k,v in r.items()} for r in self.cover_audit],
            "beta_method": "720_COMPLETED_1H_SIMPLE_RETURNS_SOL_ON_BTC_FROZEN_PER_BTC_EPISODE",
            "coverage_basis": "ACTUAL_NATIVE_BTC_SOL_QUANTITIES_AND_CURRENT_MARKS",
        }

    def _cover_bar(self, bar):
        if not self.config.research_sol_cover:
            return
        iid, ts = bar.bar_type.instrument_id, bar.ts_event
        if bar.bar_type.spec.aggregation == BarAggregation.HOUR:
            pair = self._cover_hours.setdefault(ts, {})
            pair[iid] = float(bar.close)
            if len(pair) == 2 and (self._cover_last_hour is None or ts > self._cover_last_hour):
                closes = (pair[self.config.btc_id], pair[self.config.sol_id])
                if self._cover_previous_closes is not None and ts == self._cover_last_hour + HOUR:
                    self._cover_returns.append(tuple(a/b-1 for a,b in zip(closes,self._cover_previous_closes)))
                elif self._cover_last_hour is not None:
                    self._cover_returns.clear()  # Gaps cannot become invented hourly returns.
                self._cover_previous_closes, self._cover_last_hour = closes, ts
                self._cover_hours = {k:v for k,v in self._cover_hours.items() if k >= ts}
        elif iid == self.config.sol_id:
            old = self._cover_sol_bar
            if old is not None and ts <= old[0]:
                return
            c = self._cover_cycle
            if old and c and c.get("armed_ns") is not None and ts > c["armed_ns"]:
                side = -c["side"]
                if (side == 1 and float(bar.close) > old[1]) or (side == -1 and float(bar.close) < old[2]):
                    self._cover_confirm = (ts, self.clock.timestamp_ns(), self._cover_quote_sequence + 1)
            self._cover_sol_bar = (ts,float(bar.high),float(bar.low))

    def _cover_beta(self, ts_now):
        if len(self._cover_returns) != 720 or self._cover_last_hour is None or not 0 <= ts_now-self._cover_last_hour <= HOUR:
            return None
        x,y = zip(*self._cover_returns)
        mx,my = sum(x)/720,sum(y)/720
        vx,vy = sum((a-mx)**2 for a in x),sum((a-my)**2 for a in y)
        cov = sum((a-mx)*(b-my) for a,b in self._cover_returns)
        if vx <= 0 or vy <= 0:
            return None
        beta, corr = cov/vx,cov/sqrt(vx*vy)
        return (D(str(beta)),D(str(corr))) if isfinite(beta) and D("0.2") < D(str(beta)) < D("4") else None

    def _split_prepare(self, intent, quantity, step, ts_now, sigma, decision_index):
        if not self.config.research_btc_split50 or self._split_child_submit:
            return quantity
        if self._split_parent and self._split_parent["episode_id"] == intent.episode_id:
            raise ValueError("SPLIT_DUPLICATE_LOGICAL_PARENT")
        lots = int(quantity/step)
        first = max(1,lots//2)
        p = {"episode_id":intent.episode_id,"intent":intent,"quantity":quantity,"first_quantity":D(first)*step,
             "filled":D(0),"first_notional":D(0),"first_filled":D(0),"first_vwap":None,
             "start_ns":ts_now,"deadline_ns":min(ts_now+4*HOUR,((ts_now//DAY)+1)*DAY-60_000_000_000),
             "sigma":sigma,"decision_index":decision_index,"fallback":False,"closed":False,
             "cancelled":D(0),"step":step,"side":intent.side,"single_lot_immediate":lots==1}
        self._split_parent=p
        self.split_parent_audit.append(p)
        self._domain.episode.btc_target_basis_qty=float(quantity)
        return p["first_quantity"]

    def _split_unfinished(self):
        p=self._split_parent
        return bool(p and not p["closed"] and p["filled"] < p["quantity"])

    def _split_native_fill(self,intent,event):
        p=self._split_parent
        if intent.action != "BTC_ENTRY" or not p or p["episode_id"]!=intent.episode_id:
            return
        qty=event.last_qty.as_decimal()
        if p["filled"]+qty > p["quantity"]:
            raise ValueError("SPLIT_PARENT_OVERFILL")
        before=p["filled"]
        p["filled"]+=qty
        if p.get("stop_reason"):
            p["cancelled"]=p["quantity"]-p["filled"]
        first_qty=min(qty,max(D(0),p["first_quantity"]-before))
        if first_qty:
            p["first_filled"]+=first_qty
            p["first_notional"]+=first_qty*event.last_px.as_decimal()
            p["first_vwap"]=p["first_notional"]/p["first_filled"]
        if self.config.research_btc_split_planref_v1 and p["first_filled"] == p["first_quantity"]:
            ep = self._domain.episode
            if ep is not None and ep.id == p["episode_id"] and ep.btc_planref_vwap is None:
                ep.btc_planref_vwap = p["first_vwap"]
                p["management_reference_v1"] = p["first_vwap"]
                p["management_reference_frozen_ns"] = event.ts_event
        if p["filled"]==p["quantity"]:
            p["closed"]=True

    def _split_stop(self,reason):
        p=self._split_parent
        if not p or p["closed"]:
            return
        p["closed"]=True
        p["cancelled"]=p["quantity"]-p["filled"]
        p["stop_reason"]=reason
        for order in list(self.cache.orders_open()):
            intent=self._pending_by_order.get(str(order.client_order_id))
            if intent and intent.action=="BTC_ENTRY" and intent.episode_id==p["episode_id"]:
                self.cancel_order(order)

    def _split_check(self,tick):
        if not self._split_unfinished() or tick.instrument_id!=self.config.btc_id:
            return
        p=self._split_parent
        ep=self._domain.episode
        if not ep or ep.id!=p["episode_id"] or self._forced_close_reason or self._liquidating or not self._entries_enabled():
            self._split_stop("CLOSE_OR_PAUSE_OR_DP")
            return
        # An actual early positive TP ends discount waiting, before reductions
        # can be admitted. Zero omitted levels are never early TP triggers.
        if tick.ts_event >= ((p["start_ns"]//DAY)+1)*DAY:
            self._split_stop("UTC_DAY_COMPLETION_FAILED")
            return
        px=tick.bid_price.as_decimal() if p["side"]==1 else tick.ask_price.as_decimal()
        reference = ep.btc_planref_vwap if ep.btc_planref_vwap is not None else ep.btc_entry_vwap
        early=reference and any(level>0 and (px>=D(str(reference))*(1+D(str(level))) if p["side"]==1 else px<=D(str(reference))*(1-D(str(level)))) for level in ep.wave_levels or ())
        if tick.ts_event>=p["deadline_ns"] or early:
            p["fallback"]=True
            p.setdefault("completion_reason","EARLY_TP" if early else "DEADLINE")
        owned=[(oid,i) for oid,i in self._pending_by_order.items() if i.action=="BTC_ENTRY" and i.episode_id==p["episode_id"]]
        if owned:
            if p["fallback"]:
                for oid,_ in owned:
                    order=self.cache.order(ClientOrderId(oid))
                    if order is not None and not order.is_closed and order.order_type.name=="LIMIT":
                        self.cancel_order(order)
            return  # Unknown ACK is an owned order, even absent from cache.
        # Normal terminal processing may remove only child pending, not the
        # logical parent. Restore the same intent identity for the next child.
        ep.pending[p["intent"].id]=p["intent"]
        qty=p["quantity"]-p["filled"]
        first_remaining=p["first_quantity"]-p["filled"]
        if first_remaining>0:
            qty=min(qty,first_remaining)
        self._split_child_submit=True
        try:
            self._submit_intent(p["intent"],float(tick.bid_price),float(tick.ask_price),p["sigma"],p["decision_index"],ts_now=tick.ts_event,entry_override_qty=qty)
        finally:
            self._split_child_submit=False

    def _split_tp_ioc_eligible(self,intent):
        if not self.config.research_btc_split_tp_ioc or intent.action!="BTC_REDUCE":
            return False
        p=self._split_parent
        ep=self._domain.episode
        return bool(p and ep and p["episode_id"]==intent.episode_id==ep.id
            and p["closed"] and p["filled"]==p["quantity"] and not p["cancelled"]
            and not self._forced_close_reason and not self._liquidating
            and intent.level is not None and ep.wave_levels[intent.level]>0)

    def _split_limit(self,intent,instrument,quantity):
        p=self._split_parent
        if not p or not self._split_child_submit or p["fallback"] or p["filled"]<p["first_quantity"]:
            return None
        from coinmaster.strategy.wave_overlay import _native_limit_price
        raw=p["first_vwap"]*(1-self.config.research_btc_split_discount*p["side"])
        rounding=ROUND_FLOOR if p["side"]==1 else ROUND_CEILING
        step=instrument.price_increment.as_decimal()
        price=_native_limit_price(instrument,(raw/step).to_integral_value(rounding=rounding)*step)
        return self.order_factory.limit(instrument_id=instrument.id,order_side=OrderSide.BUY if p["side"]==1 else OrderSide.SELL,
            quantity=instrument.make_qty(quantity),price=price,time_in_force=TimeInForce.GTC,post_only=True,reduce_only=False)

    def _cover_native_fill(self, intent, event):
        cycle=self._cover_cycle
        if not cycle or cycle["episode_id"]!=intent.episode_id or intent.action!="SOL_ADD":
            return
        if intent.reason=="SOL_COVER_BASE" and not cycle.get("base_anchor_complete",False):
            before=cycle.get("base_anchor_qty",D(0))
            quantity=min(event.last_qty.as_decimal(),max(D(0),cycle.get("base_anchor_target",D(0))-before))
            if quantity>0:
                cycle["base_anchor_qty"]=before+quantity
                cycle["base_anchor_notional"]=cycle.get("base_anchor_notional",D(0))+quantity*event.last_px.as_decimal()
                cycle["anchor"]=cycle["base_anchor_notional"]/cycle["base_anchor_qty"]
                if not before:
                    cycle["start_ns"]=event.ts_event
                    cycle["expiry_ns"]=((event.ts_event//DAY)+1)*DAY-60_000_000_000
                cycle["base_anchor_complete"]=cycle["base_anchor_qty"]>=cycle["base_anchor_target"]
                self.cover_audit.append({"event":"COVER_ANCHOR","episode_id":intent.episode_id,
                    "timestamp_ns":event.ts_event,"quantity":str(cycle["base_anchor_qty"]),
                    "notional":str(cycle["base_anchor_notional"]),"anchor":str(cycle["anchor"]),
                    "complete":cycle["base_anchor_complete"],"start_ns":cycle["start_ns"]})
            return
        if intent.reason!="SOL_COVER_TACTICAL":
            return
        instrument=self.cache.instrument(event.instrument_id)
        if event.commission is None or event.commission.currency!=instrument.quote_currency:
            raise ValueError("COVER_TACTICAL_FEE_RECEIPT_MISSING")
        cycle["tactical_fill_qty"]=cycle.get("tactical_fill_qty",D(0))+event.last_qty.as_decimal()
        cycle["tactical_fill_notional"]=cycle.get("tactical_fill_notional",D(0))+event.last_qty.as_decimal()*event.last_px.as_decimal()
        cycle["tactical_fill_fees"]=cycle.get("tactical_fill_fees",D(0))+event.commission.as_decimal()
        self.cover_audit.append({"event":"TACTICAL_NATIVE_BASIS","episode_id":intent.episode_id,
            "timestamp_ns":event.ts_event,"quantity":str(cycle["tactical_fill_qty"]),
            "notional":str(cycle["tactical_fill_notional"]),"fees":str(cycle["tactical_fill_fees"])})

    def _cover_check(self,tick):
        if not self.config.research_sol_cover or tick.instrument_id!=self.config.sol_id:
            return
        self._cover_quote_sequence+=1
        ep=self._domain.episode
        if ep is None or self._forced_close_reason or self._liquidating or (self.config.deposit_runtime is not None and self._deposit.latched):
            return
        positions={p.instrument_id:p for p in self.cache.positions_open()}
        btc,sol=positions.get(self.config.btc_id),positions.get(self.config.sol_id)
        cycle=self._cover_cycle
        if not cycle or cycle["episode_id"]!=ep.id:
            if btc is None:
                return  # No SOL anchor/clock for an unfilled BTC intention.
            estimate=self._cover_beta(tick.ts_event)
            if estimate is None:
                return
            cycle=self._cover_cycle={"episode_id":ep.id,"side":ep.side,"beta":estimate[0],"correlation":estimate[1],
                 "anchor":None,"base_anchor_complete":False,"start_ns":tick.ts_event,
                 "expiry_ns":((tick.ts_event//DAY)+1)*DAY-60_000_000_000,"armed_ns":None,"tactical":False,"used":False}
            self._cover_confirm=None
            self.cover_audit.append({"event":"COVER_START",**cycle})
        # Every unresolved SOL child blocks a competing owner, including
        # unknown transport ACK. Adds are canceled first after BTC shrink.
        work=[(oid,i) for oid,i in self._pending_by_order.items() if i.action.startswith("SOL")]
        mark=self._latest_marks.get(self.config.btc_id)
        if mark is None or not 0<=tick.ts_event-mark.ts_event<=self.config.max_mark_age_ns:
            return
        executable=tick.ask_price.as_decimal() if ep.side==-1 else tick.bid_price.as_decimal()
        base=D("0.5")*(btc.quantity.as_decimal() if btc else D(0))*mark.price/cycle["beta"]/executable
        inst=self.cache.instrument(self.config.sol_id)
        step=inst.size_increment.as_decimal()
        base=(base//step)*step
        held=sol.quantity.as_decimal() if sol else D(0)
        if sol and sol.is_long != (ep.side==-1):
            raise ValueError("COVER_NATIVE_SOL_WRONG_SIDE")
        # Tactical risk is removed before resizing base after any BTC reduction.
        bqty=btc.quantity.as_decimal() if btc else D(0)
        if bqty<cycle.get("last_btc_qty",bqty):
            cycle["tactical"]=False
        cycle["last_btc_qty"]=bqty
        px=tick.bid_price.as_decimal() if ep.side==-1 else tick.ask_price.as_decimal()
        anchor_ready=cycle.get("base_anchor_complete",False)
        adverse=(cycle["anchor"]-px)/cycle["anchor"]*(-ep.side) if anchor_ready else D(0)
        if not cycle["used"] and cycle["armed_ns"] is None and adverse>=D("0.005"):
            cycle["armed_ns"]=tick.ts_event
        confirm=self._cover_confirm
        if (anchor_ready and self.config.research_sol_cover>D("0.5") and not cycle["used"] and bqty>0
            and tick.ts_event<=cycle["start_ns"]+4*HOUR and cycle["armed_ns"] is not None
            and confirm and confirm[0]>cycle["armed_ns"] and confirm[2]==self._cover_quote_sequence
            and confirm[0]<=confirm[1]<=tick.ts_event and 0<=tick.ts_event-confirm[0]<=60_000_000_000
            and (cycle["anchor"]-executable)/cycle["anchor"]*(-ep.side)>=D("0.0025")):
            cycle["tactical"]=True
            cycle["used"]=True
            cycle["tactical_entry_price"]=executable
        if cycle["tactical"]:
            qty=cycle.get("tactical_fill_qty",D(0))
            notional=cycle.get("tactical_fill_notional",D(0))
            fees=cycle.get("tactical_fill_fees",D(0))
            fee=D(str(inst.taker_fee))
            gain=(-ep.side)*(px*qty-notional)-fees-fee*px*qty
            recovered=qty>0 and (-ep.side)*(px-cycle["anchor"])>=0 and gain>0
            if recovered or tick.ts_event>=cycle["expiry_ns"]:
                cycle["tactical"]=False
        tactical_add_allowed=(anchor_ready and tick.ts_event<=cycle["start_ns"]+4*HOUR
            and tick.ts_event<cycle["expiry_ns"]
            and (cycle["anchor"]-executable)/cycle["anchor"]*(-ep.side)>=D("0.0025"))
        target=base*(self.config.research_sol_cover/D("0.5")) if cycle["tactical"] else base
        target=(target//step)*step
        # No optional fallback: a partially filled tactical budget can retain
        # actual exposure, but cannot keep buying after price/window expiry.
        if cycle["tactical"] and not tactical_add_allowed:
            target=max(base,min(target,held))
        if work:
            revoke_tactical=not cycle["tactical"] or not tactical_add_allowed
            for oid,i in work:
                if i.action=="SOL_ADD" and (held>target or target<cycle.get("target_quantity",target) or not btc
                        or (i.reason=="SOL_COVER_TACTICAL" and revoke_tactical)):
                    order=self.cache.order(ClientOrderId(oid))
                    if order is not None and not order.is_closed:
                        self.cancel_order(order)
            return
        hour=self._cover_last_hour
        if bqty and hour is not None and hour>cycle.get("drift_checked_hour",cycle["start_ns"]):
            solmark=self._latest_marks.get(self.config.sol_id)
            if solmark is not None and 0<=tick.ts_event-solmark.ts_event<=self.config.max_mark_age_ns:
                actual=held*solmark.price*cycle["beta"]/(bqty*mark.price)
                desired=self.config.research_sol_cover if cycle["tactical"] else D("0.5")
                if abs(actual-desired)>D("0.05"):
                    cycle["rebalance_hour"]=hour
                    self.cover_audit.append({"event":"COVER_HOURLY_DRIFT","episode_id":ep.id,
                        "timestamp_ns":tick.ts_event,"hour_close_ns":hour,"actual":str(actual),"desired":str(desired)})
                cycle["drift_checked_hour"]=hour
        budget=(bqty,cycle["tactical"],cycle.get("rebalance_hour"))
        if cycle.get("budget")!=budget:
            cycle["target_quantity"]=target
        else:
            target=cycle["target_quantity"]
        if cycle["tactical"] and not tactical_add_allowed:
            target=max(base,min(target,held))
        delta=target-held
        # Retarget BTC changes/tactical transitions and completed-hour drift;
        # price noise alone does not create minute-scale churn.
        if cycle.get("budget")==budget and abs(delta)<step:
            return
        if cycle.get("budget")==budget and not cycle.get("incomplete",False):
            return
        if delta>0 and not self._entries_enabled():
            cycle["incomplete"]=True
            return  # Do not consume a base target while paused.
        if delta>0 and tick.ts_event<cycle.get("retry_after_ns",0):
            return
        cycle["budget"]=budget
        if abs(delta)<step:
            cycle["incomplete"]=False
            return
        action="SOL_ADD" if delta>0 else "SOL_EXIT"
        if action=="SOL_ADD" and not self._entries_enabled():
            return
        intent=self._domain._intent(ep,action,-ep.side if delta>0 else ep.side,None,quantity=float(abs(delta)),reason="SOL_COVER_TACTICAL" if cycle["tactical"] else "SOL_COVER_BASE")
        self.cover_audit.append({"event":"COVER_TARGET","timestamp_ns":tick.ts_event,"episode_id":ep.id,"btc_qty":str(bqty),"held":str(held),"target":str(target),"beta":str(cycle["beta"]),"tactical":cycle["tactical"],"confirmation_ns":confirm[0] if cycle["tactical"] and confirm else None,"confirmation_receipt_ns":confirm[1] if cycle["tactical"] and confirm else None})
        cycle["incomplete"]=True
        if action=="SOL_ADD" and not cycle.get("base_anchor_target") and not cycle["tactical"]:
            cycle["base_anchor_target"]=target
        self._submit_intent(intent,float(tick.bid_price),float(tick.ask_price),None,len(self._bars)-1,ts_now=tick.ts_event)

    def _split_cover_margin_reserve(self,instrument_id,prospective,ts_now):
        p=self._split_parent
        if p and not p["closed"] and instrument_id==self.config.btc_id:
            prospective=p["side"]*max(abs(prospective),p["quantity"])
        if self.config.research_sol_cover and instrument_id==self.config.sol_id:
            ep=self._domain.episode
            if ep is not None:
                cycle=self._cover_cycle
                estimate=(cycle["beta"],cycle["correlation"]) if cycle and cycle["episode_id"]==ep.id else self._cover_beta(ts_now)
                if estimate is None:
                    raise ValueError("COVER_BETA_NOT_READY")
                btcmark=self._latest_marks.get(self.config.btc_id)
                solmark=self._latest_marks.get(self.config.sol_id)
                if not btcmark or not solmark:
                    raise ValueError("COVER_MARK_MISSING")
                btc=next((q for q in self.cache.positions_open() if q.instrument_id==self.config.btc_id),None)
                full=D(str(ep.btc_net_planned_qty)) if not btc or (p and not p["closed"]) else btc.quantity.as_decimal()
                required=D("0.5")*full*btcmark.price/estimate[0]/solmark.price
                prospective=-ep.side*max(abs(prospective),required)
        return prospective
