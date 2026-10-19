# Opt-in BTC-owned SOL insurance; native orders/cache/account remain authoritative.
from decimal import Decimal as D
from math import log, sqrt, isfinite
from nautilus_trader.model.enums import BarAggregation

MINUTE=60_000_000_000
DAY=1440*MINUTE

class ImmediateSolInsurance:
    def _insurance_init(self):
        self.insurance_audit=[]
        self.insurance_cycles=[]
        self._insurance_cycle=None
        self._insurance_bars={}
        self._insurance_confirm={}
        self._insurance_quote_seq=0

    def _insurance_enabled(self):
        return self.config.research_immediate_sol is not None

    def _insurance_emit(self,event,ts,**values):
        s=self._insurance_cycle
        row={'event':event,'timestamp_ns':ts,'variant':self.config.research_immediate_sol}
        if s:row.update(episode_id=s['episode_id'],fraction=str(s['fraction']),recovery_fraction=str(s['recovery_fraction']),base=str(s['base']),k=str(s['k']),sigma=str(s['sigma']))
        def safe(x):
            if isinstance(x,D):return str(x)
            if isinstance(x,dict):return {str(k):safe(v) for k,v in x.items()}
            if isinstance(x,(list,tuple,set)):return [safe(v) for v in x]
            return x
        row.update(safe(values));self.insurance_audit.append(row)

    def _insurance_estimate(self,ts):
        # The existing DailyBar feature history already has two-year warmup.
        n=self.config.research_immediate_lookback
        rows=[b for b in self._bars if int(b.close_time.timestamp()*1e9)<=ts][-n-1:]
        if len(rows)!=n+1:return None
        times=[int(b.close_time.timestamp()*1e9) for b in rows]
        if any(b-a!=DAY for a,b in zip(times,times[1:])):return None
        x=[log(b.btc_close/a.btc_close) for a,b in zip(rows,rows[1:])]
        y=[log(b.sol_close/a.sol_close) for a,b in zip(rows,rows[1:])]
        mx,my=sum(x)/n,sum(y)/n
        vx=sum((v-mx)**2 for v in x)/(n-1);vy=sum((v-my)**2 for v in y)/(n-1)
        if not all(isfinite(v) for v in (vx,vy)) or vx<=0 or vy<=0:return None
        sigma=D(str(sqrt(vx)));k=D(str(sqrt(vx/vy)))
        return k,sigma,times[-1],n

    def _insurance_btc_fill(self,intent,price,ts):
        if not self._insurance_enabled() or intent.action!='BTC_ENTRY':return
        ep=self._domain.episode
        if ep is None:return
        s=self._insurance_cycle
        if s and s['episode_id']==ep.id:return
        est=self._insurance_estimate(ts)
        base=D(1)/3 if self.config.research_immediate_sol=='i33' else D('.25')
        s={'episode_id':ep.id,'side':ep.side,'first_fill_ns':ts,'first_price':D(str(price)),
            'extreme':D(str(price)),'k':est[0] if est else None,'sigma':est[1] if est else None,
            'estimate_close_ns':est[2] if est else None,'returns':est[3] if est else 0,
            'base_full':base,'base':base,'floor':base/2,'fraction':base,'light':False,
            'recovery_fraction':D(0),'recovery_used':False,'recovery_arm':None,
            'arm':None,'rearm_adverse':None,'last_change_ns':ts,'last_reverse_ns':-1,
            'last_harvest_ns':-1,'latch_btc':None,'latch_fraction':None,'target':D(0),
            'btc_position_ids':set(),'sol_position_ids':set(),'equity_start':None,'closed':False}
        self._insurance_cycle=s;self.insurance_cycles.append(s)
        self._insurance_emit('FIRST_BTC_FILL',ts,estimate_close_ns=s['estimate_close_ns'],returns=s['returns'],coefficient_valid=est is not None,funding_component='UNKNOWN')

    def _insurance_position(self,event):
        if not self._insurance_enabled() or self._insurance_cycle is None:return
        s=self._insurance_cycle
        if event.ts_event<s['first_fill_ns']:return
        if event.instrument_id in (self.config.btc_id,self.config.sol_id):
            s['btc_position_ids' if event.instrument_id==self.config.btc_id else 'sol_position_ids'].add(str(event.position_id))
        if not any(p.instrument_id in (self.config.btc_id,self.config.sol_id) for p in self.cache.positions_open()) and self._domain.episode is None:
            s['closed']=True;s['target']=D(0)
        if s['equity_start'] is None and event.instrument_id==self.config.btc_id:
            s['equity_start']=self._v3_equity()
            self._insurance_emit('EQUITY_REFERENCE',event.ts_event,native_equity=s['equity_start'])

    def _insurance_pnl(self,instrument_id,ts):
        # Read native Position.realized_pnl (already fee-net) and native mark uPnL.
        s=self._insurance_cycle
        ids=s['btc_position_ids' if instrument_id==self.config.btc_id else 'sol_position_ids']
        result=D(0);close_fee=D(0)
        instrument=self.cache.instrument(instrument_id)
        mark=self._latest_marks.get(instrument_id)
        if mark is None or not 0<=ts-mark.ts_event<=self.config.max_mark_age_ns:return None,None
        for p in self.cache.positions():
            if p.instrument_id!=instrument_id or str(p.id) not in ids:continue
            result+=p.realized_pnl.as_decimal() if p.realized_pnl is not None else D(0)
            if p.is_open:
                result+=p.unrealized_pnl(instrument.make_price(mark.price)).as_decimal()
                close_fee+=p.quantity.as_decimal()*mark.price*instrument.taker_fee
        return result,close_fee

    def _insurance_bar(self,bar):
        if not self._insurance_enabled():return
        tf=60 if bar.bar_type.spec.aggregation==BarAggregation.HOUR else 15
        key=(bar.bar_type.instrument_id,tf);ts=bar.ts_event
        old=self._insurance_bars.get(key)
        if old and ts<=old[0]:return
        s=self._insurance_cycle
        if old and bar.bar_type.instrument_id==self.config.sol_id:
            direction=1 if bar.close>old[1] else -1 if bar.close<old[2] else 0
            if direction:
                self._insurance_confirm[direction]=(ts,self.clock.timestamp_ns(),self._insurance_quote_seq+1,tf)
        if s and bar.bar_type.instrument_id==self.config.btc_id and ts>s['first_fill_ns'] and self.config.research_immediate_sol=='i25-light' and s['sigma'] and not s['light']:
            px=D(str(bar.close));move=D(str(s['side']*log(float(px/s['first_price']))))
            adverse=self._insurance_adverse(px)
            if move>=s['sigma'] and adverse<D('.25'):
                s['light']=True;s['base']=s['floor'];s['fraction']=min(s['fraction'],s['base'])
                s['arm']=None;s['rearm_adverse']=adverse;s['last_change_ns']=self.clock.timestamp_ns()
                self._insurance_emit('LIGHT_LATCH',self.clock.timestamp_ns(),bar_close_ns=ts,timeframe_minutes=tf,adverse_sigma=adverse)
        self._insurance_bars[key]=(ts,bar.high,bar.low)

    def _insurance_adverse(self,price):
        s=self._insurance_cycle
        ratio=s['extreme']/price if s['side']==1 else price/s['extreme']
        return max(D(0),D(str(log(float(ratio))))/s['sigma'])

    def _insurance_confirmation(self,side,after,ts):
        v=self._insurance_confirm.get(side)
        return v if v and v[0]>after and v[1]<=ts and self._insurance_quote_seq>=v[2] and 0<=ts-v[0]<=60*MINUTE else None

    def _insurance_check(self,tick,c):
        s=self._insurance_cycle;ep=self._domain.episode;ts=tick.ts_event
        if s is None or ep is None or s['episode_id']!=ep.id:return
        positions={p.instrument_id:p for p in self.cache.positions_open()}
        btc=positions.get(self.config.btc_id);sol=positions.get(self.config.sol_id)
        bqty=btc.quantity.as_decimal() if btc else D(0);held=sol.quantity.as_decimal() if sol else D(0)
        if tick.instrument_id==self.config.sol_id:self._insurance_quote_seq+=1
        c['active']=bool(bqty);c['original_target']=D(0)
        if not bqty:
            # Confirmed BTC-flat invalidates old resting target leaves, not a new signal.
            self._discard_queued_intents(lambda i:i.action=='BTC_REDUCE')
            for order in list(self.cache.orders_open()):
                if order.instrument_id==self.config.btc_id and order.is_reduce_only:self.cancel_order(order)
            if not s['closed']:
                s['closed']=True;s['target']=D(0);s['recovery_fraction']=D(0)
                self._insurance_emit('BTC_FLAT',ts,actual_SOL=held)
            c['qc']=D(0)
            return self._conditional_reconcile(tick,c,ep,btc,sol,held,bqty,D(0),ts)
        bm=self._latest_marks.get(self.config.btc_id);sm=self._latest_marks.get(self.config.sol_id)
        if s['k'] is None or not all(m is not None and 0<=ts-m.ts_event<=self.config.max_mark_age_ns for m in (bm,sm)):return
        if s['side']==1:s['extreme']=max(s['extreme'],bm.price)
        else:s['extreme']=min(s['extreme'],bm.price)
        adverse=self._insurance_adverse(bm.price)
        if tick.instrument_id!=self.config.sol_id:return
        hedge=-s['side'];reverse=self._insurance_confirmation(-hedge,s['last_change_ns'],ts)
        confirm=self._insurance_confirmation(hedge,s['first_fill_ns'],ts)
        spnl,sfee=self._insurance_pnl(self.config.sol_id,ts)
        bpnl,bfee=self._insurance_pnl(self.config.btc_id,ts)
        reduced=False
        if s['recovery_fraction'] and ((spnl is not None and spnl>=sfee) or reverse):
            s['recovery_fraction']=D(0);s['last_change_ns']=ts;reduced=True
            self._insurance_emit('RECOVERY_RELEASE',ts,sol_native_pnl=spnl,estimated_close_fee=sfee,funding='UNKNOWN')
        # Ordinary recovery removes extra adverse stages, never the base floor.
        if not reduced and adverse<D('.25') and reverse and s['fraction']>s['base']:
            s['fraction']=s['base'];reduced=True
        elif not reduced and reverse and spnl is not None and spnl>sfee:
            s['fraction']=self._insurance_lower(s['fraction']);reduced=True
        elif not reduced and s['fraction']>s['base_full'] and spnl is not None and spnl>sfee and s['equity_start'] is not None and bfee is not None and self._v3_equity()-sfee-bfee>=s['equity_start']:
            # At most one pre-reversal harvest per new adversity/increase state.
            if s['last_harvest_ns']<s['last_change_ns']:
                s['fraction']=self._insurance_lower(s['fraction']);reduced=True
        if reduced:
            s['rearm_adverse']=adverse;s['arm']=None;s['recovery_arm']=None
            s['last_change_ns']=ts;s['last_harvest_ns']=ts
            self._insurance_emit('HARVEST_OR_RECOVERY',ts,adverse_sigma=adverse,sol_native_pnl=spnl,estimated_close_fee=sfee)
        if not reduced:
            top=s['base_full']*3 if adverse>=1 else s['base_full']*2 if adverse>=D('.5') else s['base']
            if not s['light'] and s['base']<s['base_full']:top=max(top,s['base_full'])
            can_rearm=s['rearm_adverse'] is None or adverse>s['rearm_adverse']
            if top>s['fraction'] and can_rearm:
                if s['arm'] is None:s['arm']=(ts,top)
                receipt=self._insurance_confirmation(hedge,s['arm'][0],ts)
                if receipt:
                    s['fraction']=top
                    if not s['light']:s['base']=s['base_full']
                    s['last_change_ns']=ts;s['arm']=None;s['rearm_adverse']=None
                    self._insurance_emit('ADVERSE_STAGE',ts,adverse_sigma=adverse,bar_close_ns=receipt[0],confirmation_received_ns=receipt[1],timeframe_minutes=receipt[3])
            else:s['arm']=None
            if self.config.research_immediate_sol=='i25-recovery' and not s['recovery_used'] and bpnl is not None and bpnl>0 and spnl is not None and spnl<0:
                if s['recovery_arm'] is None:s['recovery_arm']=ts
                receipt=self._insurance_confirmation(hedge,s['recovery_arm'],ts)
                recovery=min(D('.5'),s['fraction']+s['base'])
                if receipt and recovery>s['fraction']:
                    s['recovery_used']=True;s['recovery_fraction']=recovery;s['last_change_ns']=ts
                    self._insurance_emit('RECOVERY_ADD',ts,btc_native_pnl=bpnl,sol_native_pnl=spnl,bar_close_ns=receipt[0],funding='UNKNOWN')
            else:s['recovery_arm']=None
        fraction=max(s['fraction'],s['recovery_fraction'])
        if s['latch_btc']!=bqty or s['latch_fraction']!=fraction:
            step=self.cache.instrument(self.config.sol_id).size_increment.as_decimal()
            s['target']=(fraction*bqty*bm.price*s['k']/sm.price//step)*step
            s['latch_btc']=bqty;s['latch_fraction']=fraction
            self._insurance_emit('TARGET_LATCH',ts,btc_remaining=bqty,btc_mark=bm.price,sol_mark=sm.price,target_qty=s['target'],actual_SOL=held,adverse_sigma=adverse)
        c['qc']=s['target']
        return self._conditional_reconcile(tick,c,ep,btc,sol,held,bqty,s['target'],ts)

    def _insurance_lower(self,fraction):
        s=self._insurance_cycle
        if fraction>s['base_full']*2:return s['base_full']*2
        if fraction>s['base_full']:return s['base']
        if fraction>s['floor']:
            s['base']=s['floor'];return s['floor']
        return fraction

    def _insurance_report(self):
        def safe(x):
            if isinstance(x,D):return str(x)
            if isinstance(x,dict):return {str(k):safe(v) for k,v in x.items()}
            if isinstance(x,(list,tuple,set)):return [safe(v) for v in x]
            return x
        if self._insurance_cycle and not self.cache.positions_open() and not self._pending_by_order:
            self._insurance_cycle['closed']=True;self._insurance_cycle['target']=D(0)
        return {'audit':self.insurance_audit,'cycles':safe(self.insurance_cycles),'funding_asset_attribution':'UNKNOWN_NATIVE_AUDIT_HAS_NO_COMPONENT_CASH_DELTA'}
