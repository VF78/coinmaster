"""Default-OFF SOL risk policies on the existing native NETTING owner."""
from collections import deque
from decimal import Decimal as D
from math import isfinite

HOUR=3_600_000_000_000
MINUTE=60_000_000_000


class SolRiskFirstResearch:
    def _risk_first_init(self):
        self.risk_first_sol_audit=[]
        self._rf_peak=D(str(self.config.active_seed))
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
        return self.config.research_sol_risk_first in {"cap50","dd-cov"}

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
        return {'variant':self.config.research_sol_risk_first,'audit':self.risk_first_sol_audit,
            'SOL_parents':[{k:([str(v) for v in value] if k in {'pieces','leg_filled'} else str(value) if isinstance(value,D) else value)
                for k,value in p.items() if k not in {'intent','sigma'}} for p in self._rf_sol_parents]}
