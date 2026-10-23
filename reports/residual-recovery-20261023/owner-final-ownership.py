from pathlib import Path
R=Path('/root/.openclaw/workspace/coinmaster/coinmaster/research-worktrees/residual-recovery-20261023')
p=R/'runtime/coinmaster/strategy/residual_recovery.py';s=p.read_text();old="        if t['instrument']==self.config.btc_id and t.get('targets_need_requeue') and not self._c1_own_pending():";assert old in s;s=s.replace(old,"        if t.get('targets_need_requeue') and not self._c1_own_pending():");p.write_text(s)
p=R/'runtime/coinmaster/strategy/wave_overlay.py';s=p.read_text();needle='            if (tick.instrument_id != self.config.sol_id\n';assert needle in s;s=s.replace(needle,needle+'                    or (self.config.research_residual_recovery and self._c1_own_pending())\n',1);p.write_text(s)
p=R/'runtime/tests/test_native_residual_recovery.py';s=p.read_text();s+='''

def test_sol_intervention_recreates_surviving_btc_passive_tp_coverage():
 s,e,ep=held(asset='SOL',side=1)
 try:
  cut(s,e,asset='SOL',price='145');t=s._c1_state
  for n in range(1,6):run_ticks(e,[tick(BTC_PERP,2000+n,'100'),tick(SOL_PERP,2000+n,'145')])
  assert t['instrument']==SOL_PERP.id and t['cut_filled']==500 and ep.sol_qty==50
  assert sum(o.leaves_qty.as_decimal() for o in s.cache.orders_open() if o.instrument_id==BTC_PERP.id and o.is_reduce_only)==D(100)
 finally:e.end();e.dispose()


def test_mandatory_sol_timeout_retains_slot_until_owned_c1_child_terminal():
 from nautilus_trader.model.enums import TimeInForce
 class Delayed(NativeProbe):
  allow_cancel=False
  def submit_order(self,order,*a,**kw):
   i=self._pending_by_order.get(str(order.client_order_id))
   if i is not None and i.reason==CUT:
    order=self.order_factory.limit(order.instrument_id,order.side,order.quantity,BTC_PERP.make_price(D(150)),time_in_force=TimeInForce.GTC,reduce_only=True,client_order_id=order.client_order_id)
   return super().submit_order(order,*a,**kw)
  def cancel_order(self,order,*a,**kw):
   i=self._pending_by_order.get(str(order.client_order_id))
   if i is not None and i.reason==CUT and not self.allow_cancel:return
   return super().cancel_order(order,*a,**kw)
 s,e,ep=held(asset='SOL',side=1,cls=Delayed)
 try:
  # BTC loses; profitable SOL remains a mandatory independent native exit.
  observe(s,1000,btc='55',sol='100')
  for n in range(1,6):
   observe(s,1000+n,btc='55',sol='100');run_ticks(e,[tick(BTC_PERP,1000+n,'55')])
  assert s._c1_own_pending()
  timeout=s._domain._intent(ep,'SOL_EXIT',1,None,quantity=100,reason='SOL_HARD_TIMEOUT')
  s._mandatory_sol_exit=(timeout,.01,2)
  run_ticks(e,[tick(SOL_PERP,2000,'100')])
  assert s._mandatory_sol_exit is not None and ep.sol_qty==100 and s._c1_own_pending()
  s.allow_cancel=True;s._c1_cancel_owned()
  for n in range(1,7):run_ticks(e,[tick(BTC_PERP,2000+n,'55'),tick(SOL_PERP,2000+n,'100')])
  assert s._mandatory_sol_exit is None and not s._c1_own_pending() and ep.sol_qty==0
  assert any(x['action']=='SOL_EXIT' and x['reason']=='SOL_HARD_TIMEOUT' for x in s.fill_audit)
 finally:e.end();e.dispose()
''';p.write_text(s)
print('Final two ownership corrections + focused native regressions written')
