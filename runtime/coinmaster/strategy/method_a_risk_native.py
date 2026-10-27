"""Default-OFF Method A native adapter (research only).

Existing native paired protection/retirement and sole SOL_CLOSE dispatcher are
reused. This adapter never credits a submitted order, mutates cash, or computes
realized PnL. Unsupported/unknown state fails closed before any increase.
"""
NATIVE_READINESS='INTEGRATION_CHECKPOINT_NOT_NATIVE_READY'

from decimal import Decimal as D
from dataclasses import dataclass,asdict
from fractions import Fraction as F
from coinmaster.strategy.method_a_recovery import recovery_candidates,floor as ifloor,ceil as iceil
from nautilus_trader.model.identifiers import ClientOrderId
from nautilus_trader.model.enums import OrderSide
from coinmaster.strategy.method_a_risk import (Observation, Funding, State, Liability,
    lagged_features,evaluate,tier_partition_envelope,hedge_target,useful_hedge,exact_algebra,MINUTE,DAY,TAKER,RESERVE)
from coinmaster.strategy.paired_prefix import exact_lots,sol_prices
from coinmaster.strategy.native_account_snapshot import native_account_snapshot
from coinmaster.research.method_a_risk_rows import SCHEMA,wire


@dataclass(frozen=True)
class EntrySubmissionDecision:
    status: str
    reason: str
    parent: str | None
    instrument: str
    side: int
    quantity: str
    snapshot_ref: str | None
    native_order_id: str | None = None


@dataclass
class JointCaps:
    qref: D
    bmax: D
    solmax: D
    initialized: bool = True

    def entry_terminal(self, actual_sol):
        # Terminal absence/partial entry creates no BTC debt by itself.
        exact_lots(actual_sol,self.sol_lot)

    def reconcile(self, actual_btc, actual_sol, **_):
        # Targets are set only by the fresh joint snapshot, never by a ratio.
        exact_lots(actual_btc,self.btc_lot);exact_lots(actual_sol,self.sol_lot)
        return max(D(0),actual_btc-self.bmax),max(D(0),actual_sol-self.solmax)


def mr_floor_lot(value,lot):
    ratio=F(value)/F(lot)
    if ratio<0 or lot<=0:raise ValueError('UNKNOWN_TARGET_LOT')
    return D(ifloor(ratio))*lot


class MethodARiskResearch:
    def _mr_enabled(self):
        return self.config.research_method_a_risk is not None

    def __init__(self, config):
        super().__init__(config)
        if not self._mr_enabled():return
        if config.research_method_a_risk not in ('HEDGE','TRIM') or not config.research_method_a_tp or not config.research_sol_off or config.research_paired_prefix or config.research_sol_standing_protection or config.research_a0_family or config.research_conditional_sol:
            raise ValueError('METHOD_A_RISK_REQUIRES_EXACT_P1_BTC_SOL_OFF')
        self.method_a_risk_audit=[];self._mr_peak=config.active_seed
        self._mr_parent=None;self._mr_on=False;self._mr_allocated=False
        self._mr_off_since=None;self._mr_last_episode_day=None;self._mr_failed=False
        self._mr_busy=False;self._mr_feature=None;self._mr_selection=None
        self._mr_signal_index=0;self._mr_after_busy=False;self._mr_denied_intents=set()
        self._mr_first_retired=False;self._mr_suspended=False
        self._mr_sequence=0;self._mr_pair_sequence=0;self._mr_episode=0;self._mr_last_snapshot=None
        self._mr_creation_snapshot=None;self._mr_recovery_ref=None;self._mr_suspended_entry_ids=set()
        self._mr_cached_feature_key=None;self._mr_cached_feature=None;self._mr_last_sol_boundary=None
        self._mr_submission_results={}

    def _mr_log(self,event,ns,**fields):
        self._mr_sequence+=1
        if event=='NATIVE_SNAPSHOT':self._mr_last_snapshot='risk:'+str(self._mr_sequence)
        ep=getattr(self,'_domain',None);ep=getattr(ep,'episode',None)
        row=dict(schema=SCHEMA,sequence=self._mr_sequence,event=event,timestamp_ns=str(ns),
            parent=getattr(ep,'id',None),risk_episode_id=(str(getattr(ep,'id',None))+':'+str(self._mr_episode)),snapshot_ref=self._mr_last_snapshot)
        row.update(fields);self.method_a_risk_audit.append(wire(row));return row

    def _pair_log(self,event,ns,**fields):
        if not self._mr_enabled():return super()._pair_log(event,ns,**fields)
        self._mr_pair_sequence+=1
        row=dict(schema=SCHEMA,sequence=self._mr_pair_sequence,event=event,timestamp_ns=str(ns),
            parent=self._pair['parent'] if self._pair else self._mr_parent,risk_episode_id=str(self._mr_parent)+':'+str(self._mr_episode),snapshot_ref=self._mr_last_snapshot)
        if event=='SOL_NATIVE_BOUNDARY':
            self._mr_last_sol_boundary='paired:'+str(self._mr_pair_sequence)
            position=self._pair_position(self.config.sol_id)
            fields['native_sol_position']=None if position is None else position.to_dict()
            fields['close_owners']=[dict(order_id=oid,kind=owner['kind'],native_order=None if order is None else order.to_dict()) for oid,owner,order in self._pair_work(instrument=self.config.sol_id,kinds={'SOL_CAP','SOL_CLOSE'})]
        if event=='PARENT_NATIVE_TERMINAL_FLAT':
            fields.update(native_positions=[p.to_dict() for p in self.cache.positions_open()],native_orders_open=[o.to_dict() for o in self.cache.orders_open()],native_orders_inflight=[o.to_dict() for o in self.cache.orders_inflight()],native_pending_ids=list(self._pending_by_order))
        row.update(fields);self.paired_prefix_audit.append(wire(row))

    def _mr_original_second(self):
        p=self._split_parent
        if p is None:return None
        return dict(parent=p['episode_id'],original_quantity=str(p['quantity']),original_first_quantity=str(p['first_quantity']),
            actual_filled=str(p['filled']),actual_first_filled=str(p['first_filled']),original_expiry_ns=str(p['deadline_ns']),
            original_discount=str(self.config.research_btc_split_discount),fallback=p['fallback'],closed=p['closed'],
            known_off_since_ns=None if self._mr_off_since is None else str(self._mr_off_since),first_risk_retired=self._mr_first_retired,
            remaining_original_quantity=str(p['quantity']-p['filled']))

    def _mr_fail(self,reason,ns):
        if self._mr_failed:return
        self._mr_failed=True
        capture_errors=[];positions=[];account=None
        try:
            account=native_account_snapshot(self.cache.account_for_venue(self.config.btc_id.venue),(self.config.btc_id,self.config.sol_id))
            positions=[p.to_dict() for p in self.cache.positions_open()]
        except Exception as error:capture_errors.append(type(error).__name__+':'+str(error))
        self._mr_log('QUALIFICATION_NO_GO',ns,reason=reason,failure_native_account=account,failure_positions=positions,failure_capture_errors=capture_errors)
        if self._pair:super()._pair_fail(reason,ns)
        self._begin_forced_close('METHOD_A_'+reason)

    @exact_algebra
    def _mr_margin(self,leg,qty,price):
        policy=self.config.margin_policy
        instrument=self.config.btc_id if leg=='BTC' else self.config.sol_id
        # Frozen TierMarginPolicy semantics; no update_mark/account mutation.
        profile=getattr(policy,'_profile',None)
        leverage=getattr(policy,'_selected_leverage',{}).get(instrument)
        if profile is None or leverage is None or leverage<=0:raise ValueError('UNKNOWN_SCENARIO_MARGIN')
        tier=profile.tier_for('BTCUSDT' if leg=='BTC' else 'SOLUSDT',qty*price)
        return qty*price*max(tier.im,D(1)/leverage),max(D(0),qty*price*tier.mm-tier.deduction)

    def _mr_snapshot(self,ns):
        ids=(self.config.btc_id,self.config.sol_id)
        marks=[];quantities=[];positions=self.cache.positions_open()
        if any(p.instrument_id not in ids or p.strategy_id!=self.id for p in positions):raise ValueError('UNKNOWN_FOREIGN_NATIVE_POSITION')
        account=self.cache.account_for_venue(self.config.btc_id.venue)
        inst=self.cache.instrument(self.config.btc_id)
        if account is None:raise ValueError('UNKNOWN_NATIVE_ACCOUNT')
        balance=account.balance_total(inst.quote_currency)
        free=account.balance_free(inst.quote_currency)
        if balance is None or free is None:raise ValueError('UNKNOWN_NATIVE_CASH_FREE')
        equity=balance.as_decimal()
        parity=[]
        for leg,iid in zip(('BTC','SOL'),ids):
            mark=self._latest_marks.get(iid)
            if mark is None or not 0<=ns-mark.ts_event<=2*MINUTE:raise ValueError('UNKNOWN_STALE_MARK')
            marks.append(mark.price)
            found=[p for p in positions if p.instrument_id==iid]
            if len(found)>1:raise ValueError('UNKNOWN_NETTING_MULTIPLE_POSITION')
            pos=found[0] if found else None
            q=(pos.quantity.as_decimal()*(1 if pos.is_long else -1)) if pos else D(0)
            quantities.append(q)
            if pos:
                equity+=pos.unrealized_pnl(self.cache.instrument(iid).make_price(mark.price)).as_decimal()
                expected=self._mr_margin(leg,abs(q),mark.price)
                native=(account.margin_init(iid),account.margin_maint(iid))
                if any(v is None or v.currency!=inst.quote_currency for v in native):raise ValueError('UNKNOWN_NATIVE_MARGIN')
                current=tuple(v.as_decimal() for v in native)
                if current!=expected:raise ValueError('ZERO_SHOCK_NATIVE_MARGIN_PARITY')
                parity.append(dict(leg=leg,native_position_id=str(pos.id),native_initial=str(current[0]),native_maintenance=str(current[1]),scenario_zero_initial=str(expected[0]),scenario_zero_maintenance=str(expected[1]),exact_equal=current==expected))
        observer=self.config.research_method_a_peak_source
        if observer is None or observer.unknown or observer.events.peak is None:raise ValueError('UNKNOWN_COHERENT_PREFILL_PEAK')
        self._mr_peak=max(self._mr_peak,D(observer.events.peak['equity']),equity)
        state=State(*quantities,equity,self._mr_peak,*marks)
        feature_key=ns//DAY
        if self._mr_cached_feature_key!=feature_key:
            rows=tuple(Observation(int(b.close_time.timestamp()*1_000_000_000),
                max(int(b.available_at.timestamp()*1_000_000_000),int(b.close_time.timestamp()*1_000_000_000)+MINUTE),D(str(b.btc_close)),D(str(b.sol_close))) for b in self._bars)
            funding=tuple(Funding(leg,effective,available,D(rate),interval) for leg,effective,available,rate,interval in self.config.research_method_a_funding)
            self._mr_cached_feature=lagged_features(rows,funding,ns);self._mr_cached_feature_key=feature_key
        feature=self._mr_cached_feature;self._mr_feature=feature
        self._mr_log('NATIVE_SNAPSHOT',ns,native_cash=str(balance.as_decimal()),equity=str(equity),peak=str(self._mr_peak),cushion=str(state.cushion),
            native_positions=[p.to_dict() for p in positions],
            marks=[dict(instrument=str(iid),raw_price=str(mark.price),native_price=str(self.cache.instrument(iid).make_price(mark.price)),event_ns=str(mark.ts_event),available_ns=str(mark.ts_init),age_ns=str(ns-mark.ts_event)) for iid in ids for mark in (self._latest_marks[iid],)],
            native_account=native_account_snapshot(account,ids),margin_parity=parity,
            feature={**{k:str(v) for k,v in feature.__dict__.items()},'omega':[tuple(map(str,x)) for x in feature.shocks()]},
            coherent_peak_source=dict(sequence=observer.sequence,epoch=observer.epoch,peak=dict(observer.events.peak)))
        return state,feature

    def _mr_liabilities(self,ns,proposed=None,exclude=None):
        rows={str(o.client_order_id):o for o in self.cache.orders_open()+self.cache.orders_inflight()}
        missing=(set(self._pending_by_order)|{oid for oid,_,_ in self._pair_work()})-{exclude}
        if any(oid not in rows and (self.cache.order(ClientOrderId(oid)) is None or not self.cache.order(ClientOrderId(oid)).is_closed) for oid in missing):raise ValueError('UNKNOWN_OWNED_ACK')
        result=[]
        for oid,order in rows.items():
            if order.is_closed:continue
            if order.strategy_id!=self.id or order.instrument_id not in (self.config.btc_id,self.config.sol_id):raise ValueError('UNKNOWN_FOREIGN_ORDER')
            owner=self._pair_orders.get(oid); ma=self._ma_owners.get(oid)
            if owner is None and ma is None and oid not in self._pending_by_order:raise ValueError('UNKNOWN_ORDER_OWNER')
            leaves=order.leaves_qty.as_decimal()
            # Pending old/new generations contribute a single maximum liability.
            if owner and owner.get('pending'):
                leaves=max(leaves,owner['pending']['payload'][0]-order.filled_qty.as_decimal())
            command=self._ma_commands.get(oid)
            if command:leaves=max(leaves,command['total']-order.filled_qty.as_decimal())
            iid=order.instrument_id;inst=self.cache.instrument(iid)
            mark=self._latest_marks.get(iid)
            if mark is None:raise ValueError('UNKNOWN_LIABILITY_MARK')
            result.append(Liability(oid,'BTC' if iid==self.config.btc_id else 'SOL',1 if order.side==OrderSide.BUY else -1,
                exact_lots(leaves,inst.size_increment.as_decimal()),inst.size_increment.as_decimal(),order.is_reduce_only,mark.price*(TAKER+RESERVE)))
        if proposed is not None:result.append(proposed)
        return tuple(result)

    def _mr_tier_boundaries(self,leg,price):
        profile=self.config.margin_policy._profile
        points=[]
        for tier in profile.tiers['BTCUSDT' if leg=='BTC' else 'SOLUSDT']:
            points.append(F(tier.cap)/F(price))
            if tier.mm:points.append(F(tier.deduction)/F(tier.mm)/F(price))
        return points

    def _mr_envelope(self,state,feature,liabilities):
        return tier_partition_envelope(state,feature,liabilities,self._mr_margin,self._mr_tier_boundaries)

    def _pair_sol_v2(self):
        if not self._mr_enabled():return super()._pair_sol_v2()
        return bool(self._pair)

    def _pair_sol_order(self,oid,owner):
        if not self._mr_enabled():return super()._pair_sol_order(oid,owner)
        order=self.cache.order(ClientOrderId(oid));p=self._pair
        if p is None or owner.get('parent')!=p['parent'] or owner.get('instrument')!=self.config.sol_id or order is None or order.strategy_id!=self.id or order.instrument_id!=self.config.sol_id or order.side!=(OrderSide.BUY if p['side']==1 else OrderSide.SELL) or not order.is_reduce_only or order.exec_algorithm_id is not None:
            raise ValueError('SOL_REDUCTION_OWNER_UNKNOWN')
        # Native NETTING position.id is authority. Cache order association may
        # be absent or present; neither creates a synthetic position identity.
        position=self._pair_position(self.config.sol_id)
        if position is not None and (position.strategy_id!=self.id or position.is_long!=(p['side']==-1)):
            raise ValueError('SOL_NETTING_POSITION_OWNER_UNKNOWN')
        return order

    def _pair_protect(self,ns):
        if not self._mr_enabled():return super()._pair_protect(ns)
        return self._pair_sol_protect(ns)

    def _pair_no_increase(self):
        if not self._mr_enabled():return super()._pair_no_increase()
        return getattr(self,'_mr_failed',False)

    def _pair_btc_tp_paused(self):
        if not self._mr_enabled():return super()._pair_btc_tp_paused()
        return False

    def _pair_cancel_btc_increases(self,ns):
        if not self._mr_enabled():return super()._pair_cancel_btc_increases(ns)
        # Suspend SECOND only. Uncompleted FIRST can never be restored.
        self._mr_suspended=True
        p=self._split_parent
        if p and p['first_filled']<p['first_quantity']:self._mr_first_retired=True
        for oid,intent in list(self._pending_by_order.items()):
            if intent.action=='BTC_ENTRY':
                order=self.cache.order(ClientOrderId(oid))
                if order is None:continue
                if not order.is_closed and not order.is_pending_cancel:
                    self._mr_suspended_entry_ids.add(oid)
                    self._mr_log('ORIGINAL_SECOND_SUSPEND',ns,order_id=oid,native_order=order.to_dict(),original_second=self._mr_original_second())
                    self.cancel_order(order)

    def _split_check(self,tick):
        if not self._mr_enabled():return super()._split_check(tick)
        p=self._split_parent
        if self._mr_on or self._mr_failed:
            self._pair_cancel_btc_increases(tick.ts_event);return
        if p and self._mr_suspended:
            self._mr_log('ORIGINAL_SECOND_RELEASE_CHECK',tick.ts_event,original_second=self._mr_original_second(),old_orders=[dict(order_id=oid,native_order=None if self.cache.order(ClientOrderId(oid)) is None else self.cache.order(ClientOrderId(oid)).to_dict()) for oid in sorted(self._mr_suspended_entry_ids)])
            if self._mr_first_retired:return
            if self._mr_off_since is None:self._mr_off_since=tick.ts_event
            if tick.ts_event>=p['deadline_ns']:
                self._split_stop('METHOD_A_ORIGINAL_EXPIRY');return
            if tick.ts_event<self._mr_off_since+MINUTE:return
            for oid,intent in self._pending_by_order.items():
                if intent.action=='BTC_ENTRY':
                    order=self.cache.order(ClientOrderId(oid))
                    if order is None or not order.is_closed:return
        return super()._split_check(tick)

    def _pair_quote(self,tick):
        if not self._mr_enabled():return super()._pair_quote(tick)
        if self._mr_busy:return
        self._mr_busy=True
        try:self._mr_quote(tick)
        except (ValueError,KeyError,TypeError) as error:self._mr_fail(str(error),tick.ts_event)
        finally:self._mr_busy=False

    def _mr_quote(self,tick):
        ns=tick.ts_event;self._pair_last_quote[tick.instrument_id]=tick
        self._pair_sol_retire_check(ns)
        if self._forced_close_reason or self._liquidating or self.terminal_lifecycle.get('lockout'):
            if self._pair:
                self._pair_sol_global_begin(self._forced_close_reason or 'TERMINAL',ns)
                self._pair_sol_global_dispatch(tick)
            return
        ep=self._domain.episode;btc=self._pair_qty(self.config.btc_id)
        if not ep or not btc:
            if self._pair:
                self._pair['close_sol']=True
                self._pair_sol_reduce(ns,tick.instrument_id)
                self._pair_release_if_terminal(ns)
            return
        state,feature=self._mr_snapshot(ns)
        if self._mr_parent!=ep.id:
            self._mr_parent=ep.id;self._mr_on=False;self._mr_allocated=False;self._mr_off_since=None;self._mr_selection=None
            self._mr_first_retired=False;self._mr_suspended=False
        signals=self.config.research_method_a_selection
        while self._mr_signal_index<len(signals) and signals[self._mr_signal_index].not_before_ns<ns:
            signal=signals[self._mr_signal_index];self._mr_signal_index+=1
            side=1 if state.btc>0 else -1
            if signal.valid and (getattr(signal,'b2_long' if side==1 else 'b2_short') or getattr(signal,'f0_long' if side==1 else 'f0_short')):
                self._mr_selection=signal
        selection=self._mr_selection
        active=False;branch=None
        if selection is not None:
            side=1 if state.btc>0 else -1
            branch='B2' if getattr(selection,'b2_long' if side==1 else 'b2_short') else 'F0'
            boundary=(selection.k_long if side==1 else selection.k_short) if branch=='B2' else selection.open_o
            if boundary is None:raise ValueError('UNKNOWN_SELECTION_BOUNDARY')
            active=ns>selection.not_before_ns and side*(state.pb-boundary)<0
            if not active and ns>selection.not_before_ns:self._mr_selection=None
        if self._pair and self._pair.get('deadline_ns') is not None and ns>=self._pair['deadline_ns']:
            active=False;self._mr_selection=None
        prior_on=self._mr_on;prior_allocated=self._mr_allocated;prior_day=self._mr_last_episode_day
        on,band,target=hedge_target(state,feature,self._mr_on,active)
        if not on and self._mr_on:self._mr_off_since=ns
        if on and not self._mr_on:
            if self._mr_allocated and self._mr_last_episode_day==feature.end_ns:on=False
            elif not self._pair_work(instrument=self.config.sol_id) and not state.sol:
                self._mr_allocated=False
                if self._pair:
                    self._pair.update(entry_qty=D(0),entry_notional=D(0),p0=None,first_fill_ns=None,deadline_ns=None,consumed=set(),tp_lots={},signature=None,close_sol=False,entry_terminal=True,entry_sent=False)
            else:on=False
        if on and not self._mr_on:self._mr_episode+=1
        self._mr_on=on
        if on!=prior_on:
            self._mr_log('RISK_BAND_TRANSITION',ns,previous_on=prior_on,on=on,prior_allocation_used=prior_allocated,allocation_used=self._mr_allocated,previous_feature_end_ns=None if prior_day is None else str(prior_day),feature_end_ns=str(feature.end_ns),selection_ns=None if selection is None else str(selection.decision_ns),known_off_since_ns=None if self._mr_off_since is None else str(self._mr_off_since),sol_native_held=str(abs(state.sol)),sol_owned_work=[dict(order_id=oid,native_order=None if order is None else order.to_dict()) for oid,owner,order in self._pair_work(instrument=self.config.sol_id)])
        ev=evaluate(state,feature,self._mr_margin)
        if self._pair is None:
            b=self.cache.instrument(self.config.btc_id);s=self.cache.instrument(self.config.sol_id)
            caps=JointCaps(btc,btc,D(0));caps.btc_lot=b.size_increment.as_decimal();caps.sol_lot=s.size_increment.as_decimal()
            self._pair=dict(parent=ep.id,side=ep.side,branch='METHOD_A',signal_ns=ns,eligible_ns=ns+MINUTE,quantity=D(0),caps=caps,
                boundary=state.pb,atr=D(1),risk='ACTIVE_RISK' if on else 'INACTIVE_RISK',first_fill_ns=None,deadline_ns=None,
                entry_terminal=True,entry_qty=D(0),entry_notional=D(0),p0=None,consumed=set(),signature=None,
                protection_since=None,debt_since=None,close_sol=False,failed=False,last_btc=btc,last_sol=abs(state.sol),entry_sent=False,generation=0,tp_lots={})
        p=self._pair;p['risk']='ACTIVE_RISK' if on else 'INACTIVE_RISK'
        p['caps'].bmax=btc
        p['caps'].solmax=mr_floor_lot(F(abs(state.btc))*F(state.pb)*F(feature.sigma_b)/F(feature.sigma_s)/F(state.ps),self.cache.instrument(self.config.sol_id).size_increment.as_decimal())
        # Current hard breach cannot borrow relief from an unfilled hedge.
        if state.cushion<=0 or ev.worst_deficit>0 or not ev.margin_pass:
            self._pair_cancel_btc_increases(ns)
            self._mr_recover(tick,state,feature,ev)
            return
        p['debt_since']=None  # Only a fresh actual safe snapshot clears breach debt.
        if p['protection_since'] is not None and ns>p['protection_since']:
            raise ValueError('PROTECTION_OVERDUE_NEXT_QUOTE')
        if self._pair_qty(self.config.sol_id):
            if not on:
                p['close_sol']=True
            self._pair_sol_reduce(ns,tick.instrument_id) if p['close_sol'] or abs(state.sol)>p['caps'].solmax else self._pair_protect(ns)
        if on:self._pair_cancel_btc_increases(ns)
        if self.config.research_method_a_risk=='HEDGE' and on and not self._mr_allocated and not state.sol and selection and tick.instrument_id==self.config.sol_id:
            target=mr_floor_lot(F(abs(state.btc))*F(state.pb)*F(feature.sigma_b)/F(feature.sigma_s)/F(state.ps)*(F(1) if band=='HIGH' else F(1,2)),self.cache.instrument(self.config.sol_id).size_increment.as_decimal())
            useful,benefit,cost=useful_hedge(state,feature,target)
            self._mr_creation_snapshot=self._mr_last_snapshot
            self._mr_log('HEDGE_ADMISSION',ns,band=band,target=str(target),benefit=str(benefit),cost=str(cost),useful=useful,creation_snapshot_ref=self._mr_creation_snapshot)
            if useful and target>0:
                p['quantity']=target;p['atr']=selection.atr_sol;p['branch']=branch;p['entry_terminal']=False;p['entry_sent']=True;p['close_sol']=False;p['entry_band']=band
                self._pair_submit(self.config.sol_id,-ep.side,target,'ENTRY',ns)
        self._mr_log('DECISION',ns,on=on,band=band,actual_loss=str(ev.loss),deficit=str(ev.worst_deficit),entry_allocated=self._mr_allocated,frozen_entry_band=p.get('entry_band'),quote_instrument=str(tick.instrument_id))

    def _mr_recover(self,tick,state,feature,initial):
        if state.cushion<=0:
            self._mr_fail('CUSHION_BREACH',tick.ts_event);return
        liabilities=self._mr_liabilities(tick.ts_event)
        candidates=[]
        for leg,iid,held in (('BTC',self.config.btc_id,state.btc),('SOL',self.config.sol_id,state.sol)):
            if not held:continue
            result=self._mr_recovery_choice(leg,state,feature,liabilities,initial.worst_deficit,tick.ts_event)
            if result is not None:
                d,objective,remaining_btc,turnover,proof=result
                candidates.append((objective,-remaining_btc,turnover,leg,iid,d,proof))
        if not candidates:
            self._mr_fail('NO_PROVEN_NONATOMIC_RECOVERY',tick.ts_event);return
        objective,negative_btc,turnover,leg,iid,d,proof=min(candidates,key=lambda x:x[:4])
        self._mr_recovery_ref='recovery:'+str(self._mr_sequence+1)
        self._mr_log('RECOVERY_DECISION',tick.ts_event,recovery_ref=self._mr_recovery_ref,selected_leg=leg,quantity=str(D(d)*self.cache.instrument(iid).size_increment.as_decimal()),initial_signed_deficit=str(initial.worst_deficit),full_signed_deficit=str(objective),remaining_btc=str(-negative_btc),turnover=str(turnover),legal_feasible_intervals=proof)
        p=self._pair;p['debt_since']=p['debt_since'] if p['debt_since'] is not None else tick.ts_event
        if tick.ts_event>p['debt_since']+MINUTE:raise ValueError('RECOVERY_DEADLINE')
        if tick.instrument_id==iid and self._mr_recovery_ready(iid,tick.ts_event):
            lot=self.cache.instrument(iid).size_increment.as_decimal()
            self._pair_submit(iid,-1 if (state.btc if leg=='BTC' else state.sol)>0 else 1,D(d)*lot,'BTC_DEBT' if leg=='BTC' else 'SOL_CAP',tick.ts_event)

    def _pair_submit(self,instrument,side,qty,kind,ns,**kwargs):
        if not self._mr_enabled():return super()._pair_submit(instrument,side,qty,kind,ns,**kwargs)
        if kind=='ENTRY':return self._mr_submit_entry(instrument,side,qty,ns)
        quote=self.cache.quote_tick(instrument)
        if quote is None or not 0<=ns-quote.ts_event<=MINUTE:raise ValueError('UNKNOWN_SUBMIT_QUOTE')
        inst=self.cache.instrument(instrument)
        if qty<=0 or (inst.min_quantity and qty<inst.min_quantity.as_decimal()) or (inst.min_notional and qty*(quote.bid_price.as_decimal() if side<0 else quote.ask_price.as_decimal())<inst.min_notional.as_decimal()):
            raise ValueError('UNEXECUTABLE_NATIVE_REDUCE_OR_ENTRY')
        return super()._pair_submit(instrument,side,qty,kind,ns,**kwargs)

    def _pair_fill(self,event):
        if not self._mr_enabled():return super()._pair_fill(event)
        owner=self._pair_orders.get(str(event.client_order_id))
        if owner and owner['kind']=='STOP' and self._pair:
            self._pair['close_sol']=True;self._pair['stop_filled']=True
        if owner and owner['kind']=='BTC_DEBT' and str(event.trade_id) not in self._pair_seen_fills:
            ep=self._domain.episode
            if ep is None:raise ValueError('RISK_RETIREMENT_PARENT_UNKNOWN')
            from coinmaster.strategy.method_a_tp import cumulative_entitlement
            step=self.cache.instrument(self.config.btc_id).size_increment.as_decimal()
            _,leaves=cumulative_entitlement(exact_lots(ep.btc_entry_qty_exact,step),ep.btc_tp_filled_lots,ep.btc_risk_retired_lots)
            left=exact_lots(event.last_qty.as_decimal(),step)
            for level in sorted(leaves):
                take=min(left,leaves[level]);ep.btc_risk_retired_lots[level]=ep.btc_risk_retired_lots.get(level,0)+take;left-=take
            if left:raise ValueError('RISK_RETIREMENT_EXCEEDS_HELD')
        result=super()._pair_fill(event)
        if result:
            self._pair_protect(event.ts_event)
            self._ma_reconcile(event.ts_event)
        return result

    def _pair_position_event(self,ns):
        if not self._mr_enabled():return super()._pair_position_event(ns)
        if self._pair:
            p=self._pair;p['last_btc']=self._pair_qty(self.config.btc_id);p['last_sol']=self._pair_qty(self.config.sol_id)
            if not p['last_btc']:p['close_sol']=True
            self._pair_protect(ns)
            self._pair_release_if_terminal(ns)

    @exact_algebra
    def _mr_lines(self,state,feature,unpaid):
        result=[]
        for b,s in feature.shocks():
            pb=state.pb*(1+b);ps=state.ps*(1+s)
            if min(pb,ps)<=0:raise ValueError('NONPOSITIVE_SCENARIO_PRICE')
            pnl=state.btc*state.pb*b+state.sol*state.ps*s
            cost=abs(state.btc)*pb*(TAKER+RESERVE+feature.fund_b)+abs(state.sol)*ps*(TAKER+RESERVE+feature.fund_s)+unpaid
            ib,mb=self._mr_margin('BTC',abs(state.btc),pb);is_,ms=self._mr_margin('SOL',abs(state.sol),ps)
            es=state.equity+pnl-unpaid
            result.append((-pnl+cost-state.cushion,ib+is_-es,mb+ms-es))
        return tuple(result)

    def _mr_leg(self,leg,state,feature,liabilities):
        iid=self.config.btc_id if leg=='BTC' else self.config.sol_id
        held=state.btc if leg=='BTC' else state.sol
        lot=self.cache.instrument(iid).size_increment.as_decimal()
        orders=tuple(x for x in liabilities if x.leg==leg)
        opening=tuple(x for x in orders if not x.reduce_only)
        sign=1 if held>0 else -1 if held<0 else opening[0].side if opening else 1
        if any(x.side!=sign or x.lot!=lot for x in opening):raise ValueError('UNKNOWN_CROSSING_LIABILITY')
        h=exact_lots(abs(held),lot);o=sum(x.lots for x in opening)
        reductions=tuple((x.lots,F(x.cost_per_unit)*F(lot),x.identity) for x in orders if x.reduce_only and x.side==-sign)
        r=sum(n for n,c,oid in reductions)
        entry=sum((F(x.cost_per_unit)*F(lot)*x.lots for x in opening),F(0))
        fixed=set()
        for b,s in feature.shocks():
            price=(state.pb if leg=='BTC' else state.ps)*(1+(b if leg=='BTC' else s))
            for threshold in self._mr_tier_boundaries(leg,price):
                x=F(threshold)/F(lot);a=ifloor(x);z=iceil(x)
                fixed.update((a-1,a,z,z+1))
        low=max(0,h-r);high=h+o
        points={low,high};cumulative=0
        for n,c,oid in sorted(reductions,key=lambda x:(-x[1],x[2])):
            cumulative+=n
            points.update(q for q in (h+o-cumulative-1,h+o-cumulative,h+o-cumulative+1) if low<=q<=high)
        points.update(q for q in fixed if low<=q<=high)
        return dict(leg=leg,iid=iid,sign=sign,lot=lot,h=h,o=o,reductions=reductions,entry=entry,fixed=tuple(sorted(fixed)),points=tuple(sorted(points)))

    @staticmethod
    def _mr_frontier(data,q,extra=()):
        reductions=tuple(data['reductions'])+tuple(extra)
        remaining=min(sum(n for n,c,oid in reductions),data['h']+data['o']-q)
        if remaining<0:raise ValueError('UNKNOWN_ROUTE_QUANTITY')
        cost=data['entry']
        for n,c,oid in sorted(reductions,key=lambda x:(-x[1],x[2])):
            take=min(remaining,n);cost+=take*c;remaining-=take
        if remaining:raise ValueError('UNKNOWN_ROUTE_COST')
        return cost

    @exact_algebra
    def _mr_recovery_choice(self,leg,state,feature,liabilities,initial_deficit,ns):
        selected=self._mr_leg(leg,state,feature,liabilities)
        other=self._mr_leg('SOL' if leg=='BTC' else 'BTC',state,feature,liabilities)
        quote=self.cache.quote_tick(selected['iid'])
        if quote is None or not 0<=ns-quote.ts_event<=MINUTE:return None
        inst=self.cache.instrument(selected['iid']);lot=selected['lot'];h=selected['h']
        mark=state.pb if leg=='BTC' else state.ps
        unit=F(lot)*F(mark)*(F(TAKER)+F(RESERVE))
        price=quote.bid_price.as_decimal() if selected['sign']>0 else quote.ask_price.as_decimal()
        minimum=1
        if inst.min_quantity:minimum=max(minimum,iceil(F(inst.min_quantity.as_decimal())/F(lot)))
        if inst.min_notional:minimum=max(minimum,iceil(F(inst.min_notional.as_decimal())/(F(lot)*F(price))))
        legal=((minimum,h),) if minimum<=h else ()
        if leg=='BTC' and legal:
            ep=self._domain.episode
            if ep is None:raise ValueError('UNKNOWN_RECOVERY_PARENT')
            from coinmaster.strategy.method_a_tp import cumulative_entitlement
            _,leaves=cumulative_entitlement(exact_lots(ep.btc_entry_qty_exact,lot),ep.btc_tp_filled_lots,ep.btc_risk_retired_lots)
            m=self._ma_plans[ep.id];reference=ep.btc_planref_vwap or self._split_parent['first_vwap']
            prices=self._ma_wire_prices(ep,inst,D(str(reference)),m['d3'])
            rights=[];accumulated=0
            # Retirement consumes low levels first; residual keeps their suffix.
            for level in reversed(sorted(leaves)):
                n=leaves[level]
                if n:
                    min_live=1
                    if inst.min_quantity:min_live=max(min_live,iceil(F(inst.min_quantity.as_decimal())/F(lot)))
                    if inst.min_notional:min_live=max(min_live,iceil(F(inst.min_notional.as_decimal())/(F(lot)*F(prices[level]))))
                    if n>=min_live:rights.append((accumulated+min_live,accumulated+n))
                    accumulated+=n
            if accumulated!=h:raise ValueError('UNKNOWN_RECOVERY_ENTITLEMENT')
            legal=tuple((max(minimum,h-hi),h-lo) for lo,hi in rights if max(minimum,h-hi)<=h-lo)+((h,h),)
        def outcome(q_selected,q_other):
            amounts={selected['leg']:D(q_selected)*selected['lot']*selected['sign'],other['leg']:D(q_other)*other['lot']*other['sign']}
            return State(amounts['BTC'],amounts['SOL'],state.equity,state.peak,state.pb,state.ps)
        def decimal(value):
            value=F(value);return D(value.numerator)/D(value.denominator)
        def route(d,q):
            values=[]
            for qo in other['points']:
                unpaid=decimal(self._mr_frontier(selected,q,((d,unit,'proposed-recovery'),))+self._mr_frontier(other,qo))
                for loss,initial,maintenance in self._mr_lines(outcome(q,qo),feature,unpaid):
                    values.extend(((F(loss)-F(initial_deficit),False),(F(initial),False),(F(maintenance),True)))
            return tuple(values)
        def objective(d):
            # Exactly signed L-C, not clipped at zero. No pending relief.
            fixed_other=other['h']
            return tuple(F(row[0]) for row in self._mr_lines(outcome(h-d,fixed_other),feature,decimal(unit*d)))
        intervals,candidates=recovery_candidates(h=h,opening=selected['o'],old_reductions=tuple((n,c) for n,c,oid in selected['reductions']),
            proposed_cost=unit,fixed_q_points=selected['fixed'],route_constraints=route,objective_values=objective,
            initial_deficit=F(initial_deficit),legal_intervals=legal)
        if not candidates:return None
        def rank(d):
            final_btc=abs(state.btc)-D(d)*lot if leg=='BTC' else abs(state.btc)
            return max(objective(d)),-final_btc,D(d)*lot*mark,d
        d=min(candidates,key=rank)
        objective_,negative_btc,turnover,_=rank(d)
        return d,objective_,-negative_btc,turnover,intervals

    def _record_submission(self,order,intent_id,episode_id,action,reason=None,level=None):
        if not self._mr_enabled():return super()._record_submission(order,intent_id,episode_id,action,reason,level)
        if self._mr_failed or self._forced_close_reason or self._liquidating:
            return bool(order.is_reduce_only) and super()._record_submission(order,intent_id,episode_id,action,reason,level)
        if action in ('PAIRED_TP','PAIRED_STOP'):
            # Positive reduce-only protection carries no increase permission.
            return super()._record_submission(order,intent_id,episode_id,action,reason,level)
        ns=self.clock.timestamp_ns();oid=str(order.client_order_id)
        try:
            state,feature=self._mr_snapshot(ns)
            leg='BTC' if order.instrument_id==self.config.btc_id else 'SOL'
            lot=self.cache.instrument(order.instrument_id).size_increment.as_decimal()
            proposed=Liability(oid,leg,1 if order.side==OrderSide.BUY else -1,exact_lots(order.quantity.as_decimal(),lot),lot,order.is_reduce_only,
                (state.pb if leg=='BTC' else state.ps)*(TAKER+RESERVE))
            envelope=self._mr_envelope(state,feature,self._mr_liabilities(ns,proposed,exclude=oid))
            initial=evaluate(state,feature,self._mr_margin)
            recovery=order.is_reduce_only and initial.worst_deficit>0
            allowed=envelope.safe or recovery and envelope.margin_pass and envelope.worst_deficit<=initial.worst_deficit
            self._mr_log('BEFORE_NATIVE_DISPATCH' if allowed else 'ENVELOPE_DENY',ns,order_id=oid,action=action,quantity=str(order.quantity),
                pending_hedge_credit='0',all_partial_partition_states=envelope.states,deficit=str(envelope.worst_deficit),margin_pass=envelope.margin_pass,
                native_initialized_event_id=str(order.init_event.id),native_order=order.to_dict(),liabilities=self._mr_liability_rows(ns,exclude=oid,proposed=order),creation_snapshot_ref=self._mr_creation_snapshot,recovery_ref=self._mr_recovery_ref,original_second=self._mr_original_second())
            if not allowed:
                self._mr_submission_results[oid]=EntrySubmissionDecision('DENY','JOINT_EXECUTION_ENVELOPE',episode_id,str(order.instrument_id),proposed.side,str(order.quantity),self._mr_last_snapshot,oid)
                if action=='BTC_ENTRY':self._mr_denied_intents.add(intent_id);self._mr_suspended=True
                return False
        except (ValueError,KeyError,TypeError) as error:
            self._mr_submission_results[oid]=EntrySubmissionDecision('UNKNOWN',str(error),episode_id,str(order.instrument_id),1 if order.side==OrderSide.BUY else -1,str(order.quantity),self._mr_last_snapshot,oid)
            self._mr_fail(str(error),ns);return False
        allowed=super()._record_submission(order,intent_id,episode_id,action,reason,level)
        self._mr_submission_results[oid]=EntrySubmissionDecision('ALLOW' if allowed else 'TRANSPORT_FAILURE','DURABLE_CHECKPOINT_ACCEPTED' if allowed else 'DURABLE_SUBMIT_DENIED',episode_id,str(order.instrument_id),1 if order.side==OrderSide.BUY else -1,str(order.quantity),self._mr_last_snapshot,oid)
        if not allowed:self._mr_fail('DURABLE_SUBMIT_DENIED',ns)
        return allowed

    def _deny_local_entry(self,intent,reason,ts_now):
        if not self._mr_enabled():return super()._deny_local_entry(intent,reason,ts_now)
        if intent.id not in self._mr_denied_intents and reason!='PRE_SUBMIT_INCREASE_GATE_OR_MINIMUM':return super()._deny_local_entry(intent,reason,ts_now)
        self._mr_denied_intents.discard(intent.id)
        p=self._split_parent;ep=self._domain.episode
        if p and ep and p['episode_id']==ep.id==intent.episode_id and p['first_filled']==p['first_quantity'] and self._pair_qty(self.config.btc_id)>0:
            self._domain.on_parent_terminal(intent.id)
            self._mr_log('ORIGINAL_SECOND_SUSPENDED_UNSENT',ts_now or self.clock.timestamp_ns(),parent=ep.id,original_expiry_ns=str(p['deadline_ns']),remaining=str(p['quantity']-p['filled']))
            return
        return super()._deny_local_entry(intent,reason,ts_now)

    def _pair_fail(self,reason,ns):
        if not self._mr_enabled():return super()._pair_fail(reason,ns)
        return self._mr_fail(reason,ns)

    def on_order_filled(self,event):
        if not self._mr_enabled():return super().on_order_filled(event)
        parent=self._domain.episode.id if self._domain.episode else None
        result=super().on_order_filled(event)
        self._mr_after_actual(event.ts_event)
        self._mr_log('ACTUAL_NATIVE_FILL',event.ts_event,parent=parent,native_event_id=str(event.id),trade_id=str(event.trade_id),order_id=str(event.client_order_id),native_fill=type(event).to_dict(event))
        return result

    def _mr_after_actual(self,ns):
        if self._mr_after_busy or self._forced_close_reason or self._liquidating:return
        if not self._pair or not self._pair_qty(self.config.btc_id):return
        self._mr_after_busy=True
        try:
            state,feature=self._mr_snapshot(ns);ev=evaluate(state,feature,self._mr_margin)
            self._pair['caps'].bmax=abs(state.btc)
            if state.cushion<=0:
                self._mr_fail('CUSHION_BREACH',ns);return
            if ev.worst_deficit>0 or not ev.margin_pass:
                if self._pair['debt_since'] is None:self._pair['debt_since']=ns
                if ns>self._pair['debt_since']+MINUTE:
                    self._mr_fail('RECOVERY_DEADLINE',ns);return
                self._pair_cancel_btc_increases(ns)
                choices=[]
                liabilities=self._mr_liabilities(ns)
                for leg,iid,held in (('BTC',self.config.btc_id,state.btc),('SOL',self.config.sol_id,state.sol)):
                    if held:
                        choice=self._mr_recovery_choice(leg,state,feature,liabilities,ev.worst_deficit,ns)
                        if choice is not None:
                            d,obj,btc,turn,proof=choice;choices.append((obj,-btc,turn,leg,iid,d,held,proof))
                if not choices:self._mr_fail('NO_PROVEN_POSTFILL_RECOVERY',ns);return
                objective,negative_btc,turnover,leg,iid,d,held,proof=min(choices,key=lambda x:x[:4])
                self._mr_recovery_ref='recovery:'+str(self._mr_sequence+1)
                self._mr_log('RECOVERY_DECISION',ns,recovery_ref=self._mr_recovery_ref,selected_leg=leg,quantity=str(D(d)*self.cache.instrument(iid).size_increment.as_decimal()),initial_signed_deficit=str(ev.worst_deficit),full_signed_deficit=str(objective),remaining_btc=str(-negative_btc),turnover=str(turnover),legal_feasible_intervals=proof)
                if self._mr_recovery_ready(iid,ns):
                    self._pair_submit(iid,-1 if held>0 else 1,D(d)*self.cache.instrument(iid).size_increment.as_decimal(),'BTC_DEBT' if leg=='BTC' else 'SOL_CAP',ns)
            else:self._pair['debt_since']=None
        except (ValueError,KeyError,TypeError) as error:self._mr_fail(str(error),ns)
        finally:self._mr_after_busy=False

    def _pair_sol_native_event(self, event, route):
        """Typed/generic routes share actual UUID dedup; public return is no ACK."""
        if not self._mr_enabled():return super()._pair_sol_native_event(event,route)
        oid = str(event.client_order_id)
        owner = self._pair_orders.get(oid)
        if not owner or owner["instrument"] != self.config.sol_id or owner["kind"] not in {"TP", "STOP"}:
            return
        event_id = getattr(event, "id", None)
        if event_id is None:
            self._pair_fail("SOL_UNKNOWN_NATIVE_EVENT_ID", event.ts_event)
            return
        key = str(event_id)
        if key in self._pair_sol_events:
            return
        self._pair_sol_events.add(key)
        name = type(event).__name__
        order = self.cache.order(event.client_order_id)
        if name == "OrderInitialized":
            if key != owner["initialized_event_id"] or event.strategy_id != self.id or event.instrument_id != self.config.sol_id:
                self._pair_fail("SOL_UNKNOWN_PRE_CACHE_INITIALIZATION", event.ts_event)
            return
        if (order is None or event.strategy_id != self.id or event.instrument_id != self.config.sol_id
                or not any(str(item.id) == key for item in order.events)):
            self._pair_fail("SOL_NATIVE_EVENT_OWNERSHIP_OR_HISTORY_UNKNOWN", event.ts_event)
            return
        self._pair_log("SOL_NATIVE_EVENT", event.ts_event, order_id=oid,
            native_event_id=key, event_type=name, route=route,
            observed_ns=self.clock.timestamp_ns(), status=None if order is None else order.status.name)
        if self._pair_sol_v2()and owner.get("retiring"):
            if name=="OrderCancelRejected":
                if not order.is_closed:raise ValueError("SOL_RETIRING_LIVE_CANCEL_REJECTED")
                self._pair_sol_retire_observe(oid,owner,event.ts_event,commit=True)
                if not owner["retiring"].get("terminal_event_id"):raise ValueError("SOL_RETIRING_LIVE_CANCEL_REJECTED")
            elif name in {"OrderExpired","OrderUpdated","OrderModifyRejected","OrderRejected","OrderDenied"}:
                raise ValueError("SOL_RETIRING_INVALID_NATIVE_EVENT")
            elif name!="OrderFilled":self._pair_sol_retire_observe(oid,owner,event.ts_event,commit=True)
            self._pair_sol_retire_check(event.ts_event)
            self._pair_protect(event.ts_event)
            self._pair_release_if_terminal(event.ts_event)
            return
        if self._pair_sol_v2():self._pair_sol_retire_check(event.ts_event)
        if name not in {"OrderUpdated", "OrderModifyRejected"}:
            return
        pending = owner.get("pending")
        if pending is None:
            self._pair_fail("SOL_UNOWNED_MODIFY_ACK", event.ts_event)
            return
        owner["pending"] = None
        if name == "OrderModifyRejected":
            owner["ack"] = None
            owner["rejected_desired"] = pending["desired"]
            self._pair_log("SOL_MODIFY_REJECTED", event.ts_event, order_id=oid,
                sequence=pending["sequence"], reason=str(event.reason))
        elif order is None or not self._pair_sol_payload_matches(order, pending["payload"]):
            owner["ack"] = None
            self._pair_fail("SOL_MODIFY_ACK_PAYLOAD_UNKNOWN", event.ts_event)
        else:
            owner["ack"] = pending["payload"]
            if self._pair_sol_v2():owner["last_ack_event_id"]=key
            owner.pop("rejected_desired", None)
            self._pair_log("SOL_LATEST_MODIFY_ACK", event.ts_event, order_id=oid,
                sequence=pending["sequence"], native_event_id=key, generation=pending["generation"])
        self._pair_protect(event.ts_event)

    def _pair_sol_boundary(self, label, ns, strict=False):
        """Read-only observation at native matching barriers, no pumping/mutation."""
        if not self._mr_enabled():return super()._pair_sol_boundary(label,ns,strict)
        if not self._pair:return
        p=self._pair;held=self._pair_qty(self.config.sol_id)
        if self._pair_sol_v2():self._pair_sol_retire_check(ns)
        rows=[];exact=True;expected={};retiring=[]
        if held and p["p0"] is not None:
            inst=self.cache.instrument(self.config.sol_id)
            prices,stop=sol_prices(p["p0"],p["atr"],-p["side"],inst.price_increment.as_decimal())
            expected={("TP",level):(D(count)*inst.size_increment.as_decimal(),prices[level],None)
                for level,count in p["tp_lots"].items()if count>0}
            expected[("STOP",None)]=(held,None,stop)
        work=self._pair_work(instrument=self.config.sol_id,kinds={"TP","STOP"})
        for oid,owner,order in work:
            if self._pair_sol_v2()and owner.get("retiring"):
                self._pair_sol_retire_observe(oid,owner,ns)
                retiring.append(dict(order_id=oid,original_right=str(owner["retiring"]["native_right"]),actual_filled=str(owner["retiring"]["actual_filled"]),native_leaves=str(order.leaves_qty),terminal_event_id=owner["retiring"]["terminal_event_id"]))
                continue
            target=expected.get((owner["kind"],owner["level"]))
            matches=(order is not None and target is not None and owner.get("parent")==p["parent"]
                and order.strategy_id==self.id and order.instrument_id==self.config.sol_id and order.is_reduce_only
                and order.side==(OrderSide.BUY if p["side"]==1 else OrderSide.SELL)and owner["accepted"] and owner.get("pending")is None
                and order.status.name in {"ACCEPTED","PARTIALLY_FILLED","TRIGGERED"}
                and order.leaves_qty.as_decimal()==target[0]
                and (not self._pair_sol_v2()or self._pair_sol_ack_known(order,owner))
                and self._pair_sol_payload_matches(order,(order.filled_qty.as_decimal()+target[0],target[1],target[2])))
            exact=exact and matches
            rows.append(dict(order_id=oid,kind=owner["kind"],level=owner["level"],exact=matches,
                status="UNKNOWN"if order is None else order.status.name,
                leaves="UNKNOWN"if order is None else str(order.leaves_qty),
                total="UNKNOWN"if order is None else str(order.quantity),
                filled="UNKNOWN"if order is None else str(order.filled_qty),
                price="UNKNOWN"if order is None else str(getattr(order,"price",None)),
                trigger="UNKNOWN"if order is None else str(getattr(order,"trigger_price",None)),
                desired="UNKNOWN"if target is None else [str(v)for v in target],
                desired_generation=p["generation"],pending=owner.get("pending")is not None))
        exact=exact and len(work)-len(retiring)==len(expected)and sum(p["tp_lots"].values())*self.cache.instrument(self.config.sol_id).size_increment.as_decimal()==held
        pending_commands=any(o.get("pending")is not None and o.get("parent")==p["parent"]for o in self._pair_orders.values())
        fault=self._pair_sol_v2()and (p.get("failed")or p.get("stop_filled")and held)
        state="FAULT_UNPROTECTED"if fault else"CLOSING_PROTECTED"if self._pair_sol_v2()and p["close_sol"]and held and exact else"CLOSING"if p["close_sol"]and not self._pair_sol_v2()else"DRAINING"if not held and (work or pending_commands) else"FLAT"if not held else"PROTECTED"if exact else"UNKNOWN"
        counts=getattr(self,"_pair_sol_boundary_counts",None)
        if counts is None:self._pair_sol_boundary_counts=counts=dict(checks=0,strict=0,unknown=0)
        counts["checks"]+=1;counts["strict"]+=int(strict);counts["unknown"]+=int(held and not p["close_sol"]and not exact)
        signature=repr((held,state,exact,rows,p["protection_since"]))
        detailed=bool(getattr(getattr(self.config,"research_native_book",None),"detailed",False))
        if detailed or signature!=p.get("sol_boundary_signature"):
            self._pair_log("SOL_NATIVE_BOUNDARY",ns,label=label,parent=p["parent"],actual_sol=held,
                state=state,exact=exact,orders=rows,retiring=retiring,protection_since=p["protection_since"])
            p["sol_boundary_signature"]=signature
        if strict and held and not exact and (not fault if self._pair_sol_v2()else not p["close_sol"]):
            raise ValueError("SOL_BEFORE_MATCHING_EXACT_COVERAGE_UNKNOWN")

    def _mr_liability_rows(self,ns,exclude=None,proposed=None):
        orders={str(o.client_order_id):o for o in self.cache.orders_open()+self.cache.orders_inflight() if str(o.client_order_id)!=exclude}
        if proposed is not None:orders[str(proposed.client_order_id)]=proposed
        rows=[]
        for oid,order in orders.items():
            if order.is_closed:continue
            owner=self._pair_orders.get(oid,{})
            command=self._ma_commands.get(oid)
            pending=owner.get('pending')
            leaves=order.leaves_qty.as_decimal()
            if pending:leaves=max(leaves,pending['payload'][0]-order.filled_qty.as_decimal())
            if command:leaves=max(leaves,command['total']-order.filled_qty.as_decimal())
            latest=order.events[-1]
            rows.append(dict(order_id=oid,leg='BTC' if order.instrument_id==self.config.btc_id else 'SOL',side=1 if order.side==OrderSide.BUY else -1,
                reduce_only=order.is_reduce_only,native_lot=str(self.cache.instrument(order.instrument_id).size_increment),max_native_leaves=str(leaves),native_status=order.status.name,
                native_filled=str(order.filled_qty),latest_native_event_id=str(latest.id),latest_native_event_type=type(latest).__name__,
                old_new_generation=dict(generation=owner.get('generation'),native_total=str(order.quantity),pending_payload=None if pending is None else pending['payload'],ma_command=command,last_ack_event_id=owner.get('last_ack_event_id'),ack_payload=owner.get('ack'),accepted=owner.get('accepted',False)),
                retiring=owner.get('retiring'),pending_hedge_credit='0'))
        return wire(rows)

    def _tier_allows_increase(self,instrument_id,side,quantity,ts_now):
        if not self._mr_enabled():return super()._tier_allows_increase(instrument_id,side,quantity,ts_now)
        allowed=super()._tier_allows_increase(instrument_id,side,quantity,ts_now)
        self._mr_log('NATIVE_STOCK_GUARD_RESULT',ts_now,instrument=str(instrument_id),side=getattr(side,'name',str(side)),quantity=str(quantity),allowed=allowed)
        return allowed


    def _mr_recovery_ready(self,instrument,ns):
        """Same sole-reduction blockers as the frozen SOL reduction helper.

        Positive TP/STOP remain live; ENTRY, existing reduction, retiring or
        foreign ownership blocks. No new OMS, cancellation of positive
        protection, or optimistic unknown ACK is introduced.
        """
        if instrument==self.config.btc_id:
            return not self._pair_work(instrument=instrument,kinds={'BTC_DEBT'})
        p=self._pair
        if p is None or p.get('failed') or p.get('stop_filled'):return False
        entries=self._pair_work(instrument=self.config.sol_id,kinds={'ENTRY'})
        if any(order is None or owner.get('parent')!=p['parent'] or order.strategy_id!=self.id or order.is_reduce_only
            or order.side!=(OrderSide.SELL if p['side']==1 else OrderSide.BUY) for oid,owner,order in entries):return False
        if self._pair_cancel(entries):return False
        if self._pair_work(instrument=self.config.sol_id,kinds={'SOL_CAP','SOL_CLOSE'}) or self._pair_sol_retire_busy():return False
        for order in self.cache.orders_open()+self.cache.orders_inflight():
            if order.instrument_id==self.config.sol_id:
                owner=self._pair_orders.get(str(order.client_order_id))
                if not owner or owner.get('parent')!=p['parent'] or order.strategy_id!=self.id or owner['kind'] not in {'TP','STOP'}:return False
        self._pair_sol_protect(ns)
        if p.get('failed') or p.get('protection_since') is not None:return False
        return all(self._pair_sol_positive(order,exact=True) for oid,owner,order in self._pair_work(instrument=self.config.sol_id,kinds={'TP','STOP'}))


    def _mr_entry_decision(self,status,reason,instrument,side,qty,ns,oid=None):
        decision=EntrySubmissionDecision(status,reason,self._pair['parent'] if self._pair else None,str(instrument),side,str(qty),self._mr_last_snapshot,oid)
        if status=='DENY' and not self._mr_allocated and self._pair:
            self._pair.update(entry_sent=False,entry_terminal=True,entry_band=None)
        self._mr_log('ENTRY_SUBMISSION_DECISION',ns,decision=asdict(decision),allocation_used=self._mr_allocated,pending_hedge_credit='0',original_second=self._mr_original_second())
        return decision

    def _mr_submit_entry(self,instrument,side,qty,ns):
        """Known economic denial is not a durable/transport failure.

        Use the same native MARKET/IOC factory, ownership fields and durable
        checkpoint as the frozen paired helper. No order/allocation is created
        for a known preflight DENY. An initialized CID earns no hedge credit.
        """
        if self._mr_allocated:
            return self._mr_entry_decision('DENY','ALLOCATION_ALREADY_USED',instrument,side,qty,ns)
        try:
            state,feature=self._mr_snapshot(ns)
            if self._pair is None or instrument!=self.config.sol_id or side not in (-1,1):raise ValueError('UNKNOWN_ENTRY_OWNER')
            lot=self._pair['caps'].sol_lot
            if qty<=0 or exact_lots(qty,lot)==0:
                return self._mr_entry_decision('DENY','ZERO_NATIVE_TARGET',instrument,side,qty,ns)
            useful,benefit,cost=useful_hedge(state,feature,qty)
            if not useful:return self._mr_entry_decision('DENY','FULL_TARGET_BENEFIT_HURDLE',instrument,side,qty,ns)
            # A false existing guard grants no permission. Current account,
            # ownership, marks and zero-shock getter equality were established
            # by the strict snapshot; prospective denial leaves BTC policy live.
            if not self._tier_allows_increase(instrument,OrderSide.BUY if side==1 else OrderSide.SELL,qty,ns):
                return self._mr_entry_decision('DENY','CURRENT_NATIVE_STOCK_GUARD',instrument,side,qty,ns)
            proposal=Liability('LOCAL_ENTRY_PROPOSAL_NOT_A_NATIVE_CID','SOL',side,exact_lots(qty,lot),lot,False,state.ps*(TAKER+RESERVE))
            envelope=self._mr_envelope(state,feature,self._mr_liabilities(ns,proposal))
            if not envelope.safe:return self._mr_entry_decision('DENY','JOINT_EXECUTION_ENVELOPE',instrument,side,qty,ns)
            quote=self.cache.quote_tick(instrument)
            if quote is None or not 0<=ns-quote.ts_event<=MINUTE:raise ValueError('UNKNOWN_SUBMIT_QUOTE')
            inst=self.cache.instrument(instrument)
            executable=quote.bid_price.as_decimal() if side<0 else quote.ask_price.as_decimal()
            if (inst.min_quantity and qty<inst.min_quantity.as_decimal()) or (inst.min_notional and qty*executable<inst.min_notional.as_decimal()):
                return self._mr_entry_decision('DENY','NATIVE_ENTRY_MINIMUM',instrument,side,qty,ns)
            try:self._pair_valid_allocations(qty,state.ps)
            except ValueError as error:
                if str(error)=='PAIRED_INVALID_NATIVE_TP_OR_STOP_ALLOCATION':
                    return self._mr_entry_decision('DENY','PLANNED_TP_STOP_MINIMUM',instrument,side,qty,ns)
                raise
            order=self.order_factory.market(instrument_id=instrument,order_side=OrderSide.BUY if side==1 else OrderSide.SELL,
                quantity=inst.make_qty(qty),reduce_only=False,time_in_force=TimeInForce.IOC)
            if order.quantity.as_decimal()!=qty:raise ValueError('UNKNOWN_NATIVE_WIRE_QUANTITY')
            oid=str(order.client_order_id);p=self._pair
            self._pair_orders[oid]=dict(instrument=instrument,kind='ENTRY',level=None,accepted=False,generation=p['generation'],submit_ns=ns,parent=p['parent'],initial_oid=oid,initialized_event_id=str(order.init_event.id),pending=None,ack=None,command_sequence=0)
            if not self._record_submission(order,'paired:'+oid,p['parent'],'PAIRED_ENTRY','PAIRED_ENTRY',None):
                decision=self._mr_submission_results.get(oid)
                if decision is not None and decision.status=='DENY':
                    # The command has not reached submit_order. Only initialized,
                    # absent-from-cache local metadata may be removed here.
                    if self.cache.order(order.client_order_id) is not None or order.status.name!='INITIALIZED':raise ValueError('UNKNOWN_UNSENT_ORDER_OWNERSHIP')
                    self._pair_orders.pop(oid)
                    return self._mr_entry_decision('DENY',decision.reason,instrument,side,qty,ns,oid)
                if decision is None:raise ValueError('UNKNOWN_DURABLE_SUBMISSION_RESULT')
                return decision  # UNKNOWN/transport failure already failed closed.
            self._mr_allocated=True;self._mr_last_episode_day=feature.end_ns
            p['entry_sent']=True;p['entry_terminal']=False;p['allocation_order_id']=oid
            self._pair_log('SUBMIT',ns,order_id=oid,kind='ENTRY',level=None,quantity=qty,price=None,stop=None,generation=p['generation'])
            decision=self._mr_entry_decision('ALLOW','NATIVE_ENTRY_ISSUED',instrument,side,qty,ns,oid)
            try:self.submit_order(order)
            except Exception as error:
                # The native command may already be registered/inflight. Retain
                # owner/allocation, grant no fill credit, and fail closed.
                decision=self._mr_entry_decision('UNKNOWN','NATIVE_TRANSPORT_EXCEPTION:'+type(error).__name__+':'+str(error),instrument,side,qty,ns,oid)
                self._mr_submission_results[oid]=decision;self._mr_fail(decision.reason,ns)
            return decision
        except (ValueError,KeyError,TypeError) as error:
            decision=self._mr_entry_decision('UNKNOWN',str(error),instrument,side,qty,ns)
            self._mr_fail(str(error),ns)
            return decision
