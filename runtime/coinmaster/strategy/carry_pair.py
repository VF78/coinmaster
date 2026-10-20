"""Default-off CHOP_PAIR_50_NET_v1 native residual-inventory lifecycle.

This module owns authorization only. Native positions/account/fills remain the
only inventory, money and execution sources. No synthetic funding or PnL book.
"""
from decimal import Decimal as D
from math import isfinite, log
from nautilus_trader.model.enums import BarAggregation, OrderSide
from coinmaster.domain.wave_overlay import btc_management_price

DAY = 86_400_000_000_000
HOUR = DAY // 24


def chop_snapshot(bars, ohlc, ts):
    """Only completed/available Daily history; seven transitions include today."""
    rows = [b for b in bars if int(b.close_time.timestamp()*1e9) <= ts
            and int(b.available_at.timestamp()*1e9) <= ts]
    if len(rows) < 91:
        return None
    times = [int(b.close_time.timestamp()*1e9) for b in rows]
    if times[-1] != ts or any(b-a != DAY for a,b in zip(times,times[1:])):
        return None
    if any(t not in ohlc for t in times):
        return None
    ema = None
    signs, tr = [], []
    previous = None
    for b,t in zip(rows,times):
        ema = b.btc_close if ema is None else (2/35)*b.btc_close+(33/35)*ema
        signs.append(1 if b.btc_close >= ema else -1)
        high,low = ohlc[t]
        if high < max(low,b.btc_close) or low > b.btc_close:
            return None
        tr.append(max(high-low,abs(high-previous),abs(low-previous)) if previous is not None else high-low)
        previous=b.btc_close
    atr=tr[0]
    for value in tr[1:]:
        atr=(2/15)*value+(13/15)*atr
    flips=sum(a*b < 0 for a,b in zip(signs[-8:],signs[-7:]))
    if flips < 2 or abs(rows[-1].btc_close-ema) > atr:
        return None
    x=[log(b.btc_close/a.btc_close) for a,b in zip(rows[-91:],rows[-90:])]
    y=[log(b.sol_close/a.sol_close) for a,b in zip(rows[-91:],rows[-90:])]
    mx,my=sum(x)/90,sum(y)/90
    var=sum((v-mx)**2 for v in x)
    beta=sum((a-mx)*(b-my) for a,b in zip(x,y))/var if var else 0
    if not isfinite(beta) or beta <= 0:
        return None
    return dict(beta=D(str(beta)), high=D(str(max(ohlc[t][0] for t in times[-7:]))),
                low=D(str(min(ohlc[t][1] for t in times[-7:]))), flips=flips,
                ema=str(ema), atr=str(atr), daily_close_ns=ts)


class CarryPairResearch:
    def _carry_init(self):
        self._carry=None
        self.carry_pair_audit=[]
        self.carry_pair_counts={}
        self._carry_skip_seen=set()
        self._carry_ohlc={int(t):(float(h),float(l)) for t,h,l in self.config.research_carry_daily_seed}
        self._carry_fees={}
        self._carry_used=set()
        self._carry_physical=False

    def _carry_enabled(self):
        return self.config.research_chop_pair

    def _carry_busy(self):
        return self._carry_enabled() and self._carry is not None

    def _carry_emit(self,event,ts,**values):
        self.carry_pair_counts[event]=self.carry_pair_counts.get(event,0)+1
        if event=="CLOSED_HOUR":
            return
        row=dict(event=event,timestamp_ns=ts,episode_id=self._carry["episode_id"] if self._carry else None,**values)
        self.carry_pair_audit.append({k:str(v) if isinstance(v,D) else v for k,v in row.items()})

    def _carry_daily_bar(self,bar):
        if self._carry_enabled():
            self._carry_ohlc[bar.ts_event]=(float(bar.high),float(bar.low))

    def _carry_daily(self,ts):
        if not self._carry_enabled():
            return False
        ep=self._domain.episode
        if self._carry is not None:
            if ep is not None and ep.btc_entry_vwap is not None:
                f=ep.side*(self._bars[-1].btc_close/btc_management_price(ep)-1)
                ep.best_f=max(ep.best_f,f,0.0)
                if ep.best_f>self._candidate.btc_close_trail_fraction and f<=ep.best_f-self._candidate.btc_close_trail_fraction:
                    self._carry_close("TRAIL",ts)
            key=(self._carry["episode_id"],ts)
            if key not in self._carry_skip_seen and self._current_signals[-1].side != self._carry["side"]:
                self._carry_skip_seen.add(key)
                self._carry_emit("SKIPPED_OPPOSITE_BTC_NO_BACKLOG",ts,signal_side=self._current_signals[-1].side)
            return True
        ep=self._domain.episode
        if ep is None or ep.id in self._carry_used or self._forced_close_reason or self._liquidating:
            return False
        if self._current_signals[-1].side == ep.side:
            return False
        btc=next((p for p in self.cache.positions_open() if p.instrument_id==self.config.btc_id),None)
        if btc is None or btc.quantity.as_decimal() <= 0:
            return False
        snapshot=chop_snapshot(self._bars,self._carry_ohlc,ts)
        if snapshot is None:
            return False
        self._carry_used.add(ep.id)
        self._carry=dict(episode_id=ep.id,phase="ARMING",admission_signal_ns=ts,
            side=ep.side,grant=False,intent=None,last_hour=None,hour_side=0,hour_count=0,**snapshot)
        self._carry_emit("ARM",ts,**snapshot)
        f=ep.side*(self._bars[-1].btc_close/btc_management_price(ep)-1)
        ep.best_f=max(ep.best_f,f,0.0)
        if ep.best_f>self._candidate.btc_close_trail_fraction and f<=ep.best_f-self._candidate.btc_close_trail_fraction:
            self._carry_close("TRAIL",ts)
            return True
        # Set ownership before cancellation: synchronous callbacks may re-plan.
        self._split_stop("CHOP_PAIR_ARM")
        self._accepted_reductions.clear()
        self._discard_queued_intents(lambda _:True)
        if self._mandatory_sol_exit is not None:
            self._domain.on_parent_terminal(self._mandatory_sol_exit[0].id)
            self._mandatory_sol_exit=None
        for order in list(self.cache.orders_open()):
            self.cancel_order(order)
        return True

    def _carry_money(self,ts,require_fees=False):
        ids=(self.config.btc_id,self.config.sol_id)
        positions=self.cache.positions_open()
        marks=[self._latest_marks.get(i) for i in ids]
        if any(m is None or not 0 <= ts-m.ts_event <= self.config.max_mark_age_ns for m in marks):
            return None
        if marks[0].ts_event != marks[1].ts_event or any(p.instrument_id not in ids for p in positions):
            return None
        accounts=[self.cache.account_for_venue(i.venue) for i in ids]
        if accounts[0] is None or accounts[0] is not accounts[1]:
            return None
        account=accounts[0];currency=account.base_currency
        balance=account.balance_total(currency) if currency is not None else None
        if balance is None:
            return None
        unreal=D(0);cost=D(0);oldfees=D(0);actual={}
        for p in positions:
            inst=self.cache.instrument(p.instrument_id)
            if inst is None or p.settlement_currency != currency:
                return None
            m=marks[ids.index(p.instrument_id)]
            u=p.unrealized_pnl(inst.make_price(m.price))
            fee=D(str(inst.taker_fee))
            if u is None or u.currency != currency or not fee.is_finite() or fee < 0:
                return None
            qty=p.quantity.as_decimal()
            actual[p.instrument_id]=p
            unreal+=u.as_decimal();cost+=qty*m.price*fee
            if require_fees:
                projection=self._carry_fees.get(p.instrument_id)
                signed=qty if p.is_long else -qty
                if projection is None or not projection["known"] or projection["signed"] != signed:
                    return None
                oldfees+=projection["fees"]
        return dict(equity=balance.as_decimal()+unreal,unreal=unreal,closefees=cost,
                    oldfees=oldfees,positions=actual,bm=marks[0].price,sm=marks[1].price)

    def _carry_close(self,reason,ts):
        c=self._carry
        if c is None:
            return
        if c["phase"] != "CLOSING":
            c["phase"]="CLOSING"
            self._carry_emit("GROUP_EXIT",ts,reason=reason)
        ep=self._domain.episode
        if ep is not None:
            ep.close_reason=reason
        self._group_close_reconciliation_pending=True
        self._begin_forced_close(reason)

    def _carry_inventory_valid(self):
        c=self._carry
        positions={p.instrument_id:p for p in self.cache.positions_open()}
        btc=positions.get(self.config.btc_id);sol=positions.get(self.config.sol_id)
        if btc is None or btc.is_long != (c["side"]==1) or btc.quantity.as_decimal()!=c["btc_qty"]:
            return False
        expected=c["sol_initial"]+c.get("filled",D(0))
        if expected>c["sol_target"]:
            return False
        if sol is None:
            return expected==0
        return sol.is_long==(c["side"]==-1) and sol.quantity.as_decimal()==expected

    def _carry_check(self,tick):
        if not self._carry_busy():
            return False
        c=self._carry;ts=tick.ts_event
        if self._forced_close_reason or self._liquidating or self.is_exiting():
            return True
        if c["phase"]=="CLOSING":
            self._carry_close("CHOP_PAIR_CLOSING",ts)
            return True
        if c["phase"]=="ACTIVE" and not self._carry_inventory_valid():
            self._carry_close("CHOP_PAIR_UNEXPECTED_INVENTORY",ts)
            return True
        # Unknown ACK/cache-inflight is still authoritative pending work.
        if self.cache.orders_open() or self.cache.orders_inflight() or self._pending_by_order:
            return True
        money=self._carry_money(ts,require_fees=c["phase"]=="ARMING")
        if money is None:
            if c["phase"]=="ARMING":
                self._carry_close("CHOP_PAIR_UNKNOWN_NATIVE",ts)
            return True
        btc=money["positions"].get(self.config.btc_id)
        sol=money["positions"].get(self.config.sol_id)
        bqty=btc.quantity.as_decimal() if btc else D(0)
        held=sol.quantity.as_decimal() if sol else D(0)
        if c["phase"]=="ARMING":
            if not btc or btc.is_long != (c["side"]==1) or sol and sol.is_long == btc.is_long:
                self._carry_close("CHOP_PAIR_NATIVE_SIDE",ts)
                return True
            nb=bqty*money["bm"];full=nb/c["beta"]
            if held*money["sm"] > full:
                self._carry_close("CHOP_PAIR_EXISTING_ABOVE_FULL_BETA",ts)
                return True
            inst=self.cache.instrument(self.config.sol_id);step=inst.size_increment.as_decimal()
            target=max(held,(D(".5")*nb/c["beta"]/money["sm"]//step)*step)
            quantity=target-held
            side=OrderSide.BUY if c["side"]==-1 else OrderSide.SELL
            if quantity and (not self._entries_enabled() or not self._tier_allows_increase(self.config.sol_id,side,quantity,ts)
                    or inst.min_quantity is not None and quantity<inst.min_quantity.as_decimal()
                    or inst.min_notional is not None and quantity*money["sm"]<inst.min_notional.as_decimal()):
                self._carry_close("CHOP_PAIR_ADMISSION_DENIED",ts)
                return True
            c.update(phase="ACTIVE",frozen_ns=ts,btc_qty=bqty,sol_initial=held,sol_target=target,
                quantity=quantity,benchmark=money["equity"]-money["unreal"]+money["oldfees"]+D(".001")*nb,
                E0=money["equity"],U0=money["unreal"],oldfees=money["oldfees"],btc_notional=nb)
            c["btc_actual_basis"]=str(btc.avg_px_open)
            c["sol_actual_basis"]=str(sol.avg_px_open) if sol else None
            self._carry_emit("FREEZE",ts,btc_actual_basis=c["btc_actual_basis"],sol_actual_basis=c["sol_actual_basis"],**{k:c[k] for k in ("beta","high","low","btc_qty","sol_initial","sol_target","quantity","benchmark","E0","U0","oldfees","btc_notional")})
        if money["equity"]-money["closefees"] >= c["benchmark"]:
            self._carry_emit("RECOVERY",ts,equity=money["equity"],closefees=money["closefees"],benchmark=c["benchmark"],
                             label="REMAINING_INVENTORY_RECOVERY")
            self._carry_close("CHOP_PAIR_RECOVERY",ts)
            return True
        if tick.instrument_id==self.config.sol_id and c["quantity"]>0:
            if not c["grant"]:
                c["grant"]=True
                c["intent"]=self._domain._intent(self._domain.episode,"SOL_ADD",-c["side"],None,
                    quantity=float(c["quantity"]),reason="CHOP_PAIR_SINGLE_GRANT")
                c["filled"]=D(0)
                self._carry_emit("GRANT",ts,quantity=c["quantity"],intent_id=c["intent"].id)
            # Same immutable economic intent; only unfilled native leaves retry.
            remaining=c["quantity"]-c["filled"]
            if remaining>0:
                i=c["intent"]
                self._domain.episode.pending[i.id]=i
                self._carry_physical=True
                try:
                    self._submit_intent(i,float(tick.bid_price),float(tick.ask_price),None,len(self._bars)-1,
                                        ts_now=ts,entry_override_qty=remaining)
                finally:
                    self._carry_physical=False
        return True

    def _carry_bar(self,bar):
        if not self._carry_busy() or self._carry["phase"]!="ACTIVE":
            return
        if bar.bar_type.instrument_id!=self.config.btc_id or bar.bar_type.spec.aggregation!=BarAggregation.HOUR:
            return
        c=self._carry;ts=bar.ts_event
        if ts<=c["frozen_ns"] or ts>self.clock.timestamp_ns() or c["last_hour"] is not None and ts<=c["last_hour"]:
            return
        close=D(str(bar.close));side=1 if close>c["high"] else -1 if close<c["low"] else 0
        c["hour_count"]=c["hour_count"]+1 if side and side==c["hour_side"] and c["last_hour"] is not None and ts-c["last_hour"]==HOUR else int(bool(side))
        c["last_hour"]=ts;c["hour_side"]=side
        self._carry_emit("CLOSED_HOUR",ts,side=side,count=c["hour_count"],close=close)
        if c["hour_count"]>=2:
            self._carry_close("CHOP_PAIR_RANGE_INVALIDATION",ts)

    def _carry_native_fill(self,event):
        if not self._carry_enabled():
            return
        iid=event.instrument_id
        if iid not in (self.config.btc_id,self.config.sol_id):
            return
        state=self._carry_fees.setdefault(iid,dict(signed=D(0),fees=D(0),known=True))
        q=event.last_qty.as_decimal()*(1 if event.order_side==OrderSide.BUY else -1)
        before=state["signed"];after=before+q
        inst=self.cache.instrument(iid)
        known=event.commission is not None and inst is not None and event.commission.currency==inst.quote_currency
        state["known"] &= known
        if before==0 or before*q>0:
            if known:state["fees"]+=event.commission.as_decimal()
        elif abs(q)<=abs(before):
            state["fees"]*=abs(after)/abs(before)
        else:
            state["known"]=False
        state["signed"]=after
        if after==0:
            state.update(fees=D(0),known=True)
        c=self._carry
        intent=self._pending_by_order.get(str(event.client_order_id))
        if c and c["phase"]=="ACTIVE":
            if intent is not None and intent.reason=="CHOP_PAIR_SINGLE_GRANT":
                c["filled"]+=abs(q)
                self._carry_emit("HEDGE_FILL",event.ts_event,quantity=abs(q),commission=event.commission.as_decimal())
                if c["filled"]>c["quantity"]:
                    self._carry_close("CHOP_PAIR_UNEXPECTED_INVENTORY",event.ts_event)
            else:
                self._carry_close("CHOP_PAIR_EXTERNAL_REDUCTION" if before*q<0 else "CHOP_PAIR_UNOWNED_INCREASE",event.ts_event)

    def _carry_flat(self):
        if self._carry_busy():
            self._carry_emit("NATIVE_TERMINAL_FLAT",self.clock.timestamp_ns())
            self._carry=None
