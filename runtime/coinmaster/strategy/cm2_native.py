"""CM2 BTC-first native adapter. ONE economic owner, native money/orders only."""
from __future__ import annotations
from dataclasses import asdict,replace
from datetime import datetime,timezone
from decimal import Decimal as D,ROUND_FLOOR,ROUND_CEILING,ROUND_HALF_EVEN
from hashlib import sha256
from pathlib import Path
import json
from nautilus_trader.config import StrategyConfig
from nautilus_trader.core.data import Data
from nautilus_trader.model.data import BarType,DataType
from nautilus_trader.model.enums import OrderSide,TimeInForce
from nautilus_trader.model.identifiers import InstrumentId,ClientId,ClientOrderId
from nautilus_trader.trading.strategy import Strategy
from coinmaster.domain.wave_overlay import DailyBar
from coinmaster.strategy.cm2_reference_policy import ReferenceConfig,ReferenceBtcPolicy,DAY,HOUR
from coinmaster.strategy.cm2_policy import pending_effects
from coinmaster.strategy.cm2_execution import ExecutionLimits,NativeExposure,SafetyState,order_plan
from coinmaster.strategy.cm2_checkpoint import KEY,SCHEMA,canonical,decode
from coinmaster.strategy.cm2_order_contract import (MODEL_ID,FRESH_NS,DRAIN_NS,REDUCE_FLOOR_POLICY,
    request_terms,request_cap,RequestTerms,validate_request,bbo_status,drain_update,validate_drain)
from coinmaster.venues.margin_policy import MarginMark
from coinmaster.venues.marks import VenueMark
from coinmaster.venues.signals import DailySignalBar
ZERO=D(0)


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


class CM2StrategyConfig(StrategyConfig,frozen=True):
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
    policy: ReferenceConfig
    limits: ExecutionLimits
    margin_policy: object
    active_seed: D
    btc_step: D
    trading_start_open_ns: int
    terminal_close_at_ns: int
    seed_days: tuple = ()
    seed_ohlc: tuple = ()
    exit_fee_rate: D = D('.000432')
    execution_policy_hash: str = ''
    funding_reader: object = None
    checkpoint_store: object = None
    continuity_reader: object = None


class CM2Strategy(Strategy):
    def __init__(self,config):
        if not isinstance(config.policy,ReferenceConfig):raise ValueError("OLD_CM2_POLICY_VERSION_REJECTED")
        super().__init__(config)
        self.reference=ReferenceBtcPolicy(config.policy.candidate,flags=config.policy.flags,
            btc_step=config.btc_step,
            trading_start_ns=config.trading_start_open_ns,terminal_ns=config.terminal_close_at_ns,
            max_quote_age_ns=FRESH_NS,initial_btc_equity=config.active_seed)
        ohlc={int(ns):(high,low) for ns,high,low in config.seed_ohlc}
        for day in config.seed_days:
            ns=int(day.close_time.timestamp()*1e9)
            if ns not in ohlc:raise ValueError("GENUINE_D1_OHLC_SEED_REQUIRED")
            self.reference.accept_closed_day(day,receipt_ns=config.trading_start_open_ns,
                btc_high=float(ohlc[ns][0]),btc_low=float(ohlc[ns][1]))
        self.safety=SafetyState(emergency_peak_equity=config.active_seed)
        self._latest_marks={};self._quotes={};self._owned={};self._order_audit={};self._seen_trade_ids=set()
        self._days_pending={};self._queued_tp={};self._needs_daily=False;self._tp_ready_ns=0
        self._drain={};self._drain_dispatching=set();self._risk_unknown=False;self._liquidating=False;self._restore_failed=False
        self._btc_source_frame=None;self._capital_last=None;self._capital_unknown=None
        self.fill_audit=[];self.entry_sizing_audit=[];self.pre_submit_gate_blocks=[]
        self.cm2_audit=[];self.child_permission_audit=[];self.drain_audit=[]
        self.target_blockers={};self.orphan_started_ns=None;self.orphan_intervals=[]
        self.liquidation_audit=[];self._liquidation_checks=0;self._liquidation_unknown=0
        self._retained_audit_chain='0'*64;self._checkpoint_revision=0;self._checkpoint_loaded=False
        self.terminal_lifecycle={"status":"NOT_REACHED","reason":""}
        self._admission_sources={name:sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ('cm2_native.py','cm2_reference_policy.py','cm2_execution.py','cm2_checkpoint.py','cm2_order_contract.py')}

    def on_start(self):
        if self.cache.instrument(self.config.btc_id).size_increment.as_decimal()!=self.config.btc_step:
            raise ValueError('CM2_NATIVE_REFERENCE_LOT_BINDING')
        if not self._checkpoint_loaded and (self.cache.positions_open() or self.cache.orders_open() or self.cache.orders_inflight()):
            raise ValueError("CM2_FRESH_START_REQUIRES_EMPTY_NATIVE_CACHE_NO_RECOVERY")
        if self._checkpoint_loaded and (canonical(self._native_checkpoint_binding())!=self._loaded_native_binding
                or canonical(self._feed_checkpoint_binding())!=self._loaded_feed_binding
                or not callable(self.config.continuity_reader)
                or canonical(self.config.continuity_reader())!=self._loaded_observer_binding):
            self._restore_failed=True;raise ValueError("CM2_NATIVE_CONTINUITY_CHANGED_BEFORE_START")
        for iid,dt in ((self.config.btc_id,self.config.btc_mark_data_type),(self.config.sol_id,self.config.sol_mark_data_type)):
            self.subscribe_data(dt,client_id=self.config.mark_client_id);self.subscribe_quote_ticks(iid)
        for dt in (self.config.btc_signal_data_type,self.config.sol_signal_data_type,self.config.h4_data_type):
            self.subscribe_data(dt,client_id=self.config.signal_client_id)

    def on_data(self,data):
        item=getattr(data,'data',data);now=self.clock.timestamp_ns()
        self._finalize_btc_receipt(now)
        if isinstance(item,VenueMark):
            old=self._latest_marks.get(item.instrument_id)
            if old is not None and item.ts_event<old.ts_event:return
            self._latest_marks[item.instrument_id]=item
            self.config.margin_policy.update_mark(MarginMark(item.instrument_id,D(str(item.price)),item.ts_event))
            self._check_liquidation(now);self._check_emergency_drawdown(now)
        elif isinstance(item,DailySignalBar) and getattr(item,'hours',None) is None:
            ns=item.ts_event
            if item.instrument_id not in (self.config.btc_id,self.config.sol_id):return
            if self.reference.signals and ns<=int(self.reference._features.bars[-1].close_time.timestamp()*1e9):return
            group=self._days_pending.setdefault(ns,{})
            if item.instrument_id in group:raise ValueError("DUPLICATE_DAILY_SOURCE")
            group[item.instrument_id]=item
            if all(i in group for i in (self.config.btc_id,self.config.sol_id)):
                b,s=group[self.config.btc_id],group[self.config.sol_id]
                available=max(ns,b.ts_init,s.ts_init)
                bar=DailyBar(datetime.fromtimestamp((ns-DAY)/1e9,timezone.utc),
                    datetime.fromtimestamp(ns/1e9,timezone.utc),datetime.fromtimestamp(available/1e9,timezone.utc),
                    float(b.open),float(b.close),float(s.close))
                self.reference.accept_closed_day(bar,receipt_ns=now,btc_high=float(b.high),btc_low=float(b.low))
                del self._days_pending[ns];self._needs_daily=True;self._evaluate_daily(now)
        elif getattr(item,'hours',None)==4 and item.instrument_id==self.config.btc_id:
            self.reference.accept_closed_btc_h4(open_ns=item.open_time_ns,close_ns=item.ts_event,
                available_ns=item.ts_init,receipt_ns=now,close=D(str(item.close)))

    def _native_btc_capital(self,now):
        # Owner binding: the SAME actual shared native capital as reference A.
        # Per-BTC attribution below is audit only; never a second account/book.
        account=self.cache.account_for_venue(self.config.btc_id.venue);reader=self.config.funding_reader
        if account is None or account.base_currency is None or not callable(reader) or getattr(reader,'journal',None) is None:
            raise ValueError("NATIVE_CAPITAL_OR_FUNDING_UNKNOWN")
        currency=account.base_currency;cash=account.balance_total(currency)
        if cash is None or cash.currency!=currency:raise ValueError("NATIVE_CASH_CURRENCY_UNKNOWN")
        snapshot=self._snapshot(now)
        if snapshot.unknown_orders or not snapshot.data_known or not snapshot.equity.is_finite():
            raise ValueError("ACTUAL_NATIVE_EQUITY_UNKNOWN")
        realized_total=funding_total=ZERO;btc_realized=btc_funding=ZERO;attribution_known=True
        for iid in (self.config.btc_id,self.config.sol_id):
            instrument=self.cache.instrument(iid)
            if instrument.settlement_currency!=currency:raise ValueError("SETTLEMENT_CURRENCY_UNKNOWN")
            funding=reader(iid)
            if not isinstance(funding,D) or not funding.is_finite():raise ValueError("NATIVE_SIGNED_FUNDING_UNKNOWN")
            funding_total+=funding
            realized=self.portfolio.realized_pnl(iid,account_id=account.id)
            if realized is None or realized.currency!=currency:attribution_known=False
            else:
                realized_total+=realized.as_decimal()
                if iid==self.config.btc_id:btc_realized=realized.as_decimal()
            if iid==self.config.btc_id:btc_funding=funding
        position=self._position(self.config.btc_id)
        open_pnl=ZERO
        if position is not None:
            mark=self._latest_marks.get(self.config.btc_id)
            if mark is None or not 0<=now-mark.ts_event<=FRESH_NS:raise ValueError("BTC_CAPITAL_CAUSAL_MARK_UNKNOWN")
            upnl=self.portfolio.unrealized_pnl(self.config.btc_id,
                price=self.cache.instrument(self.config.btc_id).make_price(mark.price),account_id=account.id)
            if upnl is None or upnl.currency!=currency:raise ValueError("NATIVE_BTC_UPNL_UNKNOWN")
            open_pnl=upnl.as_decimal()
        bridge=self.config.active_seed+realized_total+funding_total-cash.as_decimal() if attribution_known else None
        self.reference.note_btc_funding(str(btc_funding))
        result=dict(equity=snapshot.equity,open_pnl=open_pnl,funding=btc_funding,
            native_qty=(position.quantity.as_decimal()*(D(1) if position.is_long else D(-1))) if position else ZERO,
            position_id=str(position.id) if position else '',position_open_ns=position.ts_opened if position else 0,
            revision=self.reference.btc_revision,currency=str(currency),
            basis='TOTAL_ACTUAL_NATIVE_CASH_PLUS_HELD_NATIVE_UPNL',
            btc_attribution_audit={'status':'EXACT' if bridge==0 else 'UNKNOWN_NATIVE_ATTRIBUTION_BRIDGE',
                'btc_realized':btc_realized if attribution_known else None,'btc_signed_funding':btc_funding,
                'btc_upnl':open_pnl,'btc_derived_sizing_audit':self.config.active_seed+btc_realized+btc_funding+open_pnl if attribution_known else None,
                'unallocated_bridge':bridge,'trading_input':False,'fees':'ALREADY_INCLUDED_NATIVE_REALIZED'})
        self._capital_last=result;self._capital_unknown=None
        return result


    def _capture_btc_source(self,now):
        try:
            capital=self._native_btc_capital(now)
            self._btc_source_frame={**capital,'source_ns':now}
        except (ValueError,AttributeError,TypeError) as error:
            self._capital_unknown=str(error);self._btc_source_frame=None

    def _finalize_btc_receipt(self,now):
        frame=self._btc_source_frame
        if frame is None or now<=frame['source_ns']:return
        self._btc_source_frame=None
        try:
            current=self._native_btc_capital(now)
            if (now-frame['source_ns']>FRESH_NS or current['revision']!=frame['revision']
                    or any(current[k]!=frame[k] for k in ('equity','open_pnl','position_id','position_open_ns','native_qty','funding'))):return
            self.reference.observe_committed_btc(source_ns=frame['source_ns'],receipt_ns=now,
                revision=frame['revision'],equity=frame['equity'],open_pnl=frame['open_pnl'],
                native_qty=frame['native_qty'],position_id=frame['position_id'],position_open_ns=frame['position_open_ns'],
                btc_competing_owner=self._btc_competing_owner())
        except (ValueError,AttributeError,TypeError) as error:self._capital_unknown=str(error)

    def _evaluate_daily(self,now):
        if not self._needs_daily or now>=self.config.terminal_close_at_ns or self.safety.global_latched:return
        try:capital=self._native_btc_capital(now)['equity']
        except (ValueError,AttributeError,TypeError) as error:
            self._capital_unknown=str(error);capital=ZERO
            if self.reference.parent is None:return
        decision=self.reference.decide_on_day(native_btc_marked_equity=capital,decision_ns=now)
        # Consume the input before native side effects: synchronous close/cancel
        # reconciliation may re-arm the next causal decision.
        self._needs_daily=False
        if decision.action=='BTC_CLOSE':
            self.reference.stop_entry_remainder(decision.parent_id,reason=decision.reason)
            self.reference.revoke_c1(now,'MANDATORY_BTC_CLOSE');self._queued_tp.clear()
            self._begin_drain(now,'BTC_ECONOMIC',[str(self.config.btc_id)],decision.reason)
        elif decision.action=='BTC_ENTRY':
            self._audit(now,'BTC_ENTRY_INTENT')
        parent=self.reference.parent
        if parent is not None and parent.split_terminal and parent.filled_quantity>0 and not parent.close_reason:
            live=frozenset(info['level'] for info in self._owned.values()
                if info['instrument_id']==self.config.btc_id and info['purpose']=='TP_GTC' and info.get('level') is not None)
            pending=frozenset(info['level'] for info in self._owned.values()
                if info['instrument_id']==self.config.btc_id and info.get('level') is not None)|frozenset(self._queued_tp)
            for plan in self.reference.ordinary_tp_permissions(parent.id,decision_ns=now,
                    native_resting_levels=live,native_pending_levels=pending):self._queued_tp[plan.level]=plan
        self._persist_checkpoint()
        return decision.action=='BTC_CLOSE'

    def _btc_competing_owner(self):
        quote=self._quotes.get(self.config.btc_id)
        for plan in self._queued_tp.values():
            if plan.conditional_ioc or quote is None:return True
            parent=self.reference.parent
            if parent is None or (quote.bid_price.as_decimal()>=plan.raw_limit_price if parent.side==1 else quote.ask_price.as_decimal()<=plan.raw_limit_price):return True
        for info in self._owned.values():
            if info['instrument_id']!=self.config.btc_id or info['purpose'].startswith('C1_'):continue
            if info['purpose']!='TP_GTC' or quote is None:return True
            threshold=info.get('raw_limit_price')
            if threshold is None:return True
            p=self.reference.parent
            if p is None or (quote.bid_price.as_decimal()>=threshold if p.side==1 else quote.ask_price.as_decimal()<=threshold):return True
        return any(o.instrument_id==self.config.btc_id and str(o.client_order_id) not in self._owned
            for o in [*self.cache.orders_open(),*self.cache.orders_inflight()])

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

    def _begin_drain(self,now,scope,ids,reason):
        previous=self._drain.get(scope)
        state=drain_update(previous['state'] if previous else None,now,ids)
        self._drain[scope]={'state':state,'reason':reason,
            'parent_id':previous['parent_id'] if previous else (self.reference.parent.id if self.reference.parent else None)}
        if previous is None:
            self.drain_audit.append({'timestamp_ns':now,'scope':scope,'event':'START','state':state,'reason':reason})
        for iid in (self.config.btc_id,self.config.sol_id):
            if str(iid) in ids:
                for order in self._orders(iid):self.cancel_order(order)
        name='CM2_'+scope+'_'+str(self.id)
        if name not in self.clock.timer_names and not state['reconcile_required']:
            if now>=state['deadline_ns']:self._on_drain_deadline(None)
            else:self.clock.set_time_alert_ns(name,state['deadline_ns'],callback=self._on_drain_deadline)

    def _on_drain_deadline(self,_event):
        now=self.clock.timestamp_ns()
        for scope,drain in self._drain.items():
            state=drain['state']
            if now>=state['deadline_ns'] and not state['reconcile_required']:
                state['reconcile_required']=True
                self.drain_audit.append({'timestamp_ns':now,'scope':scope,'event':'RECONCILE_REQUIRED','state':dict(state)})
        self._persist_checkpoint()

    def _reconcile_drains(self,now):
        for scope,drain in list(self._drain.items()):
            ids=drain['state']['scoped_zero_ids']
            complete=all(self._position(iid) is None and not self._orders(iid)
                and not any(v['instrument_id']==iid for v in self._owned.values())
                for iid in (self.config.btc_id,self.config.sol_id) if str(iid) in ids)
            if not complete:continue
            if scope=='BTC_ECONOMIC':
                p=self.reference.parent
                if p is not None and p.id==drain['parent_id']:
                    self.reference.confirm_btc_close(p.id,receipt_ns=now,
                        native_btc_flat=True,native_btc_owners_terminal=True)
                    self._queued_tp.clear()
                    self._needs_daily=drain['reason']=='REGIME'
            name='CM2_'+scope+'_'+str(self.id)
            if name in self.clock.timer_names:self.clock.cancel_timer(name)
            self.drain_audit.append({'timestamp_ns':now,'scope':scope,'event':'NATIVE_SCOPED_FLAT'})
            del self._drain[scope]
            # GLOBAL safety stays latched independently; SOL drain never owns
            # the BTC economic reset or a later BTC episode's target.

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
                self.reference.revoke_c1(now,'GLOBAL_EMERGENCY')
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
        self.reference.revoke_c1(now,'GLOBAL_LIQUIDATION')
        self.liquidation_audit.append({'trigger_ts':str(now),'marked_equity':str(s.equity),
            'tier_maintenance_margin':str(maintenance),'close_fills':[],'close_value':'0','status':'ARMED'})
        self._begin_drain(now,'GLOBAL',[str(self.config.btc_id),str(self.config.sol_id)],'LIQUIDATION')

    def on_quote_tick(self,tick):
        now=self.clock.timestamp_ns()
        fresh,reason=bbo_status(tick,now)
        old=self._quotes.get(tick.instrument_id)
        if not fresh or old is not None and tick.ts_event<old.ts_event:
            self.pre_submit_gate_blocks.append({'timestamp':str(now),'instrument':str(tick.instrument_id),'reason':reason})
            return
        self._quotes[tick.instrument_id]=tick
        if now<self.config.trading_start_open_ns:return
        self._check_emergency_drawdown(now)
        if now>=self.config.terminal_close_at_ns and not self.safety.global_latched:
            self.safety.global_latched=True;self.safety.reason='TERMINAL_BOUNDARY_SETTLEMENT'
            self.reference.revoke_c1(now,'TERMINAL_BOUNDARY')
            self._begin_drain(now,'GLOBAL',[str(self.config.btc_id),str(self.config.sol_id)],self.safety.reason)
        # A close already owned on arrival consumes this BTC callback even if
        # reconciliation completes it now. The next callback may share its ns.
        close_phase='BTC_ECONOMIC' in self._drain
        btc_close_phase=tick.instrument_id==self.config.btc_id and close_phase
        self._reconcile_drains(now)
        scope=self._scope_for(tick.instrument_id)
        if scope is not None:
            self._execute_drain(tick,now,scope)
        elif not self.safety.global_latched and not self._restore_failed and tick.instrument_id==self.config.btc_id:
            if not btc_close_phase:btc_close_phase=self._evaluate_daily(now)
            if self._scope_for(self.config.btc_id) is not None:self._execute_drain(tick,now,'BTC_ECONOMIC')
            elif btc_close_phase:pass  # completing quote cannot also select q0
            elif self.reference.c1 is not None and self.reference.c1.state!='RELEASED':
                self._execute_c1(tick,now)
                # A revoked/held token blocks increases, not harmless TP leaves.
                if not any(v['purpose'].startswith('C1_') for v in self._owned.values()):self._execute_targets(tick,now)
            else:
                self._execute_entry(tick,now);self._execute_targets(tick,now)
        elif tick.instrument_id==self.config.sol_id and self._position(self.config.sol_id) is not None:
            # No SOL alpha is active in this BTC-only stage. Known subordinate
            # inventory drains without changing the BTC economic decision.
            if self._scope_for(self.config.sol_id) is None:
                self._begin_drain(now,'SOL_SUBORDINATE',[str(self.config.sol_id)],'SOL_COMPONENT_INACTIVE')
            self._execute_drain(tick,now,'SOL_SUBORDINATE')
        self._reconcile_drains(now)
        if (not self.safety.global_latched and not self._restore_failed and not close_phase
                and not btc_close_phase and 'BTC_ECONOMIC' not in self._drain
                and self.reference.consume_h4_reentry_facts(now)):
            self._needs_daily=True;self._evaluate_daily(now)
        self._capture_btc_source(now)

    def _execute_drain(self,tick,now,scope):
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

    def _execute_entry(self,tick,now):
        p=self.reference.parent
        if p is None or p.close_reason or p.split_terminal:return
        owned=[v for v in self._owned.values() if v['instrument_id']==self.config.btc_id and v['purpose'].startswith('ENTRY')]
        pending='UNKNOWN' if len(owned)>1 else ('DISCOUNT_GTC' if owned[0]['purpose']=='ENTRY_DISCOUNT' else 'IOC') if owned else 'NONE'
        if p.q0_ns is None:
            executable=tick.ask_price.as_decimal() if p.side==1 else tick.bid_price.as_decimal()
            self.reference.observe_entry_q0(p.id,quote_ns=tick.ts_event,executable_price=executable,
                canonical_wire_price=self._reference_limit(self.config.btc_id,executable).as_decimal())
            self._persist_checkpoint();return
        if p.selected_quantity is None:
            if tick.ts_event<=p.q0_ns:return
            try:
                selected=self.reference.select_entry_q1(p.id,quote_ns=tick.ts_event,
                    bid=tick.bid_price.as_decimal(),ask=tick.ask_price.as_decimal())
                if selected<=0:raise ValueError('ZERO_NET_ENTRY')
                self.reference.begin_split(p.id,now_ns=tick.ts_event)
            except ValueError as error:
                self.reference.stop_entry_remainder(p.id,reason=str(error))
                if not owned and p.filled_quantity==0:self.reference.confirm_empty_entry_terminal(p.id,native_pending=False)
                self._needs_daily=False;self._audit(now,'ENTRY_SELECTION_DENIED:'+str(error));return
            current=self.reference.parent
            self.entry_sizing_audit.append({'episode_id':p.id,'q0_ns':str(p.q0_ns),'q1_ns':str(tick.ts_event),
                'reference_btc_qty':str(D(current.gross_lots)*self.config.btc_step),
                'net_submitted_btc_qty':str(selected),'omitted_zero_levels':sorted(current.omitted_levels),
                'branch':'PASSIVE_NET_ZERO_LEVELS' if current.passive_selection else 'MARKETABLE_FULL_ENTRY_FALLBACK',
                'reference_target_lots':dict(enumerate(current.reference_targets)),
                'confirmed_native_entry_qty':str(current.filled_quantity)})
        plan=self.reference.entry_plan(p.id,now_ns=tick.ts_event,bid=tick.bid_price.as_decimal(),
            ask=tick.ask_price.as_decimal(),pending_kind=pending)
        if plan.action in ('CANCEL','CANCEL_RESTING_LIMIT'):
            for order in self._orders(self.config.btc_id):
                info=self._owned[str(order.client_order_id)]
                if info['purpose']=='ENTRY_DISCOUNT' or plan.action=='CANCEL':self.cancel_order(order)
        elif plan.action in ('IOC','DISCOUNT_GTC'):
            submitted=self._send(self.config.btc_id,plan.quantity,p.side,
                'ENTRY_DISCOUNT' if plan.action=='DISCOUNT_GTC' else 'ENTRY_IOC',now,tick,
                raw_limit=plan.raw_limit_price,reason='BTC_SPLIT')
            if not submitted and self.reference.parent is not None:
                self.reference.stop_entry_remainder(p.id,reason='LOCAL_ENTRY_ADMISSION_DENIED')
                if self.reference.parent.filled_quantity==0 and not self._orders(self.config.btc_id) and not self._owned:
                    self.reference.confirm_empty_entry_terminal(p.id,native_pending=False)

    def _queue_confirmed_targets(self,ready_ns):
        p=self.reference.parent
        if p is None or p.close_reason or not p.split_terminal or p.filled_quantity<=0:return
        for target in self.reference.confirmed_targets(p.id):
            if target.level in self._queued_tp or any(v['instrument_id']==self.config.btc_id and v.get('level')==target.level for v in self._owned.values()):continue
            self._queued_tp[target.level]=replace(target,ready_ns=ready_ns)

    def _execute_targets(self,tick,now):
        p=self.reference.parent
        if p is None or p.close_reason or not p.split_terminal or p.filled_quantity<=0 or now<self._tp_ready_ns:return
        if self.reference.c1 is not None and self.reference.c1.state in ('CUT_RESOLVING','RESTORE_RESOLVING'):return
        pending=frozenset(v['level'] for v in self._owned.values() if v['instrument_id']==self.config.btc_id and v.get('level') is not None)
        for level,target in list(self._queued_tp.items()):
            if level in pending or now<target.ready_ns:continue
            if target.conditional_ioc:
                quantity=self.reference.executable_tp_quantity(target,quote_ns=tick.ts_event,
                    bid=tick.bid_price.as_decimal(),ask=tick.ask_price.as_decimal(),native_pending_levels=pending)
                if quantity<=0:continue
                sent=self._send(self.config.btc_id,quantity,-p.side,'TP_IOC',now,tick,
                    reduce_only=True,level=level,reason='BTC_CONDITIONAL_TP',decision_index=target.decision_index)
            else:
                wire=self._reference_limit(self.config.btc_id,target.raw_limit_price)
                crossed=(tick.bid_price.as_decimal()>=wire.as_decimal() if p.side==1 else tick.ask_price.as_decimal()<=wire.as_decimal())
                if crossed and not target.positive_ioc_candidate:
                    # A marketable zero/partial resting plan is terminally
                    # suppressed. Ordinary D1 permission remains independent.
                    del self._queued_tp[level];continue
                sent=self._send(self.config.btc_id,target.quantity,-p.side,
                    'TP_IOC' if crossed else 'TP_GTC',now,tick,reduce_only=True,level=level,
                    raw_limit=None if crossed else target.raw_limit_price,
                    reason='BTC_POSITIVE_TP_CATCHUP' if crossed else 'BTC_RESTING_TP',decision_index=target.decision_index)
            # Synchronous native terminal callbacks may already have replaced
            # this same level with a retry. Remove only the submitted instance.
            if sent and self._queued_tp.get(level) is target:del self._queued_tp[level]

    def _execute_c1(self,tick,now):
        t=self.reference.c1;p=self.reference.parent
        if t is None or p is None:return
        own_c1=[v for v in self._owned.values() if v['purpose'].startswith('C1_')]
        if t.revoked:
            for order in self._orders(self.config.btc_id):
                if self._owned[str(order.client_order_id)]['purpose'].startswith('C1_'):self.cancel_order(order)
            return
        if self._btc_competing_owner():
            self.reference.revoke_c1(now,'ORDINARY_OR_UNKNOWN_COMPETING_BTC_OWNER');return
        held=self._position(self.config.btc_id)
        if held is None:return
        executable=tick.bid_price.as_decimal() if t.state=='CUT_RESOLVING' and t.side==1 or t.state!='CUT_RESOLVING' and t.side==-1 else tick.ask_price.as_decimal()
        plan=self.reference.c1_plan(now_ns=now,executable_price=executable,
            native_held_quantity=held.quantity.as_decimal(),native_btc_owners_clear=not self._orders(self.config.btc_id) and not own_c1)
        if plan is None:return
        if plan.kind=='CANCEL':
            self._queued_tp.clear()
            for order in self._orders(self.config.btc_id):
                if self._owned[str(order.client_order_id)]['purpose']=='TP_GTC':self.cancel_order(order)
            return
        self._queued_tp.clear()
        self._send(self.config.btc_id,plan.quantity,plan.side,'C1_'+plan.kind,now,tick,
            reduce_only=plan.kind=='CUT',reason='C1_RESIDUAL_'+plan.kind)

    def _reference_limit(self,iid,raw):
        instrument=self.cache.instrument(iid);value=instrument.make_price(raw).as_decimal()
        if not value.is_finite() or value<=0:raise ValueError('INVALID_REFERENCE_LIMIT')
        if iid.venue.value=='HYPERLIQUID':value=value.quantize(D(1).scaleb(value.adjusted()-4),rounding=ROUND_HALF_EVEN)
        result=instrument.make_price(value)
        if result.as_decimal()!=value:raise ValueError('NATIVE_REFERENCE_PRICE_PRECISION')
        return result

    def _send(self,iid,quantity,side,purpose,now,tick,*,reduce_only=False,
              level=None,raw_limit=None,reason='',decision_index=None):
        if quantity<=0 or side not in (-1,1):return False
        instrument=self.cache.instrument(iid)
        try:
            snapshot=self._snapshot(now)
            if snapshot.unknown_orders and (not reduce_only or not snapshot.unknown_order_assets or iid in snapshot.unknown_order_assets):
                raise ValueError('UNKNOWN_NATIVE_OWNER')
            if reduce_only:
                fresh,why=bbo_status(tick,now)
                if not fresh:raise ValueError(why)
            spec=self._contract_spec(iid,instrument)
            executable=tick.ask_price.as_decimal() if side==1 else tick.bid_price.as_decimal()
            is_limit=raw_limit is not None
            tif='GTC' if is_limit else 'IOC';intent='LIMIT' if is_limit else 'MARKET'
            terms=None
            limit=None
            if is_limit:
                raw=raw_limit
                if purpose=='ENTRY_DISCOUNT':
                    step=instrument.price_increment.as_decimal()
                    raw=(raw/step).to_integral_value(rounding=ROUND_FLOOR if side==1 else ROUND_CEILING)*step
                limit=self._reference_limit(iid,raw)
                wire=limit.as_decimal()
                if wire>=tick.ask_price.as_decimal() if side==1 else wire<=tick.bid_price.as_decimal():
                    raise ValueError('POSTONLY_CURRENT_WIRE_MARKETABLE')
                cap,classification=request_cap(spec,intent,tif)
                terms=RequestTerms(wire,max(executable,wire),min(executable,wire),cap,classification)
            else:
                terms=request_terms(spec,executable,'BUY' if side==1 else 'SELL',intent,tif)
            actual=snapshot.btc_qty if iid==self.config.btc_id else snapshot.sol_qty
            if reduce_only:
                if not actual or actual*side>=0:raise ValueError('REDUCE_ONLY_NATIVE_SIDE_UNKNOWN')
                other_ro=sum((o.leaves_qty.as_decimal() for o in self._orders(iid) if o.is_reduce_only),ZERO)
                quantity=min(quantity,max(ZERO,abs(actual)-other_ro))
            signed_target=actual+D(side)*quantity
            plan=order_plan(actual=actual,target=signed_target,pending=ZERO,unknown=False,
                price=terms.minimum_reference_price,step=instrument.size_increment.as_decimal(),
                min_qty=instrument.min_quantity.as_decimal() if instrument.min_quantity is not None else instrument.size_increment.as_decimal(),
                max_child=self.config.limits.max_child_notional,min_notional=spec.min_notional,
                emergency=purpose=='DRAIN',venue_max_child_notional=terms.cap,
                venue_reference_price=terms.cap_reference_price)
            if plan.action!='SUBMIT':
                self.target_blockers[str(iid)+':'+purpose+':'+str(level)]={'reason':plan.reason,'quantity':str(quantity),'clock_ns':str(now)}
                return False
            q=abs(plan.signed_quantity)
            if not reduce_only:
                admitted=q
                parent=self.reference.parent
                if iid==self.config.btc_id and purpose.startswith('ENTRY') and parent is not None:
                    admitted=max(q,parent.selected_quantity-parent.filled_quantity)
                if not self._admit(iid,admitted,executable,snapshot,now):
                    if purpose=='C1_RESTORE':self.reference.deny_c1_restore()
                    return False
            native_qty=instrument.make_qty(q)
            if native_qty.as_decimal()!=q:raise ValueError('NATIVE_QTY_FORMAT_MISMATCH')
            valid,why=validate_request(spec,q,terms,intent,tif)
            if not valid:raise ValueError(why)
            order=(self.order_factory.limit(instrument_id=iid,order_side=OrderSide.BUY if side==1 else OrderSide.SELL,
                    quantity=native_qty,price=limit,time_in_force=TimeInForce.GTC,post_only=True,reduce_only=reduce_only)
                if is_limit else self.order_factory.market(instrument_id=iid,order_side=OrderSide.BUY if side==1 else OrderSide.SELL,
                    quantity=native_qty,time_in_force=TimeInForce.IOC,reduce_only=reduce_only))
            actual_price=order.price.as_decimal() if getattr(order,'price',None) is not None else None
            valid,why=validate_request(spec,order.quantity.as_decimal(),terms,intent,tif)
            if (not valid or order.quantity.as_decimal()!=q or order.instrument_id!=iid
                    or order.side!=(OrderSide.BUY if side==1 else OrderSide.SELL)
                    or order.order_type.name!=intent or order.time_in_force.name!=tif
                    or actual_price!=terms.limit_price or order.is_reduce_only!=reduce_only
                    or bool(order.is_post_only)!=is_limit):
                raise ValueError('FINAL_NATIVE_REQUEST_MISMATCH:'+why)
            oid=str(order.client_order_id);parent=self.reference.parent
            context={'client_order_id':order.client_order_id,'instrument_id':iid,'purpose':purpose,
                'parent_id':parent.id if parent else None,'level':level,'submit_ns':now,'acked':False,
                'side':side,'quantity':q,'limit_price':limit.as_decimal() if limit is not None else None,
                'raw_limit_price':raw_limit,'decision_index':decision_index if decision_index is not None else (self.reference.signals[-1].index if self.reference.signals else -1),
                'accepted_retry':bool(purpose=='TP_IOC' and parent is not None and (level in parent.suppressed_zero_levels or parent.filled_quantity==parent.selected_quantity and not parent.stop_reason)),
                'reduce_only':reduce_only,'reason':reason}
            self._owned[oid]=context
            self._order_audit[oid]=_report_value({**context,'client_order_id':oid,'instrument_id':str(iid),
                'native_order_type':order.order_type.name,'native_time_in_force':order.time_in_force.name,
                'request_model_id':MODEL_ID,'request_classification':terms.classification,
                'admission':{'parent_id':context['parent_id'],'purpose':purpose,'intent':intent,
                    'source_policy_version':self.config.policy.version,'native_quote_ns':tick.ts_event,
                    'request_cap':str(terms.cap),'reduce_floor_policy':REDUCE_FLOOR_POLICY,
                    'episode_entry_signal_index':parent.decision_index if parent else None,'reference_signal_index':context['decision_index'],'tp_level':level}})
            if purpose.startswith('C1_'):self.reference.commit_c1_submission(purpose[3:],now_ns=now)
            self._chain_audit('ORDER_ADMISSION',self._order_audit[oid]);self._persist_checkpoint()
            self.submit_order(order)
            return True
        except (ValueError,AttributeError,TypeError,KeyError) as error:
            self.pre_submit_gate_blocks.append({'timestamp':str(now),'instrument':str(iid),'reason':str(error),'purpose':purpose})
            return False

    def on_order_accepted(self,event):
        info=self._owned.get(str(event.client_order_id))
        if info is not None:info['acked']=True;self._persist_checkpoint()

    def on_order_filled(self,event):
        tid=str(event.trade_id)
        if tid in self._seen_trade_ids:return
        oid=str(event.client_order_id);context=self._order_audit.get(oid)
        self._seen_trade_ids.add(tid)
        fee=event.commission.as_decimal()
        self.fill_audit.append({'client_order_id':oid,'trade_id':tid,'instrument':str(event.instrument_id),
            'venue':str(event.instrument_id.venue),'qty':str(event.last_qty.as_decimal()),'px':str(event.last_px.as_decimal()),
            'notional':str(event.last_qty.as_decimal()*event.last_px.as_decimal()),
            'commission':str(fee),'commission_currency':str(event.commission.currency),'fill_ns':str(event.ts_event),
            'native_liquidity_side':getattr(event.liquidity_side,'name',str(event.liquidity_side)),
            'order_side':getattr(event.order_side,'name',str(event.order_side)),
            'action':context['purpose'] if context else 'UNKNOWN','reason':context.get('reason') if context else 'UNKNOWN',
            'level':context.get('level') if context else None,'parent_id':context.get('parent_id') if context else None,
            'admission':context.get('admission') if context else None,'policy_hash':self.config.execution_policy_hash})
        p=self.reference.parent
        if event.instrument_id==self.config.btc_id:
            purpose=context['purpose'] if context else ''
            if purpose!='DRAIN' and (p is None or context is None or context['parent_id']!=p.id):
                self._restore_failed=True;self.safety.global_latched=True;self.safety.reason='UNOWNED_OR_LATE_FOREIGN_BTC_FILL'
                self._begin_drain(self.clock.timestamp_ns(),'GLOBAL',[str(self.config.btc_id),str(self.config.sol_id)],self.safety.reason)
            elif purpose!='DRAIN':
                kind='ENTRY' if purpose.startswith('ENTRY') else 'TP' if purpose.startswith('TP_') else purpose[3:]
                try:
                    self.reference.apply_fill(p.id,trade_id=tid,kind=kind,quantity=event.last_qty.as_decimal(),
                        price=event.last_px.as_decimal(),event_ns=event.ts_event,level=context.get('level'))
                except ValueError as error:
                    self._restore_failed=True;self.safety.global_latched=True;self.safety.reason=str(error)
                    self._begin_drain(self.clock.timestamp_ns(),'GLOBAL',[str(self.config.btc_id),str(self.config.sol_id)],self.safety.reason)
                if kind=='ENTRY':
                    self._tp_ready_ns=max(self._tp_ready_ns,event.ts_event+1)
                    self._needs_daily=bool(self.reference.parent.omitted_levels)
                    for audit in reversed(self.entry_sizing_audit):
                        if audit['episode_id']==p.id:audit['confirmed_native_entry_qty']=str(self.reference.parent.filled_quantity);break
                else:self._needs_daily=True
        if self._liquidating and self.liquidation_audit:
            row=self.liquidation_audit[-1]
            row['close_fills'].append({'trade_id':tid,'quantity':str(event.last_qty),'price':str(event.last_px)})
            row['close_value']=str(D(row['close_value'])+event.last_qty.as_decimal()*event.last_px.as_decimal())
        self._chain_audit('NATIVE_FILL',self.fill_audit[-1]);self._terminal_event(event,only_if_closed=True)
        self._persist_checkpoint()

    def _terminal_event(self,event,only_if_closed=False,failed=False):
        oid=str(event.client_order_id);info=self._owned.get(oid)
        if info is None:return
        order=self.cache.order(event.client_order_id)
        if only_if_closed and (order is None or not order.is_closed):return
        del self._owned[oid];now=self.clock.timestamp_ns()
        purpose=info['purpose'];p=self.reference.parent
        if purpose.startswith('C1_') and p is not None and p.id==info['parent_id']:
            self.reference.c1_terminal(purpose[3:],now_ns=event.ts_event)
            self._queue_confirmed_targets(event.ts_event+1)
        elif purpose.startswith('ENTRY') and p is not None and p.id==info['parent_id']:
            if failed:
                self.reference.stop_entry_remainder(p.id,reason='NATIVE_DENIED_REJECTED_EXPIRED')
                p=self.reference.parent
            # A child terminal never equals economic parent cancellation. The
            # same parent may continue on its next real quote after a partial.
            if p.stop_reason and p.filled_quantity==0:
                self.reference.confirm_empty_entry_terminal(p.id,native_pending=False)
            elif p.split_terminal:
                self._queue_confirmed_targets(0 if failed else event.ts_event+1)
        elif purpose.startswith('TP_') and p is not None and p.id==info['parent_id']:
            level=info['level']
            if not only_if_closed and not failed and p.tp_filled_lots.get(level,0)>0:
                self._queue_confirmed_targets(event.ts_event+1)
            # Resting replans and the accepted IOC remainder are independent,
            # as in the reference terminal callback. A suppressed zero level
            # cannot be recovered by confirmed_targets alone.
            if (purpose=='TP_IOC' and info['accepted_retry'] and level not in self._queued_tp
                    and not any(v['instrument_id']==self.config.btc_id and v.get('level')==level for v in self._owned.values())):
                retry=self.reference.retry_native_tp_permission(p.id,level=level,
                    decision_index=info['decision_index'],ready_ns=event.ts_event+60_000_000_000)
                if retry is not None:self._queued_tp[level]=retry
            self._needs_daily=True
        self._reconcile_drains(now)
        scope=self._scope_for(info['instrument_id'])
        filled=getattr(order,'filled_qty',None) if order is not None else None
        progressed=filled is not None and filled.as_decimal()>0
        if scope is not None and (purpose!='DRAIN' or progressed):
            tick=self._quotes.get(info['instrument_id'])
            if tick is not None:
                self.drain_audit.append({'timestamp_ns':now,'scope':scope,'event':'NATIVE_CALLBACK_PROGRESS',
                    'retired_order_id':oid,'purpose':purpose})
                self._execute_drain(tick,now,scope)
        self._persist_checkpoint()

    def on_order_canceled(self,event):self._terminal_event(event)
    def on_order_denied(self,event):self._terminal_event(event,failed=True)
    def on_order_rejected(self,event):self._terminal_event(event,failed=True)
    def on_order_expired(self,event):self._terminal_event(event,failed=True)

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
                if other==self.config.btc_id:
                    parent=self.reference.parent
                    logical=parent.selected_quantity if parent is not None and parent.selected_quantity is not None and not parent.split_terminal else ZERO
                    cycle=self.reference.c1
                    if cycle is not None and not cycle.revoked:logical=max(logical,abs(held)+D(cycle.credit)*self.config.btc_step)
                    logical_fees+=max(ZERO,logical-projected)*mark*fee_rate
                    projected=max(projected,logical)
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

    def _request_contract_identity(self):
        profile=getattr(self.config.margin_policy,'_profile',None)
        evidence=getattr(profile,'evidence',None)
        return {'model_id':MODEL_ID,'policy_version':self.config.policy.version,
            'implementation_sources':dict(self._admission_sources),
            'bbo_and_mark_max_age_ns':FRESH_NS,'drain_interval_ns':DRAIN_NS,
            'operational_intervals_authority':'OWN_RESEARCH_CHOICES_NOT_HL_PARAMETERS',
            'limit_GTC_rounding':'REFERENCE_NATIVE_MAKE_PRICE_THEN_5SIG_HALF_EVEN',
            'conditional_TP_predicate':'UNNORMALIZED_OWNED_DECIMAL_PLANREF_WAVE_THRESHOLD',
            'ambiguous_IOC_cap':'MIN_OFFICIAL_MARKET_LIMIT_OWN_CONSERVATIVE_MODEL_RULE_BACKEND_UNKNOWN',
            'reduce_only_floor':REDUCE_FLOOR_POLICY,'opening_minimum_authority':'OFFICIAL_MINIMUM',
            'capacity_model':'ZERO_IMPACT_ORDER_LEAVES_DIAGNOSTIC_NO_DISCRETIONARY_TURNOVER_CAP',
            'market_factory':'NATIVE_MARKET_IOC_BACKEND_CLASSIFICATION_UNKNOWN',
            'profile_evidence':asdict(evidence) if evidence is not None else None,
            'instruments':{key:{'quantity_increment':str(spec.quantity_increment),'min_quantity':str(spec.min_quantity),
                'min_notional':str(spec.min_notional),'max_market_notional':str(spec.max_market_notional),
                'max_limit_notional':str(spec.max_limit_notional),'max_price_decimals':spec.max_price_decimals,
                'max_price_significant_figures':spec.max_price_significant_figures}
                for key,spec in sorted(getattr(profile,'instruments',{}).items())}}

    def _checkpoint_identity(self):
        return {'schema':SCHEMA,'sources':self._admission_sources,'policy':asdict(self.config.policy),
            'execution_policy_hash':self.config.execution_policy_hash,'strategy_id':str(self.id),
            'request_model_id':MODEL_ID,'request_contract':self._request_contract_identity(),
            'seed_days_sha256':sha256(canonical([[_ns(d.open_time),_ns(d.close_time),_ns(d.available_at),
                d.btc_open,d.btc_close,d.sol_close] for d in self.config.seed_days])).hexdigest(),
            'seed_ohlc_sha256':sha256(canonical(self.config.seed_ohlc)).hexdigest(),
            'active_seed':self.config.active_seed,'exit_fee_rate':self.config.exit_fee_rate,
            'execution_limits':asdict(self.config.limits),
            'instruments':[str(self.config.btc_id),str(self.config.sol_id)],
            'start_ns':self.config.trading_start_open_ns,'end_ns':self.config.terminal_close_at_ns}

    def _feed_checkpoint_binding(self):
        return {'clock_ns':self.clock.timestamp_ns(),
            'quotes':{str(i):[q.ts_event,q.ts_init,str(q.bid_price),str(q.ask_price),str(q.bid_size),str(q.ask_size)] for i,q in self._quotes.items()},
            'marks':{str(i):[m.ts_event,str(m.price)] for i,m in self._latest_marks.items()}}

    def _checkpoint_document(self):
        if not callable(self.config.continuity_reader):raise ValueError('CM2_NATIVE_OBSERVER_CONTINUITY_REQUIRED')
        return {'identity':self._checkpoint_identity(),'native':self._native_checkpoint_binding(),
            'observer':self.config.continuity_reader(),'feed_continuity':self._feed_checkpoint_binding(),
            'audit_continuity':[len(self.fill_audit),len(self.cm2_audit),len(self._order_audit),self._retained_audit_chain],
            'domain':{'reference':self.reference.snapshot_state(),'safety':asdict(self.safety),
                'owned':{oid:{**v,'instrument_id':str(v['instrument_id']),'client_order_id':str(v['client_order_id'])} for oid,v in self._owned.items()},
                'seen_trade_ids':sorted(self._seen_trade_ids),'queued_tp':{str(k):asdict(v) for k,v in self._queued_tp.items()},
                'needs_daily':self._needs_daily,'tp_ready_ns':self._tp_ready_ns,
                'drain':self._drain,'btc_source_frame':self._btc_source_frame,'restore_failed':self._restore_failed,
                'risk_unknown':self._risk_unknown,'liquidating':self._liquidating,
                'days_pending':{str(ns):{str(i):[str(x.open),str(x.high),str(x.low),str(x.close),x.ts_event,x.ts_init]
                    for i,x in rows.items()} for ns,rows in self._days_pending.items()}}}

    def on_save(self):
        body=canonical(self._checkpoint_document());store=self.config.checkpoint_store
        if store is not None:
            revision=store.persist(body,self._checkpoint_revision)
            if revision is None:self._restore_failed=True;raise ValueError('CM2_CHECKPOINT_REVISION_CONFLICT')
            self._checkpoint_revision=revision
        return {KEY:body}

    def _persist_checkpoint(self):
        if self.config.checkpoint_store is not None:self.on_save()

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
        for oid,v in domain['owned'].items():
            owned[oid]={**v,'instrument_id':InstrumentId.from_str(v['instrument_id']),
                'client_order_id':ClientOrderId(v['client_order_id'])}
        drains=domain['drain']
        if not set(drains).issubset({'GLOBAL','BTC_ECONOMIC','SOL_SUBORDINATE'}):raise ValueError('CM2_DRAIN_SCOPE_UNKNOWN')
        for drain in drains.values():validate_drain(drain['state'],(str(self.config.btc_id),str(self.config.sol_id)))
        safety=SafetyState(**domain['safety'])
        if safety.emergency_latched and not safety.global_latched:raise ValueError('CM2_EMERGENCY_LATCH_INCONSISTENT')
        self.reference.restore_state(domain['reference']);self.safety=safety;self._owned=owned
        from coinmaster.strategy.cm2_reference_policy import TargetPlan
        self._queued_tp={int(k):TargetPlan(**v) for k,v in domain['queued_tp'].items()}
        self._seen_trade_ids=set(domain['seen_trade_ids']);self._needs_daily=domain['needs_daily'];self._tp_ready_ns=domain['tp_ready_ns']
        self._drain=drains;self._btc_source_frame=domain['btc_source_frame'];self._restore_failed=domain['restore_failed']
        self._risk_unknown=domain['risk_unknown'];self._liquidating=domain['liquidating'];self._days_pending={}
        for ns,rows in domain['days_pending'].items():
            self._days_pending[int(ns)]={InstrumentId.from_str(i):DailySignalBar(InstrumentId.from_str(i),*values[:4],values[4],values[5]) for i,values in rows.items()}
        self._checkpoint_revision=latest[0];self._checkpoint_loaded=True
        self._loaded_native_binding=canonical(document['native'])
        self._loaded_feed_binding=canonical(document['feed_continuity']);self._loaded_observer_binding=canonical(document['observer'])

    def on_stop(self):self._persist_checkpoint()

    def _audit(self,now,reason):
        parent=self.reference.parent
        row={'ts_ns':str(now),'reason':reason,'parent_id':parent.id if parent else None,
             'policy_version':self.config.policy.version,'global_latch':self.safety.global_latched}
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
            'cm2':{'policy':asdict(self.config.policy),'request_execution_model_id':MODEL_ID,
                'request_contract':request,'request_contract_sha256':sha256(canonical(request)).hexdigest(),
                'execution_comparability':'BTC_FIRST_REFERENCE_COMPONENT_WITH_EXPLICIT_NATIVE_GUARD_DEVIATIONS',
                'reduce_only_minimum_policy':REDUCE_FLOOR_POLICY,'market_wire_price_and_IOC_backend_classification':'UNKNOWN',
                'btc_reference':self.reference.snapshot_state(),'c1_audit':self.reference.c1_audit,
                'capital_last':self._capital_last,'capital_unknown':self._capital_unknown,
                'drain_state':self._drain,'drain_lifecycle':self.drain_audit,'audit':self.cm2_audit,
                'child_permission_audit':self.child_permission_audit,'order_admission_audit':list(self._order_audit.values()),
                'target_blockers':self.target_blockers,'orphan_intervals':self.orphan_intervals,
                'open_orphan_since_ns':self.orphan_started_ns,'checkpoint_revision':self._checkpoint_revision,
                'ordinary_harvest_actual_geometry':{'status':'NOT_APPLICABLE_BTC_REFERENCE_POLICY'},
                'sol_staging_harvest_context':{'status':'NOT_APPLICABLE_SOL_COMPONENT_INACTIVE'},
                'capacity_model':{'model':'ZERO_IMPACT_ORDER_LEAVES_DIAGNOSTIC','participation':None,
                    'official_venue_caps':'ENFORCED','discretionary_turnover_cap':'DISABLED_MATCHED_REFERENCE_PROFILE'},
                'restart_recovery':'SAME_CLOCK_NATIVE_CACHE_JOURNAL_BINDING_ONLY_OS_COLD_RECOVERY_UNKNOWN',
                'structural_diagnostics':'NATIVE_QUALIFICATION_PENDING',
                'liquidation_measurement':{'contract':'NATIVE_MARK_FIRST_PUBLIC_TIER_MAINTENANCE',
                    'checks':self._liquidation_checks,'unknown_checks':self._liquidation_unknown}}})


def _ns(when):return int(when.timestamp()*1_000_000_000)


def _report_value(value):
    if isinstance(value,D):return str(value)
    if isinstance(value,dict):return {str(k):_report_value(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_report_value(v) for v in value]
    if value is None or type(value) in (str,int,float,bool):return value
    raise TypeError('CM2_REPORT_UNSUPPORTED_VALUE:'+type(value).__name__)
