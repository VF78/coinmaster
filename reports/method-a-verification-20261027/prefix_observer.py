"""Read-only public native input/callback observer, identical in P0/P1.

SimulationModule.pre_process(QuoteTick) is before native matching of this input.
Strategy callbacks are explicitly AFTER cache mutation/matching, never pre-match.
No order action, fill, position/cache mutation, account bridge or PnL model here.
"""
from pathlib import Path
from collections import Counter
import gzip,hashlib,json
from nautilus_trader.backtest.modules import SimulationModule
from nautilus_trader.backtest.config import SimulationModuleConfig
from nautilus_trader.model.data import QuoteTick


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


class PrefixEvidence:
    def __init__(self,path):
        self.path=Path(path);self.file=gzip.open(self.path,'wt');self.strategy=None
        self.sequence=0;self.counts=Counter();self.last_state=None;self.registration=[]
        self.first_quote_ns=None;self.last_quote_ns=None;self.native_event_uuid_frames=0
        self.admission_attempts=0;self.admission_recorded=0;self.admission_errors=0;self.admission_error_samples=[]
    def bind(self,strategy):self.strategy=strategy
    def order(self,order,history=False):
        row=dict(order_id=str(order.client_order_id),instrument=str(order.instrument_id),
            strategy=str(order.strategy_id),status=order.status.name,side=order.side.name,
            quantity=str(order.quantity),filled=str(order.filled_qty),leaves=str(order.leaves_qty),
            price=None if getattr(order,'price',None) is None else str(order.price),reduce_only=order.is_reduce_only,
            native_position_id=None if order.position_id is None else str(order.position_id))
        if history:row['native_history']=[dict(id=str(e.id),type=type(e).__name__,event_ns=str(e.ts_event)) for e in order.events]
        return row

    @staticmethod
    def legacy_episode(ep,m=None):
        if ep is None:return None
        floats=dict(h=ep.h,btc_initial_qty=ep.btc_initial_qty,btc_net_planned_qty=ep.btc_net_planned_qty,
            btc_reference_qty=ep.btc_reference_qty,btc_entry_vwap=ep.btc_entry_vwap,beta_entry=ep.beta_entry,fixed_sigma=ep.fixed_sigma)
        maps=dict(sol_add_filled_notional=dict(ep.sol_add_filled_notional),sol_ownership_transfer_credit=dict(ep.sol_ownership_transfer_credit),
            sol_risk_retired_notional=dict(ep.sol_risk_retired_notional),sol_right_fraction=dict(ep.sol_right_fraction))
        return dict(h=ep.h,sol_add_filled_notional=maps['sol_add_filled_notional'],
            sol_ownership_transfer_credit=maps['sol_ownership_transfer_credit'],sol_risk_retired_notional=maps['sol_risk_retired_notional'],
            btc_deferred_right_touched=ep.btc_deferred_right_touched,
            btc_deferred_right_reference_price=None if ep.btc_deferred_right_reference_price is None else str(ep.btc_deferred_right_reference_price),
            sol_right_decision_index=dict(ep.sol_right_decision_index),
            source_float_values=floats,source_float_hex={k:None if v is None else float(v).hex() for k,v in floats.items()},
            source_float_maps=maps,source_float_maps_hex={name:{k:float(v).hex() for k,v in values.items()} for name,values in maps.items()},
            raw_entry=dict(btc_entry_qty_exact=str(ep.btc_entry_qty_exact),btc_planref_vwap=None if ep.btc_planref_vwap is None else str(ep.btc_planref_vwap),
                btc_reference_target_lots=dict(ep.btc_reference_target_lots),btc_tp_target_lots=dict(ep.btc_tp_target_lots),
                btc_tp_filled_lots=dict(ep.btc_tp_filled_lots),btc_tp_filled_qty=dict(ep.btc_tp_filled_qty),
                method_a_raw_target_lots=None if m is None else dict(m['raw_target_lots'])),
            sol_lifecycle=dict(sol_qty=ep.sol_qty,first_fill_at=None if ep.sol_first_fill_at is None else ep.sol_first_fill_at.isoformat(),
                first_owned_at=None if ep.sol_first_owned_at is None else ep.sol_first_owned_at.isoformat(),
                half_done=ep.sol_half_done,half_decision_index=ep.sol_half_decision_index,attempted_sol_at=dict(ep.attempted_sol_at)))

    def legacy_sessions(self):
        s=self.strategy;bars=s._bars;bar=bars[-1] if bars else None
        def native(value):
            return None if value is None else dict(instrument=str(value.bar_type.instrument_id),ts_event=str(value.ts_event),ts_init=str(value.ts_init))
        features=s._current_signals[-1] if s._current_signals else None
        return dict(last_accepted_session=None if s._last_accepted_session is None else str(s._last_accepted_session),
            latest_seen_session=None if s._latest_seen_session is None else str(s._latest_seen_session),
            current_BTC_SOL_signal_sessions=dict(BTC=native(s._current_btc),SOL=native(s._current_sol),
                bar_index=len(bars)-1,bar_close_time=None if bar is None else bar.close_time.isoformat(),
                bar_available_at=None if bar is None else bar.available_at.isoformat(),
                source_bar_session_ns=None if bar is None else str(int(bar.close_time.timestamp()*1_000_000_000))),
            current_features=None if features is None else {k:getattr(features,k) for k in ('index','side','beta','relative','mu','sigma','z')})

    def submission(self,order,intent_id,episode_id,action,reason,level):
        self.admission_attempts+=1
        s=self.strategy;ep=s._domain.episode;oid=str(order.client_order_id);intent=s._pending_by_order.get(oid)
        instrument=s.cache.instrument(order.instrument_id);quote=s.cache.quote_tick(order.instrument_id)
        m=None if ep is None else s._ma_plans.get(ep.id);candidate=s._candidate
        admission=dict(schema='METHOD_A_LEGACY_SOL_PRE_TRANSPORT_V2',checkpoint_result=True,
            boundary='ORIGINAL_RECORD_SUBMISSION_RETURNED_TRUE_BEFORE_NATIVE_TRANSPORT',
            initialized_order_is_ACK_or_fill=False,order_timestamp_semantics='NATIVE_ORDER_TS_INIT_NOT_ADMISSION_WALL_CLOCK',
            client_order_id=oid,intent_id=intent_id,parent=episode_id,action=action,reason=reason,level=level,
            pending_intent=None if intent is None else dict(id=intent.id,parent=intent.episode_id,action=intent.action,level=intent.level,
                side=intent.side,quantity=intent.quantity,requested_notional=intent.requested_notional,decision_index=intent.decision_index,reason=intent.reason),
            domain_pending_contains_intent=False if ep is None else intent_id in ep.pending,
            order_decision_index=s._decision_index_by_order.get(oid),current_parent=None if ep is None else ep.id,
            episode=None if ep is None else dict(h_at_SOL_ADD_admission=ep.h,sol_add_filled_notional_at_SOL_ADD_admission=dict(ep.sol_add_filled_notional),id=ep.id,side=ep.side,old_SOL_rights=sorted(ep.sol_rights),
                old_SOL_fractions=dict(ep.sol_right_fraction),**self.legacy_episode(ep,m)),
            sessions=self.legacy_sessions(),native_initialized_order=self.order(order,True),
            current_native_cache_order_present=s.cache.order(order.client_order_id) is not None,
            native_quote=None if quote is None else dict(instrument=str(quote.instrument_id),event_ns=str(quote.ts_event),init_ns=str(quote.ts_init),
                bid=str(quote.bid_price),ask=str(quote.ask_price)),
            instrument=None if instrument is None else dict(id=str(instrument.id),size_increment=str(instrument.size_increment),
                min_quantity=None if instrument.min_quantity is None else str(instrument.min_quantity),
                min_notional=None if instrument.min_notional is None else str(instrument.min_notional)),
            original_policy={k:getattr(candidate,k) for k in ('sol_size_multipliers_h','sol_entry_z','sol_late_entry_after_tp',
                'sol_overlay_enabled','episode_fixed_beta','max_parent_notional','sol_max_holding_days','sol_exit_half_z','sol_exit_all_z')})
        self.record('SOL_ADD_PRE_NATIVE_TRANSPORT_AFTER_CHECKPOINT',order.ts_init,admission=admission)
        self.admission_recorded+=1

    def admission_error(self,error):
        self.admission_errors+=1
        if len(self.admission_error_samples)<8:self.admission_error_samples.append(type(error).__name__[:80])

    def state(self):
        s=self.strategy
        if s is None:return None
        ep=s._domain.episode;cache=s.cache
        orders={str(o.client_order_id):self.order(o) for o in cache.orders_open()+cache.orders_inflight()}
        account=cache.account_for_venue(s.config.btc_id.venue)
        m=None if ep is None else s._ma_plans.get(ep.id)
        owners={oid:dict(owner) for oid,owner in s._ma_owners.items() if oid in orders}
        return dict(legacy_sessions=self.legacy_sessions(),native_cash=None if account is None else str(account.balance_total()),
            positions=[dict(id=str(p.id),instrument=str(p.instrument_id),side='LONG' if p.is_long else 'SHORT',quantity=str(p.quantity)) for p in cache.positions_open()],
            active_orders=orders,owned_pending={oid:dict(intent_id=i.id,parent=i.episode_id,action=i.action,level=i.level,reason=i.reason) for oid,i in s._pending_by_order.items()},
            queued=[dict(intent_id=i.id,parent=i.episode_id,action=i.action,level=i.level,side=i.side,quantity=i.quantity,
                requested_notional=i.requested_notional,decision_index=i.decision_index,reason=i.reason) for i,_,_ in s._queued_intents],
            episode=None if ep is None else dict(id=ep.id,side=ep.side,entry_qty_exact=str(ep.btc_entry_qty_exact),
                target_lots=dict(ep.btc_tp_target_lots),actual_tp_filled_lots=dict(ep.btc_tp_filled_lots),risk_retired_lots=dict(ep.btc_risk_retired_lots),
                omitted_raw_levels=sorted(ep.btc_omitted_zero_levels),old_SOL_rights=sorted(ep.sol_rights),old_SOL_fractions=dict(ep.sol_right_fraction),**self.legacy_episode(ep,m)),
            method_a=None if m is None else dict(coverage_ready=m.get('coverage_ready'),raw_levels=m.get('raw_levels'),
                raw_target_lots=m.get('raw_target_lots'),expected_cancels=sorted(m['expected_cancels'])),
            method_a_active_owners=owners,method_a_commands={oid:{k:str(v) for k,v in c.items()} for oid,c in s._ma_commands.items()})
    def record(self,phase,ns,**data):
        state=self.state();state_hash=digest(state)
        self.sequence+=1;self.counts[phase]+=1
        row=dict(sequence=self.sequence,phase=phase,event_ns=str(ns),state_sha256=state_hash,**data)
        if state_hash!=self.last_state:
            row['state']=state;self.last_state=state_hash
        else:row['state_ref_sha256']=state_hash
        self.file.write(json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)+chr(10))
    def input(self,data):
        if not isinstance(data,QuoteTick):return
        if self.first_quote_ns is None:self.first_quote_ns=data.ts_event
        self.last_quote_ns=data.ts_event
        value=dict(instrument=str(data.instrument_id),event_ns=str(data.ts_event),init_ns=str(data.ts_init),
            bid=str(data.bid_price),ask=str(data.ask_price),bid_size=str(data.bid_size),ask_size=str(data.ask_size))
        self.record('BEFORE_NATIVE_MATCHING_INPUT',data.ts_event,input=value,input_sha256=digest(value),quote_native_UUID=None)
    def callback(self,phase,event):
        native_id=getattr(event,'id',None)
        if native_id is not None:self.native_event_uuid_frames+=1
        oid=getattr(event,'client_order_id',None);order=None if oid is None or self.strategy is None else self.strategy.cache.order(oid)
        values=dict(native_event_id=None if native_id is None else str(native_id),native_event_type=type(event).__name__,
            client_order_id=None if oid is None else str(oid),native_order=None if order is None else self.order(order,True))
        position_id=getattr(event,'position_id',None)
        if type(event).__name__=='PositionClosed' and position_id is not None and self.strategy is not None:
            realized=getattr(event,'realized_pnl',None)
            values['native_position_closed_event']=dict(position_id=str(position_id),realized_pnl=None if realized is None else dict(amount=str(realized.as_decimal()),currency=str(realized.currency)),source='IMMUTABLE_NATIVE_POSITION_CLOSED_EVENT',realized_fee_convention='INCLUDES_SETTLEMENT_CURRENCY_COMMISSIONS_DO_NOT_SUBTRACT_AGAIN')
            position=self.strategy.cache.position(position_id)
            if position is not None:
                def money(value):
                    return None if value is None else dict(amount=str(value.as_decimal()),currency=str(value.currency))
                values['native_position']=dict(position_id=str(position.id),instrument=str(position.instrument_id),
                    is_closed=bool(position.is_closed),quantity=str(position.quantity),
                    realized_pnl=money(position.realized_pnl),commissions=[money(value) for value in position.commissions()],
                    settlement_currency=str(position.settlement_currency),ts_opened=str(position.ts_opened),ts_closed=str(position.ts_closed),
                    native_fill_history=[dict(event_id=str(fill.id),trade_id=str(fill.trade_id),client_order_id=str(fill.client_order_id),
                        qty=str(fill.last_qty),px=str(fill.last_px),commission=money(fill.commission)) for fill in position.events],
                    realized_fee_convention='NATIVE_POSITION_REALIZED_PNL_ALREADY_INCLUDES_SETTLEMENT_CURRENCY_COMMISSIONS_DO_NOT_SUBTRACT_AGAIN')
        for key in ('trade_id','last_qty','last_px','commission'):
            if hasattr(event,key):values[key]=str(getattr(event,key))
        self.record(phase,event.ts_event,**values)
    def close(self):
        self.file.close()
        checksum=hashlib.sha256()
        with self.path.open('rb') as stream:
            while chunk:=stream.read(1024*1024):checksum.update(chunk)
        return dict(path=str(self.path.resolve()),sha256=checksum.hexdigest(),
            legacy_SOL_admission_capture=dict(schema='METHOD_A_LEGACY_SOL_PRE_TRANSPORT_V2',attempts=self.admission_attempts,recorded=self.admission_recorded,error_count=self.admission_errors,error_samples=self.admission_error_samples,requires_financial_UNKNOWN_if_errors=True),
            frames=self.sequence,phase_counts=dict(self.counts),native_event_UUID_frames=self.native_event_uuid_frames,native_event_UUID_count_semantics='FRAME_OCCURRENCES_INCLUDING_TYPED_GENERIC_DUPLICATES;EXACT_UUID_DEDUP_IS_POST_RUN_STREAM_ANALYSIS',
            first_quote_ns=self.first_quote_ns,last_quote_ns=self.last_quote_ns,
            input_boundary='PUBLIC_SIMULATION_MODULE_PRE_PROCESS_BEFORE_NATIVE_MATCHING',
            strategy_callback_boundary='NATIVE_CACHE_ALREADY_MUTATED_NOT_PRE_MATCH',
            coverage_qualification='ROOT_ACTUAL_STREAM_REVIEW_REQUIRED_NO_AUTOMATIC_PASS',
            state_coalescing='EVERY_FRAME_RECORDED_SHA256_REFERENCES_PRIOR_IDENTICAL_FULL_STATE',actual_venue_registrations=self.registration)


class PrefixCoverageModule(SimulationModule):
    def __init__(self,evidence):super().__init__(SimulationModuleConfig());self.evidence=evidence
    def pre_process(self,data):self.evidence.input(data)
    def process(self,ts_now):pass
    def log_diagnostics(self,logger):pass
    def reset(self):pass


def observed_strategy_type(base,evidence):
    def wrap(name):
        def callback(self,event):
            evidence.callback('BEFORE_STRATEGY_'+name+'_NATIVE_CACHE_ALREADY_MUTATED',event)
            try:return getattr(super(cls,self),name)(event)
            finally:evidence.callback('AFTER_STRATEGY_'+name,event)
        return callback
    names=('on_quote_tick','on_order_filled','on_order_accepted','on_order_updated','on_order_canceled','on_order_modify_rejected','on_order_event','on_position_event')
    def record_submission(self,order,intent_id,episode_id,action,reason=None,level=None):
        result=super(cls,self)._record_submission(order,intent_id,episode_id,action,reason,level)
        if result and action=='SOL_ADD':
            try:evidence.submission(order,intent_id,episode_id,action,reason,level)
            except Exception as error:evidence.admission_error(error)
        return result
    methods={name:wrap(name) for name in names};methods['_record_submission']=record_submission
    cls=type('MethodAPrefixObservedStrategy',(base,),methods)
    return cls


def recording_engine_factory(original,evidence):
    class NativeEngineProxy:
        def __init__(self,*args,**kwargs):self.native=original(*args,**kwargs)
        def __getattr__(self,name):return getattr(self.native,name)
        def add_venue(self,*args,**kwargs):
            assert kwargs['liquidity_consumption'] is False and kwargs['bar_execution'] is True
            original_modules=list(kwargs['modules'])
            kwargs=dict(kwargs,modules=original_modules+[PrefixCoverageModule(evidence)])
            result=self.native.add_venue(*args,**kwargs)
            evidence.registration.append(dict(venue=str(kwargs['venue']),liquidity_consumption=kwargs['liquidity_consumption'],bar_execution=kwargs['bar_execution'],
                modules_before_observer=[type(m).__name__ for m in original_modules],observer_added='PrefixCoverageModule',
                authority='ACTUAL_STOCK_ADD_VENUE_RETURNED_WITH_SAME_KWARGS_PLUS_READ_ONLY_MODULE'))
            return result
        def add_strategy(self,strategy):
            evidence.bind(strategy)
            return self.native.add_strategy(strategy)
    return NativeEngineProxy
