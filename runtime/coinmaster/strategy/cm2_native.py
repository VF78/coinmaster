"""One CM2 native owner. BTC-only market policy; stock OMS/Portfolio/journal authority."""
from __future__ import annotations
from dataclasses import asdict
from decimal import Decimal as D, ROUND_FLOOR, ROUND_CEILING
from hashlib import sha256
from pathlib import Path
import json
from nautilus_trader.config import StrategyConfig
from nautilus_trader.core.data import Data
from nautilus_trader.model.data import BarType, DataType
from nautilus_trader.model.enums import OrderSide, TimeInForce, TriggerType
from nautilus_trader.model.identifiers import InstrumentId, ClientId, ClientOrderId
from nautilus_trader.trading.strategy import Strategy
from coinmaster.strategy.cm2_btc_policy import BtcConfig, BtcPolicy, BtcDay, DAY, DISCOUNT, breakeven_price
from coinmaster.strategy.cm2_policy import pending_effects
from coinmaster.strategy.cm2_execution import ExecutionLimits, NativeExposure, SafetyState, order_plan
from coinmaster.strategy.cm2_checkpoint import KEY, SCHEMA, canonical, decode
from coinmaster.strategy.cm2_order_contract import (MODEL_ID, FRESH_NS, DRAIN_NS, REDUCE_FLOOR_POLICY,
    request_terms, request_cap, RequestTerms, validate_request, bbo_status, drain_update, validate_drain, outward_price)
from coinmaster.venues.margin_policy import MarginMark
from coinmaster.venues.marks import VenueMark
from coinmaster.venues.signals import DailySignalBar
ZERO = D(0)

class MinuteTurnover(Data):
    """Historical loader compatibility only; not capacity authority for this route."""
    def __init__(self,instrument_id,turnover,ts_event):
        self.instrument_id=instrument_id;self.turnover=D(str(turnover));self._ts_event=ts_event
    @property
    def ts_event(self):return self._ts_event
    @property
    def ts_init(self):return self._ts_event


def turnover_data_type(iid):
    return DataType(MinuteTurnover,{"instrument_id":str(iid)})


def minute_turnover(iid,turnover,ns):
    from nautilus_trader.model.data import CustomData
    return CustomData(turnover_data_type(iid),MinuteTurnover(iid,turnover,ns))


class CM2StrategyConfig(StrategyConfig, frozen=True):
    btc_id: InstrumentId
    sol_id: InstrumentId
    btc_bar_type: BarType
    sol_bar_type: BarType
    btc_mark_data_type: DataType
    sol_mark_data_type: DataType
    mark_client_id: ClientId
    btc_signal_data_type: DataType
    sol_signal_data_type: DataType
    h4_data_type: DataType
    signal_client_id: ClientId
    policy: BtcConfig
    limits: ExecutionLimits
    margin_policy: object
    active_seed: D
    btc_step: D
    trading_start_open_ns: int
    terminal_close_at_ns: int
    seed_btc_days: tuple = ()
    exit_fee_rate: D = D('.000432')
    execution_policy_hash: str = ''
    funding_reader: object = None
    checkpoint_store: object = None
    continuity_reader: object = None


class CM2Strategy(Strategy):
    def __init__(self, config):
        if not isinstance(config.policy, BtcConfig):raise ValueError('OLD_CM2_POLICY_VERSION_REJECTED')
        if config.exit_fee_rate!=D('.000432'):raise ValueError('APPROVED_TAKER_EXIT_FEE_REQUIRED')
        super().__init__(config)
        self.btc=BtcPolicy(config.policy,step=config.btc_step,
            start_ns=config.trading_start_open_ns,end_ns=config.terminal_close_at_ns)
        for day in config.seed_btc_days:self.btc.accept_day(day,receipt_ns=config.trading_start_open_ns)
        self.btc.complete_seed()
        self.safety=SafetyState(emergency_peak_equity=config.active_seed)
        self._latest_marks={};self._quotes={};self._owned={};self._order_audit={};self._seen_trade_ids=set()
        self._needs_daily=False;self._entry_dispatching=False;self._protection_dispatching=False;self._protection_dirty=False
        self._drain={};self._drain_dispatching=set();self._risk_unknown=False;self._liquidating=False;self._restore_failed=False
        self.fill_audit=[];self.entry_sizing_audit=[];self.pre_submit_gate_blocks=[]
        self.cm2_audit=[];self.child_permission_audit=[];self.drain_audit=[]
        self.target_blockers={};self.orphan_started_ns=None;self.orphan_intervals=[]
        self.liquidation_audit=[];self._liquidation_checks=0;self._liquidation_unknown=0
        self._retained_audit_chain='0'*64;self._checkpoint_revision=0;self._checkpoint_loaded=False
        self.terminal_lifecycle={'status':'NOT_REACHED','reason':''}
        self._admission_sources={name:sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ('cm2_native.py','cm2_btc_policy.py','cm2_execution.py','cm2_checkpoint.py','cm2_order_contract.py')}

    def on_start(self):
        if self.cache.instrument(self.config.btc_id).size_increment.as_decimal()!=self.config.btc_step:
            raise ValueError('NATIVE_BTC_LOT_BINDING')
        if not self._checkpoint_loaded and (self.cache.positions_open() or self.cache.orders_open() or self.cache.orders_inflight()):
            raise ValueError('CM2_FRESH_START_REQUIRES_EMPTY_NATIVE_CACHE_NO_RECOVERY')
        if self._checkpoint_loaded and (canonical(self._native_checkpoint_binding())!=self._loaded_native_binding
                or canonical(self._feed_checkpoint_binding())!=self._loaded_feed_binding
                or not callable(self.config.continuity_reader)
                or canonical(self.config.continuity_reader())!=self._loaded_observer_binding):
            self._restore_failed=True;raise ValueError('CM2_NATIVE_CONTINUITY_CHANGED_BEFORE_START')
        for iid,dt in ((self.config.btc_id,self.config.btc_mark_data_type),(self.config.sol_id,self.config.sol_mark_data_type)):
            self.subscribe_data(dt,client_id=self.config.mark_client_id);self.subscribe_quote_ticks(iid)
        for dt in (self.config.btc_signal_data_type,self.config.h4_data_type):
            self.subscribe_data(dt,client_id=self.config.signal_client_id)

    def on_data(self,data):
        item=getattr(data,'data',data);now=self.clock.timestamp_ns()
        if isinstance(item,VenueMark):
            old=self._latest_marks.get(item.instrument_id)
            if old is not None and item.ts_event<old.ts_event:return
            self._latest_marks[item.instrument_id]=item
            self.config.margin_policy.update_mark(MarginMark(item.instrument_id,D(str(item.price)),item.ts_event))
            self._check_liquidation(now);self._check_emergency_drawdown(now)
        elif isinstance(item,DailySignalBar) and getattr(item,'hours',None) is None and item.instrument_id==self.config.btc_id:
            if self.btc.days and item.ts_event<=self.btc.days[-1].close_ns:return
            self.btc.accept_day(BtcDay(item.ts_event-DAY,item.ts_event,item.ts_init,
                float(item.open),float(item.high),float(item.low),float(item.close)),receipt_ns=now)
            self._needs_daily=True;self._evaluate_daily(now)
        elif getattr(item,'hours',None)==4 and item.instrument_id==self.config.btc_id:
            self.btc.accept_h4(open_ns=item.open_time_ns,close_ns=item.ts_event,
                available_ns=item.ts_init,receipt_ns=now,close=D(str(item.close)))
        self._persist_checkpoint()

    def _funding(self):
        reader=self.config.funding_reader
        account=self.cache.account_for_venue(self.config.btc_id.venue)
        if account is None or account.base_currency is None or not callable(reader) or getattr(reader,'journal',None) is None:
            raise ValueError('NATIVE_FUNDING_JOURNAL_UNKNOWN')
        btc_total=None
        for iid in (self.config.btc_id,self.config.sol_id):
            if self.cache.instrument(iid).settlement_currency!=account.base_currency:raise ValueError('SETTLEMENT_CURRENCY_UNKNOWN')
            value=reader(iid)
            if not isinstance(value,D) or not value.is_finite():raise ValueError('NATIVE_SIGNED_FUNDING_UNKNOWN')
            if iid==self.config.btc_id:btc_total=value
        return btc_total

    def _evaluate_daily(self,now):
        if not self._needs_daily:return False
        self.btc.current(now);self._needs_daily=False
        if self.btc.regime_close(now):
            self._begin_drain(now,'BTC_ECONOMIC',[str(self.config.btc_id)],'REGIME')
            return True
        return False

    def _reconcile_btc(self,now):
        p=self.btc.parent
        if p is None or self._position(self.config.btc_id) is not None:return
        if not (p.entry_filled or p.growth_stopped):return
        p.growth_stopped=True
        # Native-flat does not erase cancel-pending growth or alternative exits.
        for order in self._orders(self.config.btc_id):
            if not order.is_pending_cancel:self.cancel_order(order)
            if self.btc.parent is not p:return
        if not self._orders(self.config.btc_id) and not any(v['instrument_id']==self.config.btc_id for v in self._owned.values()):
            self.btc.confirm_flat(now=now,native_flat=True,owners_terminal=True)
            self._persist_checkpoint()

    def _cancel_growth(self):
        for order in self._orders(self.config.btc_id):
            if not order.is_reduce_only and not order.is_pending_cancel:self.cancel_order(order)

    def on_quote_tick(self,tick):
        now=self.clock.timestamp_ns();fresh,why=bbo_status(tick,now)
        old=self._quotes.get(tick.instrument_id)
        if not fresh or old is not None and tick.ts_event<old.ts_event:
            self.pre_submit_gate_blocks.append({'timestamp':str(now),'instrument':str(tick.instrument_id),'reason':why});return
        self._quotes[tick.instrument_id]=tick
        if now<self.config.trading_start_open_ns:return
        self._check_emergency_drawdown(now)
        if now>=self.config.terminal_close_at_ns and not self.safety.global_latched:
            self.safety.global_latched=True;self.safety.reason='TERMINAL_BOUNDARY_SETTLEMENT'
            self._begin_drain(now,'GLOBAL',[str(self.config.btc_id),str(self.config.sol_id)],self.safety.reason)
        close_phase='BTC_ECONOMIC' in self._drain
        self._reconcile_drains(now);scope=self._scope_for(tick.instrument_id)
        if scope is not None:self._execute_drain(tick,now,scope)
        elif tick.instrument_id==self.config.btc_id and not self.safety.global_latched and not self._restore_failed:
            consumed=close_phase or self._evaluate_daily(now)
            if self._scope_for(tick.instrument_id):self._execute_drain(tick,now,'BTC_ECONOMIC')
            elif not consumed:
                self._reconcile_btc(now)
                self._sync_protection(now)
                self._execute_entry(tick,now)
                self._sync_protection(now)
        # SOL has no approved market model. Carry is not an automatic BTC-flat exit.
        self._reconcile_drains(now)
        if not close_phase and 'BTC_ECONOMIC' not in self._drain and not self.safety.global_latched:
            if self.btc.consume_h4(now):self._needs_daily=True
        self._persist_checkpoint()

    def _execute_entry(self,tick,now):
        if self._entry_dispatching:return
        self._entry_dispatching=True
        try:
            while not self.safety.global_latched and not self._restore_failed:
                if self._scope_for(self.config.btc_id):break
                if any(v['instrument_id']==self.config.btc_id and v['purpose'].startswith('ENTRY') for v in self._owned.values()):break
                p=self.btc.parent
                if p is None:
                    if self._position(self.config.btc_id) is not None or self._orders(self.config.btc_id) or not self.btc.entry_signal(now):break
                    s=self._snapshot(now)
                    if s.unknown_orders or not s.data_known:break
                    side=self.btc.current(now).side
                    executable=tick.ask_price.as_decimal() if side==1 else tick.bid_price.as_decimal()
                    p=self.btc.open_cycle(side=side,equity=s.equity,executable=executable,now=now,funding_total=self._funding())
                    self.entry_sizing_audit.append({'episode_id':p.id,'decision_ns':str(now),'native_equity':str(s.equity),
                        'multiplier':'7.875','planned_qty':str(p.quantity),'first_half':str(p.first_quantity),
                        'split_lot_rule':'TOTAL_FLOOR_TO_EVEN_LOTS','confirmed_native_entry_qty':'0'})
                if p.growth_stopped or p.close_reason:break
                if self._position(self.config.btc_id) is not None and not self._protection_ready(now):break
                before=p.entry_filled
                if p.first_filled<p.first_quantity:
                    q=p.first_quantity-p.first_filled;raw=None;purpose='ENTRY_MARKET'
                elif p.first_terminal:
                    q=p.quantity-p.entry_filled
                    if q<=0:break
                    raw=p.first_vwap*(1-D(p.side)*DISCOUNT);purpose='ENTRY_DISCOUNT'
                else:break
                if not self._send(self.config.btc_id,q,p.side,purpose,now,tick,raw_limit=raw,reason='BTC_MARKET_SPLIT'):
                    p.growth_stopped=True;self._reconcile_btc(now);break
                if self.btc.parent is not p or p.entry_filled<=before:break
        except (ValueError,AttributeError,TypeError) as error:
            self.target_blockers['BTC_ENTRY']={'reason':str(error),'clock_ns':str(now)}
        finally:self._entry_dispatching=False

    def _sync_protection(self,now):
        if self._protection_dispatching:
            self._protection_dirty=True;return
        self._protection_dispatching=True
        try:
            while True:
                self._protection_dirty=False
                self._reconcile_protection(now)
                if not self._protection_dirty:break
        except (ValueError,AttributeError,TypeError) as error:
            p=self.btc.parent
            self.target_blockers['BTC_PROTECTION:'+(p.id if p else 'NONE')]={'reason':str(error),'clock_ns':str(now)}
            if p is not None and not p.close_reason:
                self.btc.stop_growth('REQUIRED_PROTECTION_FACTS_HOLD');self._cancel_growth()
        finally:self._protection_dispatching=False

    def _reconcile_protection(self,now):
        p=self.btc.parent;position=self._position(self.config.btc_id);tick=self._quotes.get(self.config.btc_id)
        if p is None or p.close_reason or position is None or self._scope_for(self.config.btc_id) is not None:return
        if tick is None or not bbo_status(tick,now)[0]:raise ValueError('PROTECTION_FRESH_BBO_UNKNOWN')
        self.btc.observe_funding(self._funding())
        instrument=self.cache.instrument(self.config.btc_id);average=D(str(position.avg_px_open))
        actual=position.quantity.as_decimal();desired={}
        for level,lots in enumerate(self.btc.target_lots()):
            if lots:desired[('TP_GTC',level)]=(D(lots)*self.config.btc_step,self.btc.target_price(level,average))
        if p.be_armed:
            self._cancel_growth()
            desired[('BE_STOP',None)]=(actual,breakeven_price(side=p.side,native_average=average,
                native_quantity=actual,remaining_cost=p.remaining_cost,exit_fee_rate=self.config.exit_fee_rate))
        def working(key):
            result=[]
            for info in self._owned.values():
                if info['instrument_id']==self.config.btc_id and (info['purpose'],info['level'])==key:
                    order=self.cache.order(info['client_order_id'])
                    if order is None:raise ValueError('PROTECTION_NATIVE_ORDER_UNKNOWN')
                    result.append(order)
            return result
        keys=set(desired)|{(v['purpose'],v['level']) for v in self._owned.values()
            if v['instrument_id']==self.config.btc_id and v['purpose'] in ('TP_GTC','BE_STOP')}
        for key in keys:
            orders=working(key);wanted=desired.get(key)
            wire=self._format_price(instrument,wanted[1],p.side==1) if wanted else None
            total=sum((o.leaves_qty.as_decimal() for o in orders),ZERO)
            wrong_price=any((o.trigger_price if key[0]=='BE_STOP' else o.price)!=wire for o in orders)
            if wanted is None or total>wanted[0] or wrong_price:
                for order in orders:
                    if not order.is_pending_cancel:self.cancel_order(order)
                    if self._protection_dirty:return
        for (purpose,level),(q,raw) in desired.items():
            if 'NATIVE_PROTECTION_TERMINAL:'+p.id+':'+purpose+':'+str(level) in self.target_blockers:continue
            while self.btc.parent is p and not p.close_reason:
                orders=working((purpose,level))
                wire=self._format_price(instrument,raw,p.side==1)
                if any(o.is_pending_cancel or (o.trigger_price if purpose=='BE_STOP' else o.price)!=wire for o in orders):break
                covered=sum((o.leaves_qty.as_decimal() for o in orders),ZERO)
                if covered>=q:break
                if not self._send(self.config.btc_id,q-covered,-p.side,purpose,now,tick,reduce_only=True,level=level,
                        raw_limit=raw if purpose=='TP_GTC' else None,stop_trigger=raw if purpose=='BE_STOP' else None,
                        reason='FIXED_TP' if purpose=='TP_GTC' else 'FEE_AWARE_BREAKEVEN'):
                    self.btc.stop_growth('REQUIRED_PROTECTION_REQUEST_HOLD');self._cancel_growth();return
                if self._protection_dirty:return
                after=sum((o.leaves_qty.as_decimal() for o in working((purpose,level))),ZERO)
                if after<=covered:break

    def _protection_ready(self,now):
        p=self.btc.parent;position=self._position(self.config.btc_id)
        if position is None:return True
        if p is None:return False
        try:
            if self._funding()!=p.funding_total:return False
            average=D(str(position.avg_px_open));instrument=self.cache.instrument(self.config.btc_id)
            desired={('TP_GTC',i):(D(lots)*self.config.btc_step,self.btc.target_price(i,average))
                for i,lots in enumerate(self.btc.target_lots()) if lots}
            if p.be_armed:
                q=position.quantity.as_decimal()
                desired[('BE_STOP',None)]=(q,breakeven_price(side=p.side,native_average=average,
                    native_quantity=q,remaining_cost=p.remaining_cost,exit_fee_rate=self.config.exit_fee_rate))
            for (purpose,level),(q,raw) in desired.items():
                wire=self._format_price(instrument,raw,p.side==1);covered=ZERO
                for info in self._owned.values():
                    if (info['instrument_id']!=self.config.btc_id or info['parent_id']!=p.id
                            or (info['purpose'],info['level'])!=(purpose,level)):continue
                    order=self.cache.order(info['client_order_id'])
                    if (order is None or not order.is_open or order.is_pending_cancel or not order.is_reduce_only
                            or order.side!=(OrderSide.SELL if p.side==1 else OrderSide.BUY)):continue
                    if (order.trigger_price if purpose=='BE_STOP' else order.price)!=wire:continue
                    covered+=order.leaves_qty.as_decimal()
                if covered<q:return False
            return True
        except (ValueError,AttributeError,TypeError):return False

    def _format_price(self,instrument,raw,up):
        spec=self._contract_spec(instrument.id,instrument)
        value=outward_price(spec,raw,up)
        result=instrument.make_price(value)
        if result.as_decimal()!=value:raise ValueError('NATIVE_PRICE_FORMAT_MISMATCH')
        return result

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

    def _snapshot(self,now):
        account=self.cache.account_for_venue(self.config.btc_id.venue)
        if account is None or account.base_currency is None:raise ValueError("NATIVE_ACCOUNT_UNAVAILABLE")
        cash=account.balance_total(account.base_currency)
        if cash is None or cash.currency!=account.base_currency:raise ValueError("NATIVE_CASH_UNAVAILABLE")
        equity=cash.as_decimal();qty={};prices={};known_prices={};known=True;required_mark_times=[]
        all_orders=[*self.cache.orders_open(),*self.cache.orders_inflight()]
        unknown_assets={o.instrument_id for o in all_orders if str(o.client_order_id) not in self._owned}
        for iid in (self.config.btc_id,self.config.sol_id):
            position=self._position(iid)
            qty[iid]=position.quantity.as_decimal()*(D(1) if position.is_long else D(-1)) if position else ZERO
            reachable=qty[iid]!=0 or any(o.instrument_id==iid and not o.is_reduce_only for o in all_orders)
            mark=self._latest_marks.get(iid);price=D(str(mark.price)) if mark is not None else ZERO
            fresh=mark is not None and price.is_finite() and price>0 and 0<=now-mark.ts_event<=FRESH_NS
            prices[iid]=price if fresh else ZERO;known_prices[iid]=fresh
            if reachable and not fresh:known=False
            if reachable and fresh:required_mark_times.append(mark.ts_event)
            if position is not None and fresh:
                pnl=position.unrealized_pnl(self.cache.instrument(iid).make_price(price))
                if pnl.currency!=account.base_currency:raise ValueError("NATIVE_UPNL_CURRENCY_UNKNOWN")
                equity+=pnl.as_decimal()
        if len(set(required_mark_times))>1:known=False
        for oid,info in self._owned.items():
            order=self.cache.order(info['client_order_id'])
            if order is None or (now-info['submit_ns']>FRESH_NS and not info.get('acked')):
                unknown_assets.add(info['instrument_id'])
        return NativeExposure(equity,qty[self.config.btc_id],qty[self.config.sol_id],
            prices[self.config.btc_id],prices[self.config.sol_id],bool(unknown_assets),known,known_prices,frozenset(unknown_assets))

    def _on_drain_deadline(self,_event):
        now=self.clock.timestamp_ns()
        for scope,drain in self._drain.items():
            state=drain['state']
            if now>=state['deadline_ns'] and not state['reconcile_required']:
                state['reconcile_required']=True
                self.drain_audit.append({'timestamp_ns':now,'scope':scope,'event':'RECONCILE_REQUIRED','state':dict(state)})
        self._persist_checkpoint()

    def _scope_for(self,iid):
        for scope in ('GLOBAL','BTC_ECONOMIC','SOL_SUBORDINATE'):
            record=self._drain.get(scope)
            if record is not None and str(iid) in record['state']['scoped_zero_ids']:return scope
        return None

    def _check_emergency_drawdown(self,now):
        fraction=self.config.policy.emergency_drawdown_fraction
        if fraction is None:return
        try:
            s=self._snapshot(now)
            if not s.data_known or s.unknown_orders:raise ValueError('EMERGENCY_NATIVE_VALUATION_UNKNOWN')
            self.safety.emergency_valuation_known=True
            self.safety.emergency_peak_equity=max(self.safety.emergency_peak_equity,s.equity)
            if self.safety.emergency_latched:return
            if s.equity<=self.safety.emergency_peak_equity*(1-fraction):
                self.safety.emergency_latched=True;self.safety.global_latched=True
                self.safety.reason='EMERGENCY_DRAWDOWN'
                self.safety.emergency_trigger_equity=s.equity
                self.safety.emergency_trigger_peak_equity=self.safety.emergency_peak_equity
                self.safety.emergency_trigger_fraction=fraction;self.safety.emergency_trigger_ns=now
                self._begin_drain(now,'GLOBAL',[str(self.config.btc_id),str(self.config.sol_id)],self.safety.reason)
        except (ValueError,AttributeError):self.safety.emergency_valuation_known=False

    def _check_liquidation(self,now):
        if self._liquidating:return
        try:
            s=self._snapshot(now)
            if not s.data_known:raise ValueError('HELD_NATIVE_MARK_UNKNOWN')
            maintenance=sum((self.config.margin_policy.margin_for(p.instrument_id,p.quantity.as_decimal(),now)[1]
                for p in self.cache.positions_open()),ZERO)
            self._liquidation_checks+=1;self._risk_unknown=False
        except (ValueError,AttributeError):
            self._liquidation_unknown+=1;self._risk_unknown=True;return
        if not self.cache.positions_open() or s.equity>maintenance:return
        self._liquidating=True;self.safety.global_latched=True;self.safety.reason='LIQUIDATION'
        self.liquidation_audit.append({'trigger_ts':str(now),'marked_equity':str(s.equity),
            'tier_maintenance_margin':str(maintenance),'close_fills':[],'close_value':'0','status':'ARMED'})
        self._begin_drain(now,'GLOBAL',[str(self.config.btc_id),str(self.config.sol_id)],'LIQUIDATION')

    def _execute_drain(self,tick,now,scope):
        if tick.ts_event<self._drain[scope]['state']['first_ns']:return
        iid=tick.instrument_id
        if iid in self._drain_dispatching:return
        self._drain_dispatching.add(iid)
        try:
            while self._scope_for(iid)==scope:
                if self._orders(iid) or any(v['instrument_id']==iid for v in self._owned.values()):break
                position=self._position(iid)
                if position is None:break
                before=position.quantity.as_decimal();side=-1 if position.is_long else 1
                if not self._send(iid,before,side,'DRAIN',now,tick,reduce_only=True,reason=self._drain[scope]['reason']):break
                after=self._position(iid)
                if after is None:break
                if after.quantity.as_decimal()>=before:break
            self._reconcile_drains(now)
        finally:self._drain_dispatching.remove(iid)

    def _admit(self, iid, q, price, s, now):
        now = self.clock.timestamp_ns()
        CM2Strategy._check_emergency_drawdown(self,now)
        try:
            # Caller valuation can precede a native cash/fill change. Admission
            # always samples current native cash/inventory and coherent marks.
            s = self._snapshot(now)
            marks = [self._latest_marks.get(i) for i in (self.config.btc_id,self.config.sol_id)]
            if not s.price_known.get(iid,False):
                raise ValueError("NATIVE_INCREASE_REQUIRED_MARK_UNKNOWN")
            account = self.cache.account_for_venue(iid.venue)
            currency = account.base_currency
            if currency is None or any(i.venue != iid.venue or
                    self.cache.instrument(i).settlement_currency != currency
                    for i in (self.config.btc_id,self.config.sol_id)):
                raise ValueError("NATIVE_COLLATERAL_CURRENCY_UNKNOWN")
            if self.safety.emergency_latched or (self.config.policy.emergency_drawdown_fraction is not None and not self.safety.emergency_valuation_known):
                raise ValueError("EMERGENCY_DRAWDOWN_GROWTH_HOLD")
            if s.unknown_orders or not s.data_known:
                raise ValueError("NATIVE_INCREASE_RISK_STATE_UNKNOWN")
            balances = (account.balance_free(currency),account.balance_locked(currency),account.balance_total(currency))
            if any(value is None or value.currency != currency for value in balances):
                raise ValueError("NATIVE_COLLATERAL_CURRENCY_UNKNOWN")
            free,locked,total = (value.as_decimal() for value in balances)
            fee_rate = self.config.exit_fee_rate
            if not fee_rate.is_finite() or fee_rate < 0:
                raise ValueError("NATIVE_FEE_RESERVE_UNKNOWN")
            amounts = (s.equity,s.btc_qty,s.sol_qty,s.btc_mark,s.sol_mark,q,price,free,locked,total)
            if any(not x.is_finite() for x in amounts) or min(free,locked,total) < 0 or total != free+locked:
                raise ValueError("NATIVE_COLLATERAL_BALANCE_UNKNOWN")
            if s.equity <= 0 or price <= 0:
                raise ValueError("NATIVE_COLLATERAL_VALUATION_UNKNOWN")
            # Tier/selected-leverage validation must see aggregate projected
            # inventory, not a small child at an artificially lower tier.
            reserve=ZERO
            initial=ZERO
            pending_gross=ZERO
            native_owned_order_margin=ZERO
            native_growth_reserve=ZERO
            projected_total=ZERO
            native_held_reserve=ZERO
            native_owned_position_margin=ZERO
            logical_fees=ZERO
            for other,held,mark in ((self.config.btc_id,s.btc_qty,s.btc_mark),(self.config.sol_id,s.sol_qty,s.sol_mark)):
                live = self._orders(other)
                _,growth = pending_effects(held,tuple(
                    ((D(1) if o.side == OrderSide.BUY else D(-1))*o.leaves_qty.as_decimal(),o.is_reduce_only)
                    for o in live))
                held_initial=self.config.margin_policy.margin_for(other,abs(held),now)[0] if held else ZERO
                native_initial=account.margin_init(other)
                native_maintenance = account.margin_maint(other)
                if any(value is not None and value.currency != currency for value in (native_initial,native_maintenance)):
                    raise ValueError("NATIVE_MARGIN_CURRENCY_UNKNOWN")
                native_initial = native_initial.as_decimal() if native_initial is not None else ZERO
                native_maintenance = native_maintenance.as_decimal() if native_maintenance is not None else ZERO
                if any(not x.is_finite() or x < 0 for x in (held_initial,native_initial,native_maintenance)):
                    raise ValueError("NATIVE_MARGIN_REQUIREMENT_UNKNOWN")
                native_owned_order_margin += native_initial
                native_owned_position_margin += native_maintenance
                native_held_reserve += min(held_initial,native_maintenance)
                projected=abs(held)+growth+(abs(q) if other==iid else ZERO)
                if projected and not s.price_known.get(other,False):raise ValueError("REACHABLE_COLLATERAL_MARK_UNKNOWN")
                projected_initial=self.config.margin_policy.margin_for(other,projected,now)[0] if projected else ZERO
                before_child=self.config.margin_policy.margin_for(other,abs(held)+growth,now)[0] if abs(held)+growth else ZERO
                if any(not x.is_finite() or x < 0 for x in (projected_initial,before_child)):
                    raise ValueError("NATIVE_MARGIN_REQUIREMENT_UNKNOWN")
                projected_total += projected_initial
                instrument_reserve=max(ZERO,before_child-held_initial)
                reserve += instrument_reserve
                native_growth_reserve += min(instrument_reserve,native_initial)
                initial += max(ZERO,projected_initial-before_child)
                pending_gross += growth*mark
            # Native locked cash already covers some growth IM. Never give RO credit.
            totals=(account.total_margin_init(currency),account.total_margin_maint(currency))
            if any(value is None or value.currency != currency for value in totals):
                raise ValueError("NATIVE_MARGIN_CURRENCY_UNKNOWN")
            native_margin,native_maintenance=(value.as_decimal() for value in totals)
            if any(not x.is_finite() or x < 0 for x in (native_margin,native_maintenance)) or native_margin+native_maintenance > locked:
                raise ValueError("NATIVE_MARGIN_LOCKED_EQUIVALENCE_UNKNOWN")
            if native_owned_order_margin > native_margin or native_owned_position_margin > native_maintenance:
                raise ValueError("NATIVE_OWN_MARGIN_UNKNOWN")
            uncovered=max(ZERO,reserve-native_growth_reserve)
            pending_fees=pending_gross*fee_rate
            gross = abs(s.btc_qty*s.btc_mark)+abs(s.sol_qty*s.sol_mark)
            if initial+(abs(q)*price)*fee_rate+pending_fees+logical_fees > free-uncovered:
                raise ValueError("NATIVE_FREE_MARGIN")
            # Full tierIM includes held inventory and all reachable growth.
            # Credit only matching native locks already in that requirement;
            # opaque/other locks remain unavailable. RO never releases collateral.
            unmatched_locked=max(ZERO,locked-native_growth_reserve-native_held_reserve)
            fees=(pending_gross+abs(q)*price)*fee_rate+logical_fees
            if projected_total+fees > s.equity-unmatched_locked:
                raise ValueError("NATIVE_AGGREGATE_COLLATERAL")
            if self.config.limits.max_gross_notional is not None and gross+pending_gross+abs(q)*price > self.config.limits.max_gross_notional:
                raise ValueError("EXPLICIT_CAPACITY_GROSS")
        except (ValueError,AttributeError) as error:
            self.pre_submit_gate_blocks.append({"timestamp":str(now),"reason":str(error),"instrument":str(iid)})
            return False
        return True

    def _contract_spec(self,iid,instrument):
        profile=getattr(self.config.margin_policy,"_profile",None)
        if profile is None or str(getattr(profile,"environment",""))!="mainnet":
            raise ValueError("EVIDENCE_BOUND_MAINNET_PROFILE_REQUIRED")
        spec=profile.instruments[str(iid)]
        if (instrument.size_increment.as_decimal()!=spec.quantity_increment
                or instrument.size_precision != -spec.quantity_increment.as_tuple().exponent
                or instrument.min_notional is None or instrument.min_notional.as_decimal()!=spec.min_notional):
            raise ValueError("NATIVE_REQUEST_PROFILE_MISMATCH")
        return spec

    def _native_checkpoint_binding(self):
        account=self.cache.account_for_venue(self.config.btc_id.venue)
        if account is None or account.base_currency is None:
            raise ValueError("CM2_CHECKPOINT_NATIVE_ACCOUNT_REQUIRED")
        positions=sorted(([str(p.id),str(p.instrument_id),str(p.side),str(p.quantity),str(p.avg_px_open)]
                          for p in self.cache.positions_open()))
        orders={str(o.client_order_id):o for o in [*self.cache.orders_open(),*self.cache.orders_inflight()]}
        return {"account_id":str(account.id),"currency":str(account.base_currency),
            "cash":str(account.balance_total(account.base_currency).as_decimal()),
            "free":str(account.balance_free(account.base_currency).as_decimal()),
            "locked":str(account.balance_locked(account.base_currency).as_decimal()),
            "initial_margin":{str(k):str(v.as_decimal()) for k,v in account.margins_init().items()},
            "maintenance_margin":{str(k):str(v.as_decimal()) for k,v in account.margins_maint().items()},
            "positions":positions,
            "orders":sorted([[oid,str(o.instrument_id),str(o.side),str(o.status),str(o.quantity),str(o.leaves_qty)]
                            for oid,o in orders.items()])}

    def _chain_audit(self,kind,row):
        self._retained_audit_chain=sha256(self._retained_audit_chain.encode()+canonical([kind,row])).hexdigest()

    def _feed_checkpoint_binding(self):
        return {'clock_ns':self.clock.timestamp_ns(),
            'quotes':{str(i):[q.ts_event,q.ts_init,str(q.bid_price),str(q.ask_price),str(q.bid_size),str(q.ask_size)] for i,q in self._quotes.items()},
            'marks':{str(i):[m.ts_event,str(m.price)] for i,m in self._latest_marks.items()}}

    def on_save(self):
        body=canonical(self._checkpoint_document());store=self.config.checkpoint_store
        if store is not None:
            revision=store.persist(body,self._checkpoint_revision)
            if revision is None:self._restore_failed=True;raise ValueError('CM2_CHECKPOINT_REVISION_CONFLICT')
            self._checkpoint_revision=revision
        return {KEY:body}

    def _persist_checkpoint(self):
        if self.config.checkpoint_store is not None:self.on_save()

    def on_stop(self):self._persist_checkpoint()

    def _begin_drain(self,now,scope,ids,reason):
        previous=self._drain.get(scope)
        state=drain_update(previous['state'] if previous else None,now,ids)
        p=self.btc.parent
        if p is not None and str(self.config.btc_id) in ids:
            p.close_reason=p.close_reason or reason;p.growth_stopped=True
        self._drain[scope]={'state':state,'reason':reason,
            'parent_id':previous['parent_id'] if previous else (p.id if p else None)}
        if previous is None:self.drain_audit.append({'timestamp_ns':now,'scope':scope,'event':'START','state':state,'reason':reason})
        for iid in (self.config.btc_id,self.config.sol_id):
            if str(iid) in ids:
                for order in self._orders(iid):
                    if not order.is_pending_cancel:self.cancel_order(order)
        name='CM2_'+scope+'_'+str(self.id)
        if name not in self.clock.timer_names and not state['reconcile_required']:
            if now>=state['deadline_ns']:self._on_drain_deadline(None)
            else:self.clock.set_time_alert_ns(name,state['deadline_ns'],callback=self._on_drain_deadline)

    def _reconcile_drains(self,now):
        for scope,drain in list(self._drain.items()):
            ids=drain['state']['scoped_zero_ids']
            if not all(self._position(iid) is None and not self._orders(iid)
                    and not any(v['instrument_id']==iid for v in self._owned.values())
                    for iid in (self.config.btc_id,self.config.sol_id) if str(iid) in ids):continue
            if str(self.config.btc_id) in ids:self._reconcile_btc(now)
            name='CM2_'+scope+'_'+str(self.id)
            if name in self.clock.timer_names:self.clock.cancel_timer(name)
            self.drain_audit.append({'timestamp_ns':now,'scope':scope,'event':'NATIVE_SCOPED_FLAT'})
            del self._drain[scope]

    def _send(self,iid,quantity,side,purpose,now,tick,*,reduce_only=False,
              level=None,raw_limit=None,stop_trigger=None,reason=''):
        if quantity<=0 or side not in (-1,1):return False
        instrument=self.cache.instrument(iid)
        try:
            fresh,why=bbo_status(tick,now)
            if not fresh:raise ValueError(why)
            snapshot=self._snapshot(now)
            if snapshot.unknown_orders and (not reduce_only or not snapshot.unknown_order_assets or iid in snapshot.unknown_order_assets):
                raise ValueError('UNKNOWN_NATIVE_OWNER')
            spec=self._contract_spec(iid,instrument)
            executable=tick.ask_price.as_decimal() if side==1 else tick.bid_price.as_decimal()
            intent='STOP_MARKET' if stop_trigger is not None else 'LIMIT' if raw_limit is not None else 'MARKET'
            tif='GTC' if intent!='MARKET' else 'IOC'
            limit=trigger=None
            if intent=='LIMIT':
                # Buy-discount rounds down; sell-discount up. TP sell up / buy down.
                up=side==-1
                limit=self._format_price(instrument,raw_limit,up)
                cap,classification=request_cap(spec,intent,tif)
                terms=RequestTerms(limit.as_decimal(),max(executable,limit.as_decimal()),min(executable,limit.as_decimal()),cap,classification)
            elif intent=='STOP_MARKET':
                trigger=self._format_price(instrument,stop_trigger,side==-1)
                cap,classification=request_cap(spec,intent,tif)
                terms=RequestTerms(None,max(executable,trigger.as_decimal()),min(executable,trigger.as_decimal()),cap,classification)
            else:terms=request_terms(spec,executable,'BUY' if side==1 else 'SELL',intent,tif)
            actual=snapshot.btc_qty if iid==self.config.btc_id else snapshot.sol_qty
            if reduce_only:
                if not actual or actual*side>=0:raise ValueError('REDUCE_ONLY_NATIVE_SIDE_UNKNOWN')
                # Full-position BE and TP ladder are alternative native RO exits.
                # Only concurrently attainable TP siblings reserve one another.
                other_tp=sum((o.leaves_qty.as_decimal() for o in self._orders(iid)
                    if o.is_reduce_only and self._owned[str(o.client_order_id)]['purpose']=='TP_GTC'),ZERO)
                other_be=sum((o.leaves_qty.as_decimal() for o in self._orders(iid)
                    if o.is_reduce_only and self._owned[str(o.client_order_id)]['purpose']=='BE_STOP'),ZERO)
                quantity=min(quantity,max(ZERO,abs(actual)-(other_be if purpose=='BE_STOP' else other_tp)))
            plan=order_plan(actual=actual,target=actual+D(side)*quantity,pending=ZERO,unknown=False,
                price=terms.minimum_reference_price,step=instrument.size_increment.as_decimal(),
                min_qty=instrument.min_quantity.as_decimal() if instrument.min_quantity is not None else instrument.size_increment.as_decimal(),
                max_child=self.config.limits.max_child_notional,min_notional=spec.min_notional,
                emergency=purpose=='DRAIN',venue_max_child_notional=terms.cap,venue_reference_price=terms.cap_reference_price)
            if plan.action!='SUBMIT':raise ValueError(plan.reason)
            q=abs(plan.signed_quantity)
            if not reduce_only and not self._admit(iid,q,executable,snapshot,now):return False
            native_qty=instrument.make_qty(q)
            if native_qty.as_decimal()!=q:raise ValueError('NATIVE_QTY_FORMAT_MISMATCH')
            valid,why=validate_request(spec,q,terms,intent,tif)
            if not valid:raise ValueError(why)
            common=dict(instrument_id=iid,order_side=OrderSide.BUY if side==1 else OrderSide.SELL,
                quantity=native_qty,time_in_force=TimeInForce.GTC if tif=='GTC' else TimeInForce.IOC,reduce_only=reduce_only)
            if intent=='LIMIT':order=self.order_factory.limit(**common,price=limit,post_only=False)
            elif intent=='STOP_MARKET':order=self.order_factory.stop_market(**common,trigger_price=trigger,trigger_type=TriggerType.MARK_PRICE)
            else:order=self.order_factory.market(**common)
            if (order.quantity.as_decimal()!=q or order.instrument_id!=iid or order.side!=common['order_side']
                    or order.order_type.name!=intent or order.time_in_force.name!=tif or order.is_reduce_only!=reduce_only
                    or (intent=='LIMIT' and (order.price!=limit or order.is_post_only))
                    or (intent=='STOP_MARKET' and (order.trigger_price!=trigger or order.trigger_type!=TriggerType.MARK_PRICE))):
                raise ValueError('FINAL_NATIVE_REQUEST_MISMATCH')
            p=self.btc.parent;oid=str(order.client_order_id)
            info={'client_order_id':order.client_order_id,'instrument_id':iid,'purpose':purpose,
                'parent_id':p.id if p else None,'level':level,'submit_ns':now,'acked':False,'triggered':False,
                'side':side,'quantity':q,'limit_price':limit.as_decimal() if limit is not None else None,
                'trigger_price':trigger.as_decimal() if trigger is not None else None,'reduce_only':reduce_only,'reason':reason}
            self._owned[oid]=info
            self._order_audit[oid]=_report_value({**info,'client_order_id':oid,'instrument_id':str(iid),
                'native_order_type':order.order_type.name,'native_time_in_force':order.time_in_force.name,
                'request_model_id':MODEL_ID,'request_classification':terms.classification,
                'admission':{'parent_id':info['parent_id'],'purpose':purpose,'intent':intent,
                    'source_policy_version':self.config.policy.version,'native_quote_ns':tick.ts_event,
                    'request_cap':str(terms.cap),'reduce_floor_policy':REDUCE_FLOOR_POLICY,
                    'episode_entry_signal_index':p.decision_index if p else None,'tp_level':level}})
            self._chain_audit('ORDER_ADMISSION',self._order_audit[oid]);self._persist_checkpoint()
            self.submit_order(order)
            return True
        except (ValueError,AttributeError,TypeError,KeyError) as error:
            self.pre_submit_gate_blocks.append({'timestamp':str(now),'instrument':str(iid),'reason':str(error),'purpose':purpose})
            return False

    def on_order_accepted(self,event):
        info=self._owned.get(str(event.client_order_id))
        if info is not None:
            info['acked']=True;now=self.clock.timestamp_ns();self._sync_protection(now)
            p=self.btc.parent;tick=self._quotes.get(self.config.btc_id)
            if p is not None and info['parent_id']==p.id and tick is not None and bbo_status(tick,now)[0]:self._execute_entry(tick,now)
            self._persist_checkpoint()

    def on_order_triggered(self,event):
        info=self._owned.get(str(event.client_order_id))
        if info is not None:info['triggered']=True;self._persist_checkpoint()

    def _fill_owner(self,event,context):
        order=self.cache.order(event.client_order_id)
        if (context is None or order is None or str(order.client_order_id)!=str(event.client_order_id)
                or order.instrument_id!=event.instrument_id or order.strategy_id!=event.strategy_id
                or order.side!=event.order_side or event.strategy_id!=self.id
                or context['instrument_id']!=str(event.instrument_id)
                or context['side']!=(1 if event.order_side==OrderSide.BUY else -1)):
            raise ValueError('NATIVE_FILL_IDENTITY_OR_SIDE_UNKNOWN')
        index=self.cache.position_id(event.client_order_id)
        if index is not None and index!=event.position_id:raise ValueError('CONTRADICTORY_NATIVE_POSITION_INDEX')
        account=self.cache.account_for_venue(event.instrument_id.venue)
        if account is None or event.commission.currency!=account.base_currency:raise ValueError('NATIVE_FILL_CURRENCY_UNKNOWN')
        if event.last_qty.as_decimal()<=0 or event.last_px.as_decimal()<=0:raise ValueError('NATIVE_FILL_QUANTITY_UNKNOWN')
        return order

    def on_order_filled(self,event):
        tid=str(event.trade_id)
        if tid in self._seen_trade_ids:return
        oid=str(event.client_order_id);context=self._order_audit.get(oid);now=self.clock.timestamp_ns()
        try:order=self._fill_owner(event,context)
        except (ValueError,AttributeError,TypeError) as error:
            self._restore_failed=True;self.safety.global_latched=True;self.safety.reason=str(error)
            self._begin_drain(now,'GLOBAL',[str(self.config.btc_id),str(self.config.sol_id)],str(error));return
        self._seen_trade_ids.add(tid)
        q=event.last_qty.as_decimal();price=event.last_px.as_decimal();fee=event.commission.as_decimal()
        self.fill_audit.append({'client_order_id':oid,'trade_id':tid,'instrument':str(event.instrument_id),
            'venue':str(event.instrument_id.venue),'qty':str(q),'px':str(price),'notional':str(q*price),
            'commission':str(fee),'commission_currency':str(event.commission.currency),'fill_ns':str(event.ts_event),
            'native_liquidity_side':getattr(event.liquidity_side,'name',str(event.liquidity_side)),
            'order_side':getattr(event.order_side,'name',str(event.order_side)),
            'action':context['purpose'],'reason':context['reason'],'level':context['level'],
            'parent_id':context['parent_id'],'admission':context['admission'],'policy_hash':self.config.execution_policy_hash})
        p=self.btc.parent
        if event.instrument_id==self.config.btc_id:
            if p is None or context['parent_id']!=p.id:
                self._restore_failed=True;self._begin_drain(now,'BTC_ECONOMIC',[str(self.config.btc_id)],'LATE_BTC_CYCLE_IDENTITY_HOLD')
            else:
                try:
                    self.btc.observe_funding(self._funding())
                    purpose=context['purpose']
                    if purpose.startswith('ENTRY'):
                        self.btc.entry_fill(trade_id=tid,quantity=q,price=price,commission=fee,first_leg=purpose=='ENTRY_MARKET')
                        for audit in reversed(self.entry_sizing_audit):
                            if audit['episode_id']==p.id:audit['confirmed_native_entry_qty']=str(p.entry_filled);break
                    else:
                        position=self._position(self.config.btc_id)
                        after=position.quantity.as_decimal() if position else ZERO
                        self.btc.reduction_fill(trade_id=tid,quantity=q,before_quantity=after+q,
                            level=context['level'] if purpose=='TP_GTC' else None)
                        if purpose=='BE_STOP':
                            self._begin_drain(now,'BTC_ECONOMIC',[str(self.config.btc_id)],'NATIVE_BREAKEVEN_TRIGGERED')
                    if p.be_armed:self._cancel_growth()
                except (ValueError,AttributeError,TypeError) as error:
                    self._restore_failed=True;self._begin_drain(now,'BTC_ECONOMIC',[str(self.config.btc_id)],str(error))
        if self._liquidating and self.liquidation_audit:
            row=self.liquidation_audit[-1];row['close_fills'].append({'trade_id':tid,'quantity':str(q),'price':str(price)})
            row['close_value']=str(D(row['close_value'])+q*price)
        self._chain_audit('NATIVE_FILL',self.fill_audit[-1])
        self._terminal_event(event,only_if_closed=True)
        self._sync_protection(now);self._persist_checkpoint()

    def _terminal_event(self,event,only_if_closed=False,failed=False):
        oid=str(event.client_order_id);info=self._owned.get(oid)
        if info is None:return
        order=self.cache.order(event.client_order_id)
        if only_if_closed and (order is None or not order.is_closed):return
        del self._owned[oid];now=self.clock.timestamp_ns();p=self.btc.parent;purpose=info['purpose']
        filled=order.filled_qty.as_decimal() if order is not None else ZERO
        if p is not None and p.id==info['parent_id']:
            if purpose.startswith('ENTRY'):
                if filled<info['quantity'] or failed:
                    self.btc.stop_growth('PARTIAL_OR_FAILED_ENTRY_TERMINAL_HOLD')
                if purpose=='ENTRY_MARKET' and p.first_filled==p.first_quantity:p.first_terminal=True
            elif purpose=='BE_STOP' and (info.get('triggered') or filled>0):
                self._begin_drain(now,'BTC_ECONOMIC',[str(self.config.btc_id)],'NATIVE_BREAKEVEN_TRIGGERED')
            elif purpose in ('BE_STOP','TP_GTC') and failed:
                self.target_blockers['NATIVE_PROTECTION_TERMINAL:'+p.id+':'+purpose+':'+str(info['level'])]={'reason':'NATIVE_DENIED_REJECTED_EXPIRED_HOLD','clock_ns':str(now),'parent_id':p.id}
                self.btc.stop_growth('NATIVE_REQUIRED_PROTECTION_HOLD');self._cancel_growth()
        self._reconcile_drains(now);scope=self._scope_for(info['instrument_id'])
        if scope is not None and (purpose!='DRAIN' or filled>0):
            tick=self._quotes.get(info['instrument_id'])
            if tick is not None:self._execute_drain(tick,now,scope)
        self._reconcile_btc(now)
        if scope is None and info['instrument_id']==self.config.btc_id:
            self._sync_protection(now)
            tick=self._quotes.get(self.config.btc_id);current=self.btc.parent
            if (purpose.startswith('ENTRY') and current is not None and current.id==info['parent_id']
                    and tick is not None and bbo_status(tick,now)[0]):self._execute_entry(tick,now)
        self._persist_checkpoint()

    def on_order_canceled(self,event):self._terminal_event(event)
    def on_order_denied(self,event):self._terminal_event(event,failed=True)
    def on_order_rejected(self,event):self._terminal_event(event,failed=True)
    def on_order_expired(self,event):self._terminal_event(event,failed=True)

    def _request_contract_identity(self):
        profile=getattr(self.config.margin_policy,'_profile',None)
        return {'model_id':MODEL_ID,'policy_version':self.config.policy.version,
            'implementation_sources':dict(self._admission_sources),'sol_market_model':'UNAPPROVED_DISABLED',
            'fixed_parameters':{'EMA':34,'WilderATR':14,'confirmation_ATR':'0.5','notional_multiplier':'7.875',
                'discount':'0.005','TP_distances':['0.0125','0.025','0.0375'],'TP_weights':['0.30','0.40','0.30'],
                'TP1_trigger':'FIRST_POSITIVE_ACTUAL_FILL','new_entry':'NEW_CLOSED_D1_OR_POST_REGIME_H4'},
            'bbo_and_mark_max_age_ns':FRESH_NS,'drain_interval_ns':DRAIN_NS,
            'limit_rounding':'OFFICIAL_OUTWARD_TICK_AND_SIGNIFICANT_FIGURES',
            'stop_trigger':'NATIVE_MARK_PRICE','stop_market_slippage':'STOCK_ADAPTER_SETTING_NOT_UNBOUNDED_MARKET',
            'backtest_stop_parity':'HOLD_NATIVE_1_231_MARK_TRIGGER_NOT_PROVEN',
            'qualification_binding':'SOURCE_BOUND_ECONOMIC_QUALIFICATION_NOT_RUN',
            'reduce_only_floor':REDUCE_FLOOR_POLICY,'RO_exit_geometry':'TP_SUM_ALTERNATIVE_TO_FULL_BE_NOT_ADDITIVE',
            'profile_evidence':asdict(profile.evidence) if profile is not None else None,
            'instruments':{k:{'quantity_increment':str(v.quantity_increment),'min_notional':str(v.min_notional),
                'max_market_notional':str(v.max_market_notional),'max_limit_notional':str(v.max_limit_notional)}
                for k,v in sorted(getattr(profile,'instruments',{}).items())}}

    def _checkpoint_identity(self):
        return {'schema':SCHEMA,'sources':self._admission_sources,'policy':asdict(self.config.policy),
            'execution_policy_hash':self.config.execution_policy_hash,'strategy_id':str(self.id),
            'request_model_id':MODEL_ID,'request_contract':self._request_contract_identity(),
            'seed_btc_sha256':sha256(canonical(self.config.seed_btc_days)).hexdigest(),
            'active_seed':self.config.active_seed,'exit_fee_rate':self.config.exit_fee_rate,
            'execution_limits':asdict(self.config.limits),'instruments':[str(self.config.btc_id),str(self.config.sol_id)],
            'start_ns':self.config.trading_start_open_ns,'end_ns':self.config.terminal_close_at_ns}

    def _checkpoint_document(self):
        if not callable(self.config.continuity_reader):raise ValueError('CM2_NATIVE_OBSERVER_CONTINUITY_REQUIRED')
        return {'identity':self._checkpoint_identity(),'native':self._native_checkpoint_binding(),
            'observer':self.config.continuity_reader(),'feed_continuity':self._feed_checkpoint_binding(),
            'audit_continuity':[len(self.fill_audit),len(self.cm2_audit),len(self._order_audit),self._retained_audit_chain],
            'domain':{'btc':self.btc.snapshot(),'safety':asdict(self.safety),
                'owned':{oid:{**v,'instrument_id':str(v['instrument_id']),'client_order_id':str(v['client_order_id'])} for oid,v in self._owned.items()},
                'seen_trade_ids':sorted(self._seen_trade_ids),'needs_daily':self._needs_daily,'drain':self._drain,
                'restore_failed':self._restore_failed,'risk_unknown':self._risk_unknown,'liquidating':self._liquidating,
                'protection_holds':{k:v for k,v in self.target_blockers.items() if k.startswith('NATIVE_PROTECTION_TERMINAL:')}}}

    def on_load(self,state):
        self._checkpoint_loaded=False;self._restore_failed=True
        if set(state)!={KEY} or type(state[KEY]) is not bytes:raise ValueError('CM2_CHECKPOINT_STATE_KEYS')
        body=state[KEY];document=decode(json.loads(body))
        if canonical(document)!=body:raise ValueError('CM2_CHECKPOINT_NONCANONICAL')
        for key,current in (('identity',self._checkpoint_identity()),('native',self._native_checkpoint_binding()),
                ('feed_continuity',self._feed_checkpoint_binding())):
            if canonical(document[key])!=canonical(current):raise ValueError('CM2_CHECKPOINT_BINDING_'+key)
        if not callable(self.config.continuity_reader) or canonical(document['observer'])!=canonical(self.config.continuity_reader()):
            raise ValueError('CM2_CHECKPOINT_OBSERVER_CONTINUITY')
        if document['audit_continuity']!=[len(self.fill_audit),len(self.cm2_audit),len(self._order_audit),self._retained_audit_chain]:
            raise ValueError('CM2_CHECKPOINT_AUDIT_CONTINUITY')
        store=self.config.checkpoint_store;latest=store.read() if store is not None else None
        if latest is None or latest[1]!=body:raise ValueError('CM2_CHECKPOINT_DURABLE_LATEST')
        domain=document['domain'];owned={}
        for oid,v in domain['owned'].items():owned[oid]={**v,'instrument_id':InstrumentId.from_str(v['instrument_id']),'client_order_id':ClientOrderId(v['client_order_id'])}
        drains=domain['drain']
        if not set(drains).issubset({'GLOBAL','BTC_ECONOMIC','SOL_SUBORDINATE'}):raise ValueError('CM2_DRAIN_SCOPE_UNKNOWN')
        for drain in drains.values():validate_drain(drain['state'],(str(self.config.btc_id),str(self.config.sol_id)))
        safety=SafetyState(**domain['safety'])
        if safety.emergency_latched and not safety.global_latched:raise ValueError('CM2_EMERGENCY_LATCH_INCONSISTENT')
        self.btc.restore(domain['btc']);self.safety=safety;self._owned=owned
        self._seen_trade_ids=set(domain['seen_trade_ids']);self._needs_daily=domain['needs_daily'];self._drain=drains
        self._restore_failed=domain['restore_failed'];self._risk_unknown=domain['risk_unknown'];self._liquidating=domain['liquidating']
        self.target_blockers.update(domain['protection_holds'])
        self._checkpoint_revision=latest[0];self._checkpoint_loaded=True
        self._loaded_native_binding=canonical(document['native']);self._loaded_feed_binding=canonical(document['feed_continuity'])
        self._loaded_observer_binding=canonical(document['observer'])

    def _audit(self,now,reason):
        p=self.btc.parent
        row={'ts_ns':str(now),'reason':reason,'parent_id':p.id if p else None,'policy_version':self.config.policy.version,
            'global_latch':self.safety.global_latched}
        self.cm2_audit.append(row);self._chain_audit('DOMAIN_AUDIT',row)

    def reporting_state(self):
        positions=self.cache.positions_open();orders=[*self.cache.orders_open(),*self.cache.orders_inflight()]
        terminal=self.clock.timestamp_ns()>=self.config.terminal_close_at_ns
        lifecycle={'reason':'TERMINAL_BOUNDARY_SETTLEMENT' if terminal else 'NOT_REACHED',
            'status':'FLAT' if terminal and not positions and not orders and not self._owned else 'OPEN'}
        request=self._request_contract_identity()
        return _report_value({'liquidations':self.liquidation_audit,'liquidation_lockout':self._liquidating,
            'terminal_lifecycle':lifecycle,'terminal_open_orders':len(orders),
            'pre_submit_tier_margin_gate_blocks':self.pre_submit_gate_blocks,'marked_equity_checkpoints':[],
            'fill_audit':self.fill_audit,'entry_sizing_audit':self.entry_sizing_audit,
            'emergency_drawdown_control':{'status':'LATCHED' if self.safety.emergency_latched else 'DISABLED_RESEARCH' if self.config.policy.emergency_drawdown_fraction is None else 'ARMED',
                'configured_fraction':self.config.policy.emergency_drawdown_fraction,'state':asdict(self.safety)},
            'cm2':{'policy':asdict(self.config.policy),'request_execution_model_id':MODEL_ID,'request_contract':request,
                'request_contract_sha256':sha256(canonical(request)).hexdigest(),'btc_market':self.btc.snapshot(),
                'execution_comparability':'NEW_UNQUALIFIED_BTC_MARKET_MODEL','drain_state':self._drain,
                'drain_lifecycle':self.drain_audit,'audit':self.cm2_audit,'child_permission_audit':self.child_permission_audit,
                'order_admission_audit':list(self._order_audit.values()),'target_blockers':self.target_blockers,
                'orphan_intervals':self.orphan_intervals,'open_orphan_since_ns':self.orphan_started_ns,
                'checkpoint_revision':self._checkpoint_revision,'sol_market_model':'UNAPPROVED_DISABLED',
                'capacity_model':{'model':'ZERO_IMPACT_ORDER_LEAVES_DIAGNOSTIC','participation':None,'official_venue_caps':'PER_REQUEST'},
                'structural_diagnostics':'CODE0_ONLY_NOT_NATIVE_QUALIFIED',
                'liquidation_measurement':{'contract':'NATIVE_MARK_FIRST_PUBLIC_TIER_MAINTENANCE','checks':self._liquidation_checks,'unknown_checks':self._liquidation_unknown}}})

def _report_value(value):
    if isinstance(value,D):return str(value)
    if isinstance(value,dict):return {str(k):_report_value(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_report_value(v) for v in value]
    if value is None or type(value) in (str,int,float,bool):return value
    raise TypeError('CM2_REPORT_UNSUPPORTED_VALUE:'+type(value).__name__)
