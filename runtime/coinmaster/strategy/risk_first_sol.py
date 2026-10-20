"""Default-OFF SOL risk policies on the existing native NETTING owner."""
from collections import deque
from decimal import Decimal as D, ROUND_FLOOR, ROUND_CEILING
from math import isfinite, expm1

HOUR=3_600_000_000_000
MINUTE=60_000_000_000


class SolRiskFirstResearch:
    def _risk_first_init(self):
        self.risk_first_sol_audit=[]
        self._rf_peak=max(D(10000),D(str(self.config.active_seed)))
        self._rf_equity=None
        self._rf_dirty=True
        self._rf_pending_checkpoint=None
        self._rf_fill_epoch=0
        self._rf_last_fill_ns=None
        self._rf_final_receipt=None
        self._rf_receipt_count=0
        self._rf_daily=None
        self._rf_reverse=None
        self._rf_previous15=None
        self._rf_last_budget=None
        self._rf_dd=D(0)
        self._rf_stage=0
        self._rf_stage_revision=0
        self._rf_factor=None
        self._rf_factor_ns=None
        self._rf_atr=None
        self._rf_prev_close=None
        self._rf_tr=deque(maxlen=14)
        self._rf_atr_ns=None
        self._rf_sol_parents=[]
        self._rf_sol_child=False
        self._rf_sol_orders={}
        self._rf_sol_context=None
        self._rf_sol_waiting_exits=set()

    def _risk_first_net_owner(self):
        return self.config.research_sol_risk_first in {"cap50","dd-cov","alpha-corridor-v1"}

    def _risk_first_emit(self,event,ts,**values):
        self.risk_first_sol_audit.append({"event":event,"timestamp_ns":ts,
            "variant":self.config.research_sol_risk_first,**values})

    def _risk_first_sample(self,ts):
        if self.config.research_sol_risk_first!="dd-cov":return
        if not all(i in self._latest_marks and 0<=ts-self._latest_marks[i].ts_event<=self.config.max_mark_age_ns
                   for i in (self.config.btc_id,self.config.sol_id)):return
        if getattr(self,"_risk_first_observer_driven",False):return
        self._risk_first_observe_equity(self._v3_equity(),ts)

    def _risk_first_observe_equity(self,equity,ts):
        if self.config.research_sol_risk_first=="alpha-corridor-v1":
            self._rf_peak=max(self._rf_peak,equity)
            self._rf_equity=(equity,ts)
            self._rf_dirty=False
            return
        if self.config.research_sol_risk_first!="dd-cov":return
        self._rf_peak=max(self._rf_peak,equity)
        self._rf_dd=max(D(0),(self._rf_peak-equity)/self._rf_peak)
        old=self._rf_stage
        while self._rf_stage<3 and self._rf_dd>=D((".10",".20",".30")[self._rf_stage]):self._rf_stage+=1
        while self._rf_stage>0 and self._rf_dd<=D((".05",".15",".25")[self._rf_stage-1]):self._rf_stage-=1
        if old!=self._rf_stage:
            self._rf_stage_revision+=1
            self._risk_first_emit("DD_STAGE",ts,old=old,stage=self._rf_stage,native_equity=str(equity),global_peak=str(self._rf_peak),drawdown=str(self._rf_dd))

    def _risk_first_beta_estimate(self,ts):
        if len(self._cover_returns)!=720 or self._cover_last_hour is None or not 0<=ts-self._cover_last_hour<=HOUR:return None
        x,y=zip(*self._cover_returns);mx,my=sum(x)/720,sum(y)/720
        vx=sum((a-mx)**2 for a in x);vy=sum((b-my)**2 for b in y)
        cov=sum((a-mx)*(b-my) for a,b in self._cover_returns)
        if vx<=0 or vy<=0 or cov<=0:return None
        beta=cov/vx;corr=cov/(vx*vy)**.5
        return (D(str(beta)),D(str(corr))) if isfinite(beta) and isfinite(corr) else None

    def _risk_first_factor(self,ts):
        if self._rf_factor_ns is not None and ts-self._rf_factor_ns<HOUR:return
        self._rf_factor_ns=ts
        value=self._risk_first_beta_estimate(ts)
        if value is None:
            self._rf_factor=None
        else:
            beta,corr=value[0],value[1]
            self._rf_factor=(beta,min(D(1),D(str(corr))**2)/D(str(beta))) if beta>0 and corr>0 else None
        self._risk_first_emit("COV_FACTOR",ts,beta=str(self._rf_factor[0]) if self._rf_factor else None,
            k=str(self._rf_factor[1]) if self._rf_factor else None,completed_hour_ns=self._cover_last_hour,returns=len(self._cover_returns),valid=self._rf_factor is not None)

    def _risk_first_state(self,c):
        if "rf" not in c:
            c["rf"]={"cap_btc":None,"cap":None,"oref":c["original_target"],"stage":0,
                "stage_revision":-1,"btc_qty":D(0),"factor_ns":None,"target":None,"ceiling":None,"dirty":True}
        return c["rf"]

    def _risk_first_original(self,intent,qty,ts):
        if not self._risk_first_net_owner():return
        c=self._conditional;f=self._risk_first_state(c)
        if intent.action=="SOL_ADD":
            f["oref"]+=qty;f["ceiling"]=None
        else:f["oref"]=max(D(0),f["oref"]-qty)
        f["dirty"]=True

    def _risk_first_original_terminal(self,released):
        if released>0 and self._risk_first_net_owner() and self._conditional is not None:
            f=self._risk_first_state(self._conditional)
            f["oref"]=max(D(0),f["oref"]-released);f["dirty"]=True

    def _risk_first_cap(self,c,bqty,ts):
        f=self._risk_first_state(c)
        if not bqty:
            f["cap_btc"],f["cap"]=D(0),None
            return None
        if f["cap_btc"]==bqty:return f["cap"]
        marks=self._latest_marks
        if c["beta"] is None or not all(i in marks and 0<=ts-marks[i].ts_event<=self.config.max_mark_age_ns
                for i in (self.config.btc_id,self.config.sol_id)):return None
        step=self.cache.instrument(self.config.sol_id).size_increment.as_decimal()
        f["cap"]=(D('.5')*bqty*marks[self.config.btc_id].price/c["beta"]/marks[self.config.sol_id].price//step)*step
        f["cap_btc"]=bqty
        self._risk_first_emit("CAP_LATCH",ts,btc_qty=str(bqty),cap_qty=str(f["cap"]),beta=str(c["beta"]),btc_mark=str(marks[self.config.btc_id].price),sol_mark=str(marks[self.config.sol_id].price))
        return f["cap"]

    def _risk_first_admit(self,qty,ts):
        if self.config.research_sol_risk_first!="cap50":return qty
        c=self._conditional_state(ts)
        btc=next((p for p in self.cache.positions_open() if p.instrument_id==self.config.btc_id),None)
        if btc is None:return qty
        cap=self._risk_first_cap(c,btc.quantity.as_decimal(),ts)
        allowed=D(0) if cap is None else max(D(0),cap-c["original_target"])
        admitted=min(qty,allowed)
        self._risk_first_emit("CAP_ADMISSION",ts,requested=str(qty),admitted=str(admitted),cap=str(cap),original_target=str(c["original_target"]))
        return admitted

    def _risk_first_increment(self,qty,held):
        c=self._conditional;f=self._risk_first_state(c)
        if self.config.research_sol_risk_first!="dd-cov":return max(D(0),c["original_target"]+qty-held)
        w=(D(0),D('.34'),D('.67'),D(1))[self._rf_stage]
        target=min((1-w)*(f["oref"]+qty),c["original_target"]+qty)+w*c["qc"]
        return max(D(0),target-held)

    def _risk_first_retire(self,c,target,ts):
        # Discard unfilled original authorization first; actual held risk exits
        # retain all historical fill/notional/clock facts until native reduction.
        excess=max(D(0),c["original_target"]-target)
        for task in list(c["adds"]):
            if excess<=0:break
            q=min(excess,task["remaining"]);task["remaining"]-=q;c["original_target"]-=q;excess-=q
        self._conditional_tasks_done(c)
        if excess:
            ep=self._domain.episode
            intent=self._domain._intent(ep,"SOL_EXIT",ep.side,None,quantity=float(excess),reason="SOL_RISK_FIRST_TRIM")
            c["exits"].append({"intent":intent,"remaining":excess,"sigma":None,"index":len(self._bars)-1,"price":D(0)})
            c["original_target"]-=excess
            self._risk_first_emit("ORIGINAL_RISK_RETIRE",ts,quantity=str(excess),logical_intent=intent.id,original_live_target=str(c["original_target"]),native_fill=False)

    def _risk_first_check(self,tick,c):
        if self.config.research_sol_risk_first=="alpha-corridor-v1":return self._corridor_check(tick,c)
        ep=self._domain.episode;ts=tick.ts_event;f=self._risk_first_state(c)
        positions={p.instrument_id:p for p in self.cache.positions_open()}
        btc=positions.get(self.config.btc_id);sol=positions.get(self.config.sol_id)
        held=sol.quantity.as_decimal() if sol else D(0);bqty=btc.quantity.as_decimal() if btc else D(0)
        variant=self.config.research_sol_risk_first
        if variant=="cap50":
            cap=self._risk_first_cap(c,bqty,ts)
            target=c["original_target"] if cap is None else min(c["original_target"],cap)
            c["active"]=False;c["qc"]=D(0)
        else:
            self._risk_first_sample(ts);self._risk_first_factor(ts)
            marks=self._latest_marks
            if not all(i in marks and 0<=ts-marks[i].ts_event<=self.config.max_mark_age_ns for i in (self.config.btc_id,self.config.sol_id)):return
            changed=f["btc_qty"]!=bqty or f["stage_revision"]!=self._rf_stage_revision or f["factor_ns"]!=self._rf_factor_ns or f["dirty"]
            if changed:
                qc=D(0) if self._rf_factor is None or not bqty else bqty*marks[self.config.btc_id].price*self._rf_factor[1]/marks[self.config.sol_id].price
                w=(D(0),D('.34'),D('.67'),D(1))[self._rf_stage]
                raw=min((1-w)*f["oref"],c["original_target"])+w*qc
                stage_changed=f["stage"]!=self._rf_stage;btc_changed=f["btc_qty"]!=bqty
                if self._rf_stage>f["stage"] or bqty>f["btc_qty"]:f["ceiling"]=None
                if self._rf_stage<f["stage"] or not bqty and f["btc_qty"]>0:f["ceiling"]=min(held,f["ceiling"]) if f["ceiling"] is not None else held
                if f["ceiling"] is not None:raw=min(raw,f["ceiling"])
                step=self.cache.instrument(self.config.sol_id).size_increment.as_decimal();raw=(raw//step)*step
                if stage_changed or btc_changed or f["dirty"] or f["target"] is None or not raw or abs(raw-held)>=D('.10')*abs(raw):f["target"]=raw
                c["qc"]=qc;c["active"]=self._rf_stage>0
                self._risk_first_emit("RISK_TARGET",ts,stage=self._rf_stage,weight=str(w),global_peak=str(self._rf_peak),drawdown=str(self._rf_dd),original_reference=str(f["oref"]),original_live=str(c["original_target"]),minimum_variance_qty=str(qc),raw_qty=str(raw),target_qty=str(f["target"]),actual_SOL=str(held),btc_qty=str(bqty),ceiling=str(f["ceiling"]))
                f.update(stage=self._rf_stage,stage_revision=self._rf_stage_revision,btc_qty=bqty,factor_ns=self._rf_factor_ns,dirty=False)
            target=f["target"] if f["target"] is not None else c["original_target"]
        # Native pending ownership must resolve before retiring logical tasks.
        if not any(i.action.startswith("SOL") for i in self._pending_by_order.values()):self._risk_first_retire(c,target,ts)
        return self._conditional_reconcile(tick,c,ep,btc,sol,held,bqty,target,ts)

    def _risk_first_bar(self,bar):
        if self.config.research_sol_risk_first=="alpha-corridor-v1":
            from nautilus_trader.model.enums import BarAggregation
            if bar.bar_type.instrument_id!=self.config.sol_id or bar.bar_type.spec.aggregation!=BarAggregation.MINUTE or bar.bar_type.spec.step!=15:return
            ts=bar.ts_event;old=self._rf_previous15
            if ts>self.clock.timestamp_ns() or old and ts<=old[0]:return
            ep=self._domain.episode
            if old and ep and ((ep.side==1 and D(str(bar.close))>old[1]) or (ep.side==-1 and D(str(bar.close))<old[2])):
                self._rf_reverse=(ts,self.clock.timestamp_ns())
            self._rf_previous15=(ts,D(str(bar.high)),D(str(bar.low)))
            return
        if self.config.research_sol_risk_first!='split-atr' or bar.bar_type.instrument_id!=self.config.sol_id:return
        from nautilus_trader.model.enums import BarAggregation
        if bar.bar_type.spec.aggregation!=BarAggregation.MINUTE or bar.bar_type.spec.step!=15:return
        if self._rf_atr_ns is not None and bar.ts_event<=self._rf_atr_ns:return
        high,low,close=D(str(bar.high)),D(str(bar.low)),D(str(bar.close))
        if self._rf_prev_close is not None:
            tr=max(high-low,abs(high-self._rf_prev_close),abs(low-self._rf_prev_close))
            self._rf_tr.append(tr)
            if self._rf_atr is not None:self._rf_atr=(self._rf_atr*13+tr)/14
            elif len(self._rf_tr)==14:self._rf_atr=sum(self._rf_tr)/14
        self._rf_prev_close=close;self._rf_atr_ns=bar.ts_event

    def _risk_first_sol_prepare(self,intent,qty,step,ts,sigma,index):
        if self.config.research_sol_risk_first!='split-atr' or self._rf_sol_child:return qty
        if self._rf_atr is None or self._rf_atr<=0 or self._rf_atr_ns is None or not 0<=ts-self._rf_atr_ns<=15*MINUTE:
            self._risk_first_emit('ATR_UNAVAILABLE_NATIVE_IOC',ts,logical_intent=intent.id,quantity=str(qty),atr_close_ns=self._rf_atr_ns)
            return qty
        lots=int(qty/step)
        first=max(1,lots*34//100);second=lots*33//100
        pieces=[D(first)*step,D(second)*step,D(lots-first-second)*step]
        mark=self._latest_marks.get(self.config.btc_id)
        signal_btc=mark.price if mark is not None and 0<=ts-mark.ts_event<=self.config.max_mark_age_ns else None
        p={'intent':intent,'episode_id':intent.episode_id,'quantity':qty,'filled':D(0),'cancelled':D(0),
            'pieces':pieces,'leg_filled':[D(0)]*3,'pending':[None]*3,'atr':self._rf_atr,'atr_ns':self._rf_atr_ns,
            'first_px':None,'signal_ns':ts,'deadline_ns':ts+60*MINUTE,'signal_btc':signal_btc,'btc_side':self._domain.episode.side,
            'sigma':sigma,'index':index,'fallback':False,'stopped':False,'closed':False}
        self._rf_sol_parents.append(p);self._rf_sol_context=(p,0)
        self._risk_first_emit('SOL_SPLIT_PARENT',ts,logical_intent=intent.id,quantity=str(qty),leg_quantities=[str(q) for q in pieces],atr=str(p['atr']),atr_close_ns=p['atr_ns'],deadline_ns=p['deadline_ns'],signal_btc_mark=str(signal_btc))
        return pieces[0]

    def _risk_first_sol_limit(self,intent,instrument,qty):
        context=self._rf_sol_context
        if not context or context[0]['intent'].id!=intent.id:return None
        p,leg=context
        if leg==0 or p['fallback'] or p['first_px'] is None:return None
        from coinmaster.strategy.wave_overlay import _native_limit_price
        from nautilus_trader.model.enums import OrderSide,TimeInForce
        from decimal import ROUND_FLOOR,ROUND_CEILING
        raw=p['first_px']-D(str(intent.side))*p['atr']*(D('.5') if leg==1 else D(1))
        if raw<=0:p['fallback']=True;return None
        step=instrument.price_increment.as_decimal()
        price=_native_limit_price(instrument,(raw/step).to_integral_value(rounding=ROUND_FLOOR if intent.side==1 else ROUND_CEILING)*step)
        return self.order_factory.limit(instrument_id=instrument.id,order_side=OrderSide.BUY if intent.side==1 else OrderSide.SELL,
            quantity=instrument.make_qty(qty),price=price,time_in_force=TimeInForce.GTC,post_only=True,reduce_only=False)

    def _risk_first_sol_bind(self,intent,order):
        context=self._rf_sol_context
        if context and context[0]['intent'].id==intent.id:
            p,leg=context;oid=str(order.client_order_id)
            p['pending'][leg]=oid;self._rf_sol_orders[oid]=(p,leg);self._rf_sol_context=None
            self._risk_first_emit('SOL_SPLIT_CHILD',order.ts_init,parent_intent=intent.id,leg=leg,native_order_id=oid,quantity=str(order.quantity),order_type=order.order_type.name)

    def _risk_first_sol_fill(self,intent,event):
        context=self._rf_sol_orders.get(str(event.client_order_id))
        if context is None:return
        p,leg=context;q=event.last_qty.as_decimal()
        if p['filled']+q>p['quantity'] or p['leg_filled'][leg]+q>p['pieces'][leg]:raise ValueError('SOL_SPLIT_Q_OVERFILL')
        p['filled']+=q;p['leg_filled'][leg]+=q
        if p['first_px'] is None:p['first_px']=event.last_px.as_decimal()
        if p['stopped']:p['cancelled']=p['quantity']-p['filled']
        ep=self._domain.episode
        if ep is not None and ep.id==intent.episode_id:ep.pending[intent.id]=intent
        self._risk_first_emit('SOL_SPLIT_FILL',event.ts_event,parent_intent=intent.id,leg=leg,native_order_id=str(event.client_order_id),quantity=str(q),price=str(event.last_px),filled=str(p['filled']),planned=str(p['quantity']))

    def _risk_first_sol_terminal(self,oid,ts,cause):
        context=self._rf_sol_orders.pop(oid,None)
        if context is None:return
        p,leg=context;p['pending'][leg]=None
        ep=self._domain.episode
        if p['filled']==p['quantity'] or p['stopped'] and not any(p['pending']):
            p['closed']=True;p['cancelled']=p['quantity']-p['filled']
            self._domain.on_parent_terminal(p['intent'].id)
        elif ep is not None and ep.id==p['episode_id']:
            ep.pending[p['intent'].id]=p['intent']
        self._risk_first_emit('SOL_SPLIT_TERMINAL',ts,parent_intent=p['intent'].id,leg=leg,native_order_id=oid,cause=cause,filled=str(p['filled']),cancelled=str(p['cancelled']),planned=str(p['quantity']),closed=p['closed'])

    def _risk_first_sol_stop(self,reason):
        if self.config.research_sol_risk_first!='split-atr':return False
        from nautilus_trader.model.identifiers import ClientOrderId
        for p in self._rf_sol_parents:
            if p['closed']:continue
            p['stopped']=True;p['cancelled']=p['quantity']-p['filled']
            for oid in list(p['pending']):
                if oid:
                    order=self.cache.order(ClientOrderId(oid))
                    if order is not None and not order.is_closed:self.cancel_order(order)
            if not any(p['pending']):
                p['closed']=True;self._domain.on_parent_terminal(p['intent'].id)
        return any(any(p['pending']) for p in self._rf_sol_parents if not p['closed'])

    def _risk_first_sol_check(self,tick):
        if self.config.research_sol_risk_first!='split-atr':return
        from nautilus_trader.model.identifiers import ClientOrderId
        for p in self._rf_sol_parents:
            if p['closed'] or p['stopped']:continue
            ep=self._domain.episode
            if ep is None or ep.id!=p['episode_id'] or p['intent'].level not in ep.sol_rights or self._forced_close_reason or self._liquidating or self._mandatory_sol_exit is not None:
                self._risk_first_sol_stop('MANDATORY_OR_EPISODE_END');return
            mark=self._latest_marks.get(self.config.btc_id)
            adverse=(mark is not None and p['signal_btc'] is not None and 0<=tick.ts_event-mark.ts_event<=self.config.max_mark_age_ns
                and -D(p['btc_side'])*(mark.price/p['signal_btc']-1)>=D('.01'))
            if tick.ts_event>=p['deadline_ns'] or adverse:
                p['fallback']=True
                p.setdefault('fallback_reason','BTC_ADVERSE_1PP' if adverse else '60MIN')
            if p['fallback'] and any(p['pending']):
                for oid in list(p['pending']):
                    if oid:
                        order=self.cache.order(ClientOrderId(oid))
                        if order is not None and not order.is_closed and order.order_type.name=='LIMIT':self.cancel_order(order)
                continue  # ACK/cancel/late fills own leaves until a later real quote.
            if tick.instrument_id!=self.config.sol_id or not self._entries_enabled():continue
            for leg in range(3):
                if p['pending'][leg] or p['leg_filled'][leg]>=p['pieces'][leg]:continue
                if leg and p['first_px'] is None:continue
                ep.pending[p['intent'].id]=p['intent']
                self._rf_sol_child=True;self._rf_sol_context=(p,leg)
                try:self._submit_intent(p['intent'],float(tick.bid_price),float(tick.ask_price),p['sigma'],p['index'],ts_now=tick.ts_event,entry_override_qty=p['pieces'][leg]-p['leg_filled'][leg])
                finally:self._rf_sol_child=False;self._rf_sol_context=None

    def _risk_first_report(self):
        return {'variant':self.config.research_sol_risk_first,'audit':self.risk_first_sol_audit,'corridor_status_counts':getattr(self,'_rf_corridor_counts',{}),
            'SOL_parents':[{k:([str(v) for v in value] if k in {'pieces','leg_filled'} else str(value) if isinstance(value,D) else value)
                for k,value in p.items() if k not in {'intent','sigma'}} for p in self._rf_sol_parents]}

    def _corridor_queue_checkpoint(self,source_quote_ts):
        if self.config.research_sol_risk_first=='alpha-corridor-v1':
            self._rf_pending_checkpoint=(source_quote_ts,self._rf_fill_epoch)

    def _corridor_finalize_checkpoint(self,receipt_ts):
        # Engine matching may deliver fills AFTER the strategy's quote callback.
        # A strictly later event entry is a receipt, never backdated to that quote.
        if self.config.research_sol_risk_first!='alpha-corridor-v1':return
        pending=self._rf_pending_checkpoint
        if pending is None or receipt_ts is None or receipt_ts<=pending[0]:return
        if self._rf_last_fill_ns is not None and self._rf_last_fill_ns>=receipt_ts:return
        marks=self._latest_marks
        if any(i not in marks or not 0<=receipt_ts-marks[i].ts_event<=self.config.max_mark_age_ns for i in (self.config.btc_id,self.config.sol_id)):return
        from coinmaster.strategy.wave_overlay import _native_account_money
        epoch=self._rf_fill_epoch
        account=self.cache.account_for_venue(self.config.btc_id.venue)
        if account is None:return
        equity=_native_account_money(account)
        for pos in self.cache.positions_open():
            if pos.instrument_id not in marks:return
            equity+=pos.unrealized_pnl(self.cache.instrument(pos.instrument_id).make_price(marks[pos.instrument_id].price)).as_decimal()
        if epoch!=self._rf_fill_epoch:return
        self._risk_first_observe_equity(equity,receipt_ts)
        self._rf_final_receipt=dict(source_quote_ns=pending[0],receipt_ns=receipt_ts,source_fill_epoch=pending[1],final_fill_epoch=epoch,
            mark_ns={str(i):marks[i].ts_event for i in (self.config.btc_id,self.config.sol_id)})
        self._rf_receipt_count+=1
        self._rf_pending_checkpoint=None

    def _corridor_estimate(self,ts):
        rows=[b for b in self._bars if int(b.close_time.timestamp()*1e9)<=ts and int(b.available_at.timestamp()*1e9)<=ts][-91:]
        if any(not isfinite(v) or v<=0 for b in rows for v in (b.btc_close,b.sol_close)):return None
        history=self._alpha_history(ts)
        if history is None:return None
        x,y,closed=history
        if self._rf_daily is not None and self._rf_daily['closed']==closed:return self._rf_daily
        from coinmaster.domain.wave_overlay import linear_quantile
        mx,my=sum(x)/90,sum(y)/90
        vx=sum((v-mx)**2 for v in x);vy=sum((v-my)**2 for v in y)
        cov=sum((a-mx)*(b-my) for a,b in zip(x,y))
        if vx<=0 or vy<=0 or cov<=0:return None
        beta=cov/vx
        try:values=(beta,expm1(linear_quantile([abs(v) for v in x],.95)),expm1(linear_quantile([abs(b-beta*a) for a,b in zip(x,y)],.95)))
        except (OverflowError,ValueError):return None
        if not all(isfinite(v) and v>=0 for v in values) or beta<=0:return None
        self._rf_daily=dict(closed=closed,beta=D(str(beta)),a=D(str(values[1])),u=D(str(values[2])))
        self._risk_first_emit('CORRIDOR_DAILY90',ts,**{k:str(v) for k,v in self._rf_daily.items()})
        return self._rf_daily

    def _corridor_btc_endpoints(self,btc,ts):
        # Native actual B stays actual. Known opening leaves are separate possible states.
        from nautilus_trader.model.identifiers import ClientOrderId
        from nautilus_trader.model.enums import OrderSide
        ep=self._domain.episode
        actual=(btc.quantity.as_decimal()*(1 if btc.is_long else -1) if btc else D(0))*ep.side
        low=high=actual;unknown=False
        for oid,i in self._pending_by_order.items():
            if i.action!='BTC_ENTRY':continue
            o=self.cache.order(ClientOrderId(oid))
            if o is None:unknown=True;continue
            if o.is_closed:continue
            q=o.leaves_qty.as_decimal()*(1 if o.side==OrderSide.BUY else -1)*ep.side
            low+=min(D(0),q);high+=max(D(0),q)
        return actual,low,high,unknown

    @staticmethod
    def _corridor_interval(loss,points,C):
        # Convex piecewise-linear sublevel set. Points include all loss kinks.
        points=sorted(set(points));best=min(points,key=lambda q:(loss(q),q))
        legal=[]
        for q in points:
            if loss(q)<=C:legal.append(q)
        for lo,hi in zip(points,points[1:]):
            l,h=loss(lo),loss(hi)
            if (l<C<h) or (h<C<l):legal.append(lo+(C-l)*(hi-lo)/(h-l))
        return (min(legal),max(legal)) if legal else None,best

    def _corridor_check(self,tick,c):
        from nautilus_trader.model.identifiers import ClientOrderId
        ts=tick.ts_event;ep=self._domain.episode;f=self._risk_first_state(c)
        if self._mandatory_sol_exit is not None:return
        positions={p.instrument_id:p for p in self.cache.positions_open()}
        btc=positions.get(self.config.btc_id);sol=positions.get(self.config.sol_id)
        held=sol.quantity.as_decimal() if sol else D(0)
        if c.get('corridor_mandatory_flat'):
            c.update(qc=D(0),active=False)
            if not any(i.action.startswith('SOL') for i in self._pending_by_order.values()):self._corridor_retire(c,D(0),ts)
            self._conditional_reconcile(tick,c,ep,btc,sol,held,btc.quantity.as_decimal() if btc else D(0),D(0),ts)
            if not held and not any(i.action.startswith('SOL') for i in self._pending_by_order.values()):c['corridor_mandatory_flat']=False
            return
        estimate=self._corridor_estimate(ts);marks=self._latest_marks
        low,high,unknown,pending=self._alpha_pending(held)
        actual,bl,bh,bunknown=self._corridor_btc_endpoints(btc,ts)
        # BTC-flat pure protection must close even when risk data is unknown.
        if not actual and not bl and not bh and held>c['original_target']:
            c.update(qc=c['original_target'],active=False)
            return self._conditional_reconcile(tick,c,ep,btc,sol,held,D(0),c['original_target'],ts)
        valid=(not self._rf_dirty and estimate is not None and self._rf_equity is not None and 0<=ts-self._rf_equity[1]<=self.config.max_mark_age_ns
            and all(i in marks and 0<=ts-marks[i].ts_event<=self.config.max_mark_age_ns for i in (self.config.btc_id,self.config.sol_id)))
        if not valid or unknown or bunknown:
            signature=('DATA_UNKNOWN',bool(valid),unknown,bunknown)
            if signature!=self._rf_last_budget:
                self._risk_first_emit('CORRIDOR_BUDGET',ts,status='DATA_UNKNOWN',checkpoint_valid=bool(valid),SOL_unknown_ACK=unknown,BTC_unknown_ACK=bunknown)
                self._rf_last_budget=signature
            if pending and tick.instrument_id==self.config.sol_id:
                return self._conditional_reconcile(tick,c,ep,btc,sol,held,abs(actual),held,ts)
            return
        if sol is not None and sol.is_long!=(ep.side==-1):
            if pending or tick.instrument_id!=self.config.sol_id:return
            i=self._domain._intent(ep,'SOL_EXIT',-1 if sol.is_long else 1,None,quantity=float(held),reason='CONDITIONAL_NET_EXIT')
            self._conditional_physical=True
            try:self._submit_intent(i,float(tick.bid_price),float(tick.ask_price),None,len(self._bars)-1,ts_now=ts)
            finally:self._conditional_physical=False
            return
        bm,sm=marks[self.config.btc_id].price,marks[self.config.sol_id].price
        beta,a,u=(estimate[k] for k in ('beta','a','u'))
        E=self._rf_equity[0];C=E-D('.55')*self._rf_peak
        alpha=c['original_target'];inst=self.cache.instrument(self.config.sol_id);step=inst.size_increment.as_decimal()
        q2=D(0);p=self._split_parent
        if p and not p['closed']:q2=max(D(0),p['quantity']-p['filled']-p['cancelled'])
        feeS=D(str(inst.taker_fee))*sm;feeB=D(str(self.cache.instrument(self.config.btc_id).taker_fee))*bm
        # Costs are future native-proxy transactions only; funding already paid is in E.
        constant=(max(abs(bl),abs(bh))+2*q2)*feeB+max(D(0),high-held)*feeS
        def cost(q):return constant+(abs(q-held)+q)*feeS
        def loss(q):return max(a*abs(b*bm-beta*q*sm)+u*q*sm+cost(q) for b in (bl,bh))
        neutral=[max(D(0),b*bm/beta/sm) for b in (bl,bh)]
        upper=max([alpha,held,high]+neutral)+max(D(1),abs(C))/(max(u*sm+feeS,D('1e-20')))
        points=[D(0),held,upper,max(D(0),(bl+bh)*bm/beta/sm/2)]+neutral
        interval,best=self._corridor_interval(loss,points,C)
        target=min(max(alpha,interval[0]),interval[1]) if interval else best
        # Venue/Q2 reserve is unchanged. Find the largest native-lot increase allowed by it.
        margin_ok=lambda q:q<=held or self._alpha_margin(q,held,ts)
        cap=upper
        if target>held and not margin_ok(target):
            lo_lots=int(held/step);hi_lots=int(target/step)
            while lo_lots<hi_lots:
                mid=(lo_lots+hi_lots+1)//2
                if margin_ok(D(mid)*step):lo_lots=mid
                else:hi_lots=mid-1
            cap=D(lo_lots)*step
        candidates={D(0),held}
        for q in points+[target,alpha,cap]+(list(interval) if interval else []):
            for rule in (ROUND_FLOOR,ROUND_CEILING):
                v=(max(D(0),q)/step).to_integral_value(rounding=rule)*step
                if v>cap or not margin_ok(v):continue
                if v and ((inst.min_quantity is not None and v<inst.min_quantity.as_decimal()) or (inst.min_notional is not None and v*sm<inst.min_notional.as_decimal())):continue
                candidates.add(v)
        feasible=[q for q in candidates if loss(q)<=C and margin_ok(q)]
        status='FEASIBLE' if feasible else 'SOL_RISK_INFEASIBLE' if interval is None else 'SOL_MARGIN_INSUFFICIENT'
        target=min(feasible,key=lambda q:(abs(q-alpha),q)) if feasible else min(candidates,key=lambda q:(loss(q),q))
        # Acquire headroom only after an actual breach; healthy alpha keeps its target.
        inner_correction=False
        if C>0 and loss(held)>C:
            inner,unused=self._corridor_interval(loss,points,D('.8')*C)
            if inner is not None:
                inner_candidates=set(candidates)
                for q in inner:
                    for rule in (ROUND_FLOOR,ROUND_CEILING):
                        v=(max(D(0),q)/step).to_integral_value(rounding=rule)*step
                        if v<=cap and margin_ok(v) and (not v or ((inst.min_quantity is None or v>=inst.min_quantity.as_decimal()) and (inst.min_notional is None or v*sm>=inst.min_notional.as_decimal()))):
                            inner_candidates.add(v)
                legal=[q for q in inner_candidates if loss(q)<=D('.8')*C and margin_ok(q)]
                if legal:
                    target=min(legal,key=lambda q:(abs(q-alpha),q));inner_correction=True
        # Healthy actual/alpha receives its ordinary execution, without price-boundary churn.
        risk=f.get('corridor_risk',False)
        reverse=self._rf_reverse
        release=bool(reverse and reverse[0]>f.get('last_increase',0) and reverse[1]<ts and reverse!=f.get('release_used') and loss(target)<=D('.8')*C)
        if risk and target<held and held>D(str(ep.sol_qty)) and not c['exits'] and not release and loss(held)<=C:target=held
        # New outstanding original tasks are fresh permission; old IOC terminals remove them.
        if risk and target>held and target<=alpha and (not c['adds'] or loss(target)>D('.8')*C):target=held if loss(held)<=C else target
        if not actual and not any(b for b in (bl,bh)):
            # No independent protection opening; preserve only lawful original alpha.
            target=min(target,alpha)
        transit=max(loss(low),loss(high))
        constrained=target!=alpha
        if target!=alpha and not pending:self._corridor_retire(c,min(alpha,target),ts)
        if target>held:f['last_increase']=ts
        if release and target<held:f['release_used']=reverse
        f.update(target=target,corridor_risk=constrained or status!='FEASIBLE' or (risk and not release))
        c.update(qc=target,active=target>c['original_target'])
        signature=(status,target,c['original_target'],actual,estimate['closed'],tuple(str(x) for x in (low,high)),self._rf_equity[1])
        # Bounded detailed samples, all outcomes counted independently.
        self._rf_corridor_counts=getattr(self,'_rf_corridor_counts',{})
        self._rf_corridor_counts[status]=self._rf_corridor_counts.get(status,0)+1
        if signature!=self._rf_last_budget and len(self.risk_first_sol_audit)<8192:
            self._risk_first_emit('CORRIDOR_BUDGET',ts,status=status,target=str(target),alpha=str(alpha),held=str(held),E=str(E),H=str(self._rf_peak),C=str(C),L=str(loss(target)),held_L=str(loss(held)),pending_L=str(transit),transition_satisfied=transit<=C,inner_correction=inner_correction,beta=str(beta),a=str(a),u=str(u),BTC_actual=str(actual),BTC_possible=[str(bl),str(bh)],Q2_remaining=str(q2),cost=str(cost(target)),native_final_receipt=self._rf_final_receipt,cost_basis='PINNED_TAKER_PROXY_FUTURE_COSTS_ONLY;FUNDING_L2_UNKNOWN')
            self._rf_last_budget=signature
        return self._conditional_reconcile(tick,c,ep,btc,sol,held,abs(actual),target,ts)

    def _corridor_retire(self,c,target,ts):
        # Risk-consumed unfilled authority cannot become future automatic IOC debt.
        ep=self._domain.episode;excess=max(D(0),c['original_target']-target)
        for task in c['adds']:
            q=min(excess,task['remaining']);excess-=q
            level=task['intent'].level
            if q and level is not None:
                ep.sol_risk_retired_notional[level]=ep.sol_risk_retired_notional.get(level,0)+float(q*task['price'])
        self._risk_first_retire(c,target,ts)
