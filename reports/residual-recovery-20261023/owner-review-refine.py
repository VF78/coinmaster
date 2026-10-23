from pathlib import Path
R=Path('/root/.openclaw/workspace/coinmaster/coinmaster/research-worktrees/residual-recovery-20261023')
p=R/'runtime/coinmaster/strategy/residual_recovery.py';s=p.read_text().replace('from decimal import Decimal as D','from decimal import Decimal as D\nfrom nautilus_trader.model.enums import OrderSide')
s=s.replace("            if not t['revoked']:t['state']='HELD' if t['credit'] else 'RELEASED'", "            if not t['revoked']:t['state']='HELD' if t['credit'] else 'RELEASED'\n            t['targets_need_requeue']=True")
s=s.replace("            if not t['revoked']:t['state']='RELEASED'", "            if not t['revoked']:t['state']='RELEASED'\n            t['targets_need_requeue']=True")
old="""        if t['state']=='RELEASED':
            if t['instrument']==self.config.btc_id and t['restore_filled'] and not t.get('targets_requeued') and not self._c1_own_pending():
                t['targets_requeued']=True;self._queue_confirmed_btc_targets(None,len(self._bars)-1,ns)
            return"""
new="""        if t['instrument']==self.config.btc_id and t.get('targets_need_requeue') and not self._c1_own_pending():
            t['targets_need_requeue']=False;self._queue_confirmed_btc_targets(None,len(self._bars)-1,ns)
            self._c1_log('ORIGINAL_TP_LEAVES_REQUEUED',ns,rights=self._c1_rights())
        if t['state']=='RELEASED':return"""
assert old in s;s=s.replace(old,new)
s=s.replace("            kind='RESTORE';action='BTC_RESTORE'", "            instrument=self.cache.instrument(t['instrument']);quantity=D(lots)*t['step']\n            minimum=(instrument.min_quantity is None or quantity>=instrument.min_quantity.as_decimal()) and (instrument.min_notional is None or quantity*executable>=instrument.min_notional.as_decimal())\n            native_side=OrderSide.BUY if t['side']==1 else OrderSide.SELL\n            if not minimum or not self._entries_enabled() or not self._tier_allows_increase(t['instrument'],native_side,quantity,ns):\n                t['confirmation']=None;self._c1_log('RESTORE_NATIVE_ADMISSION_DENIED',ns,credit=t['credit']);return\n            kind='RESTORE';action='BTC_RESTORE'")
s=s.replace("        if not any(x.id==i.id for x in self._pending_by_order.values()):self._c1_terminal(i,ns)", "        if not any(x.id==i.id for x in self._pending_by_order.values()) and i.id not in self._c1_terminal_ids:\n            if kind=='RESTORE' and not t.get('native_order_ids',{}).get(i.id):\n                t['state']='HELD';t['restore_submitted']=False;t['restore_committed']=0;t['confirmation']=None\n                self._c1_log('RESTORE_NOT_SUBMITTED',ns,intent_id=i.id,credit=t['credit'])\n            else:self._c1_terminal(i,ns)")
s=s.replace('    def _c1_terminal(self,i,ns):', "    def _c1_bind_submission(self,i,oid,ns):\n        if not self.config.research_residual_recovery or i.id not in self._c1_intents:return\n        self._c1_state.setdefault('native_order_ids',{})[i.id]=oid\n        self._c1_log('NATIVE_ORDER_SUBMITTED',ns,intent_id=i.id,order_id=oid,kind=self._c1_intents[i.id])\n\n    def _c1_terminal(self,i,ns):")
p.write_text(s)
p=R/'runtime/coinmaster/strategy/wave_overlay.py';s=p.read_text();needle='        self.submit_order(order)\n\n    @staticmethod\n    def _reduction_key';assert needle in s;s=s.replace(needle,'        self._c1_bind_submission(intent,client_order_id,ts_now or self.clock.timestamp_ns())\n'+needle);p.write_text(s)
# Dedicated regression coverage for the two review findings and genuine group reset.
p=R/'runtime/tests/test_native_residual_recovery.py';s=p.read_text();s+='''

def test_restore_local_admission_denial_keeps_credit_and_requires_new_closed_bar():
 class Admission(NativeProbe):
  allow=True
  def _tier_allows_increase(self,*a):return self.allow
 s,e,ep=held(cls=Admission)
 try:
  cut(s,e);t=s._c1_state
  observe(s,2*H4,btc='80');s._c1_closed_bar(next_closed_bar(BTC_PERP.id,4,D(80),D(80),D(80),D(80),2*H4).data)
  s.allow=False
  for n in range(1,8):
   observe(s,2*H4+n,btc='80');run_ticks(e,[tick(BTC_PERP,2*H4+n,'80')])
  assert t['state']=='HELD' and not t['restore_submitted'] and t['credit']==50000 and t['confirmation'] is None
  s.allow=True;observe(s,2*H4+100,btc='80');run_ticks(e,[tick(BTC_PERP,2*H4+100,'80')])
  assert not t['restore_submitted']
 finally:e.end();e.dispose()


def test_remaining_native_tp_leaves_recreated_while_held_and_genuine_group_reset():
 s,e,ep=held()
 try:
  cut(s,e);t=s._c1_state
  for n in range(1,5):run_ticks(e,[tick(BTC_PERP,2000+n,'55')])
  orders=[o for o in s.cache.orders_open() if o.is_reduce_only]
  assert sum(o.leaves_qty.as_decimal() for o in orders)==D(50)
  assert t['state']=='HELD' and not t['revoked']
  oldH=s._c1_peak
  s._begin_forced_close('REGIME')
  for n in range(1,10):run_ticks(e,[tick(BTC_PERP,3000+n,'55'),tick(SOL_PERP,3000+n,'100')])
  assert not s.cache.positions_open() and s._domain.episode is None and s._c1_state is None
  assert s._c1_peak==oldH
  # New actual group gets a fresh claim counter, never a reset of global H.
  prepare_day(s,4000,1);ep2=s._domain.episode=Episode('c1-second',1,10000,1,wave_levels=(.5,.6,.7),btc_planref_vwap=D(100))
  i=s._domain._intent(ep2,'BTC_ENTRY',1,None,quantity=100);s._submit_intent(i,100,100,None,2,ts_now=4000)
  run_ticks(e,[tick(BTC_PERP,4001),tick(BTC_PERP,4002)])
  s._split_parent=dict(episode_id=ep2.id,closed=True,start_ns=4000,management_reference_frozen_ns=4001,planref_v1_beta=2.)
  observe(s,5000,btc='55');assert s._c1_state['group']=='c1-second' and not s._c1_state['cut_submitted']
  assert s._c1_peak==oldH
 finally:e.end();e.dispose()
''';p.write_text(s)
print('Review admission/TP issues addressed with regressions')
