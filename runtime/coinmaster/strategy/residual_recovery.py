"""Default-off bounded C1 lifecycle. Native strategy executor owns every order."""
from decimal import Decimal as D
from nautilus_trader.model.enums import OrderSide

H4=14_400_000_000_000
CUT='C1_RESIDUAL_CUT'
RESTORE='C1_RESIDUAL_RESTORE'

class ResidualRecoveryResearch:
    def _c1_init(self):
        if self.config.research_c1_btc_cut_divisor not in (2,4):raise ValueError('C1_BTC_CUT_DIVISOR_MUST_BE_2_OR_4')
        if self.config.research_c1_restore_dd not in (D(".35"),D(".40")):raise ValueError("C1_RESTORE_DD_MUST_BE_35_OR_40")
        if self.config.research_c1_global_cut_arm and (self.config.research_c1_btc_cut_divisor!=2 or self.config.research_c1_restore_dd!=D('.35')):raise ValueError('G_STANDALONE_REQUIRES_C1_HALF_RESTORE35')
        if getattr(self.config,'research_c1_first_fresh_h4',False) and (not self.config.research_residual_recovery or self.config.research_c1_btc_cut_divisor!=4 or self.config.research_c1_restore_dd!=D('.40') or self.config.research_c1_global_cut_arm):raise ValueError('FIRST_FRESH_REQUIRES_COMBO_Q_R_NO_G')
        if getattr(self.config,'research_c1_btc_postcut_d1',False) and (not getattr(self.config,'research_c1_first_fresh_h4',False) or self.config.research_c1_btc_cut_divisor!=4 or self.config.research_c1_restore_dd!=D('.40') or self.config.research_c1_global_cut_arm):raise ValueError('BTC_POSTCUT_D1_REQUIRES_FIRST_FRESH_COMBO')
        self._c1_global_cut_armed=True
        self._c1_global_rearm_blocked_source=None
        self.c1_audit=[];self._c1_state=None;self._c1_peak=D(str(self.config.active_seed))
        self._c1_checkpoint=None;self._c1_fill_epoch=0;self._c1_intents={};self._c1_last_bars={};self._c1_sol_levels={};self._c1_terminal_ids=set();self.c1_denials={};self._c1_blocked_ids=set()
        if self.config.research_residual_recovery and (not self.config.research_wait_4h or self.config.research_regime_reentry_band!=D('.5') or self.config.research_zero_retrace or self.config.research_sol_dominant or self.config.research_wait_persist):
            raise ValueError('C1_REQUIRES_CLEAN_E4')

    def _c1_log(self,event,ns,**kw):
        t=self._c1_state
        self.c1_audit.append(dict(event=event,sequence=len(self.c1_audit)+1,timestamp_ns=int(ns),group=t['group'] if t else None,state=t['state'] if t else 'IDLE',**kw))

    def _c1_rights(self):
        ep=self._domain.episode
        if ep is None:return None
        return dict(btc_targets=dict(ep.btc_tp_target_lots),btc_filled=dict(ep.btc_tp_filled_lots),btc_retired=dict(ep.btc_risk_retired_lots),sol_rights=sorted(ep.sol_rights),sol_right_fraction=dict(ep.sol_right_fraction),sol_held_lots=dict(self._c1_sol_levels.get(ep.id,{})),sol_consumed=dict(ep.sol_add_filled_notional),btc_open=str(ep.btc_open_qty),sol_open=str(ep.sol_qty),PLANREF=str(ep.btc_planref_vwap),H=str(ep.h))

    def _c1_own_pending(self):
        return any(i.id in self._c1_intents for i in self._pending_by_order.values())

    def _c1_cancel_owned(self):
        for o in self.cache.orders_open()+self.cache.orders_inflight():
            i=self._pending_by_order.get(str(o.client_order_id))
            if i is not None and i.id in self._c1_intents and not o.is_pending_cancel:self.cancel_order(o)

    def _c1_revoke(self,ns,reason):
        t=self._c1_state
        if not t or t['state']=='RELEASED':return
        if t['revoked']:return
        if getattr(self.config,'research_c1_first_fresh_h4',False):t.pop('first_fresh_deferred',None)
        t['revoked']=True;t['credit']=0;t['state']='REVOKED'
        self._c1_cancel_owned();self._c1_log('TOKEN_REVOKED',ns,reason=reason,rights=self._c1_rights())

    def _c1_native_fill(self,event):
        if not self.config.research_residual_recovery:return
        self._c1_fill_epoch+=1
        i=self._pending_by_order.get(str(event.client_order_id))
        if i is None or i.id not in self._c1_intents:self._c1_revoke(event.ts_event,'ACTUAL_ORDINARY_OR_MANDATORY_FILL')
        else:self._c1_log('NATIVE_FILL_RECEIPT',event.ts_event,order_id=str(event.client_order_id),trade_id=str(event.trade_id),intent_id=i.id,quantity=str(event.last_qty),price=str(event.last_px),commission=str(event.commission))

    def _c1_harmless_tp(self,i):
        if i.action!='BTC_REDUCE' or i.limit_price is None:return False
        q=self.cache.quote_tick(self.config.btc_id)
        if q is None:return False
        p=D(str(i.limit_price))
        return q.bid_price.as_decimal()<p if i.side==-1 else q.ask_price.as_decimal()>p

    def _c1_conflict(self):
        if self._forced_close_reason or self._liquidating or self._mandatory_sol_exit is not None:return True
        for i in list(self._pending_by_order.values())+[x[0] for x in self._queued_intents]:
            if i.id in self._c1_intents:continue
            if i.action in ('BTC_ENTRY','SOL_ADD') or not self._c1_harmless_tp(i):return True
        known=set(self._pending_by_order)
        return any(str(o.client_order_id) not in known for o in self.cache.orders_open()+self.cache.orders_inflight())

    def _c1_current_money(self,ns):
        c=self._c1_checkpoint
        if not c or not c['source']<c['receipt']<=ns or ns-c['source']>self.config.max_mark_age_ns or c['epoch']!=self._c1_fill_epoch:return None
        account=self.cache.account_for_venue(self.config.btc_id.venue)
        if account is None or account.last_event.ts_event>c['source']:return None
        return c

    def _c1_update_global_cut_arm(self,ns):
        if not self.config.research_c1_global_cut_arm or self._c1_global_cut_armed:return
        c=self._c1_current_money(ns)
        if c is None or c['DD']>D('.35'):return
        if self._c1_own_pending() or self.cache.orders_inflight():
            # An ACK/terminal later cannot reuse a remembered recovery quote.
            old=self._c1_global_rearm_blocked_source
            self._c1_global_rearm_blocked_source=max(c['source'],old if old is not None else c['source'])
            return
        if self._c1_global_rearm_blocked_source is not None and c['source']<=self._c1_global_rearm_blocked_source:return
        self._c1_global_cut_armed=True
        self._c1_global_rearm_blocked_source=None
        self._c1_log('GLOBAL_CUT_ARM_REARMED',ns,source_quote_ns=c['source'],DD=str(c['DD']),H=str(c['H']))

    def _c1_consume_global_cut_arm(self,cut_lots):
        if not self.config.research_c1_global_cut_arm:return
        if cut_lots<=0 or not self._c1_global_cut_armed:raise ValueError('G_CUT_ARM_COMMIT_INVALID')
        # Economically committed claim consumes before any submit/fill/ACK.
        self._c1_global_cut_armed=False

    def _c1_loss_candidates(self,details):
        """Shared native materializer: research supplies genuine mark OHLC."""
        from coinmaster.strategy.c1_inputs import C1PositionInput
        candidates=[]
        for row in details:
            if isinstance(row,C1PositionInput):
                inst=self.config.btc_id if row.instrument_id==str(self.config.btc_id) else self.config.sol_id
                if row.instrument_id not in (str(self.config.btc_id),str(self.config.sol_id)):raise ValueError('C1_INPUT_INSTRUMENT_SCOPE')
                pos=self._hb_position(inst)
                if (pos is None or str(pos.id)!=row.position_id or pos.ts_opened!=row.opened_ns
                    or pos.is_long!=row.is_long or pos.quantity.as_decimal()!=row.quantity
                    or self.cache.instrument(inst).size_increment.as_decimal()!=row.step):
                    raise ValueError('C1_INPUT_POSITION_MOVED')
                mark=row.mark;pnl=row.native_pnl
            else:
                inst=self.config.btc_id if row['instrument_id']==str(self.config.btc_id) else self.config.sol_id
                pos=self._hb_position(inst)
                if pos is None:continue
                mark=D(row['mark_ohlc']['close']);instrument=self.cache.instrument(inst)
                pnl=pos.unrealized_pnl(instrument.make_price(mark)).as_decimal()
            if pnl<0:candidates.append((pnl,0 if inst==self.config.btc_id else 1,inst,pos,mark))
        return candidates

    def _c1_observe(self,equity,ns,source,epoch,details,*,allow_peak_raise=True):
        if not self.config.research_residual_recovery:return
        E=D(str(equity))
        if not E.is_finite() or E<=0 or source>=ns:return
        if allow_peak_raise:self._c1_peak=max(self._c1_peak,E)
        self._c1_checkpoint=dict(E=E,H=self._c1_peak,DD=1-E/self._c1_peak,C=max(D(0),E-D('.5')*self._c1_peak),source=source,receipt=ns,epoch=epoch)
        self._c1_update_global_cut_arm(ns)
        ep=self._domain.episode;t=self._c1_state
        if t and (ep is None or ep.id!=t['group']):
            if self.cache.positions_open() or self.cache.orders_open() or self.cache.orders_inflight() or self._pending_by_order or self._queued_intents:raise ValueError('C1_GROUP_CHANGED_BEFORE_NATIVE_FLAT')
            self._c1_log('GROUP_FLAT_RESET',ns,credit_expired=t['credit']);self._c1_state=None;t=None
        if t:
            if t['state']=='REVOKED' and not self._c1_own_pending() and self._c1_checkpoint['DD']<=D('.35'):
                t['state']='RELEASED';self._c1_log('REVOKED_HOLD_RELEASE',ns)
            return
        c=self._c1_checkpoint
        if c['DD']<D('.4') or ep is None:return
        p=self._split_parent
        gates=dict(parent_complete=bool(p and p.get('episode_id')==ep.id and p.get('closed') and not self._split_unfinished()),no_competing_owner=not self._c1_conflict(),checkpoint_epoch=epoch==self._c1_fill_epoch)
        candidates=self._c1_loss_candidates(details)
        if not candidates:return
        pnl,_,inst,pos,mark=min(candidates,key=lambda x:(x[0],x[1]));loss=-pnl;gates['open_loss_dominates']=loss>c['C']
        if not gates['open_loss_dominates']:return
        step=self.cache.instrument(inst).size_increment.as_decimal();lots=int(pos.quantity.as_decimal()/step)
        cut_lots=lots//(self.config.research_c1_btc_cut_divisor if inst==self.config.btc_id else 2)
        gates['native_half_exists']=cut_lots>0
        if self.config.research_c1_global_cut_arm:gates['global_cut_armed']=self._c1_global_cut_armed
        if not all(gates.values()):
            from datetime import datetime,timezone
            key=str((ep.id,datetime.fromtimestamp(ns/1e9,timezone.utc).strftime('%Y-%m'),tuple(sorted(gates.items()))))
            old=self.c1_denials.get(key)
            if old is not None:old['count']+=1;old['last_ns']=ns;return
            self.c1_denials[key]=dict(count=1,first_ns=ns,last_ns=ns,gates=gates,group=ep.id)
        self._c1_log('PROPOSED_DECISION',ns,source_quote_ns=source,receipt_ns=ns,fill_epoch=epoch,E=str(E),H=str(c['H']),DD=str(c['DD']),cushion=str(c['C']),selected=str(inst),selected_loss=str(loss),positions=details,gates=gates,rights=self._c1_rights(),pending=[i.id for i in self._pending_by_order.values()])
        if not all(gates.values()):return
        self._domain._ensure_btc_targets(ep)
        self._c1_consume_global_cut_arm(cut_lots)
        self._c1_state=dict(group=ep.id,state='CUT_RESOLVING',instrument=inst,side=1 if pos.is_long else -1,step=step,held_lots=lots,target_lots=lots-cut_lots,cut_lots=cut_lots,cut_submitted=False,restore_submitted=False,cut_filled=0,restore_filled=0,credit=0,cut_value=D(0),bucket={},revoked=False,claim_ns=ns,native_position_id=str(pos.id),native_position_open_ns=pos.ts_opened,cut_terminal_ns=None,last_cut_fill_ns=None,confirmation=None)
        self._c1_log('CLAIM',ns,native_position_id=str(pos.id),native_position_open_ns=pos.ts_opened,frozen_held_lots=lots,frozen_target_lots=lots-cut_lots,rights=self._c1_rights())

    def _c1_observed_btc_d1(self,bar):
        if not getattr(self.config,'research_c1_btc_postcut_d1',False):return
        if bar.instrument_id!=(self.config.btc_signal_id or self.config.btc_id):return
        close=bar.ts_event;available=self.clock.timestamp_ns();init=bar.ts_init;day=86_400_000_000_000
        if type(close) is not int or type(init) is not int or close<=0 or close%day or not close<=init<=available:return
        try:values=[D(str(getattr(bar,k))) for k in ('open','high','low','close')]
        except (ValueError,TypeError,ArithmeticError):return
        o,h,l,c=values
        if not all(v.is_finite() for v in values) or not 0<l<=min(o,c)<=max(o,c)<=h:return
        old=self._c1_last_bars.get('BTC_POSTCUT_D1')
        if old is not None and close<=old['close_ns']:return
        self._c1_last_bars['BTC_POSTCUT_D1']=dict(open_ns=close-day,close_ns=close,available_ns=available,instrument=str(bar.instrument_id))

    def _c1_btc_postcut_d1_allowed(self,t,c,ns):
        if not getattr(self.config,'research_c1_btc_postcut_d1',False) or t['instrument']!=self.config.btc_id:return True
        bar=self._c1_last_bars.get('BTC_POSTCUT_D1');last=t.get('last_cut_fill_ns')
        return bool(bar and type(last) is int and bar['instrument']==str(self.config.btc_signal_id or self.config.btc_id)
                    and bar['open_ns']>=last and bar['close_ns']<=bar['available_ns']<=c['source']<=ns)

    def _c1_deferred_identity(self,t):
        # Actual lifecycle/fill identity; a stale money checkpoint is no authority.
        keys=('group','instrument','side','state','restore_submitted','native_position_id',
              'native_position_open_ns','cut_filled','cut_value','credit','bucket',
              'last_cut_fill_ns','cut_terminal_ns','revoked')
        return dict(values={k:(dict(t[k]) if k=='bucket' else t[k]) for k in keys},fill_epoch=self._c1_fill_epoch)

    def _c1_closed_bar(self,bar):
        if not self.config.research_residual_recovery or getattr(bar,'hours',None)!=4:return
        t=self._c1_state
        if not t or bar.instrument_id!=t['instrument']:return
        deferred=getattr(self.config,'research_c1_first_fresh_h4',False)
        if deferred:
            # Every NEW relevant H4 invalidates only the deferred market candidate.
            if bar.ts_event<=t.get('first_fresh_last_h4_ns',-1):return
            t['first_fresh_last_h4_ns']=bar.ts_event
            t.pop('first_fresh_deferred',None)
        if t['state']!='HELD' or not t['credit']:return
        if bar.open_time_ns<=max(t['last_cut_fill_ns'],t['cut_terminal_ns']):return
        close=bar.close.as_decimal() if hasattr(bar.close,'as_decimal') else D(str(bar.close))
        c=self._c1_current_money(bar.ts_event)
        reclaim=t['side']*(close-t['cut_value']/(D(t['cut_filled'])*t['step']))>0
        if deferred and c is None and reclaim and t['confirmation'] is None and not t['revoked'] and not t['restore_submitted']:
            t['first_fresh_deferred']=dict(close_ns=bar.ts_event,open_ns=bar.open_time_ns,close=close,
                available_ns=max(bar.ts_event,getattr(bar,'ts_init',bar.ts_event)),identity=self._c1_deferred_identity(t))
            self._c1_log('CLOSED_4H_DEFERRED_NO_MONEY',bar.ts_event,open_ns=bar.open_time_ns,close=str(close),actual_fill_epoch=self._c1_fill_epoch)
        if c is not None and c['DD']<=self.config.research_c1_restore_dd and reclaim:
            t['confirmation']=dict(close_ns=bar.ts_event,open_ns=bar.open_time_ns,close=close)
            self._c1_log('CLOSED_4H_RECLAIM',bar.ts_event,open_ns=bar.open_time_ns,close=str(close),DD=str(c['DD']))

    def _c1_first_fresh_quote(self,tick,c,*,decision_ns=None):
        if not getattr(self.config,'research_c1_first_fresh_h4',False):return
        t=self._c1_state;pending=t.get('first_fresh_deferred') if t else None
        if pending is None or tick.instrument_id!=t['instrument']:return
        evaluation_ns=tick.ts_event if decision_ns is None else decision_ns
        if evaluation_ns<=pending['available_ns'] or c['source']<pending['close_ns']:return
        # This first fresh evaluation consumes once, including on denial.
        t.pop('first_fresh_deferred')
        ep=self._domain.episode
        identity=(ep is not None and ep.id==t['group'] and pending['identity']==self._c1_deferred_identity(t)
                  and t['state']=='HELD' and not t['revoked'] and not t['restore_submitted'] and t['credit']>0 and t['confirmation'] is None)
        executable=tick.ask_price.as_decimal() if t['side']==1 else tick.bid_price.as_decimal()
        reclaim=t['side']*(executable-t['cut_value']/(D(t['cut_filled'])*t['step']))>0 if t['cut_filled'] else False
        if not identity or c['DD']>self.config.research_c1_restore_dd or not reclaim:
            self._c1_log('DEFERRED_4H_FIRST_FRESH_DENIED',evaluation_ns,identity=identity,current_reclaim=reclaim,DD=str(c['DD']))
            return
        t['confirmation']={k:pending[k] for k in ('close_ns','open_ns','close')}
        self._c1_log('DEFERRED_4H_FIRST_FRESH_CONFIRMED',evaluation_ns,close_ns=pending['close_ns'],source_quote_ns=c['source'],actual_fill_epoch=self._c1_fill_epoch,DD=str(c['DD']))

    def _c1_before_submit(self,i,ns):
        if not self.config.research_residual_recovery:return True
        t=self._c1_state
        if not t or t['state']=='RELEASED':return True
        if i.id in self._c1_intents:return True
        if i.action in ('BTC_ENTRY','SOL_ADD'):
            self._domain.on_parent_terminal(i.id);self._c1_log('NORMAL_INCREASE_BLOCKED',ns,intent_id=i.id,action=i.action,rights=self._c1_rights());return False
        if not self._c1_harmless_tp(i):
            self._c1_revoke(ns,'INDEPENDENT_ORDINARY_EXIT_DECISION')
            return not self._c1_own_pending()
        return True

    def _c1_bind_submission(self,i,oid,ns):
        if not self.config.research_residual_recovery or i.id not in self._c1_intents:return
        self._c1_state.setdefault('native_order_ids',{})[i.id]=oid
        self._c1_log('NATIVE_ORDER_SUBMITTED',ns,intent_id=i.id,order_id=oid,kind=self._c1_intents[i.id])

    def _c1_terminal(self,i,ns):
        if not self.config.research_residual_recovery or i is None or i.id not in self._c1_intents:return
        if i.id in self._c1_terminal_ids:return
        self._c1_terminal_ids.add(i.id)
        kind=self._c1_intents[i.id];t=self._c1_state
        if not t or i.episode_id!=t['group']:raise ValueError('C1_TERMINAL_LOST_GROUP')
        if kind=='CUT':
            t['cut_terminal_ns']=max(ns,t.get('cut_terminal_ns') or 0)
            if not t['revoked']:t['state']='HELD' if t['credit'] else 'RELEASED'
            t['targets_need_requeue']=True
        else:
            t['credit']=0
            if not t['revoked']:t['state']='RELEASED'
            t['targets_need_requeue']=True
        self._c1_log('ATTEMPT_TERMINAL',ns,kind=kind,intent_id=i.id,credit=t['credit'],rights=self._c1_rights())

    @staticmethod
    def _c1_allocate(available,lots):
        total=sum(available.values())
        if lots>total:raise ValueError('C1_ORIGINAL_LEVEL_LOTS_UNDERFLOW')
        if not lots:return {k:0 for k in available}
        allocation={k:lots*n//total for k,n in available.items()};left=lots-sum(allocation.values())
        for k in sorted(available):
            take=min(left,available[k]-allocation[k]);allocation[k]+=take;left-=take
        return allocation

    def _c1_fill(self,i,quantity,price,ns):
        if not self.config.research_residual_recovery:return False
        ep=self._domain.episode
        if i.id not in self._c1_intents:
            if ep is not None and i.action.startswith('SOL'):
                ledger=self._c1_sol_levels.setdefault(ep.id,{})
                lots=self._domain._lots(quantity,self.cache.instrument(self.config.sol_id).size_increment.as_decimal())
                if i.action=='SOL_ADD':ledger[i.level]=ledger.get(i.level,0)+lots
                else:
                    allocation=self._c1_allocate(ledger,lots)
                    for k,n in allocation.items():ledger[k]-=n
            return False
        t=self._c1_state
        if ep is None or not t or ep.id!=t['group']:raise ValueError('C1_FILL_LOST_GROUP')
        lots=self._domain._lots(quantity,t['step']);kind=self._c1_intents[i.id];before=self._c1_rights();credit_before=t['credit']
        if kind=='CUT':
            if t['cut_filled']+lots>t['cut_lots']:raise ValueError('C1_CUT_EXCEEDS_FIXED_TARGET')
            if t['instrument']==self.config.btc_id:
                available={k:max(0,n-ep.btc_tp_filled_lots.get(k,0)-ep.btc_risk_retired_lots.get(k,0)) for k,n in ep.btc_tp_target_lots.items()};total=sum(available.values())
                if lots>total:raise ValueError('C1_CUT_EXCEEDS_TP_LEAVES')
                allocation={k:lots*n//total for k,n in available.items()};left=lots-sum(allocation.values())
                for k in sorted(available):
                    take=min(left,available[k]-allocation[k]);allocation[k]+=take;left-=take
                for k,n in allocation.items():ep.btc_risk_retired_lots[k]=ep.btc_risk_retired_lots.get(k,0)+n;t['bucket'][k]=t['bucket'].get(k,0)+n
                ep.btc_open_qty=float(max(D(0),D(str(ep.btc_open_qty))-D(lots)*t['step']))
            else:
                ledger=self._c1_sol_levels.setdefault(ep.id,{})
                allocation=self._c1_allocate(ledger,lots)
                for k,n in allocation.items():ledger[k]-=n;t['bucket'][k]=t['bucket'].get(k,0)+n
                ep.sol_qty=float(max(D(0),D(str(ep.sol_qty))-D(lots)*t['step']))
            t['cut_filled']+=lots;t['cut_value']+=D(str(price))*D(lots)*t['step'];t['last_cut_fill_ns']=ns
            if not t['revoked']:t['credit']+=lots
        else:
            if lots>t.get('restore_committed',0)-t['restore_filled']:raise ValueError('C1_RESTORE_EXCEEDS_ACTUAL_CREDIT')
            if t['instrument']==self.config.btc_id:
                left=lots
                for k in sorted(t['bucket']):
                    take=min(left,t['bucket'][k]);t['bucket'][k]-=take;ep.btc_risk_retired_lots[k]-=take;left-=take
                    if take:ep.btc_tps.discard(k)
                if left:raise ValueError('C1_RESTORE_BUCKET_UNDERFLOW')
                ep.btc_open_qty=float(D(str(ep.btc_open_qty))+D(lots)*t['step'])
            else:
                ledger=self._c1_sol_levels.setdefault(ep.id,{})
                allocation=self._c1_allocate(t['bucket'],lots)
                for k,n in allocation.items():t['bucket'][k]-=n;ledger[k]=ledger.get(k,0)+n
                ep.sol_qty=float(D(str(ep.sol_qty))+D(lots)*t['step'])
            t['credit']=max(0,t['credit']-lots);t['restore_filled']+=lots
        self._c1_log('ACTUAL_FILL',ns,cut_attempts=int(t['cut_submitted']),restore_attempts=int(t['restore_submitted']),kind=kind,intent_id=i.id,lots=lots,price=str(price),credit_before=credit_before,credit=t['credit'],bucket=dict(t['bucket']),rights_before=before,rights_after=self._c1_rights())
        return True

    def _c1_terminal_flat(self,ns):
        if not self.config.research_residual_recovery or self._c1_state is None:return
        if self.cache.positions_open() or self.cache.orders_open() or self.cache.orders_inflight() or self._pending_by_order or self._queued_intents:return
        self._c1_log('TERMINAL_FLAT_CONFIRMED',ns,credit_expired=self._c1_state['credit'],native_positions=0,native_orders=0,native_inflight=0,pending=0,queued=0,H=str(self._c1_peak))
        self._c1_state=None

    def _c1_export_terminal(self):
        t=self._c1_state
        return dict(active_hold=bool(t and t['state']!='RELEASED'),credit=t['credit'] if t else 0,state=t['state'] if t else 'IDLE',group=t['group'] if t else None,H=str(self._c1_peak),native_positions=len(self.cache.positions_open()),native_orders=len(self.cache.orders_open()),native_inflight=len(self.cache.orders_inflight()),pending=len(self._pending_by_order),queued=len(self._queued_intents))

    def _c1_discard_increase(self,i,ns):
        if i.action not in ('BTC_ENTRY','SOL_ADD'):return False
        if i.id not in self._c1_blocked_ids:
            self._c1_blocked_ids.add(i.id);self._c1_log('QUEUED_INCREASE_BLOCKED',ns,intent_id=i.id,action=i.action,rights=self._c1_rights())
        return True

    def _c1_quote(self,tick,*,decision_ns=None):
        if not self.config.research_residual_recovery:return
        t=self._c1_state
        if not t:return
        ns=tick.ts_event if decision_ns is None else decision_ns
        if self.config.terminal_close_at_ns is not None and ns>=self.config.terminal_close_at_ns:self._c1_revoke(ns,'TERMINAL_BOUNDARY');return
        if self._forced_close_reason or self._liquidating or self._mandatory_sol_exit is not None:self._c1_revoke(ns,'MANDATORY_PRIORITY');return
        if t.get('targets_need_requeue') and not self._c1_own_pending():
            t['targets_need_requeue']=False
            if self._hb_position(self.config.btc_id) is not None:self._queue_confirmed_btc_targets(None,len(self._bars)-1,ns)
            self._c1_log('ORIGINAL_TP_LEAVES_REQUEUED',ns,rights=self._c1_rights())
        if t['state']=='RELEASED':return
        # A claim holds every group increase. Terminal cancel receipts retain
        # ownership until callbacks; no inferred cancellation or ACK completion.
        self._discard_queued_intents(lambda i:self._c1_discard_increase(i,ns))
        for o in self.cache.orders_open()+self.cache.orders_inflight():
            i=self._pending_by_order.get(str(o.client_order_id))
            if i is not None and i.id not in self._c1_intents and i.action in ('BTC_ENTRY','SOL_ADD') and not o.is_pending_cancel:self.cancel_order(o)
        if tick.instrument_id!=t['instrument'] or t['revoked']:return
        if self._c1_conflict():self._c1_revoke(ns,'ORDINARY_OR_UNKNOWN_COMPETING_OWNER');return
        c=self._c1_current_money(ns)
        if c is None:return
        self._c1_first_fresh_quote(tick,c,decision_ns=ns)
        if t['state']=='CUT_RESOLVING' and not t['cut_submitted']:
            for o in self.cache.orders_open()+self.cache.orders_inflight():
                i=self._pending_by_order.get(str(o.client_order_id))
                if i is not None and self._c1_harmless_tp(i) and not o.is_pending_cancel:self.cancel_order(o)
            if self._pending_by_order or self.cache.orders_open() or self.cache.orders_inflight() or self._queued_intents:return
            p=self._hb_position(t['instrument'])
            if p is None:self._c1_revoke(ns,'SELECTED_POSITION_DISAPPEARED');return
            if ns<=t['claim_ns']:return
            held=int(p.quantity.as_decimal()/t['step']);lots=min(t['cut_lots'],max(0,held-t['target_lots']))
            if lots<=0:self._c1_revoke(ns,'FROZEN_TARGET_ALREADY_REACHED');return
            kind='CUT';action='BTC_REDUCE' if t['instrument']==self.config.btc_id else 'SOL_EXIT';side=-t['side'];reason=CUT;t['cut_submitted']=True
        elif t['state']=='HELD' and not t['restore_submitted']:
            conf=t['confirmation']
            if not conf or ns<=conf['close_ns']:return
            if not self._c1_btc_postcut_d1_allowed(t,c,ns):return
            if c['DD']>self.config.research_c1_restore_dd:t['confirmation']=None;return
            vwap=t['cut_value']/(D(t['cut_filled'])*t['step']);executable=tick.ask_price.as_decimal() if t['side']==1 else tick.bid_price.as_decimal()
            if t['side']*(executable-vwap)<=0:
                t['confirmation']=None;self._c1_log('RESTORE_CURRENT_RECLAIM_FAILED',ns);return
            for o in self.cache.orders_open()+self.cache.orders_inflight():
                i=self._pending_by_order.get(str(o.client_order_id))
                if i is not None and self._c1_harmless_tp(i) and not o.is_pending_cancel:self.cancel_order(o)
            if self._pending_by_order or self.cache.orders_open() or self.cache.orders_inflight() or self._queued_intents:return
            lots=t['credit']
            if lots<=0:return
            instrument=self.cache.instrument(t['instrument']);quantity=D(lots)*t['step']
            minimum=(instrument.min_quantity is None or quantity>=instrument.min_quantity.as_decimal()) and (instrument.min_notional is None or quantity*executable>=instrument.min_notional.as_decimal())
            native_side=OrderSide.BUY if t['side']==1 else OrderSide.SELL
            if not minimum or not self._entries_enabled() or not self._tier_allows_increase(t['instrument'],native_side,quantity,ns):
                t['confirmation']=None;self._c1_log('RESTORE_NATIVE_ADMISSION_DENIED',ns,credit=t['credit']);return
            kind='RESTORE';action='BTC_RESTORE' if t['instrument']==self.config.btc_id else 'SOL_RESTORE';side=t['side'];reason=RESTORE;t['restore_submitted']=True;t['restore_committed']=lots;t['state']='RESTORE_RESOLVING'
        else:return
        ep=self._domain.episode
        if ep is None or ep.id!=t['group']:raise ValueError('C1_SUBMIT_LOST_GROUP')
        i=self._domain._intent(ep,action,side,None,quantity=float(D(lots)*t['step']),reason=reason);self._c1_intents[i.id]=kind
        self._c1_log('ATTEMPT_SUBMIT',ns,claim_ns=t['claim_ns'],confirmation=({**t['confirmation'],'close':str(t['confirmation']['close'])} if t['confirmation'] else None),kind=kind,intent_id=i.id,instrument=str(t['instrument']),side=side,original_side=t['side'],step=str(t['step']),lots=lots,quote_ns=tick.ts_event if decision_ns is None else decision_ns,bid=str(tick.bid_price),ask=str(tick.ask_price),executable_price=str(tick.ask_price if side==1 else tick.bid_price),E=str(c['E']),H=str(c['H']),DD=str(c['DD']),source_quote_ns=c['source'],receipt_ns=c['receipt'],fill_epoch=c['epoch'],current_fill_epoch=self._c1_fill_epoch,account_event_ns=self.cache.account_for_venue(self.config.btc_id.venue).last_event.ts_event,pending_ids=list(self._pending_by_order),native_open_orders=len(self.cache.orders_open()),native_inflight_orders=len(self.cache.orders_inflight()),queued_intents=len(self._queued_intents),cut_actual_vwap=str(t['cut_value']/(D(t['cut_filled'])*t['step'])) if t['cut_filled'] else None,cut_last_fill_ns=t['last_cut_fill_ns'],cut_terminal_ns=t['cut_terminal_ns'],native_admission='PASSED_EXISTING_INCREASE_GATES' if kind=='RESTORE' else 'REDUCE_ONLY_BYPASS',rights=self._c1_rights())
        self._submit_intent(i,float(tick.bid_price),float(tick.ask_price),None,len(self._bars)-1,ts_now=ns)
        self._c1_log('SUBMIT_OUTCOME',ns,intent_id=i.id,kind=kind,native_submitted=bool(t.get('native_order_ids',{}).get(i.id)),order_id=t.get('native_order_ids',{}).get(i.id),pending_native=any(x.id==i.id for x in self._pending_by_order.values()),terminal_receipt=i.id in self._c1_terminal_ids)
        if not any(x.id==i.id for x in self._pending_by_order.values()) and i.id not in self._c1_terminal_ids:
            if kind=='RESTORE' and not t.get('native_order_ids',{}).get(i.id):
                t['state']='HELD';t['restore_submitted']=False;t['restore_committed']=0;t['confirmation']=None
                self._c1_log('RESTORE_NOT_SUBMITTED',ns,intent_id=i.id,credit=t['credit'])
            else:self._c1_terminal(i,ns)
