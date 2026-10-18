"""Opt-in original/conditional SOL ownership on the existing native executor.

Quantities and authorization credits only: no matching, cash or PnL ledger.
"""
from datetime import datetime, UTC
from decimal import Decimal as D
from nautilus_trader.model.identifiers import ClientOrderId
from nautilus_trader.model.enums import BarAggregation, OrderSide

HOUR=3_600_000_000_000


class ConditionalSolResearch:
    def _conditional_init(self):
        self._conditional=None
        self.conditional_audit=[]
        self._conditional_bars={}
        self._conditional_quote_seq=0
        self._conditional_physical=False

    def _conditional_enabled(self):
        return self.config.research_conditional_sol or self._risk_first_net_owner()

    def _conditional_emit(self,event,ts,**values):
        c=self._conditional
        if c is None:
            return
        ep=self._domain.episode
        positions={p.instrument_id:p for p in self.cache.positions_open()}
        btc=positions.get(self.config.btc_id);sol=positions.get(self.config.sol_id)
        combined=max(c["original_target"],c["qc"])
        if self.config.research_sol_risk_first=="dd-cov" and c.get("rf",{}).get("target") is not None:combined=c["rf"]["target"]
        row={"event":event,"timestamp_ns":ts,"episode_id":c["episode_id"],"side":c["side"],
            "btc_qty":str(btc.quantity.as_decimal() if btc else D(0)),
            "btc_actual_vwap":str(ep.btc_entry_vwap if ep else None),"beta":str(c["beta"]),
            "beta_frozen_ns":c["beta_ns"],"original_desired":str(c["original_target"]),
            "original_allocated":str(ep.sol_qty if ep else 0),"conditional_target":str(c["qc"]),
            "combined_target":str(combined),
            "actual_sol_qty":str(sol.quantity.as_decimal() if sol else D(0)),**values}
        (self.risk_first_sol_audit if self._risk_first_net_owner() else self.conditional_audit).append(row)

    def _conditional_state(self,ts):
        if not self._conditional_enabled() or self._domain.episode is None:
            return None
        ep=self._domain.episode
        if self._conditional is None or self._conditional["episode_id"]!=ep.id:
            self._conditional={"episode_id":ep.id,"side":ep.side,"beta":None,"beta_ns":None,
                "armed_ns":None,"active":False,"confirm":None,"last_mark_ns":None,
                "original_target":D(str(ep.sol_qty)),"adds":[],"exits":[],"qc":D(0),"qc_btc_qty":None,"retry_ns":0,"original_attempts":{}}
        c=self._conditional
        if c["beta"] is None and any(p.instrument_id==self.config.btc_id for p in self.cache.positions_open()):
            estimate=self._risk_first_beta_estimate(ts) if self._risk_first_net_owner() else self._cover_beta(ts)
            if estimate is not None:
                c["beta"],c["beta_ns"]=estimate[0],ts
                self._conditional_emit("BETA_FREEZE",ts)
        return c

    def _conditional_bar(self,bar):
        if not self.config.research_conditional_sol or bar.bar_type.instrument_id!=self.config.sol_id:
            return
        minutes=60 if bar.bar_type.spec.aggregation==BarAggregation.HOUR else 15
        ts=bar.ts_event;old=self._conditional_bars.get(minutes)
        if old and ts<=old[0]:
            return
        c=self._conditional
        if old and c and c["armed_ns"] is not None and ts>c["armed_ns"] and not c["active"]:
            side=-c["side"]
            if (side==1 and float(bar.close)>old[1]) or (side==-1 and float(bar.close)<old[2]):
                receipt=self.clock.timestamp_ns()
                c["confirm"]=(ts,receipt,self._conditional_quote_seq+1,minutes)
                self._conditional_emit("CONFIRM",receipt,bar_close_ns=ts,timeframe_minutes=minutes)
        self._conditional_bars[minutes]=(ts,float(bar.high),float(bar.low))

    def _conditional_original(self,intent,qty,price,sigma,index,ts):
        """Called after existing minimum/pause/native-margin admission. No fill replay."""
        c=self._conditional_state(ts)
        if c is None:
            return
        if self._risk_first_net_owner():self._risk_first_state(c)
        if any(t["intent"].id==intent.id for t in c["adds"]+c["exits"]):
            return
        task={"intent":intent,"remaining":qty,"sigma":sigma,"index":index,"price":price}
        if intent.action=="SOL_ADD":
            c["adds"].append(task);c["original_target"]+=qty
        else:
            task["remaining"]=min(qty,c["original_target"])
            c["exits"].append(task);c["original_target"]-=task["remaining"]
        if self._risk_first_net_owner():self._risk_first_original(intent,task["remaining"],ts)
        self._conditional_emit("ORIGINAL_AUTHORIZED",ts,action=intent.action,level=intent.level,quantity=str(task["remaining"]))
        tick=self.cache.quote_tick(self.config.sol_id)
        if tick is not None and tick.ts_event==ts:
            self._conditional_check(tick)

    def _conditional_original_increment(self,qty):
        c=self._conditional
        held=next((p.quantity.as_decimal() for p in self.cache.positions_open() if p.instrument_id==self.config.sol_id),D(0))
        if self._risk_first_net_owner() and c is not None:return self._risk_first_increment(qty,held)
        target=(c["original_target"] if c else D(str(self._domain.episode.sol_qty)))+qty
        return max(D(0),target-held)

    def _conditional_tasks_done(self,c):
        for name in ("adds","exits"):
            remaining=[]
            for t in c[name]:
                if t["remaining"]<=0:
                    ep=self._domain.episode
                    if t["intent"].action=="SOL_HALF_EXIT" and ep is not None and ep.sol_half_done:
                        self._domain.on_half_exit_decision(max(t["index"],len(self._bars)-1))
                    self._domain.on_parent_terminal(t["intent"].id)
                else:
                    remaining.append(t)
            c[name]=remaining

    def _conditional_assign(self,quantity,ts,price,task_ids=None):
        c=self._conditional;ep=self._domain.episode
        for t in c["adds"]:
            if task_ids is not None and t["intent"].id not in task_ids:
                continue
            q=min(quantity,t["remaining"])
            if q<=0:
                continue
            self._domain.on_sol_ownership_transfer(t["intent"].id,float(q),float(price),datetime.fromtimestamp(ts/1e9,UTC),t["sigma"])
            t["remaining"]-=q;quantity-=q
            self._conditional_emit("TRANSFER_TO_ORIGINAL",ts,quantity=str(q),ownership_transfer_credit=str(q*price),original_level=t["intent"].level,native_fill=False)
        self._conditional_tasks_done(c)

    def _conditional_release(self,quantity,ts):
        c=self._conditional
        for t in c["exits"]:
            q=min(quantity,t["remaining"])
            if q<=0:
                continue
            self._domain.on_sol_ownership_release(t["intent"].id,float(q))
            t["remaining"]-=q;quantity-=q
            self._conditional_emit("RELEASE_ORIGINAL",ts,quantity=str(q),reason=t["intent"].reason,native_fill=False)
        self._conditional_tasks_done(c)

    def _conditional_check(self,tick):
        if not self._conditional_enabled():
            return
        c=self._conditional_state(tick.ts_event)
        if c is None or self._forced_close_reason or self._liquidating or (self.config.deposit_runtime is not None and self._deposit.latched):
            return
        if self._risk_first_net_owner():return self._risk_first_check(tick,c)
        ep=self._domain.episode;ts=tick.ts_event
        positions={p.instrument_id:p for p in self.cache.positions_open()}
        btc=positions.get(self.config.btc_id);sol=positions.get(self.config.sol_id)
        held=sol.quantity.as_decimal() if sol else D(0);bqty=btc.quantity.as_decimal() if btc else D(0)
        bm=self._latest_marks.get(self.config.btc_id);sm=self._latest_marks.get(self.config.sol_id)
        fresh=bm is not None and 0<=ts-bm.ts_event<=self.config.max_mark_age_ns
        adverse=None
        if fresh and btc is not None and ep.btc_entry_vwap:
            adverse=-D(ep.side)*(bm.price/D(str(ep.btc_entry_vwap))-1)
            if adverse<=D(".01"):
                if c["armed_ns"] is not None or c["active"]:
                    self._conditional_emit("OFF",ts,adverse=str(adverse),btc_mark=str(bm.price))
                c.update(active=False,armed_ns=None,confirm=None)
            elif adverse>D(".02") and c["armed_ns"] is None:
                c["armed_ns"]=ts
                self._conditional_emit("ARM",ts,adverse=str(adverse),btc_mark=str(bm.price))
        if not bqty and ep.btc_initial_qty>0:
            # A native BTC-flat receipt invalidates all remaining BTC TP leaves.
            for order in self.cache.orders_open():
                if order.instrument_id==self.config.btc_id and order.is_reduce_only:
                    self.cancel_order(order)
        if not bqty:
            c.update(active=False,armed_ns=None,confirm=None,qc=D(0))
            # BTC-flat revokes protection only; original overlay authority survives.
        if tick.instrument_id==self.config.sol_id:
            self._conditional_quote_seq+=1
            confirm=c["confirm"]
            if (not c["active"] and confirm and self._conditional_quote_seq>=confirm[2]
                and ts>=confirm[1] and fresh and adverse is not None and adverse>D(".02") and bqty and c["beta"] is not None):
                c["active"]=True;c["confirm"]=None
                self._conditional_emit("ACTIVATE",ts,adverse=str(adverse),confirmation_bar_ns=confirm[0],confirmation_received_ns=confirm[1],timeframe_minutes=confirm[3])
        if c["active"] and c["qc_btc_qty"]!=bqty and fresh and sm is not None and 0<=ts-sm.ts_event<=self.config.max_mark_age_ns:
            inst=self.cache.instrument(self.config.sol_id);step=inst.size_increment.as_decimal()
            c["qc"]=(D(".5")*bqty*bm.price/c["beta"]/sm.price//step)*step
            c["qc_btc_qty"]=bqty
            self._conditional_emit("QC_LATCH",ts,btc_mark=str(bm.price),sol_mark=str(sm.price),trigger="ACTIVATION_OR_ACTUAL_BTC_QUANTITY_CHANGE")
        elif not c["active"]:
            c["qc"]=D(0);c["qc_btc_qty"]=None
        target=max(c["original_target"],c["qc"])
        return self._conditional_reconcile(tick,c,ep,btc,sol,held,bqty,target,ts)

    def _conditional_reconcile(self,tick,c,ep,btc,sol,held,bqty,target,ts):
        work=[(oid,i) for oid,i in self._pending_by_order.items() if i.action.startswith("SOL")]
        if work:
            for oid,i in work:
                order=self.cache.order(ClientOrderId(oid))
                if order is not None and not order.is_closed:
                    leaves=order.leaves_qty.as_decimal()
                    stale_add=i.action=="SOL_ADD" and (not bqty and not c["adds"] or held+leaves>target or not c["active"] and not c["adds"])
                    stale_reduce=i.action!="SOL_ADD" and held-leaves<target
                    if stale_add or stale_reduce:
                        self.cancel_order(order)
            return  # Unknown ACK is owned too; no transfer of reserved-closing inventory.
        if tick.instrument_id!=self.config.sol_id:
            return
        if sol is not None and sol.is_long != (ep.side==-1):
            raise ValueError("CONDITIONAL_SOL_WRONG_NATIVE_SIDE")
        # Ownership releases can satisfy an original exit while protection retains inventory.
        original=D(str(ep.sol_qty));protective=max(D(0),held-original)
        release=min(max(D(0),original-c["original_target"]),max(D(0),target-c["original_target"]-protective))
        if release:
            self._conditional_release(release,ts)
        # Transfers with no native increment are atomic after original admission.
        if c["adds"] and held>=target:
            self._conditional_assign(max(D(0),held-D(str(ep.sol_qty))),ts,tick.ask_price.as_decimal() if ep.side==-1 else tick.bid_price.as_decimal())
        delta=target-held
        inst=self.cache.instrument(self.config.sol_id);step=inst.size_increment.as_decimal()
        quantity=(abs(delta)//step)*step
        if quantity<=0:
            self._conditional_tasks_done(c)
            if not btc and not sol and self._group_close_reconciliation_pending:
                self._reconcile_group_flat()  # Existing authorized close only; TP-flat retains its episode.
            return
        if delta>0 and (not self._entries_enabled() or ts<c["retry_ns"] and not c["adds"] or not bqty and not c["adds"]):
            return
        action="SOL_ADD" if delta>0 else "SOL_EXIT"
        i=self._domain._intent(ep,action,-ep.side if delta>0 else ep.side,None,quantity=float(quantity),reason="CONDITIONAL_NET_ADD" if delta>0 else "CONDITIONAL_NET_EXIT")
        c["physical_intent"]=i.id
        bound=tuple(t["intent"].id for t in c["adds"]) if delta>0 else ()
        if delta>0:
            c["original_attempts"][i.id]=bound
        self._conditional_emit("TARGET" if delta>0 else "TRIM",ts,quantity=str(quantity),reason=i.reason,physical_intent=i.id,original_attempt_ids=list(bound))
        self._conditional_physical=True
        try:
            self._submit_intent(i,float(tick.bid_price),float(tick.ask_price),None,len(self._bars)-1,ts_now=ts)
        finally:
            self._conditional_physical=False

    def _conditional_fill(self,intent,quantity,price,ts):
        c=self._conditional;ep=self._domain.episode
        if c is None or ep is None:
            return
        q=D(str(quantity));px=D(str(price));when=datetime.fromtimestamp(ts/1e9,UTC)
        original_native=D(0)
        if intent.action=="SOL_ADD":
            bound=c["original_attempts"].get(intent.id,())
            # Only now is a required native original admission fill-confirmed.
            held=next((p.quantity.as_decimal() for p in self.cache.positions_open() if p.instrument_id==self.config.sol_id),D(0))
            available=max(D(0),held-D(str(ep.sol_qty))-q)
            if c["adds"] and available:
                self._conditional_assign(available,ts,px,task_ids=bound)
            for t in c["adds"]:
                if t["intent"].id not in bound:
                    continue
                part=min(q,t["remaining"])
                if part<=0:
                    continue
                self._domain.on_fill(t["intent"].id,float(part),price,when,t["sigma"],decision_index=t["index"])
                t["remaining"]-=part;q-=part;original_native+=part
        else:
            for t in c["exits"]:
                part=min(q,t["remaining"],D(str(ep.sol_qty)))
                if part<=0:
                    continue
                self._domain.on_fill(t["intent"].id,float(part),price,when,t["sigma"],decision_index=t["index"])
                t["remaining"]-=part;q-=part;original_native+=part
        self._conditional_tasks_done(c)
        self._conditional_emit("NATIVE_FILL",ts,physical_intent=intent.id,action=intent.action,quantity=str(quantity),price=str(price),original_native_quantity=str(original_native),conditional_native_quantity=str(q))

    def _conditional_cancel_original_adds(self,ts):
        c=self._conditional
        if c is None:
            return
        for t in c["adds"]:
            c["original_target"]-=t["remaining"]
            self._domain.on_parent_terminal(t["intent"].id)
        c["adds"]=[]
        self._conditional_emit("ORIGINAL_UNFILLED_CANCELED",ts)

    def _conditional_attempt_terminal(self,intent,ts,cause,order_id=None):
        if not self._conditional_enabled() or self._conditional is None or intent is None or intent.reason!="CONDITIONAL_NET_ADD":
            return
        c=self._conditional
        bound=c["original_attempts"].pop(intent.id,None)
        if bound is None:
            return  # ACK is not terminal; repeated native receipts are idempotent.
        retained=[];released=D(0)
        for t in c["adds"]:
            if t["intent"].id in bound:
                released+=t["remaining"]
                c["original_target"]-=t["remaining"]
                self._domain.on_parent_terminal(t["intent"].id)
            else:
                retained.append(t)
        c["adds"]=retained
        if self._risk_first_net_owner():self._risk_first_original_terminal(released)
        self._conditional_emit("ORIGINAL_ATTEMPT_TERMINAL",ts,physical_intent=intent.id,
            native_order_id=order_id,terminal_cause=cause,original_attempt_ids=list(bound),
            unfilled_original_authorization_released=str(released))

    def _conditional_failed(self,intent,ts,order_id=None):
        if not self._conditional_enabled() or self._conditional is None:
            return
        if intent and intent.reason=="CONDITIONAL_NET_ADD":
            self._conditional_attempt_terminal(intent,ts,"DENIED_REJECTED_EXPIRED",order_id)
            self._conditional["retry_ns"]=ts+HOUR
            self._conditional_emit("NATIVE_ADD_DENIED",ts)
