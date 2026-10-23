from pathlib import Path
ROOT=Path('/root/.openclaw/workspace/coinmaster/coinmaster/research-worktrees/residual-recovery-20261023')
assert ROOT.exists()
def edit(rel,old,new,count=1):
 p=ROOT/rel;s=p.read_text();assert s.count(old)>=count,(rel,old[:90]);p.write_text(s.replace(old,new,count))
module='''"""Default-off bounded C1 lifecycle. Native strategy executor owns every order."""
from decimal import Decimal as D

H4=14_400_000_000_000
CUT='C1_RESIDUAL_CUT'
RESTORE='C1_RESIDUAL_RESTORE'

class ResidualRecoveryResearch:
    def _c1_init(self):
        self.c1_audit=[];self._c1_state=None;self._c1_peak=D(str(self.config.active_seed))
        self._c1_checkpoint=None;self._c1_fill_epoch=0;self._c1_intents={};self._c1_last_bars={}
        if self.config.research_residual_recovery and (not self.config.research_wait_4h or self.config.research_regime_reentry_band!=D('.5') or self.config.research_zero_retrace or self.config.research_sol_dominant or self.config.research_wait_persist):
            raise ValueError('C1_REQUIRES_CLEAN_E4')

    def _c1_log(self,event,ns,**kw):
        t=self._c1_state
        self.c1_audit.append(dict(event=event,sequence=len(self.c1_audit)+1,timestamp_ns=int(ns),group=t['group'] if t else None,state=t['state'] if t else 'IDLE',**kw))

    def _c1_rights(self):
        ep=self._domain.episode
        if ep is None:return None
        return dict(btc_targets=dict(ep.btc_tp_target_lots),btc_filled=dict(ep.btc_tp_filled_lots),btc_retired=dict(ep.btc_risk_retired_lots),sol_rights=sorted(ep.sol_rights),sol_consumed=dict(ep.sol_add_filled_notional),btc_open=str(ep.btc_open_qty),sol_open=str(ep.sol_qty),PLANREF=str(ep.btc_planref_vwap),H=str(ep.h))

    def _c1_own_pending(self):
        return any(i.id in self._c1_intents for i in self._pending_by_order.values())

    def _c1_cancel_owned(self):
        for o in self.cache.orders_open()+self.cache.orders_inflight():
            i=self._pending_by_order.get(str(o.client_order_id))
            if i is not None and i.id in self._c1_intents and not o.is_pending_cancel:self.cancel_order(o)

    def _c1_revoke(self,ns,reason):
        t=self._c1_state
        if not t or t['state']=='RELEASED':return
        t['revoked']=True;t['credit']=0;t['state']='REVOKED'
        self._c1_cancel_owned();self._c1_log('TOKEN_REVOKED',ns,reason=reason,rights=self._c1_rights())

    def _c1_native_fill(self,event):
        if not self.config.research_residual_recovery:return
        self._c1_fill_epoch+=1
        i=self._pending_by_order.get(str(event.client_order_id))
        if i is None or i.id not in self._c1_intents:self._c1_revoke(event.ts_event,'ACTUAL_ORDINARY_OR_MANDATORY_FILL')

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

    def _c1_observe(self,equity,ns,source,epoch,details):
        if not self.config.research_residual_recovery:return
        E=D(str(equity))
        if not E.is_finite() or E<=0 or source>=ns:return
        self._c1_peak=max(self._c1_peak,E)
        self._c1_checkpoint=dict(E=E,H=self._c1_peak,DD=1-E/self._c1_peak,C=max(D(0),E-D('.5')*self._c1_peak),source=source,receipt=ns,epoch=epoch)
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
        candidates=[]
        for row in details:
            inst=self.config.btc_id if row['instrument_id']==str(self.config.btc_id) else self.config.sol_id
            pos=self._hb_position(inst)
            if pos is None:continue
            mark=D(row['mark_ohlc']['close']);instrument=self.cache.instrument(inst)
            pnl=pos.unrealized_pnl(instrument.make_price(mark)).as_decimal()
            if pnl<0:candidates.append((pnl,0 if inst==self.config.btc_id else 1,inst,pos,mark))
        if not candidates:return
        pnl,_,inst,pos,mark=min(candidates,key=lambda x:(x[0],x[1]));loss=-pnl;gates['open_loss_dominates']=loss>c['C']
        if not gates['open_loss_dominates']:return
        step=self.cache.instrument(inst).size_increment.as_decimal();lots=int(pos.quantity.as_decimal()/step);gates['native_half_exists']=lots//2>0
        self._c1_log('PROPOSED_DECISION',ns,source_quote_ns=source,receipt_ns=ns,fill_epoch=epoch,E=str(E),H=str(c['H']),DD=str(c['DD']),cushion=str(c['C']),selected=str(inst),selected_loss=str(loss),positions=details,gates=gates,rights=self._c1_rights(),pending=[i.id for i in self._pending_by_order.values()])
        if not all(gates.values()):return
        self._domain._ensure_btc_targets(ep)
        self._c1_state=dict(group=ep.id,state='CUT_RESOLVING',instrument=inst,side=1 if pos.is_long else -1,step=step,held_lots=lots,target_lots=lots-lots//2,cut_lots=lots//2,cut_submitted=False,restore_submitted=False,cut_filled=0,restore_filled=0,credit=0,cut_value=D(0),bucket={},revoked=False,claim_ns=ns,cut_terminal_ns=None,last_cut_fill_ns=None,confirmation=None)
        self._c1_log('CLAIM',ns,frozen_held_lots=lots,frozen_target_lots=lots-lots//2,rights=self._c1_rights())

    def _c1_closed_bar(self,bar):
        if not self.config.research_residual_recovery or getattr(bar,'hours',None)!=4:return
        t=self._c1_state
        if not t or t['state']!='HELD' or not t['credit'] or bar.instrument_id!=t['instrument']:return
        if bar.open_time_ns<=max(t['last_cut_fill_ns'],t['cut_terminal_ns']):return
        close=bar.close.as_decimal() if hasattr(bar.close,'as_decimal') else D(str(bar.close))
        c=self._c1_current_money(bar.ts_event)
        if c is not None and c['DD']<=D('.35') and t['side']*(close-t['cut_value']/(D(t['cut_filled'])*t['step']))>0:
            t['confirmation']=dict(close_ns=bar.ts_event,open_ns=bar.open_time_ns,close=close)
            self._c1_log('CLOSED_4H_RECLAIM',bar.ts_event,open_ns=bar.open_time_ns,close=str(close),DD=str(c['DD']))

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

    def _c1_terminal(self,i,ns):
        if not self.config.research_residual_recovery or i is None or i.id not in self._c1_intents:return
        kind=self._c1_intents[i.id];t=self._c1_state
        if not t or i.episode_id!=t['group']:raise ValueError('C1_TERMINAL_LOST_GROUP')
        if kind=='CUT':
            t['cut_terminal_ns']=max(ns,t.get('cut_terminal_ns') or 0)
            if not t['revoked']:t['state']='HELD' if t['credit'] else 'RELEASED'
        else:
            t['credit']=0
            if not t['revoked']:t['state']='RELEASED'
        self._c1_log('ATTEMPT_TERMINAL',ns,kind=kind,intent_id=i.id,credit=t['credit'],rights=self._c1_rights())

    def _c1_fill(self,i,quantity,price,ns):
        if not self.config.research_residual_recovery or i.id not in self._c1_intents:return False
        t=self._c1_state;ep=self._domain.episode
        if ep is None or not t or ep.id!=t['group']:raise ValueError('C1_FILL_LOST_GROUP')
        lots=self._domain._lots(quantity,t['step']);kind=self._c1_intents[i.id];before=self._c1_rights()
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
            else:ep.sol_qty=float(max(D(0),D(str(ep.sol_qty))-D(lots)*t['step']))
            t['cut_filled']+=lots;t['cut_value']+=D(str(price))*D(lots)*t['step'];t['last_cut_fill_ns']=ns
            if not t['revoked']:t['credit']+=lots
        else:
            if lots>t['credit']:raise ValueError('C1_RESTORE_EXCEEDS_ACTUAL_CREDIT')
            if t['instrument']==self.config.btc_id:
                left=lots
                for k in sorted(t['bucket']):
                    take=min(left,t['bucket'][k]);t['bucket'][k]-=take;ep.btc_risk_retired_lots[k]-=take;left-=take
                    if take:ep.btc_tps.discard(k)
                if left:raise ValueError('C1_RESTORE_BUCKET_UNDERFLOW')
                ep.btc_open_qty=float(D(str(ep.btc_open_qty))+D(lots)*t['step'])
            else:ep.sol_qty=float(D(str(ep.sol_qty))+D(lots)*t['step'])
            t['credit']-=lots;t['restore_filled']+=lots
        self._c1_log('ACTUAL_FILL',ns,kind=kind,intent_id=i.id,lots=lots,price=str(price),credit=t['credit'],bucket=dict(t['bucket']),rights_before=before,rights_after=self._c1_rights())
        return True

    def _c1_quote(self,tick):
        if not self.config.research_residual_recovery:return
        t=self._c1_state
        if not t:return
        ns=tick.ts_event
        if self.config.terminal_close_at_ns is not None and ns>=self.config.terminal_close_at_ns:self._c1_revoke(ns,'TERMINAL_BOUNDARY');return
        if self._forced_close_reason or self._liquidating or self._mandatory_sol_exit is not None:self._c1_revoke(ns,'MANDATORY_PRIORITY');return
        if t['state']=='RELEASED':
            if t['instrument']==self.config.btc_id and t['restore_filled'] and not t.get('targets_requeued') and not self._c1_own_pending():
                t['targets_requeued']=True;self._queue_confirmed_btc_targets(None,len(self._bars)-1,ns)
            return
        # A claim holds every group increase. Terminal cancel receipts retain
        # ownership until callbacks; no inferred cancellation or ACK completion.
        self._discard_queued_intents(lambda i:i.action in ('BTC_ENTRY','SOL_ADD'))
        for o in self.cache.orders_open()+self.cache.orders_inflight():
            i=self._pending_by_order.get(str(o.client_order_id))
            if i is not None and i.id not in self._c1_intents and i.action in ('BTC_ENTRY','SOL_ADD') and not o.is_pending_cancel:self.cancel_order(o)
        if tick.instrument_id!=t['instrument'] or t['revoked']:return
        if self._c1_conflict():self._c1_revoke(ns,'ORDINARY_OR_UNKNOWN_COMPETING_OWNER');return
        c=self._c1_current_money(ns)
        if c is None:return
        if t['state']=='CUT_RESOLVING' and not t['cut_submitted']:
            for o in self.cache.orders_open()+self.cache.orders_inflight():
                i=self._pending_by_order.get(str(o.client_order_id))
                if i is not None and self._c1_harmless_tp(i) and not o.is_pending_cancel:self.cancel_order(o)
            if self._pending_by_order or self.cache.orders_open() or self.cache.orders_inflight() or self._queued_intents:return
            p=self._hb_position(t['instrument'])
            if p is None:self._c1_revoke(ns,'SELECTED_POSITION_DISAPPEARED');return
            held=int(p.quantity.as_decimal()/t['step']);lots=min(t['cut_lots'],max(0,held-t['target_lots']))
            if lots<=0:self._c1_revoke(ns,'FROZEN_TARGET_ALREADY_REACHED');return
            kind='CUT';action='BTC_REDUCE' if t['instrument']==self.config.btc_id else 'SOL_EXIT';side=-t['side'];reason=CUT;t['cut_submitted']=True
        elif t['state']=='HELD' and not t['restore_submitted']:
            conf=t['confirmation']
            if not conf or ns<=conf['close_ns'] or c['DD']>D('.35'):return
            vwap=t['cut_value']/(D(t['cut_filled'])*t['step']);executable=tick.ask_price.as_decimal() if t['side']==1 else tick.bid_price.as_decimal()
            if t['side']*(executable-vwap)<=0:
                t['confirmation']=None;self._c1_log('RESTORE_CURRENT_RECLAIM_FAILED',ns);return
            if self._pending_by_order or self.cache.orders_open() or self.cache.orders_inflight() or self._queued_intents:return
            lots=t['credit']
            if lots<=0:return
            kind='RESTORE';action='BTC_RESTORE' if t['instrument']==self.config.btc_id else 'SOL_RESTORE';side=t['side'];reason=RESTORE;t['restore_submitted']=True;t['state']='RESTORE_RESOLVING'
        else:return
        ep=self._domain.episode
        if ep is None or ep.id!=t['group']:raise ValueError('C1_SUBMIT_LOST_GROUP')
        i=self._domain._intent(ep,action,side,None,quantity=float(D(lots)*t['step']),reason=reason);self._c1_intents[i.id]=kind
        self._c1_log('ATTEMPT_SUBMIT',ns,kind=kind,intent_id=i.id,lots=lots,source_quote_ns=c['source'],receipt_ns=c['receipt'],fill_epoch=c['epoch'],rights=self._c1_rights())
        self._submit_intent(i,float(tick.bid_price),float(tick.ask_price),None,len(self._bars)-1,ts_now=ns)
        if not any(x.id==i.id for x in self._pending_by_order.values()):self._c1_terminal(i,ns)
'''
(ROOT/'runtime/coinmaster/strategy/residual_recovery.py').write_text(module)
w='runtime/coinmaster/strategy/wave_overlay.py'
edit(w,'from coinmaster.strategy.next_band import NextBandResearch, NextClosedBar','from coinmaster.strategy.next_band import NextBandResearch, NextClosedBar\nfrom coinmaster.strategy.residual_recovery import ResidualRecoveryResearch')
edit(w,'    research_next_signals:', '    research_residual_recovery: bool = False\n    research_next_signals:')
edit(w,'class WaveOverlayStrategy(NextBandResearch,','class WaveOverlayStrategy(ResidualRecoveryResearch, NextBandResearch,')
edit(w,'        self._next_init()','        self._next_init()\n        self._c1_init()')
edit(w,'        self._next_quote(tick)','        self._next_quote(tick)\n        self._c1_quote(tick)')
edit(w,'        self._record_native_fill(event)','        self._c1_native_fill(event)\n        self._record_native_fill(event)')
edit(w,'        if self._next_risk_fill(intent,quantity,ts_event):','        if self._c1_fill(intent,quantity,price,ts_event):\n            pass\n        elif self._next_risk_fill(intent,quantity,ts_event):')
edit(w,'        failed_intent = self._pending_by_order.get(client_order_id)','        failed_intent = self._pending_by_order.get(client_order_id)\n        self._c1_terminal(failed_intent,self.clock.timestamp_ns())')
edit(w,'        self._group_close_reconciliation_pending = False\n        if self._insurance_enabled()', '        self._group_close_reconciliation_pending = False\n        if self._c1_state is not None:\n            self._c1_log("GROUP_FLAT_RESET", self.clock.timestamp_ns(), credit_expired=self._c1_state["credit"])\n            self._c1_state = None\n        if self._insurance_enabled()')
edit(w,'    def _begin_forced_close(', '    def _begin_forced_close(') # exact hook located below after inspection, quote/fill hooks already preempt
n='runtime/coinmaster/strategy/next_band.py'
edit(n,'    def _next_terminal(self,intent,ns):','    def _next_terminal(self,intent,ns):\n        self._c1_terminal(intent,ns)')
edit(n,'    def _next_closed_bar(self,bar):','    def _next_closed_bar(self,bar):\n        self._c1_closed_bar(bar)')
edit(n,'    def _next_before_submit(self,intent,ns):','    def _next_before_submit(self,intent,ns):\n        if not self._c1_before_submit(intent,ns):return False')
m='runtime/coinmaster/research/minute_risk.py'
edit(m,'        self.receipt_pending = None\n\n    def capture', '        self.receipt_pending = None\n        # C1 decisions consume the committed consistent receipt and frozen marks.\n        if getattr(strategy.config,"research_residual_recovery",False):\n            strategy._c1_observe(equity,timestamp,source,epoch,details)\n\n    def capture')
b='runtime/coinmaster/research/native_baseline.py'
edit(b,'from decimal import Decimal','from decimal import Decimal, localcontext')
p=ROOT/b;s=p.read_text();start=s.index('    compounded = Decimal("1")');end=s.index('    for timestamp in',start);block=s[start:end];s=s[:start]+'    with localcontext() as context:\n        context.prec = 80\n'+''.join('    '+line+'\n' for line in block.splitlines())+s[end:];p.write_text(s)
# Three public entry signatures/call propagation; default OFF.
p=ROOT/b;s=p.read_text();s=s.replace('research_wait_4h: bool = False,','research_residual_recovery: bool = False, research_wait_4h: bool = False,');s=s.replace('research_wait_4h=research_wait_4h,','research_residual_recovery=research_residual_recovery, research_wait_4h=research_wait_4h,');s=s.replace('research_wait_4h=args.research_wait_4h,','research_residual_recovery=args.research_residual_recovery, research_wait_4h=args.research_wait_4h,');s=s.replace('("wait-4h", "wait-persist", "zero-retrace", "sol-dominant")','("residual-recovery", "wait-4h", "wait-persist", "zero-retrace", "sol-dominant")');s=s.replace('((research_wait_4h,"E4"),','((research_residual_recovery,"C1"),(research_wait_4h,"E4"),');s=s.replace('next_bar_types = tuple(next_bar_type(inst.id,hours) for inst,hours in ((btc_instrument,4),(sol_instrument,1)))','next_bar_types = tuple(next_bar_type(inst.id,hours) for inst,hours in ((btc_instrument,4),(sol_instrument,1),*((((sol_instrument,4),)) if research_residual_recovery else ())))');s=s.replace('for instrument,row,hours,kind in ((btc_instrument,minute.btc_execution,4,next_bar_types[0]),(sol_instrument,minute.sol_execution,1,next_bar_types[1])):', 'for instrument,row,hours,kind in ((btc_instrument,minute.btc_execution,4,next_bar_types[0]),(sol_instrument,minute.sol_execution,1,next_bar_types[1]),*((((sol_instrument,minute.sol_execution,4,next_bar_types[2]),)) if research_residual_recovery else ())):');s=s.replace('        if next_enabled:\n            full_config["next_band_research"]', '        if research_residual_recovery:\n            full_config["residual_recovery_research"]=dict(version="C1",trigger_DD="0.40",open_loss_dominates_remaining_50_cushion=True,cut_fraction="0.50",restore_DD="0.35",restore_closed_hours=4,max_cut_restore_per_group=1)\n        if next_enabled:\n            full_config["next_band_research"]');s=s.replace('        if next_enabled:\n            result["next_band_audit"]','        if research_residual_recovery:\n            result["c1_audit"]=strategy.c1_audit\n        if next_enabled:\n            result["next_band_audit"]');s=s.replace('("next_band", "strategy/next_band.py"),','("next_band", "strategy/next_band.py"), *(((("residual_recovery", "strategy/residual_recovery.py"),)) if research_residual_recovery else ()),');needle='    next_enabled = research_wait_4h or';idx=s.index(needle);s=s[:idx]+'    if research_residual_recovery and (not observe_minute_risk or not research_wait_4h or research_regime_reentry_band!="0.5" or research_zero_retrace or research_sol_dominant or research_wait_persist or research_sol_risk_first or research_conditional_sol or research_alpha_cushion or research_chop_pair):raise ValueError("C1_REQUIRES_CLEAN_E4_SETTLED_OBSERVER")\n'+s[idx:];p.write_text(s)
print('C1 source written canonical isolated worktree only')
