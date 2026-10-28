import json
from coinmaster.research.native_audit import audit_json_default
from decimal import Decimal as D
from copy import deepcopy
from types import SimpleNamespace
import pytest
from coinmaster.domain.wave_overlay import Candidate,Episode
from coinmaster.strategy.next_band import next_closed_bar,H4,DAY
from coinmaster.strategy.residual_recovery import CUT,RESTORE
from coinmaster.strategy.wave_overlay import _native_account_money
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP
from test_native_next_band import cfg
from test_native_episode_risk import NativeProbe,tick,run_ticks,marks
from test_native_btc_sizing import prepare_day
from test_wave_native_integration import native_engine,lifecycle_config

def held(asset='BTC',side=1,cls=NativeProbe,cut_divisor=2):
 s=cls(cfg(research_wait_4h=True,research_residual_recovery=True,research_c1_btc_cut_divisor=cut_divisor,candidate=Candidate(btc_tp_fractions_initial_qty=(.2125,.2125,.575))))
 e=native_engine(s);run_ticks(e,[tick(BTC_PERP,1),tick(SOL_PERP,1)])
 prepare_day(s,2,side);ep=s._domain.episode=Episode('c1',side,10000,1,wave_levels=(.50,.60,.70),btc_planref_vwap=D(100))
 i=s._domain._intent(ep,'BTC_ENTRY',side,None,quantity=100)
 s._submit_intent(i,100,100,None,2,ts_now=2);run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4)])
 s._split_parent=dict(episode_id=ep.id,closed=True,start_ns=2,management_reference_frozen_ns=3,planref_v1_beta=2.)
 if asset=='SOL':
  i=s._domain._intent(ep,'SOL_ADD',-side,0,quantity=100)
  s._submit_intent(i,100,100,.01,2,ts_now=5);run_ticks(e,[tick(SOL_PERP,6),tick(SOL_PERP,7)])
 return s,e,ep

def observe(s,ns,btc='55',sol='100',equity=None):
 details=[];E=_native_account_money(s.cache.account_for_venue(BTC_PERP.id.venue))
 for p in s.cache.positions_open():
  inst=s.cache.instrument(p.instrument_id);mark=D(btc if p.instrument_id==BTC_PERP.id else sol)
  E+=p.unrealized_pnl(inst.make_price(mark)).as_decimal()
  details.append(dict(instrument_id=str(p.instrument_id),side=str(p.side),quantity=str(p.quantity),avg_px_open=str(p.avg_px_open),mark_ohlc=dict(close=str(mark))))
 s._c1_observe(E if equity is None else D(equity),ns,ns-1,s._c1_fill_epoch,details)
 return E

def cut(s,e,asset='BTC',price='55',size='1000'):
 ns=1000;observe(s,ns,btc=price if asset=='BTC' else '100',sol=price if asset=='SOL' else '100')
 inst=BTC_PERP if asset=='BTC' else SOL_PERP
 for n in range(1,7):
  observe(s,ns+n,btc=price if asset=="BTC" else "100",sol=price if asset=="SOL" else "100");run_ticks(e,[tick(inst,ns+n,price,size)])
 return ns+6

@pytest.mark.parametrize('side',[1,-1])
def test_actual_halfcut_restore_native_money_original_btc_basis_rights_and_one_group(side):
 s,e,ep=held(side=side)
 try:
  original=(ep.btc_initial_qty,deepcopy(ep.btc_tp_target_lots),ep.btc_planref_vwap,ep.h,deepcopy(ep.sol_add_filled_notional))
  adverse='55' if side==1 else '145';cut(s,e,price=adverse)
  t=s._c1_state;assert t['state']=='HELD' and t['cut_filled']==50000 and t['credit']==50000
  assert ep.btc_open_qty==50 and not ep.sol_rights and sum(ep.btc_risk_retired_lots.values())==50000
  saved_targets=deepcopy(ep.btc_tp_target_lots)
  # Partial/incomplete4h candle, or one whose open precedes terminal, cannot confirm.
  observe(s,H4,btc='80' if side==1 else '120')
  s._c1_closed_bar(next_closed_bar(BTC_PERP.id,4,D(80),D(80),D(80),D(80),H4).data)
  assert t['confirmation'] is None
  restore='80' if side==1 else '120';observe(s,2*H4,btc=restore)
  s._c1_closed_bar(next_closed_bar(BTC_PERP.id,4,D(restore),D(restore),D(restore),D(restore),2*H4).data)
  assert t['confirmation'] is not None
  for n in range(1,6):
   observe(s,2*H4+n,btc=restore);run_ticks(e,[tick(BTC_PERP,2*H4+n,restore)])
  assert t['state']=='RELEASED' and t['restore_filled']==50000 and t['credit']==0
  witness=next(x for x in s.c1_audit if x['event']=='ATTEMPT_SUBMIT' and x['kind']=='RESTORE')
  assert D(witness['DD'])<=D('.35') and witness['fill_epoch']==witness['current_fill_epoch']
  assert side*(D(witness['executable_price'])-D(witness['cut_actual_vwap']))>0
  assert witness['pending_ids']==[] and witness['native_open_orders']==witness['native_inflight_orders']==witness['queued_intents']==0
  assert witness['source_quote_ns']<witness['receipt_ns']<=witness['quote_ns'] and witness['account_event_ns']<=witness['source_quote_ns']
  assert witness['native_admission']=='PASSED_EXISTING_INCREASE_GATES'
  # Exercise the unchanged production JSON serializer on the ACTUAL native audit.
  payload=dict(c1_audit=s.c1_audit,c1_denial_counts=s.c1_denials,c1_terminal_state=s._c1_export_terminal())
  encoded=json.dumps(payload,indent=2,sort_keys=True,default=audit_json_default)
  decoded=json.loads(encoded)
  restored=next(x for x in decoded['c1_audit'] if x['event']=='ATTEMPT_SUBMIT' and x['kind']=='RESTORE')
  assert isinstance(restored['confirmation']['close'],str) and D(restored['confirmation']['close'])==D(restore)
  # Numeric policy state stays Decimal; only the copied witness is primitive.
  assert isinstance(t['confirmation']['close'],D)
  assert ep.btc_open_qty==100 and sum(ep.btc_risk_retired_lots.values())==0 and not ep.sol_rights
  assert original==(ep.btc_initial_qty,saved_targets,ep.btc_planref_vwap,ep.h,ep.sol_add_filled_notional)
  observe(s,3*H4,btc=adverse);run_ticks(e,[tick(BTC_PERP,3*H4+1,adverse)])
  assert len([x for x in s.c1_audit if x['event']=='CLAIM'])==1
 finally:e.end();e.dispose()

def test_sol_original_consumption_clocks_sigma_preserved_and_increases_blocked():
 s,e,ep=held(asset='SOL',side=-1)
 try:
  # Remove BTC risk causally through its ordinary reduce, leaving original group SOL.
  i=s._domain._intent(ep,'BTC_REDUCE',1,2,quantity=100,reason='BTC_TP3');s._submit_intent(i,100,100,None,2,ts_now=10)
  run_ticks(e,[tick(BTC_PERP,11),tick(BTC_PERP,12)])
  original=(deepcopy(ep.sol_add_filled_notional),ep.sol_first_fill_at,ep.fixed_sigma,ep.sol_half_done,ep.h,ep.btc_planref_vwap)
  cut(s,e,asset='SOL',price='55')
  t=s._c1_state;assert t['instrument']==SOL_PERP.id and t['cut_filled']==500 and ep.sol_qty==50
  for action in ['BTC_ENTRY','SOL_ADD']:
   i=s._domain._intent(ep,action,1,0,quantity=1);s._submit_intent(i,55,55,.01,2,ts_now=2000)
   assert i.id not in ep.pending
  observe(s,2*H4,btc='100',sol='80');s._c1_closed_bar(next_closed_bar(SOL_PERP.id,4,D(80),D(80),D(80),D(80),2*H4).data)
  for n in range(1,6):
   observe(s,2*H4+n,btc='100',sol='80');run_ticks(e,[tick(SOL_PERP,2*H4+n,'80')])
  assert t['restore_filled']==500 and ep.sol_qty==100 and s._c1_sol_levels[ep.id]=={0:1000}
  assert original==(ep.sol_add_filled_notional,ep.sol_first_fill_at,ep.fixed_sigma,ep.sol_half_done,ep.h,ep.btc_planref_vwap)
 finally:e.end();e.dispose()

def test_inherited_cash_loss_strict_dominance_parent_busy_stale_and_denials_bounded():
 s,e,ep=held()
 try:
  observe(s,1000,btc='99',equity='5900');assert s._c1_state is None # open loss100 < cushion900
  s._split_parent['closed']=False
  for ns in range(1001,1010):observe(s,ns,btc='55')
  assert s._c1_state is None and len(s.c1_denials)==1 and next(iter(s.c1_denials.values()))['count']==9
  s._split_parent['closed']=True;observe(s,2000,btc='55');assert s._c1_state is not None
  c=s._c1_checkpoint
  assert s._c1_current_money(c['source']) is None
  assert s._c1_current_money(c['source']+s.config.max_mark_age_ns+1) is None
  s._c1_fill_epoch+=1;assert s._c1_current_money(2001) is None
 finally:e.end();e.dispose()

def test_partial_cut_actual_credit_ordinary_exit_revocation_no_extra_cut_or_restore():
 s,e,ep=held()
 try:
  cut(s,e,price='55',size='3');t=s._c1_state
  assert 0<t['cut_filled']<=50000 and t['credit']==t['cut_filled']
  count=t['cut_filled'];assert ep.btc_open_qty==float(D(100)-D(count)*D('.001'))
  i=s._domain._intent(ep,'BTC_REDUCE',-1,2,quantity=1,reason='BTC_TP3')
  s._submit_intent(i,55,55,None,2,ts_now=2000)
  assert t['revoked'] and t['credit']==0
  for n in range(1,4):run_ticks(e,[tick(BTC_PERP,2000+n,'55')])
  assert t['restore_filled']==0
 finally:e.end();e.dispose()

def test_default_off_and_temporary_tp_cancel_is_not_ordinary_exit():
 assert not lifecycle_config().research_residual_recovery
 s,e,ep=held()
 try:
  i=s._domain._intent(ep,'BTC_REDUCE',-1,2,quantity=10,limit_price=150,reason='BTC_TP3')
  s._submit_intent(i,100,100,None,2,ts_now=10);run_ticks(e,[tick(BTC_PERP,11)])
  cut(s,e);assert s._c1_state['credit']==50000 and not s._c1_state['revoked']
 finally:e.end();e.dispose()


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


def test_terminal_native_flat_burns_credit_and_exports_no_active_hold():
 s,e,ep=held()
 try:
  cut(s,e);assert s._c1_state['credit']>0
  s._submit_terminal_closes()
  for n in range(1,10):run_ticks(e,[tick(BTC_PERP,4000+n,'55'),tick(SOL_PERP,4000+n,'100')])
  s.reporting_state();out=s._c1_export_terminal()
  assert not out['active_hold'] and out['credit']==0 and out['native_positions']==0 and out['pending']==0
  assert any(x['event']=='TERMINAL_FLAT_CONFIRMED' for x in s.c1_audit)
 finally:e.end();e.dispose()
