from pathlib import Path
R=Path('/root/.openclaw/workspace/coinmaster/coinmaster/research-worktrees/residual-recovery-20261023')
p=R/'runtime/tests/test_native_residual_recovery.py';s=p.read_text();s+='''

@pytest.mark.parametrize('mode',['denied','rejected'])
def test_actual_native_cut_denial_rejection_has_no_credit_no_retry_original_tp_survives(mode):
 from nautilus_trader.model.objects import Quantity
 from nautilus_trader.model.enums import TimeInForce
 class NativeFailure(NativeProbe):
  def submit_order(self,order,*a,**kw):
   i=self._pending_by_order.get(str(order.client_order_id))
   if i is not None and i.reason==CUT:
    if mode=='denied':order=self.order_factory.market(order.instrument_id,order.side,Quantity.from_str('50.0001'),time_in_force=TimeInForce.IOC,reduce_only=True,client_order_id=order.client_order_id)
    else:order=self.order_factory.limit(order.instrument_id,order.side,order.quantity,BTC_PERP.make_price(D(1)),time_in_force=TimeInForce.GTC,post_only=True,reduce_only=True,client_order_id=order.client_order_id)
   return super().submit_order(order,*a,**kw)
 s,e,ep=held(cls=NativeFailure)
 try:
  cut(s,e);t=s._c1_state
  assert t['state']=='RELEASED' and t['cut_submitted'] and not t['credit'] and not t['cut_filled']
  for n in range(1,5):run_ticks(e,[tick(BTC_PERP,2000+n,'55')])
  assert sum(o.leaves_qty.as_decimal() for o in s.cache.orders_open() if o.is_reduce_only)==D(100)
  assert ep.btc_open_qty==100 and not ep.sol_rights
  assert len([x for x in s.c1_audit if x['event']=='ATTEMPT_SUBMIT'])==1
 finally:e.end();e.dispose()


def test_actual_native_zero_fill_cut_restores_original_tp_coverage():
 s,e,ep=held()
 try:
  cut(s,e,size='0');t=s._c1_state
  assert t['state']=='RELEASED' and t['cut_filled']==0 and t['credit']==0
  for n in range(1,5):run_ticks(e,[tick(BTC_PERP,2000+n,'55')])
  assert sum(o.leaves_qty.as_decimal() for o in s.cache.orders_open() if o.is_reduce_only)==D(100)
 finally:e.end();e.dispose()


def test_current_executable_reclaim_is_rechecked_and_same_clock_cut_is_blocked():
 s,e,ep=held()
 try:
  observe(s,1000,btc='55');run_ticks(e,[tick(BTC_PERP,1000,'55')]);assert not s._c1_state['cut_submitted']
  for n in range(1,6):
   observe(s,1000+n,btc='55');run_ticks(e,[tick(BTC_PERP,1000+n,'55')])
  t=s._c1_state;assert t['state']=='HELD'
  observe(s,2*H4,btc='80');s._c1_closed_bar(next_closed_bar(BTC_PERP.id,4,D(80),D(80),D(80),D(80),2*H4).data)
  observe(s,2*H4+1,btc='80');run_ticks(e,[tick(BTC_PERP,2*H4+1,'55')])
  assert t['state']=='HELD' and t['credit']==50000 and not t['restore_submitted'] and t['confirmation'] is None
  submit=next(x for x in s.c1_audit if x['event']=='ATTEMPT_SUBMIT');assert submit['timestamp_ns']>submit['claim_ns']
 finally:e.end();e.dispose()


def test_actual_native_duplicate_fill_keeps_recorder_and_controller_epoch_aligned():
 from coinmaster.research.minute_risk import observed_strategy_type
 class Recorder:
  bundles={}
  fill_epoch=0
  def note_fill(self,ns):self.fill_epoch+=1
  def capture(self,*a):pass
  def finalize_receipt(self,*a):pass
 class Capture(NativeProbe):
  actual_events=[]
  def on_order_filled(self,event):
   self.actual_events.append(event);super().on_order_filled(event)
 recorder=Recorder();Observed=observed_strategy_type(Capture,recorder)
 s,e,ep=held(cls=Observed)
 try:
  before=(recorder.fill_epoch,s._c1_fill_epoch,len(s.fill_audit));event=s.actual_events[-1]
  s.on_order_filled(event)
  assert before==(recorder.fill_epoch,s._c1_fill_epoch,len(s.fill_audit))
  assert recorder.fill_epoch==s._c1_fill_epoch
 finally:e.end();e.dispose()
''';p.write_text(s)
print('C1 native rejected/denied/zero-fill/timing/duplicate regressions written')
