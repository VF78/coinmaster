"""Actual DailySignal producer -> actual on_data -> C1 guard; native constructors0."""
import ast
from decimal import Decimal as D
from types import SimpleNamespace as N
import pytest
from test_c1_first_fresh_h4_pure import Owner,ROOT,MINUTE,ID
DAY=86_400_000_000_000
class Wrapped:
 def __init__(self,kind,data):self.data=data
signals=ast.parse((ROOT/'venues/signals.py').read_text())
env=dict(Decimal=D,Data=object,InstrumentId=ID,CustomData=Wrapped,DataType=lambda *a:None)
exec(compile(ast.Module(body=[n for n in signals.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))],type_ignores=[]),'actual_daily_signal_producer','exec'),env)
wave=ast.parse((ROOT/'strategy/wave_overlay.py').read_text())
method=next(n for c in wave.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='on_data')
exec(compile(ast.Module(body=[method],type_ignores=[]),'actual_wave_on_data','exec'),dict(env,NextClosedBar=type('NotNext',(object,),{}),VenueMark=type('NotMark',(object,),{})),bind:={})
class LiveOwner(Owner):
 on_data=bind['on_data']
 def __init__(self,window='NOV',enabled=True):
  super().__init__(window);self.config.research_c1_btc_postcut_d1=enabled
  self.config.btc_signal_id=ID('BTC_SIGNAL');self.config.sol_signal_id=ID('SOL_SIGNAL')
  self.config.btc_bar_type='BTC_D1';self.config.sol_bar_type='SOL_D1'
  self._group_close_reconciliation_pending=False;self._latest_seen_session=None;self._last_accepted_session=None
  self._day={};self._latest_marks={};self.now=self.close_ns;self.clock=N(timestamp_ns=lambda:self.now)
 def _apply_verified_backfill(self):pass
 def _try_advance_session(self,ns):pass
 def daily(self,close=None,instrument=None,init=None,low='90'):
  close=self.close_ns//DAY*DAY+2*DAY if close is None else close
  return env['daily_signal'](instrument or self.config.btc_signal_id,D(100),D(110),D(low),D(105),close,close if init is None else init)
 def observe_day(self,**kw):
  bar=self.daily(**kw);self.now=max(self.now,bar.data.ts_init);self.on_data(bar);return bar
 def at_day(self):
  bar=self.observe_day();self.now=bar.data.ts_init+MINUTE
  self.money(source=bar.data.ts_init,receipt=self.now)
  return self.quote(self.now-self.close_ns)


def test_actual_dispatch_observes_btc_only_and_actual_availability():
 s=LiveOwner();s.now+=10*DAY
 sol=s.daily(instrument=s.config.sol_signal_id);s.on_data(sol);assert not s._c1_last_bars
 b=s.daily();s.on_data(b);d=s._c1_last_bars['BTC_POSTCUT_D1']
 assert d['available_ns']==s.now and d['open_ns']==b.data.ts_event-DAY and d['instrument']=='BTC_SIGNAL'

@pytest.mark.parametrize('normal',[False,True])
def test_all_btc_restores_wait_without_cancel_or_credit_attempt_loss_then_real_ack(normal):
 s=LiveOwner();s.capture();s.money();t=s._c1_state
 if normal:t['confirmation']=dict(close_ns=s.close_ns,open_ns=s.close_ns-1,close=D(s.market));t.pop('first_fresh_deferred')
 tp=N(id='tp',action='BTC_REDUCE');o=N(client_order_id='tp',is_pending_cancel=False)
 s._pending_by_order['tp']=tp;s.orders=[o];credit=t['credit']
 s._c1_quote(s.quote());assert t['confirmation'] and not s.cancelled and not s.submitted and t['credit']==credit and not t['restore_submitted']
 q=s.at_day();s._c1_quote(q);assert s.cancelled==[o] and not s.submitted and t['confirmation']
 s.orders.clear();s._pending_by_order.clear();s._c1_quote(q);assert len(s.submitted)==1 and t['restore_committed']==credit

@pytest.mark.parametrize('fault',['unobserved','open_before_cut','future_close','future_init','unaligned','malformed','unknown_instrument','source_before_available'])
def test_invalid_or_unavailable_day_never_authorizes(fault):
 s=LiveOwner();s.capture();s.money();t=s._c1_state;close=s.daily().data.ts_event
 if fault=='unobserved':pass
 elif fault=='open_before_cut':s.observe_day(close=close-DAY)
 elif fault=='future_close':s.on_data(s.daily())
 elif fault=='future_init':s.now=close;s.on_data(s.daily(init=close+1))
 elif fault=='unaligned':s.observe_day(close=close+1)
 elif fault=='malformed':s.observe_day(low='111')
 elif fault=='unknown_instrument':s.observe_day(instrument=ID('OTHER'))
 else:
  s.observe_day();s.money(source=s.now-1,receipt=s.now+1);s.account.last_event.ts_event=s.now-1
 q=s.quote(max(MINUTE,s.now+1-s.close_ns));s._c1_quote(q)
 assert not s.submitted and not s.cancelled and not t['restore_submitted']


def test_postcut_boundary_equal_open_allowed_later_actual_cutfill_moves_window():
 s=LiveOwner();b=s.observe_day();t=s._c1_state;t['last_cut_fill_ns']=b.data.ts_event-DAY
 s.money(source=s.now,receipt=s.now+1);assert s._c1_btc_postcut_d1_allowed(t,s._c1_checkpoint,s.now+1)
 t['last_cut_fill_ns']+=1;assert not s._c1_btc_postcut_d1_allowed(t,s._c1_checkpoint,s.now+1)
 s.observe_day(close=b.data.ts_event+DAY);s.money(source=s.now,receipt=s.now+1)
 assert s._c1_btc_postcut_d1_allowed(t,s._c1_checkpoint,s.now+1)


def test_out_of_order_and_duplicate_bar_do_not_replace_observed_newer_authority():
 s=LiveOwner();b=s.observe_day();old=dict(s._c1_last_bars['BTC_POSTCUT_D1']);s.now+=DAY
 s.on_data(s.daily(close=b.data.ts_event-DAY));s.on_data(b)
 assert s._c1_last_bars['BTC_POSTCUT_D1']==old


def test_ordinary_exit_revokes_while_waiting_and_mandatory_priority_remains():
 for mandatory in (False,True):
  s=LiveOwner();s.capture();s.money();s._c1_quote(s.quote());t=s._c1_state
  if mandatory:s._forced_close_reason='STOP';s._c1_quote(s.quote())
  else:s._c1_harmless_tp=lambda i:False;s._c1_before_submit(N(id='exit',action='BTC_REDUCE'),s.close_ns+MINUTE)
  assert t['revoked'] and t['credit']==0 and not s.submitted


def test_sol_early_restore_is_unchanged_without_any_d1_and_off_btc_legacy_restores():
 for window,enabled in [('OCT',True),('NOV',False)]:
  s=LiveOwner(window,enabled);s.capture();s.money();s._c1_quote(s.quote());assert len(s.submitted)==1


def test_default_off_source_config_and_policy_plumbing():
 text=(ROOT/'strategy/wave_overlay.py').read_text();assert 'research_c1_btc_postcut_d1: bool = False' in text
 tree=ast.parse((ROOT/'research/native_baseline.py').read_text());s=ast.unparse(tree)
 assert 'BTC_POSTCUT_D1_REQUIRES_FIRST_FRESH_COMBO' in s and 'args.research_c1_btc_postcut_d1' in s
 node=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and isinstance(n.test,ast.Name) and n.test.id=='research_c1_btc_postcut_d1')
 assert 'btc_postcut_d1' in ast.unparse(node)


@pytest.mark.parametrize('fault',['DD','price'])
def test_universal_firstfresh_signal_denial_still_consumes_before_day_execution_gate(fault):
 s=LiveOwner();s.capture();s.money();t=s._c1_state;credit=t['credit']
 if fault=='DD':s._c1_checkpoint['DD']=D('.41')
 q=s.quote(value='92000' if fault=='price' else None) # NOV short reclaim denial.
 s._c1_quote(q)
 assert not t.get('first_fresh_deferred') and t['confirmation'] is None
 assert t['credit']==credit and not t['restore_submitted'] and not s.submitted and not s.cancelled
 # A later observed D1 cannot resurrect the consumed first-fresh signal.
 q=s.at_day();s._c1_quote(q)
 assert t['confirmation'] is None and not s.submitted and t['credit']==credit
