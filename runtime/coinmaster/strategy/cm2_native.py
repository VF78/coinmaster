"""Independent thin Nautilus Strategy adapter for CM2 research.

Native cache, account, orders, fills and funding module remain authoritative.
This module has no import from WaveOverlay or its research mixins.
"""
from __future__ import annotations
from collections import deque
from dataclasses import asdict
from decimal import Decimal
from nautilus_trader.config import StrategyConfig
from nautilus_trader.core.data import Data
from nautilus_trader.model.data import CustomData
from nautilus_trader.model.data import BarType, DataType
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.identifiers import InstrumentId, ClientId
from nautilus_trader.trading.strategy import Strategy
from coinmaster.strategy.cm2_policy import (
    Config, State, Snapshot, Features, Hour, PairedHourBuilder, features, decide, D, ZERO)
from coinmaster.strategy.cm2_execution import ExecutionLimits, order_plan, stage_targets
from coinmaster.venues.margin_policy import MarginMark
from coinmaster.venues.marks import VenueMark

class MinuteTurnover(Data):
    def __init__(self,instrument_id,turnover,ts_event):
        self.instrument_id=instrument_id
        self.turnover=D(str(turnover))
        self._ts_event=ts_event
    @property
    def ts_event(self): return self._ts_event
    @property
    def ts_init(self): return self._ts_event

def turnover_data_type(iid):
    return DataType(MinuteTurnover,{"instrument_id":str(iid)})

def minute_turnover(iid,turnover,ns):
    return CustomData(turnover_data_type(iid),MinuteTurnover(iid,turnover,ns))

class CM2StrategyConfig(StrategyConfig, frozen=True):
    btc_id: InstrumentId
    sol_id: InstrumentId
    btc_bar_type: BarType
    sol_bar_type: BarType
    btc_mark_data_type: DataType
    sol_mark_data_type: DataType
    mark_client_id: ClientId
    policy: Config
    limits: ExecutionLimits
    margin_policy: object
    trading_start_open_ns: int
    terminal_close_at_ns: int
    seed_hours: tuple = ()
    exit_fee_rate: Decimal = Decimal(".000432")
    execution_policy_hash: str = ""
    funding_reader: object = None

class CM2Strategy(Strategy):
    def __init__(self, config):
        super().__init__(config)
        self.policy_state = State()
        self.hour_builder = PairedHourBuilder()
        self.hours = deque(config.seed_hours,maxlen=170)
        self.current_features = features(tuple(self.hours),config.policy,config.trading_start_open_ns) if self.hours else Features(config.trading_start_open_ns,config.trading_start_open_ns,False,"WARMUP")
        self._latest_marks = {}
        self._quotes = {}
        self._owned = {}
        self._seen_trade_ids = set()
        self._last_child = {}
        self._entry_fees = ZERO
        self._btc_cost_qty = ZERO
        self._parent_funding = ZERO
        self._funding_last = ZERO
        self._turnover = {}
        self._parent_cost_known = callable(config.funding_reader)
        self._order_audit = {}
        self.fill_audit = []
        self.pre_submit_gate_blocks = []
        self.entry_sizing_audit = []
        self.marked_equity_checkpoints = {}
        self.liquidation_audit = []
        self._liquidating = False
        self._liquidation_checks = 0
        self._liquidation_unknown = 0
        self._risk_unknown = False
        self.cm2_audit = []
        self.target_blockers = {}
        self.orphan_started_ns = None
        self.orphan_intervals = []
        self.terminal_lifecycle = {"status":"NOT_REACHED","reason":""}
        self._replay_supported = False

    def on_start(self):
        for bt in (self.config.btc_bar_type,self.config.sol_bar_type):
            self.subscribe_bars(bt)
        for i,dt in ((self.config.btc_id,self.config.btc_mark_data_type),(self.config.sol_id,self.config.sol_mark_data_type)):
            self.subscribe_data(dt,client_id=self.config.mark_client_id)
            self.subscribe_quote_ticks(i)
            self.subscribe_data(turnover_data_type(i),client_id=self.config.mark_client_id)

    def on_bar(self, bar):
        symbol = "BTC" if bar.bar_type.instrument_id == self.config.btc_id else "SOL"
        hour = self.hour_builder.add(symbol,bar.ts_event,bar.ts_init,
            float(bar.open),float(bar.high),float(bar.low),float(bar.close))
        if hour is not None:
            self.hours.append(hour)
            self.current_features = features(tuple(self.hours),self.config.policy,hour.available_ns)

    def on_data(self, data):
        mark = getattr(data,"data",data)
        if isinstance(mark,MinuteTurnover):
            rows=self._turnover.setdefault(mark.instrument_id,deque(maxlen=2))
            if not rows or mark.ts_event > rows[-1][0]:
                rows.append((mark.ts_event,mark.turnover))
            return
        if isinstance(mark,VenueMark):
            self._latest_marks[mark.instrument_id] = mark
            self.config.margin_policy.update_mark(MarginMark(mark.instrument_id,D(str(mark.price)),mark.ts_event))
            if all(self._latest_marks.get(i) is not None and self._latest_marks[i].ts_event==mark.ts_event
                   for i in (self.config.btc_id,self.config.sol_id)):
                self._check_liquidation(mark.ts_event)

    def _orders(self, instrument_id):
        found = {}
        for order in [*self.cache.orders_open(),*self.cache.orders_inflight()]:
            if str(order.client_order_id) in self._owned and order.instrument_id == instrument_id:
                found[str(order.client_order_id)] = order
        return list(found.values())

    def _position(self, iid):
        positions = [p for p in self.cache.positions_open() if p.instrument_id == iid]
        if len(positions) > 1:
            raise ValueError("CM2_REQUIRES_NATIVE_NETTING")
        return positions[0] if positions else None

    def _snapshot(self, now):
        account = self.cache.account_for_venue(self.config.btc_id.venue)
        if account is None or account.base_currency is None:
            raise ValueError("NATIVE_ACCOUNT_UNAVAILABLE")
        cash = account.balance_total(account.base_currency)
        if cash is None:
            raise ValueError("NATIVE_CASH_UNAVAILABLE")
        equity = cash.as_decimal()
        qtys,marks,pending = {},{},{}
        known = not self._risk_unknown
        unknown = False
        for iid in (self.config.btc_id,self.config.sol_id):
            mark = self._latest_marks.get(iid)
            if mark is None or now-mark.ts_event > 120_000_000_000 or mark.ts_event > now:
                known = False
            price = D(str(mark.price)) if mark is not None else ZERO
            if price <= 0:
                quote = self._quotes.get(iid)
                price = (quote.bid_price.as_decimal()+quote.ask_price.as_decimal())/2 if quote else D("1")
            marks[iid] = price
            pos = self._position(iid)
            qtys[iid] = (pos.quantity.as_decimal()*(D(1) if pos.is_long else D(-1))) if pos is not None else ZERO
            if pos is not None:
                equity += pos.unrealized_pnl(self.cache.instrument(iid).make_price(price)).as_decimal()
            leaves = ZERO
            live = self._orders(iid)
            for o in live:
                leaves += (D(1) if o.side == OrderSide.BUY else D(-1))*o.leaves_qty.as_decimal()
                if "UNKNOWN" in str(o.status):
                    unknown = True
                info = self._owned[str(o.client_order_id)]
                if now-info["submit_ns"] > 120_000_000_000 and not info.get("acked",False):
                    unknown = True
            pending[iid] = leaves
            # A locally submitted ID disappearing before terminal acknowledgement
            # is UNKNOWN, not an invitation to send again.
            for oid,info in self._owned.items():
                if info["instrument_id"] == iid and not info.get("terminal",False) and not any(str(o.client_order_id)==oid for o in live):
                    order = self.cache.order(info["client_order_id"])
                    if order is None or not order.is_closed:
                        unknown = True
        bpos = self._position(self.config.btc_id)
        self._sync_funding()
        return Snapshot(equity,qtys[self.config.btc_id],qtys[self.config.sol_id],
                        marks[self.config.btc_id],marks[self.config.sol_id],
                        pending[self.config.btc_id],pending[self.config.sol_id],unknown,known,
                        D(str(bpos.avg_px_open)) if bpos else None,
                        self._entry_fees if bpos else ZERO,
                        self._parent_funding if self._parent_cost_known else None,
                        self.config.exit_fee_rate,D(str(self.cache.instrument(self.config.btc_id).price_increment)),
                        self.config.limits.max_gross_notional,self.config.limits.max_gross_notional)

    def on_quote_tick(self, tick):
        self._quotes[tick.instrument_id] = tick
        now = tick.ts_event
        if now < self.config.trading_start_open_ns:
            return
        terminal = now >= self.config.terminal_close_at_ns
        f = self.current_features
        # A closed-hour signal cannot act on its own same-timestamp quote.
        if not terminal and now <= f.available_ns:
            return
        s = self._snapshot(now)
        decision = decide(self.config.policy,f,s,self.policy_state,terminal=terminal or self._liquidating)
        self.policy_state = decision.state
        sol_instrument=self.cache.instrument(self.config.sol_id)
        btc,sol,staged = stage_targets(decision,s,f,
            sol_step=sol_instrument.size_increment.as_decimal(),
            sol_min_qty=sol_instrument.min_quantity.as_decimal() if sol_instrument.min_quantity is not None else ZERO,
            sol_min_notional=sol_instrument.min_notional.as_decimal() if sol_instrument.min_notional is not None else ZERO)
        if staged:
            self._audit(now,"SOL_BEFORE_ORDINARY_BTC_REDUCTION")
        target = btc if tick.instrument_id == self.config.btc_id else sol
        actual = s.btc_qty if tick.instrument_id == self.config.btc_id else s.sol_qty
        pending = s.btc_pending if tick.instrument_id == self.config.btc_id else s.sol_pending
        if s.btc_qty == 0 and s.sol_qty != 0:
            if self.orphan_started_ns is None: self.orphan_started_ns = now
        elif self.orphan_started_ns is not None:
            self.orphan_intervals.append({"start_ns":str(self.orphan_started_ns),"end_ns":str(now),"reason":"BTC_FLAT_DRAIN"})
            self.orphan_started_ns = None
        emergency = terminal or decision.state.draining
        instrument = self.cache.instrument(tick.instrument_id)
        price = tick.ask_price.as_decimal() if target > actual else tick.bid_price.as_decimal()
        plan = order_plan(actual=actual,target=target,pending=pending,unknown=s.unknown_orders,
            price=price,step=D(str(instrument.size_increment)),
            min_qty=D(str(instrument.min_quantity or instrument.size_increment)),
            max_child=self._child_capacity(tick.instrument_id,now),emergency=emergency,
            min_notional=instrument.min_notional.as_decimal() if instrument.min_notional is not None else ZERO)
        if plan.action == "CANCEL":
            for order in self._orders(tick.instrument_id):
                self.cancel_order(order)
            return
        if plan.action != "SUBMIT":
            if plan.action=="HOLD" and actual!=target and plan.reason.startswith("VENUE_"):
                key=str(tick.instrument_id)
                previous=self.target_blockers.get(key,{})
                self.target_blockers[key]={"reason":plan.reason,"actual":str(actual),"target":str(target),
                    "first_ns":previous.get("first_ns",str(now)),"last_ns":str(now),
                    "observations":previous.get("observations",0)+1,"guard_staged":staged,
                    "emergency":emergency,"status":"MODEL_OR_VENUE_MINIMUM_BLOCKED_NOT_FILLED"}
            return
        if not emergency and now-self._last_child.get(tick.instrument_id,0) < self.config.limits.child_interval_ns:
            return
        q = plan.signed_quantity
        reducing = actual*q < 0
        if decision.cancel_increases and not reducing:
            return
        if not reducing and not self._admit(tick.instrument_id,q,price,s,now):
            return
        order = self._make_order(tick.instrument_id,OrderSide.BUY if q > 0 else OrderSide.SELL,
                                 instrument.make_qty(abs(q)),reducing,price)
        oid = str(order.client_order_id)
        self._owned[oid] = {"instrument_id":tick.instrument_id,"client_order_id":order.client_order_id,
                            "submit_ns":now,"terminal":False,"acked":False}
        self._order_audit[oid] = {"client_order_id":oid,"instrument":str(tick.instrument_id),
            "action":"BTC" if tick.instrument_id == self.config.btc_id else "SOL",
            "reason":decision.reason,"submit_ns":str(now),"decision_ns":str(f.available_ns),
            "quantity":str(abs(q)),"reduce_only":reducing}
        self.target_blockers.pop(str(tick.instrument_id),None)
        self._last_child[tick.instrument_id] = now
        self.submit_order(order)
        self._audit(now,decision.reason)

    def _make_order(self,iid,side,quantity,reducing,price):
        return self.order_factory.market(instrument_id=iid,order_side=side,
            quantity=quantity,time_in_force=TimeInForce.IOC,reduce_only=reducing)

    def _check_liquidation(self,now):
        # Reuses the mature mark-first contract: native cash + native marked
        # unrealized PnL <= existing public-tier maintenance. Never synthetic PnL.
        if self._liquidating:
            return
        try:
            s=self._snapshot(now)
            maintenance=sum((self.config.margin_policy.margin_for(p.instrument_id,p.quantity.as_decimal(),now)[1]
                             for p in self.cache.positions_open()),ZERO)
            self._liquidation_checks += 1
            self._risk_unknown = False
        except (ValueError,AttributeError):
            self._liquidation_unknown += 1
            self._risk_unknown = True
            return
        if not self.cache.positions_open() or s.equity > maintenance:
            return
        self._liquidating=True
        self.liquidation_audit.append({"trigger_ts":str(now),"marked_equity":str(s.equity),
            "tier_maintenance_margin":str(maintenance),"status":"ARMED","close_fills":[],
            "close_value":"0","lockout":"true"})
        # Exact native cancel/market reductions run on the next own-symbol
        # executable quote, with normal capacity/cadence exemptions.
        for iid in (self.config.btc_id,self.config.sol_id):
            for order in self._orders(iid):
                self.cancel_order(order)

    def _admit(self, iid, q, price, s, now):
        account = self.cache.account_for_venue(iid.venue)
        try:
            free = account.balance_free(account.base_currency).as_decimal()
            # Tier/selected-leverage validation must see aggregate projected
            # inventory, not a small child at an artificially lower tier.
            reserve=ZERO
            initial=ZERO
            for other,held in ((self.config.btc_id,s.btc_qty),(self.config.sol_id,s.sol_qty)):
                leaves=sum((abs(o.leaves_qty.as_decimal()) for o in self._orders(other)),ZERO)
                held_initial=self.config.margin_policy.margin_for(other,abs(held),now)[0]
                projected=abs(held)+leaves+(abs(q) if other==iid else ZERO)
                projected_initial=self.config.margin_policy.margin_for(other,projected,now)[0]
                before_child=self.config.margin_policy.margin_for(other,abs(held)+leaves,now)[0]
                reserve += max(ZERO,before_child-held_initial)
                initial += max(ZERO,projected_initial-before_child)
            gross = abs(s.btc_qty*s.btc_mark)+abs(s.sol_qty*s.sol_mark)
            pending_gross = abs(s.btc_pending*s.btc_mark)+abs(s.sol_pending*s.sol_mark)
            if initial+abs(q)*price*self.config.exit_fee_rate > free-reserve:
                raise ValueError("NATIVE_FREE_MARGIN")
            if self.config.limits.max_gross_notional is not None and gross+pending_gross+abs(q)*price > self.config.limits.max_gross_notional:
                raise ValueError("EXPLICIT_CAPACITY_GROSS")
        except (ValueError,AttributeError) as error:
            self.pre_submit_gate_blocks.append({"timestamp":str(now),"reason":str(error),"instrument":str(iid)})
            return False
        return True

    def _sync_funding(self):
        if not callable(self.config.funding_reader):
            self._parent_cost_known=False
            return
        current=self.config.funding_reader(self.config.btc_id)
        if current is None:
            self._parent_cost_known=False
            return
        current=D(str(current))
        if self._btc_cost_qty:
            self._parent_funding += current-self._funding_last
        self._funding_last=current

    def _child_capacity(self,iid,now):
        eligible=[value for ns,value in self._turnover.get(iid,()) if ns < now and now-ns <= 120_000_000_000]
        if not eligible or not eligible[-1].is_finite() or eligible[-1] <= 0:
            return ZERO
        return min(self.config.limits.max_child_notional,eligible[-1]*D(".01"))

    def on_order_accepted(self,event):
        info=self._owned.get(str(event.client_order_id))
        if info: info["acked"]=True
    def on_order_filled(self,event):
        if str(event.trade_id) in self._seen_trade_ids:
            return
        self._seen_trade_ids.add(str(event.trade_id))
        oid=str(event.client_order_id)
        context=self._order_audit.get(oid,{})
        fee=event.commission.as_decimal()
        self.fill_audit.append({"venue":str(event.instrument_id.venue),"instrument":str(event.instrument_id),
            "client_order_id":oid,"trade_id":str(event.trade_id),"action":context.get("action","UNKNOWN"),
            "reason":context.get("reason","UNKNOWN"),"order_side":getattr(event.order_side,"name",str(event.order_side)),
            "qty":str(event.last_qty.as_decimal()),
            "px":str(event.last_px.as_decimal()),"notional":str(event.last_qty.as_decimal()*event.last_px.as_decimal()),
            "commission":str(fee),"commission_currency":str(event.commission.currency),
            "native_liquidity_side":str(getattr(event.liquidity_side,"name",event.liquidity_side)),
            "fill_ns":str(event.ts_event),"policy_hash":self.config.execution_policy_hash})
        if event.instrument_id == self.config.btc_id:
            self._sync_funding()
            q=event.last_qty.as_decimal()
            if context.get("reduce_only"):
                keep=max(ZERO,self._btc_cost_qty-q)/self._btc_cost_qty if self._btc_cost_qty else ZERO
                self._entry_fees *= keep
                self._parent_funding *= keep
                self._btc_cost_qty=max(ZERO,self._btc_cost_qty-q)
            else:
                if self._btc_cost_qty == 0:
                    self._entry_fees=ZERO
                    self._parent_funding=ZERO
                self._entry_fees += fee
                self._btc_cost_qty += q
        if self._liquidating and self.liquidation_audit:
            row=self.liquidation_audit[-1]
            row["close_fills"].append({"trade_id":str(event.trade_id),"quantity":str(event.last_qty),"price":str(event.last_px)})
            row["close_value"]=str(D(row["close_value"])+event.last_qty.as_decimal()*event.last_px.as_decimal())
        self._terminal_event(event,only_if_closed=True)
    def _terminal_event(self,event,only_if_closed=False):
        info=self._owned.get(str(event.client_order_id))
        if info:
            order=self.cache.order(event.client_order_id)
            if not only_if_closed or (order is not None and order.is_closed):
                info["terminal"]=True
    def on_order_canceled(self,event): self._terminal_event(event)
    def on_order_denied(self,event): self._terminal_event(event)
    def on_order_rejected(self,event): self._terminal_event(event)
    def on_order_expired(self,event): self._terminal_event(event)
    def on_stop(self): pass

    def _audit(self,now,reason):
        self.cm2_audit.append({"ts_ns":str(now),"reason":reason,"parent":self.policy_state.parent,
            "btc_target":str(self.policy_state.btc_target),"sol_target":str(self.policy_state.sol_target)})
    def reporting_state(self):
        positions=self.cache.positions_open()
        open_orders=[*self.cache.orders_open(),*self.cache.orders_inflight()]
        terminal=self.clock.timestamp_ns() >= self.config.terminal_close_at_ns
        lifecycle={"reason":"TERMINAL_BOUNDARY_SETTLEMENT" if terminal else "NOT_REACHED",
                   "status":"FLAT" if terminal and not positions and not open_orders else "OPEN"}
        return {"liquidations":self.liquidation_audit,"liquidation_lockout":self._liquidating,
                "terminal_lifecycle":lifecycle,"terminal_open_orders":len(open_orders),
                "pre_submit_tier_margin_gate_blocks":self.pre_submit_gate_blocks,
                "marked_equity_checkpoints":[],"fill_audit":self.fill_audit,
                "entry_sizing_audit":self.entry_sizing_audit,
                "cm2":{"policy":asdict(self.config.policy),"audit":self.cm2_audit,
                       "target_blockers":self.target_blockers,"orphan_intervals":self.orphan_intervals,"open_orphan_since_ns":self.orphan_started_ns,
                       "parent_cost_attribution":"NATIVE_FILL_FEES_PRO_RATA_AND_SIGNED_NATIVE_POSTINGS" if self._parent_cost_known else "UNKNOWN_HARVEST_BLOCKED",
                       "restart_recovery":"UNTESTED_NOT_LIVE_RECOVERY",
                       "liquidation_measurement":{"contract":"NATIVE_MARK_FIRST_PUBLIC_TIER_MAINTENANCE",
                           "checks":self._liquidation_checks,"unknown_checks":self._liquidation_unknown,
                           "acceptance":"UNKNOWN_PENDING_NATIVE_FIXTURE"},
                       "structural_diagnostics":"UNKNOWN_PENDING_NATIVE_ACCEPTANCE"}}
