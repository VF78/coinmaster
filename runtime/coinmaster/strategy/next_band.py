"""Bounded B follow-ups: policy state only; existing native executor owns orders."""
from decimal import Decimal as D, ROUND_CEILING, ROUND_FLOOR
from math import isfinite
from coinmaster.venues.signals import DailySignalBar
from nautilus_trader.model.data import CustomData, DataType

class NextClosedBar(DailySignalBar):
    """Decision-only OHLC; never a native matching Bar."""
    def __init__(self,instrument_id,hours,open_,high,low,close,ts_event,ts_init=None):
        super().__init__(instrument_id,open_,high,low,close,ts_event,ts_init)
        if hours not in (1,4) or ts_event % (hours*3_600_000_000_000) or self.ts_init<ts_event:
            raise ValueError('NEXT_REQUIRES_CAUSAL_CLOSED_UTC_BAR')
        if not (0<self.low<=min(self.open,self.close)<=max(self.open,self.close)<=self.high):raise ValueError('NEXT_INVALID_REAL_OHLC')
        self.hours=hours
        self.open_time_ns=ts_event-hours*3_600_000_000_000

def next_bar_type(instrument_id,hours):
    return DataType(NextClosedBar,dict(instrument_id=str(instrument_id),hours=hours))

def next_closed_bar(instrument_id,hours,open_,high,low,close,ns):
    return CustomData(next_bar_type(instrument_id,hours),NextClosedBar(instrument_id,hours,open_,high,low,close,ns))


DAY=86_400_000_000_000
H4=DAY//6
H1=DAY//24
Z_REASON='ZERO_RETRACE_RISK'
S_REASON='SOL_DOMINANT_ADVERSE_RISK'

class NextBandResearch:
    def _next_init(self):
        c=self.config
        self.next_band_audit=[]
        self._next_enabled=bool(c.research_wait_4h or c.research_wait_persist or c.research_zero_retrace or c.research_sol_dominant)
        if self._next_enabled and (c.research_regime_reentry_band != D('.5') or c.research_h4_ema is not None or c.research_sol_btc_open_only):
            raise ValueError('NEXT_REQUIRES_ORIGINAL_B')
        if c.research_wait_4h and c.research_wait_persist:raise ValueError('E4_EP_EXCLUSIVE')
        self._next_bars=[]
        self._next_last_bar={}
        self._next_daily_ns=None
        self._next_daily_side=None
        self._next_count=0
        self._next_wait=False
        self._next_release=None
        self._next_peak=D(str(c.active_seed))
        self._next_equity=None
        self._next_equity_ns=None
        self._next_z=None
        self._next_s=None
        self._next_risk_intents={}
        self._next_entry_terminal={}

    def _next_log(self,event,ns,**kw):
        self.next_band_audit.append(dict(event=event,timestamp_ns=int(ns),**kw))

    def _next_terminal(self,intent,ns):
        if self._next_enabled and intent is not None and intent.action=='BTC_ENTRY':
            self._next_entry_terminal[intent.episode_id]=max(ns,self._next_entry_terminal.get(intent.episode_id,0))

    def _next_observe_settled(self,equity,ns,source):
        if not self._next_enabled:return
        self._next_equity=D(str(equity));self._next_equity_ns=ns
        self._next_peak=max(self._next_peak,self._next_equity)

    def _next_daily(self):
        if not self._next_enabled:return
        ns=self._last_accepted_session
        if not self._hb_wait_regime:
            self._next_count=0;self._next_daily_ns=None;self._next_wait=False
            return
        if ns==self._next_daily_ns:return
        side=self._current_signals[-1].side
        contiguous=self._next_daily_ns is not None and ns==self._next_daily_ns+DAY
        self._next_count=self._next_count+1 if contiguous and side==self._next_daily_side else 1
        self._next_daily_ns=ns;self._next_daily_side=side;self._next_wait=True
        self._next_log('WAIT_D1_COUNT',ns,count=self._next_count,side=side)

    def _next_wait_allowed(self,side,close,ema,atr,ns,original):
        if not self._next_enabled:return original
        self._next_daily()
        distance=side*(close-ema)/atr
        ep=self.config.research_wait_persist and self._next_count>=2 and distance>=.25
        e4=self.config.research_wait_4h and self._next_release is not None and self._next_release['daily_ns']==ns
        allowed=original or ep or e4
        self._next_log('WAIT_PERMISSION',self.clock.timestamp_ns(),signal_asof_ns=ns,side=side,distance=distance,count=self._next_count,original=original,EP=bool(ep),E4=bool(e4),allowed=bool(allowed))
        return allowed

    def _next_closed_bar(self,bar):
        if not self._next_enabled:return
        ns=bar.ts_event
        instrument=getattr(bar,'instrument_id',None);hours=getattr(bar,'hours',None)
        if hours is None:instrument=bar.bar_type.instrument_id;hours=bar.bar_type.spec.step
        key=(str(instrument),hours)
        if ns<=self._next_last_bar.get(key,0):return
        self._next_last_bar[key]=ns
        close=bar.close.as_decimal() if hasattr(bar.close,'as_decimal') else D(bar.close)
        self._next_bars.append((ns,instrument,hours,close))

    def _next_busy(self,instrument,increases_only=False):
        def applies(i):return (i.action.startswith('BTC') if instrument==self.config.btc_id else i.action.startswith('SOL')) and (not increases_only or i.action in ('BTC_ENTRY','SOL_ADD'))
        return (any(applies(i) for i in self._pending_by_order.values()) or any(applies(i) for i,_,_ in self._queued_intents)
            or any(o.instrument_id==instrument and (not increases_only or not o.is_reduce_only) for o in self.cache.orders_open()+self.cache.orders_inflight()))

    def _next_higher(self,instrument):
        if self._forced_close_reason or self._liquidating or self._mandatory_sol_exit is not None:return True
        def ordinary(i):
            if not ((i.action.startswith('BTC') if instrument==self.config.btc_id else i.action.startswith('SOL')) and i.reason not in (Z_REASON,S_REASON) and i.action not in ('BTC_ENTRY','SOL_ADD')):return False
            if instrument==self.config.btc_id and i.action=='BTC_REDUCE' and i.limit_price is not None:
                q=self.cache.quote_tick(instrument)
                if q is not None and (q.bid_price.as_decimal()<D(str(i.limit_price)) if i.side==-1 else q.ask_price.as_decimal()>D(str(i.limit_price))):return False
            return True
        return any(ordinary(i) for i in self._pending_by_order.values()) or any(ordinary(i) for i,_,_ in self._queued_intents)

    def _next_risk_busy(self,task,instrument):
        if task['kind']!='Z':return self._next_busy(instrument)
        def harmless(i):
            ep=self._domain.episode
            return (ep is not None and i.action=='BTC_REDUCE' and i.limit_price is not None and i.level is not None and ep.wave_levels[i.level]>0)
        if any(i.action.startswith('BTC') and not harmless(i) for i in self._pending_by_order.values()):return True
        if any(i.action.startswith('BTC') for i,_,_ in self._queued_intents):return True
        for o in self.cache.orders_open()+self.cache.orders_inflight():
            if o.instrument_id!=instrument:continue
            i=self._pending_by_order.get(str(o.client_order_id))
            if i is None or not harmless(i):return True
        return False

    def _next_cancel_task(self,task,ns,reason):
        if not task:return
        task['canceled']=True
        for oid,i in list(self._pending_by_order.items()):
            if self._next_risk_intents.get(i.id) is task:
                order=self.cache.order(next((o.client_order_id for o in self.cache.orders_open()+self.cache.orders_inflight() if str(o.client_order_id)==oid),None)) if any(str(o.client_order_id)==oid for o in self.cache.orders_open()+self.cache.orders_inflight()) else None
                if order is not None and not order.is_pending_cancel:self.cancel_order(order)
        self._next_log('RISK_PREEMPT',ns,kind=task['kind'],reason=reason)

    def _next_sol_cancel_adds(self):
        self._discard_queued_intents(lambda i:i.action=='SOL_ADD')
        for o in self.cache.orders_open()+self.cache.orders_inflight():
            if o.instrument_id==self.config.sol_id and not o.is_reduce_only and not o.is_pending_cancel:self.cancel_order(o)

    def _next_before_submit(self,intent,ns):
        if not self._next_enabled:return True
        if intent.action=='SOL_ADD':
            if self._next_s is not None:
                self._domain.on_parent_terminal(intent.id);self._next_log('S_BLOCK_INCREASE',ns,episode_id=intent.episode_id);return False
            if self._next_z is not None:
                self._next_cancel_task(self._next_z,ns,'SOL_INCREASE')
                if any(self._next_risk_intents.get(i.id) is self._next_z for i in self._pending_by_order.values()):return False
        instrument=self.config.btc_id if intent.action.startswith('BTC') else self.config.sol_id
        task=self._next_z if instrument==self.config.btc_id else self._next_s
        if task and intent.reason not in (Z_REASON,S_REASON) and intent.action not in ('BTC_ENTRY','SOL_ADD'):
            self._next_cancel_task(task,ns,'ORDINARY_OR_MANDATORY_REDUCTION')
            return not any(self._next_risk_intents.get(i.id) is task for i in self._pending_by_order.values())
        return True

    def _next_z_state(self,ns):
        ep=self._domain.episode;p=self._split_parent;btc=self._hb_position(self.config.btc_id)
        if not ep or not p or not btc or not p.get('closed') or self._split_unfinished() or self._next_busy(self.config.btc_id,True):return None
        audit=next((a for a in self.entry_sizing_audit if a.get('episode_id')==ep.id),None)
        if not audit or audit.get('branch')!='MARKETABLE_FULL_ENTRY_FALLBACK':return None
        if self._hb_position(self.config.sol_id) or self._next_busy(self.config.sol_id,True) or self._next_higher(self.config.btc_id):return None
        if any(ep.btc_tp_filled_lots.values()):return None
        self._domain._ensure_btc_targets(ep)
        slots={k:max(0,v-ep.btc_tp_filled_lots.get(k,0)-ep.btc_risk_retired_lots.get(k,0)) for k,v in ep.btc_tp_target_lots.items() if ep.wave_levels[k]==0 and k not in ep.btc_omitted_zero_levels}
        if not sum(slots.values()):return None
        inst=self.cache.instrument(self.config.btc_id);a=ep.btc_entry_notional_exact/ep.btc_entry_qty_exact;c=ep.btc_entry_fees_exact/ep.btc_entry_qty_exact;fee=inst.taker_fee
        be=(a+c)/(1-fee) if ep.side==1 else (a-c)/(1+fee);p0=ep.btc_planref_vwap
        if p0 is None:return None
        step=inst.price_increment.as_decimal();g=max(p0,be) if ep.side==1 else min(p0,be)
        g=(g/step).to_integral_value(rounding=ROUND_CEILING if ep.side==1 else ROUND_FLOOR)*step
        return dict(kind='Z',episode_id=ep.id,side=ep.side,G=g,slots=slots,canceled=False,triggered=False,armed=False,entry_terminal_ns=self._next_entry_terminal.get(ep.id,ns))

    def _next_process_bars(self,ns):
        # Explicit delivery buffer: at a common timestamp accepted D1 is already
        # processed by the data callback before the first quote consumes these.
        ready=[b for b in self._next_bars if b[0]<=ns];self._next_bars=[b for b in self._next_bars if b[0]>ns]
        for bar_ns,instrument,step,close in ready:
            self._next_log('CLOSED_BAR',ns,signal_asof_ns=bar_ns,instrument=str(instrument),hours=step,close=str(close))
            if step==4 and instrument==self.config.btc_id:
                if self.config.research_wait_4h and self._hb_wait_regime and self._domain.episode is None:
                    # Original chain calculates EMA/ATR and logs its latest state.
                    self._hedge_band_allowed()
                    state=next((x for x in reversed(self.hedge_band_audit) if 'atr14' in x),None)
                    if state and bar_ns>getattr(self,'_next_latch_ns',0) and state['timestamp_ns']==self._last_accepted_session and state['atr14']>0 and state['side']*(float(close)-state['ema'])/state['atr14']>=.5:
                        self._next_release=dict(daily_ns=self._last_accepted_session,signal_asof_ns=bar_ns)
                        self._next_intraday_entry(ns)
                if self.config.research_zero_retrace:
                    fresh=self._next_z_state(ns);ep=self._domain.episode
                    if self._next_z is None or (ep and self._next_z['episode_id']!=ep.id):self._next_z=fresh
                    z=self._next_z
                    if fresh and z and not z['triggered'] and not z['canceled'] and bar_ns>z['entry_terminal_ns']:
                        tick=self.cache.instrument(self.config.btc_id).price_increment.as_decimal()
                        if z['side']*(close-z['G'])>=tick:
                            z['armed']=True;z['armed_ns']=ns;self._next_log('Z_ARM',ns,signal_asof_ns=bar_ns,episode_id=z['episode_id'],G=str(z['G']),slots=z['slots'])
            if step==1 and instrument==self.config.sol_id and self.config.research_sol_dominant:self._next_s_signal(bar_ns,close,ns)

    def _next_intraday_entry(self,ns):
        if self._domain.episode is not None or self.cache.positions_open() or self.cache.orders_open() or self.cache.orders_inflight() or self._pending_by_order or self._queued_intents or self._forced_close_reason or self._liquidating or not self._entries_enabled():return
        if not self._hedge_band_allowed():return
        bm=self._latest_marks.get(self.config.btc_id);sm=self._latest_marks.get(self.config.sol_id)
        if bm is None or sm is None:return
        self._bind_native_lots()
        intents=self._domain.decide(self._bars,self._current_signals,len(self._bars)-1,self._active_marked(bm,sm),btc_notional_multiplier=self._research_btc_entry_multiplier())
        for i in intents:
            if i.action!='BTC_ENTRY':raise ValueError('INTRADAY_ENTRY_ONLY')
            self._queued_intents.append((i,self._current_signals[-1].sigma,len(self._bars)-1));self._queued_intent_ready_ns[i.id]=ns
            self._next_log('E4_ENTRY_INTENT',ns,signal_asof_ns=self._next_release['signal_asof_ns'],daily_asof_ns=self._last_accepted_session,episode_id=i.episode_id)

    def _next_s_signal(self,bar_ns,close,ns):
        if self._next_s is not None:return
        btc=self._hb_position(self.config.btc_id);sol=self._hb_position(self.config.sol_id);p=self._split_parent;ep=self._domain.episode
        if btc is None or sol is None or p is None or ep is None or btc.is_long==sol.is_long or self._next_higher(self.config.sol_id):return
        beta=p.get('planref_v1_beta');bm=self._latest_marks.get(self.config.btc_id);sm=self._latest_marks.get(self.config.sol_id)
        if beta is None or not isfinite(beta) or not .2<beta<4 or bm is None or sm is None or self._next_equity is None or self._next_equity_ns is None or self._next_equity_ns>ns:return
        if D(str(beta))*sol.quantity.as_decimal()*sm.price<=btc.quantity.as_decimal()*bm.price:return
        if 1-self._next_equity/self._next_peak<D('.4'):return
        side=1 if sol.is_long else -1
        if -side*(close/D(str(sol.avg_px_open))-1)<D('.02'):return
        step=self.cache.instrument(self.config.sol_id).size_increment.as_decimal();held=sol.quantity.as_decimal();remaining=(held*D('.5')//step)*step
        self._next_s=dict(kind='S',episode_id=ep.id,side=side,remaining=remaining,triggered=True,canceled=False)
        self._next_sol_cancel_adds();self._next_log('S_TRIGGER',ns,signal_asof_ns=bar_ns,held=str(held),desired_remaining=str(remaining),beta=beta,settled_equity=str(self._next_equity),peak=str(self._next_peak))

    def _next_quote(self,tick):
        if not self._next_enabled:return
        ns=tick.ts_event
        if self.config.terminal_close_at_ns is not None and ns>=self.config.terminal_close_at_ns:return
        self._next_daily();self._next_process_bars(ns)
        if self._next_z and not self._next_z['canceled']:
            z=self._next_z;fresh=self._next_z_state(ns)
            if not fresh:self._next_cancel_task(z,ns,'ELIGIBILITY_CHANGED')
            elif z.get('armed') and not z['triggered'] and ns>z['armed_ns'] and tick.instrument_id==self.config.btc_id:
                executable=tick.bid_price.as_decimal() if z['side']==1 else tick.ask_price.as_decimal()
                if z['side']*(executable-z['G'])<=0:
                    z['triggered']=True;self._next_log('Z_TRIGGER',ns,episode_id=z['episode_id'],G=str(z['G']),actual_quote=str(executable),slots=z['slots'])
        if self._next_s:self._next_sol_cancel_adds()
        for task,instrument in ((self._next_z,self.config.btc_id),(self._next_s,self.config.sol_id)):
            if not task or task['canceled'] or not task['triggered'] or tick.instrument_id!=instrument:continue
            if self._next_higher(instrument):self._next_cancel_task(task,ns,'HIGHER_PRIORITY');continue
            if self._next_risk_busy(task,instrument):continue
            ep=self._domain.episode;position=self._hb_position(instrument)
            if ep is None or ep.id!=task['episode_id'] or position is None:continue
            step=self.cache.instrument(instrument).size_increment.as_decimal()
            if task['kind']=='Z':qty=min(position.quantity.as_decimal(),D(sum(task['slots'].values()))*step)
            else:qty=max(D(0),position.quantity.as_decimal()-task['remaining'])
            qty=(qty//step)*step
            if qty<=0:continue
            intent=self._domain._intent(ep,'BTC_REDUCE' if task['kind']=='Z' else 'SOL_EXIT',-task['side'],None,quantity=float(qty),reason=Z_REASON if task['kind']=='Z' else S_REASON)
            self._next_risk_intents[intent.id]=task
            self._next_log('RISK_CHILD',ns,kind=task['kind'],quantity=str(qty),intent_id=intent.id)
            self._submit_intent(intent,float(tick.bid_price),float(tick.ask_price),None,len(self._bars)-1,ts_now=ns)
        if self._next_s and self._hb_position(self.config.sol_id) is None and not self._next_busy(self.config.sol_id):self._next_s=None

    def _next_risk_fill(self,intent,quantity,ns):
        task=self._next_risk_intents.get(intent.id)
        if task is None:return False
        ep=self._domain.episode
        if ep is None or ep.id!=intent.episode_id:raise ValueError('RISK_FILL_LOST_EPISODE')
        if task['kind']=='Z':
            step=self.cache.instrument(self.config.btc_id).size_increment.as_decimal();lots=self._domain._lots(quantity,step);left=lots
            for level in sorted(task['slots']):
                take=min(left,task['slots'][level]);task['slots'][level]-=take;ep.btc_risk_retired_lots[level]=ep.btc_risk_retired_lots.get(level,0)+take;left-=take
            if left:raise ValueError('RISK_FILL_EXCEEDS_FROZEN_ZERO_TARGET')
            ep.btc_open_qty=max(0,ep.btc_open_qty-quantity)
        else:ep.sol_qty=max(0,ep.sol_qty-quantity)
        self._next_log('RISK_FILL',ns,kind=task['kind'],quantity=quantity,episode_id=ep.id,retired_lots=dict(ep.btc_risk_retired_lots))
        return True
