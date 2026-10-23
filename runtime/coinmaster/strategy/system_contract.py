"""Explicit research child policy; observes native receipts without changing them."""
from decimal import Decimal as D

CHILD_CAP = D("1000")
DAY=86_400_000_000_000
MINUTE=60_000_000_000


def add_budget_quantity(requested, step, *, equity, high_water, btc_reserve,
                        held_sol, pending_sol, pending_entry_fees,
                        sol_atr, sol_mark, sol_fee, executable):
    """Fixed gross-direction stress, all costs USD; result SOL rounded down.

    post(q)=E-R_B-F_pending-(held+pending)*c-q*(entry_fee_per_SOL+c),
    c=ATR_SOL+f_SOL*(mark_SOL+ATR_SOL). Nonnegative constant coefficients
    make post nonincreasing in q, so the lot-floored closed form is maximal.
    Entry fees concern only unbooked openings; c includes stressed exit fee.
    """
    values=(requested,step,equity,high_water,btc_reserve,held_sol,pending_sol,
            pending_entry_fees,sol_atr,sol_mark,sol_fee,executable)
    if any(not v.is_finite() or v<0 for v in values) or step<=0 or equity<=0 or high_water<=0 or sol_mark<=0 or executable<=0:
        raise ValueError("INVALID_ADD_BUDGET_UNITS_OR_STATE")
    stress=sol_atr+sol_fee*(sol_mark+sol_atr)
    coefficient=stress+sol_fee*executable
    if coefficient<=0:
        raise ValueError("UNDEFINED_ZERO_STRESS_COEFFICIENT")
    available=equity-D('.55')*high_water-btc_reserve-pending_entry_fees-(held_sol+pending_sol)*stress
    allowed=min(requested,max(D(0),available)/coefficient)
    return (allowed//step)*step


def q90(values):
    if not values or any(not v.is_finite() or v<0 for v in values):
        raise ValueError("INVALID_COMPLETED_LABELS")
    ordered=sorted(values);position=D(len(ordered)-1)*D('.9');lo=int(position)
    return ordered[lo]+(ordered[min(lo+1,len(ordered)-1)]-ordered[lo])*(position-lo)


def repeat_sizing(labels, decision_ns, repeated):
    valid=[];invalid=0
    for item in labels:
        if item.get('status')!='VALID':continue
        ready=item.get('label_ready_at')
        if not isinstance(ready,int):invalid+=1;continue
        if ready>=decision_ns:continue
        try:
            value=D(item['u'])
            if not value.is_finite() or value<0:raise ValueError('INVALID_U')
        except (ValueError,ArithmeticError,TypeError):invalid+=1;continue
        valid.append(item)
    groups=[[D(x['u']) for x in valid if x['repeated']==group] for group in (False,True)]
    counts=[len(v) for v in groups];waves=[len({x['wave_id'] for x in valid if x['repeated']==group}) for group in (False,True)]
    quantiles=[q90(v) if v else None for v in groups]
    reason='FIRST_ENTRY' if not repeated else 'INVALID_COMPLETED_LABEL' if invalid else 'INSUFFICIENT_COMPLETED_GROUPS' if min(counts)<8 else 'ZERO_REPEAT_Q90' if not quantiles[1] else 'CAUSAL_Q90_RATIO'
    k=min(D(1),quantiles[0]/quantiles[1]) if reason=='CAUSAL_Q90_RATIO' else D(1)
    return dict(k=str(k),fallback=reason,n_first=counts[0],n_repeat=counts[1],
                waves_first=waves[0],waves_repeat=waves[1],invalid_labels=invalid,
                q90_first=str(quantiles[0]) if quantiles[0] is not None else None,
                q90_repeat=str(quantiles[1]) if quantiles[1] is not None else None)


def child_quantity(intended, step):
    if not intended.is_finite() or not step.is_finite() or intended < 0 or step <= 0:
        raise ValueError("INVALID_EXPLICIT_CHILD_QUANTITY")
    return (min(intended, CHILD_CAP) // step) * step


class SystemContractResearch:
    def _sc_init(self):
        self.system_contract_audit = []
        self._sc_attempts = {}
        self._sc_orders = {}
        self._sc_seen_events = set()
        self._sc_active=bool(self.config.research_sol_explicit_child or self.config.research_sol_add_budget or self.config.research_btc_repeat_sizing)
        if (self.config.research_sol_add_budget or self.config.research_btc_repeat_sizing) and not self.config.research_sol_explicit_child:
            raise ValueError("SYSTEM_RISK_REQUIRES_EXPLICIT_CHILD_CONTROL")
        if self.config.research_btc_repeat_sizing and not self.config.research_v0_deferred_selective_zero_tp:
            raise ValueError("REPEAT_SIZING_REQUIRES_PRE_ZERO_TP_Q0_HOOK")
        self._sc_peak=D(str(self.config.active_seed))
        self._sc_order_prices={}
        self._sc_atr_cache=None
        self._sc_ohlc={self.config.btc_id:{ns:(high,low) for ns,high,low in self.config.research_sc_btc_daily_seed},
                       self.config.sol_id:{ns:(high,low) for ns,high,low in self.config.research_sc_sol_daily_seed}}
        self._sc_wave_side=None
        self._sc_wave_id=None
        self._sc_wave_parents=set()
        self._sc_btc_plans={}
        self._sc_btc_observations={}
        self.sc_btc_labels=[]
        self.sc_btc_decisions=[]
        self.sc_btc_outcomes=[]
        self.sc_sol_budget_audit=[]

    def _sc_sol_quantity(self, intent, intended, step, price, ns):
        if not self.config.research_sol_explicit_child:
            return intended
        allowed = child_quantity(intended, step)
        # The domain has already consumed this level's original D1 attempt.
        # Keep the original notional right and intent unchanged.
        row = dict(event="SOL_ATTEMPT", timestamp_ns=int(ns), intent_id=intent.id,
                   episode_id=intent.episode_id, level=intent.level,
                   decision_index=intent.decision_index,
                   next_attempt_earliest_decision_index=intent.decision_index + 1,
                   next_attempt_condition="ORIGINAL_D1_SIGNAL_RIGHT_AND_ADMISSION",
                   original_remaining_notional=str(intent.requested_notional),
                   intended_quantity=str(intended), allowed_quantity=str(allowed),
                   submitted_quantity="0", filled_quantity="0", filled_notional="0",
                   unused_right_notional=str(intent.requested_notional),
                   executable_price=str(price), native_status="NOT_SUBMITTED")
        self._sc_attempts[intent.id] = row
        self.system_contract_audit.append(row)
        return allowed

    def _sc_bind(self, intent, order):
        row = self._sc_attempts.get(intent.id)
        if row is None:
            return
        row["client_order_id"] = str(order.client_order_id)
        row["submitted_quantity"] = str(order.quantity.as_decimal())
        self._sc_order_prices[str(order.client_order_id)]=D(row["executable_price"])
        self._sc_orders[str(order.client_order_id)] = row

    def _sc_denied(self, intent, reason):
        row = self._sc_attempts.get(intent.id)
        if row is not None:
            row["local_denial"] = reason
            row["native_status"] = "LOCAL_UNSENT"
            row["submitted_quantity"] = "0"

    def _sc_native_event(self, event):
        row = self._sc_orders.get(str(event.client_order_id))
        if row is None:
            return
        identity = str(event.id)
        if identity in self._sc_seen_events:
            return
        self._sc_seen_events.add(identity)
        order = self.cache.order(event.client_order_id)
        if order is not None:
            row["native_status"] = order.status.name
        qty = getattr(event, "last_qty", None)
        if qty is not None:
            price = event.last_px.as_decimal()
            row["filled_quantity"] = str(D(row["filled_quantity"]) + qty.as_decimal())
            row["filled_notional"] = str(D(row["filled_notional"]) + qty.as_decimal() * price)
            row["unused_right_notional"] = str(max(D(0), D(row["original_remaining_notional"]) - D(row["filled_notional"])))
        self.system_contract_audit.append(dict(event=type(event).__name__,
            native_event_id=identity, timestamp_ns=int(event.ts_event),
            client_order_id=str(event.client_order_id),
            native_status=row["native_status"], filled_quantity=row["filled_quantity"],
            unused_right_notional=row["unused_right_notional"],
            commission=str(getattr(event, "commission", "UNKNOWN_NOT_A_FILL"))))


    def _sc_observe_settled(self,equity):
        if self._sc_active and equity.is_finite() and equity>0:
            self._sc_peak=max(self._sc_peak,equity)

    def _sc_daily(self, ns, ready_ns, btc, sol):
        if not self._sc_active:return
        for instrument,bar in ((self.config.btc_id,btc),(self.config.sol_id,sol)):
            self._sc_ohlc[instrument][ns]=(float(bar.high),float(bar.low))
        side=self._current_signals[-1].side
        if side!=self._sc_wave_side:
            if self._sc_wave_id is not None:
                for observation in self._sc_btc_observations.values():
                    if observation['wave_id']!=self._sc_wave_id or observation.get('label_ready_at') is not None:continue
                    complete=observation['last_mark_ns']==ns and observation['mark_count']>0 and not observation['gap']
                    atr=observation['frozen_atr_fraction']
                    valid=complete and atr is not None and atr>0
                    label=dict(parent_id=observation['parent_id'],wave_id=self._sc_wave_id,
                        repeated=observation['repeated'],first_fill_ns=observation['first_fill_ns'],
                        label_reference_price=str(observation['label_reference_price']),
                        frozen_atr_fraction=str(atr) if atr is not None else None,
                        minute_mae=str(observation['mae']),label_ready_at=int(ready_ns),
                        mark_count=observation['mark_count'],status='VALID' if valid else 'INCOMPLETE_MINUTE_MARKS_OR_ATR',
                        u=str(observation['mae']/atr) if valid else None)
                    observation['label_ready_at']=int(ready_ns)
                    self.sc_btc_labels.append(label)
            self._sc_wave_side=side;self._sc_wave_id=str(ns);self._sc_wave_parents=set()

    def _sc_atrs(self):
        ns=self._last_accepted_session
        if self._sc_atr_cache and self._sc_atr_cache[0]==ns:return self._sc_atr_cache[1]
        result=[]
        from math import isfinite
        for instrument,asset in ((self.config.btc_id,'btc'),(self.config.sol_id,'sol')):
            previous=last=None;atr=None;trs=[]
            for row in self._bars:
                stamp=int(row.close_time.timestamp()*1_000_000_000)
                if ns is None or stamp>ns:return None
                close=getattr(row,asset+'_close')
                if previous is not None:
                    hl=self._sc_ohlc[instrument].get(stamp)
                    if hl is None or stamp!=last+DAY:return None
                    high,low=hl
                    if not all(isfinite(v) and v>0 for v in (high,low,close,previous)) or not low<=close<=high:return None
                    tr=max(high-low,abs(high-previous),abs(low-previous))
                    if atr is None:
                        trs.append(tr)
                        if len(trs)==14:atr=sum(trs)/14
                    else:atr=(13*atr+tr)/14
                previous=close;last=stamp
            if last!=ns or atr is None or not isfinite(atr) or atr<=0:return None
            result.append(D(str(atr)))
        self._sc_atr_cache=(ns,tuple(result))
        return tuple(result)

    def _sc_opening_inventory(self,ns):
        ids=(self.config.btc_id,self.config.sol_id)
        held={i:D(0) for i in ids};pending={i:D(0) for i in ids};fees={i:D(0) for i in ids}
        for position in self.cache.positions_open():
            if position.instrument_id in held:held[position.instrument_id]+=position.quantity.as_decimal()
        orders={str(o.client_order_id):o for o in self.cache.orders_open()+self.cache.orders_inflight()}
        for oid,intent in self._pending_by_order.items():
            if intent.action not in ('BTC_ENTRY','SOL_ADD'):continue
            from nautilus_trader.model.identifiers import ClientOrderId
            order=self.cache.order(ClientOrderId(oid))
            if order is None:raise ValueError('UNRESOLVED_OPENING_SUBMISSION')
            if not order.is_closed:orders[oid]=order
        for oid,order in orders.items():
            if order.instrument_id not in held or order.is_reduce_only:continue
            if oid not in self._pending_by_order:raise ValueError('UNKNOWN_OPENING_ORDER_OWNER')
            qty=order.quantity.as_decimal()-order.filled_qty.as_decimal()
            if qty<0:raise ValueError('NEGATIVE_NATIVE_LEAVES')
            instrument=order.instrument_id
            mark=self._latest_marks[instrument].price
            prices=[mark]
            if oid in self._sc_order_prices:prices.append(self._sc_order_prices[oid])
            if hasattr(order,'price'):prices.append(order.price.as_decimal())
            quote=self.cache.quote_tick(instrument)
            if quote is not None:prices.extend((quote.bid_price.as_decimal(),quote.ask_price.as_decimal()))
            price=max(prices)
            pending[instrument]+=qty
            fees[instrument]+=qty*price*self.cache.instrument(instrument).taker_fee
        parent=self._split_parent
        if parent and not parent['closed']:
            unfilled=max(D(0),parent['quantity']-parent['filled'])
            extra=max(D(0),unfilled-pending[self.config.btc_id])
            pending[self.config.btc_id]+=extra
            fees[self.config.btc_id]+=extra*self._latest_marks[self.config.btc_id].price*self.cache.instrument(self.config.btc_id).taker_fee
        return held,pending,fees

    def _sc_budget(self,intent,requested,step,executable,ns):
        if not self.config.research_sol_add_budget:return requested
        row=dict(event='H_SOL_ADD',timestamp_ns=int(ns),intent_id=intent.id,level=intent.level,
                 requested_quantity=str(requested),allowed_quantity='0')
        try:
            ids=(self.config.btc_id,self.config.sol_id)
            if not all(i in self._latest_marks and self._latest_marks[i].ts_event==ns for i in ids):raise ValueError('UNPAIRED_CURRENT_MARKS')
            if self._last_accepted_session is None or not 0<=ns-self._last_accepted_session<=DAY:raise ValueError('STALE_DAILY_STATE')
            atrs=self._sc_atrs()
            if atrs is None:raise ValueError('UNKNOWN_CLOSED_ATR14')
            held,pending,fees=self._sc_opening_inventory(ns)
            equity=self._v3_equity();self._sc_observe_settled(equity)
            ab,ass=atrs;b=self._latest_marks[ids[0]].price;s=self._latest_marks[ids[1]].price
            fb=self.cache.instrument(ids[0]).taker_fee;fs=self.cache.instrument(ids[1]).taker_fee
            reserve=(held[ids[0]]+pending[ids[0]])*(ab+fb*(b+ab))+fees[ids[0]]
            allowed=add_budget_quantity(requested,step,equity=equity,high_water=self._sc_peak,
                btc_reserve=reserve,held_sol=held[ids[1]],pending_sol=pending[ids[1]],pending_entry_fees=fees[ids[1]],
                sol_atr=ass,sol_mark=s,sol_fee=fs,executable=executable)
            row.update(allowed_quantity=str(allowed),equity=str(equity),high_water=str(self._sc_peak),
                btc_reserve=str(reserve),held_btc=str(held[ids[0]]),pending_btc=str(pending[ids[0]]),
                held_sol=str(held[ids[1]]),pending_sol=str(pending[ids[1]]),pending_entry_fees=str(fees[ids[1]]),
                btc_atr=str(ab),sol_atr=str(ass),sol_mark=str(s),sol_fee=str(fs),executable=str(executable),reason='MAX_LOT_FEASIBLE_ADD')
        except (ValueError,KeyError,AttributeError) as error:
            allowed=D(0);row['reason']=str(error)
        self.sc_sol_budget_audit.append(row)
        attempt=self._sc_attempts.get(intent.id)
        if attempt is not None:attempt['allowed_quantity']=str(allowed)
        return allowed

    def _sc_btc_plan(self,intent,tick,wire):
        if not self._sc_active:return D(str(intent.requested_notional))
        if intent.id in self._sc_btc_plans:return D(self._sc_btc_plans[intent.id]['after_k_notional'])
        repeated=bool(self._sc_wave_parents)
        sizing=repeat_sizing(self.sc_btc_labels,tick.ts_event,repeated)
        before=D(str(intent.requested_notional))
        after=before*D(sizing['k']) if self.config.research_btc_repeat_sizing else before
        atrs=self._sc_atrs();atr=atrs[0]/wire if atrs is not None and wire>0 else None
        row=dict(parent_id=intent.id,episode_id=intent.episode_id,decision_ns=int(tick.ts_event),
                 q0_wire_price=str(wire),frozen_atr_fraction=str(atr) if atr is not None else None,
                 frozen_daily_ns=self._last_accepted_session,wave_id=self._sc_wave_id,
                 repeated=repeated,before_k_notional=str(before),after_k_notional=str(after),
                 applied=bool(self.config.research_btc_repeat_sizing),side=intent.side,**sizing)
        row['held_inventory']=[dict(instrument=str(p.instrument_id),quantity=str(p.quantity)) for p in self.cache.positions_open()]
        row['pending_order_ids']=sorted(self._pending_by_order)
        try:row['decision_native_equity']=str(self._v3_equity())
        except (ValueError,KeyError,AttributeError):row['decision_native_equity']='UNKNOWN_NATIVE_MARK_STATE'
        feature=self._current_signals[-1] if self._current_signals else None
        row['closed_features']=dict(side=feature.side,beta=feature.beta,relative=feature.relative,
            mu=feature.mu,sigma=feature.sigma,z=feature.z) if feature is not None else None
        row['daily_index']=len(self._bars)-1
        row['original_ema_e4_gate']='PASSED_EXISTING_ADMISSION_TO_Q0'
        row['future_label_is_feature']=False
        row['available_prefix_snapshot']=self._sc_prefix_snapshot(tick.ts_event,atrs)
        self._sc_btc_plans[intent.id]=row;self.sc_btc_decisions.append(row)
        return after

    def _sc_btc_fill(self,intent,event):
        if not self._sc_active or intent.action!='BTC_ENTRY':return
        if intent.id not in self._sc_btc_observations:
            plan=self._sc_btc_plans.get(intent.id)
            repeated=bool(self._sc_wave_parents)
            self._sc_wave_parents.add(intent.id)
            atr=D(plan['frozen_atr_fraction']) if plan and plan['frozen_atr_fraction'] is not None else None
            self._sc_btc_observations[intent.id]=dict(parent_id=intent.id,wave_id=self._sc_wave_id,
                repeated=repeated,first_fill_ns=int(event.ts_event),label_reference_price=event.last_px.as_decimal(),
                frozen_atr_fraction=atr,side=intent.side,mae=D(0),mark_count=0,
                last_mark_ns=(event.ts_event//MINUTE)*MINUTE,gap=False,label_ready_at=None)
            if plan is not None:
                plan.update(label_reference_price=str(event.last_px.as_decimal()),first_fill_ns=int(event.ts_event),actual_repeated=repeated)

    def _sc_mark(self,mark):
        if not self._sc_active or mark.instrument_id!=self.config.btc_id:return
        for observation in self._sc_btc_observations.values():
            if observation['label_ready_at'] is not None or mark.ts_event<=observation['first_fill_ns']:continue
            if mark.ts_event<=observation['last_mark_ns']:continue
            if mark.ts_event!=observation['last_mark_ns']+MINUTE:observation['gap']=True
            adverse=max(D(0),-D(observation['side'])*(mark.price/observation['label_reference_price']-1))
            observation['mae']=max(observation['mae'],adverse)
            observation['last_mark_ns']=mark.ts_event;observation['mark_count']+=1


    def _sc_labels_report(self):
        censored=[dict(parent_id=o['parent_id'],wave_id=o['wave_id'],repeated=o['repeated'],
                    first_fill_ns=o['first_fill_ns'],label_reference_price=str(o['label_reference_price']),
                    frozen_atr_fraction=str(o['frozen_atr_fraction']) if o['frozen_atr_fraction'] is not None else None,
                    minute_mae=str(o['mae']),mark_count=o['mark_count'],label_ready_at=None,
                    status='CENSORED_UNFINISHED_WAVE',u=None)
                  for o in self._sc_btc_observations.values() if o['label_ready_at'] is None]
        return self.sc_btc_labels+censored


    def _sc_btc_outcome(self,intent,event):
        if not self._sc_active or intent.action not in ('BTC_ENTRY','BTC_REDUCE'):return
        episode=self._domain.episode
        self.sc_btc_outcomes.append(dict(episode_id=intent.episode_id,parent_intent_id=intent.id,
            timestamp_ns=int(event.ts_event),action=intent.action,native_quantity=str(event.last_qty.as_decimal()),
            native_price=str(event.last_px.as_decimal()),native_commission=str(event.commission),
            h=str(episode.h) if episode is not None else None,
            management_planref=str(episode.btc_planref_vwap) if episode is not None and episode.btc_planref_vwap is not None else None,
            actual_blended_btc_vwap=str(episode.btc_entry_vwap) if episode is not None else None,
            btc_gross_reference_quantity=str(episode.btc_reference_qty) if episode is not None else None,
            btc_remaining_quantity=str(episode.btc_open_qty) if episode is not None else None,
            sol_right_fraction=dict(episode.sol_right_fraction) if episode is not None else None,
            sol_consumed_notional=dict(episode.sol_add_filled_notional) if episode is not None else None))


    def _sc_prefix_snapshot(self,ns,atrs):
        """Read-only q0 evidence; no gate evaluation or admission mutation."""
        positions=[dict(instrument=str(p.instrument_id),side='LONG' if p.is_long else 'SHORT',
                        quantity=str(p.quantity.as_decimal()),average_open_price=str(p.avg_px_open))
                   for p in self.cache.positions_open()]
        orders={str(o.client_order_id):o for o in self.cache.orders_open()+self.cache.orders_inflight()}
        from nautilus_trader.model.identifiers import ClientOrderId
        unknown=[]
        for oid in self._pending_by_order:
            order=self.cache.order(ClientOrderId(oid))
            if order is None:unknown.append(oid)
            elif not order.is_closed:orders[oid]=order
        opening=[dict(client_order_id=oid,instrument=str(o.instrument_id),side=o.side.name,
                      native_status=o.status.name,reduce_only=bool(o.is_reduce_only),
                      quantity=str(o.quantity.as_decimal()),filled_quantity=str(o.filled_qty.as_decimal()),
                      leaves_quantity=str(o.quantity.as_decimal()-o.filled_qty.as_decimal()),
                      limit_price=str(o.price.as_decimal()) if hasattr(o,'price') else None,
                      owned_intent_id=self._pending_by_order[oid].id if oid in self._pending_by_order else None)
                 for oid,o in sorted(orders.items())]
        ema=None;alpha=2/(self._candidate.ema_period+1)
        closed=[bar for bar in self._bars if int(bar.close_time.timestamp()*1_000_000_000)<=self._last_accepted_session] if self._last_accepted_session is not None else []
        for bar in closed:ema=bar.btc_close if ema is None else alpha*bar.btc_close+(1-alpha)*ema
        side=self._current_signals[-1].side if self._current_signals else None
        age=0
        for feature in reversed(self._current_signals[:len(closed)]):
            if feature.side!=side:break
            age+=1
        atr=atrs[0] if atrs is not None else None
        close=D(str(closed[-1].btc_close)) if closed else None
        distance=close-D(str(ema)) if close is not None and ema is not None else None
        available=dict(timestamp_ns=int(ns),positions=positions,native_open_orders=opening,
            unresolved_submission_ids=sorted(unknown),closed_daily_ns=self._last_accepted_session,
            closed_btc_atr14_price=str(atr) if atr is not None else None,
            closed_btc_ema=str(ema) if ema is not None else None,
            close_minus_ema_price=str(distance) if distance is not None else None,
            signed_ema_distance_atr=str(D(side)*distance/atr) if side is not None and distance is not None and atr is not None and atr>0 else None,
            current_ema_wave_closed_bar_count=age if closed else None,
            gate_witness=dict(status='PASSED_TO_Q0_NOT_FULL_INTERNAL_GATE_VECTOR',
                reentry_band=str(self.config.research_regime_reentry_band) if self.config.research_regime_reentry_band is not None else None,
                wait_regime=bool(self._hb_wait_regime),closed_wait_count=self._next_count,
                e4_release=dict(self._next_release) if self._next_release is not None else None))
        account=self.cache.account_for_venue(self.config.btc_id.venue)
        available['native_account_free_margin']=str(self._free_margin_for_increase(account)) if account is not None else None
        return available
