"""Default-OFF whole-position SOL scenario budget; native ownership/execution only."""
from decimal import Decimal as D, ROUND_FLOOR, ROUND_CEILING
from math import log, expm1, isfinite
from nautilus_trader.model.identifiers import ClientOrderId
from nautilus_trader.model.enums import BarAggregation, OrderSide
from coinmaster.domain.wave_overlay import linear_quantile

DAY=86_400_000_000_000


class AlphaCushionResearch:
    def _alpha_init(self):
        self.alpha_cushion_audit=[]
        self.alpha_cushion_counts={}
        self._alpha_sampled_rows=0
        self._alpha_audit_dropped=0
        self._alpha_observer_samples=0
        self._alpha_peak_updates=0
        self._alpha_peak_decreases=0
        self._alpha_peak=D(str(self.config.active_seed))
        self._alpha_equity=None
        self._alpha_cycle=None
        self._alpha_bar_previous=None
        self._alpha_reverse=None
        self._alpha_last_audit=None

    def _alpha_enabled(self):
        return self.config.research_alpha_cushion

    def _alpha_emit(self,event,ts,**values):
        def safe(v):
            if isinstance(v,D):return str(v)
            if isinstance(v,dict):return {str(k):safe(x) for k,x in v.items()}
            if isinstance(v,(list,tuple)):return [safe(x) for x in v]
            return v
        self.alpha_cushion_counts[event]=self.alpha_cushion_counts.get(event,0)+1
        if event not in {"BETA_FREEZE","DAILY_STRESS"}:
            if self._alpha_sampled_rows>=4096:
                self._alpha_audit_dropped+=1
                return
            self._alpha_sampled_rows+=1
        self.alpha_cushion_audit.append(safe(dict(event=event,timestamp_ns=ts,**values)))

    def _alpha_observe_equity(self,equity,ts):
        if not self._alpha_enabled():return
        old=self._alpha_peak
        self._alpha_peak=max(self._alpha_peak,equity)
        self._alpha_observer_samples+=1
        self._alpha_peak_updates+=self._alpha_peak>old
        self._alpha_peak_decreases+=self._alpha_peak<old
        self._alpha_equity=(equity,ts)

    def _alpha_history(self,ts):
        rows=[b for b in self._bars if int(b.close_time.timestamp()*1e9)<=ts and int(b.available_at.timestamp()*1e9)<=ts][-91:]
        if len(rows)!=91:return None
        times=[int(b.close_time.timestamp()*1e9) for b in rows]
        if any(b-a!=DAY for a,b in zip(times,times[1:])) or not 0<=ts-times[-1]<=DAY:return None
        try:
            x=[log(b.btc_close/a.btc_close) for a,b in zip(rows,rows[1:])]
            y=[log(b.sol_close/a.sol_close) for a,b in zip(rows,rows[1:])]
        except (ValueError,ZeroDivisionError):return None
        if not all(isfinite(v) for v in x+y):return None
        return x,y,times[-1]

    def _alpha_btc_fill(self,intent,ts):
        if not self._alpha_enabled() or intent.action!='BTC_ENTRY':return
        ep=self._domain.episode
        if ep is None or self._alpha_cycle and self._alpha_cycle['episode_id']==ep.id:return
        history=self._alpha_history(ts);beta=None
        if history:
            x,y,_=history;mx,my=sum(x)/90,sum(y)/90
            var=sum((v-mx)**2 for v in x)
            cov=sum((a-mx)*(b-my) for a,b in zip(x,y))
            if var>0 and cov>0 and isfinite(cov/var):beta=D(str(cov/var))
        self._alpha_cycle=dict(episode_id=ep.id,beta=beta,beta_ns=ts,stress_ns=None,a=None,u=None,
            target=None,risk=False,last_increase_ns=ts,btc_qty=None,release_used=None)
        self._alpha_emit('BETA_FREEZE',ts,episode_id=ep.id,beta=beta,returns=90 if history else 0,
            daily_close_ns=history[2] if history else None,valid=beta is not None,global_peak=self._alpha_peak)

    def _alpha_coefficients(self,ts):
        f=self._alpha_cycle
        if f is None or f['beta'] is None:return None
        if f['stress_ns'] is not None and ts//DAY==f['stress_ns']//DAY:return f
        history=self._alpha_history(ts)
        if history is None:return None
        x,y,closed=history
        if f['stress_ns']!=closed:
            beta=float(f['beta'])
            f.update(stress_ns=closed,a=D(str(expm1(linear_quantile([abs(v) for v in x],.95)))),
                u=D(str(expm1(linear_quantile([abs(b-beta*a) for a,b in zip(x,y)],.95)))))
            self._alpha_emit('DAILY_STRESS',ts,beta=f['beta'],a=f['a'],u=f['u'],daily_close_ns=closed,returns=90)
        return f

    def _alpha_bar(self,bar):
        if not self._alpha_enabled() or bar.bar_type.instrument_id!=self.config.sol_id:return
        if bar.bar_type.spec.aggregation!=BarAggregation.MINUTE or bar.bar_type.spec.step!=15:return
        old=self._alpha_bar_previous;ts=bar.ts_event
        if ts>self.clock.timestamp_ns():return
        if old and ts<=old[0]:return
        ep=self._domain.episode
        if old and ep:
            # Reverse of protective SOL: same direction as the current BTC.
            if (ep.side==1 and D(str(bar.close))>old[1]) or (ep.side==-1 and D(str(bar.close))<old[2]):
                self._alpha_reverse=(ts,self.clock.timestamp_ns())
        self._alpha_bar_previous=(ts,D(str(bar.high)),D(str(bar.low)))

    def _alpha_ready(self,ts):
        if not self._alpha_enabled():return True
        if self._alpha_coefficients(ts) is None or self._alpha_equity is None:return False
        return (0<=ts-self._alpha_equity[1]<=self.config.max_mark_age_ns
            and any(p.instrument_id==self.config.btc_id for p in self.cache.positions_open()))

    def _alpha_pending(self,held):
        low=high=held;rows=[];unknown=False
        for oid,i in self._pending_by_order.items():
            if not i.action.startswith('SOL'):continue
            o=self.cache.order(ClientOrderId(oid))
            if o is None:
                unknown=True;rows.append(dict(order_id=oid,status='UNKNOWN_ACK',intent=i.id));continue
            if o.is_closed:continue
            q=o.leaves_qty.as_decimal();rows.append(dict(order_id=oid,status=str(o.status),leaves=q,intent=i.id))
            if i.action=='SOL_ADD':high+=q
            else:low=max(D(0),low-q)
        return low,high,unknown,rows

    def _alpha_cost(self,target,held,bqty,bm,sm):
        # Known remaining execution costs WITHIN the pinned native quote proxy.
        # Historical funding is already cash; unknown future funding/L2 is not labelled zero.
        btc=self.cache.instrument(self.config.btc_id);sol=self.cache.instrument(self.config.sol_id)
        p=self._split_parent;remaining=D(0)
        if p and not p['closed']:remaining=max(D(0),p['quantity']-p['filled']-p['cancelled'])
        _,high,_,_=self._alpha_pending(held)
        pending=max(D(0),high-held)
        return ((bqty+2*remaining)*bm*D(str(btc.taker_fee))
            +(abs(target-held)+target+pending)*sm*D(str(sol.taker_fee))),remaining

    def _alpha_L(self,NS,NB,cost):
        f=self._alpha_cycle
        return abs(NB-f['beta']*NS)*f['a']+abs(NS)*f['u']+cost

    def _alpha_margin(self,target,held,ts):
        if target<=held:return True  # Native reductions do not require new margin.
        ep=self._domain.episode
        return self._entries_enabled() and self._tier_allows_increase(self.config.sol_id,
            OrderSide.BUY if ep.side==-1 else OrderSide.SELL,target-held,ts)

    def _alpha_release_ready(self,ts,L,C):
        f=self._alpha_cycle;r=self._alpha_reverse
        return bool(r and r[0]>f['last_increase_ns'] and r[1]<ts and r!=f['release_used'] and L<=D('.8')*C)

    def _alpha_admit(self,qty,price,ts):
        if not self._alpha_enabled():return True
        if not self._alpha_ready(ts):return False
        held=next((p.quantity.as_decimal() for p in self.cache.positions_open() if p.instrument_id==self.config.sol_id),D(0))
        if self._alpha_pending(held)[2]:return False
        f=self._alpha_cycle
        if not f['risk']:return True
        c=self._conditional_state(ts)
        positions={p.instrument_id:p for p in self.cache.positions_open()}
        btc=positions.get(self.config.btc_id);sol=positions.get(self.config.sol_id)
        held=sol.quantity.as_decimal() if sol else D(0)
        marks=self._latest_marks
        if any(i not in marks or not 0<=ts-marks[i].ts_event<=self.config.max_mark_age_ns for i in (self.config.btc_id,self.config.sol_id)):return False
        target=c['original_target']+qty;bm=marks[self.config.btc_id].price;sm=marks[self.config.sol_id].price
        cost,_=self._alpha_cost(target,held,btc.quantity.as_decimal(),bm,sm)
        L=self._alpha_L(target*sm,btc.quantity.as_decimal()*bm,cost)
        C=max(D(0),self._alpha_equity[0]-D('.55')*self._alpha_peak)
        if not self._alpha_release_ready(ts,L,C):return False
        self._alpha_emit('RESTORE_AUTHORIZED',ts,target=target,L=L,C=C,bar_close_ns=self._alpha_reverse[0])
        return True

    def _alpha_risk_cancel(self,c,intent,ts):
        # Reuse the existing physical-attempt -> original-task snapshot.
        # Late native fills reduce task.remaining before terminal retirement.
        if intent.id in c['original_attempts']:
            c.setdefault('alpha_risk_cancels',set()).add(intent.id)
            self._alpha_emit('RISK_CANCEL_REQUEST',ts,physical_intent=intent.id,
                original_attempt_ids=list(c['original_attempts'][intent.id]))

    def _alpha_terminal_retirement(self,c,intent,task,ts):
        if intent.id not in c.get('alpha_risk_cancels',()):return
        q=task['remaining'];level=task['intent'].level
        if q<=0 or level is None:return
        ep=self._domain.episode;credit=q*task['price']
        ep.sol_risk_retired_notional[level]=ep.sol_risk_retired_notional.get(level,0)+float(credit)
        self._alpha_emit('RETIRE_RISK_CANCELED_AUTHORITY',ts,physical_intent=intent.id,
            original_intent=task['intent'].id,level=level,quantity=q,authorization_notional=credit,native_fill=False)

    def _alpha_retire(self,c,target,ts):
        ep=self._domain.episode;excess=max(D(0),c['original_target']-target)
        for task in c['adds']:
            if excess<=0:break
            q=min(excess,task['remaining']);task['remaining']-=q;c['original_target']-=q;excess-=q
            if q and task['intent'].level is not None:
                level=task['intent'].level;credit=q*task['price']
                ep.sol_risk_retired_notional[level]=ep.sol_risk_retired_notional.get(level,0)+float(credit)
                self._alpha_emit('RETIRE_UNFILLED_AUTHORITY',ts,original_intent=task['intent'].id,level=level,quantity=q,authorization_notional=credit,native_fill=False)
        self._conditional_tasks_done(c)
        if excess:
            i=self._domain._intent(ep,'SOL_EXIT',ep.side,None,quantity=float(excess),reason='ALPHA_RISK_RETIRE')
            c['exits'].append(dict(intent=i,remaining=excess,sigma=None,index=len(self._bars)-1,price=D(0)))
            c['original_target']-=excess
            self._alpha_emit('RETIRE_HELD_AUTHORITY',ts,logical_intent=i.id,quantity=excess,native_fill=False)

    def _alpha_check(self,tick,c):
        ts=tick.ts_event;ep=self._domain.episode
        if tick.instrument_id!=self.config.sol_id or self._mandatory_sol_exit is not None:return
        f=self._alpha_cycle
        positions={p.instrument_id:p for p in self.cache.positions_open()}
        btc=positions.get(self.config.btc_id);sol=positions.get(self.config.sol_id)
        held=sol.quantity.as_decimal() if sol else D(0);bqty=btc.quantity.as_decimal() if btc else D(0)
        if c.get('alpha_mandatory_flat'):
            c.update(qc=D(0),active=False)
            if f:f['target']=D(0)
            self._conditional_reconcile(tick,c,ep,btc,sol,held,bqty,D(0),ts)
            if not held and not any(i.action.startswith('SOL') for i in self._pending_by_order.values()):c['alpha_mandatory_flat']=False
            return
        if not bqty:
            if ep.btc_initial_qty<=0:return  # Pending first BTC admission is not BTC-flat.
            self._discard_queued_intents(lambda i:i.action=='BTC_REDUCE')
            for order in list(self.cache.orders_open()):
                if order.instrument_id==self.config.btc_id and order.is_reduce_only:self.cancel_order(order)
            if not any(i.action.startswith('SOL') for i in self._pending_by_order.values()):self._alpha_retire(c,D(0),ts)
            c.update(qc=D(0),active=False)
            if f:f['target']=D(0)
            return self._conditional_reconcile(tick,c,ep,btc,sol,held,bqty,D(0),ts)
        coeff=self._alpha_coefficients(ts);marks=self._latest_marks
        low,high,unknown,pending=self._alpha_pending(held)
        valid=coeff is not None and self._alpha_ready(ts) and all(i in marks and 0<=ts-marks[i].ts_event<=self.config.max_mark_age_ns for i in (self.config.btc_id,self.config.sol_id))
        if not valid or unknown:
            signature=('UNKNOWN',valid,unknown)
            if signature!=self._alpha_last_audit:
                self._alpha_emit('UNKNOWN',ts,coefficients_valid=bool(valid),pending=pending);self._alpha_last_audit=signature
            # Known live orders can be canceled, but unknown ACK stays owned.
            if pending:return self._conditional_reconcile(tick,c,ep,btc,sol,held,bqty,held,ts)
            return
        bm=marks[self.config.btc_id].price;sm=marks[self.config.sol_id].price;NB=bqty*bm
        E=self._alpha_equity[0];C=max(D(0),E-D('.55')*self._alpha_peak)
        signed=held if sol is None or sol.is_long==(ep.side==-1) else -held
        # A wrong-side actual position is reduced by its actual closing side, never a blind reversal.
        if signed<0:
            if pending:return
            i=self._domain._intent(ep,'SOL_EXIT',-1 if sol.is_long else 1,None,quantity=float(held),reason='CONDITIONAL_NET_EXIT')
            self._conditional_physical=True
            try:self._submit_intent(i,float(tick.bid_price),float(tick.ask_price),None,len(self._bars)-1,ts_now=ts)
            finally:self._conditional_physical=False
            self._alpha_emit('WRONG_SIDE_REDUCE',ts,actual_signed_SOL=-held,quantity=held)
            return
        alpha=c['original_target'];cost,q2=self._alpha_cost(alpha,held,bqty,bm,sm)
        Lalpha=self._alpha_L(alpha*sm,NB,cost)
        transit=max(self._alpha_L(q*sm,NB,cost) for q in (low,high,alpha))
        alpha_ok=Lalpha<=C and transit<=C and self._alpha_margin(alpha,held,ts)
        release=self._alpha_release_ready(ts,Lalpha,C)
        choices=[];inst=self.cache.instrument(self.config.sol_id);step=inst.size_increment.as_decimal()
        for coverage in (D(0),D('.25'),D('.5'),D('.75'),D(1)):
            raw=coverage*NB/f['beta']/sm
            quantities=sorted({(raw/step).to_integral_value(rounding=rule)*step for rule in (ROUND_FLOOR,ROUND_CEILING)})
            for q in quantities:
                minimum=q==0 or ((inst.min_quantity is None or q>=inst.min_quantity.as_decimal()) and (inst.min_notional is None or q*sm>=inst.min_notional.as_decimal()))
                if not minimum or not self._alpha_margin(q,held,ts):continue
                kcost,_=self._alpha_cost(q,held,bqty,bm,sm);loss=self._alpha_L(q*sm,NB,kcost)
                choices.append(dict(c=coverage,quantity=q,L=loss,cost=kcost))
        feasible=next((x for x in choices if x['L']<=C),None)
        status='ALPHA' if alpha_ok and (not f['risk'] or release) else 'PROTECTION' if feasible else 'UNHEDGEABLE'
        if status=='ALPHA':target=alpha
        elif choices:target=(feasible or min(choices,key=lambda x:(x['L'],x['quantity'])))['quantity']
        else:
            self._alpha_emit('UNKNOWN',ts,reason='NO_LOT_MARGIN_VALID_GRID',pending=pending);return
        # Removal of useful protection requires hysteresis; risk-reducing excess trim and BTCactual changes do not wait.
        btc_changed=f['btc_qty'] is not None and f['btc_qty']!=bqty
        old_target=f['target']
        if f['risk'] and old_target is not None and target<old_target and not btc_changed:
            nextcost,_=self._alpha_cost(target,held,bqty,bm,sm)
            oldcost,_=self._alpha_cost(old_target,held,bqty,bm,sm)
            if self._alpha_L(target*sm,NB,nextcost)>self._alpha_L(old_target*sm,NB,oldcost) and not self._alpha_release_ready(ts,self._alpha_L(target*sm,NB,nextcost),C):target=old_target
        if target!=alpha and not pending:self._alpha_retire(c,min(alpha,target),ts)
        if old_target is None or target>old_target:f['last_increase_ns']=ts
        if status=='ALPHA' and f['risk']:
            f['release_used']=self._alpha_reverse
            self._alpha_emit('RELEASE',ts,target=target,L=Lalpha,C=C,bar_close_ns=self._alpha_reverse[0])
        f.update(target=target,risk=status!='ALPHA',btc_qty=bqty)
        c.update(qc=target,active=status!='ALPHA')
        signature=(status,target,c['original_target'],bqty,f['stress_ns'],str(pending))
        if signature!=self._alpha_last_audit:
            self._alpha_emit('BUDGET',ts,status=status,episode_id=ep.id,native_equity=E,global_peak=self._alpha_peak,floor=D('.55')*self._alpha_peak,C=C,
                BTCqty=bqty,BTCmark=bm,SOLmark=sm,actual_signed_SOL_qty=signed,original_target=c['original_target'],target=target,
                beta=f['beta'],beta_frozen_ns=f['beta_ns'],a=f['a'],u=f['u'],stress_close_ns=f['stress_ns'],L_alpha=Lalpha,L_actual_to_alpha=transit,
                pending=pending,Q2_remaining=q2,remaining_execution_cost=cost,grid=choices,actual_transition_budget_satisfied=transit<=C,
                cost_basis='PINNED_NATIVE_QUOTE_TAKER_FEES;FUTURE_FUNDING_AND_REAL_L2_UNKNOWN')
            self._alpha_last_audit=signature
        return self._conditional_reconcile(tick,c,ep,btc,sol,held,bqty,target,ts)
